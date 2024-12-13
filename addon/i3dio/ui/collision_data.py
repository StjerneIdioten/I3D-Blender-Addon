import bpy
from .. import xml_i3d
from pathlib import Path
from bpy.app.handlers import (persistent, load_post)
from collections import namedtuple


COLLISIONS = {
    'flags': {},  # {name: bit}
    'presets': {},  # {name: CollisionPreset}
    'rules': []  # List[CollisionRule]
}

COLLISIONS_ENUM_LIST_DEFAULT = ('NONE', 'No Preset', 'No Collision preset set')
COLLISIONS_ENUM_LIST = [COLLISIONS_ENUM_LIST_DEFAULT]

CollisionPreset = namedtuple('CollisionPreset', ['name', 'group', 'group_hex', 'mask', 'mask_hex', 'desc'])
CollisionOutput = namedtuple('CollisionOutput', ['preset', 'group', 'mask', 'without_flags', 'is_trigger'])
CollisionRule = namedtuple('CollisionRule', ['mask_old', 'outputs'])


def compute_bitmask(flags, flag_dict):
    return sum(1 << flag_dict[flag] for flag in flags if flag in flag_dict)


def parse_collision_mask_flags(filepath) -> None:
    """Parse collisionMaskFlags.xml to populate flags and presets."""
    global COLLISIONS

    tree = xml_i3d.parse(filepath)
    if tree is None:
        print(f"Failed to parse {filepath}")
        return None

    root = tree.getroot()

    # Parse flags
    COLLISIONS['flags'] = {flag.get('name'): int(flag.get('bit')) for flag in root.findall('./flag')}

    # Parse presets
    for preset in root.findall('./preset'):
        name = preset.get('name')
        group_flags = [flag.get('name') for flag in preset.findall('./group/flag')]
        desc = preset.get('desc')

        # Compute the group hex
        group_hex = f"{compute_bitmask(group_flags, COLLISIONS['flags']):x}"

        # Handle the <mask> element
        mask_value = 0
        mask_element = preset.find('./mask')
        if mask_element is not None:
            # Some mask elements have a direct value attribute
            direct_value = mask_element.get('value')
            if direct_value is not None:
                try:
                    mask_value = int(direct_value, 16)
                except ValueError:
                    print(f"Invalid mask value '{direct_value}' in preset '{name}'")
                    continue
            else:
                # If no single value attribute, compute the bitmask from the flags
                mask_value = compute_bitmask([flag.get('name') for flag in
                                              mask_element.findall('./flag')], COLLISIONS['flags'])

        mask_hex = f"{mask_value:x}"
        COLLISIONS['presets'][name] = CollisionPreset(name, group_flags, group_hex, mask_value, mask_hex, desc)


def parse_collision_mask_rules(filepath) -> None:
    """Parse collisionMaskConversionRules.xml to populate conversion rules."""
    global COLLISIONS

    tree = xml_i3d.parse(filepath)
    if tree is None:
        print(f"Failed to parse {filepath}")
        return None

    root = tree.getroot()

    for rule in root.findall('./conversionRules/rule'):
        mask_old = int(rule.get('maskOld'))
        outputs = []

        for output in rule.findall('./output'):
            preset = output.get('preset')
            is_trigger = output.get('isTrigger', 'false').lower() == 'true'
            group_flags = [flag.get('name') for flag in output.findall('./group/flag')]

            # Check for a value in the mask element
            mask_element = output.find('./mask')
            mask_value = mask_element.get('value') if mask_element is not None else None
            if mask_value is not None:
                try:
                    mask_flags = int(mask_value, 16)
                except ValueError:
                    print(f"Invalid mask value '{mask_value}' in rule for maskOld '{mask_old}'")
                    mask_flags = 0
            else:
                # Parse individual flag names
                mask_flags = [flag.get('name') for flag in output.findall('./mask/flag')]

            without_flags = [flag.get('name') for flag in output.findall('./mask/withoutFlag')]

            outputs.append(CollisionOutput(preset, group_flags, mask_flags, without_flags, is_trigger))

        COLLISIONS['rules'].append(CollisionRule(mask_old, outputs))


def populate_collision_enum_list() -> None:
    """Populate COLLISIONS_ENUM_LIST with collision presets."""
    global COLLISIONS, COLLISIONS_ENUM_LIST

    if not COLLISIONS['presets']:
        print("No collision presets available to populate the enum list.")
        return

    COLLISIONS_ENUM_LIST.extend([
        (preset.name, preset.name, preset.desc or f"Collision preset: {preset.name}")
        for preset in COLLISIONS['presets'].values()
    ])


