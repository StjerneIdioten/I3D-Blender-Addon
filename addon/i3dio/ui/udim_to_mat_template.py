from __future__ import annotations
from collections import defaultdict
import math
import re
import bpy

from .material_templates import get_template_by_name, apply_template_to_material, brand_name_from_color
from .shader_migration_utils import migrate_variation, migrate_and_apply_parameters, migrate_material_textures

# UDIM tile index to material template mapping.
# key[1] = colorMask variations with colorMatN
# key[0] = template name for the rest of the UDIMs
UDIM_TO_MAT_TEMPLATE = {
    0: ('metalPaintedGray', 'metalPainted'),
    1: ('plasticPaintedBlack', 'plasticPainted'),
    2: ('chrome', 'chrome'),
    3: ('copperScratched', 'copperScratched'),
    4: ('metalGalvanized', 'metalGalvanized'),
    5: ('rubberBlack', 'rubber'),
    6: ('metalPaintedOldGray', 'metalPaintedOld'),
    7: ('fabric1Bluish', 'fabric1'),
    8: ('silverScratched', 'silverScratched'),
    9: ('silverBumpy', 'silverBumpy'),
    10: ('fabric2Gray', 'fabric2'),
    11: ('fabric3Gray', 'fabric3'),
    12: ('leather1Brown', 'leather1'),
    13: ('leather2Brown', 'leather2'),
    14: ('wood1Cedar', 'wood1'),
    15: ('dirt', 'dirt'),
    16: ('metalPaintedBlack', 'metalPainted'),
    17: ('plasticPainted', 'plasticPainted'),
    18: ('silverRough', 'silverRough'),
    19: ('brassScratched', 'brassScratched'),
    20: ('reflectorWhite', 'reflectorWhite'),
    21: ('reflectorRed', 'reflectorWhite'),
    22: ('reflectorOrange', 'reflectorWhite'),
    23: ('reflectorOrangeDaylight', 'reflectorWhiteDaylight'),
    24: ('plasticGearShiftGrayDark', 'plasticGearShift'),
    25: ('leather3GrayDark', 'leather3'),
    26: ('perforatedSynthetic1Black', 'perforatedSynthetic1'),
    27: ('glassClear01', 'glassClear01'),
    28: ('glassSquare01', 'glassSquare01'),
    29: ('glassLine01', 'glassLine01'),
    30: ('palladiumScratched', 'palladiumScratched'),
    31: ('bronzeScratched', 'bronzeScratched'),
    32: ('metalPaintedGraphiteBlack', 'metalPaintedGraphite'),
    33: ('halfMetalNoise1Black', 'halfMetalNoise1'),
    34: ('plasticPaintedShinyGray', 'plasticPaintedShinyGray'),
    35: ('goldScratched', 'goldScratched'),
    36: ('metalPaintedRoughGray', 'metalPaintedRough'),
    37: ('perforatedSynthetic2Black', 'perforatedSynthetic2'),
    38: ('fellGray', 'fell'),
    39: ('steelTreadPlate', 'steelTreadPlate'),
    40: ('calibratedGlossPaint', 'calibratedGlossPaint'),
    41: ('fabric4Beige', 'fabric4'),
    42: ('wood2Oak', 'wood2'),
    43: ('silverScratchedShiny', 'silverScratchedShiny'),
    44: ('reflectorYellow', 'reflectorWhite'),
    45: ('silverCircularBrushed', 'silverCircularBrushed'),
    46: ('fabric5Dark', 'fabric5'),
    47: ('calibratedPaint', 'calibratedPaint'),
    48: ('calibratedMetallic', 'calibratedMetallic'),
    49: ('fabric6Bluish', 'fabric6'),
}

classes = []


def register(cls):
    classes.append(cls)
    return cls


def is_vehicle_shader(i3d_attributes):
    """Check if the material is a vehicle shader."""
    # Modern and legacy property checks (old files stored the entire shader path in 'source')
    return (i3d_attributes.shader_name == "vehicleShader" or "vehicleShader" in i3d_attributes.get('source', ''))


