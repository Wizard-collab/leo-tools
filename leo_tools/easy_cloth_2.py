from PySide2 import QtWidgets, QtCore, QtGui
from maya import OpenMayaUI as omui
from shiboken2 import wrapInstance 
import pymel.core as pm
import logging

EASY_CLOTH_PREFIX = 'easycloth'
SIM_GRP_NAME = f"{EASY_CLOTH_PREFIX}_sim_grp"
CLOTH_MTL_NAME = f'{EASY_CLOTH_PREFIX}_cloth_mtl'
RIGID_MTL_NAME = f'{EASY_CLOTH_PREFIX}_rigid_mtl'
CLOTH_GRP_NAME = 'cloth_grp'
RIGID_GRP_NAME = 'rigid_grp'
DUPLICATA_SUFFIX = 'sim_msh'
NUCLEUS_NAME = 'easy_cloth_nucleus'

def maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)

class easy_cloth(QtWidgets.QDialog):
    def __init__(self, parent=maya_main_window()):
        super(easy_cloth, self).__init__(parent)
        self.setWindowTitle("Easy cloth")
        self.build_ui()
        self.connect_functions()

    def build_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

        self.create_ncloth_button = QtWidgets.QPushButton("Create nCloth on selection")
        self.create_ncloth_button.setIconSize(QtCore.QSize(40,40))
        self.create_ncloth_button.setIcon(QtGui.QIcon(':/nClothCreate.png'))
        self.main_layout.addWidget(self.create_ncloth_button)

        self.assign_default_cloth_parameters_button = QtWidgets.QPushButton("Assign Guff parameters on cloth")
        self.main_layout.addWidget(self.assign_default_cloth_parameters_button)

        self.create_nrigid_button = QtWidgets.QPushButton("Create nRigid on selection")
        self.create_nrigid_button.setIconSize(QtCore.QSize(40,40))
        self.create_nrigid_button.setIcon(QtGui.QIcon(':/nClothCreatePassive.png'))
        self.main_layout.addWidget(self.create_nrigid_button)

        self.assign_default_rigid_parameters_button = QtWidgets.QPushButton("Assign Guff parameters on collider")
        self.main_layout.addWidget(self.assign_default_rigid_parameters_button)

    def connect_functions(self):
        self.create_ncloth_button.clicked.connect(apply_nCloth_to_selected)
        self.assign_default_cloth_parameters_button.clicked.connect(lambda:assign_default_ncloth_parameters())
        self.create_nrigid_button.clicked.connect(apply_nRigid_to_selected)
        self.assign_default_rigid_parameters_button.clicked.connect(lambda:assign_default_nrigid_parameters())

def create_or_get_nucleus():
    sim_grp = create_or_get_sim_grp()
    if not pm.objExists(NUCLEUS_NAME):
        nucleus = pm.createNode('nucleus', name=NUCLEUS_NAME)
        time_node = pm.PyNode('time1')
        time_node.outTime >> nucleus.currentTime
    nucleus = pm.PyNode(NUCLEUS_NAME)
    pm.parent(nucleus, sim_grp)
    return nucleus

def apply_nCloth_to_selected():
    obj = get_selection()
    if not obj:
        return
    sim_grp = create_or_get_sim_grp()
    sim_duplicata, cloth_grp = duplicate_hide_and_group(obj=obj,
                                                        grp_name=f"{obj.split(':')[-1]}_{CLOTH_GRP_NAME}",
                                                        duplicata_suffix=DUPLICATA_SUFFIX,
                                                        parent=sim_grp)
    ncloth = apply_nCloth_to_object(sim_duplicata)
    pm.parent(ncloth, cloth_grp)
    pm.select(sim_duplicata)

def apply_nRigid_to_selected():
    obj = get_selection()
    if not obj:
        return
    sim_grp = create_or_get_sim_grp()
    sim_duplicata, rigid_grp = duplicate_hide_and_group(obj=obj,
                                                        grp_name=f"{obj.split(':')[-1]}_{RIGID_GRP_NAME}",
                                                        duplicata_suffix=DUPLICATA_SUFFIX,
                                                        parent=sim_grp)
    nrigid = apply_nRigid_to_object(sim_duplicata)
    pm.parent(nrigid, rigid_grp)
    pm.select(sim_duplicata)

def duplicate_hide_and_group(obj, grp_name, duplicata_suffix, parent):
    grp = pm.group(empty=True, name=grp_name)
    logging.info(f"{grp_name} created")
    duplicata = pm.duplicate(obj)[0]
    pm.parent(duplicata, grp)
    duplicata.rename(f"{obj}_{duplicata_suffix}")
    logging.info(f"{obj} duplicated to {duplicata}")
    pm.setAttr(obj.visibility, 0)
    pm.parent(grp, parent)
    return duplicata, grp

