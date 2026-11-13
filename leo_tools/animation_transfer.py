import re
import json
import mathutils
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

# Marker used in the "export all" file to distinguish it from a single-armature export
ALL_EXPORT_TYPE = "anim_export_all"


def _json_safe(obj):
    """Recursively coerce values into plain JSON-serializable types.
    Blender mathutils types (Vector, Matrix, Euler, Quaternion...) are turned
    into nested lists of floats; anything else unsupported becomes a string."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    # mathutils types convert via to_list() (Vector, Matrix, Euler, Quaternion)
    if hasattr(obj, "to_list") and callable(getattr(obj, "to_list", None)):
        obj = obj.to_list()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    try:
        return [_json_safe(v) for v in obj]
    except TypeError:
        return str(obj)


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


# CONSTRAINT DEFINITION HELPERS ------------------------------------------------
# Constraint *animation* (influence, offsets...) is already handled by the generic
# custom-property channel, because Blender stores bone-constraint F-curves as
# pose-bone properties with paths like:
#     pose.bones["Bone"]["constraints[Ctrl].influence"]
# What this block adds is the constraint *definition* (type/settings/targets) so
# the constraint object exists with the right settings on import.

def serialize_constraint(constraint):
    """Serialize a single pose-bone constraint into a JSON-serializable dict,
    walking its RNA properties generically instead of hard-coding per type.
    Collection props (e.g. Armature.constraints.targets) are skipped for now."""
    data = {
        "name": constraint.name,
        "type": constraint.type,
        "mute": bool(constraint.mute),
        "settings": {},
    }

    skip = {"name", "type", "active", "show_expanded", "bl_rna", "rna_type"}

    for prop in constraint.bl_rna.properties:
        ident = prop.identifier
        if ident in skip or getattr(prop, "is_readonly", False):
            continue
        if prop.type == 'COLLECTION':
            # Collection-backed props aren't represented simply; skip them.
            continue
        try:
            if prop.type == 'POINTER':
                value = getattr(constraint, ident)
                data["settings"][ident] = {
                    "__pointer__": True,
                    "name": value.name if value else "",
                }
            elif isinstance(getattr(constraint, ident), mathutils.Matrix):
                # Matrix props (e.g. Child-Of inverse_matrix) are stored as a
                # flat 16-float list so they can be rebuilt exactly on import.
                mtx = getattr(constraint, ident)
                data["settings"][ident] = {
                    "__matrix__": True,
                    "data": [float(v) for row in mtx for v in row],
                }
            elif getattr(prop, "array_length", 0):
                data["settings"][ident] = _json_safe(getattr(constraint, ident))
            else:
                value = getattr(constraint, ident)
                if isinstance(value, (int, float, bool, str)):
                    data["settings"][ident] = value
        except Exception:
            continue

    return data


def serialize_bone_constraints(pose_bone):
    return [serialize_constraint(c) for c in pose_bone.constraints]


def _flatten(value):
    """Flatten a possibly-nested list of numbers into a single flat list."""
    flat = []
    for v in value:
        if isinstance(v, (list, tuple)):
            flat.extend(_flatten(v))
        else:
            flat.append(v)
    return flat


def _set_constraint_prop(constraint, ident, value, prop):
    """Apply a single constraint setting, tolerating pointers, matrices and
    array props. Each assignment is isolated so a bad value never aborts the
    import. Matrix props (stored via __matrix__) are rebuilt as mathutils
    Matrix objects and assigned whole, so they round-trip exactly."""
    try:
        if isinstance(value, dict) and value.get("__pointer__"):
            target = bpy.data.objects.get(value.get("name"))
            if target is not None:
                try:
                    setattr(constraint, ident, target)
                except Exception:
                    pass
            return

        if isinstance(value, dict) and value.get("__matrix__"):
            data16 = [float(v) for v in value.get("data", [])][:16]
            if len(data16) == 16:
                mtx = mathutils.Matrix([data16[i * 4:(i + 1) * 4] for i in range(4)])
                setattr(constraint, ident, mtx)
            return

        array_len = getattr(prop, "array_length", 0) if prop is not None else 0
        if array_len and isinstance(value, (list, tuple)):
            # Matrix-valued props may have been stored as nested 4x4 rows;
            # rebuild them as a Matrix so element slots aren't clobbered.
            if (array_len == 16 and value
                    and all(isinstance(v, (list, tuple)) for v in value)):
                flat = [float(v) for v in _flatten(value)][:16]
                if len(flat) == 16:
                    mtx = mathutils.Matrix([flat[i * 4:(i + 1) * 4] for i in range(4)])
                    setattr(constraint, ident, mtx)
                    return

            arr = getattr(constraint, ident)
            flat = _flatten(value)
            for i, v in enumerate(flat):
                if i < len(arr):
                    arr[i] = v
            return

        setattr(constraint, ident, value)
    except Exception:
        # Unsettable / unsupported property - skip it silently.
        pass


def apply_bone_constraints(pose_bone, stored_constraints):
    """Recreate/update a pose bone's constraints from stored definitions.
    Existing constraints are matched by name and updated; missing ones are
    created with the stored type. Extra constraints are left untouched."""
    for cdata in stored_constraints:
        name = cdata.get("name")
        ctype = cdata.get("type")

        constraint = pose_bone.constraints.get(name)
        if constraint is None and ctype:
            constraint = pose_bone.constraints.new(ctype)
        if constraint is None:
            continue

        try:
            if constraint.name != name:
                constraint.name = name
        except Exception:
            pass

        constraint.mute = bool(cdata.get("mute", constraint.mute))
        prop_map = {p.identifier: p for p in constraint.bl_rna.properties}
        for ident, value in cdata.get("settings", {}).items():
            _set_constraint_prop(constraint, ident, value, prop_map.get(ident))


# SHARED SERIALIZATION HELPERS -------------------------------------------------

def build_armature_export_data(armature, store_constraints=False):
    """Build the JSON-serializable export dict for a single armature, or None
    if it is not an armature or has no animation data.

    If store_constraints is True, each pose bone's constraint definitions are
    captured as well (constraint *animation* is always captured via the custom
    property channel).

    Note: armatures with no animation but with constraints will still be
    exported when store_constraints is enabled.

    Full F-Curve fidelity is preserved (keyframe co, both bezier handles,
    handle types, interpolation, easing, extrapolation) - nothing is
    resampled, and no scene.frame_set/depsgraph evaluation is needed."""
    if not armature or armature.type != 'ARMATURE':
        return None

    if not armature.animation_data or not armature.animation_data.action:
        if not store_constraints:
            return None
        # No animation to store, but the user asked for constraints - allow
        # exporting definitions only (bones/animation below will be empty).
        action = None
    else:
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
        "action": action.name if action else None,
        "frame_range": [min_frame, max_frame],
        "object_custom_properties": get_custom_properties(armature),
        "bones": {},
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

    # Constraint definitions (opt-in). These are stored per pose bone so they
    # can be reconstructed on import, giving constraint animation a target.
    if store_constraints:
        constraints_map = {}
        for pose_bone in armature.pose.bones:
            if pose_bone.constraints:
                constraints_map[pose_bone.name] = serialize_bone_constraints(pose_bone)
        if constraints_map:
            data["constraints"] = constraints_map

    return data


def apply_armature_import_data(armature, data, frame_offset=0, clear_existing=False):
    """Apply an armature export dict (as built by build_armature_export_data)
    to the given armature. Returns (imported_bone_count, object_animated)."""
    # Clear existing animation if requested
    if clear_existing and armature.animation_data:
        if armature.animation_data.action:
            bpy.data.actions.remove(armature.animation_data.action)

    # Ensure armature has animation data
    if not armature.animation_data:
        armature.animation_data_create()

    for prop_name, value in data.get("object_custom_properties", {}).items():
        set_custom_property(armature, prop_name, value)

    # Recreate constraints *before* animation so constraint F-curves have a
    # target to land on and the right names are in place.
    for bone_name, stored_constraints in data.get("constraints", {}).items():
        if bone_name not in armature.pose.bones:
            print(f"Warning: Bone '{bone_name}' has stored constraints but was not found, skipping")
            continue
        apply_bone_constraints(armature.pose.bones[bone_name], stored_constraints)

    style_tasks = []

    object_animated = False
    object_animation = data.get("object_animation")
    if object_animation:
        armature.rotation_mode = object_animation["rotation_mode"]
        insert_channel_keyframes(armature, object_animation["channels"], "", frame_offset, style_tasks)
        object_animated = True

    imported_count = 0

    for source_bone, bone_data in data.get("bones", {}).items():
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


# EXPORT OPERATOR --------------------------------------------------------------
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
        store_constraints = get_scene_store_constraints(context)
        
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select an armature")
            return {'CANCELLED'}

        has_data = bool(armature.animation_data and armature.animation_data.action) or store_constraints
        if not has_data:
            self.report({'ERROR'}, "Armature has no animation data")
            return {'CANCELLED'}
        
        # Export animation data
        bone_count, object_animated = self.export_armature_animation(
            armature,
            self.filepath,
            store_constraints,
        )

        # Constraint-only exports are still a success.
        if bone_count > 0 or object_animated or store_constraints:
            parts = []
            if bone_count > 0:
                parts.append(f"{bone_count} bones")
            if object_animated:
                parts.append("object transform")
            if store_constraints:
                parts.append("constraints")
            self.report({'INFO'}, f"Exported {' and '.join(parts)} to {self.filepath}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No animated bones found")
            return {'CANCELLED'}
    
    def export_armature_animation(self, armature, filepath, store_constraints=False):
        """Serialize one armature's animation (and optionally its constraints)
        and write it to a JSON file."""
        data = build_armature_export_data(armature, store_constraints=store_constraints)
        if data is None:
            return 0, False

        with open(filepath, 'w') as f:
            json.dump(_json_safe(data), f, indent=2)

        return len(data["bones"]), "object_animation" in data


# IMPORT OPERATOR --------------------------------------------------------------
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
        """Read a single-armature JSON export and apply it to the armature."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read file: {str(e)}")
            return 0, False

        return apply_armature_import_data(armature, data, frame_offset, clear_existing)


