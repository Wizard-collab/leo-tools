"""
Render Tools
Export/import render settings and view layers (name, render passes, and
per-collection holdout/indirect/visibility settings) to/from JSON, so they
can be transferred between scenes. Missing view layers are created on import.
"""

import json
import bpy
from bpy.types import Operator, Panel
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper


OUTPUT_SETTINGS = {
    "resolution_x", "resolution_y", "resolution_percentage",
    "pixel_aspect_x", "pixel_aspect_y", "filepath", "image_settings",
    "ffmpeg", "frame_map_old", "frame_map_new", "use_file_extension",
    "use_overwrite", "use_placeholder",
}


def get_rna_settings(owner, excluded=None):
    """Collect JSON-compatible writable scalar properties from an RNA owner."""
    settings = {}
    excluded = excluded or set()
    for prop in owner.bl_rna.properties:
        if (prop.identifier == "rna_type" or prop.identifier in excluded
                or prop.is_readonly):
            continue
        if prop.type not in {'BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM'}:
            continue

        value = getattr(owner, prop.identifier)
        if getattr(prop, "array_length", 0) > 0:
            value = list(value)
        settings[prop.identifier] = value
    return settings


def get_render_settings(scene):
    """Collect settings shown in Render Properties, excluding Output Properties."""
    settings = {
        "render": get_rna_settings(scene.render, OUTPUT_SETTINGS),
    }
    for owner_name in ("cycles", "eevee"):
        owner = getattr(scene, owner_name, None)
        if owner is not None:
            settings[owner_name] = get_rna_settings(owner)
    return settings


def apply_render_settings(scene, settings):
    """Apply exported Render Properties supported by the current Blender version."""
    owners = {"render": scene.render}
    for owner_name in ("cycles", "eevee"):
        owner = getattr(scene, owner_name, None)
        if owner is not None:
            owners[owner_name] = owner

    if "render" not in settings and "cycles" not in settings and "eevee" not in settings:
        settings = {"render": settings}

    for owner_name, owner_settings in settings.items():
        owner = owners.get(owner_name)
        if owner is None:
            continue
        excluded = OUTPUT_SETTINGS if owner_name == "render" else set()
        for key, value in owner_settings.items():
            prop = owner.bl_rna.properties.get(key)
            if (prop is None or prop.identifier in excluded
                    or prop.is_readonly):
                continue
            try:
                setattr(owner, key, value)
            except (AttributeError, TypeError, ValueError):
                # Render properties vary by Blender version and render engine.
                continue


def get_pass_settings(view_layer):
    """Collect every 'use_pass_*' toggle on the view layer, plus its
    engine-specific settings (e.g. Cycles), without hardcoding a pass list
    so it stays valid across Blender versions/render engines."""
    passes = {
        prop.identifier: getattr(view_layer, prop.identifier)
        for prop in view_layer.bl_rna.properties
        if prop.identifier.startswith("use_pass")
    }

    cycles_settings = getattr(view_layer, "cycles", None)
    if cycles_settings is not None:
        cycles_passes = {
            prop.identifier: getattr(cycles_settings, prop.identifier)
            for prop in cycles_settings.bl_rna.properties
            if prop.identifier.startswith("use_pass") or prop.identifier.startswith("denoising")
        }
        if cycles_passes:
            passes["cycles"] = cycles_passes

    return passes


def apply_pass_settings(view_layer, passes):
    """Apply previously collected pass toggles back onto a view layer."""
    for key, value in passes.items():
        if key == "cycles":
            continue
        if hasattr(view_layer, key):
            setattr(view_layer, key, value)

    cycles_settings = getattr(view_layer, "cycles", None)
    cycles_passes = passes.get("cycles")
    if cycles_settings is not None and cycles_passes:
        for key, value in cycles_passes.items():
            if hasattr(cycles_settings, key):
                setattr(cycles_settings, key, value)


def flatten_layer_collections(layer_collection, result, is_root=True,
                              inherited_settings=None):
    """Store hierarchical render flags at their highest enabled collection."""
    inherited_settings = inherited_settings or {
        "exclude": False,
        "holdout": False,
        "indirect_only": False,
    }

    if not is_root:
        current_settings = {
            "exclude": layer_collection.exclude,
            "holdout": layer_collection.holdout,
            "indirect_only": layer_collection.indirect_only,
        }
        result[layer_collection.collection.name] = {
            setting: True
            for setting, enabled in current_settings.items()
            if enabled and not inherited_settings[setting]
        }
        inherited_settings = {
            setting: inherited_settings[setting] or current_settings[setting]
            for setting in inherited_settings
        }

    for child in layer_collection.children:
        flatten_layer_collections(child, result, False, inherited_settings)


