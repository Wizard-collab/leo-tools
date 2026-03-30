import bpy
import mathutils
import importlib
from leo_tools import texturing_tools
from leo_tools import corrective_shapekey
from leo_tools import intermediate_shapekey
from leo_tools import position_driven_shapekey
from leo_tools import mirror_shapekeys
from leo_tools import combo_shapekey
from leo_tools import animation_transfer
from leo_tools import empty_from_vertices
from leo_tools import collection_display


class CustomToolboxPanel(bpy.types.Panel):
    bl_label = "Leo tools"  # The name of the panel
    bl_idname = "VIEW3D_PT_leo_tools"  # Unique ID for the panel
    bl_space_type = 'VIEW_3D'  # Panel location
    # Region (e.g., 'UI' for the N-panel, 'TOOLS' for the T-panel)
    bl_region_type = 'UI'
    bl_category = "Leo tools"  # Tab name in the N-panel

    def draw(self, context):
        layout = self.layout
        obj = context.object
        # Add some buttons/operators to the panel
        layout.label(text="Texturing")
        layout.operator("leo_tools.create_udim_mask",
                        text="Create mask with UDIMS")
        layout.label(text="Rigging Tools")
        layout.operator("leo_tools.mirror_rig_drivers",
                        text="Mirror rig drivers")
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
        layout.operator("mesh.create_empty_from_vertices",
                        text="Empty from 3 Vertices")
        layout.separator()
        layout.label(text="Display Tools")
        layout.operator("object.collection_bounding_box",
                        text="Collection to Bounding Box")
        layout.operator("object.collection_textured",
                        text="Collection to Textured")
        layout.separator()
        layout.label(text="Animation Tools")
        layout.operator("anim.flip_animation",
                        text="Flip Animation")
        layout.label(text="Shading Tools")
        layout.operator("leo_tools.remove_materials", text="Remove materials")
        layout.operator("leo_tools.create_checker",
                        text="Create new checker material")
        layout.label(text="Rendering Tools")
        layout.operator("leo_tools.init_settings", text="Init Cycles")
        layout.operator("leo_tools.fixed_threads",
                        text="Set fixed threads to 16")
        layout.operator("leo_tools.threads_all", text="Use all threads")
        layout.label(text="Utils")
        layout.operator("leo_tools.add_subdiv",
                        text="Add subdivision to selection")
        layout.operator("leo_tools.clean_shapes_names",
                        text="Clean shapes names")
        layout.operator("leo_tools.add_msh_suffix",
                        text="Add _MSH to meshes")
        layout.operator("leo_tools.remove_all_modifiers",
                        text="Remove all modifiers")
        layout.operator("leo_tools.apply_mirror_modifiers",
                text="Apply mirror modifiers")
        layout.operator("leo_tools.remove_all_vertex_groups",
                        text="Remove all vertex groups")
        layout.operator("leo_tools.create_cage_deform_joints",
                        text="Create cage deform joints")
        layout.separator()
        layout.label(text="Grease Pencil")
        layout.operator("leo_tools.merge_gp_objects",
                        text="Duplicate & Bake GP")


class AnimToolsPanel(bpy.types.Panel):
    bl_label = "Anim tools"
    bl_idname = "VIEW3D_PT_anim_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Anim tools"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        
        # Keyframe Interpolation Mode
        layout.label(text="Default Interpolation")
        prefs = context.preferences.edit
        current_mode = prefs.keyframe_new_interpolation_type
        
        if current_mode == 'CONSTANT':
            mode_text = "Current: Stepped"
            button_text = "Switch to Curve"
        else:
            mode_text = "Current: Curve"
            button_text = "Switch to Stepped"
        
        layout.label(text=mode_text)
        layout.operator("anim.toggle_interpolation_mode", text=button_text)
        
        layout.separator()
        
        # Mode switching
        layout.label(text="Mode Switch")
        if obj and obj.type == 'ARMATURE':
            if obj.mode == 'POSE':
                layout.operator("anim.toggle_pose_object_mode", text="Switch to Object Mode")
            elif obj.mode == 'OBJECT':
                layout.operator("anim.toggle_pose_object_mode", text="Switch to Pose Mode")
            else:
                layout.label(text="Switch to Object or Pose Mode")
        else:
            layout.label(text="Select an armature")
        
        layout.separator()
        
        # Convert rig interpolation
        layout.label(text="Convert Rig Keys")
        if obj and obj.type == 'ARMATURE' and obj.animation_data and obj.animation_data.action:
            layout.operator("anim.convert_rig_interpolation", text="Stepped ↔ Curve")
        else:
            layout.label(text="No animated rig selected")
        
        layout.separator()
        
        layout.label(text="Tween Machine")
        if obj:
            layout.label(text=f"Selected Object: {obj.name}")
            layout.prop(context.scene, "tween_machine_percentage",
                        text="Percentage", slider=True)
            if context.scene.tween_stored_pose:
                layout.operator("anim.reset_tween_stored_pose", text="Clear Stored Pose")
        else:
            layout.label(text="No object selected")
            layout.prop(context.scene, "tween_machine_percentage",
                        text="Percentage", slider=True)


class reset_tween_stored_pose(bpy.types.Operator):
    bl_idname = "anim.reset_tween_stored_pose"
    bl_label = "Clear Stored Pose"
    bl_description = "Clear the stored pose from memory"

    def execute(self, context):
        context.scene.tween_stored_pose = ""
        self.report({'INFO'}, "Stored pose cleared")
        return {'FINISHED'}


