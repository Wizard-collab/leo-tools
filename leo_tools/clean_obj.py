# coding: utf-8
# Author: Leo BRUNEL
# Contact: contact@leobrunel.com

import os
import pymel.core as pm

def export_delete_reimport_rename():
    temp_dir = os.path.join(pm.internalVar(userTmpDir=True), 'exported_objs')
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    selected_objects = pm.ls(selection=True)
    for obj in selected_objects:
        obj_name = str(obj)
        parent = obj.getParent()
        obj_export_name = obj_name.split(':')[-1]
        if '|' in obj_export_name:
            obj_export_name = obj_export_name.replace('|', '__')
        export_path = os.path.join(temp_dir, '{}.obj'.format(obj_export_name))
        pm.select(obj)
        pm.exportSelected(export_path, force=True, type='OBJexport', options='groups=0;ptgroups=0;materials=0;smoothing=0;normals=0')
        pm.delete(obj)
        imported_objs = pm.importFile(export_path, defaultNamespace=1, type='OBJ', options='mo=1', ignoreVersion=True, ra=True, mergeNamespacesOnClash=False, returnNewNodes=True)
        if imported_objs:
            imported_obj = imported_objs[0]
            if parent:
                imported_obj.setParent(parent)
            imported_obj.rename(obj_name)
    
    obj_files = [f for f in os.listdir(temp_dir) if f.endswith('.obj')]
    for obj_file in obj_files:
        os.remove(os.path.join(temp_dir, obj_file))
    os.rmdir(temp_dir)
