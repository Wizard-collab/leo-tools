import bpy
import os
import tempfile


class smart_bake_textures(bpy.types.Operator):
    bl_idname = "leo_tools.smart_bake_textures"
    bl_label = "Bake selected textures"
    bl_description = "Create/reuse UDIM bake images, inject bake nodes in materials, and bake selected map types"
    bl_options = {'REGISTER', 'UNDO'}

    map_types: bpy.props.EnumProperty(
        name="Map Types",
        description="Maps to bake",
        items=[
            ('BASECOLOR', "BaseColor", "Bake base color"),
            ('ROUGHNESS', "Roughness", "Bake roughness"),
            ('METALLIC', "Metallic", "Bake metallic"),
            ('NORMAL', "Normal", "Bake normal"),
            ('DISPLACEMENT', "Displacement", "Bake displacement"),
            ('SUBSURFACE', "Subsurface", "Bake subsurface weight"),
            ('EMISSION', "Emission", "Bake emission color"),
            ('ALPHA', "Alpha", "Bake alpha"),
            ('TRANSMISSION', "Transmission", "Bake transmission"),
            ('SHEEN', "Sheen", "Bake sheen and related parameters")
        ],
        options={'ENUM_FLAG'},
        default={'BASECOLOR', 'ROUGHNESS', 'METALLIC', 'NORMAL'}
    )

    bake_name: bpy.props.StringProperty(
        name="Bake Name",
        description="Base name for output images",
        default="Bake"
    )

    resolution: bpy.props.EnumProperty(
        name="Resolution",
        description="Resolution for newly created images",
        items=[
            ('512', "512", "512x512"),
            ('2048', "2048", "2048x2048"),
            ('4096', "4096", "4096x4096")
        ],
        default='4096'
    )

    basecolor_colorspace: bpy.props.EnumProperty(
        name="BaseColor Color Space",
        description="Color space assigned to BaseColor baked image",
        items=[
            ('ACESCG', "ACEScg", "Use ACEScg / ACES - ACEScg"),
            ('SRGB', "sRGB", "Use sRGB texture color space"),
            ('RAW', "Raw", "Use Raw/Non-Color")
        ],
        default='ACESCG'
    )

    plug_baked_to_bsdf: bpy.props.BoolProperty(
        name="Plug Baked Maps To BSDF",
        description="Automatically connect baked image nodes to Principled BSDF inputs after baking",
        default=False
    )

    output_dir: bpy.props.StringProperty(
        name="Output Folder",
        description="Folder where baked images will be saved",
        subtype='DIR_PATH',
        default=""
    )

    save_format: bpy.props.EnumProperty(
        name="Save Format",
        description="File format used when saving baked maps",
        items=[
            ('PNG', "PNG", "Save baked maps as PNG"),
            ('OPEN_EXR', "OpenEXR", "Save baked maps as OpenEXR")
        ],
        default='PNG'
    )

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        if not getattr(self, 'output_dir', ''):
            blend_path = bpy.data.filepath
            if blend_path:
                default_dir = os.path.join(os.path.dirname(blend_path), "bakes")
            else:
                default_dir = os.path.join(tempfile.gettempdir(), "bakes")
            self.output_dir = default_dir
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "bake_name")
        layout.prop(self, "resolution")
        layout.prop(self, "basecolor_colorspace")
        layout.prop(self, "plug_baked_to_bsdf")
        layout.prop(self, "output_dir")
        layout.prop(self, "save_format")
        layout.label(text="Map Types")
        layout.prop(self, "map_types")

    def _selected_meshes(self, context):
        return [obj for obj in context.selected_objects if obj.type == 'MESH']

    def _get_udims_from_meshes(self, mesh_objects):
        udim_tiles = set()
        for obj in mesh_objects:
            mesh = obj.data
            if not mesh or not mesh.uv_layers:
                continue

            uv_layer = mesh.uv_layers.active
            if not uv_layer:
                continue
            uv_data = uv_layer.data

            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    uv = uv_data[loop_index].uv
                    u_tile = int(uv.x)
                    v_tile = int(uv.y)
                    udim = 1001 + u_tile + (v_tile * 10)
                    udim_tiles.add(udim)

        if not udim_tiles:
            udim_tiles.add(1001)
        return sorted(udim_tiles)

    def _get_image_editor_override(self, context):
        image_editor = None
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                image_editor = area
                break

        if image_editor:
            return image_editor, None

        if context.area is None:
            return None, None

        original_type = context.area.type
        context.area.type = 'IMAGE_EDITOR'
        return context.area, original_type

    def _ensure_udim_tiles_initialized(self, context, image, width, udims):
        image_editor, original_type = self._get_image_editor_override(context)
        if image_editor is None:
            return False

        try:
            existing_tiles = {tile.number for tile in image.tiles}
            for udim in udims:
                if udim in existing_tiles:
                    continue

                with context.temp_override(area=image_editor, space_data=image_editor.spaces.active):
                    bpy.context.space_data.image = image
                    bpy.ops.image.tile_add(
                        number=udim,
                        fill=True,
                        color=(0.0, 0.0, 0.0, 1.0),
                        generated_type="BLANK",
                        width=width,
                        height=width,
                        float=False,
                        alpha=False
                    )
            return True
        finally:
            if original_type is not None and context.area is not None:
                context.area.type = original_type

    def _create_tiled_image(self, image_name, width):
        bpy.ops.image.new(name=image_name, width=width, height=width)
        image = bpy.data.images.get(image_name)
        if image is None:
            return None
        image.source = 'TILED'
        return image

    def _ensure_udim_image(self, context, image_name, width, udims):
        image = bpy.data.images.get(image_name)

        needs_rebuild = False
        if image is not None:
            if image.source != 'TILED':
                needs_rebuild = True
            elif image.size[0] <= 0 or image.size[1] <= 0:
                needs_rebuild = True
            elif hasattr(image, 'has_data') and not image.has_data:
                needs_rebuild = True

        if needs_rebuild and image is not None:
            bpy.data.images.remove(image)
            image = None

        if image is None:
            image = self._create_tiled_image(image_name, width)
            if image is None:
                return None

        if image.source != 'TILED':
            image.source = 'TILED'

        # Ensure tile 1001 exists and is initialized.
        if not any(tile.number == 1001 for tile in image.tiles):
            if not self._ensure_udim_tiles_initialized(context, image, width, [1001]):
                image.tiles.new(1001)

        # Add and initialize missing UDIM tiles.
        if not self._ensure_udim_tiles_initialized(context, image, width, udims):
            existing_tiles = {tile.number for tile in image.tiles}
            for udim in udims:
                if udim not in existing_tiles:
                    image.tiles.new(udim)

        return image

    def _set_first_available_colorspace(self, image, candidates):
        for color_space_name in candidates:
            try:
                image.colorspace_settings.name = color_space_name
                return True
            except TypeError:
                continue
        return False

    def _map_suffix(self, map_type):
        mapping = {
            'BASECOLOR': 'basecolor',
            'ROUGHNESS': 'roughness',
            'METALLIC': 'metallic',
            'NORMAL': 'normal',
            'DISPLACEMENT': 'displacement',
            'SUBSURFACE': 'subsurface',
            'EMISSION': 'emission',
            'ALPHA': 'alpha',
            'TRANSMISSION': 'transmission',
            'SUBSURFACE_RADIUS': 'subsurface_radius',
            'SUBSURFACE_SCALE': 'subsurface_scale',
            'SHEEN': 'sheen',
            'SHEEN_ROUGHNESS': 'sheen_roughness',
            'SHEEN_TINT': 'sheen_tint'
        }
        return mapping[map_type]

    def _expanded_map_types(self):
        expanded = set(self.map_types)

        if 'SUBSURFACE' in expanded:
            expanded.add('SUBSURFACE_RADIUS')
            expanded.add('SUBSURFACE_SCALE')

        if 'SHEEN' in expanded:
            expanded.add('SHEEN_ROUGHNESS')
            expanded.add('SHEEN_TINT')

        return expanded

    def _map_order(self):
        return [
            'BASECOLOR',
            'ROUGHNESS',
            'METALLIC',
            'NORMAL',
            'DISPLACEMENT',
            'SUBSURFACE',
            'SUBSURFACE_RADIUS',
            'SUBSURFACE_SCALE',
            'TRANSMISSION',
            'ALPHA',
            'EMISSION',
            'SHEEN',
            'SHEEN_ROUGHNESS',
            'SHEEN_TINT'
        ]

    def _principled_input_candidates(self, map_type):
        mapping = {
            'BASECOLOR': ['Base Color'],
            'ROUGHNESS': ['Roughness'],
            'METALLIC': ['Metallic'],
            'NORMAL': ['Normal'],
            'SUBSURFACE': ['Subsurface Weight', 'Subsurface'],
            'EMISSION': ['Emission Color', 'Emission'],
            'ALPHA': ['Alpha'],
            'TRANSMISSION': ['Transmission Weight', 'Transmission'],
            'SUBSURFACE_RADIUS': ['Subsurface Radius'],
            'SUBSURFACE_SCALE': ['Subsurface Scale'],
            'SHEEN': ['Sheen Weight', 'Sheen'],
            'SHEEN_WEIGHT': ['Sheen Weight', 'Sheen'],
            'SHEEN_ROUGHNESS': ['Sheen Roughness'],
            'SHEEN_TINT': ['Sheen Tint']
        }
        return mapping.get(map_type, [])

    def _get_principled_input_socket(self, principled, map_type):
        for input_name in self._principled_input_candidates(map_type):
            socket = principled.inputs.get(input_name)
            if socket is not None:
                return socket
        return None

    def _source_reroute_name(self, map_type):
        return f"__LEOTOOLS_BAKE_SOURCE_{self._map_suffix(map_type)}"

    def _default_prop_name(self, map_type):
        return f"_leotools_bake_default_{self._map_suffix(map_type)}"

    def _get_principled_node(self, material):
        if not material.use_nodes or not material.node_tree:
            return None
        for node in material.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                return node
        return None

    def _get_output_node(self, material):
        if not material.use_nodes or not material.node_tree:
            return None
        for node in material.node_tree.nodes:
            if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
                return node
        for node in material.node_tree.nodes:
            if node.type == 'OUTPUT_MATERIAL':
                return node
        return None

    def _graph_anchor_for_bake_frame(self, node_tree, frame):
        candidate_nodes = [
            node for node in node_tree.nodes
            if node != frame and node.parent is None and node.type != 'FRAME'
        ]

        if not candidate_nodes:
            return (350.0, 180.0)

        max_x = max(node.location.x + getattr(node, 'width', 180.0) for node in candidate_nodes)
        max_y = max(node.location.y for node in candidate_nodes)
        return (max_x + 260.0, max_y + 40.0)

    def _ensure_bake_frame(self, material):
        node_tree = material.node_tree
        frame_name = f"__LEOTOOLS_BAKE_FRAME_{self.bake_name}"
        frame = node_tree.nodes.get(frame_name)
        created = False
        if frame is None or frame.type != 'FRAME':
            frame = node_tree.nodes.new(type='NodeFrame')
            frame.name = frame_name
            frame.label = f"BAKE {self.bake_name}"
            created = True

        if created:
            frame.location = self._graph_anchor_for_bake_frame(node_tree, frame)
            frame.width = 520
        return frame

    def _ensure_bake_node(self, material, map_type, image, map_index, frame):
        node_name = f"BAKE_{self.bake_name}_{self._map_suffix(map_type)}"
        node_tree = material.node_tree
        bake_node = node_tree.nodes.get(node_name)
        created = False
        if bake_node is None or bake_node.type != 'TEX_IMAGE':
            bake_node = node_tree.nodes.new(type='ShaderNodeTexImage')
            bake_node.name = node_name
            created = True

        bake_node.label = node_name
        bake_node.image = image
        if created:
            bake_node.parent = frame
            bake_node.location = (40, -50 - (map_index * 320))
        bake_node.hide = False
        bake_node.select = True
        node_tree.nodes.active = bake_node
        return bake_node

    def _store_input_default_snapshot(self, material, principled, map_type):
        socket = self._get_principled_input_socket(principled, map_type)
        if socket is None:
            return

        default_prop = self._default_prop_name(map_type)
        if default_prop in material:
            return

        value = socket.default_value
        if isinstance(value, float):
            material[default_prop] = float(value)
        else:
            material[default_prop] = list(value)

    def _is_baked_source_socket(self, source_socket):
        node = getattr(source_socket, 'node', None)
        if node is None:
            return False

        node_name = getattr(node, 'name', '')
        if node_name.startswith("BAKE_"):
            return True
        if node_name.startswith("__LEOTOOLS_BAKE_TMP_"):
            return True
        return False

    def _ensure_fallback_source_node(self, material, map_type, source_input):
        node_tree = material.node_tree
        suffix = self._map_suffix(map_type)
        node_name = f"__LEOTOOLS_BAKE_FALLBACK_{suffix}"
        fallback = node_tree.nodes.get(node_name)

        stored_default = self._get_stored_default(material, map_type)
        if stored_default is None:
            stored_default = source_input.default_value

        is_scalar = isinstance(stored_default, float)
        if fallback is None:
            fallback = node_tree.nodes.new(type='ShaderNodeValue' if is_scalar else 'ShaderNodeRGB')
            fallback.name = node_name
            fallback.label = node_name

        if is_scalar:
            if fallback.type != 'VALUE':
                node_tree.nodes.remove(fallback)
                fallback = node_tree.nodes.new(type='ShaderNodeValue')
                fallback.name = node_name
                fallback.label = node_name
            fallback.outputs[0].default_value = float(stored_default)
        else:
            if fallback.type != 'RGB':
                node_tree.nodes.remove(fallback)
                fallback = node_tree.nodes.new(type='ShaderNodeRGB')
                fallback.name = node_name
                fallback.label = node_name

            value = stored_default
            try:
                value = tuple(stored_default)
            except TypeError:
                value = source_input.default_value

            if len(value) == 3:
                value = (value[0], value[1], value[2], 1.0)
            fallback.outputs[0].default_value = value

        return fallback.outputs[0]

    def _ensure_source_reroute(self, material, map_type):
        if map_type == 'DISPLACEMENT':
            return

        principled = self._get_principled_node(material)
        if principled is None:
            return

        input_socket = self._get_principled_input_socket(principled, map_type)
        if input_socket is None:
            return

        # For Normal, only capture linked source chains (no fallback constant).
        if map_type == 'NORMAL' and not input_socket.links:
            return

        # Snapshot current default value so we can recover if link is replaced later.
        self._store_input_default_snapshot(material, principled, map_type)

        node_tree = material.node_tree
        reroute_name = self._source_reroute_name(map_type)
        reroute = node_tree.nodes.get(reroute_name)
        if reroute is None or reroute.type != 'REROUTE':
            reroute = node_tree.nodes.new(type='NodeReroute')
            reroute.name = reroute_name
            reroute.label = reroute_name
            try:
                map_index = self._map_order().index(map_type)
            except ValueError:
                map_index = 0
            reroute.location = (principled.location.x - 260, principled.location.y - (map_index * 20))

        if reroute.inputs[0].links:
            return

        source_socket = None
        if input_socket.links:
            candidate_socket = input_socket.links[0].from_socket
            if not self._is_baked_source_socket(candidate_socket):
                source_socket = candidate_socket

        if source_socket is None:
            source_socket = self._ensure_fallback_source_node(material, map_type, input_socket)

        try:
            node_tree.links.new(source_socket, reroute.inputs[0])
        except RuntimeError:
            pass

    def _get_marked_source(self, material, map_type):
        node_tree = material.node_tree
        reroute_name = self._source_reroute_name(map_type)
        reroute = node_tree.nodes.get(reroute_name)
        if reroute and reroute.type == 'REROUTE' and reroute.inputs[0].links:
            return reroute.inputs[0].links[0].from_socket
        return None

    def _get_stored_default(self, material, map_type):
        prop_name = self._default_prop_name(map_type)
        if prop_name not in material:
            return None

        stored_value = material[prop_name]
        if map_type in {
            'ROUGHNESS',
            'METALLIC',
            'DISPLACEMENT',
            'SUBSURFACE',
            'SUBSURFACE_SCALE',
            'TRANSMISSION',
            'ALPHA',
            'SHEEN',
            'SHEEN_ROUGHNESS',
            'SHEEN_TINT'
        }:
            try:
                return float(stored_value)
            except (TypeError, ValueError):
                return None

        try:
            values = list(stored_value)
        except TypeError:
            return None

        if len(values) == 3:
            values.append(1.0)
        if len(values) < 4:
            return None
        return (float(values[0]), float(values[1]), float(values[2]), float(values[3]))

    def _setup_emission_override(self, material, map_type):
        node_tree = material.node_tree
        links = node_tree.links
        output = self._get_output_node(material)
        if not output:
            return None

        if map_type == 'NORMAL':
            return None

        principled = self._get_principled_node(material)

        original_surface_links = [
            (link.from_socket, link.to_socket)
            for link in output.inputs['Surface'].links
        ]
        for link in output.inputs['Surface'].links[:]:
            links.remove(link)

        emission = node_tree.nodes.new(type='ShaderNodeEmission')
        emission.name = f"__BAKE_TMP_EMISSION_{self._map_suffix(map_type)}"

        if map_type == 'DISPLACEMENT':
            source_input = output.inputs.get('Displacement')
        else:
            if principled is None:
                node_tree.nodes.remove(emission)
                return None
            source_input = self._get_principled_input_socket(principled, map_type)

        if source_input is None:
            node_tree.nodes.remove(emission)
            return None

        marked_source = self._get_marked_source(material, map_type)
        if marked_source is not None:
            links.new(marked_source, emission.inputs['Color'])
        elif source_input.links:
            links.new(source_input.links[0].from_socket, emission.inputs['Color'])
        else:
            stored_default = self._get_stored_default(material, map_type)
            if stored_default is not None:
                if isinstance(stored_default, float):
                    emission.inputs['Color'].default_value = (stored_default, stored_default, stored_default, 1.0)
                else:
                    emission.inputs['Color'].default_value = stored_default
            else:
                default_value = source_input.default_value
                if isinstance(default_value, float):
                    emission.inputs['Color'].default_value = (default_value, default_value, default_value, 1.0)
                else:
                    emission.inputs['Color'].default_value = default_value

        links.new(emission.outputs['Emission'], output.inputs['Surface'])
        return {
            'material': material,
            'emission': emission,
            'original_surface_links': original_surface_links
        }

    def _restore_emission_override(self, override_data):
        material = override_data['material']
        emission = override_data['emission']
        original_surface_links = override_data['original_surface_links']

        if not material.use_nodes or not material.node_tree:
            return
        node_tree = material.node_tree
        links = node_tree.links
        output = self._get_output_node(material)
        if output is None:
            return

        for link in output.inputs['Surface'].links[:]:
            links.remove(link)

        for from_socket, to_socket in original_surface_links:
            if from_socket and to_socket:
                try:
                    links.new(from_socket, to_socket)
                except RuntimeError:
                    pass

        if emission and emission.name in node_tree.nodes:
            node_tree.nodes.remove(emission)

    def _prepare_material_nodes(self, materials, images_by_type):
        ordered_selected_map_types = [map_type for map_type in self._map_order() if map_type in images_by_type]
        for material in materials:
            if not material.use_nodes or not material.node_tree:
                continue

            frame = self._ensure_bake_frame(material)

            for map_type in ordered_selected_map_types:
                self._ensure_source_reroute(material, map_type)
            for index, map_type in enumerate(ordered_selected_map_types):
                self._ensure_bake_node(material, map_type, images_by_type[map_type], index, frame)

    def _activate_map_nodes(self, materials, map_type):
        node_name = f"BAKE_{self.bake_name}_{self._map_suffix(map_type)}"
        for material in materials:
            if not material.use_nodes or not material.node_tree:
                continue
            node_tree = material.node_tree
            node = node_tree.nodes.get(node_name)
            if node and node.type == 'TEX_IMAGE':
                for n in node_tree.nodes:
                    n.select = False
                node.select = True
                node_tree.nodes.active = node

    def _configure_image_colorspace(self, image, map_type):
        basecolor_space = getattr(self, 'basecolor_colorspace', 'ACESCG')
        if map_type in {'BASECOLOR', 'EMISSION'}:
            if basecolor_space == 'RAW':
                preferred = ['Non-Color', 'Utility - Raw', 'Raw', 'Role - data', 'role_data']
            elif basecolor_space == 'SRGB':
                preferred = ['sRGB', 'Utility - sRGB - Texture', 'Input - Generic - sRGB - Texture', 'srgb_texture']
            else:
                preferred = ['acescg', 'ACES - ACEScg']

            # Prefer the user-selected color space, then fallback to common texture roles.
            self._set_first_available_colorspace(
                image,
                preferred + [
                    'acescg',
                    'ACES - ACEScg',
                    'sRGB',
                    'Utility - sRGB - Texture',
                    'Input - Generic - sRGB - Texture',
                    'srgb_texture',
                    'Role - texture_paint',
                    'role_texture_paint'
                ]
            )
        else:
            # Data maps should be non-color/raw depending on OCIO config.
            self._set_first_available_colorspace(
                image,
                [
                    'Non-Color',
                    'Utility - Raw',
                    'Raw',
                    'Role - data',
                    'role_data'
                ]
            )

    def _connect_baked_maps_to_bsdf(self, materials, images_by_type):
        ordered_map_types = self._map_order()

        for material in materials:
            if not material.use_nodes or not material.node_tree:
                continue

            node_tree = material.node_tree
            links = node_tree.links
            principled = self._get_principled_node(material)
            if principled is None:
                continue

            for map_type in ordered_map_types:
                if map_type not in images_by_type:
                    continue

                bake_node_name = f"BAKE_{self.bake_name}_{self._map_suffix(map_type)}"
                bake_node = node_tree.nodes.get(bake_node_name)
                if bake_node is None or bake_node.type != 'TEX_IMAGE':
                    continue

                if map_type == 'NORMAL':
                    normal_input = principled.inputs.get('Normal')
                    if normal_input is None:
                        continue

                    normal_map_node_name = f"{bake_node_name}_normal_map"
                    normal_map = node_tree.nodes.get(normal_map_node_name)
                    if normal_map is None or normal_map.type != 'NORMAL_MAP':
                        normal_map = node_tree.nodes.new(type='ShaderNodeNormalMap')
                        normal_map.name = normal_map_node_name
                        normal_map.label = normal_map_node_name
                        normal_map.location = (bake_node.location.x + 220, bake_node.location.y)

                    normal_map.space = 'TANGENT'

                    for link in normal_map.inputs['Color'].links[:]:
                        links.remove(link)
                    for link in normal_input.links[:]:
                        links.remove(link)

                    links.new(bake_node.outputs['Color'], normal_map.inputs['Color'])
                    links.new(normal_map.outputs['Normal'], normal_input)
                    continue

                if map_type == 'DISPLACEMENT':
                    output = self._get_output_node(material)
                    if output is None:
                        continue

                    displacement_node_name = f"{bake_node_name}_displacement"
                    displacement_node = node_tree.nodes.get(displacement_node_name)
                    if displacement_node is None or displacement_node.type != 'DISPLACEMENT':
                        displacement_node = node_tree.nodes.new(type='ShaderNodeDisplacement')
                        displacement_node.name = displacement_node_name
                        displacement_node.label = displacement_node_name
                        displacement_node.location = (bake_node.location.x + 220, bake_node.location.y)

                    for link in displacement_node.inputs['Height'].links[:]:
                        links.remove(link)
                    for link in output.inputs['Displacement'].links[:]:
                        links.remove(link)

                    links.new(bake_node.outputs['Color'], displacement_node.inputs['Height'])
                    links.new(displacement_node.outputs['Displacement'], output.inputs['Displacement'])
                    continue

                bsdf_input = self._get_principled_input_socket(principled, map_type)
                if bsdf_input is None:
                    continue

                for link in bsdf_input.links[:]:
                    links.remove(link)

                links.new(bake_node.outputs['Color'], bsdf_input)

    def _get_save_directory(self):
        output_dir = getattr(self, 'output_dir', "//bakes")

        if output_dir:
            save_dir = bpy.path.abspath(output_dir)
        else:
            blend_path = bpy.data.filepath
            if blend_path:
                base_dir = os.path.dirname(blend_path)
            else:
                base_dir = tempfile.gettempdir()
            save_dir = os.path.join(base_dir, "bakes")

        if not save_dir:
            save_dir = os.path.join(tempfile.gettempdir(), "bakes")

        os.makedirs(save_dir, exist_ok=True)
        return save_dir

    def _save_baked_images(self, images_by_type):
        save_dir = self._get_save_directory()
        failed = []
        save_format = getattr(self, 'save_format', 'PNG')
        extension = '.exr' if save_format == 'OPEN_EXR' else '.png'

        for map_type, image in images_by_type.items():
            suffix = self._map_suffix(map_type)
            filename = f"{self.bake_name}_{suffix}.<UDIM>{extension}"
            filepath = os.path.join(save_dir, filename)

            try:
                image.filepath_raw = filepath
                image.file_format = save_format
                image.save()
            except RuntimeError:
                failed.append(image.name)

        return save_dir, failed

    def _build_temp_bake_object(self, context, source_meshes):
        if not source_meshes:
            return None

        bpy.ops.object.select_all(action='DESELECT')
        for obj in source_meshes:
            obj.select_set(True)
        context.view_layer.objects.active = source_meshes[0]

        bpy.ops.object.duplicate()
        dupes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not dupes:
            return None

        # Apply visual transform + evaluated geometry on duplicates only.
        for obj in dupes:
            if obj.name not in bpy.data.objects:
                continue
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            try:
                bpy.ops.object.visual_transform_apply()
            except RuntimeError:
                pass
            try:
                bpy.ops.object.convert(target='MESH')
            except RuntimeError:
                pass

        dupe_names = [obj.name for obj in dupes]
        dupes = [obj for obj in bpy.data.objects if obj.name in dupe_names and obj.type == 'MESH']
        if not dupes:
            return None

        bpy.ops.object.select_all(action='DESELECT')
        for obj in dupes:
            obj.select_set(True)
        context.view_layer.objects.active = dupes[0]

        if len(dupes) > 1:
            bpy.ops.object.join()

        temp_obj = context.view_layer.objects.active
        if temp_obj and temp_obj.type == 'MESH':
            temp_obj.name = f"__LEOTOOLS_BAKE_TMP_{self.bake_name}"
            return temp_obj

        return None

    def _cleanup_temp_bake_object(self, temp_obj):
        if not temp_obj or temp_obj.name not in bpy.data.objects:
            return

        mesh_data = temp_obj.data if temp_obj.type == 'MESH' else None
        bpy.data.objects.remove(temp_obj, do_unlink=True)

        if mesh_data and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)

    def _progress_begin(self, context, total_steps):
        self._progress_total = max(1, int(total_steps))
        self._progress_current = 0
        context.window_manager.progress_begin(0, self._progress_total)

    def _progress_step(self, context):
        self._progress_current = min(self._progress_current + 1, self._progress_total)
        context.window_manager.progress_update(self._progress_current)

    def _progress_end(self, context):
        context.window_manager.progress_end()
        self._progress_total = 0
        self._progress_current = 0

    def execute(self, context):
        if not self.map_types:
            self.report({'ERROR'}, "Please select at least one map type")
            return {'CANCELLED'}

        selected_meshes = self._selected_meshes(context)
        if not selected_meshes:
            self.report({'ERROR'}, "Select at least one mesh object")
            return {'CANCELLED'}

        if context.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                self.report({'ERROR'}, "Switch to Object mode before baking")
                return {'CANCELLED'}

        resolution = int(self.resolution)
        udims = self._get_udims_from_meshes(selected_meshes)

        materials = []
        for obj in selected_meshes:
            for slot in obj.material_slots:
                mat = slot.material
                if mat and mat not in materials:
                    materials.append(mat)

        if not materials:
            self.report({'ERROR'}, "No materials found on selected meshes")
            return {'CANCELLED'}

        requested_map_types = self._expanded_map_types()
        ordered_requested_map_types = [m for m in self._map_order() if m in requested_map_types]

        total_progress_steps = (2 * len(ordered_requested_map_types)) + 4
        self._progress_begin(context, total_progress_steps)

        try:
            images_by_type = {}
            for map_type in ordered_requested_map_types:
                image_name = f"{self.bake_name}_{self._map_suffix(map_type)}"
                image = self._ensure_udim_image(context, image_name, resolution, udims)
                if image is None:
                    self.report({'ERROR'}, f"Could not create or load image: {image_name}")
                    return {'CANCELLED'}
                self._configure_image_colorspace(image, map_type)
                images_by_type[map_type] = image
                self._progress_step(context)

            self._prepare_material_nodes(materials, images_by_type)

            original_engine = context.scene.render.engine
            original_samples = context.scene.cycles.samples if hasattr(context.scene, 'cycles') else None
            original_active = context.view_layer.objects.active
            original_selected = list(context.selected_objects)
            temp_bake_object = None

            try:
                context.scene.render.engine = 'CYCLES'
                if hasattr(context.scene, 'cycles'):
                    context.scene.cycles.samples = 1

                if len(selected_meshes) > 1:
                    temp_bake_object = self._build_temp_bake_object(context, selected_meshes)
                self._progress_step(context)

                bake_targets = [temp_bake_object] if temp_bake_object else selected_meshes

                bpy.ops.object.select_all(action='DESELECT')
                for obj in bake_targets:
                    if obj and obj.name in bpy.data.objects:
                        obj.select_set(True)
                if bake_targets and bake_targets[0] and bake_targets[0].name in bpy.data.objects:
                    context.view_layer.objects.active = bake_targets[0]
                else:
                    self.report({'ERROR'}, "No valid object available for baking")
                    return {'CANCELLED'}

                for map_type in ordered_requested_map_types:
                    self._activate_map_nodes(materials, map_type)

                    if map_type == 'NORMAL':
                        bpy.ops.object.bake(
                            type='NORMAL',
                            normal_space='TANGENT',
                            use_clear=True,
                            margin=2
                        )
                    else:
                        overrides = []
                        for material in materials:
                            if not material.use_nodes or not material.node_tree:
                                continue
                            override_data = self._setup_emission_override(material, map_type)
                            if override_data:
                                overrides.append(override_data)

                        if not overrides:
                            self.report({'WARNING'}, f"Skipped {self._map_suffix(map_type)}: no valid Principled setup found")
                            self._progress_step(context)
                            continue

                        try:
                            bpy.ops.object.bake(
                                type='EMIT',
                                use_clear=True,
                                margin=2
                            )
                        finally:
                            for override_data in overrides:
                                self._restore_emission_override(override_data)

                    self._progress_step(context)

            finally:
                self._cleanup_temp_bake_object(temp_bake_object)

                if original_engine:
                    context.scene.render.engine = original_engine
                if original_samples is not None and hasattr(context.scene, 'cycles'):
                    context.scene.cycles.samples = original_samples

                bpy.ops.object.select_all(action='DESELECT')
                for obj in original_selected:
                    if obj and obj.name in bpy.data.objects:
                        obj.select_set(True)
                if original_active and original_active.name in bpy.data.objects:
                    context.view_layer.objects.active = original_active

            save_dir, failed_saves = self._save_baked_images(images_by_type)
            if failed_saves:
                self.report({'WARNING'}, f"Some images could not be saved: {', '.join(failed_saves)}")
            self._progress_step(context)

            if getattr(self, 'plug_baked_to_bsdf', False):
                self._connect_baked_maps_to_bsdf(materials, images_by_type)
            self._progress_step(context)

            baked_list = ", ".join([self._map_suffix(m) for m in self._map_order() if m in images_by_type])
            self.report({'INFO'}, f"Bake complete: {baked_list} | Saved to: {save_dir}")
            return {'FINISHED'}
        finally:
            self._progress_end(context)


def register():
    try:
        bpy.utils.unregister_class(smart_bake_textures)
    except RuntimeError:
        pass
    bpy.utils.register_class(smart_bake_textures)


def unregister():
    try:
        bpy.utils.unregister_class(smart_bake_textures)
    except RuntimeError:
        pass
