# coding: utf-8
# Author: Leo BRUNEL
# Contact: contact@leobrunel.com

import pymel.core as pm
import maya.cmds as cmds

def tween():
    from tweenMachine import tweenMachine
    tweenMachine.start()

def cloth():
    from leo_tools import easy_cloth
    win = easy_cloth.easy_cloth()
    win.showUI()

def clean():
    from leo_tools import clean_obj
    clean_obj.export_delete_reimport_rename()

def anim_view():
    current_panel = cmds.getPanel(withFocus=True)
    cmds.modelEditor(current_panel, edit=True, allObjects=False)  # Hide non-polygon objects
    cmds.modelEditor(current_panel, edit=True, polymeshes=True)
    cmds.modelEditor(current_panel, edit=True, manipulators=False)
    cmds.modelEditor(current_panel, edit=True, grid=False)
    cmds.modelEditor(current_panel, edit=True, sel=False) # Hide NURBS curves
    cmds.refresh()

def work_view():
    current_panel = cmds.getPanel(withFocus=True)
    cmds.modelEditor(current_panel, edit=True, allObjects=True)  # Hide non-polygon objects
    cmds.modelEditor(current_panel, edit=True, manipulators=True)
    cmds.modelEditor(current_panel, edit=True, grid=True)
    cmds.modelEditor(current_panel, edit=True, sel=True) # Hide NURBS curves
    cmds.refresh()

def create_nulls():
    from leo_tools import create_nulls
    create_nulls.create_nulls_on_selection()

def create_matrix_constraint():
    from leo_tools import matrix_constraint
    matrix_constraint.create_constraint()

def picker():
    from mgear import anim_picker
    anim_picker.load()

def create_shelf(shelf_name, button_functions):
    try:
        pm.deleteUI(shelf_name, layout=True)
    except:
        pass

    shelf = pm.shelfLayout(shelf_name, p="ShelfLayout")

    for button in button_functions:
        button_function = button[0]
        button_icon = button[1]
        button_name = button_function.__name__
        pm.shelfButton(annotation=button_name, imageOverlayLabel=button_name, image=button_icon, command=pm.Callback(button_function))

def create_leo_shelf():
    create_shelf('Leo', [(tween, 'pythonFamily.png'),
                        (cloth, 'pythonFamily.png'),
                        (clean, 'pythonFamily.png'),
                        (anim_view, 'pythonFamily.png'),
                        (work_view, 'pythonFamily.png'),
                        (create_nulls, 'pythonFamily.png'),
                        (create_matrix_constraint, 'pythonFamily.png'),
                        (picker, 'pythonFamily.png')])