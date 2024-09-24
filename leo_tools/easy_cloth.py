from PySide2 import QtWidgets, QtCore, QtGui
from maya import OpenMayaUI as omui
from shiboken2 import wrapInstance 
import pymel.core as pm
import logging
import os

EASY_CLOTH_PREFIX = 'easycloth'
SIM_GRP_SUFFIX = f"sim_grp"
CLOTH_MTL_NAME = f'{EASY_CLOTH_PREFIX}_cloth_mtl'
RIGID_MTL_NAME = f'{EASY_CLOTH_PREFIX}_rigid_mtl'
CLOTH_GRP_NAME = 'cloth_grp'
RIGID_GRP_NAME = 'rigid_grp'
DUPLICATA_SUFFIX = 'sim_msh'
NUCLEUS__SUFFIX = 'nucleus'
BLEND_SHAPE_SUFFIX = 'collider_bs'
SIM_GRP_ATTR_NAME = 'easy_cloth_sim_group'

def maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)

class create_sim_grp_widget(QtWidgets.QDialog):
    def __init__(self, parent=maya_main_window()):
        super(create_sim_grp_widget, self).__init__(parent)
        self.build_ui()
        self.connect_functions()

    def build_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.name_lineedit = QtWidgets.QLineEdit()
        self.main_layout.addWidget(self.name_lineedit)
        self.create_button = QtWidgets.QPushButton('Create')
        self.main_layout.addWidget(self.create_button)

    def connect_functions(self):
        self.create_button.clicked.connect(self.create_sim_group)

    def create_sim_group(self):
        name = self.name_lineedit.text()
        if name == '':
            logging.warning('Please enter a name')
            return
        if create_sim_grp(name):
            self.accept()

