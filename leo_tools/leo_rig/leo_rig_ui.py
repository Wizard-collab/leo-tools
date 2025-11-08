import bpy
from leo_tools import blender_tools
from leo_tools.leo_rig import leo_rig
import os
import importlib
importlib.reload(blender_tools)


class leo_rig_ui(bpy.types.Panel):
    bl_label = "leo_rig_ui"  # The name of the panel
    bl_idname = "VIEW3D_PT_leo_rig"  # Unique ID for the panel
    bl_space_type = 'VIEW_3D'  # Panel location
    # Region (e.g., 'UI' for the N-panel, 'TOOLS' for the T-panel)
    bl_region_type = 'UI'
    bl_category = "Leo rig"  # Tab name in the N-panel

    def draw(self, context):
        layout = self.layout
        layout.label(text="Build")
        layout.operator("leo_rig.import_rig_template",
                        text="Import rig template")
        layout.operator("leo_rig.build_rig", text="Build rig")
        layout.label(text="Manipulate")
        layout.operator("leo_rig.switch_fk_ik", text="Switch FK/IK")
        layout.operator("leo_rig.ik_to_fk", text="snap IK > FK")
        layout.operator("leo_rig.fk_to_ik", text="snap FK > IK")


class import_leo_rig(bpy.types.Operator):
    bl_idname = "leo_rig.import_rig_template"
    bl_label = "Import rig template"
    bl_description = "Import rig template"

    def execute(self, context):
        import_rig_template()
        return {'FINISHED'}


class b_rig(bpy.types.Operator):
    bl_idname = "leo_rig.build_rig"
    bl_label = "Build rig from template"
    bl_description = "Build rig from template"

    def execute(self, context):
        build_rig()
        return {'FINISHED'}


class switch_fk_ik(bpy.types.Operator):
    bl_idname = "leo_rig.switch_fk_ik"
    bl_label = "FK/IK switch"
    bl_description = "FK/IK switch"

    def execute(self, context):
        fk_ik_switch()
        return {'FINISHED'}


class ik_fk(bpy.types.Operator):
    bl_idname = "leo_rig.ik_to_fk"
    bl_label = "Snap IK on FK"
    bl_description = "Snap IK on FK"

    def execute(self, context):
        ik_to_fk_snap()
        return {'FINISHED'}


class fk_ik(bpy.types.Operator):
    bl_idname = "leo_rig.fk_to_ik"
    bl_label = "Snap FK on IK"
    bl_description = "Snap FK on IK"

    def execute(self, context):
        fk_to_ik_snap()
        return {'FINISHED'}


def refresh_viewport():
    bpy.context.view_layer.update()
    for area in bpy.context.screen.areas:
        area.tag_redraw()
    bpy.context.evaluated_depsgraph_get().update()


def ik_to_fk_snap():
    armature = bpy.context.object
    selected_bone = [
        bone for bone in armature.pose.bones if bone.bone.select][0]
    if "leg" in selected_bone.name:
        if '_L' in selected_bone.name:
            align_bn_to_bn(
                armature.pose.bones['foot_ik_L'], armature.pose.bones['foot_fk_L'])
            align_bn_to_bn(
                armature.pose.bones['CTRL_leg_ik_pole_vector_L'], armature.pose.bones['leg_ik_target_L'])
        else:
            align_bn_to_bn(
                armature.pose.bones['foot_ik_R'], armature.pose.bones['foot_fk_R'])
            align_bn_to_bn(
                armature.pose.bones['CTRL_leg_ik_pole_vector_R'], armature.pose.bones['leg_ik_target_R'])
    if "arm" in selected_bone.name:
        if '_L' in selected_bone.name:
            align_bn_to_bn(
                armature.pose.bones['hand_ik_L'], armature.pose.bones['hand_fk_L'])
            align_bn_to_bn(
                armature.pose.bones['CTRL_arm_ik_pole_vector_L'], armature.pose.bones['arm_ik_target_L'])
        else:
            align_bn_to_bn(
                armature.pose.bones['hand_ik_R'], armature.pose.bones['hand_fk_R'])
            align_bn_to_bn(
                armature.pose.bones['CTRL_arm_ik_pole_vector_R'], armature.pose.bones['arm_ik_target_R'])


def fk_to_ik_snap():
    armature = bpy.context.object
    selected_bone = [
        bone for bone in armature.pose.bones if bone.bone.select][0]
    if "leg" in selected_bone.name:
        if '_L' in selected_bone.name:
            align_bn_to_bn(
                armature.pose.bones['leg_1_fk_L'], armature.pose.bones['leg_1_ik_L'])
            align_bn_to_bn(
                armature.pose.bones['leg_2_fk_L'], armature.pose.bones['leg_2_ik_L'])
            align_bn_to_bn(
                armature.pose.bones['foot_fk_L'], armature.pose.bones['foot_ik_L'])
        else:
            align_bn_to_bn(
                armature.pose.bones['leg_1_fk_R'], armature.pose.bones['leg_1_ik_R'])
            align_bn_to_bn(
                armature.pose.bones['leg_2_fk_R'], armature.pose.bones['leg_2_ik_R'])
            align_bn_to_bn(
                armature.pose.bones['foot_fk_R'], armature.pose.bones['foot_ik_R'])
    if "arm" in selected_bone.name:
        if '_L' in selected_bone.name:
            align_bn_to_bn(
                armature.pose.bones['arm_1_fk_L'], armature.pose.bones['arm_1_ik_L'])
            align_bn_to_bn(
                armature.pose.bones['arm_2_fk_L'], armature.pose.bones['arm_2_ik_L'])
            align_bn_to_bn(
                armature.pose.bones['hand_fk_L'], armature.pose.bones['hand_ik_L'])
        else:
            align_bn_to_bn(
                armature.pose.bones['arm_1_fk_R'], armature.pose.bones['arm_1_ik_R'])
            align_bn_to_bn(
                armature.pose.bones['arm_2_fk_R'], armature.pose.bones['arm_2_ik_R'])
            align_bn_to_bn(
                armature.pose.bones['hand_fk_R'], armature.pose.bones['hand_ik_R'])


def fk_ik_switch():
    armature = bpy.context.object
    selected_bone = [
        bone for bone in armature.pose.bones if bone.bone.select][0]
    selected_bone["fk/ik"] = 1.0-selected_bone["fk/ik"]
    armature.update_tag()
    bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="POSE")


def import_rig_template():
    leo_rig.import_rig_template()


def build_rig():
    leo_rig.build_rig()


def align_bn_to_bn(bone, target):
    bone.matrix = target.matrix
    refresh_viewport()


def register():
    bpy.utils.register_class(leo_rig_ui)
    bpy.utils.register_class(import_leo_rig)
    bpy.utils.register_class(b_rig)
    bpy.utils.register_class(switch_fk_ik)
    bpy.utils.register_class(ik_fk)
    bpy.utils.register_class(fk_ik)


def unregister():
    bpy.utils.unregister_class(leo_rig_ui)


if __name__ == "__main__":
    register()
