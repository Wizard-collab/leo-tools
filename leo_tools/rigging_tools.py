import re
import bpy
import mathutils
from leo_tools import corrective_shapekey
from leo_tools import intermediate_shapekey
from leo_tools import position_driven_shapekey
from leo_tools import mirror_shapekeys
from leo_tools import combo_shapekey


class RiggingPanel(bpy.types.Panel):
    bl_label = "Rigging"
    bl_idname = "VIEW3D_PT_leo_rigging"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Rigging"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Drivers")
        layout.operator("leo_tools.mirror_rig_drivers",
                        text="Mirror rig drivers")
        layout.operator("leo_tools.copy_bone_driver",
                text="Copy driver to selected bones")
        layout.separator()
        layout.label(text="Shape Keys")
        layout.operator("mesh.create_corrective_shapekey",
                        text="Create Corrective Shape Key")
        layout.operator("mesh.create_intermediate_shapekey",
                        text="Create Intermediate Shape Key")
        layout.operator("mesh.create_position_driven_shapekey",
                        text="Add Position Driver")
        layout.operator("mesh.mirror_shapekeys_and_drivers",
                        text="Mirror Shape Keys L→R")
        layout.operator("mesh.create_combo_shapekey",
                        text="Create Combo Shape Key")
        layout.separator()
        layout.label(text="Utils")
        layout.operator("mesh.create_empty_from_vertices",
                        text="Empty from 3 Vertices")
        layout.operator("leo_tools.create_cage_deform_joints",
                        text="Create cage deform joints")
        layout.operator("leo_tools.organize_bones",
                        text="Organize bones (deform + collections)")
        layout.operator("leo_tools.duplicate_mirror_object",
                        text="Duplicate + mirror (world origin)")
        layout.operator("leo_tools.mirror_vertex_weights",
                        text="Mirror vertex weights")
        layout.separator()
        layout.label(text="Bone Constraints")
        layout.operator("leo_tools.add_copy_transforms_constraint",
                        text="Add copy transforms constraint")
        layout.operator("leo_tools.add_child_of_constraint",
                        text="Add child of constraint")
        layout.operator("leo_tools.reset_child_of_inverse",
                        text="Reset child of inverse")
        layout.operator("leo_tools.retarget_shrinkwrap_constraints",
                        text="Retarget shrinkwrap constraints")
        layout.operator("leo_tools.copy_bone_shape",
                        text="Copy controller shape")
        layout.operator("leo_tools.cleanup_duplicate_bone_shapes",
                        text="Clean up duplicate control shapes")
        layout.operator("leo_tools.copy_specific_constraints",
                        text="Copy specific constraints")
        layout.operator("leo_tools.symmetrize_bone_constraints",
                        text="Symmetrize bone constraints")
        layout.operator("leo_tools.blend_bone_chain",
                        text="Blend chain between two bones")
        layout.separator()
        layout.label(text="Symmetry")
        layout.operator("leo_tools.symmetrize_rig",
                        text="Symmetrize Rig (bones, constraints, drivers)")


class create_cage_deform_joints(bpy.types.Operator):
    bl_idname = "leo_tools.create_cage_deform_joints"
    bl_label = "Create cage deform joints"
    bl_description = "Create a joint for each vertex of the selected mesh, named by vertex ID with _CAGE_DEFORM suffix"

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object")
            return {'CANCELLED'}

        mesh = obj.data
        mesh_name = obj.name

        # Create armature
        armature_data = bpy.data.armatures.new(f"{mesh_name}_CAGE_DEFORM")
        armature_obj = bpy.data.objects.new(
            f"{mesh_name}_CAGE_DEFORM", armature_data)
        context.collection.objects.link(armature_obj)

        # Position armature at mesh location
        armature_obj.location = obj.location
        armature_obj.rotation_euler = obj.rotation_euler
        armature_obj.scale = obj.scale

        # Enter edit mode to create bones
        context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='EDIT')

        # Create a bone for each vertex
        for vert in mesh.vertices:
            bone_name = f"{vert.index}_CAGE_DEFORM"
            bone = armature_data.edit_bones.new(bone_name)
            # Get vertex position in world space
            world_pos = obj.matrix_world @ vert.co
            # Convert to armature local space
            local_pos = armature_obj.matrix_world.inverted() @ world_pos
            bone.head = local_pos
            bone.tail = local_pos + mathutils.Vector((0, 0, 0.1))

        bpy.ops.object.mode_set(mode='OBJECT')

        self.report(
            {'INFO'}, f"Created {len(mesh.vertices)} joints for cage deform")
        return {'FINISHED'}


class duplicate_mirror_object(bpy.types.Operator):
    bl_idname = "leo_tools.duplicate_mirror_object"
    bl_label = "Duplicate + Mirror Object"
    bl_description = "Duplicate selected object(s) on the +X side and mirror them to -X across the world origin"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def execute(self, context):
        mirror_matrix = mathutils.Matrix.Scale(-1, 4, (1, 0, 0))
        source_objects = [
            obj for obj in context.selected_objects
            if obj.matrix_world.translation.x > 0]

        if not source_objects:
            self.report(
                {'WARNING'}, "No selected object is on the +X side")
            return {'CANCELLED'}

        created = []
        for obj in source_objects:
            new_obj = obj.copy()
            if obj.data:
                new_obj.data = obj.data.copy()
            new_obj.name = f"{obj.name}_mirror"
            # Parenting carries a matrix_parent_inverse computed for the
            # original transform, which would offset the mirrored copy.
            new_obj.parent = None

            collections = obj.users_collection or (context.collection,)
            for coll in collections:
                coll.objects.link(new_obj)

            new_obj.matrix_world = mirror_matrix @ obj.matrix_world
            created.append(new_obj)

        for obj in context.selected_objects:
            obj.select_set(False)
        for new_obj in created:
            new_obj.select_set(True)
        if created:
            context.view_layer.objects.active = created[-1]

        self.report(
            {'INFO'}, f"Duplicated and mirrored {len(created)} object(s) from +X to -X")
        return {'FINISHED'}


