

import bpy


def get_udims_from_selected_objects():
    """
    Lists all UDIM tiles used by the selected objects in Blender.
    Checks UV coordinates and identifies which UDIM tiles they fall into.
    """
    selected_objects = bpy.context.selected_objects

    if not selected_objects:
        print("No objects selected!")
        return

    udim_tiles = set()

    for obj in selected_objects:
        if obj.type != 'MESH':
            continue

        # Get mesh data
        mesh = obj.data

        # Check if the mesh has UV layers
        if not mesh.uv_layers:
            print(f"Object '{obj.name}' has no UV layers")
            continue

        # Get the active UV layer
        uv_layer = mesh.uv_layers.active.data

        # Iterate through all UV coordinates
        for poly in mesh.polygons:
            for loop_index in poly.loop_indices:
                uv = uv_layer[loop_index].uv

                # Calculate UDIM tile number
                # UDIM format: 1001 + u_tile + (v_tile * 10)
                u_tile = int(uv.x)
                v_tile = int(uv.y)
                udim = 1001 + u_tile + (v_tile * 10)

                udim_tiles.add(udim)

    # Sort and display results
    if udim_tiles:
        sorted_udims = sorted(udim_tiles)
        print(f"\nFound {len(sorted_udims)} UDIM tile(s) in selected objects:")
        for udim in sorted_udims:
            u_tile = (udim - 1001) % 10
            v_tile = (udim - 1001) // 10
            print(f"  UDIM {udim} (U: {u_tile}, V: {v_tile})")
        return sorted_udims
    else:
        print("No UDIM tiles found in selected objects")
        return []


def create_map_with_udims(name, width):
    # Find a unique name if the image already exists
    unique_name = name
    counter = 1

    while bpy.data.images.get(unique_name) is not None:
        unique_name = f"{name}.{counter:03d}"
        counter += 1

    # Create a new image with the unique name
    bpy.ops.image.new(name=unique_name, width=width, height=width)

    # Get the newly created image object
    new_image = bpy.data.images.get(unique_name)
    if not new_image:
        print("Image not created")
        return
    new_image.source = 'TILED'
    # Get UDIMs from selected objects
    udims = get_udims_from_selected_objects()

    # Add tiles for each found UDIM
    if udims:
        # Find an Image Editor area or use override
        image_editor = None
        for area in bpy.context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                image_editor = area
                break

        # Store the original area type if we need to switch
        original_area = None
        original_type = None

        if not image_editor:
            # No Image Editor found, temporarily switch an area
            original_area = bpy.context.area
            original_type = original_area.type
            original_area.type = 'IMAGE_EDITOR'
            image_editor = original_area

        for udim in udims:
            # Set the image in the Image Editor context
            with bpy.context.temp_override(area=image_editor, space_data=image_editor.spaces.active):
                bpy.context.space_data.image = new_image
                bpy.ops.image.tile_add(number=udim,
                                       fill=True,
                                       color=(0.0, 0.0, 0.0, 1.0),
                                       generated_type="BLANK",
                                       width=width,
                                       height=width,
                                       float=False,
                                       alpha=False)

        # Restore the original area type if we changed it
        if original_area and original_type:
            original_area.type = original_type

    return new_image


# Operator to create UDIM map with dialog
class OBJECT_OT_create_udim_map(bpy.types.Operator):
    """Create a UDIM map for selected objects"""
    bl_idname = "object.create_udim_map"
    bl_label = "Create UDIM Map"
    bl_options = {'REGISTER', 'UNDO'}

    # Properties for the dialog
    image_name: bpy.props.StringProperty(
        name="Image Name",
        description="Name for the new UDIM image",
        default="MyMask"
    )

    image_width: bpy.props.IntProperty(
        name="Width",
        description="Width and height of the image in pixels",
        default=4096,
        min=64,
        max=16384
    )

    def execute(self, context):
        # Call the function with the user-provided values
        create_map_with_udims(self.image_name, self.image_width)
        self.report({'INFO'}, f"Created UDIM map: {self.image_name}")
        return {'FINISHED'}

    def invoke(self, context, event):
        # Show the dialog window
        return context.window_manager.invoke_props_dialog(self)


# Register the operator
def register():
    try:
        bpy.utils.register_class(OBJECT_OT_create_udim_map)
    except ValueError:
        pass


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_create_udim_map)


if __name__ == "__main__":
    register()

    # Call the operator to show the dialog
    bpy.ops.object.create_udim_map('INVOKE_DEFAULT')
