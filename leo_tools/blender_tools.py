# coding: utf-8
# Author: Leo BRUNEL
# Contact: contact@leobrunel.com

# Python modules
import os
import traceback
import logging
logger = logging.getLogger(__name__)

# Blender modules
import bpy

# Wizard modules
import wizard_communicate
from blender_wizard import wizard_plugin

def add_subdivision_surface_modifier():
    selected_objects = bpy.context.selected_objects
    for obj in selected_objects:
        for modifier in obj.modifiers:
            if modifier.type == 'SUBSURF':
                return
        subsurf_modifier = obj.modifiers.new(name="Subdivision", type='SUBSURF')
        subsurf_modifier.render_levels = 2
        subsurf_modifier.levels = 1

def init_render_settings():
    wizard_plugin.set_image_size()
    bpy.context.scene.render.engine = 'CYCLES'
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

def set_fixed_thread():
    bpy.context.scene.render.threads_mode = 'FIXED'
    bpy.context.scene.render.threads = 18

def set_thread_all():
    bpy.context.scene.render.threads_mode = 'AUTO'

class init_settings(bpy.types.Operator):
    bl_idname = "leo.init_settings"
    bl_label = "Init render settings"
    bl_description = "Init render settings"
    
    def execute(self, context):
        init_render_settings()
        return {'FINISHED'}

class threads(bpy.types.Operator):
    bl_idname = "leo.threads"
    bl_label = "Set fixed threads to 18"
    bl_description = "Set fixed threads to 18"
    
    def execute(self, context):
        set_fixed_thread()
        return {'FINISHED'}

class threads_all(bpy.types.Operator):
    bl_idname = "leo.threads_all"
    bl_label = "Set threads to all"
    bl_description = "Set threads to all"
    
    def execute(self, context):
        set_thread_all()
        return {'FINISHED'}

class add_subdiv(bpy.types.Operator):
    bl_idname = "leo.add_subdiv"
    bl_label = "Add subdiv on selection"
    bl_description = "Add subdiv on selection"
    
    def execute(self, context):
        add_subdivision_surface_modifier()
        return {'FINISHED'}

class TOPBAR_MT_leo_menu(bpy.types.Menu):
    bl_label = "Leo"

    def draw(self, context):
        layout = self.layout
        layout.operator("leo.init_settings", icon_value=leo_icons["all"].icon_id)
        layout.operator("leo.threads", icon_value=leo_icons["all"].icon_id)
        layout.operator("leo.threads_all", icon_value=leo_icons["all"].icon_id)
        layout.operator("leo.add_subdiv", icon_value=leo_icons["all"].icon_id)

    def menu_draw(self, context):
        self.layout.menu("TOPBAR_MT_leo_menu")

classes = ( init_settings,
            threads,
            threads_all,
            add_subdiv,
            TOPBAR_MT_leo_menu)

def register():
    # Register classes
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_editor_menus.append(TOPBAR_MT_leo_menu.menu_draw)

    # Register icons
    global leo_icons
    leo_icons = bpy.utils.previews.new()
    leo_icons.load("all", 'icons/all.png', 'IMAGE')

def unregister():
    # Unregister classes
    bpy.types.TOPBAR_MT_editor_menus.remove(TOPBAR_MT_leo_menu.menu_draw)
    for cls in classes:
        bpy.utils.unregister_class(cls)

    # Unregister icons
    global custom_icons
    bpy.utils.previews.remove(leo_icons)