def populate_collision_cache() -> None:
    """Populate the COLLISIONS cache from XML files."""
    data_path = Path(bpy.context.preferences.addons['i3dio'].preferences.fs_data_path)
    shared_dir = data_path.parent / 'shared'
    flags_path = shared_dir / 'collisionMaskFlags.xml'
    rules_path = shared_dir / 'collisionMaskConversionRules.xml'

    # Parse XML files
    if flags_path.exists():
        parse_collision_mask_flags(flags_path)
    else:
        print(f"Collision flags file not found: {flags_path}")

    if rules_path.exists():
        parse_collision_mask_rules(rules_path)
    else:
        print(f"Collision rules file not found: {rules_path}")

    # Populate the enum list
    populate_collision_enum_list()


def apply_rule_to_mask(rule: CollisionRule, is_trigger: bool) -> dict[str, str]:
    """Apply a collision rule based on the `isTrigger` condition."""
    global COLLISIONS

    def _get_bitmask(flags: list[str], flag_map: dict[str, int]) -> int:
        """Compute the bitmask for a list of flags."""
        bitmask = 0
        for flag in flags:
            if flag in flag_map:
                bitmask |= (1 << flag_map[flag])
            else:
                print(f"Unknown flag '{flag}'.")
        return bitmask

    # Find mathcing output, in maskOld="1073741824" there is 2 outputs, one for trigger and one for non-trigger
    output = next((o for o in rule.outputs if o.is_trigger == is_trigger), None)
    if not output:
        print(f"No matching output for trigger={is_trigger}")
        return {'group_hex': '0', 'mask_hex': '0'}

    group_value = 0
    mask_value = 0

    if output.preset:
        preset = COLLISIONS['presets'][output.preset]
        group_value = compute_bitmask(preset.group, COLLISIONS['flags'])
        mask_value = preset.mask

    # Add group & mask flags
    group_value |= _get_bitmask(output.group, COLLISIONS['flags'])
    if isinstance(output.mask, int):
        mask_value = output.mask  # Directly set the mask value if it's an integer e.g.: <mask value="1"/>
    else:
        mask_value |= _get_bitmask(output.mask, COLLISIONS['flags'])

    # Remove flags specified in `withoutFlag`: <withoutFlag name="TERRAIN_DELTA" />
    for flag in output.without_flags:
        if flag in COLLISIONS['flags']:
            mask_value &= ~(1 << COLLISIONS['flags'][flag])
        else:
            print(f"Unknown withoutFlag '{flag}' in rule.")

    return {'group_hex': f"{group_value:x}", 'mask_hex': f"{mask_value:x}"}


@persistent
def convert_old_collision_masks(dummy) -> None:
    global COLLISIONS
    rule_lookup = {rule.mask_old: rule for rule in COLLISIONS['rules']}

    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            print(f"Skipping non-mesh object: {obj.name}")
            continue

        if (old_mask_hex := obj.i3d_attributes.get('collision_mask')) is not None:
            try:
                old_mask_decimal = int(old_mask_hex, 16)  # Convert to decimal
            except ValueError:
                print(f"Invalid collision mask '{old_mask_hex}' for object '{obj.name}'")
                continue

            # Get all matching rules for this mask
            rule = rule_lookup.get(old_mask_decimal)
            if not rule:
                print(f"No rule found for mask '{old_mask_hex}' for object '{obj.name}'")
                continue

            is_trigger = getattr(obj.i3d_attributes, 'trigger', False)
            # Apply the rule to calculate the new values
            result = apply_rule_to_mask(rule, is_trigger)

            # If a preset is specified, set the collisions_preset
            if (preset_name := next((output.preset for output in rule.outputs if output.preset), None)):
                obj.i3d_attributes.collisions_preset = preset_name

            # Assign the computed values
            obj.i3d_attributes.collision_filter_group = result['group_hex']
            obj.i3d_attributes.collision_filter_mask = result['mask_hex']

            print(f"Converted collision mask for '{obj.name}': "
                  f"group='{result['group_hex']}', mask='{result['mask_hex']}', trigger={is_trigger}")


def register():
    populate_collision_cache()
    load_post.append(convert_old_collision_masks)


def unregister():
    load_post.remove(convert_old_collision_masks)
