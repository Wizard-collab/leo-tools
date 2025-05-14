import bpy
import mathutils
import os

bones_tuples = [("head","DEF_head"),
                ("neck", "DEF_neck"),
                ("back_1", "DEF_back_1"),
                ("back_2", "DEF_back_2"),
                ("back_3", "DEF_back_3"),
                ("pelvis", "DEF_pelvis"),
                ("shoulder_L", "DEF_shoulder_L"),
                ("arm_1_L", "DEF_arm_1_L"),
                ("arm_2_L", "arm_2_L"),
                ("hand_L", "DEF_hand_L"),
                ("arm_1_L", "arm_1_ik_L"),
                ("arm_2_L", "arm_2_ik_L"),
                ("hand_L", "hand_ik_L"),
                ("arm_1_L", "arm_1_fk_L"),
                ("arm_2_L", "arm_2_fk_L"),
                ("hand_L", "hand_fk_L"),
                ("finger_1_1_L", "DEF_finger_1_1_L"),
                ("finger_1_2_L", "DEF_finger_1_2_L"),
                ("finger_1_3_L", "DEF_finger_1_3_L"),
                ("finger_2_1_L", "DEF_finger_2_1_L"),
                ("finger_2_2_L", "DEF_finger_2_2_L"),
                ("finger_2_3_L", "DEF_finger_2_3_L"),
                ("finger_3_1_L", "DEF_finger_3_1_L"),
                ("finger_3_2_L", "DEF_finger_3_2_L"),
                ("finger_3_3_L", "DEF_finger_3_3_L"),
                ("finger_4_1_L", "DEF_finger_4_1_L"),
                ("finger_4_2_L", "DEF_finger_4_2_L"),
                ("finger_4_3_L", "DEF_finger_4_3_L"),
                ("thumb_1_L", "DEF_thumb_1_L"),
                ("thumb_2_L", "DEF_thumb_2_L"),
                ("thumb_3_L", "DEF_thumb_3_L"),
                ("leg_1_L", "DEF_leg_1_L"),
                ("leg_2_L", "leg_2_L"),
                ("foot_L", "foot_L"),
                ("foot_1_L", "DEF_foot_1_L"),
                ("foot_2_L", "DEF_foot_2_L"),
                ("leg_1_L", "leg_1_ik_L"),
                ("leg_2_L", "leg_2_ik_L"),
                ("foot_L", "foot_ik_L"),
                ("leg_1_L", "leg_1_fk_L"),
                ("leg_2_L", "leg_2_fk_L"),
                ("foot_L", "foot_fk_L"),]

arm_tiwst_bones = ["DEF_arm_2_twist_1_L",
                    "DEF_arm_2_twist_2_L",
                    "DEF_arm_2_twist_3_L"]

leg_tiwst_bones = ["DEF_leg_2_twist_1_L",
                    "DEF_leg_2_twist_2_L",
                    "DEF_leg_2_twist_3_L"]

ctrl_arm_ik_fk = "CTRL_arm_ik_fk_L"
ctrl_leg_ik_fk = "CTRL_leg_ik_fk_L"

ctrl_arm_ik_pole_vector = "CTRL_arm_ik_pole_vector_L"
arm_ik_target = "arm_ik_target_L"
ctrl_leg_ik_pole_vector = "CTRL_leg_ik_pole_vector_L"
leg_ik_target = "leg_ik_target_L"


def refresh_viewport():
    bpy.context.view_layer.update()
    for area in bpy.context.screen.areas:
        area.tag_redraw()
    bpy.context.evaluated_depsgraph_get().update()

def end():
    deselect_all_objects()
    bpy.data.objects["template"].hide_viewport = True

def select_armatures():
    deselect_all_objects()
    template_armature = bpy.data.objects["template"]
    bpy.context.view_layer.objects.active = template_armature
    rig_armature = bpy.data.objects["rig"]
    template_armature.hide_viewport = False
    rig_armature.hide_viewport = False

    bpy.ops.object.mode_set(mode="OBJECT")
    template_armature.select_set(True)
    rig_armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    
    return template_armature, rig_armature

