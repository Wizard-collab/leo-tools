import bpy
from leo_tools import blender_tools
import importlib
importlib.reload(blender_tools)

class CustomToolboxPanel(bpy.types.Panel):
    bl_label = "Leo tools"  # The name of the panel
    bl_idname = "VIEW3D_PT_leo_tools"  # Unique ID for the panel
    bl_space_type = 'VIEW_3D'  # Panel location
    bl_region_type = 'UI'  # Region (e.g., 'UI' for the N-panel, 'TOOLS' for the T-panel)
    bl_category = "Leo tools"  # Tab name in the N-panel

    def draw(self, context):
        layout = self.layout
        obj = context.object
        # Add some buttons/operators to the panel
        layout.label(text="Rigging Tools")
        layout.operator("leo_tools.create_zero", text="Create zero on selection")
        layout.operator("leo_tools.align_objects", text="Align objects")
        layout.operator("leo_tools.align_object_to_bone", text="Align object to bone")
        layout.operator("leo_tools.align_bone_to_bone", text="Align bone to bone")
        layout.operator("leo_tools.reset_trsfrm", text="Reset transforms")
        layout.operator("leo_tools.mirror_rig_drivers", text="Mirror rig drivers")
        layout.label(text="Shading Tools")
        layout.operator("leo_tools.remove_materials", text="Remove materials")
        layout.operator("leo_tools.create_checker", text="Create new checker material")
        layout.label(text="Rendering Tools")
        layout.operator("leo_tools.init_settings", text="Init Cycles")
        layout.operator("leo_tools.fixed_threads", text="Set fixed threads to 16")
        layout.operator("leo_tools.threads_all", text="Use all threads")
        layout.label(text="Utils")
        layout.operator("leo_tools.add_subdiv", text="Add subdivision to selection")
        layout.label(text="Tween")
        layout.label(text=f"Selected Object: {obj.name}")
        layout.prop(obj, "tween_machine_percentage", text="Percentage")

class add_subdiv(bpy.types.Operator):
    bl_idname = "leo_tools.add_subdiv"
    bl_label = "Add subdiv on selection"
    bl_description = "Add subdiv on selection"
    
    def execute(self, context):
        add_subdivision_surface_modifier()
        return {'FINISHED'}

class create_z(bpy.types.Operator):
    bl_idname = "leo_tools.create_zero"
    bl_label = "Create a zero object on selection"
    bl_description = "Create a zero object on selection"

    def execute(self, context):
        create_zero()
        return {'FINISHED'}

class align_objs(bpy.types.Operator):
    bl_idname = "leo_tools.align_objects"
    bl_label = "Align two objects"
    bl_description = "Align two objects"

    def execute(self, context):
        align_objects()
        return {'FINISHED'}

class align_obj_to_bone(bpy.types.Operator):
    bl_idname = "leo_tools.align_object_to_bone"
    bl_label = "Align an object to a bone in pose mode"
    bl_description = "Align an object to a bone in pose mode"

    def execute(self, context):
        align_bn_to_bn()
        return {'FINISHED'}

class align_bone_to_bone(bpy.types.Operator):
    bl_idname = "leo_tools.align_bone_to_bone"
    bl_label = "Align a bone to a bone in pose mode"
    bl_description = "Align a bone to a bone in pose mode"

    def execute(self, context):
        align_bn_to_bn()
        return {'FINISHED'}


class reset_trsfrm(bpy.types.Operator):
    bl_idname = "leo_tools.reset_trsfrm"
    bl_label = "Reset transforms of selected objects"
    bl_description = "Reset transforms of selected objects"

    def execute(self, context):
        reset_transforms()
        return {'FINISHED'}

class remove_materials(bpy.types.Operator):
    bl_idname = "leo_tools.remove_materials"
    bl_label = "Remove all materials from selected objects"
    bl_description = "Remove all materials from selected objects"

    def execute(self, context):
        remove_shaders()
        return {'FINISHED'}

class init_settings(bpy.types.Operator):
    bl_idname = "leo_tools.init_settings"
    bl_label = "Init render settings"
    bl_description = "Init render settings"
    
    def execute(self, context):
        init_render_settings()
        return {'FINISHED'}

