"""
Collection Display Tools
Set display properties for all objects in a collection
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty


class OBJECT_OT_collection_bounding_box(Operator):
    """Set all objects in the selected collection to bounding box display"""
    bl_idname = "object.collection_bounding_box"
    bl_label = "Collection to Bounding Box"
    bl_options = {'REGISTER', 'UNDO'}
    
    collection_name: StringProperty(
        name="Collection Name",
        description="Name of the collection to set to bounding box display",
        default=""
    )
    
    @classmethod
    def poll(cls, context):
        return context.view_layer.active_layer_collection is not None
    
    def invoke(self, context, event):
        # Get the active collection name
        active_collection = context.view_layer.active_layer_collection.collection
        self.collection_name = active_collection.name
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "collection_name")
    
    def execute(self, context):
        # Find the collection by name
        collection = bpy.data.collections.get(self.collection_name)
        
        if not collection:
            self.report({'ERROR'}, f"Collection '{self.collection_name}' not found")
            return {'CANCELLED'}
        
        # Count objects processed
        count = 0
        
        # Set all objects in the collection to bounding box display
        for obj in collection.all_objects:
            obj.display_type = 'BOUNDS'
            count += 1
        
        self.report({'INFO'}, f"Set {count} objects in '{self.collection_name}' to bounding box display")
        return {'FINISHED'}


class OBJECT_OT_collection_textured(Operator):
    """Set all objects in the selected collection to textured display"""
    bl_idname = "object.collection_textured"
    bl_label = "Collection to Textured"
    bl_options = {'REGISTER', 'UNDO'}
    
    collection_name: StringProperty(
        name="Collection Name",
        description="Name of the collection to set to textured display",
        default=""
    )
    
    @classmethod
    def poll(cls, context):
        return context.view_layer.active_layer_collection is not None
    
    def invoke(self, context, event):
        # Get the active collection name
        active_collection = context.view_layer.active_layer_collection.collection
        self.collection_name = active_collection.name
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "collection_name")
    
    def execute(self, context):
        # Find the collection by name
        collection = bpy.data.collections.get(self.collection_name)
        
        if not collection:
            self.report({'ERROR'}, f"Collection '{self.collection_name}' not found")
            return {'CANCELLED'}
        
        # Count objects processed
        count = 0
        
        # Set all objects in the collection to textured display
        for obj in collection.all_objects:
            obj.display_type = 'TEXTURED'
            count += 1
        
        self.report({'INFO'}, f"Set {count} objects in '{self.collection_name}' to textured display")
        return {'FINISHED'}


# Registration
classes = (
    OBJECT_OT_collection_bounding_box,
    OBJECT_OT_collection_textured,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