# EXPORT ALL OPERATOR ----------------------------------------------------------
class ANIM_OT_export_all_animations(Operator, ExportHelper):
    """Export animation data from every armature in the scene to one file"""
    bl_idname = "anim.export_all_animations"
    bl_label = "Export All Armature Animations"
    bl_description = "Export all armature animations from the current scene to a single file"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    
    def invoke(self, context, event):
        return super().invoke(context, event)
    
    @staticmethod
    def _scene_armatures(context):
        return (obj for obj in context.scene.objects if obj.type == 'ARMATURE')
    
    def execute(self, context):
        armatures = list(self._scene_armatures(context))
        if not armatures:
            self.report({'ERROR'}, "No armatures found in the scene")
            return {'CANCELLED'}

        store_constraints = get_scene_store_constraints(context)
        export_data = {"type": ALL_EXPORT_TYPE, "armatures": {}}
        skipped = []
        exported_count = 0

        for armature in armatures:
            data = build_armature_export_data(armature, store_constraints=store_constraints)
            if data is None:
                skipped.append(armature.name)
                continue
            export_data["armatures"][armature.name] = data
            exported_count += 1

        if exported_count == 0:
            self.report({'ERROR'}, "No armatures with exportable data found in the scene")
            return {'CANCELLED'}

        with open(self.filepath, 'w') as f:
            json.dump(_json_safe(export_data), f, indent=2)

        msg = f"Exported {'animations and constraints ' if store_constraints else 'animations '}"
        msg += f"from {exported_count} armature{'s' if exported_count != 1 else ''} to {self.filepath}"
        if skipped:
            reason = "without animation data" if not store_constraints else "without animation or constraints"
            msg += f" (skipped {len(skipped)} {reason})"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# IMPORT ALL OPERATOR ----------------------------------------------------------