class mirror_vertex_weights(bpy.types.Operator):
    bl_idname = "leo_tools.mirror_vertex_weights"
    bl_label = "Mirror Vertex Weights"
    bl_description = "Mirror all vertex group weights from one half of the mesh onto the other, across X=0"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        name="Direction",
        description="Which half receives the mirrored weights",
        items=[
            ('NEGATIVE_TO_POSITIVE', "-X to +X",
             "Copy weights from the -X side onto the +X side"),
            ('POSITIVE_TO_NEGATIVE', "+X to -X",
             "Copy weights from the +X side onto the -X side"),
        ],
        default='POSITIVE_TO_NEGATIVE',
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.vertex_groups

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        original_mode = obj.mode
        original_mask = mesh.use_paint_mask_vertex

        # The mirror operator only overwrites selected vertices, so select the
        # destination half instead of going through edit mode + mask by hand.
        select_positive = self.direction == 'NEGATIVE_TO_POSITIVE'
        for v in mesh.vertices:
            v.select = (v.co.x > 0) if select_positive else (v.co.x < 0)

        if obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        mesh.use_paint_mask_vertex = True
        bpy.ops.object.vertex_group_mirror(
            all_groups=True, use_topology=False)
        mesh.use_paint_mask_vertex = original_mask
        bpy.ops.object.mode_set(mode='OBJECT')
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode=original_mode)

        self.report(
            {'INFO'}, f"Mirrored vertex weights ({self.direction.replace('_', ' ').lower()})")
        return {'FINISHED'}


class mirror_rig_drivers(bpy.types.Operator):
    bl_idname = "leo_tools.mirror_rig_drivers"
    bl_label = "Mirror the rig drivers"
    bl_description = "Mirror the rig drivers"

    def execute(self, context):
        copy_rig_drivers()
        return {'FINISHED'}


def pose_bone_driver_items(self, context):
    armature_obj = context.active_object
    source = context.active_pose_bone
    if not armature_obj or not source or not armature_obj.animation_data:
        return []

    bone_path = source.path_from_id()
    items = []
    for fcurve in armature_obj.animation_data.drivers:
        if not fcurve.data_path.startswith(bone_path):
            continue
        key = f"{fcurve.data_path}|{fcurve.array_index}"
        label = fcurve.data_path.removeprefix(f"{bone_path}.")
        if fcurve.array_index >= 0:
            label = f"{label} [{fcurve.array_index}]"
        items.append((key, label, f"Copy this driver from '{source.name}'"))
    return items


class copy_bone_driver(bpy.types.Operator):
    bl_idname = "leo_tools.copy_bone_driver"
    bl_label = "Copy Driver to Selected Bones"
    bl_description = "Copy one driver from the active bone to every other selected bone"
    bl_options = {'REGISTER', 'UNDO'}

    driver_key: bpy.props.EnumProperty(name="Driver", items=pose_bone_driver_items)

    @classmethod
    def poll(cls, context):
        armature_obj = context.active_object
        return (context.mode == 'POSE' and context.active_pose_bone
                and context.selected_pose_bones
                and len(context.selected_pose_bones) > 1
                and armature_obj.animation_data
                and armature_obj.animation_data.drivers)

    def invoke(self, context, event):
        if not pose_bone_driver_items(self, context):
            self.report({'ERROR'}, "The active bone has no drivers")
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "driver_key")

    def execute(self, context):
        armature_obj = context.active_object
        source = context.active_pose_bone
        source_path, array_index = self.driver_key.rsplit('|', 1)
        array_index = int(array_index)
        source_fcurve = next(
            (fcurve for fcurve in armature_obj.animation_data.drivers
             if fcurve.data_path == source_path and fcurve.array_index == array_index),
            None)
        if source_fcurve is None:
            self.report({'ERROR'}, "The selected source driver no longer exists")
            return {'CANCELLED'}

        source_bone_path = source.path_from_id()
        copied_count = 0
        for target in context.selected_pose_bones:
            if target == source:
                continue
            target_path = source_path.replace(
                source_bone_path, target.path_from_id(), 1)
            try:
                armature_obj.driver_remove(target_path, array_index)
            except (TypeError, ValueError):
                try:
                    armature_obj.driver_remove(target_path)
                except (TypeError, ValueError):
                    pass
            try:
                target_fcurve = armature_obj.driver_add(target_path, array_index)
            except TypeError:
                target_fcurve = armature_obj.driver_add(target_path)
            copy_fcurve_properties(source_fcurve, target_fcurve, mirror_targets=False)
            copied_count += 1

        self.report({'INFO'}, f"Copied driver to {copied_count} bone(s)")
        return {'FINISHED'}


class add_copy_transforms_constraint(bpy.types.Operator):
    bl_idname = "leo_tools.add_copy_transforms_constraint"
    bl_label = "Add Copy Transforms Constraint"
    bl_description = "Add a Copy Transforms constraint on the active bone, targeting the first selected bone"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and context.active_pose_bone
                and context.selected_pose_bones
                and len(context.selected_pose_bones) > 1)

    def execute(self, context):
        owner = context.active_pose_bone
        target = next(
            (b for b in context.selected_pose_bones if b != owner), None)
        if target is None:
            self.report(
                {'ERROR'}, "Select at least two bones (target bone, then the active bone)")
            return {'CANCELLED'}

        con = owner.constraints.new('COPY_TRANSFORMS')
        con.target = context.active_object
        con.subtarget = target.name

        self.report(
            {'INFO'}, f"Added Copy Transforms on '{owner.name}' targeting '{target.name}'")
        return {'FINISHED'}