def custom_udim_index(u: float, v: float, udim_tiles_x: int = 8) -> int:
    """
    Calculates the UDIM tile index for given UV coordinates, supporting negative Y ("colorMat" row).
    - For positive Y: standard UDIM index (v * tiles_x + u).
    - For negative Y: only the first row below (v < 0), returns negative indices.
    """
    u_idx = int(math.floor(abs(u)))
    v_idx = int(math.floor(abs(v)))
    if v < 0:
        udim = (abs(v_idx) * udim_tiles_x + u_idx + 1) * -1
    else:
        udim = v_idx * udim_tiles_x + u_idx
    return udim


def get_poly_udim_by_center(poly: bpy.types.MeshPolygon, uv_layer: bpy.types.MeshUVLoopLayer) -> int:
    """
    Returns the UDIM tile index for a face based on the average (center) of its UVs.
    Prevents border/corner faces from being split across multiple tiles.
    """
    u_total, v_total = 0.0, 0.0
    for loop_index in poly.loop_indices:
        u, v = uv_layer.data[loop_index].uv
        u_total += u
        v_total += v
    n = len(poly.loop_indices)
    u_avg, v_avg = u_total / n, v_total / n
    return custom_udim_index(u_avg, v_avg)


def remove_mat_suffix(name: str) -> str:
    """
    Removes the '_mat' suffix from a material name, if present.
    This is used to clean up material names before applying templates.
    """
    return re.sub(r'(_mat|\.mat)$', '', name, flags=re.IGNORECASE)


def strip_texture_suffix(name: str) -> str:
    return re.sub(r'_(diffuse|normal|specular|vmask|alpha|height)\.dds$', '', name, flags=re.IGNORECASE)


def main_texture_name(mat: bpy.types.Material) -> str:
    """
    Returns the name from the first texture node in the material's node tree,
    or the material's name if no texture node is found.
    """
    texture_node = next((node for node in mat.node_tree.nodes if node.type == 'TEX_IMAGE'), None)
    if texture_node and texture_node.image:
        return strip_texture_suffix(texture_node.image.name)
    return remove_mat_suffix(mat.name)