class fixed_threads(bpy.types.Operator):
    bl_idname = "leo_tools.fixed_threads"
    bl_label = "Set fixed threads to 16"
    bl_description = "Set fixed threads to 16"
    
    def execute(self, context):
        set_fixed_thread()
        return {'FINISHED'}

class threads_all(bpy.types.Operator):
    bl_idname = "leo_tools.threads_all"
    bl_label = "Set threads to all"
    bl_description = "Set threads to all"
    
    def execute(self, context):
        set_thread_all()
        return {'FINISHED'}

class create_checker(bpy.types.Operator):
    bl_idname = "leo_tools.create_checker"
    bl_label = "Create new checker material"
    bl_description = "Create new checker material"
    
    def execute(self, context):
        create_checker_material()
        return {'FINISHED'}

class mirror_rig_drivers(bpy.types.Operator):
    bl_idname = "leo_tools.mirror_rig_drivers"
    bl_label = "Mirror the rig drivers"
    bl_description = "Mirror the rig drivers"
    
    def execute(self, context):
        copy_rig_drivers()
        return {'FINISHED'}

def update_tween(self, context):
    obj = context.object

    # Ensure the object has animation data
    if not obj.animation_data or not obj.animation_data.action:
        return

    action = obj.animation_data.action
    fcurves = action.fcurves
    current_frame = context.scene.frame_current
    previous_frame = None
    next_frame = None

    # Find previous and next keyframes
    for fcurve in fcurves:
        keyframe_points = fcurve.keyframe_points
        for i, key in enumerate(keyframe_points):
            if key.co[0] < current_frame:
                previous_frame = key.co[0]
            elif key.co[0] > current_frame:
                next_frame = key.co[0]
                break

        if previous_frame is not None and next_frame is not None:
            break

    if previous_frame is None or next_frame is None:
        return

    # Interpolate between keyframes
    factor = obj.tween_machine_percentage / 100.0
    interpolated_location = []

    for fcurve in fcurves:
        prev_value = fcurve.evaluate(previous_frame)
        next_value = fcurve.evaluate(next_frame)
        interpolated_value = (1 - factor) * prev_value + factor * next_value
        interpolated_location.append(interpolated_value)

    # Apply the interpolated location to the object
    obj.location = interpolated_location[:3]

    # Check if Auto Keying is enabled and set a keyframe
    if context.scene.tool_settings.use_keyframe_insert_auto:
        obj.keyframe_insert(data_path="location", frame=current_frame)

def add_subdivision_surface_modifier():
    selected_objects = bpy.context.selected_objects
    for obj in selected_objects:
        for modifier in obj.modifiers:
            if modifier.type == 'SUBSURF':
                return
        subsurf_modifier = obj.modifiers.new(name="Subdivision", type='SUBSURF')
        subsurf_modifier.render_levels = 2
        subsurf_modifier.levels = 1

def align_object_to_bone():
    if bpy.context.object and bpy.context.object.type == 'ARMATURE' and bpy.context.object.mode == 'POSE':
        # Get the active armature and selected bone

        armature = bpy.context.object
        selected_objects = bpy.context.selected_objects
        selected_objects.remove(armature)
        object_to_align = selected_objects[0]
        selected_bones = [bone for bone in armature.pose.bones if bone.bone.select]

        if selected_bones:
            # Get the first selected bone (if multiple are selected, it uses the first one)
            selected_bone = selected_bones[0]

            # Align object's location to the selected bone
            object_to_align.location = armature.matrix_world @ selected_bone.head

            # Align object's rotation to the selected bone
            object_to_align.rotation_mode = 'XYZ'  # Set the rotation mode to Euler (XYZ)
            combined_matrix = armature.matrix_world @ selected_bone.matrix
            object_to_align.rotation_euler = combined_matrix.to_euler()
            print(f"Object '{object_to_align.name}' aligned to bone '{selected_bone.name}' in armature '{armature.name}'.")
        else:
            print("No bone is selected in the armature.")
    else:
        print("Please select an armature in Pose Mode and a bone.")