class add_child_of_constraint(bpy.types.Operator):
    bl_idname = "leo_tools.add_child_of_constraint"
    bl_label = "Add Child Of Constraint"
    bl_description = "Add a Child Of constraint on the active bone, targeting the first selected bone"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and context.active_pose_bone
                and context.selected_pose_bones
                and len(context.selected_pose_bones) > 1)

    def execute(self, context):
        armature_obj = context.active_object
        owner = context.active_pose_bone
        target = next(
            (b for b in context.selected_pose_bones if b != owner), None)
        if target is None:
            self.report(
                {'ERROR'}, "Select at least two bones (target bone, then the active bone)")
            return {'CANCELLED'}

        con = owner.constraints.new('CHILD_OF')
        con.target = armature_obj
        con.subtarget = target.name

        armature_obj.data.bones.active = owner.bone
        bpy.ops.constraint.childof_set_inverse(
            constraint=con.name, owner='BONE')

        self.report(
            {'INFO'}, f"Added Child Of on '{owner.name}' targeting '{target.name}'")
        return {'FINISHED'}


def reset_child_of_inverses(armature_obj, bones, context):
    """Recompute the Set Inverse matrix of every Child Of constraint owned by `bones`.

    Every constraint on the owner bones AND their Child Of targets is muted first,
    so the inverse is computed against a clean, un-constrained transform (matching
    Blender's clear+set inverse behaviour), then all constraints are restored.
    Returns the number of Child Of constraints reset."""
    pose_bones = armature_obj.pose.bones

    affected_bones = set()
    child_of_cons = []
    for bone in bones:
        for con in bone.constraints:
            if con.type != 'CHILD_OF' or not con.target:
                continue
            target_bone = (pose_bones.get(con.subtarget)
                            if con.target == armature_obj else None)
            child_of_cons.append((con, target_bone))
            affected_bones.add(bone)
            if target_bone is not None:
                affected_bones.add(target_bone)

    if not child_of_cons:
        return 0

    # Mute so the inverse is computed against the clean, un-constrained
    # transform, then force a depsgraph update before reading it back.
    original_enabled = {}
    for bone in affected_bones:
        for con in bone.constraints:
            original_enabled[con] = con.enabled
            con.enabled = False
    context.view_layer.update()

    for con, target_bone in child_of_cons:
        if target_bone is not None:
            con.inverse_matrix = target_bone.matrix.inverted()
        else:
            con.inverse_matrix = con.target.matrix_world.inverted()

    for con, enabled in original_enabled.items():
        con.enabled = enabled

    return len(child_of_cons)


class reset_child_of_inverse(bpy.types.Operator):
    bl_idname = "leo_tools.reset_child_of_inverse"
    bl_label = "Reset Child Of Inverse"
    bl_description = "Mute every constraint on the selected bone(s) and their Child Of target(s), reset the inverse, then restore all constraints"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'POSE' and context.selected_pose_bones

    def execute(self, context):
        armature_obj = context.active_object
        reset_count = reset_child_of_inverses(
            armature_obj, context.selected_pose_bones, context)

        if reset_count == 0:
            self.report(
                {'WARNING'}, "No Child Of constraint found on the selected bone(s)")
            return {'CANCELLED'}

        self.report(
            {'INFO'}, f"Reset inverse on {reset_count} Child Of constraint(s)")
        return {'FINISHED'}


def _shrinkwrap_retarget_items(self, context):
    old_target = getattr(self, '_old_target', None)
    items = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj != old_target:
            items.append((obj.name, obj.name, f"Retarget shrinkwraps to '{obj.name}'"))
    return items


class retarget_shrinkwrap_constraints(bpy.types.Operator):
    bl_idname = "leo_tools.retarget_shrinkwrap_constraints"
    bl_label = "Retarget Shrinkwrap Constraints"
    bl_description = ("Select a mesh and an armature: every Shrinkwrap bone constraint "
                       "targeting that mesh gets retargeted to another mesh you choose")
    bl_options = {'REGISTER', 'UNDO'}

    new_target: bpy.props.EnumProperty(
        name="New Target",
        description="Mesh to use instead on matching Shrinkwrap constraints",
        items=_shrinkwrap_retarget_items,
    )

    @classmethod
    def poll(cls, context):
        return (context.selected_objects and len(context.selected_objects) == 2
                and any(obj.type == 'ARMATURE' for obj in context.selected_objects)
                and any(obj.type == 'MESH' for obj in context.selected_objects))

    def invoke(self, context, event):
        armature_obj, old_target = self._get_armature_and_mesh(context)
        if armature_obj is None or old_target is None:
            self.report(
                {'ERROR'}, "Select exactly one mesh and one armature")
            return {'CANCELLED'}

        self._old_target = old_target
        if not _shrinkwrap_retarget_items(self, context):
            self.report(
                {'ERROR'}, "No other mesh object found to retarget to")
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "new_target")

    @staticmethod
    def _get_armature_and_mesh(context):
        armature_obj = next(
            (obj for obj in context.selected_objects if obj.type == 'ARMATURE'), None)
        old_target = next(
            (obj for obj in context.selected_objects if obj.type == 'MESH'), None)
        return armature_obj, old_target

    def execute(self, context):
        armature_obj, old_target = self._get_armature_and_mesh(context)
        if armature_obj is None or old_target is None:
            self.report(
                {'ERROR'}, "Select exactly one mesh and one armature")
            return {'CANCELLED'}

        new_target = bpy.data.objects.get(self.new_target)
        if new_target is None:
            self.report({'ERROR'}, "Chosen replacement mesh no longer exists")
            return {'CANCELLED'}

        changed = 0
        for bone in armature_obj.pose.bones:
            for con in bone.constraints:
                if con.type == 'SHRINKWRAP' and con.target == old_target:
                    con.target = new_target
                    changed += 1

        if changed == 0:
            self.report(
                {'WARNING'}, f"No Shrinkwrap constraint targeting '{old_target.name}' was found")
            return {'CANCELLED'}

        self.report(
            {'INFO'}, f"Retargeted {changed} Shrinkwrap constraint(s) from "
            f"'{old_target.name}' to '{new_target.name}'")
        return {'FINISHED'}