class toggle_pose_object_mode(bpy.types.Operator):
    bl_idname = "anim.toggle_pose_object_mode"
    bl_label = "Toggle Pose/Object Mode"
    bl_description = "Switch between Pose and Object mode for the selected armature"

    def execute(self, context):
        obj = context.active_object
        
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select an armature")
            return {'CANCELLED'}
        
        if obj.mode == 'POSE':
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'INFO'}, "Switched to Object Mode")
        elif obj.mode == 'OBJECT':
            bpy.ops.object.mode_set(mode='POSE')
            self.report({'INFO'}, "Switched to Pose Mode")
        else:
            # If in another mode (like Edit mode), go to Object mode first
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'INFO'}, "Switched to Object Mode")
        
        return {'FINISHED'}


class toggle_interpolation_mode(bpy.types.Operator):
    bl_idname = "anim.toggle_interpolation_mode"
    bl_label = "Toggle Interpolation Mode"
    bl_description = "Toggle between stepped and curve default interpolation for new keyframes"

    def execute(self, context):
        prefs = context.preferences.edit
        current_mode = prefs.keyframe_new_interpolation_type
        
        if current_mode == 'CONSTANT':
            prefs.keyframe_new_interpolation_type = 'BEZIER'
            self.report({'INFO'}, "Default interpolation set to Curve (Bezier)")
        else:
            prefs.keyframe_new_interpolation_type = 'CONSTANT'
            self.report({'INFO'}, "Default interpolation set to Stepped (Constant)")
        
        # Force UI refresh
        for area in context.screen.areas:
            area.tag_redraw()
        
        return {'FINISHED'}


class convert_rig_interpolation(bpy.types.Operator):
    bl_idname = "anim.convert_rig_interpolation"
    bl_label = "Convert Rig Interpolation"
    bl_description = "Convert all keyframes on the current rig between stepped and curve interpolation"

    def execute(self, context):
        obj = context.active_object
        
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select an armature")
            return {'CANCELLED'}
        
        if not obj.animation_data or not obj.animation_data.action:
            self.report({'ERROR'}, "Armature has no animation data")
            return {'CANCELLED'}
        
        action = obj.animation_data.action
        
        # Count interpolation types to determine what to convert to
        constant_count = 0
        bezier_count = 0
        total_keys = 0
        
        for fcurve in action.fcurves:
            for keyframe in fcurve.keyframe_points:
                total_keys += 1
                if keyframe.interpolation == 'CONSTANT':
                    constant_count += 1
                elif keyframe.interpolation == 'BEZIER':
                    bezier_count += 1
        
        if total_keys == 0:
            self.report({'WARNING'}, "No keyframes found")
            return {'CANCELLED'}
        
        # Determine target interpolation (convert to whichever is less common)
        if constant_count >= bezier_count:
            target_interpolation = 'BEZIER'
            target_name = "Curve (Bezier)"
        else:
            target_interpolation = 'CONSTANT'
            target_name = "Stepped (Constant)"
        
        # Convert all keyframes
        converted = 0
        for fcurve in action.fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.interpolation != target_interpolation:
                    keyframe.interpolation = target_interpolation
                    converted += 1
        
        self.report({'INFO'}, f"Converted {converted} keyframes to {target_name}")
        
        # Force viewport update
        for area in context.screen.areas:
            area.tag_redraw()
        
        return {'FINISHED'}


class create_udim_mask(bpy.types.Operator):
    bl_idname = "leo_tools.create_udim_mask"
    bl_label = "Create mask with UDIMS"
    bl_description = "Create mask with UDIMS"

    def execute(self, context):
        bpy.ops.object.create_udim_map('INVOKE_DEFAULT')
        return {'FINISHED'}


class add_subdiv(bpy.types.Operator):
    bl_idname = "leo_tools.add_subdiv"
    bl_label = "Add subdiv on selection"
    bl_description = "Add subdiv on selection"

    def execute(self, context):
        add_subdivision_surface_modifier()
        return {'FINISHED'}


class clean_shapes_names(bpy.types.Operator):
    bl_idname = "leo_tools.clean_shapes_names"
    bl_label = "Clean shapes names"
    bl_description = "Rename object data (shapes) with pattern objectname_shape"

    def execute(self, context):
        clean_object_shapes_names()
        return {'FINISHED'}


class add_msh_suffix(bpy.types.Operator):
    bl_idname = "leo_tools.add_msh_suffix"
    bl_label = "Add _MSH suffix to selected meshes"
    bl_description = "Add _MSH suffix to all selected mesh objects"

    def execute(self, context):
        renamed_count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                if not obj.name.endswith('_MSH'):
                    obj.name = obj.name + '_MSH'
                    renamed_count += 1
        self.report({'INFO'}, f"Renamed {renamed_count} mesh(es)")
        return {'FINISHED'}


class remove_all_modifiers(bpy.types.Operator):
    bl_idname = "leo_tools.remove_all_modifiers"
    bl_label = "Remove all modifiers from selected objects"
    bl_description = "Remove all modifiers from all selected objects"

    def execute(self, context):
        removed_count = 0
        for obj in context.selected_objects:
            for mod in obj.modifiers[:]:
                obj.modifiers.remove(mod)
                removed_count += 1
        self.report({'INFO'}, f"Removed {removed_count} modifier(s)")
        return {'FINISHED'}