class easy_cloth(QtWidgets.QDialog):
    def __init__(self, parent=maya_main_window()):
        super(easy_cloth, self).__init__(parent)
        self.setWindowTitle("Easy cloth")
        self.build_ui()
        self.connect_functions()
        self.is_sim_group_modif_manual = True
        self.current_sim = None
        self.refresh()

    def refresh_sim_grps(self):
        self.is_sim_group_modif_manual = False
        current_sim = self.sim_groups_combobox.currentText()
        self.sim_groups_combobox.clear()
        for sim_grp in list_scene_sim_grps():
            self.sim_groups_combobox.addItem(str(sim_grp))
        if current_sim != '':
            self.sim_groups_combobox.setCurrentText(current_sim)
        self.is_sim_group_modif_manual = True

    def modify_sim_grp(self):
        if not self.is_sim_group_modif_manual:
            return
        self.refresh()

    def refresh(self):
        self.refresh_sim_grps()
        current_sim = self.sim_groups_combobox.currentText()
        if current_sim == '':
            self.current_sim = None
        else:
            self.current_sim = current_sim
        if self.current_sim:
            self.nucleus_group.setEnabled(True)
            self.ncloth_group.setEnabled(True)
            self.nrigid_group.setEnabled(True)
            self.ncache_group.setEnabled(True)
            self.nucleus_name_label.setText(f'Nucleus : {self.current_sim}_{NUCLEUS__SUFFIX}')
            self.start_frame_spinBox.setValue(get_start_frame(self.current_sim))
        else:
            self.nucleus_group.setEnabled(False)
            self.ncloth_group.setEnabled(False)
            self.nrigid_group.setEnabled(False)
            self.ncache_group.setEnabled(False)
            self.nucleus_name_label.setText(f'Nucleus : ...')
            self.start_frame_spinBox.setValue(0)

    def create_sim_grp(self):
        self.create_sim_grp_widget = create_sim_grp_widget(self)
        self.create_sim_grp_widget.exec_()
        self.refresh()

    def build_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

        self.sim_grp_group = QtWidgets.QGroupBox("Simulation group")
        self.sim_grp_layout = QtWidgets.QHBoxLayout()
        self.sim_grp_group.setLayout(self.sim_grp_layout)
        self.main_layout.addWidget(self.sim_grp_group)

        self.sim_groups_combobox = QtWidgets.QComboBox()
        self.sim_grp_layout.addWidget(self.sim_groups_combobox)

        self.create_new_sim_grp_button = QtWidgets.QPushButton('+')
        self.create_new_sim_grp_button.setFixedSize(20,20)
        self.sim_grp_layout.addWidget(self.create_new_sim_grp_button)

        self.refresh_sim_grp_button = QtWidgets.QPushButton('refresh')
        self.refresh_sim_grp_button.setFixedSize(60,20)
        self.sim_grp_layout.addWidget(self.refresh_sim_grp_button)

        self.nucleus_group = QtWidgets.QGroupBox("Nucleus")
        self.nucleus_layout = QtWidgets.QVBoxLayout()
        self.nucleus_group.setLayout(self.nucleus_layout)
        self.main_layout.addWidget(self.nucleus_group)

        self.nucleus_name_label = QtWidgets.QLabel()
        self.nucleus_layout.addWidget(self.nucleus_name_label)

        self.start_frame_layout = QtWidgets.QHBoxLayout()
        self.nucleus_layout.addLayout(self.start_frame_layout)
        self.start_frame_spinBox = QtWidgets.QSpinBox()
        self.start_frame_spinBox.setValue(0)
        self.start_frame_spinBox.setRange(-1000000, 1000000)
        self.start_frame_layout.addWidget(QtWidgets.QLabel('Start frame'))
        self.start_frame_layout.addWidget(self.start_frame_spinBox)

        self.assign_default_nucleus_parameters_button = QtWidgets.QPushButton("Assign Guff parameters on nucleus")
        self.nucleus_layout.addWidget(self.assign_default_nucleus_parameters_button)

        self.ncloth_group = QtWidgets.QGroupBox("nCloth")
        self.ncloth_layout = QtWidgets.QVBoxLayout()
        self.ncloth_group.setLayout(self.ncloth_layout)
        self.main_layout.addWidget(self.ncloth_group)

        self.create_ncloth_button = QtWidgets.QPushButton("Create nCloth on selection")
        self.create_ncloth_button.setIconSize(QtCore.QSize(40,40))
        self.create_ncloth_button.setIcon(QtGui.QIcon(':/nClothCreate.png'))
        self.ncloth_layout.addWidget(self.create_ncloth_button)

        self.assign_default_cloth_parameters_button = QtWidgets.QPushButton("Assign Guff parameters on cloth")
        self.ncloth_layout.addWidget(self.assign_default_cloth_parameters_button)

        self.nrigid_group = QtWidgets.QGroupBox("nRigid")
        self.nrigid_layout = QtWidgets.QVBoxLayout()
        self.nrigid_group.setLayout(self.nrigid_layout)
        self.main_layout.addWidget(self.nrigid_group)

        self.subdiv_layout = QtWidgets.QHBoxLayout()
        self.nrigid_layout.addLayout(self.subdiv_layout)

        self.subdiv_layout.addWidget(QtWidgets.QLabel('Collider subdivision'))
        self.subdiv_combobox = QtWidgets.QComboBox()
        self.subdiv_layout.addWidget(self.subdiv_combobox)
        for subdiv in range(0,5):
            self.subdiv_combobox.addItem(str(subdiv))

        self.create_nrigid_button = QtWidgets.QPushButton("Create nRigid on selection")
        self.create_nrigid_button.setIconSize(QtCore.QSize(40,40))
        self.create_nrigid_button.setIcon(QtGui.QIcon(':/nClothCreatePassive.png'))
        self.nrigid_layout.addWidget(self.create_nrigid_button)

        self.assign_default_rigid_parameters_button = QtWidgets.QPushButton("Assign Guff parameters on collider")
        self.nrigid_layout.addWidget(self.assign_default_rigid_parameters_button)

        self.ncache_group = QtWidgets.QGroupBox("nCache")
        self.ncache_layout = QtWidgets.QVBoxLayout()
        self.ncache_group.setLayout(self.ncache_layout)
        self.main_layout.addWidget(self.ncache_group)

        self.create_ncache_button = QtWidgets.QPushButton("Sim nCache on selection")
        self.create_ncache_button.setIconSize(QtCore.QSize(40,40))
        self.create_ncache_button.setIcon(QtGui.QIcon(':/nClothCacheCreate.png'))
        self.ncache_layout.addWidget(self.create_ncache_button)

        self.create_ncache_HD_button = QtWidgets.QPushButton("Sim nCache on selection (HD)")
        self.create_ncache_HD_button.setIconSize(QtCore.QSize(40,40))
        self.create_ncache_HD_button.setIcon(QtGui.QIcon(':/nClothCacheCreate.png'))
        self.ncache_layout.addWidget(self.create_ncache_HD_button)

        self.open_ncache_folder_button = QtWidgets.QPushButton("Open nCache folder")
        self.ncache_layout.addWidget(self.open_ncache_folder_button)

    def connect_functions(self):
        self.create_ncloth_button.clicked.connect(lambda:apply_nCloth_to_selected(sim_grp_name=self.current_sim))
        self.assign_default_cloth_parameters_button.clicked.connect(lambda:assign_default_ncloth_parameters())
        self.create_nrigid_button.clicked.connect(lambda:apply_nRigid_to_selected(sim_grp_name=self.current_sim, subdiv=int(self.subdiv_combobox.currentText())))
        self.assign_default_rigid_parameters_button.clicked.connect(lambda:assign_default_nrigid_parameters())
        self.start_frame_spinBox.valueChanged.connect(lambda:set_start_frame(sim_grp_name=self.current_sim, start_frame=self.start_frame_spinBox.value()))
        self.create_ncache_button.clicked.connect(lambda:create_ncache_on_selection())
        self.create_ncache_HD_button.clicked.connect(lambda:create_ncache_on_selection(HD=True))
        self.open_ncache_folder_button.clicked.connect(open_ncache_folder)
        self.create_new_sim_grp_button.clicked.connect(self.create_sim_grp)
        self.refresh_sim_grp_button.clicked.connect(self.refresh)
        self.sim_groups_combobox.currentTextChanged.connect(self.modify_sim_grp)