class blend_bone_chain(bpy.types.Operator):
    bl_idname = "leo_tools.blend_bone_chain"
    bl_label = "Blend Chain Between Two Bones"
    bl_description = ("Create STP_ helper bones (root proxy, tip proxy, blend) for each "
                       "bone between two endpoint bones. The blend bone follows both ends "
                       "via two weighted Copy Transforms constraints, and the original bone "
                       "gets a Child Of constraint targeting it, so it can still be animated "
                       "on top. Uses the parent/child chain when available, otherwise orders "
                       "bones by distance between the two farthest-apart bones")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and context.active_object
                and context.active_object.type == 'ARMATURE'
                and context.selected_pose_bones
                and len(context.selected_pose_bones) >= 3)

    def execute(self, context):
        armature_obj = context.active_object

        chain = order_bone_chain(context.selected_pose_bones)
        if chain is None:
            chain = order_bone_chain_by_distance(context.selected_pose_bones)
        if chain is None:
            self.report(
                {'ERROR'}, "Could not determine two endpoint bones from the selection")
            return {'CANCELLED'}

        root, *middle, tip = chain
        count = len(middle)
        root_name, tip_name = root.name, tip.name
        middle_names = [(bone.name, index / (count + 1))
                         for index, bone in enumerate(middle, start=1)]

        stp_names = []
        for bone_name, t in middle_names:
            base_name, side_suffix = split_side_suffix(bone_name)
            # Replace a leading CTRL_ with STP_ instead of stacking both prefixes.
            base_name = base_name.removeprefix('CTRL_')
            stp_names.extend([
                f"STP_{base_name}_ROOT_PROXY{side_suffix}",
                f"STP_{base_name}_TIP_PROXY{side_suffix}",
                f"STP_{base_name}_BLEND{side_suffix}",
            ])
        cleanup_stp_setup(armature_obj, stp_names)

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = armature_obj.data.edit_bones
        stp_collection = get_or_create_stp_bone_collection(armature_obj.data)

        created = []
        for bone_name, t in middle_names:
            base_name, side_suffix = split_side_suffix(bone_name)
            base_name = base_name.removeprefix('CTRL_')
            root_proxy_name = f"STP_{base_name}_ROOT_PROXY{side_suffix}"
            tip_proxy_name = f"STP_{base_name}_TIP_PROXY{side_suffix}"
            blend_name = f"STP_{base_name}_BLEND{side_suffix}"

            bone_eb = edit_bones[bone_name]

            # Aligned to the chain bone (not root/tip) so Child Of tracks each
            # end's motion delta while preserving the chain bone's own rotation offset.
            proxy_root_eb = edit_bones.new(root_proxy_name)
            proxy_root_eb.head, proxy_root_eb.tail = bone_eb.head, bone_eb.tail
            proxy_root_eb.roll = bone_eb.roll

            proxy_tip_eb = edit_bones.new(tip_proxy_name)
            proxy_tip_eb.head, proxy_tip_eb.tail = bone_eb.head, bone_eb.tail
            proxy_tip_eb.roll = bone_eb.roll

            blend_eb = edit_bones.new(blend_name)
            blend_eb.head, blend_eb.tail = bone_eb.head, bone_eb.tail
            blend_eb.roll = bone_eb.roll

            # New edit bones are selected by default, which would leak into pose
            # mode and get them picked up as part of the chain on the next run.
            for new_eb in (proxy_root_eb, proxy_tip_eb, blend_eb):
                new_eb.select = False
                new_eb.select_head = False
                new_eb.select_tail = False

            if stp_collection is not None:
                stp_collection.assign(proxy_root_eb)
                stp_collection.assign(proxy_tip_eb)
                stp_collection.assign(blend_eb)

            created.append(
                (bone_name, root_proxy_name, tip_proxy_name, blend_name, t))

        bpy.ops.object.mode_set(mode='POSE')

        # Restore selection to just the original chain bones so the STP helper
        # bones (deselected above, but be defensive) never leak into the next run.
        for pbone in armature_obj.pose.bones:
            pbone.select = False
        for bone_name in (root_name, tip_name, *(name for name, *_ in created)):
            armature_obj.pose.bones[bone_name].select = True

        for bone_name, root_proxy_name, tip_proxy_name, blend_name, t in created:
            bone = armature_obj.pose.bones[bone_name]
            proxy_root = armature_obj.pose.bones[root_proxy_name]
            proxy_tip = armature_obj.pose.bones[tip_proxy_name]
            blend_bone = armature_obj.pose.bones[blend_name]

            # The original bone isn't recreated, so its old constraints must be
            # cleared explicitly; the proxy/blend bones are always fresh.
            for con in list(bone.constraints):
                bone.constraints.remove(con)

            armature_obj.data.bones.active = proxy_root.bone
            con = proxy_root.constraints.new('CHILD_OF')
            con.target = armature_obj
            con.subtarget = root_name
            bpy.ops.constraint.childof_set_inverse(
                constraint=con.name, owner='BONE')

            armature_obj.data.bones.active = proxy_tip.bone
            con = proxy_tip.constraints.new('CHILD_OF')
            con.target = armature_obj
            con.subtarget = tip_name
            bpy.ops.constraint.childof_set_inverse(
                constraint=con.name, owner='BONE')

            # Copy Transforms blends the final matrices (slerp/lerp), unlike the
            # nested Child Of stack, so influence 1.0 then t gives a true blend.
            con_root = blend_bone.constraints.new('COPY_TRANSFORMS')
            con_root.target = armature_obj
            con_root.subtarget = root_proxy_name
            con_root.influence = 1.0

            con_tip = blend_bone.constraints.new('COPY_TRANSFORMS')
            con_tip.target = armature_obj
            con_tip.subtarget = tip_proxy_name
            con_tip.influence = t

            # Child Of (not Copy Transforms) so the original bone's own animated
            # channels still apply as an offset on top of the blended follow.
            armature_obj.data.bones.active = bone.bone
            con_follow = bone.constraints.new('CHILD_OF')
            con_follow.target = armature_obj
            con_follow.subtarget = blend_name
            bpy.ops.constraint.childof_set_inverse(
                constraint=con_follow.name, owner='BONE')

        self.report(
            {'INFO'}, f"Blended {count} bone(s) between '{root_name}' and '{tip_name}'")
        return {'FINISHED'}