class apply_mirror_modifiers(bpy.types.Operator):
    bl_idname = "leo_tools.apply_mirror_modifiers"
    bl_label = "Apply mirror modifiers on selected objects"
    bl_description = "Apply all Mirror modifiers on selected objects"

    def execute(self, context):
        selected_objects = list(context.selected_objects)
        if not selected_objects:
            self.report({'ERROR'}, "No object selected")
            return {'CANCELLED'}

        original_active = context.view_layer.objects.active
        original_mode = context.mode

        if context.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                self.report({'ERROR'}, "Switch to Object mode to apply modifiers")
                return {'CANCELLED'}

        applied_count = 0
        touched_objects = 0
        failed_count = 0

        for obj in selected_objects:
            if not hasattr(obj, "modifiers"):
                continue

            mirror_modifiers = [mod.name for mod in obj.modifiers if mod.type == 'MIRROR']
            if not mirror_modifiers:
                continue

            touched_objects += 1
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj

            for modifier_name in mirror_modifiers:
                try:
                    bpy.ops.object.modifier_apply(modifier=modifier_name)
                    applied_count += 1
                except RuntimeError:
                    failed_count += 1

        bpy.ops.object.select_all(action='DESELECT')
        for obj in selected_objects:
            if obj.name in bpy.data.objects:
                obj.select_set(True)

        if original_active and original_active.name in bpy.data.objects:
            context.view_layer.objects.active = original_active

        if original_mode != 'OBJECT' and context.view_layer.objects.active:
            try:
                bpy.ops.object.mode_set(mode=original_mode)
            except RuntimeError:
                pass

        if applied_count == 0 and touched_objects == 0:
            self.report({'WARNING'}, "No Mirror modifier found on selected objects")
            return {'CANCELLED'}

        if failed_count > 0:
            self.report({'WARNING'}, f"Applied {applied_count} Mirror modifier(s), {failed_count} failed")
            return {'FINISHED'}

        self.report({'INFO'}, f"Applied {applied_count} Mirror modifier(s) on {touched_objects} object(s)")
        return {'FINISHED'}


class remove_all_vertex_groups(bpy.types.Operator):
    bl_idname = "leo_tools.remove_all_vertex_groups"
    bl_label = "Remove all vertex groups from selected objects"
    bl_description = "Remove all vertex groups from all selected objects"

    def execute(self, context):
        removed_count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                count = len(obj.vertex_groups)
                obj.vertex_groups.clear()
                removed_count += count
        self.report({'INFO'}, f"Removed {removed_count} vertex group(s)")
        return {'FINISHED'}


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
        armature_obj = bpy.data.objects.new(f"{mesh_name}_CAGE_DEFORM", armature_data)
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
        
        self.report({'INFO'}, f"Created {len(mesh.vertices)} joints for cage deform")
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