def align_bn_to_bn():
    if bpy.context.object and bpy.context.object.type == 'ARMATURE' and bpy.context.object.mode == 'POSE':
        # Get the active armature and selected bone

        armature = bpy.context.object
        active_pose_bone = armature.pose.bones[armature.data.bones.active.name]
        selected_bones = [bone for bone in armature.pose.bones if bone.bone.select]
        selected_bones.remove(bpy.data.objects[armature.name].pose.bones[active_pose_bone.name])

        if selected_bones:
            # Get the first selected bone (if multiple are selected, it uses the first one)
            selected_bone = selected_bones[0]

            selected_bone.matrix = active_pose_bone.matrix
            print(f"Bone '{selected_bone.name}' aligned to bone '{active_pose_bone.name}' in armature '{armature.name}'.")
        else:
            print("No bone is selected in the armature.")
    else:
        armature = bpy.context.object
        active_bone = armature.data.bones[armature.data.bones.active.name]
        selected_bones = [bone for bone in armature.data.bones if bone.select]
        selected_bones.remove(bpy.data.objects[armature.name].data.bones[active_bone.name])

        if selected_bones:
            # Get the first selected bone (if multiple are selected, it uses the first one)
            selected_bone = selected_bones[0]

            selected_bone.head = active_bone.head
            selected_bone.tail = active_bone.tail
            selected_bone.roll = active_bone.roll
            print(f"Bone '{selected_bone.name}' aligned to bone '{active_pose_bone.name}' in armature '{armature.name}'.")
        else:
            print("No bone is selected in the armature.")

def create_checker_material():
    # Create a new material
    material = bpy.data.materials.new(name="CheckerMaterial")
    material.use_nodes = True  # Enable nodes
    # Get the material's node tree
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    # Clear all existing nodes
    for node in nodes:
        nodes.remove(node)
    # Add a Principled BSDF node
    bsdf_node = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf_node.location = (0, 0)
    # Add a Material Output node
    output_node = nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (300, 0)
    # Link BSDF to Material Output
    links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
    # Add a Checker Texture node
    checker_node = nodes.new(type='ShaderNodeTexChecker')
    checker_node.location = (-300, 0)
    checker_node.inputs['Scale'].default_value = 50
    # Link Checker Texture to Base Color of BSDF
    links.new(checker_node.outputs['Color'], bsdf_node.inputs['Base Color'])
    # Add a Texture Coordinate node
    tex_coord_node = nodes.new(type='ShaderNodeTexCoord')
    tex_coord_node.location = (-600, 0)
    # Link Texture Coordinate UV output to Checker Texture Vector input
    links.new(tex_coord_node.outputs['UV'], checker_node.inputs['Vector'])
    # Assign the material to the active object
    if bpy.context.object:
        bpy.context.object.data.materials.append(material)

def set_fixed_thread():
    bpy.context.scene.render.threads_mode = 'FIXED'
    bpy.context.scene.render.threads = 16

def set_thread_all():
    bpy.context.scene.render.threads_mode = 'AUTO'

def refresh_viewport():
    bpy.context.view_layer.update()
    for area in bpy.context.screen.areas:
        area.tag_redraw()
    bpy.context.evaluated_depsgraph_get().update()

def init_render_settings():
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'GPU'
    bpy.context.scene.render.film_transparent = True
    '''
    bpy.context.scene.render.image_settings.file_format = 'OPEN_EXR_MULTILAYER'
    bpy.context.scene.render.image_settings.color_management = 'OVERRIDE'
    bpy.context.scene.view_layers["ViewLayer"].use_pass_mist = True
    bpy.context.scene.view_layers["ViewLayer"].use_pass_diffuse_direct = True
    bpy.context.scene.view_layers["ViewLayer"].use_pass_diffuse_indirect = True
    bpy.context.scene.view_layers["ViewLayer"].use_pass_diffuse_color = True
    bpy.context.scene.view_layers["ViewLayer"].use_pass_glossy_direct = True
    bpy.context.scene.view_layers["ViewLayer"].use_pass_glossy_indirect = True
    bpy.context.scene.view_layers["ViewLayer"].use_pass_cryptomatte_object = True
    bpy.context.scene.view_layers["ViewLayer"].use_pass_cryptomatte_material = True
    bpy.context.scene.view_layers["ViewLayer"].cycles.denoising_store_passes = True
    bpy.context.scene.view_layers["ViewLayer"].use_pass_vector = True
    bpy.context.scene.view_layers["ViewLayer"].use_pass_object_index = True
    bpy.context.scene.view_layers["ViewLayer"].use_pass_material_index = True
    bpy.context.scene.render.use_overwrite = False
    bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[1].default_value = 0
    bpy.context.scene.world.mist_settings.start = 0
    bpy.context.scene.world.mist_settings.depth = 250
    bpy.context.scene.render.use_persistent_data = True
    bpy.context.scene.render.use_motion_blur = True
    bpy.context.scene.render.motion_blur_shutter = 0.2
    bpy.context.scene.cycles.caustics_refractive = False
    bpy.context.scene.cycles.caustics_reflective = False
    '''

