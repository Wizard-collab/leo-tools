"""
Mirror Shape Keys and Drivers
Mirrors _L shape keys to _R with proper driver mirroring
Handles cascading ISK (Intermediate Shape Key) dependencies
"""

import bpy
from bpy.types import Operator, Panel
import re


class MESH_OT_mirror_shapekeys_and_drivers(Operator):
    """Mirror shape keys and their drivers from _L to _R"""
    bl_idname = "mesh.mirror_shapekeys_and_drivers"
    bl_label = "Mirror Shape Keys and Drivers"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and obj.data.shape_keys)
    
    def execute(self, context):
        obj = context.active_object
        shape_keys = obj.data.shape_keys
        
        if not shape_keys:
            self.report({'ERROR'}, "No shape keys found.")
            return {'CANCELLED'}
        
        # Step 1: Collect all _L shape keys first (before deleting anything)
        # Process non-ISK keys first, then ISK keys (to handle dependencies)
        left_keys = []
        isk_keys = []
        
        for key in shape_keys.key_blocks:
            if '_L' in key.name and key.name != 'Basis':
                if key.name.endswith('_ISK'):
                    isk_keys.append(key.name)
                else:
                    left_keys.append(key.name)
        
        if not left_keys and not isk_keys:
            self.report({'WARNING'}, "No _L shape keys found to mirror.")
            return {'CANCELLED'}
        
        # Step 2: Delete all _R shape keys
        keys_to_delete = []
        for key in shape_keys.key_blocks:
            if '_R' in key.name:
                keys_to_delete.append(key.name)
        
        # Delete in reverse order to avoid index issues
        for key_name in reversed(keys_to_delete):
            idx = shape_keys.key_blocks.find(key_name)
            if idx >= 0:
                obj.active_shape_key_index = idx
                bpy.ops.object.shape_key_remove()
        
        self.report({'INFO'}, f"Deleted {len(keys_to_delete)} _R shape keys")
        
        # Step 3: Process order: original keys first, then ISK intermediates
        keys_to_mirror = left_keys + isk_keys
        
        # Step 4: Mirror each shape key
        mirrored_count = 0
        
        for key_name in keys_to_mirror:
            # Verify key still exists
            if key_name not in shape_keys.key_blocks:
                continue
                
            original_key = shape_keys.key_blocks[key_name]
            
            # Generate mirrored name
            mirrored_name = key_name.replace('_L', '_R')
            
            # Set the original key as active
            obj.active_shape_key_index = shape_keys.key_blocks.find(key_name)
            
            # Create new shape key for the mirrored version
            new_key = obj.shape_key_add(name=mirrored_name, from_mix=False)
            
            # Copy vertex positions from original to new key
            for i, vert in enumerate(original_key.data):
                new_key.data[i].co = vert.co.copy()
            
            # Now mirror the vertex positions in the new key
            obj.active_shape_key_index = shape_keys.key_blocks.find(mirrored_name)
            bpy.ops.object.shape_key_mirror(use_topology=False)
            
            # Copy and mirror the driver if it exists
            self.mirror_driver(original_key, new_key, shape_keys, obj)
            
            mirrored_count += 1
        
        self.report({'INFO'}, f"Successfully mirrored {mirrored_count} shape keys")
        return {'FINISHED'}
    
    def mirror_driver(self, original_key, new_key, shape_keys, obj):
        """Mirror driver from original key to new key"""
        # Safety check
        if not new_key:
            return
        
        # Check if original has a driver
        anim_data = shape_keys.animation_data
        if not anim_data or not anim_data.drivers:
            return
        
        original_driver = None
        for driver in anim_data.drivers:
            if driver.data_path == f'key_blocks["{original_key.name}"].value':
                original_driver = driver
                break
        
        if not original_driver or not original_driver.driver:
            return
        
        # Remove existing driver on new key if any
        try:
            new_key.driver_remove("value")
        except:
            pass
        
        # Create new driver
        new_driver_fcurve = new_key.driver_add("value")
        new_driver = new_driver_fcurve.driver
        
        # Copy driver type and expression
        new_driver.type = original_driver.driver.type
        
        # Mirror the expression (replace _L with _R in variable names and references)
        original_expression = original_driver.driver.expression
        mirrored_expression = original_expression
        
        # Copy and mirror variables
        for var in original_driver.driver.variables:
            new_var = new_driver.variables.new()
            new_var.name = var.name
            new_var.type = var.type
            
            # Mirror variable targets
            for i, target in enumerate(var.targets):
                new_target = new_var.targets[i]
                
                # Mirror based on variable type
                if var.type == 'TRANSFORMS':
                    # Bone transform variable
                    # Set id first (this also sets id_type automatically)
                    new_target.id = target.id
                    if target.bone_target:
                        new_target.bone_target = target.bone_target.replace('_L', '_R')
                    new_target.transform_type = target.transform_type
                    new_target.transform_space = target.transform_space
                
                elif var.type == 'SINGLE_PROP':
                    # Property variable (like shape key references)
                    # Set id_type first to accept Key datablock
                    new_target.id_type = 'KEY'
                    # Now set the Key datablock as the target
                    new_target.id = obj.data.shape_keys
                    
                    if target.data_path:
                        # Mirror shape key references in data path
                        mirrored_data_path = target.data_path
                        
                        # Find shape key references and mirror them
                        # Pattern: key_blocks["name_L"]
                        import re
                        pattern = r'key_blocks\["([^"]+)"\]'
                        matches = re.findall(pattern, mirrored_data_path)
                        
                        for match in matches:
                            if '_L' in match:
                                mirrored_match = match.replace('_L', '_R')
                                mirrored_data_path = mirrored_data_path.replace(
                                    f'key_blocks["{match}"]',
                                    f'key_blocks["{mirrored_match}"]'
                                )
                        
                        new_target.data_path = mirrored_data_path
        
        # Set mirrored expression
        new_driver.expression = mirrored_expression


class VIEW3D_PT_mirror_shapekeys_panel(Panel):
    """Panel for mirroring shape keys and drivers"""
    bl_label = "Mirror Shape Keys"
    bl_idname = "VIEW3D_PT_mirror_shapekeys"
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
                left_count = sum(1 for k in obj.data.shape_keys.key_blocks if '_L' in k.name)
                right_count = sum(1 for k in obj.data.shape_keys.key_blocks if '_R' in k.name)
                
                box.label(text=f"Total Keys: {key_count}")
                box.label(text=f"Left Keys: {left_count}")
                box.label(text=f"Right Keys: {right_count}")
            else:
                box.label(text="No shape keys", icon='ERROR')
        else:
            box.label(text="No mesh selected", icon='ERROR')
        
        layout.separator()
        
        # Operator button
        layout.operator("mesh.mirror_shapekeys_and_drivers", 
                       text="Mirror Shape Keys L→R", 
                       icon='MOD_MIRROR')
        
        # Instructions
        layout.separator()
        box = layout.box()
        box.label(text="Instructions:", icon='QUESTION')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text="1. Select mesh with shape keys")
        col.label(text="2. Click 'Mirror Shape Keys L→R'")
        col.label(text="3. All _R keys will be deleted")
        col.label(text="4. All _L keys will be mirrored")
        col.label(text="5. Drivers will be copied & mirrored")


# Registration
classes = (
    MESH_OT_mirror_shapekeys_and_drivers,
    VIEW3D_PT_mirror_shapekeys_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