class bake_gp_objects(bpy.types.Operator):
    """Duplicate selected Grease Pencil objects and bake constraints/parenting/modifiers to keyframes"""
    bl_idname = "leo_tools.merge_gp_objects"
    bl_label = "Duplicate & Bake GP Objects"
    bl_description = "Duplicate GP objects and bake constraints/parenting/modifiers (Shrinkwrap, etc.) to keyframes"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Support both legacy GP (Blender 3.x) and new GP v3 (Blender 4.0+)
    GP_TYPES = ('GPENCIL', 'GREASEPENCIL')
    
    # Property for user to input the suffix for baked objects
    bake_suffix: bpy.props.StringProperty(
        name="Suffix",
        description="Suffix to add to duplicated object names",
        default="_baked"
    )
    
    bake_modifiers: bpy.props.BoolProperty(
        name="Bake Modifiers",
        description="Bake GP modifiers (Shrinkwrap, etc.) into stroke data",
        default=True
    )

    @classmethod
    def poll(cls, context):
        # Check if we have at least one GP object selected
        selected_gp = [obj for obj in context.selected_objects 
                       if obj.type in cls.GP_TYPES]
        return len(selected_gp) >= 1
    
    def invoke(self, context, event):
        # Show dialog
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "bake_suffix")
        layout.prop(self, "bake_modifiers")

    def bake_gp_transforms(self, context, gp_obj, frame_start, frame_end):
        """Bake all constraints and parenting transforms to keyframes for a GP object"""
        scene = context.scene
        
        # Check if object has constraints or parent
        has_constraints = len(gp_obj.constraints) > 0
        has_parent = gp_obj.parent is not None
        
        if not has_constraints and not has_parent:
            return False  # Nothing to bake
        
        # Store world matrices for each frame
        world_matrices = {}
        for frame in range(frame_start, frame_end + 1):
            scene.frame_set(frame)
            world_matrices[frame] = gp_obj.matrix_world.copy()
        
        # Remove constraints
        for constraint in gp_obj.constraints[:]:
            gp_obj.constraints.remove(constraint)
        
        # Clear parent while keeping transform
        if gp_obj.parent:
            # Store current world matrix
            mat_world = gp_obj.matrix_world.copy()
            gp_obj.parent = None
            gp_obj.matrix_world = mat_world
        
        # Bake keyframes
        for frame, mat in world_matrices.items():
            scene.frame_set(frame)
            gp_obj.matrix_world = mat
            gp_obj.keyframe_insert(data_path="location", frame=frame)
            gp_obj.keyframe_insert(data_path="rotation_euler", frame=frame)
            gp_obj.keyframe_insert(data_path="scale", frame=frame)
        
        return True
    
    def get_gp_modifiers(self, gp_obj):
        """Get GP modifiers - different attribute name for legacy GP vs GP v3"""
        # Legacy GP (Blender 3.x) uses grease_pencil_modifiers
        if hasattr(gp_obj, 'grease_pencil_modifiers') and gp_obj.grease_pencil_modifiers:
            return gp_obj.grease_pencil_modifiers
        # GP v3 (Blender 4.0+) uses regular modifiers
        if hasattr(gp_obj, 'modifiers') and gp_obj.modifiers:
            return gp_obj.modifiers
        return None
    
    def bake_gp_modifiers(self, context, gp_obj, frame_start, frame_end):
        """Bake GP modifiers (like Shrinkwrap) into the stroke point data"""
        # Get the appropriate modifier collection
        gp_modifiers = self.get_gp_modifiers(gp_obj)
        
        if not gp_modifiers or len(gp_modifiers) == 0:
            return False
        
        scene = context.scene
        depsgraph = context.evaluated_depsgraph_get()
        gp_data = gp_obj.data
        
        # Determine if this is legacy GP or GP v3
        is_legacy_gp = gp_obj.type == 'GPENCIL'
        
        # For each frame, get the evaluated (modifier-applied) stroke positions
        for frame in range(frame_start, frame_end + 1):
            scene.frame_set(frame)
            depsgraph.update()
            
            # Get evaluated object with modifiers applied
            eval_obj = gp_obj.evaluated_get(depsgraph)
            eval_data = eval_obj.data
            
            if is_legacy_gp:
                # Legacy GP (Blender 3.x): layers -> frames -> strokes -> points
                for layer_idx, layer in enumerate(gp_data.layers):
                    if layer_idx >= len(eval_data.layers):
                        continue
                    eval_layer = eval_data.layers[layer_idx]
                    
                    # Find the frame for this frame number
                    src_frame = None
                    eval_frame = None
                    for f in layer.frames:
                        if f.frame_number == frame:
                            src_frame = f
                            break
                    for f in eval_layer.frames:
                        if f.frame_number == frame:
                            eval_frame = f
                            break
                    
                    if src_frame is None or eval_frame is None:
                        continue
                    
                    # Copy deformed point positions from evaluated to original
                    for stroke_idx, stroke in enumerate(src_frame.strokes):
                        if stroke_idx >= len(eval_frame.strokes):
                            continue
                        eval_stroke = eval_frame.strokes[stroke_idx]
                        
                        for point_idx, point in enumerate(stroke.points):
                            if point_idx >= len(eval_stroke.points):
                                continue
                            # Copy the deformed position
                            point.co = eval_stroke.points[point_idx].co.copy()
            else:
                # GP v3 (Blender 4.0+): structure is different
                # layers -> frames -> drawing
                for layer_idx, layer in enumerate(gp_data.layers):
                    if layer_idx >= len(eval_data.layers):
                        continue
                    eval_layer = eval_data.layers[layer_idx]
                    
                    # Find matching frames
                    for frame_idx, gp_frame in enumerate(layer.frames):
                        if gp_frame.frame_number != frame:
                            continue
                        
                        # Find corresponding eval frame
                        eval_gp_frame = None
                        for ef in eval_layer.frames:
                            if ef.frame_number == frame:
                                eval_gp_frame = ef
                                break
                        
                        if eval_gp_frame is None:
                            continue
                        
                        # Access drawing data (GP v3 structure)
                        if hasattr(gp_frame, 'drawing') and hasattr(eval_gp_frame, 'drawing'):
                            src_drawing = gp_frame.drawing
                            eval_drawing = eval_gp_frame.drawing
                            
                            if hasattr(src_drawing, 'strokes') and hasattr(eval_drawing, 'strokes'):
                                for stroke_idx, stroke in enumerate(src_drawing.strokes):
                                    if stroke_idx >= len(eval_drawing.strokes):
                                        continue
                                    eval_stroke = eval_drawing.strokes[stroke_idx]
                                    
                                    # Copy points - GP v3 uses 'points' attribute
                                    if hasattr(stroke, 'points') and hasattr(eval_stroke, 'points'):
                                        for point_idx in range(min(len(stroke.points), len(eval_stroke.points))):
                                            stroke.points[point_idx].position = eval_stroke.points[point_idx].position.copy()
        
        # Remove all GP modifiers after baking
        modifier_names = [mod.name for mod in gp_modifiers]
        for mod_name in modifier_names:
            mod = gp_modifiers.get(mod_name)
            if mod:
                gp_modifiers.remove(mod)
        
        return True
    
    def get_layer_name_attr(self, layer):
        """Get layer name attribute - 'info' for legacy GP, 'name' for GP v3"""
        if hasattr(layer, 'info'):
            return layer.info
        return layer.name
    
    def set_layer_name(self, layer, name):
        """Set layer name - 'info' for legacy GP, 'name' for GP v3"""
        if hasattr(layer, 'info'):
            layer.info = name
        else:
            layer.name = name

    def execute(self, context):
        # Get all selected GP objects
        selected_gp = [obj for obj in context.selected_objects 
                       if obj.type in self.GP_TYPES]
        
        if len(selected_gp) == 0:
            self.report({'ERROR'}, "No Grease Pencil objects selected")
            return {'CANCELLED'}
        
        # Store original names before duplicating
        original_names = {obj.name: obj.name for obj in selected_gp}
        
        # Get frame range for baking
        frame_start = context.scene.frame_start
        frame_end = context.scene.frame_end
        current_frame = context.scene.frame_current
        
        # Step 1: Duplicate selected GP objects (keeping originals)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in selected_gp:
            obj.select_set(True)
        context.view_layer.objects.active = selected_gp[0]
        
        bpy.ops.object.duplicate()
        
        # Get the duplicated objects
        duplicated_gp = [obj for obj in context.selected_objects 
                         if obj.type in self.GP_TYPES]
        
        # Map duplicates to their original names
        dup_to_original_name = {}
        for dup_obj in duplicated_gp:
            # Blender adds .001 etc to duplicates, find the base name
            base_name = dup_obj.name.rsplit('.', 1)[0]
            if base_name in original_names:
                dup_to_original_name[dup_obj] = base_name
            else:
                # Fallback: use the duplicate's name without suffix
                dup_to_original_name[dup_obj] = base_name
        
        # Step 2: Rename duplicated objects and their layers
        for dup_obj in duplicated_gp:
            original_name = dup_to_original_name.get(dup_obj, dup_obj.name.rsplit('.', 1)[0])
            
            # Rename object
            new_name = f"{original_name}{self.bake_suffix}"
            dup_obj.name = new_name
            if dup_obj.data:
                dup_obj.data.name = new_name
            
            # Rename layers to include original object name
            gp_data = dup_obj.data
            for layer in gp_data.layers:
                current_name = self.get_layer_name_attr(layer)
                if not current_name.startswith(original_name):
                    self.set_layer_name(layer, f"{original_name}_{current_name}")
        
        # Step 3: Bake GP modifiers (Shrinkwrap, etc.) if enabled
        modifiers_baked = 0
        if self.bake_modifiers:
            for gp_obj in duplicated_gp:
                if self.bake_gp_modifiers(context, gp_obj, frame_start, frame_end):
                    modifiers_baked += 1
        
        # Step 4: Bake constraints/parenting for all duplicated GP objects
        transforms_baked = 0
        for gp_obj in duplicated_gp:
            if self.bake_gp_transforms(context, gp_obj, frame_start, frame_end):
                transforms_baked += 1
        
        # Restore frame
        context.scene.frame_set(current_frame)
        
        # Ensure all duplicated objects are selected
        bpy.ops.object.select_all(action='DESELECT')
        for obj in duplicated_gp:
            obj.select_set(True)
        if duplicated_gp:
            context.view_layer.objects.active = duplicated_gp[0]
        
        self.report({'INFO'}, 
                    f"Duplicated {len(duplicated_gp)} GP objects "
                    f"({transforms_baked} transforms, {modifiers_baked} modifiers baked)")
        
        return {'FINISHED'}


