from __future__ import annotations
from collections import defaultdict
import math
import re
import bpy

from .material_templates import get_template_by_name, template_to_material, get_brand_mat_name_from_color

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
    34: ('plasticPaintedShinyGray', 'plasticPaintedShiny'),
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

OLD_TO_NEW_VARIATIONS = {
    'secondUV_colorMask': 'vmaskUV2',
    'secondUV': 'vmaskUV2',
    'Decal': 'vmaskUV2',
    'Decal_colorMask': 'vmaskUV2',
    'Decal_normalThirdUV': 'vmaskUV2_normalUV3',
    'Decal_normalThirdUV_colorMask': 'vmaskUV2_normalUV3',
    'uvScroll': 'uvTransform',
    'uvScroll_colorMask': 'uvTransform',
    'uvRotate': 'uvTransform',
    'uvRotate_colorMask': 'uvTransform',
    'uvScale': 'uvTransform',
    'uvScale_colorMask': 'uvTransform',
    'Decal_uvScroll': 'uvTransform_vmaskUV2',
    'tirePressureDeformation': 'tirePressureDeformation',
    'tirePressureDeformation_secondUV': 'tirePressureDeformation_vmaskUV2',
    'motionPathRubber': 'motionPathRubber',
    'motionPathRubber_secondUV_colorMask': 'motionPathRubber_vmaskUV2',
    'motionPath': 'motionPath',
    'motionPath_secondUV_colorMask': 'motionPath_vmaskUV2',
    'vtxRotate_colorMask': 'vtxRotate',
    'vtxRotate': 'vtxRotate',
    'meshScroll': 'meshScroll',
    'meshScroll_colorMask': 'meshScroll',
    'rim': 'rim',
    'rim_colorMask': 'rim',
    'rim_numberOfStatics_colorMask': 'rim_numberOfStatics',
    'rimDual_colorMask': 'rimDual_numberOfStatics',
    'hubDual_colorMask': 'hubDual',
    'windBend': 'windBend',
    'windBend_colorMask': 'windBend',
    'windBend_colorMask_vtxColor': 'windBend_vtxColor',
    'windBend_vtxColor_Decal': 'windBend_vtxColor_vmaskUV2',
    'windBend_vtxColor_Decal_colorMask': 'windBend_vtxColor_vmaskUV2',
    'shaking_colorMask': 'shaking',
    'shaking_colorMask_Decal': 'shaking_vmaskUV2',
    'jiggling_colorMask': 'jiggling',
    'cableTrayChain_colorMask': 'cableTrayChain',
    'localCatmullRom': 'localCatmullRom_uvTransform',
    'localCatmullRom_colorMask': 'localCatmullRom_uvTransform',
    'localCatmullRom_colorMask_uvScale': 'localCatmullRom_uvTransform',
    'reflector_colorMask': 'reflector',
    'backLight_colorMask': 'backLight',
}

OLD_TO_NEW_PARAMETERS = {
    'morphPosition': 'morphPos',
    'scrollPosition': 'scrollPos',
    'blinkOffset': 'blinkMulti',
    'offsetUV': 'offsetUV',
    'uvCenterSize': 'uvCenterSize',
    'uvScale': 'uvScale',
    'lengthAndRadius': 'lengthAndRadius',
    'widthAndDiam': 'widthAndDiam',
    'connectorPos': 'connectorPos',
    'numberOfStatics': 'numberOfStatics',
    'connectorPosAndScale': 'connectorPosAndScale',
    'lengthAndDiameter': 'lengthAndDiameter',
    'backLightScale': 'backLightScale',
    'amplFreq': 'amplFreq',
    'shaking': 'shaking',
    'rotationAngle': 'rotationAngle',
    'directionBend': 'directionBend',
    'controlPointAndLength': 'controlPointAndLength',
}

OLD_TO_NEW_CUSTOM_TEXTURES = {'mTrackArray': 'trackArray'}
COLOR_MASK_VARIATIONS = ("colormask", "staticlight", "tirepressuredeformation")


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


def get_name_from_texture_node(mat: bpy.types.Material) -> str:
    """
    Extracts the name from the first texture node in the material's node tree.
    If no texture nodes are found, returns the material's name.
    """
    texture_node = next((node for node in mat.node_tree.nodes if node.type == 'TEX_IMAGE'), None)
    if texture_node and texture_node.image:
        # If the texture node has an image, use its name
        return strip_texture_suffix(texture_node.image.name)
    return remove_mat_suffix(mat.name)


