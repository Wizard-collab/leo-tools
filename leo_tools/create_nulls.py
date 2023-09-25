import pymel.core as pm

def create_nulls_on_selection():
    ctrl_list = pm.ls(sl=True)
    for ctrl in ctrl_list:
        create_null(ctrl)

def create_null(ctrl):
    zero_name = f'{ctrl.name()}_zero'
    zero = pm.group( em=True, name=zero_name)
    pm.parent( zero, ctrl )
    pm.setAttr(zero.tx, 0)
    pm.setAttr(zero.ty, 0)
    pm.setAttr(zero.tz, 0)
    pm.setAttr(zero.rx, 0)
    pm.setAttr(zero.ry, 0)
    pm.setAttr(zero.rz, 0)
    pm.parent(zero, world=True)
    parent = pm.listRelatives(ctrl, parent=True)
    if len(parent)==1:
        pm.parent(zero, parent)
    pm.parent(ctrl, zero)
    print(f"{zero_name} created for {ctrl}")

    