def update_tween(self, context):
    current_frame = context.scene.frame_current
    # Get the percentage from the scene property
    factor = context.scene.tween_machine_percentage / 100.0
    
    # Get or create stored pose data
    import json
    stored_data = {}
    if context.scene.tween_stored_pose:
        try:
            stored_data = json.loads(context.scene.tween_stored_pose)
        except:
            stored_data = {}

    # Handle armature in pose mode - work with selected bones
    if (context.object and context.object.type == 'ARMATURE' and
            context.object.mode == 'POSE'):

        armature = context.object
        if not armature.animation_data or not armature.animation_data.action:
            return

        action = armature.animation_data.action
        selected_bones = [
            bone for bone in armature.pose.bones if bone.bone.select]
        
        # Store initial pose if not already stored
        if not stored_data:
            stored_data = {"armature": armature.name, "bones": {}}
            for bone in selected_bones:
                bone_name = bone.name
                stored_data["bones"][bone_name] = {
                    "location": list(bone.location),
                    "rotation_euler": list(bone.rotation_euler),
                    "rotation_quaternion": list(bone.rotation_quaternion),
                    "scale": list(bone.scale)
                }
            context.scene.tween_stored_pose = json.dumps(stored_data)

        for bone in selected_bones:
            bone_name = bone.name
            # Process location, rotation, and scale channels for each bone
            for data_path_base in ["location", "rotation_euler", "rotation_quaternion", "scale"]:
                data_path = f'pose.bones["{bone_name}"].{data_path_base}'

                # Find fcurves for this bone's property
                bone_fcurves = [
                    fc for fc in action.fcurves if fc.data_path == data_path]
                if not bone_fcurves:
                    continue

                previous_frame, next_frame = find_keyframe_range(
                    bone_fcurves, current_frame)
                
                # If no keys found, skip
                if previous_frame is None and next_frame is None:
                    continue

                # Interpolate values for each component (x, y, z or w for quaternion)
                interpolated_values = []
                for i, fcurve in enumerate(bone_fcurves):
                    if previous_frame is not None and next_frame is not None:
                        # Both keys exist - normal interpolation
                        prev_value = fcurve.evaluate(previous_frame)
                        next_value = fcurve.evaluate(next_frame)
                        interpolated_value = (1 - factor) * prev_value + factor * next_value
                    elif previous_frame is not None:
                        # Only previous key exists - interpolate from previous to stored current
                        prev_value = fcurve.evaluate(previous_frame)
                        # Use stored value instead of evaluated current
                        if bone_name in stored_data.get("bones", {}):
                            stored_bone = stored_data["bones"][bone_name]
                            if data_path_base in stored_bone:
                                current_value = stored_bone[data_path_base][i]
                            else:
                                current_value = fcurve.evaluate(current_frame)
                        else:
                            current_value = fcurve.evaluate(current_frame)
                        interpolated_value = (1 - factor) * prev_value + factor * current_value
                    else:
                        # Only next key exists - interpolate from stored current to next
                        next_value = fcurve.evaluate(next_frame)
                        # Use stored value instead of evaluated current
                        if bone_name in stored_data.get("bones", {}):
                            stored_bone = stored_data["bones"][bone_name]
                            if data_path_base in stored_bone:
                                current_value = stored_bone[data_path_base][i]
                            else:
                                current_value = fcurve.evaluate(current_frame)
                        else:
                            current_value = fcurve.evaluate(current_frame)
                        interpolated_value = (1 - factor) * current_value + factor * next_value
                    interpolated_values.append(interpolated_value)

                # Apply interpolated values to bone
                if data_path_base == "location" and len(interpolated_values) >= 3:
                    bone.location = interpolated_values[:3]
                elif data_path_base == "rotation_euler" and len(interpolated_values) >= 3:
                    bone.rotation_euler = interpolated_values[:3]
                elif data_path_base == "rotation_quaternion" and len(interpolated_values) >= 4:
                    bone.rotation_quaternion = interpolated_values[:4]
                elif data_path_base == "scale" and len(interpolated_values) >= 3:
                    bone.scale = interpolated_values[:3]

                # Auto keyframe if enabled
                if context.scene.tool_settings.use_keyframe_insert_auto:
                    bone.keyframe_insert(
                        data_path=data_path_base, frame=current_frame)

    # Handle regular objects - work with all selected objects
    else:
        selected_objects = context.selected_objects
        if not selected_objects:
            selected_objects = [context.object] if context.object else []

        for obj in selected_objects:
            if not obj or not obj.animation_data or not obj.animation_data.action:
                continue

            action = obj.animation_data.action

            # Process location, rotation, and scale for each object
            for data_path in ["location", "rotation_euler", "rotation_quaternion", "scale"]:
                obj_fcurves = [
                    fc for fc in action.fcurves if fc.data_path == data_path]
                if not obj_fcurves:
                    continue

                previous_frame, next_frame = find_keyframe_range(
                    obj_fcurves, current_frame)
                
                # If no keys found, skip
                if previous_frame is None and next_frame is None:
                    continue

                # Interpolate values for each component
                interpolated_values = []
                for fcurve in obj_fcurves:
                    if previous_frame is not None and next_frame is not None:
                        # Both keys exist - normal interpolation
                        prev_value = fcurve.evaluate(previous_frame)
                        next_value = fcurve.evaluate(next_frame)
                        interpolated_value = (1 - factor) * prev_value + factor * next_value
                    elif previous_frame is not None:
                        # Only previous key exists - interpolate from previous to current
                        prev_value = fcurve.evaluate(previous_frame)
                        current_value = fcurve.evaluate(current_frame)
                        interpolated_value = (1 - factor) * prev_value + factor * current_value
                    else:
                        # Only next key exists - interpolate from current to next
                        current_value = fcurve.evaluate(current_frame)
                        next_value = fcurve.evaluate(next_frame)
                        interpolated_value = (1 - factor) * current_value + factor * next_value
                    interpolated_values.append(interpolated_value)

                # Apply interpolated values to object
                if data_path == "location" and len(interpolated_values) >= 3:
                    obj.location = interpolated_values[:3]
                elif data_path == "rotation_euler" and len(interpolated_values) >= 3:
                    obj.rotation_euler = interpolated_values[:3]
                elif data_path == "rotation_quaternion" and len(interpolated_values) >= 4:
                    obj.rotation_quaternion = interpolated_values[:4]
                elif data_path == "scale" and len(interpolated_values) >= 3:
                    obj.scale = interpolated_values[:3]

                # Auto keyframe if enabled
                if context.scene.tool_settings.use_keyframe_insert_auto:
                    obj.keyframe_insert(data_path=data_path,
                                        frame=current_frame)


