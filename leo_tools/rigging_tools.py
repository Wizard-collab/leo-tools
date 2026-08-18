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
        layout.separator()
        layout.label(text="Bone Constraints")
        layout.operator("leo_tools.add_copy_transforms_constraint",
                        text="Add copy transforms constraint")
        layout.operator("leo_tools.add_child_of_constraint",
                        text="Add child of constraint")
        layout.operator("leo_tools.copy_bone_shape",
                        text="Copy controller shape")
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


class mirror_rig_drivers(bpy.types.Operator):
    bl_idname = "leo_tools.mirror_rig_drivers"
    bl_label = "Mirror the rig drivers"
    bl_description = "Mirror the rig drivers"

    def execute(self, context):
        copy_rig_drivers()
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
                if hasattr(value, 'copy'):
                    value = value.copy()
                setattr(bone, prop, value)

        self.report(
            {'INFO'}, f"Copied controller shape from '{source.name}' to {len(targets)} bone(s)")
        return {'FINISHED'}


def symmetrize_constraints(armature_obj, selected_bones):
    """Mirror constraints from '_L' bones (selected_bones, or all pose bones if
    None) onto their '_R' counterparts.

    Returns (source_count, mirrored_bones, mirrored_constraints)."""
    pose_bones = armature_obj.pose.bones
    source_bones = [b for b in (selected_bones or pose_bones) if '_L' in b.name]

    mirrored_bones = 0
    mirrored_constraints = 0

    for source in source_bones:
        target = pose_bones.get(mirror_bone_name(source.name))
        if target is None or target == source:
            continue

        for con in list(target.constraints):
            target.constraints.remove(con)
        for con in source.constraints:
            copy_bone_constraint(con, target)
            mirrored_constraints += 1

        reset_bone_constraint_inverses(armature_obj, target)
        mirrored_bones += 1

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
            armature_obj, context.selected_pose_bones)

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
            armature_obj, None)
        copy_rig_drivers()

        bpy.ops.object.mode_set(mode=original_mode)

        self.report(
            {'INFO'},
            f"Symmetrized bones, {mirrored_constraints} constraint(s) on {mirrored_bones} bone(s), and drivers")
        return {'FINISHED'}


def mirror_bone_name(name):
    return name.replace('_L', '_R') if name else name


def reset_bone_constraint_inverses(armature_obj, bone):
    """Recompute the Set Inverse matrix of any Child Of constraint on bone.

    Computed directly (no bpy.ops), since the operator relies on bones.active/
    context state that isn't reliable when looping over many bones at once."""
    for con in bone.constraints:
        if con.type != 'CHILD_OF' or not con.target:
            continue
        target_bone = (armature_obj.pose.bones.get(con.subtarget)
                        if con.target == armature_obj else None)
        if target_bone is not None:
            con.inverse_matrix = target_bone.matrix.inverted()
        else:
            con.inverse_matrix = con.target.matrix_world.inverted()


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
    corrective_shapekey.register()
    intermediate_shapekey.register()
    position_driven_shapekey.register()
    mirror_shapekeys.register()
    combo_shapekey.register()

    if not hasattr(bpy.types, 'LEO_TOOLS_OT_create_cage_deform_joints'):
        bpy.utils.register_class(create_cage_deform_joints)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_mirror_rig_drivers'):
        bpy.utils.register_class(mirror_rig_drivers)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_add_copy_transforms_constraint'):
        bpy.utils.register_class(add_copy_transforms_constraint)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_add_child_of_constraint'):
        bpy.utils.register_class(add_child_of_constraint)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_copy_bone_shape'):
        bpy.utils.register_class(copy_bone_shape)
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
    if hasattr(bpy.types, 'LEO_TOOLS_OT_add_child_of_constraint'):
        bpy.utils.unregister_class(add_child_of_constraint)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_add_copy_transforms_constraint'):
        bpy.utils.unregister_class(add_copy_transforms_constraint)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_mirror_rig_drivers'):
        bpy.utils.unregister_class(mirror_rig_drivers)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_create_cage_deform_joints'):
        bpy.utils.unregister_class(create_cage_deform_joints)

    combo_shapekey.unregister()
    mirror_shapekeys.unregister()
    position_driven_shapekey.unregister()
    intermediate_shapekey.unregister()
    corrective_shapekey.unregister()


if __name__ == "__main__":
    register()
