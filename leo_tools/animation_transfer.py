import re
import json
import bpy
from bpy.types import Operator, Panel
from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

# pose.bones["BoneName"]["prop_name"] - bone custom property fcurve data path
CUSTOM_PROP_RE = re.compile(r'^pose\.bones\["(.+)"\]\["(.+)"\]$')
# ["prop_name"] - object custom property fcurve data path
OBJECT_CUSTOM_PROP_RE = re.compile(r'^\["(.+)"\]$')
TRANSFORM_CHANNELS = {
    "location": 3,
    "rotation_euler": 3,
    "rotation_quaternion": 4,
    "scale": 3,
}
# Keyframe attributes copied as-is (handle_left/right vectors are handled separately)
KEYFRAME_POINT_ATTRS = (
    "handle_left_type", "handle_right_type", "interpolation", "easing",
    "back", "amplitude", "period", "type",
)


def get_action_fcurves(action, armature=None):
    """Get fcurves from an action, supporting both legacy actions
    and the new layered/slotted action system (Blender 4.4+)."""
    if hasattr(action, "fcurves"):
        return list(action.fcurves)

    fcurves = []

    if hasattr(action, "layers"):
        target_slot = None
        if (armature is not None
                and armature.animation_data is not None
                and getattr(armature.animation_data, "action_slot", None) is not None):
            target_slot = armature.animation_data.action_slot

        for layer in action.layers:
            for strip in layer.strips:
                if hasattr(strip, "channelbags"):
                    for channelbag in strip.channelbags:
                        if target_slot is not None and channelbag.slot_handle != target_slot.handle:
                            continue
                        fcurves.extend(channelbag.fcurves)

    return fcurves


def get_custom_properties(id_data):
    """Return a JSON-serializable dict of an ID/bone's custom properties."""
    props = {}
    for key in id_data.keys():
        if key.startswith('_'):
            continue
        value = id_data[key]
        if isinstance(value, (int, float, str, bool)):
            props[key] = value
        else:
            try:
                props[key] = list(value)
            except TypeError:
                props[key] = str(value)
    return props


def set_custom_property(id_data, prop_name, value):
    """Assign a custom property, casting to the existing IDProperty's type
    (Blender rejects assigning a float to an existing Int property, etc.)."""
    if prop_name in id_data.keys():
        existing = id_data[prop_name]
        if isinstance(existing, bool):
            value = bool(value)
        elif isinstance(existing, int):
            value = int(round(value))
        elif isinstance(existing, float):
            value = float(value)
    id_data[prop_name] = value


def _classify_fcurve(data_path):
    """Return (scope, bone_name, prop) identifying what an action F-Curve
    targets, so it can be filed under the right bone/object/custom bucket."""
    if data_path in TRANSFORM_CHANNELS:
        return "object_transform", None, data_path

    match = OBJECT_CUSTOM_PROP_RE.match(data_path)
    if match:
        return "object_custom", None, match.group(1)

    if data_path.startswith("pose.bones["):
        prop = data_path.rsplit('.', 1)[-1]
        if prop in TRANSFORM_CHANNELS:
            return "bone_transform", data_path.split('"')[1], prop
        match = CUSTOM_PROP_RE.match(data_path)
        if match:
            return "bone_custom", match.group(1), match.group(2)

    return None, None, None


def _new_channels():
    return {
        "location": [None, None, None],
        "rotation_euler": [None, None, None],
        "rotation_quaternion": [None, None, None, None],
        "scale": [None, None, None],
        "custom": {},
    }


def _channels_animated(channels):
    transform_props = ("location", "rotation_euler", "rotation_quaternion", "scale")
    if any(fc is not None for prop in transform_props for fc in channels[prop]):
        return True
    return bool(channels["custom"])


def serialize_keyframe(keyframe):
    """Full keyframe data: co, both bezier handles, handle types, interpolation, easing..."""
    return {
        "co": list(keyframe.co),
        "handle_left": list(keyframe.handle_left),
        "handle_right": list(keyframe.handle_right),
        "handle_left_type": keyframe.handle_left_type,
        "handle_right_type": keyframe.handle_right_type,
        "interpolation": keyframe.interpolation,
        "easing": keyframe.easing,
        "back": keyframe.back,
        "amplitude": keyframe.amplitude,
        "period": keyframe.period,
        "type": keyframe.type,
    }


def serialize_fcurve(fcurve):
    return {
        "extrapolation": fcurve.extrapolation,
        "keyframes": [serialize_keyframe(kp) for kp in fcurve.keyframe_points],
    }


def serialize_channels(channels):
    """Convert a _new_channels()-shaped dict of live F-Curves to JSON data."""
    result = {
        prop: [serialize_fcurve(fc) if fc is not None else None for fc in channels[prop]]
        for prop in ("location", "rotation_euler", "rotation_quaternion", "scale")
    }
    result["custom"] = {name: serialize_fcurve(fc) for name, fc in channels["custom"].items()}
    return result