def create_or_get_sim_grp():
    if not pm.objExists(SIM_GRP_NAME):
        pm.group(empty=True, name=SIM_GRP_NAME)
        logging.info(f'{SIM_GRP_NAME} created')
    return pm.PyNode(SIM_GRP_NAME)

def assign_ec_nucleus_and_remove_created_one(n_shape, before_creation_nucleus_list):
    nucleus_created_by_maya = list(set(pm.ls(type='nucleus')) - set(before_creation_nucleus_list))
    for nucleus in nucleus_created_by_maya:
        pm.delete(nucleus)
        logging.info(f'Deleting {nucleus} ( Created by maya )')
    ec_nucleus = create_or_get_nucleus()
    if pm.objectType(n_shape) == 'nCloth':
        connect_ncloth_shape_to_nucleus(n_shape, ec_nucleus)
    elif pm.objectType(n_shape) == 'nRigid':
        connect_nrigid_shape_to_nucleus(n_shape, ec_nucleus)

def connect_ncloth_shape_to_nucleus(ncloth_shape, nucleus):
    nucleus.startFrame >> ncloth_shape.startFrame
    ncloth_shape.currentState >> nucleus.inputActive[len(nucleus.inputActive.listConnections(plugs=True))]
    ncloth_shape.startState >> nucleus.inputActiveStart[len(nucleus.inputActiveStart.listConnections(plugs=True))]
    nucleus.outputObjects[len(nucleus.outputObjects.listConnections(plugs=True))] >> ncloth_shape.nextState

def connect_nrigid_shape_to_nucleus(nrigid_shape, nucleus):
    nucleus.startFrame >> nrigid_shape.startFrame
    nrigid_shape.currentState >> nucleus.inputActive[len(nucleus.inputActive.listConnections(plugs=True))]
    nrigid_shape.startState >> nucleus.inputActiveStart[len(nucleus.inputActiveStart.listConnections(plugs=True))]

def apply_nCloth_to_object(obj):
    before_creation_nucleus_list = pm.ls(type='nucleus')

    pm.select(obj)
    logging.info(f"Creating nCloth for {obj}")
    ncloth_shape = pm.mel.eval('createNCloth 0;')
    if len(ncloth_shape) == 0:
        logging.warning(f"Can't create nCloth on {obj}")
        return

    ncloth_shape = pm.PyNode(ncloth_shape[0])
    ncloth = ncloth_shape.getParent()
    ncloth.rename(f"{obj.name()}_nCloth")
    
    output_cloth_mesh = ncloth_shape.outputMesh.listConnections(destination=True, plugs=True)[0].node()
    output_cloth_mesh.rename(f"{obj.name()}_outputcloth")
    logging.info(f"{obj.name()}_nCloth created")
    assign_mtl(obj, CLOTH_MTL_NAME, RGB=[0.3,0.3,0.5])
    assign_default_ncloth_parameters(ncloth_shape)

    assign_ec_nucleus_and_remove_created_one(ncloth_shape,
                                            before_creation_nucleus_list)

    return ncloth

def apply_nRigid_to_object(obj):
    before_creation_nucleus_list = pm.ls(type='nucleus')
    logging.info(f"Creating nRigid for {obj}")
    nrigid_shape = pm.mel.eval('makeCollideNCloth;')
    if len(nrigid_shape) == 0:
        logging.warning(f"Can't create nRigid on {obj}")
        return
    nrigid_shape = pm.PyNode(nrigid_shape[0])
    nrigid = nrigid_shape.getParent()
    nrigid.rename(f"{obj.name()}_nRigid")
    logging.info(f"{obj.name()}_nRigid created")
    assign_mtl(obj, RIGID_MTL_NAME, RGB=[0.5,0.3,0.3])
    assign_default_nrigid_parameters(nrigid_shape)
    assign_ec_nucleus_and_remove_created_one(nrigid_shape,
                                            before_creation_nucleus_list)
    return nrigid

def get_selection():
    selected_objects = pm.ls(selection=True)
    if not selected_objects:
        pm.warning("Please select an object.")
        return
    if len(selected_objects) != 1:
        pm.warning("Please select one object.")
        return

    obj = selected_objects[0]
    shape = obj.getShape()
    if not shape or not isinstance(shape, pm.nodetypes.Mesh):
        pm.warning(f"{obj} is not a mesh. Skipping.")
        return
    return selected_objects[0]

