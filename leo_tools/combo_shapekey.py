"""
Combo Shape Key Creator
Creates a combination shape key driven by two parent shape keys
Captures the current state and uses those values as max range
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, StringProperty


def get_shape_keys(self, context):
    """Get list of shape keys for EnumProperty"""
    items = []
    obj = context.active_object
    
    if obj and obj.type == 'MESH' and obj.data.shape_keys:
        for i, key in enumerate(obj.data.shape_keys.key_blocks):
            if key.name != 'Basis':
                items.append((key.name, key.name, f"Shape key: {key.name}"))
    
    if not items:
        items.append(('NONE', 'No shape keys', 'No shape keys available'))
    
    return items


class MESH_OT_create_combo_shapekey(Operator):
    """Create a combo shape key from two parent shape keys"""
    bl_idname = "mesh.create_combo_shapekey"
    bl_label = "Create Combo Shape Key"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Properties for selecting two shape keys
    shape_key_1: EnumProperty(
        name="Shape Key 1",
        description="First parent shape key",
        items=get_shape_keys
    )
    
    shape_key_2: EnumProperty(
        name="Shape Key 2",
        description="Second parent shape key",
        items=get_shape_keys
    )
    
    combo_name: StringProperty(
        name="Combo Name",
        description="Name for the new combo shape key",
        default="combo_CSK"
    )
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and 
                context.mode == 'OBJECT' and 
                obj.data.shape_keys and
                len(obj.data.shape_keys.key_blocks) > 1)
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "shape_key_1")
        layout.prop(self, "shape_key_2")
        layout.prop(self, "combo_name")
    
    def execute(self, context):
        obj = context.active_object
        shape_keys = obj.data.shape_keys
        
        # Validate selection
        if self.shape_key_1 == 'NONE' or self.shape_key_2 == 'NONE':
            self.report({'ERROR'}, "No shape keys available")
            return {'CANCELLED'}
        
        if self.shape_key_1 == self.shape_key_2:
            self.report({'ERROR'}, "Please select two different shape keys")
            return {'CANCELLED'}
        
        # Get the two parent shape keys
        key1 = shape_keys.key_blocks.get(self.shape_key_1)
        key2 = shape_keys.key_blocks.get(self.shape_key_2)
        
        if not key1 or not key2:
            self.report({'ERROR'}, "Could not find selected shape keys")
            return {'CANCELLED'}
        
        # Capture current values (these will be the max values)
        max_value_1 = key1.value
        max_value_2 = key2.value
        
        if max_value_1 == 0 or max_value_2 == 0:
            self.report({'ERROR'}, "Both shape keys must have values greater than 0")
            return {'CANCELLED'}
        
        # Store original values of ALL keys first
        original_values = {}
        for key in shape_keys.key_blocks:
            original_values[key.name] = key.value
        
        # Zero all keys except the two parent keys
        for key in shape_keys.key_blocks:
            if key.name != 'Basis' and key != key1 and key != key2:
                key.value = 0
        
        # CRITICAL: Set Basis as active so from_mix=False copies from clean mesh
        obj.active_shape_key_index = 0
        
        # Force update so mesh reflects the current shape key state
        context.view_layer.update()
        
        # Set both parent keys to their current values (already set)
        # Create new shape key from current mix (with only key1 and key2 active)
        combo_key = obj.shape_key_add(name=self.combo_name, from_mix=False)
        
        # Restore all shape key values
        for key_name, value in original_values.items():
            if key_name in shape_keys.key_blocks:
                shape_keys.key_blocks[key_name].value = value
        
        # Reset the combo key value to 0
        combo_key.value = 0
        
        # Create driver for the combo shape key
        driver_fcurve = combo_key.driver_add("value")
        driver = driver_fcurve.driver
        driver.type = 'SCRIPTED'
        
        # Add variable for first shape key
        var1 = driver.variables.new()
        var1.name = "key1"
        var1.type = 'SINGLE_PROP'
        target1 = var1.targets[0]
        target1.id_type = 'KEY'
        target1.id = shape_keys
        target1.data_path = f'key_blocks["{key1.name}"].value'
        
        # Add variable for second shape key
        var2 = driver.variables.new()
        var2.name = "key2"
        var2.type = 'SINGLE_PROP'
        target2 = var2.targets[0]
        target2.id_type = 'KEY'
        target2.id = shape_keys
        target2.data_path = f'key_blocks["{key2.name}"].value'
        
        # Set expression: multiply normalized values
        # When both keys reach their captured values, combo is at 1.0
        driver.expression = f"(key1/{max_value_1}) * (key2/{max_value_2})"
        
        # Update dependencies
        shape_keys.animation_data.drivers.update()
        context.view_layer.update()
        
        self.report({'INFO'}, 
                   f"Created combo '{self.combo_name}' from '{key1.name}' and '{key2.name}' "
                   f"(max values: {max_value_1:.2f}, {max_value_2:.2f})")
        
        return {'FINISHED'}


class VIEW3D_PT_combo_shapekey_panel(bpy.types.Panel):
    """Panel for creating combo shape keys"""
    bl_label = "Combo Shape Keys"
    bl_idname = "VIEW3D_PT_combo_shapekey"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Leo Tools'
    
    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        # Show current context info
        box = layout.box()
        box.label(text="Current Object:", icon='INFO')
        
        if obj and obj.type == 'MESH':
            box.label(text=f"Object: {obj.name}")
            
            if obj.data.shape_keys:
                key_count = len(obj.data.shape_keys.key_blocks)
                box.label(text=f"Total Keys: {key_count}")
            else:
                box.label(text="No shape keys", icon='ERROR')
        else:
            box.label(text="No mesh selected", icon='ERROR')
        
        layout.separator()
        
        # Operator button
        layout.operator("mesh.create_combo_shapekey", 
                       text="Create Combo Shape Key", 
                       icon='SHAPEKEY_DATA')
        
        # Instructions
        layout.separator()
        box = layout.box()
        box.label(text="Instructions:", icon='QUESTION')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text="1. Set both parent keys to desired values")
        col.label(text="2. Click 'Create Combo Shape Key'")
        col.label(text="3. Select two shape keys to combine")
        col.label(text="4. Combo activates when both reach their values")


# Registration
classes = (
    MESH_OT_create_combo_shapekey,
    VIEW3D_PT_combo_shapekey_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
