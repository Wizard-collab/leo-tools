"""
Empty from Vertices Tool
Creates an empty object parented to selected vertices (3 vertices required)
The empty is positioned at the average location of the selected vertices
"""

import bpy
from bpy.types import Operator, Panel
from bpy.props import StringProperty
import bmesh
from mathutils import Vector


class MESH_OT_create_empty_from_vertices(Operator):
    """Create an empty parented to 3 selected vertices"""
    bl_idname = "mesh.create_empty_from_vertices"
    bl_label = "Create Empty from Vertices"
    bl_options = {'REGISTER', 'UNDO'}
    
    empty_name: StringProperty(
        name="Empty Name",
        description="Name for the new empty object",
        default="VertexEmpty"
    )
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "empty_name")
    
    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        
        # Get selected vertices in edit mode
        bm = bmesh.from_edit_mesh(mesh)
        selected_verts = [v for v in bm.verts if v.select]
        
        # Check if exactly 3 vertices are selected
        if len(selected_verts) != 3:
            self.report({'ERROR'}, f"Please select exactly 3 vertices (currently selected: {len(selected_verts)})")
            return {'CANCELLED'}
        
        # Calculate the average position of the 3 vertices in local space
        avg_position = Vector((0, 0, 0))
        vert_indices = []
        
        for vert in selected_verts:
            avg_position += vert.co
            vert_indices.append(vert.index)
        
        avg_position /= 3
        
        # Switch to object mode to create the empty
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Create the empty at origin first
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
        empty = context.active_object
        empty.name = self.empty_name
        
        # Parent the empty to the mesh with vertex parent
        empty.parent = obj
        empty.parent_type = 'VERTEX_3'
        
        # Set the vertex indices for the parent - this will automatically position the empty
        empty.parent_vertices = vert_indices
        
        # Select the original mesh again
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        
        # Return to edit mode
        bpy.ops.object.mode_set(mode='EDIT')
        
        self.report({'INFO'}, f"Empty '{self.empty_name}' created and parented to vertices {vert_indices}")
        return {'FINISHED'}


# Registration
classes = (
    MESH_OT_create_empty_from_vertices,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
