import json
import bpy
from bpy.types import Operator, Panel
from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper


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
        result = self.export_armature_animation(
            armature, 
            self.filepath
        )
        
        if result > 0:
            self.report({'INFO'}, f"Exported {result} animated bones to {self.filepath}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No animated bones found")
            return {'CANCELLED'}
    
    def export_armature_animation(self, armature, filepath):
        """Export all bones with keyframes from an armature"""
        action = armature.animation_data.action
        
        # Organize fcurves by bone and find frame range
        bone_fcurves = {}
        min_frame = float('inf')
        max_frame = float('-inf')
        
        for fcurve in action.fcurves:
            if fcurve.data_path.startswith("pose.bones["):
                bone_name = fcurve.data_path.split('"')[1]
                if any(prop in fcurve.data_path for prop in ["location", "rotation", "scale"]):
                    if bone_name not in bone_fcurves:
                        bone_fcurves[bone_name] = []
                    bone_fcurves[bone_name].append(fcurve)
                    
                    # Track min/max frames
                    for keyframe in fcurve.keyframe_points:
                        frame = int(keyframe.co[0])
                        min_frame = min(min_frame, frame)
                        max_frame = max(max_frame, frame)
        
        # Handle case with no keyframes
        if min_frame == float('inf'):
            min_frame = 0
            max_frame = 0
        
        data = {
            "armature": armature.name,
            "action": action.name,
            "frame_range": [min_frame, max_frame],
            "bones": {}
        }
        
        # Export keyframe data for each animated bone
        scene = bpy.context.scene
        current_frame = scene.frame_current
        
        for bone_name, fcurves in bone_fcurves.items():
            if bone_name not in armature.pose.bones:
                continue
            
            pose_bone = armature.pose.bones[bone_name]
            
            # Collect all unique keyframe frames for this bone
            keyframe_frames = set()
            for fcurve in fcurves:
                for keyframe in fcurve.keyframe_points:
                    frame = int(keyframe.co[0])
                    keyframe_frames.add(frame)
            
            if not keyframe_frames:
                continue
            
            bone_data = {
                "rotation_mode": pose_bone.rotation_mode,
                "keyframes": []
            }
            
            # Get location, rotation, and scale values at each keyframe
            for frame in sorted(keyframe_frames):
                scene.frame_set(frame)
                bone_data["keyframes"].append({
                    "frame": frame,
                    "location": list(pose_bone.location),
                    "rotation_euler": list(pose_bone.rotation_euler),
                    "rotation_quaternion": list(pose_bone.rotation_quaternion),
                    "scale": list(pose_bone.scale)
                })
            
            data["bones"][bone_name] = bone_data
        
        # Restore original frame
        scene.frame_set(current_frame)
        
        # Write to file
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        return len(bone_fcurves)


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
        result = self.import_armature_animation(
            armature, 
            self.filepath, 
            self.frame_offset,
            self.clear_existing
        )
        
        if result > 0:
            self.report({'INFO'}, f"Imported animation for {result} bones")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No bones were imported")
            return {'CANCELLED'}
    
    def import_armature_animation(self, armature, filepath, frame_offset, clear_existing):
        """Import animation data to armature"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read file: {str(e)}")
            return 0
        
        # Clear existing animation if requested
        if clear_existing and armature.animation_data:
            if armature.animation_data.action:
                bpy.data.actions.remove(armature.animation_data.action)
        
        # Ensure armature has animation data
        if not armature.animation_data:
            armature.animation_data_create()
        
        imported_count = 0
        scene = bpy.context.scene
        current_frame = scene.frame_current
        
        for source_bone, bone_data in data["bones"].items():
            if source_bone not in armature.pose.bones:
                print(f"Warning: Bone '{source_bone}' not found in target armature, skipping")
                continue
            
            pose_bone = armature.pose.bones[source_bone]
            pose_bone.rotation_mode = bone_data["rotation_mode"]
            
            # Import only keyframes (not every frame)
            for keyframe_data in bone_data["keyframes"]:
                frame = keyframe_data["frame"] + frame_offset
                scene.frame_set(frame)
                
                # Apply location
                if "location" in keyframe_data:
                    pose_bone.location = keyframe_data["location"]
                    pose_bone.keyframe_insert(data_path="location", frame=frame)
                
                # Apply rotation
                if pose_bone.rotation_mode == 'QUATERNION':
                    pose_bone.rotation_quaternion = keyframe_data["rotation_quaternion"]
                    pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
                else:
                    pose_bone.rotation_euler = keyframe_data["rotation_euler"]
                    pose_bone.keyframe_insert(data_path="rotation_euler", frame=frame)
                
                # Apply scale
                if "scale" in keyframe_data:
                    pose_bone.scale = keyframe_data["scale"]
                    pose_bone.keyframe_insert(data_path="scale", frame=frame)
            
            imported_count += 1
        
        # Restore original frame
        scene.frame_set(current_frame)
        
        return imported_count


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
