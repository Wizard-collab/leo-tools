"""
Corrective Shape Key Creator
Creates shape keys driven by bone rotations with automatic driver setup
"""

import bpy
from bpy.props import StringProperty, EnumProperty, FloatProperty, BoolProperty
from bpy.types import Operator, Panel
import math


class MESH_OT_create_corrective_shapekey(Operator):
    """Create a corrective shape key driven by bone rotation"""
    bl_idname = "mesh.create_corrective_shapekey"
    bl_label = "Create Corrective Shape Key"
    bl_options = {'REGISTER', 'UNDO'}
    
    shapekey_name: StringProperty(
        name="Shape Key Name",
        description="Name for the new shape key",
        default="Corrective"
    )
    
    use_x_axis: BoolProperty(
        name="X Axis",
        description="Drive by X axis rotation",
        default=True
    )
    
    use_y_axis: BoolProperty(
        name="Y Axis",
        description="Drive by Y axis rotation",
        default=False
    )
    
    use_z_axis: BoolProperty(
        name="Z Axis",
        description="Drive by Z axis rotation",
        default=False
    )
    
    # Store rotation values captured in invoke (hidden from UI)
    stored_rotation_x: FloatProperty(options={'HIDDEN'})
    stored_rotation_y: FloatProperty(options={'HIDDEN'})
    stored_rotation_z: FloatProperty(options={'HIDDEN'})
    stored_armature_name: StringProperty(options={'HIDDEN'})
    stored_bone_name: StringProperty(options={'HIDDEN'})
    
    @classmethod
    def poll(cls, context):
        # Check if we're in pose mode with an active bone and have a selected mesh
        return (context.mode == 'POSE' and 
                context.active_pose_bone is not None)
    
    def execute(self, context):
        # Use stored armature and bone info
        armature_obj = bpy.data.objects.get(self.stored_armature_name)
        bone_name = self.stored_bone_name
        
        if armature_obj is None or bone_name == "":
            self.report({'ERROR'}, "Stored bone information is missing.")
            return {'CANCELLED'}
        
        # Find the mesh object (look for selected mesh or mesh with armature modifier)
        mesh_obj = None
        
        # First, check selected objects for a mesh
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj != armature_obj:
                mesh_obj = obj
                break
        
        # If no mesh selected, look for meshes with armature modifier pointing to current armature
        if mesh_obj is None:
            for obj in bpy.data.objects:
                if obj.type == 'MESH':
                    for mod in obj.modifiers:
                        if mod.type == 'ARMATURE' and mod.object == armature_obj:
                            mesh_obj = obj
                            break
                    if mesh_obj:
                        break
        
        if mesh_obj is None:
            self.report({'ERROR'}, "No mesh found. Please select a mesh object.")
            return {'CANCELLED'}
        
        # Validate at least one axis is selected
        selected_axes = []
        if self.use_x_axis:
            selected_axes.append(('X', self.stored_rotation_x))
        if self.use_y_axis:
            selected_axes.append(('Y', self.stored_rotation_y))
        if self.use_z_axis:
            selected_axes.append(('Z', self.stored_rotation_z))
        
        if not selected_axes:
            self.report({'ERROR'}, "Please select at least one rotation axis")
            return {'CANCELLED'}
        
        # Check if any selected axis has near-zero rotation
        for axis_name, max_value in selected_axes:
            if abs(max_value) < 0.001:
                self.report({'WARNING'}, 
                           f"Bone rotation on {axis_name} axis is nearly zero ({max_value:.4f}). "
                           "Consider rotating the bone to the desired maximum pose before creating the shape key.")
        
        # Exit pose mode
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Select and make the mesh active
        bpy.ops.object.select_all(action='DESELECT')
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj
        
        # Create shape key
        if mesh_obj.data.shape_keys is None:
            # Create basis shape key if it doesn't exist
            basis = mesh_obj.shape_key_add(name='Basis')
            basis.interpolation = 'KEY_LINEAR'
        
        # Store and zero all existing shape keys to prevent doubling deformations
        original_values = {}
        if mesh_obj.data.shape_keys:
            for key in mesh_obj.data.shape_keys.key_blocks:
                if key.name != 'Basis':
                    original_values[key.name] = key.value
                    key.value = 0
            
            # Set Basis as active to ensure mesh is at rest state
            mesh_obj.active_shape_key_index = 0
            
            # Force update to apply the zeroed shape keys
            context.view_layer.update()
        
        # Create the corrective shape key (from_mix=False copies from active key = Basis)
        shape_key = mesh_obj.shape_key_add(name=self.shapekey_name, from_mix=False)
        shape_key.value = 0.0
        
        # Restore all shape key values
        for key_name, value in original_values.items():
            if key_name in mesh_obj.data.shape_keys.key_blocks:
                mesh_obj.data.shape_keys.key_blocks[key_name].value = value
        
        # Set the new shape key as active
        mesh_obj.active_shape_key_index = len(mesh_obj.data.shape_keys.key_blocks) - 1
        
        # Create driver on shape key value
        driver = shape_key.driver_add("value").driver
        driver.type = 'SCRIPTED'
        
        # Add variables for each selected axis
        var_expressions = []
        for axis_name, max_value in selected_axes:
            var = driver.variables.new()
            var.name = f"var{axis_name}"
            var.type = 'TRANSFORMS'
            
            # Setup variable target
            target = var.targets[0]
            target.id = armature_obj
            target.bone_target = bone_name
            target.transform_type = f'ROT_{axis_name}'
            target.transform_space = 'LOCAL_SPACE'
            
            # Add this axis's normalized expression with max(0, ...) and pow(..., 2)
            var_expressions.append(f"pow(max(0, var{axis_name}/{max_value}), 2)")
        
        # Combine expressions: multiply all normalized axes
        if len(var_expressions) == 1:
            driver.expression = var_expressions[0]
        else:
            driver.expression = " * ".join(var_expressions)
       
        # Build info message about selected axes
        axes_info = ", ".join([f"{axis}={math.degrees(val):.2f}°" for axis, val in selected_axes])
        
        self.report({'INFO'}, 
                   f"Created shape key '{self.shapekey_name}' driven by "
                   f"{armature_obj.name}:{bone_name} ({axes_info})")
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # Store the current bone rotation values before showing dialog
        if context.active_pose_bone is None:
            self.report({'ERROR'}, "No active pose bone.")
            return {'CANCELLED'}
        
        pose_bone = context.active_pose_bone
        armature_obj = context.active_object
        
        # Store armature and bone names
        self.stored_armature_name = armature_obj.name
        self.stored_bone_name = pose_bone.name
        
        # Get rotation AFTER constraints in local space (same as driver reads)
        # This calculates the rotation relative to rest pose, matching what transform drivers use
        rest_bone = armature_obj.data.bones[pose_bone.name]
        
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
        
        self.stored_rotation_x = rotation_euler.x
        self.stored_rotation_y = rotation_euler.y
        self.stored_rotation_z = rotation_euler.z
        
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        """Draw the operator dialog"""
        layout = self.layout
        layout.prop(self, "shapekey_name")
        
        # Axis selection with checkboxes
        box = layout.box()
        box.label(text="Rotation Axes:", icon='ORIENTATION_GIMBAL')
        row = box.row()
        row.prop(self, "use_x_axis")
        row.prop(self, "use_y_axis")
        row.prop(self, "use_z_axis")


