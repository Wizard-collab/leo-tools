"""
Debug Bone Rotation - Test script to capture bone rotation values
"""

import bpy
import math


class POSE_OT_debug_bone_rotation(bpy.types.Operator):
    """Debug: Print bone rotation in different ways"""
    bl_idname = "pose.debug_bone_rotation"
    bl_label = "Debug Bone Rotation"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and 
                context.active_pose_bone is not None)
    
    def execute(self, context):
        bone = context.active_pose_bone
        armature = context.active_object
        
        print("\n" + "="*60)
        print(f"DEBUG: Bone Rotation for {armature.name}:{bone.name}")
        print("="*60)
        
        # Method 1: rotation_euler
        print("\n1. bone.rotation_euler:")
        print(f"   X: {bone.rotation_euler.x} rad ({math.degrees(bone.rotation_euler.x):.2f}°)")
        print(f"   Y: {bone.rotation_euler.y} rad ({math.degrees(bone.rotation_euler.y):.2f}°)")
        print(f"   Z: {bone.rotation_euler.z} rad ({math.degrees(bone.rotation_euler.z):.2f}°)")
        
        # Method 2: matrix_basis
        print("\n2. bone.matrix_basis.to_euler():")
        euler = bone.matrix_basis.to_euler()
        print(f"   X: {euler.x} rad ({math.degrees(euler.x):.2f}°)")
        print(f"   Y: {euler.y} rad ({math.degrees(euler.y):.2f}°)")
        print(f"   Z: {euler.z} rad ({math.degrees(euler.z):.2f}°)")
        
        # Method 3: matrix
        print("\n3. bone.matrix.to_euler():")
        euler = bone.matrix.to_euler()
        print(f"   X: {euler.x} rad ({math.degrees(euler.x):.2f}°)")
        print(f"   Y: {euler.y} rad ({math.degrees(euler.y):.2f}°)")
        print(f"   Z: {euler.z} rad ({math.degrees(euler.z):.2f}°)")
        
        # Method 4: Check rotation mode
        print(f"\n4. Rotation Mode: {bone.rotation_mode}")
        
        # Method 5: Try quaternion if that's the mode
        if bone.rotation_mode == 'QUATERNION':
            print("\n5. bone.rotation_quaternion to euler:")
            euler = bone.rotation_quaternion.to_euler()
            print(f"   X: {euler.x} rad ({math.degrees(euler.x):.2f}°)")
            print(f"   Y: {euler.y} rad ({math.degrees(euler.y):.2f}°)")
            print(f"   Z: {euler.z} rad ({math.degrees(euler.z):.2f}°)")
        
        # Method 6: Check if bone has parent and constraints
        print(f"\n6. Bone parent: {bone.parent.name if bone.parent else 'None'}")
        print(f"   Constraints: {len(bone.constraints)}")
        
        # Method 7: Try to get local rotation AFTER constraints (like driver does)
        print("\n7. Post-constraint local rotation (matrix relative to rest):")
        pose_bone = bone
        rest_bone = armature.data.bones[bone.name]
        
        # Get the final pose matrix and the rest matrix
        if pose_bone.parent:
            # Local matrix = parent's final matrix inverse @ bone's final matrix
            parent_matrix = pose_bone.parent.matrix
            local_pose_matrix = parent_matrix.inverted() @ pose_bone.matrix
            
            # Get rest local matrix
            parent_rest = rest_bone.parent.matrix_local
            local_rest_matrix = parent_rest.inverted() @ rest_bone.matrix_local
        else:
            # No parent, use armature space
            local_pose_matrix = pose_bone.matrix
            local_rest_matrix = rest_bone.matrix_local
        
        # Get rotation difference: rest_inverse @ pose
        rotation_matrix = local_rest_matrix.inverted() @ local_pose_matrix
        rotation_euler = rotation_matrix.to_euler()
        
        print(f"   X: {rotation_euler.x} rad ({math.degrees(rotation_euler.x):.2f}°)")
        print(f"   Y: {rotation_euler.y} rad ({math.degrees(rotation_euler.y):.2f}°)")
        print(f"   Z: {rotation_euler.z} rad ({math.degrees(rotation_euler.z):.2f}°)")
        
        print("\n" + "="*60)
        
        self.report({'INFO'}, "Check console for rotation values")
        return {'FINISHED'}


class VIEW3D_PT_debug_bone_rotation_panel(bpy.types.Panel):
    """Debug panel"""
    bl_label = "Debug Bone Rotation"
    bl_idname = "VIEW3D_PT_debug_bone_rotation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Leo Tools'
    
    def draw(self, context):
        layout = self.layout
        
        if context.mode == 'POSE' and context.active_pose_bone:
            bone = context.active_pose_bone
            armature = context.active_object
            
            box = layout.box()
            box.label(text=f"Armature: {armature.name}")
            box.label(text=f"Bone: {bone.name}")
            box.label(text=f"Mode: {bone.rotation_mode}")
            
            layout.operator("pose.debug_bone_rotation", 
                          text="Print Rotation Values", 
                          icon='CONSOLE')
        else:
            layout.label(text="Enter Pose Mode", icon='ERROR')


def register():
    bpy.utils.register_class(POSE_OT_debug_bone_rotation)
    bpy.utils.register_class(VIEW3D_PT_debug_bone_rotation_panel)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_debug_bone_rotation_panel)
    bpy.utils.unregister_class(POSE_OT_debug_bone_rotation)


if __name__ == "__main__":
    register()
