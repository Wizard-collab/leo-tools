"""
Render Tools
Export/import view layers (name, render passes, and per-collection
holdout/indirect/visibility settings) to/from JSON, so they can be
transferred between scenes. Missing view layers are created on import.
"""

import json
import bpy
from bpy.types import Operator, Panel
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper


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


def flatten_layer_collections(layer_collection, result, is_root=True):
    """Flatten a view layer's collection tree to {collection_name: settings},
    skipping the root master collection which has no meaningful toggles."""
    if not is_root:
        result[layer_collection.collection.name] = {
            "exclude": layer_collection.exclude,
            "holdout": layer_collection.holdout,
            "indirect_only": layer_collection.indirect_only,
            "hide_viewport": layer_collection.hide_viewport,
        }
    for child in layer_collection.children:
        flatten_layer_collections(child, result, False)


def find_layer_collection(layer_collection, name):
    """Recursively find the LayerCollection matching a collection name."""
    if layer_collection.collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        found = find_layer_collection(child, name)
        if found is not None:
            return found
    return None


def apply_collection_settings(view_layer, collections_data, stats):
    """Apply saved holdout/indirect/visibility settings to collections that
    exist in the target view layer, skipping (and counting) the rest."""
    for name, settings in collections_data.items():
        layer_collection = find_layer_collection(view_layer.layer_collection, name)
        if layer_collection is None:
            stats["skipped"] += 1
            continue
        layer_collection.exclude = settings.get("exclude", layer_collection.exclude)
        layer_collection.holdout = settings.get("holdout", layer_collection.holdout)
        layer_collection.indirect_only = settings.get("indirect_only", layer_collection.indirect_only)
        layer_collection.hide_viewport = settings.get("hide_viewport", layer_collection.hide_viewport)
        stats["applied"] += 1


# EXPORT OPERATOR
class LEO_TOOLS_OT_export_view_layers(Operator, ExportHelper):
    """Export view layers (names, render passes, per-collection holdout/indirect/visibility) to a JSON file"""
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
            "view_layers": view_layers_data,
        }

        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)

        self.report({'INFO'}, f"Exported {len(view_layers_data)} view layer(s) to {self.filepath}")
        return {'FINISHED'}


# IMPORT OPERATOR
class LEO_TOOLS_OT_import_view_layers(Operator, ImportHelper):
    """Import view layers from a JSON file, creating any that don't already exist"""
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

        stats = {"applied": 0, "skipped": 0}
        created = 0

        for view_layer_name, view_layer_data in data.get("view_layers", {}).items():
            view_layer = scene.view_layers.get(view_layer_name)
            if view_layer is None:
                view_layer = scene.view_layers.new(name=view_layer_name)
                created += 1

            apply_pass_settings(view_layer, view_layer_data.get("passes", {}))
            apply_collection_settings(view_layer, view_layer_data.get("collections", {}), stats)

        self.report(
            {'INFO'},
            f"Imported {len(data.get('view_layers', {}))} view layer(s) ({created} created): "
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