class organize_bones(bpy.types.Operator):
    bl_idname = "leo_tools.organize_bones"
    bl_label = "Organize Bones"
    bl_description = ("Enable deform only on bones with 'DEF_' in their name, and sort every "
                       "bone into a collection named after its prefix (DEF, STP, CTRL, etc.) "
                       "with a nested sub-collection named after the part that follows it "
                       "(eyes, body, etc.), further split into L/R sub-collections when the "
                       "bone name ends in '_L' or '_R'")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    @staticmethod
    def remove_empty_collections(armature_data):
        # Sweep away leftover collections (e.g. old '.001'/'.002' duplicates
        # from earlier runs) that ended up with no bones and no children,
        # repeating since removing a leaf can empty out its parent too.
        # collections_all is used since it includes nested collections;
        # .collections only lists root-level ones.
        removed_any = True
        while removed_any:
            removed_any = False
            for collection in list(armature_data.collections_all):
                if not collection.bones and not collection.children:
                    print(f"[organize_bones] removing empty collection '{collection.name}'")
                    armature_data.collections.remove(collection)
                    removed_any = True

    def execute(self, context):
        armature_obj = context.active_object
        # Bone collection membership only syncs when leaving edit mode, so
        # bones/collections would look unassigned and get duplicated otherwise.
        original_mode = armature_obj.mode
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

        armature_data = armature_obj.data
        has_collections = hasattr(armature_data, 'collections')

        print(f"[organize_bones] --- start, mode was {original_mode} ---")
        if has_collections:
            print(f"[organize_bones] existing collections before run: "
                  f"{[c.name for c in armature_data.collections_all]}")

        seen_names = set()
        deform_count = 0
        sorted_count = 0

        for bone in armature_data.bones:
            bone.use_deform = 'DEF_' in bone.name
            if bone.use_deform:
                deform_count += 1

            if not has_collections:
                continue
            tokens = bone.name.split('_')
            prefix = tokens[0]
            if not prefix:
                continue

            # Always look collections up fresh by name instead of caching
            # BoneCollection references, since new() calls elsewhere in this
            # loop can invalidate previously fetched python wrappers.
            # collections_all is used since it includes nested collections;
            # .collections only lists root-level ones, so nested part
            # collections would never be found there and get recreated.
            prefix_collection = armature_data.collections_all.get(prefix)
            if prefix_collection is None:
                prefix_collection = armature_data.collections.new(prefix)
                print(f"[organize_bones] bone '{bone.name}': created prefix "
                      f"collection '{prefix_collection.name}' (wanted '{prefix}')")
            seen_names.add(prefix)

            part = tokens[1] if len(tokens) > 1 and tokens[1] else None
            # Ancestor chain the bone should belong to (e.g. DEF, DEF_eye,
            # DEF_eye_L), so it stays visible from any level in the outliner.
            ancestor_collections = [prefix_collection]
            if part:
                # Name includes the prefix so it stays armature-wide unique
                # instead of relying on Blender's '.001' auto-renaming.
                part_name = f"{prefix}_{part}"
                part_collection = armature_data.collections_all.get(part_name)
                if part_collection is None:
                    part_collection = armature_data.collections.new(
                        part_name, parent=prefix_collection)
                    print(f"[organize_bones] bone '{bone.name}': created part "
                          f"collection '{part_collection.name}' (wanted '{part_name}', "
                          f"parent '{prefix_collection.name}')")
                seen_names.add(part_name)
                ancestor_collections.append(part_collection)

                side = tokens[-1] if tokens[-1] in ('L', 'R') else None
                if side:
                    # Name includes prefix+part so it stays armature-wide unique.
                    side_name = f"{part_name}_{side}"
                    side_collection = armature_data.collections_all.get(side_name)
                    if side_collection is None:
                        side_collection = armature_data.collections.new(
                            side_name, parent=part_collection)
                        print(f"[organize_bones] bone '{bone.name}': created side "
                              f"collection '{side_collection.name}' (wanted '{side_name}', "
                              f"parent '{part_collection.name}')")
                    seen_names.add(side_name)
                    ancestor_collections.append(side_collection)

            for other in list(bone.collections):
                if other not in ancestor_collections:
                    other.unassign(bone)
            for collection in ancestor_collections:
                collection.assign(bone)
            sorted_count += 1

        if has_collections:
            print(f"[organize_bones] collections before cleanup: "
                  f"{[(c.name, c.parent.name if c.parent else None, len(c.bones)) for c in armature_data.collections_all]}")
            self.remove_empty_collections(armature_data)
            print(f"[organize_bones] collections after cleanup: "
                  f"{[(c.name, c.parent.name if c.parent else None, len(c.bones)) for c in armature_data.collections_all]}")

        total_collections = len(seen_names)
        self.report(
            {'INFO'},
            f"Set deform on {deform_count} bone(s), sorted {sorted_count} bone(s) into "
            f"{total_collections} collection(s)")
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


def get_or_create_stp_bone_collection(armature_data):
    """Get or create the 'STP' bone collection used to group blend-chain helper bones."""
    if not hasattr(armature_data, 'collections'):
        return None
    collection = armature_data.collections.get('STP')
    if collection is None:
        collection = armature_data.collections.new('STP')
    return collection


def cleanup_stp_setup(armature_obj, stp_names):
    """Remove the given STP_ helper bones (and stale '.NNN' duplicates from a
    fragmented undo/redo) plus any constraint targeting them, scoped to this
    chain only so unrelated STP setups elsewhere in the armature are untouched."""
    name_set = set(stp_names)

    def matches(name):
        return name in name_set or any(name.startswith(n + '.') for n in name_set)

    for pbone in armature_obj.pose.bones:
        for con in [c for c in pbone.constraints
                    if matches(getattr(c, 'subtarget', ''))]:
            pbone.constraints.remove(con)

    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature_obj.data.edit_bones
    for eb in [b for b in edit_bones if matches(b.name)]:
        edit_bones.remove(eb)
    bpy.ops.object.mode_set(mode='POSE')