def open_ncache_folder():
    ncache_path = get_ncache_dir()
    if not ncache_path:
        return
    os.startfile(ncache_path)

def create_or_get_nucleus(sim_grp_name):
    sim_grp = get_sim_grp(sim_grp_name)
    nucleus_name = f"{sim_grp_name}_{NUCLEUS__SUFFIX}"
    if not pm.objExists(nucleus_name):
        nucleus = pm.createNode('nucleus', name=nucleus_name)
        time_node = pm.PyNode('time1')
        time_node.outTime >> nucleus.currentTime
    nucleus = pm.PyNode(nucleus_name)
    pm.parent(nucleus, sim_grp)
    assign_default_nucleus_parameters(nucleus)
    return nucleus

def set_start_frame(start_frame, sim_grp_name):
    nucleus = create_or_get_nucleus(sim_grp_name)
    pm.setAttr(nucleus.startFrame, start_frame)

def get_start_frame(sim_grp_name):
    nucleus = create_or_get_nucleus(sim_grp_name)
    return pm.getAttr(nucleus.startFrame)

def create_ncache_on_selection(HD=False):
    obj = get_selection()
    if not obj:
        return
    sim_dir = get_sim_dir(obj).replace('\\', '/')
    if not sim_dir:
        return
    if HD==True:
        melCommand = 'doCreateNclothCache 5 { "2", "1", "10", "OneFile", "1", "' + sim_dir + '","0","' + obj + '","0", "replace", "0", "0.2", "1","0","1","mcx" } ;'
    else:
        melCommand = 'doCreateNclothCache 5 { "2", "1", "10", "OneFile", "1", "' + sim_dir + '","0","' + obj + '","0", "replace", "0", "1", "1","0","1","mcx" } ;'
    logging.info(f"Writing cache in {sim_dir}")
    pm.mel.eval(melCommand)

def get_ncache_dir():
    scene_dir = os.path.dirname(pm.sceneName())
    if not scene_dir:
        logging.warning("Please save scene before creating nCache")
        return
    ncache_path = os.path.join(scene_dir, 'ncache')
    if not os.path.isdir(ncache_path):
        os.makedirs(ncache_path)
    return ncache_path

def get_sim_dir(obj):
    ncache_dir = get_ncache_dir()
    if not ncache_dir:
        return
    obj_ncache_dir = os.path.join(ncache_dir, obj.getName())
    if not os.path.isdir(obj_ncache_dir):
        os.makedirs(obj_ncache_dir)

    version = 1
    version_dir = os.path.join(obj_ncache_dir, str(version).zfill(4))
    while os.path.isdir(version_dir):
        version += 1
        version_dir = os.path.join(obj_ncache_dir, str(version).zfill(4))
    os.makedirs(version_dir)
    return version_dir

def increment_folder(folder_name):
    num=1
    folder = "{}_{}".format(folder_name, str(num).zfill(4))
    while os.path.isdir(folder):
        num+=1
        folder = "{}_{}".format(folder_name, str(num).zfill(4))
    os.makedirs(folder)

    return folder