class ANIM_OT_import_all_animations(Operator, ImportHelper):
    """Import animation data for all armatures from a single file"""
    bl_idname = "anim.import_all_animations"
    bl_label = "Import All Armature Animations"
    bl_description = "Import all armature animations from a single file, matching armatures by name"
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
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read file: {str(e)}")
            return {'CANCELLED'}

        if data.get("type") != ALL_EXPORT_TYPE:
            self.report({'ERROR'},
                        "Not an 'Export All' file. Use 'Import from File' with a single-armature export.")
            return {'CANCELLED'}

        scene_armatures = {obj.name: obj for obj in context.scene.objects if obj.type == 'ARMATURE'}

        imported_count = 0
        missing = []

        for name, armature_data in data.get("armatures", {}).items():
            armature = scene_armatures.get(name)
            if armature is None:
                missing.append(name)
                continue
            apply_armature_import_data(armature, armature_data, self.frame_offset, self.clear_existing)
            imported_count += 1

        if imported_count == 0:
            self.report({'WARNING'}, "No matching armatures were found/imported")
            return {'CANCELLED'}

        msg = f"Imported animations for {imported_count} matching armature{'s' if imported_count != 1 else ''}"
        if missing:
            msg += f" (no matching armature for: {', '.join(missing)})"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# UI PANEL ---------------------------------------------------------------------
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
        col.operator("anim.export_rotation_data", text="Export Selected Armature", icon='DISK_DRIVE')
        col.operator("anim.export_all_animations", text="Export All Scene Armatures", icon='NONE')
        box.prop(context.scene, "leo_anim_store_constraints", text="Store Constraints")
        
        layout.separator()
        
        # Import section
        box = layout.box()
        box.label(text="Import Animation", icon='IMPORT')
        col = box.column(align=True)
        col.operator("anim.import_rotation_data", text="Import to Selected Armature", icon='FILE_FOLDER')
        col.operator("anim.import_all_animations", text="Import All Scene Armatures", icon='NONE')
        
        layout.separator()
        
        # Hint for import-all matching
        box = layout.box()
        box.label(text="Import All matches armatures by name.", icon='INFO')
        box.label(text="Armatures missing from the scene are skipped.")