def find_layer_collection(layer_collection, name):
    """Recursively find the LayerCollection matching a collection name."""
    if layer_collection.collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        found = find_layer_collection(child, name)
        if found is not None:
            return found
    return None


def set_collection_setting_recursive(layer_collection, setting, value):
    """Set a collection render flag on a collection and its descendants."""
    setattr(layer_collection, setting, value)
    for child in layer_collection.children:
        set_collection_setting_recursive(child, setting, value)


def clear_hierarchical_settings(layer_collection):
    """Clear hierarchical render flags before applying the exported hierarchy."""
    for child in layer_collection.children:
        for setting in ("exclude", "holdout", "indirect_only"):
            set_collection_setting_recursive(child, setting, False)


def apply_collection_settings(view_layer, collections_data, stats):
    """Apply exported exclude, holdout, and indirect-only hierarchy settings."""
    clear_hierarchical_settings(view_layer.layer_collection)

    for name, settings in collections_data.items():
        layer_collection = find_layer_collection(view_layer.layer_collection, name)
        if layer_collection is None:
            stats["skipped"] += 1
            continue
        for setting in ("exclude", "holdout", "indirect_only"):
            if settings.get(setting, False):
                set_collection_setting_recursive(layer_collection, setting, True)
        stats["applied"] += 1


# EXPORT OPERATOR
class LEO_TOOLS_OT_export_view_layers(Operator, ExportHelper):
    """Export render settings and view layers to a JSON file."""
    bl_idname = "leo_tools.export_view_layers"
    bl_label = "Export View Layers"
    bl_options = {'REGISTER'}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        self.filepath = f"{context.scene.name}_view_layers.json"
        return super().invoke(context, event)

    def execute(self, context):
        scene = context.scene

        view_layers_data = {}
        for view_layer in scene.view_layers:
            collections = {}
            flatten_layer_collections(view_layer.layer_collection, collections)
            view_layers_data[view_layer.name] = {
                "passes": get_pass_settings(view_layer),
                "collections": collections,
            }

        data = {
            "scene": scene.name,
            "render_settings": get_render_settings(scene),
            "view_layers": view_layers_data,
        }

        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)

        self.report({'INFO'}, f"Exported {len(view_layers_data)} view layer(s) to {self.filepath}")
        return {'FINISHED'}


# IMPORT OPERATOR
class LEO_TOOLS_OT_import_view_layers(Operator, ImportHelper):
    """Import render settings and view layers from a JSON file."""
    bl_idname = "leo_tools.import_view_layers"
    bl_label = "Import View Layers"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        scene = context.scene

        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read file: {str(e)}")
            return {'CANCELLED'}

        view_layers_data = data.get("view_layers", {})
        if not view_layers_data:
            self.report({'ERROR'}, "JSON contains no view layers; Blender requires at least one")
            return {'CANCELLED'}

        stats = {"applied": 0, "skipped": 0}
        created = 0
        removed = 0

        apply_render_settings(scene, data.get("render_settings", {}))

        imported_names = set(view_layers_data)
        imported_layers = {}
        for view_layer_name, view_layer_data in view_layers_data.items():
            view_layer = scene.view_layers.get(view_layer_name)
            if view_layer is None:
                view_layer = scene.view_layers.new(name=view_layer_name)
                created += 1
            imported_layers[view_layer_name] = view_layer

        active_view_layer = next(iter(imported_layers.values()))
        for window in bpy.context.window_manager.windows:
            if window.scene == scene:
                window.view_layer = active_view_layer

        for view_layer in list(scene.view_layers):
            if view_layer.name not in imported_names:
                scene.view_layers.remove(view_layer)
                removed += 1

        for view_layer_name, view_layer_data in view_layers_data.items():
            view_layer = imported_layers[view_layer_name]
            apply_pass_settings(view_layer, view_layer_data.get("passes", {}))
            apply_collection_settings(view_layer, view_layer_data.get("collections", {}), stats)

        self.report(
            {'INFO'},
            f"Imported {len(view_layers_data)} view layer(s) ({created} created, {removed} removed): "
            f"{stats['applied']} collections applied, {stats['skipped']} skipped (not found)"
        )
        return {'FINISHED'}


# UI PANEL
class RENDER_TOOLS_PT_panel(Panel):
    """Panel for render tools"""
    bl_label = "Render Tools"
    bl_idname = "RENDER_TOOLS_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Render Tools"

    def draw(self, context):
        layout = self.layout
        layout.label(text="View Layers")
        layout.operator("leo_tools.export_view_layers", text="Export View Layers", icon='EXPORT')
        layout.operator("leo_tools.import_view_layers", text="Import View Layers", icon='IMPORT')


classes = (
    LEO_TOOLS_OT_export_view_layers,
    LEO_TOOLS_OT_import_view_layers,
    RENDER_TOOLS_PT_panel,
)


def register():
    for cls in classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
