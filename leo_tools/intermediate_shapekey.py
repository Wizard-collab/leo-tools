"""
Intermediate Shape Key Creator
Creates intermediate shape keys that activate/deactivate at a specific percentage of the original shape key
"""

import bpy
from bpy.props import FloatProperty
from bpy.types import Operator, Panel


class MESH_OT_create_intermediate_shapekey(Operator):
    """Create an intermediate shape key driven by the original shape key"""
    bl_idname = "mesh.create_intermediate_shapekey"
    bl_label = "Create Intermediate Shape Key"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Store the captured percentage
    captured_percentage: FloatProperty(
        name="Peak Value",
        description="The value at which the intermediate shape key reaches full influence (1.0)",
        default=0.5,
        min=0.0,
        max=1.0,
        options={'HIDDEN'}
    )
    
    original_key_name: bpy.props.StringProperty(options={'HIDDEN'})
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and 
                obj.data.shape_keys and 
                obj.active_shape_key and
                obj.active_shape_key != obj.data.shape_keys.key_blocks.get('Basis'))
    
    def execute(self, context):
        obj = context.active_object
        original_key = obj.data.shape_keys.key_blocks[self.original_key_name]
        
        # Create the intermediate shape key with ISK suffix
        intermediate_name = f"{original_key.name}_{int(self.captured_percentage * 100)}_ISK"
        intermediate_key = obj.shape_key_add(name=intermediate_name, from_mix=False)
        intermediate_key.value = 0.0
        
        # Copy the shape from the original key at the captured percentage
        # First, disable all other intermediate shape keys from the same original
        # to avoid cumulative effects
        other_intermediates = {}
        for key in obj.data.shape_keys.key_blocks:
            # Find other intermediates (keys that end with "_ISK" and start with original name)
            if key != original_key and key.name.startswith(original_key.name) and key.name.endswith("_ISK"):
                other_intermediates[key.name] = key.value
                key.value = 0.0
        
        # Set original to the captured value
        original_value_backup = original_key.value
        original_key.value = self.captured_percentage
        
        # Update the scene to apply the shape
        context.view_layer.update()
        
        # Copy vertex positions
        for i, vert in enumerate(obj.data.vertices):
            intermediate_key.data[i].co = vert.co
        
        # Restore original value and other intermediates
        original_key.value = original_value_backup
        for key_name, value in other_intermediates.items():
            obj.data.shape_keys.key_blocks[key_name].value = value
        
        # Get all ISK intermediates for this original key and sort by percentage
        all_intermediates = []
        for key in obj.data.shape_keys.key_blocks:
            if key.name.startswith(original_key.name) and key.name.endswith("_ISK"):
                # Extract percentage from name: "name_XX_ISK"
                try:
                    parts = key.name.rsplit("_", 2)
                    if len(parts) == 3 and parts[2] == "ISK":
                        percentage = int(parts[1]) / 100.0
                        all_intermediates.append((percentage, key))
                except:
                    pass
        
        # Sort by percentage
        all_intermediates.sort(key=lambda x: x[0])
        
        # Update drivers for all intermediates to create proper ranges
        for i, (peak, key) in enumerate(all_intermediates):
            # Determine the range for this intermediate
            prev_peak = all_intermediates[i-1][0] if i > 0 else 0.0
            next_peak = all_intermediates[i+1][0] if i < len(all_intermediates) - 1 else 1.0
            
            # Remove existing driver if any
            try:
                key.driver_remove("value")
            except:
                pass
            
            # Create new driver
            driver = key.driver_add("value").driver
            driver.type = 'SCRIPTED'
            
            # Add variable pointing to the original shape key
            var = driver.variables.new()
            var.name = "original"
            var.type = 'SINGLE_PROP'
            
            # Setup variable target
            var.targets[0].id_type = 'KEY'
            var.targets[0].id = obj.data.shape_keys
            var.targets[0].data_path = f'key_blocks["{original_key.name}"].value'
            
            # Create expression that ramps up from prev_peak to peak, then down from peak to next_peak
            # Ramp up: (original - prev_peak) / (peak - prev_peak)
            # Ramp down: (next_peak - original) / (next_peak - peak)
            
            if peak - prev_peak < 0.001:  # At the start
                up_expr = "1"
            else:
                up_expr = f"(original - {prev_peak}) / {peak - prev_peak}"
            
            if next_peak - peak < 0.001:  # At the end
                down_expr = "1"
            else:
                down_expr = f"({next_peak} - original) / {next_peak - peak}"
            
            # Combine: max(0, min(up_ramp, down_ramp))
            driver.expression = f"max(0, min({up_expr}, {down_expr}))"
        
        # Update dependencies to ensure drivers persist
        obj.data.shape_keys.animation_data.drivers.update()
        context.view_layer.update()
        context.evaluated_depsgraph_get().update()
        
        # Set the new shape key as active
        for i, key in enumerate(obj.data.shape_keys.key_blocks):
            if key == intermediate_key:
                obj.active_shape_key_index = i
                break
        
        self.report({'INFO'}, 
                   f"Created intermediate shape key '{intermediate_name}' "
                   f"peaking at {self.captured_percentage:.2f}")
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        obj = context.active_object
        original_key = obj.active_shape_key
        
        # Store the original key name and current value
        self.original_key_name = original_key.name
        self.captured_percentage = original_key.value
        
        if self.captured_percentage <= 0.001:
            self.report({'WARNING'}, 
                       "Shape key value is very close to 0. Set it to the desired peak value first.")
        
        if self.captured_percentage >= 0.999:
            self.report({'WARNING'}, 
                       "Shape key value is very close to 1. This will create a shape that stays at full influence.")
        
        return self.execute(context)