def split_side_suffix(name):
    """Split a trailing '_L'/'_R'/'_M' side suffix off name, for keeping it at
    the end of generated bone names so mirroring tools still recognize it."""
    for suffix in ('_L', '_R', '_M'):
        if name.endswith(suffix):
            return name[:-len(suffix)], suffix
    return name, ''


def order_bone_chain(selected_bones):
    """Order a set of selected pose bones as a single parent/child chain.

    Returns [root, ...middle bones in order..., tip] or None if the selection
    doesn't form a single continuous chain (branching/disconnected bones)."""
    selected_set = set(selected_bones)
    neighbors = {bone: [] for bone in selected_set}

    for bone in selected_set:
        parent = bone.parent
        if parent in selected_set:
            neighbors[bone].append(parent)
            neighbors[parent].append(bone)

    endpoints = [bone for bone, adj in neighbors.items() if len(adj) == 1]
    if len(endpoints) != 2:
        return None
    if any(len(adj) not in (1, 2) for adj in neighbors.values()):
        return None

    chain = [endpoints[0]]
    previous = None
    current = endpoints[0]
    while len(chain) < len(selected_set):
        next_bones = [b for b in neighbors[current] if b != previous]
        if not next_bones:
            return None
        previous, current = current, next_bones[0]
        chain.append(current)

    if chain[-1] != endpoints[1]:
        return None

    return chain


def order_bone_chain_by_distance(selected_bones):
    """Fallback ordering for bones that aren't parented in a chain.

    Uses the two bones farthest apart (current pose head location) as the
    endpoints, and orders the rest by their projection along that axis."""
    bones = list(selected_bones)
    if len(bones) < 3:
        return None

    root = tip = None
    max_dist = -1.0
    for i, bone_a in enumerate(bones):
        for bone_b in bones[i + 1:]:
            dist = (bone_a.matrix.translation -
                    bone_b.matrix.translation).length
            if dist > max_dist:
                max_dist = dist
                root, tip = bone_a, bone_b

    axis = tip.matrix.translation - root.matrix.translation
    if axis.length == 0:
        return None

    middle = [b for b in bones if b not in (root, tip)]
    middle.sort(key=lambda b: (
        b.matrix.translation - root.matrix.translation).dot(axis))

    return [root] + middle + [tip]


class LEO_TOOLS_PG_constraint_toggle(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(default=True)


class copy_specific_constraints(bpy.types.Operator):
    bl_idname = "leo_tools.copy_specific_constraints"
    bl_label = "Copy Specific Constraints"
    bl_description = "Copy chosen constraints from the active bone to the other selected bones"
    bl_options = {'REGISTER', 'UNDO'}

    constraint_toggles: bpy.props.CollectionProperty(
        type=LEO_TOOLS_PG_constraint_toggle)

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and context.active_pose_bone
                and context.selected_pose_bones
                and len(context.selected_pose_bones) > 1)

    def invoke(self, context, event):
        source = context.active_pose_bone
        if not source.constraints:
            self.report({'WARNING'}, "Active bone has no constraints")
            return {'CANCELLED'}

        self.constraint_toggles.clear()
        for con in source.constraints:
            item = self.constraint_toggles.add()
            item.name = con.name
            item.enabled = True

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        for item in self.constraint_toggles:
            layout.prop(item, "enabled", text=item.name)

    def execute(self, context):
        source = context.active_pose_bone
        targets = [b for b in context.selected_pose_bones if b != source]
        if not targets:
            self.report(
                {'ERROR'}, "Select at least two bones (active bone is the source)")
            return {'CANCELLED'}

        selected_names = {
            item.name for item in self.constraint_toggles if item.enabled}
        if not selected_names:
            self.report({'WARNING'}, "No constraint selected to copy")
            return {'CANCELLED'}

        copied = 0
        for target in targets:
            for con in source.constraints:
                if con.name in selected_names:
                    copy_bone_constraint(con, target)
                    copied += 1

        self.report(
            {'INFO'}, f"Copied {copied} constraint(s) to {len(targets)} bone(s)")
        return {'FINISHED'}


class copy_bone_shape(bpy.types.Operator):
    bl_idname = "leo_tools.copy_bone_shape"
    bl_label = "Copy Controller Shape"
    bl_description = "Copy the custom (controller) shape from the active bone to the other selected bones"
    bl_options = {'REGISTER', 'UNDO'}

    SHAPE_PROPS = (
        'custom_shape',
        'custom_shape_transform',
        'use_custom_shape_bone_size',
        'custom_shape_scale_xyz',
        'custom_shape_translation',
        'custom_shape_rotation_euler',
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and context.active_pose_bone
                and context.selected_pose_bones
                and len(context.selected_pose_bones) > 1)

    def execute(self, context):
        source = context.active_pose_bone
        targets = [b for b in context.selected_pose_bones if b != source]
        if not targets:
            self.report(
                {'ERROR'}, "Select at least two bones (active bone is the source)")
            return {'CANCELLED'}

        for bone in targets:
            for prop in self.SHAPE_PROPS:
                if not hasattr(source, prop):
                    continue
                value = getattr(source, prop)
                # custom_shape/custom_shape_transform are Object references;
                # .copy() on those would duplicate the widget datablock
                # instead of just pointing the target bone at the same one.
                if prop not in ('custom_shape', 'custom_shape_transform') and hasattr(value, 'copy'):
                    value = value.copy()
                setattr(bone, prop, value)

        self.report(
            {'INFO'}, f"Copied controller shape from '{source.name}' to {len(targets)} bone(s)")
        return {'FINISHED'}


def _is_still_used_as_shape(name):
    for armature_obj in bpy.data.objects:
        if armature_obj.type != 'ARMATURE' or not armature_obj.pose:
            continue
        for bone in armature_obj.pose.bones:
            for prop in ('custom_shape', 'custom_shape_transform'):
                shape_obj = getattr(bone, prop, None)
                if shape_obj and shape_obj.name == name:
                    return True
    return False