def find_keyframe_range(fcurves, current_frame):
    """Helper function to find previous and next keyframes"""
    previous_frame = None
    next_frame = None

    for fcurve in fcurves:
        keyframe_points = fcurve.keyframe_points
        for key in keyframe_points:
            if key.co[0] < current_frame:
                if previous_frame is None or key.co[0] > previous_frame:
                    previous_frame = key.co[0]
            elif key.co[0] > current_frame:
                if next_frame is None or key.co[0] < next_frame:
                    next_frame = key.co[0]

        if previous_frame is not None and next_frame is not None:
            break

    return previous_frame, next_frame


def clean_object_shapes_names():
    selected_objects = bpy.context.selected_objects
    for obj in selected_objects:
        if obj.data:  # Make sure the object has data
            obj.data.name = f"{obj.name}_shape"


def add_subdivision_surface_modifier():
    selected_objects = bpy.context.selected_objects
    for obj in selected_objects:
        for modifier in obj.modifiers:
            if modifier.type == 'SUBSURF':
                return
        subsurf_modifier = obj.modifiers.new(
            name="Subdivision", type='SUBSURF')
        subsurf_modifier.render_levels = 2
        subsurf_modifier.levels = 1


def align_object_to_bone():
    if bpy.context.object and bpy.context.object.type == 'ARMATURE' and bpy.context.object.mode == 'POSE':
        # Get the active armature and selected bone

        armature = bpy.context.object
        selected_objects = bpy.context.selected_objects
        selected_objects.remove(armature)
        object_to_align = selected_objects[0]
        selected_bones = [
            bone for bone in armature.pose.bones if bone.bone.select]

        if selected_bones:
            # Get the first selected bone (if multiple are selected, it uses the first one)
            selected_bone = selected_bones[0]

            # Align object's location to the selected bone
            object_to_align.location = armature.matrix_world @ selected_bone.head

            # Align object's rotation to the selected bone
            # Set the rotation mode to Euler (XYZ)
            object_to_align.rotation_mode = 'XYZ'
            combined_matrix = armature.matrix_world @ selected_bone.matrix
            object_to_align.rotation_euler = combined_matrix.to_euler()
            print(
                f"Object '{object_to_align.name}' aligned to bone '{selected_bone.name}' in armature '{armature.name}'.")
        else:
            print("No bone is selected in the armature.")
    else:
        print("Please select an armature in Pose Mode and a bone.")


