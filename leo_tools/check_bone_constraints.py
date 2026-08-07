"""
Check Bone Constraints - Scan armatures for bone constraints with an
empty/unset target (Object) or subtarget (bone name) field.
"""

import bpy


def find_empty_constraint_fields(armature_obj):
    """Return a list of (bone_name, constraint_name, constraint_type, issue) tuples
    for every bone constraint missing a required target or subtarget."""
    issues = []

    for bone in armature_obj.pose.bones:
        for con in bone.constraints:
            # Armature constraint holds its targets in a sub-collection
            if con.type == 'ARMATURE':
                if len(con.targets) == 0:
                    issues.append((bone.name, con.name, con.type, "no targets in list"))
                for i, sub in enumerate(con.targets):
                    if sub.target is None:
                        issues.append((bone.name, con.name, con.type, f"target {i}: empty object"))
                    elif sub.target.type == 'ARMATURE' and not sub.subtarget:
                        issues.append((bone.name, con.name, con.type, f"target {i}: empty bone (subtarget)"))
                continue

            if hasattr(con, 'target'):
                if con.target is None:
                    issues.append((bone.name, con.name, con.type, "empty target object"))
                elif con.target.type == 'ARMATURE' and hasattr(con, 'subtarget') and not con.subtarget:
                    issues.append((bone.name, con.name, con.type, "empty bone (subtarget)"))

    return issues


class POSE_OT_check_empty_bone_constraints(bpy.types.Operator):
    """Check selected (or all) armatures for bone constraints with an empty target/subtarget"""
    bl_idname = "pose.check_empty_bone_constraints"
    bl_label = "Check Empty Bone Constraints"
    bl_options = {'REGISTER'}

    def execute(self, context):
        armatures = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if not armatures:
            armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']

        if not armatures:
            self.report({'WARNING'}, "No armature found in the scene")
            return {'CANCELLED'}

        total_issues = 0
        print("\n" + "=" * 60)
        print("CHECK BONE CONSTRAINTS - empty target/subtarget fields")
        print("=" * 60)

        for armature_obj in armatures:
            issues = find_empty_constraint_fields(armature_obj)
            if not issues:
                continue
            print(f"\nArmature: {armature_obj.name}")
            for bone_name, con_name, con_type, issue in issues:
                print(f"  Bone '{bone_name}' - constraint '{con_name}' ({con_type}): {issue}")
            total_issues += len(issues)

        print("\n" + "=" * 60)

        if total_issues == 0:
            self.report({'INFO'}, "No empty constraint fields found")
        else:
            self.report({'WARNING'}, f"{total_issues} empty constraint field(s) found, see console")

        return {'FINISHED'}


def register():
    bpy.utils.register_class(POSE_OT_check_empty_bone_constraints)


def unregister():
    bpy.utils.unregister_class(POSE_OT_check_empty_bone_constraints)


if __name__ == "__main__":
    register()
