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
DEBUG = True


def _print(message: str) -> None:
    if DEBUG:
        print(message)


def migrate_variation(i3d_attrs, old_variation_name: str, is_incompatible_vehicle_shader: bool) -> None:
    """Migrates the variation name and assigns it to the new property."""
    if not old_variation_name:
        return
    new_variation = old_variation_name
    if is_incompatible_vehicle_shader:
        # For all vehicleShader variations that is not part of colorMask, we can safely convert with this check
        new_variation = OLD_TO_NEW_VARIATIONS.get(old_variation_name, old_variation_name)

    if new_variation in i3d_attrs.shader_variations:
        i3d_attrs.shader_variation_name = new_variation
    else:
        _print(f"[Migration] Variation '{new_variation}' not found for shader '{i3d_attrs.shader_name}'.")


def migrate_and_apply_parameters(new_mat_attrs, old_mat_attrs) -> None:
    """
    Migrates all user-defined parameters from an old material to a new one.
    - Handles "old-old" legacy data from 'shader_parameters' (list of dicts).
    - Handles "new-old" legacy data from 'shader_material_params' (collection).
    - Translates old parameter names to new ones using OLD_TO_NEW_PARAMETERS.
    """
    new_params_collection = new_mat_attrs.shader_material_params
    params_to_migrate = {}

    # Gather all parameters to migrate
    if 'shader_parameters' in old_mat_attrs:
        # "Old-Old" Legacy (from the list of dicts)
        for old_param in old_mat_attrs.get('shader_parameters', []):
            if name := old_param.get('name'):
                value = next((old_param.get(k) for k in ('data_float_4', 'data_float_3', 'data_float_2', 'data_float_1')
                              if k in old_param), None)
                if value is not None:
                    if isinstance(value, (float, int)):
                        value = [float(value)]
                    elif isinstance(value, (list, tuple)):
                        value = [float(v) for v in value]
                    params_to_migrate[name] = value

    elif 'shader_material_params' in old_mat_attrs:
        # Iterate over the keys (the parameter names) of the collection.
        for param_name in old_mat_attrs.shader_material_params.keys():
            param_value = old_mat_attrs.shader_material_params[param_name]
            params_to_migrate[param_name] = param_value

    if not params_to_migrate:
        return  # No parameters to migrate

    for old_name, old_value in params_to_migrate.items():
        new_name = OLD_TO_NEW_PARAMETERS.get(old_name, old_name)
        if new_name in new_params_collection:
            try:
                target_param = new_params_collection[new_name]
                expected_length = len(target_param)
                value_to_assign = list(old_value)
                sliced_value = value_to_assign[:expected_length]
                print(f"[Migration] Migrating '{old_name}' -> '{new_name}'. "
                      f"Original value: {value_to_assign} (len {len(value_to_assign)}), "
                      f"Target length: {expected_length}, "
                      f"Assigned: {sliced_value}")
                new_params_collection[new_name] = sliced_value
            except (TypeError, ValueError, KeyError, AttributeError) as e:
                _print(f"[Migration] Could not apply param '{old_name}' as '{new_name}': {e}")


def migrate_material_parameters(target_attrs, source_attrs=None) -> None:
    """
    Migrates parameters from the legacy 'shader_parameters' collection
    to the new 'shader_material_params' collection.
    This function also cleans up the old collection.
    """
    if source_attrs is None:
        source_attrs = target_attrs
    if not (old_params := source_attrs.get('shader_parameters')):
        return
    new_params_collection = target_attrs.shader_material_params
    for old_param in old_params:
        if (old_name := old_param.get('name')) is None:
            continue
        if (new_name := OLD_TO_NEW_PARAMETERS.get(old_name, old_name)) not in new_params_collection:
            continue

        value = None
        for key, length in {'data_float_1': 1, 'data_float_2': 2, 'data_float_3': 3, 'data_float_4': 4}.items():
            if key in old_param:
                data = old_param[key]
                if isinstance(data, (float, int)):
                    value = [float(data)]
                else:
                    value = [float(v) for v in data]
                value = (value + [0.0] * length)[:length]
                break
        if value is None:
            continue
        try:
            target_param = new_params_collection[new_name]
            expected_length = len(target_param)
            value_to_assign = list(value)
            sliced_value = value_to_assign[:expected_length]
            new_params_collection[new_name] = sliced_value
        except (TypeError, ValueError, KeyError) as e:
            _print(f"[Migration] Could not set param '{new_name}': {e}")
    # Always remove the old collection after migration to prevent leftover legacy data.
    if 'shader_parameters' in target_attrs:
        del target_attrs['shader_parameters']


def migrate_material_textures(target_attrs, source_attrs=None) -> None:
    """
    Migrates textures from the legacy 'shader_textures' collection
    to the new 'shader_material_textures' collection.
    This function also cleans up the old collection.
    """
    if source_attrs is None:
        source_attrs = target_attrs
    if not (old_textures := source_attrs.get('shader_textures')):
        return
    new_textures_collection = target_attrs.get('shader_material_textures')
    for old_tex in old_textures:
        if (old_name := old_tex.get('name')) is None:
            continue
        new_name = OLD_TO_NEW_CUSTOM_TEXTURES.get(old_name, old_name)
        target_tex_slot = next((t for t in new_textures_collection if t.name == new_name), None)
        if target_tex_slot:
            old_source_path = old_tex.get('source', '')
            # Only overwrite if the user had set a custom path
            if old_source_path and old_source_path != target_tex_slot.default_source:
                target_tex_slot.source = old_source_path
    # Always remove the old collection after migration to prevent leftover legacy data.
    if 'shader_textures' in target_attrs:
        del target_attrs['shader_textures']
