"""
Position-Driven Shape Key Creator
Adds a position driver to an existing shape key
"""

import bpy
from bpy.props import StringProperty, EnumProperty, FloatProperty
from bpy.types import Operator, Panel


def get_shape_keys(self, context):
    """Get list of shape keys from selected mesh"""
    items = []
    
    # Find mesh object
    mesh_obj = None
    for obj in context.selected_objects:
        if obj.type == 'MESH':
            mesh_obj = obj
            break
    
    if mesh_obj and mesh_obj.data.shape_keys:
        for i, key in enumerate(mesh_obj.data.shape_keys.key_blocks):
            if key.name != 'Basis':  # Skip basis
                items.append((key.name, key.name, f"Add driver to {key.name}"))
    
    if not items:
        items.append(('NONE', "No shape keys found", ""))
    
    return items


class MESH_OT_create_position_driven_shapekey(Operator):
    """Add a position driver to an existing shape key"""
    bl_idname = "mesh.create_position_driven_shapekey"
    bl_label = "Add Position Driver to Shape Key"
    bl_options = {'REGISTER', 'UNDO'}
    
    target_shapekey: EnumProperty(
        name="Target Shape Key",
        description="Shape key to add the driver to",
        items=get_shape_keys
    )
    
    position_axis: EnumProperty(
        name="Position Axis",
        description="Bone position axis to drive the shape key",
        items=[
            ('X', "X Position", "Drive by X axis position"),
            ('Y', "Y Position", "Drive by Y axis position"),
            ('Z', "Z Position", "Drive by Z axis position"),
        ],
        default='X'
    )
    
    # Store position values captured in invoke (hidden from UI)
    stored_position_x: FloatProperty(options={'HIDDEN'})
    stored_position_y: FloatProperty(options={'HIDDEN'})
    stored_position_z: FloatProperty(options={'HIDDEN'})
    stored_armature_name: StringProperty(options={'HIDDEN'})
    stored_bone_name: StringProperty(options={'HIDDEN'})
    
    @classmethod
    def poll(cls, context):
        # Check if we're in pose mode with an active bone and have a mesh with shape keys
        has_mesh_with_keys = False
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj.data.shape_keys:
                has_mesh_with_keys = True
                break
        
        return (context.mode == 'POSE' and 
                context.active_pose_bone is not None and
                has_mesh_with_keys)
    
    def execute(self, context):
        # Use stored armature and bone info
        armature_obj = bpy.data.objects.get(self.stored_armature_name)
        bone_name = self.stored_bone_name
        
        if armature_obj is None or bone_name == "":
            self.report({'ERROR'}, "Stored bone information is missing.")
            return {'CANCELLED'}
        
        if self.target_shapekey == 'NONE':
            self.report({'ERROR'}, "No shape key selected.")
            return {'CANCELLED'}
        
        # Find the mesh object
        mesh_obj = None
        
        # First, check selected objects for a mesh
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj != armature_obj:
                mesh_obj = obj
                break
        
        if mesh_obj is None:
            self.report({'ERROR'}, "No mesh found. Please select a mesh object.")
            return {'CANCELLED'}
        
        # Get the target shape key
        shape_key = mesh_obj.data.shape_keys.key_blocks.get(self.target_shapekey)
        if shape_key is None:
            self.report({'ERROR'}, f"Shape key '{self.target_shapekey}' not found.")
            return {'CANCELLED'}
        
        # Get the stored position value for the selected axis
        axis_index = ['X', 'Y', 'Z'].index(self.position_axis)
        stored_positions = [self.stored_position_x, self.stored_position_y, self.stored_position_z]
        max_value = stored_positions[axis_index]
        
        if abs(max_value) < 0.001:
            self.report({'WARNING'}, 
                       f"Bone position on {self.position_axis} axis is nearly zero ({max_value:.4f}). "
                       "Consider moving the bone to the desired maximum position before creating the driver.")
        
        # Remove existing driver if any
        try:
            shape_key.driver_remove("value")
        except:
            pass
        
        # Create driver on shape key value
        driver = shape_key.driver_add("value").driver
        driver.type = 'SCRIPTED'
        
        # Add variable
        var = driver.variables.new()
        var.name = "var"
        var.type = 'TRANSFORMS'
        
        # Setup variable target
        target = var.targets[0]
        target.id = armature_obj
        target.bone_target = bone_name
        target.transform_type = f'LOC_{self.position_axis}'
        target.transform_space = 'LOCAL_SPACE'
        
        driver.expression = f"var/{max_value}"
        
        # Update dependencies
        mesh_obj.data.shape_keys.animation_data.drivers.update()
        context.view_layer.update()
        
        self.report({'INFO'}, 
                   f"Added driver to '{self.target_shapekey}' driven by "
                   f"{armature_obj.name}:{bone_name} {self.position_axis} position "
                   f"(max: {max_value:.3f})")
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # Store the current bone position values before showing dialog
        if context.active_pose_bone is None:
            self.report({'ERROR'}, "No active pose bone.")
            return {'CANCELLED'}
        
        pose_bone = context.active_pose_bone
        armature_obj = context.active_object
        
        # Store armature and bone names
        self.stored_armature_name = armature_obj.name
        self.stored_bone_name = pose_bone.name
        
        # Get position from the pose bone's matrix
        # Use matrix_basis for local position
        matrix = pose_bone.matrix_basis
        position = matrix.to_translation()
        
        self.stored_position_x = position.x
        self.stored_position_y = position.y
        self.stored_position_z = position.z
        
        return context.window_manager.invoke_props_dialog(self)


class VIEW3D_PT_position_driven_shapekey_panel(Panel):
    """Panel for position-driven shape key creation"""
    bl_label = "Position-Driven Shape Key"
    bl_idname = "VIEW3D_PT_position_driven_shapekey"
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
            
            # Show current positions
            position = bone.matrix_basis.to_translation()
            row = box.row(align=True)
            row.label(text="Position:")
            col = box.column(align=True)
            col.label(text=f"X: {position.x:.3f}")
            col.label(text=f"Y: {position.y:.3f}")
            col.label(text=f"Z: {position.z:.3f}")
        else:
            box.label(text="Enter Pose Mode", icon='ERROR')
            box.label(text="and select a bone")
        
        layout.separator()
        
        # Operator button
        layout.operator("mesh.create_position_driven_shapekey", 
                       text="Create Position-Driven Shape Key", 
                       icon='SHAPEKEY_DATA')
        
        # Instructions
        box = layout.box()
        box.label(text="Instructions:", icon='QUESTION')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text="1. Move bone to max position")
        col.label(text="2. Click 'Create Position...'")
        col.label(text="3. Enter shape key name")
        col.label(text="4. Select position axis")
        col.label(text="5. Sculpt the shape")


# Registration
classes = (
    MESH_OT_create_position_driven_shapekey,
    VIEW3D_PT_position_driven_shapekey_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
