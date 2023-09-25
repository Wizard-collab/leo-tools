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

def init_render_settings():
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.render.film_transparent = True
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
    wizard_plugin.set_image_size()

def set_LD():
    bpy.context.scene.render.resolution_percentage = 50
    bpy.context.scene.cycles.adaptive_threshold = 0.1
    bpy.context.scene.render.threads_mode = 'AUTO'
    job_name = f"{os.environ['WIZARD_CATEGORY_NAME']}_{os.environ['WIZARD_ASSET_NAME']}_{os.environ['WIZARD_STAGE_NAME']}_LD"

def set_HD():
    bpy.context.scene.render.resolution_percentage = 100
    bpy.context.scene.cycles.adaptive_threshold = 0.01
    bpy.context.scene.render.threads_mode = 'AUTO'
    job_name = f"{os.environ['WIZARD_CATEGORY_NAME']}_{os.environ['WIZARD_ASSET_NAME']}_{os.environ['WIZARD_STAGE_NAME']}_HD"

def set_fixed_thread():
    bpy.context.scene.render.threads_mode = 'FIXED'
    bpy.context.scene.render.threads = 10

def get_RND_dir(export_name):
    RND_dir = wizard_communicate.request_render(int(os.environ['wizard_version_id']), export_name)
    return RND_dir

class leo_render_settings(bpy.types.Operator):
    bl_idname = "leo.leo_render_settings"
    bl_label = "Leo render settings"
    bl_description = "Apply leo render settings"
    
    def execute(self, context):
        init_render_settings()
        return {'FINISHED'}

class leo_LD(bpy.types.Operator):
    bl_idname = "leo.leo_ld"
    bl_label = "Set LD render settings"
    bl_description = "Set LD render settings"
    
    def execute(self, context):
        set_LD()
        return {'FINISHED'}

class leo_HD(bpy.types.Operator):
    bl_idname = "leo.leo_hd"
    bl_label = "Set HD render settings"
    bl_description = "Set HD render settings"
    
    def execute(self, context):
        set_HD()
        return {'FINISHED'}

class threads(bpy.types.Operator):
    bl_idname = "leo.threads"
    bl_label = "Set fixed threads to 10"
    bl_description = "Set fixed threads to 10"
    
    def execute(self, context):
        set_fixed_thread()
        return {'FINISHED'}

class TOPBAR_MT_leo_menu(bpy.types.Menu):
    bl_label = "Leo"

    def draw(self, context):
        layout = self.layout
        layout.operator("leo.leo_render_settings", icon_value=leo_icons["all"].icon_id)
        layout.operator("leo.leo_ld", icon_value=leo_icons["all"].icon_id)
        layout.operator("leo.leo_hd", icon_value=leo_icons["all"].icon_id)
        layout.operator("leo.threads", icon_value=leo_icons["all"].icon_id)
        layout.operator("leo.submit_flamenco", icon_value=leo_icons["all"].icon_id)

    def menu_draw(self, context):
        self.layout.menu("TOPBAR_MT_leo_menu")

classes = (leo_render_settings,
            leo_LD,
            leo_HD,
            threads,
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