class VIEW3D_PT_corrective_shapekey_panel(Panel):
    """Panel for corrective shape key creation"""
    bl_label = "Corrective Shape Key"
    bl_idname = "VIEW3D_PT_corrective_shapekey"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Leo Tools'
    
    def draw(self, context):
        layout = self.layout
        
        # Show current context info
        box = layout.box()
        box.label(text="Current Context:", icon='INFO')
        
        if context.mode == 'POSE' and context.active_pose_bone:
            armature = context.active_object
            bone = context.active_pose_bone
            box.label(text=f"Armature: {armature.name}")
            box.label(text=f"Bone: {bone.name}")
            
            # Show current rotations
            row = box.row(align=True)
            row.label(text="Rotation:")
            col = box.column(align=True)
            col.label(text=f"X: {math.degrees(bone.rotation_euler[0]):.2f}°")
            col.label(text=f"Y: {math.degrees(bone.rotation_euler[1]):.2f}°")
            col.label(text=f"Z: {math.degrees(bone.rotation_euler[2]):.2f}°")
        else:
            box.label(text="Enter Pose Mode", icon='ERROR')
            box.label(text="and select a bone")
        
        layout.separator()
        
        # Operator button
        layout.operator("mesh.create_corrective_shapekey", 
                       text="Create Corrective Shape Key", 
                       icon='SHAPEKEY_DATA')
        
        # Instructions
        box = layout.box()
        box.label(text="Instructions:", icon='QUESTION')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text="1. Pose bone to max rotation")
        col.label(text="2. Click 'Create Corrective...'")
        col.label(text="3. Enter shape key name")
        col.label(text="4. Select rotation axis")
        col.label(text="5. Sculpt the corrective shape")


# Registration
classes = (
    MESH_OT_create_corrective_shapekey,
    VIEW3D_PT_corrective_shapekey_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
