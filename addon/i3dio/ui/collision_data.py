from collections import namedtuple

import bpy
from bpy.app.handlers import load_post, persistent

from .. import addon_logging, xml_i3d
from ..utility import get_fs_data_path
from .helper_functions import humanize_template

logger = addon_logging.get_logger("collision_data")

COLLISIONS = {
    'flags': {},  # {name: bit}
    'presets': {},  # {name: CollisionPreset}
    'rules': [],  # List[CollisionRule]
}

CollisionPreset = namedtuple('CollisionPreset', ['name', 'group', 'group_hex', 'mask', 'mask_hex', 'desc'])
CollisionOutput = namedtuple('CollisionOutput', ['preset', 'group', 'mask', 'without_flags', 'is_trigger'])
CollisionRule = namedtuple('CollisionRule', ['mask_old', 'outputs'])


COLLISION_PRESET_CUSTOM = "CUSTOM"
_COLLISION_PRESET_ENUM_ITEMS: list[tuple[str, str, str]] = []


def rebuild_collision_preset_enum_items() -> None:
    """Build Blender enum items for collision presets.
    Kept as a persistent list so dynamic EnumProperty callbacks return stable string references.
    """
    _COLLISION_PRESET_ENUM_ITEMS.clear()
    _COLLISION_PRESET_ENUM_ITEMS.extend(
        ((COLLISION_PRESET_CUSTOM, "Custom", "Use manually edited collision filter group and mask values"),)
    )

    _COLLISION_PRESET_ENUM_ITEMS.extend(
        (name, humanize_template(name), preset.desc or "") for name, preset in sorted(COLLISIONS["presets"].items())
    )


def get_collision_preset_enum_items(self, context):
    return _COLLISION_PRESET_ENUM_ITEMS


def compute_bitmask(flags: list[str], flag_dict: dict[str, int]) -> int:
    bitmask = 0
    for flag in flags:
        if (bit := flag_dict.get(flag)) is None:
            raise ValueError(f"Unknown collision flag {flag!r}")
        bitmask |= 1 << bit
    return bitmask


def parse_collision_mask_flags(filepath) -> None:
    """Parse collisionMaskFlags.xml to populate flags and presets"""
    tree = xml_i3d.parse(filepath)
    if tree is None:
        logger.error(f"Failed to parse {filepath}")
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
                    logger.error(f"Invalid mask value '{direct_value}' in preset '{name}'")
                    continue
            else:
                # If no single value attribute, compute the bitmask from the flags
                mask_value = compute_bitmask(
                    [flag.get('name') for flag in mask_element.findall('./flag')], COLLISIONS['flags']
                )

        mask_hex = f"{mask_value:x}"
        COLLISIONS['presets'][name] = CollisionPreset(name, group_flags, group_hex, mask_value, mask_hex, desc)


def parse_collision_mask_rules(filepath) -> None:
    """Parse collisionMaskConversionRules.xml to populate conversion rules"""
    if (tree := xml_i3d.parse(filepath)) is None:
        logger.error(f"Failed to parse {filepath}")
        return None

    root = tree.getroot()

    for rule in root.findall('./conversionRules/rule'):
        try:
            mask_old = int(rule.get('maskOld'))
        except (ValueError, TypeError):
            logger.error(f"Invalid maskOld {rule.get('maskOld')!r}, skipping rule.")
            continue
        outputs = []
        invalid_rule = False

        for output in rule.findall('./output'):
            preset = output.get('preset')
            trigger_attr = output.get('isTrigger')
            is_trigger = None if trigger_attr is None else trigger_attr.lower() == 'true'
            group_flags = [flag.get('name') for flag in output.findall('./group/flag')]

            # Check for a value in the mask element
            mask_element = output.find('./mask')
            mask_value = mask_element.get('value') if mask_element is not None else None
            if mask_value is not None:
                try:
                    mask_flags = int(mask_value, 16)
                except ValueError:
                    logger.error(f"Invalid mask value {mask_value!r} in rule {mask_old}, skipping rule.")
                    invalid_rule = True
                    break
            else:
                # Parse individual flag names
                mask_flags = [flag.get('name') for flag in output.findall('./mask/flag')]

            without_flags = [flag.get('name') for flag in output.findall('./mask/withoutFlag')]

            outputs.append(CollisionOutput(preset, group_flags, mask_flags, without_flags, is_trigger))

        if invalid_rule:
            continue

        if not outputs:
            logger.warning(f"Skipping collision conversion rule '{mask_old}': no outputs defined.")
            continue

        COLLISIONS['rules'].append(CollisionRule(mask_old, outputs))