def assign_mtl(obj, mtl_name, RGB=[0.5,0.5,0.5]):
    if not pm.objExists(mtl_name):
        shader = pm.shadingNode('blinn', asShader=True)
        shader.rename(mtl_name)
        shading_group = pm.sets(name=f'{mtl_name}SG', empty=True, renderable=True, noSurfaceShader=True)
        shader.outColor >> shading_group.surfaceShader
        pm.setAttr(shader.colorR, RGB[0])
        pm.setAttr(shader.colorG, RGB[1])
        pm.setAttr(shader.colorB, RGB[2])
        pm.setAttr(shader.eccentricity, 0.85)
        pm.setAttr(shader.specularRollOff, 0.15)
    pm.sets(pm.PyNode(f'{mtl_name}SG'), edit=True, forceElement=obj)
    logging.info(f"{mtl_name} assigned to {obj}")

def assign_default_ncloth_parameters(ncloth_shape=None):
    if ncloth_shape is None:
        obj = get_selection()
        if obj is None:
            return
        obj_shape = obj.getShape()
        ncloth_obj = pm.listConnections(obj_shape, type='nCloth', source=0, destination=1)
        if len(ncloth_obj) == 0:
            logging.warning(f"No nCloth assigned to {obj}")
            return
        ncloth_shape = ncloth_obj[0].getShape()

    pm.setAttr(ncloth_shape.isDynamic,1)
    pm.setAttr(ncloth_shape.depthSort,0)
    pm.setAttr(ncloth_shape.thickness,0.058)
    pm.setAttr(ncloth_shape.bounce,0)
    pm.setAttr(ncloth_shape.friction,0.1)
    pm.setAttr(ncloth_shape.damp,0.01)
    pm.setAttr(ncloth_shape.stickiness,0)
    pm.setAttr(ncloth_shape.collideStrength,1)
    pm.setAttr(ncloth_shape.collisionFlag,3)
    pm.setAttr(ncloth_shape.selfCollisionFlag,1)
    pm.setAttr(ncloth_shape.maxSelfCollisionIterations,64)
    pm.setAttr(ncloth_shape.maxIterations,10000)
    pm.setAttr(ncloth_shape.pointMass,1)
    pm.setAttr(ncloth_shape.restLengthScale,1)
    pm.setAttr(ncloth_shape.localForceX,0)
    pm.setAttr(ncloth_shape.localForceY,0)
    pm.setAttr(ncloth_shape.localForceZ,0)
    pm.setAttr(ncloth_shape.localWindX,0)
    pm.setAttr(ncloth_shape.localWindY,0)
    pm.setAttr(ncloth_shape.localWindZ,0)
    pm.setAttr(ncloth_shape.collide,1)
    pm.setAttr(ncloth_shape.selfCollide,1)
    pm.setAttr(ncloth_shape.collisionLayer,0)
    pm.setAttr(ncloth_shape.windShadowDiffusion,0)
    pm.setAttr(ncloth_shape.windShadowDistance,0)
    pm.setAttr(ncloth_shape.airPushDistance,0)
    pm.setAttr(ncloth_shape.airPushVorticity,0)
    pm.setAttr(ncloth_shape.pushOut,0)
    pm.setAttr(ncloth_shape.pushOutRadius,0.231)
    pm.setAttr(ncloth_shape.crossoverPush,0)
    pm.setAttr(ncloth_shape.trappedCheck,0)
    pm.setAttr(ncloth_shape.forceField,0)
    pm.setAttr(ncloth_shape.fieldMagnitude,1)
    pm.setAttr(ncloth_shape.fieldDistance,1)
    pm.setAttr(ncloth_shape.pointForceField,0)
    pm.setAttr(ncloth_shape.pointFieldMagnitude,1)
    pm.setAttr(ncloth_shape.selfAttract,0)
    pm.setAttr(ncloth_shape.pointFieldDistance,2)
    pm.setAttr(ncloth_shape.localSpaceOutput,1)
    pm.setAttr(ncloth_shape.displayColorR,1)
    pm.setAttr(ncloth_shape.displayColorG,0.8)
    pm.setAttr(ncloth_shape.displayColorB,0)
    pm.setAttr(ncloth_shape.stretchResistance,200)
    pm.setAttr(ncloth_shape.compressionResistance,30)
    pm.setAttr(ncloth_shape.bendResistance,1)
    pm.setAttr(ncloth_shape.bendAngleDropoff,0.3)
    pm.setAttr(ncloth_shape.restitutionTension,1000)
    pm.setAttr(ncloth_shape.restitutionAngle,360)
    pm.setAttr(ncloth_shape.shearResistance,0)
    pm.setAttr(ncloth_shape.rigidity,0)
    pm.setAttr(ncloth_shape.usePolygonShells,0)
    pm.setAttr(ncloth_shape.deformResistance,0)
    pm.setAttr(ncloth_shape.inputMeshAttract,0)
    pm.setAttr(ncloth_shape.collideLastThreshold,0.2)
    pm.setAttr(ncloth_shape.inputAttractDamp,0.5)
    pm.setAttr(ncloth_shape.inputMotionDrag,0)
    pm.setAttr(ncloth_shape.wrinkleMapScale,1)
    pm.setAttr(ncloth_shape.bendAngleScale,1)
    pm.setAttr(ncloth_shape.sortLinks,0)
    pm.setAttr(ncloth_shape.addCrossLinks,1)
    pm.setAttr(ncloth_shape.stretchDamp,200)
    pm.setAttr(ncloth_shape.selfCollideWidthScale,3)
    pm.setAttr(ncloth_shape.selfCrossoverPush,0)
    pm.setAttr(ncloth_shape.selfTrappedCheck,0)
    pm.setAttr(ncloth_shape.pressure,0)
    pm.setAttr(ncloth_shape.startPressure,0)
    pm.setAttr(ncloth_shape.incompressibility,5)
    pm.setAttr(ncloth_shape.pressureDamping,0)
    pm.setAttr(ncloth_shape.pumpRate,0)
    pm.setAttr(ncloth_shape.airTightness,1)
    pm.setAttr(ncloth_shape.sealHoles,1)
    pm.setAttr(ncloth_shape.ignoreSolverGravity,0)
    pm.setAttr(ncloth_shape.ignoreSolverWind,0)
    pm.setAttr(ncloth_shape.windSelfShadow,0)
    pm.setAttr(ncloth_shape.lift,0.02)
    pm.setAttr(ncloth_shape.drag,0.01)
    pm.setAttr(ncloth_shape.tangentialDrag,0.2)

    logging.info(f"Default parameters assigned to {ncloth_shape}")

