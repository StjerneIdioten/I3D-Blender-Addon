from __future__ import annotations
from collections import defaultdict
import math
import bpy


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


classes = []


def register(cls):
    classes.append(cls)
    return cls


def is_vehicle_shader(i3d_attributes):
    """Check if the material is a vehicle shader."""
    return (i3d_attributes.shader_name == "vehicleShader" or "vehicleShader" in i3d_attributes.get('source', ''))


def custom_udim_index(u: float, v: float) -> int:
    u_idx = int(math.floor(abs(u)))
    v_idx = int(math.floor(abs(v)))
    if v < 0:
        udim = (abs(v_idx) * 8 + u_idx + 1) * -1
    else:
        udim = v_idx * 8 + u_idx
    return udim


def get_colormat_index_from_udim(neg_udim_index: int) -> int:
    return abs(neg_udim_index) - 1  # -1 => 0, -2 => 1, ..., -8 => 7


@register
class I3D_IO_OT_udim_to_mat_template(bpy.types.Operator):
    bl_idname = "i3dio.udim_to_mat_template"
    bl_label = "UDIM to Material Template"
    bl_description = "Convert UDIM to material template"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mesh_objects = [obj for obj in context.scene.objects if obj.type == 'MESH' and obj.data.uv_layers]
        if not mesh_objects:
            self.report({'ERROR'}, "No mesh objects with UV layers found")
            return {'CANCELLED'}

        # TODO: Implement the conversion logic
        # Need to iterate through each mesh object and convert first UV layer uvs locations to material template (0-49)
        # NOTE: materials can be used by multiple objects, we therefore need to ensure we collect all information
        # for each object for each material.
        # Also keep in mind that -1 on Y axis -> 0 -> 8 on X axis belongs to old "colorMaterials", to correctly extract
        # the material template for these we need the colorMat
        # parameters from the material (first 3 = color and last is the material (0-49))
        # When we have retrived all the information, we will create/assign new correct materials to respective triangles
        # Would also be nice to move all UVs back into 0-1 range of the "first" "udim" tile, since in the FS25 shader
        # "wetness" will only be applied for meshes from Y 0 and above
        # (which means old colorMats won't have wetness without doing this)"

        # First we need to gather all faces per (material, target_index)
        mat_face_map = defaultdict(lambda: defaultdict(list))
        for obj in mesh_objects:
            mesh = obj.data
            uv_layer = mesh.uv_layers[0]  # UDIM is always in the first UV layer
            for mat_slot_idx, mat in enumerate(mesh.materials):
                if mat is None or not is_vehicle_shader(mat.i3d_attributes) \
                        or mat.i3d_attributes.shader_game_version == '25':
                    continue  # Skip non-vehicleShader materials and those with game version 25
                for poly in mesh.polygons:
                    if poly.material_index != mat_slot_idx:
                        continue  # Only process polygons with the current material
                    # Find all UDIMs touched by this face
                    udim_indices = set()
                    for loop_index in poly.loop_indices:
                        u, v = uv_layer.data[loop_index].uv
                        u_idx = int(math.floor(u))
                        v_idx = int(math.floor(v))
                        udim_index = v_idx * 8 + u_idx
                        udim_indices.add(udim_index)
                    for udim in udim_indices:
                        if udim < 0:
                            colormat_slot = get_colormat_index_from_udim(udim)
                            param_name = f"colorMat{colormat_slot}"
                            shader_params = mat.i3d_attributes.get('shader_parameters', {})
                            color_mat_vec = None
                            for param in shader_params:
                                if param.get("name") == param_name:
                                    color_mat_vec = param.get("data_float_4", None)
                                    break
                            if color_mat_vec and len(color_mat_vec) == 4:
                                template_idx = int(color_mat_vec[3])  # The last value is the udim/template index
                                mat_face_map[(mat, f"colorMat{colormat_slot}", template_idx)][obj].append(
                                    (poly.index, list(poly.loop_indices)))
                    else:
                        mat_face_map[(mat, None, udim)][obj].append((poly.index, list(poly.loop_indices)))

        print(f"Found {len(mat_face_map)} materials with UDIMs")
        print(f"UDIM map: {mat_face_map}")

        new_material_lookup = dict()  # key: mat, param, idx) -> new_mat
        for (old_mat, param, idx), obj_dict in mat_face_map.items():
            key = (old_mat, param, idx)
            if key in new_material_lookup:
                continue  # Already processed this material 
            template_info = UDIM_TO_MAT_TEMPLATE.get(idx)
            new_mat = old_mat.copy()
            if template_info:
                new_mat.name = f"{template_info[0]}_{old_mat.name}"
            else:
                new_mat.name = f"UnknownTemplate_{old_mat.name}"

            new_material_lookup[key] = new_mat

        print(f"Created {len(new_material_lookup)} new materials")
        print(f"New material lookup: {new_material_lookup}")

        self.report({'INFO'}, "UDIM converted to material template")
        return {'FINISHED'}


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _register()


def unregister():
    _unregister()
