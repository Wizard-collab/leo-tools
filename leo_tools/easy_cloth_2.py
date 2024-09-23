from PySide2 import QtWidgets, QtCore, QtGui
from maya import OpenMayaUI as omui
from shiboken2 import wrapInstance 
import pymel.core as pm
import logging

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
        self.main_layout.addWidget(self.create_ncloth_button)

    def connect_functions(self):
        self.create_ncloth_button.clicked.connect(apply_nCloth_to_selected)

def apply_nCloth_to_selected():
    selected_objects = pm.ls(selection=True)
    if not selected_objects:
        pm.warning("Please select an object to apply nCloth.")
        return
    if len(selected_objects) != 1:
        pm.warning("Please select one object to apply nCloth")
        return

    obj = selected_objects[0]
    shape = obj.getShape()
    if not shape or not isinstance(shape, pm.nodetypes.Mesh):
        pm.warning(f"{obj} is not a mesh. Skipping.")
        continue
    
    logging.info(f"Creating nCloth for {obj}")
    ncloth_shape = pm.mel.eval('createNCloth 0;')
    ncloth_shape = pm.PyNode(ncloth_shape[0])
    ncloth_shape.getParent().rename(f"{obj.name()}_nCloth")
    
    output_cloth_mesh = ncloth_shape.outputMesh.listConnections(destination=True, plugs=True)[0].node()
    output_cloth_mesh.rename(f"{obj.name()}_outputcloth")
    logging.info(f"{obj.name()}_nCloth created")