def insert_channel_keyframes(target, channels_data, base_path, frame_offset, style_tasks):
    """Insert keyframes for a bone's or the armature object's channels.
    Queues (data_path, index, fcurve_data) so bezier styling can be applied
    in a single batched pass once every F-Curve has been created."""
    for prop in ("location", "rotation_euler", "rotation_quaternion", "scale"):
        for index, fcurve_data in enumerate(channels_data.get(prop) or []):
            if fcurve_data is None:
                continue
            for kp_data in fcurve_data["keyframes"]:
                frame = kp_data["co"][0] + frame_offset
                getattr(target, prop)[index] = kp_data["co"][1]
                target.keyframe_insert(data_path=prop, index=index, frame=frame)
            data_path = f"{base_path}.{prop}" if base_path else prop
            style_tasks.append((data_path, index, fcurve_data))

    for prop_name, fcurve_data in (channels_data.get("custom") or {}).items():
        for kp_data in fcurve_data["keyframes"]:
            frame = kp_data["co"][0] + frame_offset
            set_custom_property(target, prop_name, kp_data["co"][1])
            target.keyframe_insert(data_path=f'["{prop_name}"]', frame=frame)
        data_path = f'{base_path}["{prop_name}"]' if base_path else f'["{prop_name}"]'
        style_tasks.append((data_path, 0, fcurve_data))


def apply_fcurve_styles(action, armature, style_tasks, frame_offset):
    """Restore extrapolation/handles/handle types/interpolation/easing on
    every F-Curve that insert_channel_keyframes() just created."""
    fcurve_lookup = {(fc.data_path, fc.array_index): fc for fc in get_action_fcurves(action, armature)}

    for data_path, index, fcurve_data in style_tasks:
        fcurve = fcurve_lookup.get((data_path, index))
        if fcurve is None:
            continue

        fcurve.extrapolation = fcurve_data.get("extrapolation", fcurve.extrapolation)

        by_frame = {
            round(kp_data["co"][0] + frame_offset): kp_data
            for kp_data in fcurve_data["keyframes"]
        }
        for kp in fcurve.keyframe_points:
            kp_data = by_frame.get(round(kp.co[0]))
            if kp_data is None:
                continue
            for attr in KEYFRAME_POINT_ATTRS:
                if attr in kp_data:
                    setattr(kp, attr, kp_data[attr])
            # Handle positions only stick for FREE/ALIGNED types (others are auto-computed)
            if "handle_left" in kp_data:
                kp.handle_left = kp_data["handle_left"]
            if "handle_right" in kp_data:
                kp.handle_right = kp_data["handle_right"]

        fcurve.update()


# EXPORT OPERATOR
class ANIM_OT_export_rotation_data(Operator, ExportHelper):
    """Export rotation animation data from armature"""
    bl_idname = "anim.export_rotation_data"
    bl_label = "Export Rotation Data"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    
    def invoke(self, context, event):
        return super().invoke(context, event)
    
    def execute(self, context):
        armature = context.active_object
        
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select an armature")
            return {'CANCELLED'}
        
        if not armature.animation_data or not armature.animation_data.action:
            self.report({'ERROR'}, "Armature has no animation data")
            return {'CANCELLED'}
        
        # Export animation data
        bone_count, object_animated = self.export_armature_animation(
            armature, 
            self.filepath
        )

        if bone_count > 0 or object_animated:
            parts = []
            if bone_count > 0:
                parts.append(f"{bone_count} bones")
            if object_animated:
                parts.append("object transform")
            self.report({'INFO'}, f"Exported {' and '.join(parts)} to {self.filepath}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No animated bones found")
            return {'CANCELLED'}
    
    def export_armature_animation(self, armature, filepath):
        """Export all bones with keyframes from an armature, plus the
        armature object's own transform if it is animated too.

        Full F-Curve fidelity is preserved (keyframe co, both bezier handles,
        handle types, interpolation, easing, extrapolation) - nothing is
        resampled, and no scene.frame_set/depsgraph evaluation is needed."""
        action = armature.animation_data.action

        bones = {}
        object_channels = _new_channels()
        min_frame = float('inf')
        max_frame = float('-inf')

        for fcurve in get_action_fcurves(action, armature):
            scope, bone_name, prop = _classify_fcurve(fcurve.data_path)
            if scope is None:
                continue

            for keyframe in fcurve.keyframe_points:
                frame = keyframe.co[0]
                if frame < min_frame:
                    min_frame = frame
                if frame > max_frame:
                    max_frame = frame

            if scope == "object_transform":
                if 0 <= fcurve.array_index < TRANSFORM_CHANNELS[prop]:
                    object_channels[prop][fcurve.array_index] = fcurve
            elif scope == "object_custom":
                object_channels["custom"][prop] = fcurve
            elif scope == "bone_transform":
                entry = bones.setdefault(bone_name, _new_channels())
                if 0 <= fcurve.array_index < TRANSFORM_CHANNELS[prop]:
                    entry[prop][fcurve.array_index] = fcurve
            elif scope == "bone_custom":
                entry = bones.setdefault(bone_name, _new_channels())
                entry["custom"][prop] = fcurve

        # Handle case with no keyframes
        if min_frame == float('inf'):
            min_frame, max_frame = 0, 0
        else:
            min_frame, max_frame = int(round(min_frame)), int(round(max_frame))

        data = {
            "armature": armature.name,
            "action": action.name,
            "frame_range": [min_frame, max_frame],
            "object_custom_properties": get_custom_properties(armature),
            "bones": {}
        }

        # Armature object's own transform animation
        if _channels_animated(object_channels):
            data["object_animation"] = {
                "rotation_mode": armature.rotation_mode,
                "channels": serialize_channels(object_channels),
            }

        for bone_name, channels in bones.items():
            if bone_name not in armature.pose.bones or not _channels_animated(channels):
                continue

            pose_bone = armature.pose.bones[bone_name]
            data["bones"][bone_name] = {
                "rotation_mode": pose_bone.rotation_mode,
                "custom_properties": get_custom_properties(pose_bone),
                "channels": serialize_channels(channels),
            }

        # Write to file
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        return len(data["bones"]), "object_animation" in data