def apply_nCloth_to_selected(sim_grp_name):
    obj = get_selection()
    if not obj:
        return
    sim_grp = get_sim_grp(sim_grp_name)
    sim_duplicata, cloth_grp = duplicate_hide_and_group(obj=obj,
                                                        grp_name=f"{obj.split(':')[-1]}_{CLOTH_GRP_NAME}",
                                                        duplicata_suffix=DUPLICATA_SUFFIX,
                                                        parent=sim_grp)
    ncloth = apply_nCloth_to_object(sim_duplicata, sim_grp_name)
    pm.parent(ncloth, cloth_grp)
    pm.select(sim_duplicata)

def apply_nRigid_to_selected(sim_grp_name, subdiv=0):
    obj = get_selection()
    if not obj:
        return
    sim_grp = get_sim_grp(sim_grp_name)
    sim_duplicata, rigid_grp = duplicate_hide_and_group(obj=obj,
                                                        grp_name=f"{obj.split(':')[-1]}_{RIGID_GRP_NAME}",
                                                        duplicata_suffix=DUPLICATA_SUFFIX,
                                                        parent=sim_grp,
                                                        blend_shape=True)
    if subdiv > 0:
        pm.polySmooth(sim_duplicata, dv=subdiv)
        pm.delete(sim_duplicata, constructionHistory=True)
    nrigid = apply_nRigid_to_object(sim_duplicata, sim_grp_name)
    pm.parent(nrigid, rigid_grp)
    pm.select(sim_duplicata)

def duplicate_hide_and_group(obj, grp_name, duplicata_suffix, parent, blend_shape=False):
    grp = pm.group(empty=True, name=grp_name)
    logging.info(f"{grp_name} created")
    duplicata = pm.duplicate(obj)[0]
    pm.parent(duplicata, grp)
    duplicata.rename(f"{obj}_{duplicata_suffix}")
    pm.delete(duplicata, constructionHistory=True)
    logging.info(f"{obj} duplicated to {duplicata}")
    pm.setAttr(obj.visibility, 0)
    pm.parent(grp, parent)
    if blend_shape is True:
        blendshape_node = pm.blendShape(obj,
                                        duplicata,
                                        origin='world',
                                        name=f'{obj}_{BLEND_SHAPE_SUFFIX}')[0]
        blendshape_node.setAttr(obj.name(), 1.0) 
    return duplicata, grp

def list_scene_sim_grps():
    sim_grps = []
    for transform in pm.ls(type='transform'):
        if transform.hasAttr('easy_cloth_sim_group'):
            sim_grps.append(transform)
    return sim_grps

def create_sim_grp(sim_grp_name):
    if not pm.objExists(sim_grp_name):
        grp = pm.group(empty=True, name=sim_grp_name)
        logging.info(f'{sim_grp_name} created')
        create_or_get_nucleus(sim_grp_name)
        pm.addAttr(grp, longName=SIM_GRP_ATTR_NAME, attributeType='enum')
        return 1
    else:
        logging.warning(f"{sim_grp_name} already exists")
        return 0

def get_sim_grp(sim_grp_name):
    return pm.PyNode(sim_grp_name)

def assign_ec_nucleus_and_remove_created_one(sim_grp_name, n_shape, before_creation_nucleus_list):
    nucleus_created_by_maya = list(set(pm.ls(type='nucleus')) - set(before_creation_nucleus_list))
    for nucleus in nucleus_created_by_maya:
        pm.delete(nucleus)
        logging.info(f'Deleting {nucleus} ( Created by maya )')
    ec_nucleus = create_or_get_nucleus(sim_grp_name)
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

def apply_nCloth_to_object(obj, sim_grp_name):
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
    assign_mtl(obj, CLOTH_MTL_NAME, RGB=[0.1,0.1,0.3])
    assign_default_ncloth_parameters(ncloth_shape)
    assign_ec_nucleus_and_remove_created_one(sim_grp_name,
                                            ncloth_shape,
                                            before_creation_nucleus_list)

    return ncloth

def apply_nRigid_to_object(obj, sim_grp_name):
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
    assign_mtl(obj, RIGID_MTL_NAME, RGB=[0.3,0.1,0.1])
    assign_default_nrigid_parameters(nrigid_shape)
    assign_ec_nucleus_and_remove_created_one(sim_grp_name,
                                            nrigid_shape,
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


def assign_default_nucleus_parameters(nucleus):
    pm.setAttr(nucleus.subSteps, 12)
    pm.setAttr(nucleus.maxCollisionIterations, 24)
    pm.setAttr(nucleus.spaceScale, 0.1)

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