# SCENE PROPERTY -----------------------------------------------------------------
# Boolean toggle shared by both export operators. Kept as a Scene property so the
# panel can display it without relying on operator button property access.
SCENE_STORE_CONSTRAINTS_ATTR = "leo_anim_store_constraints"


def get_scene_store_constraints(context):
    """Return whether constraint definitions should be stored on export."""
    return bool(getattr(context.scene, SCENE_STORE_CONSTRAINTS_ATTR, False))


def register_properties():
    from bpy.types import Scene
    if hasattr(Scene, SCENE_STORE_CONSTRAINTS_ATTR):
        return
    Scene.leo_anim_store_constraints = BoolProperty(
        name="Store Constraints",
        description="Also store each bone's constraint definitions on export. "
                    "Target objects are restored by name on import",
        default=False,
    )


def unregister_properties():
    from bpy.types import Scene
    if hasattr(Scene, SCENE_STORE_CONSTRAINTS_ATTR):
        del Scene.leo_anim_store_constraints


# REGISTRATION
classes = (
    ANIM_OT_export_rotation_data,
    ANIM_OT_import_rotation_data,
    ANIM_OT_export_all_animations,
    ANIM_OT_import_all_animations,
    ANIM_PT_transfer_panel,
)


def register():
    register_properties()
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_properties()


if __name__ == "__main__":
    register()