# IMPORT OPERATOR
class ANIM_OT_import_rotation_data(Operator, ImportHelper):
    """Import rotation animation data to armature"""
    bl_idname = "anim.import_rotation_data"
    bl_label = "Import Rotation Data"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    
    frame_offset: IntProperty(
        name="Frame Offset",
        description="Offset imported frames by this amount",
        default=0
    )
    
    clear_existing: BoolProperty(
        name="Clear Existing Animation",
        description="Clear existing animation before importing",
        default=False
    )
    
    def execute(self, context):
        armature = context.active_object
        
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select an armature")
            return {'CANCELLED'}
        
        # Import animation data
        bone_count, object_animated = self.import_armature_animation(
            armature, 
            self.filepath, 
            self.frame_offset,
            self.clear_existing
        )

        if bone_count > 0 or object_animated:
            parts = []
            if bone_count > 0:
                parts.append(f"{bone_count} bones")
            if object_animated:
                parts.append("object transform")
            self.report({'INFO'}, f"Imported animation for {' and '.join(parts)}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No bones were imported")
            return {'CANCELLED'}
    
    def import_armature_animation(self, armature, filepath, frame_offset, clear_existing):
        """Import animation data to armature, rebuilding original bezier
        handles/handle types/interpolation/easing/extrapolation exactly."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read file: {str(e)}")
            return 0, False
        
        # Clear existing animation if requested
        if clear_existing and armature.animation_data:
            if armature.animation_data.action:
                bpy.data.actions.remove(armature.animation_data.action)
        
        # Ensure armature has animation data
        if not armature.animation_data:
            armature.animation_data_create()

        for prop_name, value in data.get("object_custom_properties", {}).items():
            set_custom_property(armature, prop_name, value)

        style_tasks = []

        object_animated = False
        object_animation = data.get("object_animation")
        if object_animation:
            armature.rotation_mode = object_animation["rotation_mode"]
            insert_channel_keyframes(armature, object_animation["channels"], "", frame_offset, style_tasks)
            object_animated = True

        imported_count = 0

        for source_bone, bone_data in data["bones"].items():
            if source_bone not in armature.pose.bones:
                print(f"Warning: Bone '{source_bone}' not found in target armature, skipping")
                continue
            
            pose_bone = armature.pose.bones[source_bone]
            pose_bone.rotation_mode = bone_data["rotation_mode"]

            for prop_name, value in bone_data.get("custom_properties", {}).items():
                set_custom_property(pose_bone, prop_name, value)

            insert_channel_keyframes(
                pose_bone, bone_data["channels"], f'pose.bones["{source_bone}"]', frame_offset, style_tasks
            )

            imported_count += 1

        action = armature.animation_data.action
        if action is not None:
            apply_fcurve_styles(action, armature, style_tasks, frame_offset)

        return imported_count, object_animated


# UI PANEL
class ANIM_PT_transfer_panel(Panel):
    """Panel for animation transfer tools"""
    bl_label = "Animation Transfer"
    bl_idname = "ANIM_PT_transfer_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Anim Transfer'
    
    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        # Info box
        box = layout.box()
        if obj and obj.type == 'ARMATURE':
            box.label(text=f"Armature: {obj.name}", icon='ARMATURE_DATA')
            if obj.animation_data and obj.animation_data.action:
                box.label(text=f"Action: {obj.animation_data.action.name}", icon='ACTION')
            else:
                box.label(text="No animation data", icon='ERROR')
        else:
            box.label(text="Select an armature", icon='INFO')
        
        layout.separator()
        
        # Export section
        box = layout.box()
        box.label(text="Export Animation", icon='EXPORT')
        col = box.column(align=True)
        col.operator("anim.export_rotation_data", text="Export to File", icon='DISK_DRIVE')
        
        layout.separator()
        
        # Import section
        box = layout.box()
        box.label(text="Import Animation", icon='IMPORT')
        col = box.column(align=True)
        col.operator("anim.import_rotation_data", text="Import from File", icon='FILE_FOLDER')


# REGISTRATION
classes = (
    ANIM_OT_export_rotation_data,
    ANIM_OT_import_rotation_data,
    ANIM_PT_transfer_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