def select_rig_armature():
    deselect_all_objects()
    rig_armature = bpy.data.objects["rig"]

    bpy.ops.object.mode_set(mode="OBJECT")
    rig_armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    
    return rig_armature

def deselect_all_objects():
    for obj in bpy.context.view_layer.objects:
        if not obj.hide_viewport:
            obj.select_set(False)
    bpy.context.view_layer.update()

def align_edit_bones(rig_bone, target):
    rig_bone.head = target.head
    rig_bone.tail = target.tail
    rig_bone.roll = target.roll

def align_base_bones():
    template_armature, rig_armature = select_armatures()
    for bone_tuple in bones_tuples:
        target = template_armature.data.edit_bones[bone_tuple[0]]
        rig_bone = rig_armature.data.edit_bones[bone_tuple[1]]
        align_edit_bones(rig_bone, target)

def align_arm_twist_bones():
    template_armature, rig_armature = select_armatures()
    arm_2_bone = template_armature.data.edit_bones["arm_2_L"]
    first_twist_bone = rig_armature.data.edit_bones[arm_tiwst_bones[0]]
    second_twist_bone = rig_armature.data.edit_bones[arm_tiwst_bones[1]]
    third_twist_bone = rig_armature.data.edit_bones[arm_tiwst_bones[2]]
    first_twist_bone.head = arm_2_bone.head
    t = 1/3
    first_twist_bone.tail = (1-t) * arm_2_bone.head + t*arm_2_bone.tail
    t = 2/3
    second_twist_bone.tail = (1-t) * arm_2_bone.head + t*arm_2_bone.tail
    third_twist_bone.tail = arm_2_bone.tail

def align_leg_twist_bones():
    template_armature, rig_armature = select_armatures()
    leg_2_bone = template_armature.data.edit_bones["leg_2_L"]
    first_twist_bone = rig_armature.data.edit_bones[leg_tiwst_bones[0]]
    second_twist_bone = rig_armature.data.edit_bones[leg_tiwst_bones[1]]
    third_twist_bone = rig_armature.data.edit_bones[leg_tiwst_bones[2]]
    first_twist_bone.head = leg_2_bone.head
    t = 1/3
    first_twist_bone.tail = (1-t) * leg_2_bone.head + t*leg_2_bone.tail
    t = 2/3
    second_twist_bone.tail = (1-t) * leg_2_bone.head + t*leg_2_bone.tail
    third_twist_bone.tail = leg_2_bone.tail

def place_ik_fk_ctrls():
    template_armature, rig_armature = select_armatures()
    arm_ik_fk_ctrl = rig_armature.data.edit_bones[ctrl_arm_ik_fk]
    target_hand = template_armature.data.edit_bones["hand_L"]
    align_edit_bones(arm_ik_fk_ctrl, target_hand)
    arm_ik_fk_ctrl.head += mathutils.Vector((2.0, 0.0, 1.0))
    arm_ik_fk_ctrl.tail = arm_ik_fk_ctrl.head + mathutils.Vector((0.0, 0.0, 1.0))
    arm_ik_fk_ctrl.roll = 0
    
    leg_ik_fk_ctrl = rig_armature.data.edit_bones[ctrl_leg_ik_fk]
    target_foot = template_armature.data.edit_bones["foot_L"]
    align_edit_bones(leg_ik_fk_ctrl, target_foot)
    leg_ik_fk_ctrl.head += mathutils.Vector((2.0, 0.0, 1.0))
    leg_ik_fk_ctrl.tail = leg_ik_fk_ctrl.head + mathutils.Vector((0.0, 0.0, 1.0))
    leg_ik_fk_ctrl.roll = 0

