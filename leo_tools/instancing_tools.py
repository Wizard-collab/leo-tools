import bpy


class LEO_TOOLS_OT_instance_on_collection(bpy.types.Operator):
    """Create linked instances of an object at every target transform"""
    bl_idname = "leo_tools.instance_on_collection"
    bl_label = "Instance Final on Collection"
    bl_options = {'REGISTER', 'UNDO'}

    final_object: bpy.props.PointerProperty(
        name="Final Object",
        description="Object to create as linked instances",
        type=bpy.types.Object
    )
    target_collection: bpy.props.PointerProperty(
        name="Target Collection",
        description="Create one instance for every object in this collection",
        type=bpy.types.Collection
    )

    def invoke(self, context, event):
        self.final_object = context.active_object
        active_layer_collection = context.view_layer.active_layer_collection
        if active_layer_collection:
            self.target_collection = active_layer_collection.collection
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "final_object")
        layout.prop(self, "target_collection")

    def execute(self, context):
        if self.final_object is None:
            self.report({'ERROR'}, "Select a final object")
            return {'CANCELLED'}
        if self.target_collection is None:
            self.report({'ERROR'}, "Select a target collection")
            return {'CANCELLED'}

        targets = list(self.target_collection.all_objects)
        if not targets:
            self.report({'WARNING'}, "The target collection contains no objects")
            return {'CANCELLED'}

        instance_collection = bpy.data.collections.new(
            f"{self.target_collection.name}_instances")
        context.scene.collection.children.link(instance_collection)

        for target in targets:
            instance = self.final_object.copy()
            instance.data = self.final_object.data
            instance.matrix_world = target.matrix_world.copy()
            instance_collection.objects.link(instance)

        self.report(
            {'INFO'},
            f"Created {len(targets)} linked instance(s) in "
            f"'{instance_collection.name}'")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(LEO_TOOLS_OT_instance_on_collection)


def unregister():
    bpy.utils.unregister_class(LEO_TOOLS_OT_instance_on_collection)