class cleanup_duplicate_bone_shapes(bpy.types.Operator):
    bl_idname = "leo_tools.cleanup_duplicate_bone_shapes"
    bl_label = "Clean Up Duplicate Control Shapes"
    bl_description = ("Retarget bones using a duplicated control shape object (e.g. "
                       "'WGT_circle.001') back to the original, then delete the duplicate")
    bl_options = {'REGISTER', 'UNDO'}

    SHAPE_PROPS = ('custom_shape', 'custom_shape_transform')

    @staticmethod
    def _base_name(name):
        match = re.match(r'^(.*)\.\d{3}$', name)
        return match.group(1) if match else None

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        retargeted = 0
        duplicate_names = set()

        for armature_obj in bpy.data.objects:
            if armature_obj.type != 'ARMATURE' or not armature_obj.pose:
                continue
            for bone in armature_obj.pose.bones:
                for prop in self.SHAPE_PROPS:
                    shape_obj = getattr(bone, prop, None)
                    if shape_obj is None:
                        continue
                    base_name = self._base_name(shape_obj.name)
                    if base_name is None:
                        continue
                    original = bpy.data.objects.get(base_name)
                    if original is None or original == shape_obj:
                        continue
                    duplicate_names.add(shape_obj.name)
                    setattr(bone, prop, original)
                    retargeted += 1

        deleted = 0
        for name in duplicate_names:
            obj = bpy.data.objects.get(name)
            if obj is None or _is_still_used_as_shape(name):
                continue
            mesh_data = obj.data if obj.type == 'MESH' else None
            bpy.data.objects.remove(obj, do_unlink=True)
            deleted += 1
            if mesh_data and mesh_data.users == 0:
                bpy.data.meshes.remove(mesh_data)

        self.report(
            {'INFO'}, f"Retargeted {retargeted} bone(s), deleted {deleted} duplicate shape object(s)")
        return {'FINISHED'}


def symmetrize_constraints(armature_obj, selected_bones, context):
    """Mirror constraints from '_L' bones (selected_bones, or all pose bones if
    None) onto their '_R' counterparts.

    Returns (source_count, mirrored_bones, mirrored_constraints)."""
    pose_bones = armature_obj.pose.bones
    source_bones = [b for b in (selected_bones or pose_bones) if '_L' in b.name]

    mirrored_bones = 0
    mirrored_constraints = 0
    mirrored_targets = []

    for source in source_bones:
        target = pose_bones.get(mirror_bone_name(source.name))
        if target is None or target == source:
            continue

        for con in list(target.constraints):
            target.constraints.remove(con)
        for con in source.constraints:
            copy_bone_constraint(con, target)
            mirrored_constraints += 1

        mirrored_targets.append(target)
        mirrored_bones += 1

    reset_child_of_inverses(armature_obj, mirrored_targets, context)

    return len(source_bones), mirrored_bones, mirrored_constraints


class symmetrize_bone_constraints(bpy.types.Operator):
    bl_idname = "leo_tools.symmetrize_bone_constraints"
    bl_label = "Symmetrize Bone Constraints"
    bl_description = "Mirror constraints from '_L' bones onto their '_R' counterparts"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'POSE' and context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        armature_obj = context.active_object
        source_count, mirrored_bones, mirrored_constraints = symmetrize_constraints(
            armature_obj, context.selected_pose_bones, context)

        if source_count == 0:
            self.report(
                {'WARNING'}, "No '_L' bones found/selected to mirror from")
            return {'CANCELLED'}

        self.report(
            {'INFO'}, f"Mirrored {mirrored_constraints} constraint(s) on {mirrored_bones} bone(s)")
        return {'FINISHED'}


class symmetrize_rig(bpy.types.Operator):
    bl_idname = "leo_tools.symmetrize_rig"
    bl_label = "Symmetrize Rig"
    bl_description = "Symmetrize bone edit data, constraints and drivers from one side of the armature onto the other"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        name="Direction",
        description="Which side to copy from and to",
        items=[
            ('NEGATIVE_X', "-X to +X",
             "Copy bones on the negative X side onto their positive X counterparts"),
            ('POSITIVE_X', "+X to -X",
             "Copy bones on the positive X side onto their negative X counterparts"),
        ],
        default='POSITIVE_X',
    )

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        armature_obj = context.active_object
        original_mode = armature_obj.mode

        bpy.ops.object.mode_set(mode='EDIT')
        # Selecting every bone (both sides) makes Blender mirror both ways at
        # once; only select the '_L' source bones so '_R' is always the copy.
        bpy.ops.armature.select_all(action='DESELECT')
        for eb in armature_obj.data.edit_bones:
            is_source = '_L' in eb.name
            eb.select = eb.select_head = eb.select_tail = is_source
        bpy.ops.armature.symmetrize(direction=self.direction)
        bpy.ops.object.mode_set(mode='POSE')

        # Whole-rig pass, so mirror every '_L' bone rather than just the selection.
        _, mirrored_bones, mirrored_constraints = symmetrize_constraints(
            armature_obj, None, context)
        copy_rig_drivers()

        bpy.ops.object.mode_set(mode=original_mode)

        self.report(
            {'INFO'},
            f"Symmetrized bones, {mirrored_constraints} constraint(s) on {mirrored_bones} bone(s), and drivers")
        return {'FINISHED'}


def mirror_bone_name(name):
    return name.replace('_L', '_R') if name else name