@register
class I3D_IO_OT_udim_to_mat_template(bpy.types.Operator):
    bl_idname = "i3dio.udim_to_mat_template"
    bl_label = "UDIM to Material Template"
    bl_description = "Convert UDIM to material template"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, _context):
        """
        Converts legacy FS19/22 UDIM-based vehicleShader materials to FS25 material templates.
        - For each mesh and material, assign triangles to a new material based on their UDIM tile.
        - Faces in negative Y UDIMs (Y = -1) are handled as colorable materials ("colorMat" row).
          For these, the real target template is taken from the A-channel of the appropriate
          colorMatN parameter (colorMat0..7) in shader_parameters.
        - All faces are remapped to use a single template/material per UDIM/colorMat index.
        - Optionally, remap UVs into 0-1 space within first tile (for FS25 wetness support).
        - Dlete old materials after conversion (if they have no users).
        """
        mesh_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH' and len(obj.data.uv_layers)]
        if not mesh_objects:
            self.report({'ERROR'}, "No mesh objects with UV layers found")
            return {'CANCELLED'}

        # NOTE: While FS19/22 had a "strict rule" to only have one material per mesh.
        # We cannot guarantee that, so loop over everthing.

        # Gather all faces per (material, target_index)
        # key: (material, param name or None, template idx) → value: {obj: [ (poly.index, loop_indices), ... ]}

        new_material_work_orders = defaultdict(lambda: {'objects': defaultdict(list), 'color': None})
        for obj in mesh_objects:
            mesh = obj.data
            uv_layer = mesh.uv_layers[0]  # UDIM is always in the first UV layer
            for mat_slot_idx, mat in enumerate(mesh.materials):
                if mat is None or not is_vehicle_shader(mat.i3d_attributes):
                    continue  # Skip non-vehicleShader materials

                i3d_attrs = mat.i3d_attributes
                if i3d_attrs.shader_game_version == '25':
                    continue  # Already migrated to FS25

                for poly in mesh.polygons:
                    if poly.material_index != mat_slot_idx:
                        continue  # Only process polygons with the current material
                    # Use the average UV center to determine the tile index
                    udim = get_poly_udim_by_center(poly, uv_layer)
                    key = (mat, udim)
                    work_order = new_material_work_orders[key]
                    work_order['objects'][obj].append((poly.index, list(poly.loop_indices)))

                    if udim < 0:  # If it's a colorable material, find and store its color.
                        colormat_slot = abs(udim) - 1  # Negative UDIM index to colorMat tile: -1→0, -2→1, ..., -8→7
                        param_name = f"colorMat{colormat_slot}"
                        work_order['param_name'] = param_name

                        if 'source' in i3d_attrs:
                            # Legacy shader system, with old FS19/22 shader
                            shader_params_list = i3d_attrs.get('shader_parameters', [])
                            param_data = next((p for p in shader_params_list if p.get("name") == param_name), None)
                            if param_data:
                                color_mat_vec = param_data.get("data_float_4")
                        else:
                            # New shader system, with old FS19/22 shader
                            if param_name in i3d_attrs.shader_material_params:
                                color_mat_vec = i3d_attrs.shader_material_params[param_name]

                        if color_mat_vec and len(color_mat_vec) == 4:
                            work_order['color'] = color_mat_vec[:3]
                            work_order['template_idx_from_alpha'] = int(color_mat_vec[3])
                        else:
                            # The colorMat data was missing. Assign a default template index.
                            print(f"WARNING: {param_name!r} data not found for material {mat.name!r}.")
                            work_order['template_idx_from_alpha'] = 0  # Default to UDIM 0 (metalPainted)
                            work_order['color'] = None  # Color will be taken from the template

        print(f"Found {len(new_material_work_orders)} materials with UDIMs")

        # Create a new material for each unique (mat, param, idx) combo (reuse if possible)
        for (old_mat, udim), work_order in new_material_work_orders.items():
            key = (old_mat, udim)

            from_alpha = "template_idx_from_alpha" in work_order
            template_idx = work_order.get('template_idx_from_alpha', udim)

            template_info = UDIM_TO_MAT_TEMPLATE.get(template_idx)
            template_name = \
                template_info[1 if from_alpha else 0] if template_info else f"unknownTemplate_{template_idx}"

            brand_name = brand_name_from_color(work_order['color']) if work_order['color'] else None
            name_from_texture_node = main_texture_name(old_mat)

            name_parts = [name_from_texture_node, template_name]
            if brand_name:
                name_parts.append(brand_name)
            elif param_name := work_order.get('param_name'):
                name_parts.append(param_name)  # Ensures uniqueness if no brand name
            final_name = "_".join(name_parts) + "_mat"

            # Create a full copy of the old material
            # This is necessary to preserve node tree, textures and all other properties that user might have set
            new_mat = old_mat.copy()
            new_mat.name = final_name
            old_i3d_attrs = old_mat.i3d_attributes
            new_i3d_attrs = new_mat.i3d_attributes
            params = new_i3d_attrs.shader_material_params
            textures = new_i3d_attrs.shader_material_textures

            # Set shader and variation first to ensure material properties is "initialized" correctly
            new_i3d_attrs.shader_name = ""  # Reset to empty string to avoid potential issues with old shader names
            new_i3d_attrs.shader_name = 'vehicleShader'
            old_variation_name = (old_i3d_attrs.get('temp_old_variation_name') or old_i3d_attrs.shader_variation_name)
            migrate_variation(new_i3d_attrs, old_variation_name, True)

            base_template = get_template_by_name(template_name)
            brand_template = get_template_by_name(brand_name) if brand_name else None

            if brand_template:
                # Check if brand template has a parent template
                if getattr(brand_template, 'parentTemplate', None):
                    # Use the parent template to create the material
                    apply_template_to_material(params, textures, brand_template)
                else:
                    # The brand template have no parent
                    # Apply the base UDIM template first, then the brand template on top
                    if base_template:
                        apply_template_to_material(params, textures, base_template)
                    apply_template_to_material(params, textures, brand_template)
            elif base_template:
                # No brand was found, apply the base UDIM template
                apply_template_to_material(params, textures, base_template)
            else:
                print(f"WARNING: No base or brand template found for {template_name!r} or {brand_name!r}.")

            migrate_and_apply_parameters(new_i3d_attrs, old_i3d_attrs)
            migrate_material_textures(new_i3d_attrs, old_i3d_attrs)

            if work_order['color']:
                if 'colorScale' in new_i3d_attrs.shader_material_params:
                    new_i3d_attrs.shader_material_params['colorScale'] = work_order['color']
                else:
                    print(f"WARNING: Could not find 'colorScale' on '{new_mat.name}' to apply color.")

            legacy_keys = ['source', 'variation', 'variations', 'shader_parameters', 'shader_textures']
            for key in legacy_keys:
                if key in new_i3d_attrs:
                    del new_i3d_attrs[key]

            work_order['new_material'] = new_mat
            # new_material_lookup[key] = new_mat

        print("Finished creating materials.")

        affected_objects: set[bpy.types.Object] = set()
        processed_old_mats: set[bpy.types.Material] = set()
        for (old_mat, udim), work_order in new_material_work_orders.items():
            processed_old_mats.add(old_mat)
            for obj in work_order['objects']:
                affected_objects.add(obj)

        print(f"Updating {len(affected_objects)} affected objects...")

        # Update mesh material slots and poly assignments
        for obj in affected_objects:
            mesh = obj.data
            uv_layer = mesh.uv_layers[0]  # Needed for UV remapping later (to tile 0-1 space)

            # Build a map of which polygon needs to be assigned to which new material for THIS object
            poly_to_new_mat_map: dict[int, bpy.types.Material] = {}
            for (old_mat, udim), work_order in new_material_work_orders.items():
                if obj in work_order['objects']:
                    new_mat = work_order['new_material']
                    for poly_idx, _loop_indices in work_order['objects'][obj]:
                        poly_to_new_mat_map[poly_idx] = new_mat

            # Non-destructively add new materials to slots and get their indices
            needed_new_mats = set(poly_to_new_mat_map.values())
            new_mat_to_slot_idx = {}
            for new_mat in needed_new_mats:
                slot_idx = mesh.materials.find(new_mat.name)
                if slot_idx == -1:
                    mesh.materials.append(new_mat)
                    slot_idx = len(mesh.materials) - 1
                new_mat_to_slot_idx[new_mat] = slot_idx

            print(f"Assigned {len(new_mat_to_slot_idx)} new materials to slots in {obj.name}")

            # Re-assign all relevant polygons to their new material slots
            for poly_idx, new_mat in poly_to_new_mat_map.items():
                mesh.polygons[poly_idx].material_index = new_mat_to_slot_idx[new_mat]

            used_slot_indices = {p.material_index for p in mesh.polygons}

            # Iterate backwards when removing to avoid index issues
            for i in range(len(mesh.materials) - 1, -1, -1):
                if i not in used_slot_indices:
                    mesh.materials.pop(index=i)

        print("Finished assigning materials to polygons.")

        print("Unused material cleanup")
        for old_mat in processed_old_mats:
            if 'temp_old_variation_name' in old_mat.i3d_attributes:
                del old_mat.i3d_attributes['temp_old_variation_name']
            if old_mat.users == 0:
                print(f"Removing unused old material data-block: {old_mat.name}")
                bpy.data.materials.remove(old_mat)

        self.report({'INFO'}, "UDIM converted to material template")
        return {'FINISHED'}


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _register()


def unregister():
    _unregister()