def place_ik_pole_vector_and_target():
    template_armature, rig_armature = select_armatures()
    
    head = template_armature.data.edit_bones["arm_1_L"].tail + mathutils.Vector((0.0, 5.0, 0.0))
    ctrl_arm_ik_pole_vector_ = rig_armature.data.edit_bones[ctrl_arm_ik_pole_vector]
    arm_ik_target_ = rig_armature.data.edit_bones[arm_ik_target]
    ctrl_arm_ik_pole_vector_.head = head
    arm_ik_target_.head = head
    ctrl_arm_ik_pole_vector_.tail = head + mathutils.Vector((0.0, 0.0, 1.0))
    arm_ik_target_.tail = head + mathutils.Vector((0.0, 0.0, 1.0))
    
    head = template_armature.data.edit_bones["leg_1_L"].tail + mathutils.Vector((0.0, -5.0, 0.0))
    ctrl_leg_ik_pole_vector_ = rig_armature.data.edit_bones[ctrl_leg_ik_pole_vector]
    leg_ik_target_ = rig_armature.data.edit_bones[leg_ik_target]
    ctrl_leg_ik_pole_vector_.head = head
    leg_ik_target_.head = head
    ctrl_leg_ik_pole_vector_.tail = head + mathutils.Vector((0.0, 0.0, 1.0))
    leg_ik_target_.tail = head + mathutils.Vector((0.0, 0.0, 1.0))

def symmetrize_rig_armature():
    rig_armature = select_rig_armature()
    all_vis = rig_armature.data.collections_all["all"].is_visible
    deform_bones = rig_armature.data.collections_all["deform_bones"].is_visible
    control_bones = rig_armature.data.collections_all["control_bones"].is_visible

    rig_armature.data.collections_all["all"].is_visible = True
    rig_armature.data.collections_all["deform_bones"].is_visible = True
    rig_armature.data.collections_all["control_bones"].is_visible = True

    for bone in rig_armature.data.edit_bones:
        bone.select = True
    
    # Force update of selection
    rig_armature.update_tag()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.view_layer.update()
    
    bpy.ops.armature.symmetrize(direction='POSITIVE_X')
    rig_armature.update_tag()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.view_layer.update()
    
    copy_pose_drivers()
    copy_armature_data_drivers()

    rig_armature.data.collections_all["all"].is_visible = all_vis
    rig_armature.data.collections_all["deform_bones"].is_visible = deform_bones
    rig_armature.data.collections_all["control_bones"].is_visible = control_bones

def copy_pose_drivers():
    rig_armature = select_rig_armature()
    for fcurve in (rig_armature.animation_data.drivers):
            if '_R' in fcurve.data_path:
                continue
            new_fcurve = rig_armature.driver_add(fcurve.data_path.replace('_L', '_R'))
            copy_fcurve_properties(fcurve, new_fcurve) 

def copy_armature_data_drivers():
    rig_armature = select_rig_armature()
    armature_data = rig_armature.data
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

def import_rig_template():
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.realpath(__file__))
    
    # Specify the blend file name (must be in the same directory as the script)
    blend_file_name = "leo_rig.blend"  # Replace with your .blend file name
    
    # Full path to the blend file
    blend_file_path = os.path.join(script_dir, blend_file_name)
    
    # The path inside the .blend file to append from
    data_path = "Collection"  # Target collections in the blend file
    
    # Name of the collection to append
    collection_name = "leo_rig"  # Replace with the name of the collection you want to append
    
    # Open the blend file and append the collection
    with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
        # Check if the collection exists in the blend file
        if collection_name in data_from.collections:
            # Append the collection by name
            data_to.collections = [collection_name]
        else:
            print(f"Collection '{collection_name}' not found in the blend file.")
            return
    
    # Link the appended collection to the current scene
    for collection in data_to.collections:
        if collection is not None:
            bpy.context.scene.collection.children.link(collection)
            print(f"Appended collection '{collection.name}' to the scene.")


def build_rig():
    align_base_bones()
    align_arm_twist_bones()
    align_leg_twist_bones()
    place_ik_fk_ctrls()
    place_ik_pole_vector_and_target()
    symmetrize_rig_armature()
    end()