def align_bn_to_bn():
    if bpy.context.object and bpy.context.object.type == 'ARMATURE' and bpy.context.object.mode == 'POSE':
        # Get the active armature and selected bone

        armature = bpy.context.object
        active_pose_bone = armature.pose.bones[armature.data.bones.active.name]
        selected_bones = [
            bone for bone in armature.pose.bones if bone.bone.select]
        selected_bones.remove(
            bpy.data.objects[armature.name].pose.bones[active_pose_bone.name])

        if selected_bones:
            # Get the first selected bone (if multiple are selected, it uses the first one)
            selected_bone = selected_bones[0]

            selected_bone.matrix = active_pose_bone.matrix
            print(
                f"Bone '{selected_bone.name}' aligned to bone '{active_pose_bone.name}' in armature '{armature.name}'.")
        else:
            print("No bone is selected in the armature.")
    else:
        armature = bpy.context.object
        active_bone = armature.data.bones[armature.data.bones.active.name]
        selected_bones = [bone for bone in armature.data.bones if bone.select]
        selected_bones.remove(
            bpy.data.objects[armature.name].data.bones[active_bone.name])

        if selected_bones:
            # Get the first selected bone (if multiple are selected, it uses the first one)
            selected_bone = selected_bones[0]

            selected_bone.head = active_bone.head
            selected_bone.tail = active_bone.tail
            selected_bone.roll = active_bone.roll
            print(
                f"Bone '{selected_bone.name}' aligned to bone '{active_pose_bone.name}' in armature '{armature.name}'.")
        else:
            print("No bone is selected in the armature.")


def create_checker_material():
    # Check if CheckerMaterial already exists
    material = bpy.data.materials.get("CheckerMaterial")

    if material is None:
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
        links.new(checker_node.outputs['Color'],
                  bsdf_node.inputs['Base Color'])
        # Add a Texture Coordinate node
        tex_coord_node = nodes.new(type='ShaderNodeTexCoord')
        tex_coord_node.location = (-600, 0)
        # Link Texture Coordinate UV output to Checker Texture Vector input
        links.new(tex_coord_node.outputs['UV'], checker_node.inputs['Vector'])

    # Assign the material to all selected objects
    for obj in bpy.context.selected_objects:
        if obj.data and hasattr(obj.data, 'materials'):
            # Clear all existing materials first
            obj.data.materials.clear()
            obj.data.materials.append(material)


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
    # Register texturing tools
    texturing_tools.register()
    
    # Register animation transfer
    animation_transfer.register()
    
    # Register empty from vertices
    empty_from_vertices.register()
    
    # Register collection display tools
    collection_display.register()
    
    # Register our operators (only if not already registered)
    if not hasattr(bpy.types, 'ANIM_OT_reset_tween_stored_pose'):
        bpy.utils.register_class(reset_tween_stored_pose)
    if not hasattr(bpy.types, 'ANIM_OT_toggle_pose_object_mode'):
        bpy.utils.register_class(toggle_pose_object_mode)
    if not hasattr(bpy.types, 'ANIM_OT_toggle_interpolation_mode'):
        bpy.utils.register_class(toggle_interpolation_mode)
    if not hasattr(bpy.types, 'ANIM_OT_convert_rig_interpolation'):
        bpy.utils.register_class(convert_rig_interpolation)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_create_udim_mask'):
        bpy.utils.register_class(create_udim_mask)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_remove_materials'):
        bpy.utils.register_class(remove_materials)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_init_settings'):
        bpy.utils.register_class(init_settings)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_fixed_threads'):
        bpy.utils.register_class(fixed_threads)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_threads_all'):
        bpy.utils.register_class(threads_all)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_create_checker'):
        bpy.utils.register_class(create_checker)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_add_subdiv'):
        bpy.utils.register_class(add_subdiv)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_clean_shapes_names'):
        bpy.utils.register_class(clean_shapes_names)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_add_msh_suffix'):
        bpy.utils.register_class(add_msh_suffix)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_remove_all_modifiers'):
        bpy.utils.register_class(remove_all_modifiers)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_apply_mirror_modifiers'):
        bpy.utils.register_class(apply_mirror_modifiers)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_remove_all_vertex_groups'):
        bpy.utils.register_class(remove_all_vertex_groups)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_create_cage_deform_joints'):
        bpy.utils.register_class(create_cage_deform_joints)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_mirror_rig_drivers'):
        bpy.utils.register_class(mirror_rig_drivers)
    if not hasattr(bpy.types, 'LEO_TOOLS_OT_merge_gp_objects'):
        bpy.utils.register_class(bake_gp_objects)
    if not hasattr(bpy.types, 'VIEW3D_PT_leo_tools'):
        bpy.utils.register_class(CustomToolboxPanel)
    if not hasattr(bpy.types, 'VIEW3D_PT_anim_tools'):
        bpy.utils.register_class(AnimToolsPanel)
    
    # Register shape key operators (only if not already registered)
    if not hasattr(bpy.types, 'MESH_OT_create_corrective_shapekey'):
        bpy.utils.register_class(corrective_shapekey.MESH_OT_create_corrective_shapekey)
    if not hasattr(bpy.types, 'MESH_OT_create_intermediate_shapekey'):
        bpy.utils.register_class(intermediate_shapekey.MESH_OT_create_intermediate_shapekey)
    if not hasattr(bpy.types, 'MESH_OT_create_position_driven_shapekey'):
        bpy.utils.register_class(position_driven_shapekey.MESH_OT_create_position_driven_shapekey)
    if not hasattr(bpy.types, 'MESH_OT_mirror_shapekeys_and_drivers'):
        bpy.utils.register_class(mirror_shapekeys.MESH_OT_mirror_shapekeys_and_drivers)
    if not hasattr(bpy.types, 'MESH_OT_create_combo_shapekey'):
        bpy.utils.register_class(combo_shapekey.MESH_OT_create_combo_shapekey)
    
    bpy.types.Scene.tween_machine_percentage = bpy.props.FloatProperty(
        name="Percentage",
        description="Percentage between previous and next keyframes",
        default=50.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE',
        update=update_tween)
    
    bpy.types.Scene.tween_stored_pose = bpy.props.StringProperty(
        name="Stored Pose",
        description="JSON data storing the initial pose for tweening",
        default="")


