from __future__ import annotations
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


old_to_new_variations = {
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


old_to_new_parameters = {
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

old_to_new_custom_textures = {'mTrackArray': 'trackArray'}


classes = []


def register(cls):
    classes.append(cls)
    return cls


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
        new_materials = {}
        for obj in mesh_objects:
            mesh = obj.data
            uv_layer = mesh.uv_layers[0]  # UDIM is always in the first UV layer
            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    u_floor = math.floor(abs(uv_layer.data[loop_index].uv.x))
                    v_floor = math.floor(abs(uv_layer.data[loop_index].uv.y))
                    v = uv_layer[loop_index].uv.y
                    udim_index = (abs(v_floor) * 8 + u_floor + (1 if v < 0 else 0)) * (-1 if v < 0 else 1)
            pass

        self.report({'INFO'}, "UDIM converted to material template")
        return {'FINISHED'}


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _register()


def unregister():
    _unregister()
