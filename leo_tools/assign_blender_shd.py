# coding: utf-8
# Author: Leo BRUNEL
# Contact: contact@leobrunel.com

# Python modules
import bpy
import os

# Wizard modules
import wizard_communicate

# List all shading refs
references = wizard_communicate.get_references(int(os.environ['wizard_work_env_id']))

shading_dic = dict()
animation_objects = []

if 'shading' in references.keys():
    for reference in references['shading']:
        namespace = reference['namespace']
        coll = bpy.data.collections[namespace]
        for obj in coll.all_objects:
            if obj.type != 'MESH' or not obj.data.materials:
                continue
            material = obj.material_slots[0].material
            shading_dic[obj['wizardTags']] = material


if 'animation' in references.keys():
    for reference in references['animation']:
        namespace = reference['namespace']
        coll = bpy.data.collections[namespace]
        for obj in coll.all_objects:
            print(obj)
            if obj.type != 'MESH':
                continue
            try:
                tags = obj['wizardTags']
            except KeyError:
                continue
            if tags not in shading_dic.keys():
                continue
            material = shading_dic[tags]
            print(material)