def clear_collision_cache() -> None:
    COLLISIONS["flags"].clear()
    COLLISIONS["presets"].clear()
    COLLISIONS["rules"].clear()
    rebuild_collision_preset_enum_items()


def populate_collision_cache() -> None:
    """Populate the COLLISIONS cache from XML files"""
    clear_collision_cache()

    shared_dir = get_fs_data_path(as_path=True).parent / 'shared'
    flags_path = shared_dir / 'collisionMaskFlags.xml'
    rules_path = shared_dir / 'collisionMaskConversionRules.xml'

    # Parse XML files
    if flags_path.exists():
        try:
            parse_collision_mask_flags(flags_path)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid collision flag definitions: {e}")
            clear_collision_cache()
            return
    else:
        logger.error(f"Collision flags file not found: {flags_path}")

    if not COLLISIONS['flags']:
        logger.error("Cannot load collision conversion rules without valid collision flags.")
        return

    if rules_path.exists():
        parse_collision_mask_rules(rules_path)
    else:
        logger.error(f"Collision rules file not found: {rules_path}")

    rebuild_collision_preset_enum_items()


def apply_rule_to_mask(rule: CollisionRule, is_trigger: bool) -> dict[str, str]:
    """Apply a collision rule based on the `isTrigger` condition"""
    # Prefer an output matching the object's trigger state, or one without an isTrigger attribute.
    # Fall back to the first output if neither exists, preserving the previous behavior.
    if (output := next((o for o in rule.outputs if o.is_trigger == is_trigger), None)) is None:
        output = next((o for o in rule.outputs if o.is_trigger is None), rule.outputs[0])

    group_value = 0
    mask_value = 0

    if output.preset:
        preset = COLLISIONS['presets'][output.preset]
        group_value = compute_bitmask(preset.group, COLLISIONS['flags'])
        mask_value = preset.mask

    # Add group & mask flags
    group_value |= compute_bitmask(output.group, COLLISIONS['flags'])
    if isinstance(output.mask, int):
        mask_value = output.mask  # Directly set the mask value if it's an integer e.g.: <mask value="1"/>
    else:
        mask_value |= compute_bitmask(output.mask, COLLISIONS['flags'])

    # Remove flags specified in `withoutFlag`: <withoutFlag name="TERRAIN_DELTA" />
    mask_value &= ~compute_bitmask(output.without_flags, COLLISIONS['flags'])

    return {'group_hex': f"{group_value:x}", 'mask_hex': f"{mask_value:x}"}


@persistent
def convert_old_collision_masks(dummy) -> None:
    if not COLLISIONS['rules']:
        return

    rule_lookup = {rule.mask_old: rule for rule in COLLISIONS['rules']}

    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue

        if (old_mask_hex := obj.i3d_attributes.get('collision_mask')) is not None:
            try:
                old_mask_decimal = int(old_mask_hex, 16)  # Convert to decimal
            except (ValueError, TypeError):
                logger.error(f"Invalid collision mask '{old_mask_hex}' for object {obj.name!r}, skipping.")
                continue

            # Get all matching rules for this mask
            if not (rule := rule_lookup.get(old_mask_decimal)):
                logger.error(f"No rule found for mask '{old_mask_hex}' for object {obj.name!r}, skipping.")
                continue

            is_trigger = getattr(obj.i3d_attributes, 'trigger', False)
            # Apply the rule to calculate the new values
            try:
                result = apply_rule_to_mask(rule, is_trigger)
            except (ValueError, KeyError) as e:
                logger.error(f"Failed to convert collision mask {old_mask_hex!r} for object {obj.name!r}: {e}")
                continue

            # Assign the computed values
            obj.i3d_attributes.collision_filter_group = result['group_hex']
            obj.i3d_attributes.collision_filter_mask = result['mask_hex']

            del obj.i3d_attributes['collision_mask']


def register():
    populate_collision_cache()
    load_post.append(convert_old_collision_masks)


def unregister():
    load_post.remove(convert_old_collision_masks)