def assign_default_nrigid_parameters(nrigid_shape=None):
    if nrigid_shape is None:
        obj = get_selection()
        if obj is None:
            return
        obj_shape = obj.getShape()
        nrigid_obj = pm.listConnections(obj_shape, type='nRigid', source=0, destination=1)
        if len(nrigid_obj) == 0:
            logging.warning(f"No nRigid assigned to {obj}")
            return
        nrigid_shape = nrigid_obj[0].getShape()

    pm.setAttr(nrigid_shape.isDynamic,1)
    pm.setAttr(nrigid_shape.depthSort,0)
    pm.setAttr(nrigid_shape.thickness,0.102)
    pm.setAttr(nrigid_shape.bounce,0)
    pm.setAttr(nrigid_shape.friction,0.1)
    pm.setAttr(nrigid_shape.damp,0)
    pm.setAttr(nrigid_shape.stickiness,0)
    pm.setAttr(nrigid_shape.collideStrength,1)
    pm.setAttr(nrigid_shape.collisionFlag,3)
    pm.setAttr(nrigid_shape.selfCollisionFlag,1)
    pm.setAttr(nrigid_shape.maxSelfCollisionIterations,4)
    pm.setAttr(nrigid_shape.maxIterations,10000)
    pm.setAttr(nrigid_shape.pointMass,1)
    pm.setAttr(nrigid_shape.restLengthScale,1)
    pm.setAttr(nrigid_shape.localForceX,0)
    pm.setAttr(nrigid_shape.localForceY,0)
    pm.setAttr(nrigid_shape.localForceZ,0)
    pm.setAttr(nrigid_shape.localWindX,0)
    pm.setAttr(nrigid_shape.localWindY,0)
    pm.setAttr(nrigid_shape.localWindZ,0)
    pm.setAttr(nrigid_shape.collide,1)
    pm.setAttr(nrigid_shape.selfCollide,0)
    pm.setAttr(nrigid_shape.collisionLayer,0)
    pm.setAttr(nrigid_shape.windShadowDiffusion,0)
    pm.setAttr(nrigid_shape.windShadowDistance,0)
    pm.setAttr(nrigid_shape.airPushDistance,0)
    pm.setAttr(nrigid_shape.airPushVorticity,0)
    pm.setAttr(nrigid_shape.pushOut,0)
    pm.setAttr(nrigid_shape.pushOutRadius,0)
    pm.setAttr(nrigid_shape.crossoverPush,0)
    pm.setAttr(nrigid_shape.trappedCheck,1)
    pm.setAttr(nrigid_shape.forceField,0)
    pm.setAttr(nrigid_shape.fieldMagnitude,1)
    pm.setAttr(nrigid_shape.fieldDistance,1)
    pm.setAttr(nrigid_shape.pointForceField,0)
    pm.setAttr(nrigid_shape.pointFieldMagnitude,1)
    pm.setAttr(nrigid_shape.selfAttract,0)
    pm.setAttr(nrigid_shape.pointFieldDistance,2)
    pm.setAttr(nrigid_shape.localSpaceOutput,0)
    pm.setAttr(nrigid_shape.displayColorR,1)
    pm.setAttr(nrigid_shape.displayColorG,0.8)
    pm.setAttr(nrigid_shape.displayColorB,0)

    logging.info(f"Default parameters assigned to {nrigid_shape}")