@register
class I3D_IO_OT_udim_to_mat_template(bpy.types.Operator):
    bl_idname = "i3dio.udim_to_mat_template"
    bl_label = "UDIM to Material Template"
    bl_description = "Convert UDIM to material template"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        """
        Converts legacy FS19/22 UDIM-based vehicleShader materials to FS25 material templates.
        - For each mesh and material, assign triangles to a new material based on their UDIM tile.
        - Faces in negative Y UDIMs (Y = -1) are handled as colorable materials ("colorMat" row).
          For these, the real target template is taken from the A-channel of the appropriate
          colorMatN parameter (colorMat0..7) in shader_parameters.
        - All faces are remapped to use a single template/material per UDIM/colorMat index.
        - Optionally, remap UVs into 0-1 space within first tile (for FS25 wetness support).
        - Optionally, delete old materials after conversion (if they have no users).
        """
        # NOTE: should we run on scene objects or all data objects?
        mesh_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.data.uv_layers]
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
                if mat is None or not is_vehicle_shader(mat.i3d_attributes) \
                        or mat.i3d_attributes.shader_game_version == '25':
                    continue  # Skip non-vehicleShader materials and those already migrated
                for poly in mesh.polygons:
                    if poly.material_index != mat_slot_idx:
                        continue  # Only process polygons with the current material
                    # Use the average UV center to determine the tile index
                    udim = get_poly_udim_by_center(poly, uv_layer)

                    key = (mat, udim)
                    work_order = new_material_work_orders[key]
                    work_order['objects'][obj].append((poly.index, list(poly.loop_indices)))

                    if udim < 0:  # If it's a colorable material, find and store its color now.
                        colormat_slot = abs(udim) - 1  # Negative UDIM index to colorMat tile: -1→0, -2→1, ..., -8→7
                        param_name = f"colorMat{colormat_slot}"
                        shader_params = mat.i3d_attributes.get('shader_parameters', {})

                        if (color_mat_vec := next((p.get("data_float_4") for p in shader_params
                                                   if p.get("name") == param_name), None)):
                            work_order['color'] = color_mat_vec[:3]
                            work_order['template_idx_from_alpha'] = int(color_mat_vec[3])

        print(f"Found {len(new_material_work_orders)} materials with UDIMs")

        # Create a new material for each unique (mat, param, idx) combo (reuse if possible)
        new_material_lookup = dict()  # key: mat, param, idx) -> new_mat
        for (old_mat, udim), work_order in new_material_work_orders.items():
            key = (old_mat, udim)

            template_idx = work_order.get('template_idx_from_alpha', udim)

            template_info = UDIM_TO_MAT_TEMPLATE.get(template_idx)
            template_name = template_info[1] if template_info else f"unknownTemplate_{template_idx}"
            brand_name = None
            if work_order['color']:
                brand_name = get_brand_mat_name_from_color(work_order['color'])

            name_from_texture_node = get_name_from_texture_node(old_mat)
            name_parts = [name_from_texture_node]
            if brand_name:
                name_parts.append(brand_name)
            name_parts.append(template_name)
            final_name = "_".join(name_parts) + "_mat"

            # Create a full copy of the old material
            # This is necessary to preserve node tree, textures and all other properties that user might have set
            new_mat = old_mat.copy()
            new_mat.name = final_name
            i3d_attrs = new_mat.i3d_attributes
            i3d_attrs.shader_name = 'vehicleShader'

            old_variation_name = old_mat.i3d_attributes.get('temp_old_variation_name', '')
            if old_variation_name:
                new_variation = OLD_TO_NEW_VARIATIONS.get(old_variation_name, old_variation_name)
                if new_variation in i3d_attrs.shader_variations:
                    i3d_attrs.shader_variation_name = new_variation

            target_template_name_for_lookup = f"{brand_name}_{template_name}" if brand_name else template_name
            if template := get_template_by_name(target_template_name_for_lookup) or get_template_by_name(template_name):
                template_to_material(i3d_attrs.shader_material_params, i3d_attrs.shader_material_textures, template)
            else:
                print(f"WARNING: No template found for '{target_template_name_for_lookup}' or '{template_name}'.")

            if work_order['color']:
                if 'colorScale' in i3d_attrs.shader_material_params:
                    i3d_attrs.shader_material_params['colorScale'] = work_order['color']
                else:
                    print(f"WARNING: Could not find 'colorScale' on '{new_mat.name}' to apply color.")

            new_material_lookup[key] = new_mat

        print(f"Created {len(new_material_lookup)} new materials")
        print(f"New material lookup: {new_material_lookup}")

        # Update mesh material slots and poly assignments
        for obj in mesh_objects:
            # Only process objects that actually have faces to update
            relevant_keys = [key for key in new_material_work_orders if obj in new_material_work_orders[key]]
            if not relevant_keys:
                continue  # Skip objects with no faces to update
            mesh = obj.data
            uv_layer = mesh.uv_layers[0]
            new_slots = []
            old_to_new_slot = {}
            # Iterate over all faces relevant to this object
            for (old_mat, udim), work_order in new_material_work_orders.items():
                if obj not in work_order['objects']:
                    continue
                new_mat = new_material_lookup[(old_mat, udim)]
                if new_mat not in new_slots:
                    new_slots.append(new_mat)
                old_to_new_slot[(old_mat, udim)] = new_slots.index(new_mat)
            # Clear existing materials
            mesh.materials.clear()
            # Assign new materials to the mesh
            for mat in new_slots:
                mesh.materials.append(mat)

            # Assign polygons and remap UVs
            for (old_mat, udim), work_order in new_material_work_orders.items():
                if obj not in work_order['objects']:
                    continue
                slot_idx = old_to_new_slot[(old_mat, udim)]
                for poly_idx, _loop_indices in work_order['objects'][obj]:
                    poly = mesh.polygons[poly_idx]
                    poly.material_index = slot_idx

        self.report({'INFO'}, "UDIM converted to material template")
        return {'FINISHED'}


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _register()


def unregister():
    _unregister()