def unregister():
    # Unregister operators (only if registered)
    if hasattr(bpy.types, 'ANIM_OT_reset_tween_stored_pose'):
        bpy.utils.unregister_class(reset_tween_stored_pose)
    if hasattr(bpy.types, 'ANIM_OT_toggle_pose_object_mode'):
        bpy.utils.unregister_class(toggle_pose_object_mode)
    if hasattr(bpy.types, 'ANIM_OT_toggle_interpolation_mode'):
        bpy.utils.unregister_class(toggle_interpolation_mode)
    if hasattr(bpy.types, 'ANIM_OT_convert_rig_interpolation'):
        bpy.utils.unregister_class(convert_rig_interpolation)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_create_udim_mask'):
        bpy.utils.unregister_class(create_udim_mask)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_remove_materials'):
        bpy.utils.unregister_class(remove_materials)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_init_settings'):
        bpy.utils.unregister_class(init_settings)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_fixed_threads'):
        bpy.utils.unregister_class(fixed_threads)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_threads_all'):
        bpy.utils.unregister_class(threads_all)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_create_checker'):
        bpy.utils.unregister_class(create_checker)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_add_subdiv'):
        bpy.utils.unregister_class(add_subdiv)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_clean_shapes_names'):
        bpy.utils.unregister_class(clean_shapes_names)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_add_msh_suffix'):
        bpy.utils.unregister_class(add_msh_suffix)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_remove_all_modifiers'):
        bpy.utils.unregister_class(remove_all_modifiers)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_apply_mirror_modifiers'):
        bpy.utils.unregister_class(apply_mirror_modifiers)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_remove_all_vertex_groups'):
        bpy.utils.unregister_class(remove_all_vertex_groups)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_create_cage_deform_joints'):
        bpy.utils.unregister_class(create_cage_deform_joints)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_mirror_rig_drivers'):
        bpy.utils.unregister_class(mirror_rig_drivers)
    if hasattr(bpy.types, 'LEO_TOOLS_OT_merge_gp_objects'):
        bpy.utils.unregister_class(bake_gp_objects)
    if hasattr(bpy.types, 'VIEW3D_PT_leo_tools'):
        bpy.utils.unregister_class(CustomToolboxPanel)
    if hasattr(bpy.types, 'VIEW3D_PT_anim_tools'):
        bpy.utils.unregister_class(AnimToolsPanel)
    
    # Unregister animation transfer
    animation_transfer.unregister()
    
    # Unregister empty from vertices
    empty_from_vertices.unregister()
    
    # Unregister collection display tools
    collection_display.unregister()
    
    # Unregister shape key operators (only if registered)
    if hasattr(bpy.types, 'MESH_OT_create_corrective_shapekey'):
        bpy.utils.unregister_class(corrective_shapekey.MESH_OT_create_corrective_shapekey)
    if hasattr(bpy.types, 'MESH_OT_create_intermediate_shapekey'):
        bpy.utils.unregister_class(intermediate_shapekey.MESH_OT_create_intermediate_shapekey)
    if hasattr(bpy.types, 'MESH_OT_create_position_driven_shapekey'):
        bpy.utils.unregister_class(position_driven_shapekey.MESH_OT_create_position_driven_shapekey)
    if hasattr(bpy.types, 'MESH_OT_mirror_shapekeys_and_drivers'):
        bpy.utils.unregister_class(mirror_shapekeys.MESH_OT_mirror_shapekeys_and_drivers)
    if hasattr(bpy.types, 'MESH_OT_create_combo_shapekey'):
        bpy.utils.unregister_class(combo_shapekey.MESH_OT_create_combo_shapekey)
    
    # Delete scene properties (only if they exist)
    if hasattr(bpy.types.Scene, 'tween_machine_percentage'):
        del bpy.types.Scene.tween_machine_percentage
    if hasattr(bpy.types.Scene, 'tween_stored_pose'):
        del bpy.types.Scene.tween_stored_pose


if __name__ == "__main__":
    register()