def create_zero():
    selected_objects = bpy.context.selected_objects
    for obj in selected_objects:
        empty = bpy.ops.object.empty_add(type='ARROWS', location=(0, 0, 0))
        refresh_viewport()
        empty_object = bpy.context.object
        empty_object.name = f"{obj.name}_zero"
        align_objects([obj, empty_object])
        refresh_viewport()
        obj.parent = empty_object
        refresh_viewport()
        reset_transforms(obj)
        refresh_viewport()

def reset_transforms(obj=None):
    if not obj:
        objects = bpy.context.selected_objects
    else:
        objects = [obj]
    for obj in objects:
        obj.location = (0.0, 0.0, 0.0)
        obj.rotation_euler = (0.0, 0.0, 0.0)

def align_objects(objects=None):
    if not objects:
        selected_objects = bpy.context.selected_objects
        active_object = bpy.context.active_object
        selected_objects.remove(active_object)
        objects = [active_object, selected_objects[0]]
    objects[1].matrix_world = objects[0].matrix_world

def remove_shaders():
    for obj in bpy.context.selected_objects:
        if obj.type == 'MESH':
            obj.data.materials.clear()

def copy_pose_drivers():
    armature = bpy.context.object
    for fcurve in (armature.animation_data.drivers):
            if '_R' in fcurve.data_path:
                continue
            new_fcurve = armature.driver_add(fcurve.data_path.replace('_L', '_R'))
            copy_fcurve_properties(fcurve, new_fcurve) 

def copy_armature_data_drivers():
    armature = bpy.context.object
    armature_data = armature.data
    bones_with_hide_drivers = []
    if armature_data.animation_data and armature_data.animation_data.drivers:
        for fcurve in armature_data.animation_data.drivers:
            if '_R' in fcurve.data_path:
                continue
            new_fcurve = armature_data.driver_add(fcurve.data_path.replace('_L', '_R'))
            copy_fcurve_properties(fcurve, new_fcurve)

def copy_fcurve_properties(fcurve, new_fcurve):
    
    while new_fcurve.driver.variables:
        new_fcurve.driver.variables.remove(new_fcurve.driver.variables[0])
    
    for var in fcurve.driver.variables:
        print(var)
    
        new_var = new_fcurve.driver.variables.new()
        new_var.name = var.name
        new_var.type = var.type

        for i, target in enumerate(var.targets):
            new_var_target = new_var.targets[i]
            new_var_target.id = target.id
            new_var_target.data_path = target.data_path.replace('_L', '_R')
            new_var_target.bone_target = target.bone_target.replace('_L', '_R')
    
    new_fcurve.driver.type = fcurve.driver.type
    new_fcurve.driver.expression = fcurve.driver.expression
    
def copy_rig_drivers():                
    copy_pose_drivers()
    copy_armature_data_drivers()

def register():
    bpy.utils.register_class(create_z)
    bpy.utils.register_class(align_objs)
    bpy.utils.register_class(align_obj_to_bone)
    bpy.utils.register_class(align_bone_to_bone)
    bpy.utils.register_class(reset_trsfrm)
    bpy.utils.register_class(remove_materials)
    bpy.utils.register_class(init_settings)
    bpy.utils.register_class(fixed_threads)
    bpy.utils.register_class(threads_all)
    bpy.utils.register_class(create_checker)
    bpy.utils.register_class(add_subdiv)
    bpy.utils.register_class(mirror_rig_drivers)
    bpy.utils.register_class(CustomToolboxPanel)
    bpy.types.Object.tween_machine_percentage = bpy.props.FloatProperty(
        name="Percentage",
        description="Percentage between previous and next keyframes",
        default=50.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE',
        update=update_tween)

def unregister():
    bpy.utils.unregister_class(CustomToolboxPanel)

if __name__ == "__main__":
    register()