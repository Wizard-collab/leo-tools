import pymel.core as pm
import maya.OpenMaya as om

def getDagPath(node=None):
    sel = om.MSelectionList()
    sel.add(node)
    d = om.MDagPath()
    sel.getDagPath(0, d)
    return d

def getLocalOffset(parent, child):
    parentWorldMatrix = getDagPath(parent).inclusiveMatrix()
    childWorldMatrix = getDagPath(child).inclusiveMatrix()

    return childWorldMatrix * parentWorldMatrix.inverse()

def create_constraint():
    parent = pm.selected()[0]
    child = pm.selected()[1]

    nameMult = str(parent) + '_MMX'
    nameDec = str(parent) + '_DMX'
    nameQuatprod = str(parent) + '_QPRD'
    nameQuatinv = str(parent) + '_QINV'
    nameQuattoEuler = str(parent) + '_QTE'
    nameEulertoQuat = str(parent) + '_ETQ'

    multMatrix = pm.createNode('multMatrix', n= nameMult)
    decomposeMatrix = pm.createNode('decomposeMatrix', n= nameDec)

    localOffset = getLocalOffset(parent, child)
    pm.setAttr(multMatrix.matrixIn[0], [localOffset(i, j) for i in range(4) for j in range(4)], type="matrix")

    parent.worldMatrix[0] >> multMatrix.matrixIn[1]
    child.parentInverseMatrix[0] >> multMatrix.matrixIn[2]

    multMatrix.matrixSum >> decomposeMatrix.inputMatrix

    if child.nodeType() == "joint":
        quatProd = pm.createNode('quatProd', n=nameQuatprod)
        eulerToQuat = pm.createNode('eulerToQuat', n=nameEulertoQuat)
        quatInvert = pm.createNode('quatInvert', n=nameQuatinv)
        quatToEuler = pm.createNode('quatToEuler', n=nameQuattoEuler)
        decomposeMatrix.outputQuat >> quatProd.input1Quat
        child.jointOrient >> eulerToQuat.inputRotate
        eulerToQuat.outputQuat >> quatInvert.inputQuat
        quatInvert.outputQuat >> quatProd.input2Quat
        quatProd.outputQuat >> quatToEuler.inputQuat
        quatToEuler.outputRotate >> child.rotate
    else:
        decomposeMatrix.outputRotate >> child.rotate
    decomposeMatrix.outputTranslate >> child.translate

    print(f"Constraint created between {parent} (parent) and {child} (child)")