class MESH_OT_create_intermediate_at_value(Operator):
    """Create an intermediate shape key with a custom peak value"""
    bl_idname = "mesh.create_intermediate_at_value"
    bl_label = "Create Intermediate at Custom Value"
    bl_options = {'REGISTER', 'UNDO'}
    
    peak_value: FloatProperty(
        name="Peak Value",
        description="The value at which the intermediate shape key reaches full influence",
        default=0.5,
        min=0.001,
        max=0.999
    )
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and 
                obj.data.shape_keys and 
                obj.active_shape_key and
                obj.active_shape_key != obj.data.shape_keys.key_blocks.get('Basis'))
    
    def execute(self, context):
        obj = context.active_object
        original_key = obj.active_shape_key
        
        # Call the main operator with the custom value
        bpy.ops.mesh.create_intermediate_shapekey(
            captured_percentage=self.peak_value,
            original_key_name=original_key.name
        )
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class VIEW3D_PT_intermediate_shapekey_panel(Panel):
    """Panel for intermediate shape key creation"""
    bl_label = "Intermediate Shape Key"
    bl_idname = "VIEW3D_PT_intermediate_shapekey"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Leo Tools'
    
    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        # Show current context info
        box = layout.box()
        box.label(text="Current Selection:", icon='INFO')
        
        if obj and obj.type == 'MESH':
            box.label(text=f"Object: {obj.name}")
            
            if obj.data.shape_keys and obj.active_shape_key:
                key = obj.active_shape_key
                box.label(text=f"Shape Key: {key.name}")
                box.label(text=f"Value: {key.value:.3f}")
                
                # Check if it has a driver (without creating one)
                anim_data = obj.data.shape_keys.animation_data
                has_driver = False
                if anim_data and anim_data.drivers:
                    for driver in anim_data.drivers:
                        if driver.data_path == f'key_blocks["{key.name}"].value':
                            has_driver = True
                            break
                
                if has_driver:
                    box.label(text="Driver: Yes", icon='DRIVER')
            else:
                box.label(text="No shape key selected", icon='ERROR')
        else:
            box.label(text="No mesh selected", icon='ERROR')
        
        layout.separator()
        
        # Operators
        col = layout.column(align=True)
        col.operator("mesh.create_intermediate_shapekey", 
                    text="Create at Current Value", 
                    icon='SHAPEKEY_DATA')
        col.operator("mesh.create_intermediate_at_value", 
                    text="Create at Custom Value", 
                    icon='SHAPEKEY_DATA')
        
        # Instructions
        layout.separator()
        box = layout.box()
        box.label(text="Instructions:", icon='QUESTION')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text="1. Select mesh object")
        col.label(text="2. Select target shape key")
        col.label(text="3. Set value to peak point")
        col.label(text="4. Click 'Create at Current Value'")
        col.label(text="Or use 'Custom Value' for dialog")


def register():
    bpy.utils.register_class(MESH_OT_create_intermediate_shapekey)
    bpy.utils.register_class(MESH_OT_create_intermediate_at_value)
    bpy.utils.register_class(VIEW3D_PT_intermediate_shapekey_panel)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_intermediate_shapekey_panel)
    bpy.utils.unregister_class(MESH_OT_create_intermediate_at_value)
    bpy.utils.unregister_class(MESH_OT_create_intermediate_shapekey)


if __name__ == "__main__":
    register()