def copy_bone_constraint(con, target_bone):
    """Duplicate a bone constraint onto target_bone, mirroring _L bone/object references to _R."""
    new_con = target_bone.constraints.new(con.type)
    new_con.name = mirror_bone_name(con.name)

    for prop in con.bl_rna.properties:
        identifier = prop.identifier
        if prop.is_readonly or identifier in ('rna_type', 'name', 'targets'):
            continue
        try:
            value = getattr(con, identifier)
        except AttributeError:
            continue
        try:
            setattr(new_con, identifier, value)
        except (AttributeError, TypeError):
            pass

    if hasattr(new_con, 'subtarget'):
        new_con.subtarget = mirror_bone_name(new_con.subtarget)
    if hasattr(new_con, 'pole_subtarget'):
        new_con.pole_subtarget = mirror_bone_name(new_con.pole_subtarget)
    if getattr(new_con, 'target', None) and '_L' in new_con.target.name:
        mirrored_target = bpy.data.objects.get(
            mirror_bone_name(new_con.target.name))
        if mirrored_target:
            new_con.target = mirrored_target

    # The Armature constraint stores its targets in a dedicated sub-collection
    if con.type == 'ARMATURE':
        for sub in con.targets:
            new_sub = new_con.targets.new()
            new_sub.target = sub.target
            new_sub.subtarget = mirror_bone_name(sub.subtarget)
            new_sub.weight = sub.weight

    return new_con


def copy_pose_drivers():
    armature = bpy.context.object
    if not armature.animation_data:
        return
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
            new_fcurve = armature_data.driver_add(
                fcurve.data_path.replace('_L', '_R'))
            copy_fcurve_properties(fcurve, new_fcurve)


def copy_fcurve_properties(fcurve, new_fcurve, mirror_targets=True):

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
            new_var_target.data_path = target.data_path
            new_var_target.bone_target = target.bone_target
            new_var_target.transform_type = target.transform_type
            new_var_target.transform_space = target.transform_space
            new_var_target.rotation_mode = target.rotation_mode
            if mirror_targets:
                new_var_target.data_path = new_var_target.data_path.replace('_L', '_R')
                new_var_target.bone_target = new_var_target.bone_target.replace('_L', '_R')

    new_fcurve.driver.type = fcurve.driver.type
    new_fcurve.driver.expression = fcurve.driver.expression


def copy_rig_drivers():
    copy_pose_drivers()
    copy_armature_data_drivers()


def register():
    corrective_shapekey.register()
    intermediate_shapekey.register()
    position_driven_shapekey.register()
    mirror_shapekeys.register()
    combo_shapekey.register()

    if not hasattr(bpy.types, 'LEO_TOOLS_OT_create_cage_deform_joints'):
        bpy.utils.register_class(create_cage_deform_joints)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_duplicate_mirror_object'):
        bpy.utils.register_class(duplicate_mirror_object)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_mirror_vertex_weights'):
        bpy.utils.register_class(mirror_vertex_weights)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_organize_bones'):
        bpy.utils.register_class(organize_bones)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_mirror_rig_drivers'):
        bpy.utils.register_class(mirror_rig_drivers)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_copy_bone_driver'):
        bpy.utils.register_class(copy_bone_driver)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_add_copy_transforms_constraint'):
        bpy.utils.register_class(add_copy_transforms_constraint)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_add_child_of_constraint'):
        bpy.utils.register_class(add_child_of_constraint)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_reset_child_of_inverse'):
        bpy.utils.register_class(reset_child_of_inverse)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_retarget_shrinkwrap_constraints'):
        bpy.utils.register_class(retarget_shrinkwrap_constraints)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_copy_bone_shape'):
        bpy.utils.register_class(copy_bone_shape)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_cleanup_duplicate_bone_shapes'):
        bpy.utils.register_class(cleanup_duplicate_bone_shapes)
    if not hasattr(bpy.types, 'LEO_TOOLS_PG_constraint_toggle'):
        bpy.utils.register_class(LEO_TOOLS_PG_constraint_toggle)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_copy_specific_constraints'):
        bpy.utils.register_class(copy_specific_constraints)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_symmetrize_bone_constraints'):
        bpy.utils.register_class(symmetrize_bone_constraints)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_blend_bone_chain'):
        bpy.utils.register_class(blend_bone_chain)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_symmetrize_rig'):
        bpy.utils.register_class(symmetrize_rig)
    if not hasattr(bpy.types, 'VIEW3D_PT_leo_rigging'):
        bpy.utils.register_class(RiggingPanel)


def unregister():
    if hasattr(bpy.types, 'VIEW3D_PT_leo_rigging'):
        bpy.utils.unregister_class(RiggingPanel)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_symmetrize_rig'):
        bpy.utils.unregister_class(symmetrize_rig)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_blend_bone_chain'):
        bpy.utils.unregister_class(blend_bone_chain)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_symmetrize_bone_constraints'):
        bpy.utils.unregister_class(symmetrize_bone_constraints)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_copy_bone_shape'):
        bpy.utils.unregister_class(copy_bone_shape)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_cleanup_duplicate_bone_shapes'):
        bpy.utils.unregister_class(cleanup_duplicate_bone_shapes)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_copy_specific_constraints'):
        bpy.utils.unregister_class(copy_specific_constraints)
    if hasattr(bpy.types, 'LEO_TOOLS_PG_constraint_toggle'):
        bpy.utils.unregister_class(LEO_TOOLS_PG_constraint_toggle)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_reset_child_of_inverse'):
        bpy.utils.unregister_class(reset_child_of_inverse)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_retarget_shrinkwrap_constraints'):
        bpy.utils.unregister_class(retarget_shrinkwrap_constraints)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_add_child_of_constraint'):
        bpy.utils.unregister_class(add_child_of_constraint)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_add_copy_transforms_constraint'):
        bpy.utils.unregister_class(add_copy_transforms_constraint)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_copy_bone_driver'):
        bpy.utils.unregister_class(copy_bone_driver)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_mirror_rig_drivers'):
        bpy.utils.unregister_class(mirror_rig_drivers)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_create_cage_deform_joints'):
        bpy.utils.unregister_class(create_cage_deform_joints)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_duplicate_mirror_object'):
        bpy.utils.unregister_class(duplicate_mirror_object)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_mirror_vertex_weights'):
        bpy.utils.unregister_class(mirror_vertex_weights)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_organize_bones'):
        bpy.utils.unregister_class(organize_bones)

    combo_shapekey.unregister()
    mirror_shapekeys.unregister()
    position_driven_shapekey.unregister()
    intermediate_shapekey.unregister()
    corrective_shapekey.unregister()


if __name__ == "__main__":
    register()
