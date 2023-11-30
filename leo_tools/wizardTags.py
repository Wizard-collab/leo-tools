from PySide2 import QtWidgets, QtGui, QtCore
from shiboken2 import wrapInstance
import maya.OpenMayaUI as omui
import pymel.core as pm
import logging

logger = logging.getLogger(__name__)

class wizardTags_editor(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(wizardTags_editor, self).__init__(parent)

        self.setWindowTitle("WizardTags editor")
        self.setMinimumWidth(800)
        self.setMinimumHeight(400)

        self.build_ui()
        self.connect_functions()

    def build_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

        self.selected_object_label = QtWidgets.QLabel("No object selected")
        self.main_layout.addWidget(self.selected_object_label)

        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.main_layout.addWidget(self.refresh_button)

        self.wizardTags_list = QtWidgets.QListWidget()
        self.wizardTags_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.main_layout.addWidget(self.wizardTags_list)

        self.remove_selected_tag_button = QtWidgets.QPushButton("Remove selected tags")
        self.main_layout.addWidget(self.remove_selected_tag_button)

        self.add_tag_lineEdit = QtWidgets.QLineEdit()
        self.add_tag_lineEdit.setPlaceholderText("New tag")
        self.main_layout.addWidget(self.add_tag_lineEdit)

        self.add_button = QtWidgets.QPushButton("Add tag")
        self.main_layout.addWidget(self.add_button)

    def connect_functions(self):
        self.refresh_button.clicked.connect(self.refresh)
        self.remove_selected_tag_button.clicked.connect(self.remove_tags)
        self.add_button.clicked.connect(self.add_tag)

    def refresh(self):
        self.selection = pm.ls(sl=True)
        if len(self.selection) > 1:
            self.selected_object_label.setText("More than one object selected")
            self.selection = None
        elif len(self.selection) < 1:
            self.selected_object_label.setText("No object selected")
            self.selection = None
        else:
            self.selected_object_label.setText(f"{self.selection[0].getName()}")
        self.refresh_existing_tags()

    def refresh_existing_tags(self):
        self.wizardTags_list.clear()
        if not self.selection:
            return
        if not pm.attributeQuery("wizardTags", node=self.selection[0], exists=True):
            pm.addAttr(self.selection[0], ln="wizardTags", dt='string')
        attr_value = pm.getAttr(f"{self.selection[0]}.wizardTags")
        if attr_value is None or attr_value == '':
            return
        for tag in attr_value.split(','):
            self.wizardTags_list.addItem(tag)

    def add_tag(self):
        if not self.selection:
            return
        attr_value = pm.getAttr(f"{self.selection[0]}.wizardTags")
        if attr_value is None:
            attr_value = ''
        new_tag = self.add_tag_lineEdit.text()
        if ',' in new_tag:
            logger.warning("Can't add a tag containing a coma")
            return
        if new_tag == '':
            return
        if new_tag in attr_value.split(','):
            return
        if attr_value is None or attr_value == '':
            tags_list = []
        else:
            tags_list = attr_value.split(',')
        tags_list.append(new_tag)
        pm.setAttr(f'{self.selection[0]}.wizardTags', ",".join(tags_list))
        self.refresh()

    def remove_tags(self):
        if not self.selection:
            return
        selected_tags = [item.text() for item in self.wizardTags_list.selectedItems()]
        attr_value = pm.getAttr(f"{self.selection[0]}.wizardTags")
        if attr_value is None or attr_value == '':
            tags_list = []
        else:
            tags_list = attr_value.split(',')
        for tag in selected_tags:
            if tag in tags_list:
                tags_list.remove(tag)
        pm.setAttr(f'{self.selection[0]}.wizardTags', ",".join(tags_list))
        self.refresh()

def show_ui():
    global ui
    try:
        ui.close()  # Close the existing UI
    except:
        pass

    ui = wizardTags_editor()
    ui.show()

show_ui()