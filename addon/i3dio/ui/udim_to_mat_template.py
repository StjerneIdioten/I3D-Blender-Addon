from __future__ import annotations
from collections import defaultdict
import math
import re
import bpy

from ..utility import get_fs_data_path
from .material_templates import (get_template_by_name, apply_template_to_material, brand_name_from_color,
                                 ensure_base_color_texture)
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
UDIM_TILES_X = 8  # Number of UDIM tiles in the X direction (standard FS UDIM layout)

classes = []


def register(cls):
    classes.append(cls)
    return cls


def is_vehicle_shader(i3d_attributes) -> bool:
    """
    Determines if a given material's attributes correspond to a vehicle shader.
    Checks both the 'shader_name' and the legacy 'source' path,
    since old files stored the full shader XML path in 'source'.
    """
    return (i3d_attributes.shader_name == "vehicleShader" or "vehicleShader" in i3d_attributes.get('source', ''))


def custom_udim_index(u: float, v: float) -> int:
    """
    Calculates a "custom" UDIM tile index, supporting both standard (positive Y) and colorMat row (negative Y).

    - Standard UDIM: (v * tiles_x + u)
    - colorMat row: Only for faces with v < 0 (Blender UVs below 0), returns negative index.
      These are legacy colorMat faces (special row for color-mapped materials).
    """
    u_idx = int(math.floor(abs(u)))
    v_idx = int(math.floor(abs(v)))
    if v < 0:
        # For negative Y, encode the UDIM as a negative value (to keep colorMat row distinct)
        udim = (abs(v_idx) * UDIM_TILES_X + u_idx + 1) * -1
    else:
        udim = v_idx * UDIM_TILES_X + u_idx
    return udim


def get_poly_udim_by_center(poly: bpy.types.MeshPolygon, uv_layer: bpy.types.MeshUVLoopLayer) -> int:
    """
    Returns the UDIM tile index for a polygon by averaging all its UVs.

    This ensures the tile assignment doesn't get "split" by edge/corner faces with mixed UVs.
    (Without this, faces right on the border between tiles could be assigned inconsistently.)
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
    Removes the '_mat' or '.mat' suffix (case-insensitive) and any Blender-style numerical suffixes (e.g., .001)
    from a material name if present. This avoids duplicated suffixes like 'trackBase_metalPainted_mat_mat.002'.
    """
    name = re.sub(r'(_mat|\.mat)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.\d{3}$', '', name)  # Remove trailing '.001', '.002', etc.
    return name


def strip_texture_suffix(name: str) -> str:
    """
    Removes common FS texture role suffixes (diffuse, normal, etc.) from texture names,
    e.g., 'metalPainted_diffuse.dds' -> 'metalPainted'.
    Handles optional Blender numerical suffixes.
    """
    return re.sub(r'_(diffuse|normal|specular|vmask|alpha|height)\.dds(\.\d+)?$', '', name, flags=re.IGNORECASE)


def main_texture_name(mat: bpy.types.Material) -> str:
    """
    Gets the base name for a material by prioritizing the first texture node's filename.
    Texture filenames are typically named following the intended convention (e.g., vehicle_part_normal.dds),
    while Blender material names are often inconsistent. Falls back to the material name (with suffix removed)
    if no texture is found. This base name is used as a prefix for new material names during conversion.
    """
    texture_node = next((node for node in mat.node_tree.nodes if node.type == 'TEX_IMAGE'), None)
    if texture_node and texture_node.image:
        return strip_texture_suffix(texture_node.image.name)
    return remove_mat_suffix(mat.name)


def should_be_wet(all_names: list[str], mat: bpy.types.Material) -> bool:
    """
    Determines if a material should receive the in-game wetness effect.

    The decision is based on a set of rules, primarily by checking associated
    object and material names against a list of keywords for parts that should
    remain dry (e.g., interiors, windows). To handle naming inconsistencies, this
    function uses a ratio. If the percentage of "dry" keywords in the names
    meets a threshold, the material is designated as dry.

    Returns:
        bool: True if the material should be wet, False if it should be dry.
    """
    # 'staticLight' variation is a hard-coded exception and should always be wet.
    if mat.i3d_attributes.shader_variation_name == "staticLight":
        return True

    if not all_names:
        return True  # Default to wet if no names are available, as exterior parts are more common.

    # Keywords indicating parts that should NOT receive rain/wetness effects.
    DRY_KEYWORDS = (
        "window", "glass", "winshield",
        "interior", "seat", "dashboard", "steeringwheel", "pedal"
    )

    # Count how many of the provided names suggest the part should be dry.
    names_lower = [n.lower() for n in all_names]
    dry_matches = sum(1 for name in names_lower if any(keyword in name for keyword in DRY_KEYWORDS))

    dry_ratio = dry_matches / len(names_lower)  # Calculate the ratio of names that imply a "dry" state.
    threshold = 0.5  # If 50% or more of the names suggest a dry part, we classify it as dry.
    # A low ratio of "dry" keywords means the material is likely exterior and should be wet.
    return dry_ratio < threshold


def remap_wetness_uvs(new_material_work_orders: dict) -> None:
    """
    Adjusts UV coordinates to enable or disable the FS25 wetness shader effect.

    The game engine uses the V-axis of the UV map to control this feature:
    - V >= 0: Enables the wetness effect (rain drops, darker surface, etc.).
    - V <  0: Disables the wetness effect.

    This function iterates through all processed material groups and moves their
    UVs into the correct region based on whether they are for an interior/window
    or an exterior part.
    """
    print("--- Starting Wetness UV Remapping ---")

    for (old_mat, udim), work_order in new_material_work_orders.items():
        new_mat = work_order['new_material']
        obj_names = [obj.name for obj in work_order['objects']]

        # Gather all relevant names to determine the desired state.
        all_names = obj_names + [new_mat.name]
        texture_node = next((n for n in old_mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None)
        if texture_node:
            all_names.append(texture_node.image.name)

        # Determine the current state (based on UV position) and desired state (based on naming).
        is_currently_in_wet_region = (udim >= 0)
        is_desired_wet = should_be_wet(all_names, new_mat)  # Using the clearer function

        print(f"Processing '{new_mat.name}' (UDIM {udim}): "
              f"Currently in {'WET' if is_currently_in_wet_region else 'DRY'} region. "
              f"Desired state: {'WET' if is_desired_wet else 'DRY'}.")

        if is_desired_wet and not is_currently_in_wet_region:
            # Move from DRY region (V < 0) to WET region (V >= 0).
            print("  -> Action: Moving UVs UP into wet region.")

            # Calculate how many full rows below V=0 the UVs are.
            # e.g., UDIM -1 -> -8 are on row 0, -9 -> -16 are on row 1, etc.
            rows_below_zero = (abs(udim) - 1) // UDIM_TILES_X
            # The offset moves the UVs up by the number of rows plus one,
            # placing them in the V=[0, 1] range.
            offset = float(rows_below_zero + 1)

            for obj, polys in work_order['objects'].items():
                uv_layer = obj.data.uv_layers[0]
                for _poly_idx, loop_indices in polys:
                    for li in loop_indices:
                        uv_layer.data[li].uv[1] += offset

        elif not is_desired_wet and is_currently_in_wet_region:
            # Move from WET region (V >= 0) to DRY region (V < 0).
            print("  -> Action: Moving UVs DOWN into dry region.")

            # Calculate the current UDIM tile row index (0 for UDIMs 0-7, 1 for 8-15, etc.).
            rows_above_zero = udim // UDIM_TILES_X
            # The offset moves the UVs down by the number of rows plus one,
            # placing them in the V=[-1, 0] range.
            offset = float(rows_above_zero + 1)

            for obj, polys in work_order['objects'].items():
                uv_layer = obj.data.uv_layers[0]
                for _poly_idx, loop_indices in polys:
                    for li in loop_indices:
                        uv_layer.data[li].uv[1] -= offset
        else:
            # The UVs are already in the correct region. No action needed.
            print("  -> Action: NONE. State is already correct.")

    print("--- Finished Wetness UV Remapping ---")


@register
class I3D_IO_OT_udim_to_mat_template(bpy.types.Operator):
    bl_idname = "i3dio.udim_to_mat_template"
    bl_label = "UDIM to Material Template"
    bl_description = "Convert UDIM to material template"
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        """
        Convert legacy FS19/22 vehicleShader materials (UDIM-based) to FS25-style material templates and brand templates

        - For each mesh & material, group faces by (material, UDIM) combo.
        - ColorMat faces (UVs with negative Y, colorable) are handled by their colorMatN param.
        - Each group is assigned a new converted Blender material using the FS25 template system.
        - UVs/indices are updated accordingly, and old materials are cleaned up.
        """

        mesh_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH' and len(obj.data.uv_layers)]
        if not mesh_objects:
            self.report({'ERROR'}, "No mesh objects with UV layers found")
            return {'CANCELLED'}

        active_object = context.view_layer.objects.active
        original_mode = None
        # Ensure we are in OBJECT mode before processing
        if active_object and active_object.mode != 'OBJECT' and bpy.ops.object.mode_set.poll():
            original_mode = active_object.mode
            bpy.ops.object.mode_set(mode='OBJECT')

        # Previous game versions (FS19/22) used a "one material per mesh" rule, but in practice,
        # many user mods break this rule. We cannot assume that meshes have only one material,
        # so we need to handle all materials per mesh.

        # Each work_order groups all faces (per-object) by unique (material, UDIM) combination.
        new_material_work_orders = defaultdict(lambda: {'objects': defaultdict(list), 'color': None})

        # Group all polygons by (material, UDIM)
        for obj in mesh_objects:
            mesh = obj.data
            uv_layer = mesh.uv_layers[0]  # Always use the first UV layer for UDIMs
            for mat_slot_idx, mat in enumerate(mesh.materials):
                if mat is None or not is_vehicle_shader(mat.i3d_attributes):
                    continue  # Skip non-vehicleShader materials

                i3d_attrs = mat.i3d_attributes
                if i3d_attrs.shader_game_version == '25':
                    continue  # Already migrated to FS25

                for poly in mesh.polygons:
                    if poly.material_index != mat_slot_idx:
                        continue  # Polygon isn't using this slot/material
                    udim = get_poly_udim_by_center(poly, uv_layer)
                    key = (mat, udim)
                    work_order = new_material_work_orders[key]
                    work_order['objects'][obj].append((poly.index, list(poly.loop_indices)))

                    # Handle colorMat row (negative Y UDIM), fetch color/alpha if available
                    if udim < 0:
                        # Wrap to 0-7 for colorMatN, some variations have uv placed -2 on the Y axis
                        colormat_slot = (abs(udim) - 1) % 8
                        param_name = f"colorMat{colormat_slot}"
                        work_order['param_name'] = param_name

                        # Old system: 'source' in i3d_attrs
                        if 'source' in i3d_attrs:
                            shader_params_list = i3d_attrs.get('shader_parameters', [])
                            param_data = next((p for p in shader_params_list if p.get("name") == param_name), None)
                            if param_data:
                                color_mat_vec = param_data.get("data_float_4")
                        else:
                            # New shader system, direct lookup in shader_material_params
                            if param_name in i3d_attrs.shader_material_params:
                                color_mat_vec = i3d_attrs.shader_material_params[param_name]

                        if color_mat_vec and len(color_mat_vec) == 4:
                            work_order['color'] = color_mat_vec[:3]
                            work_order['template_idx_from_alpha'] = int(color_mat_vec[3])
                        else:
                            # No colorMat info found: fallback to default template/color
                            print(f"WARNING: {param_name!r} data not found for material {mat.name!r}.")
                            work_order['template_idx_from_alpha'] = 0  # Defaults to metalPainted
                            work_order['color'] = None  # Color will be taken from the template

        print(f"Found {len(new_material_work_orders)} materials with UDIMs")

        # Convert to new materials for each unique (material, UDIM) combo
        for (old_mat, udim), work_order in new_material_work_orders.items():
            key = (old_mat, udim)
            old_i3d_attrs = old_mat.i3d_attributes
            old_variation_name = (old_i3d_attrs.get('temp_old_variation_name') or old_i3d_attrs.shader_variation_name)

            from_alpha = "template_idx_from_alpha" in work_order
            template_idx = work_order.get('template_idx_from_alpha', udim)

            # Look up the FS25 template name by UDIM index or by the alpha-channel override
            template_info = UDIM_TO_MAT_TEMPLATE.get(template_idx)
            template_name = (template_info[1 if from_alpha else 0]
                             if template_info else f"unknownTemplate_{template_idx}")

            if "decal" in old_variation_name.lower() and udim == 0:
                template_name = "decal"  # Special case for decals, use a generic decal template

            # Brand template, if color matches any known brand colorScale (from xml)
            brand_name = brand_name_from_color(work_order['color']) if work_order['color'] else None
            name_from_texture_node = main_texture_name(old_mat)

            name_parts = [name_from_texture_node, template_name]
            if brand_name:
                name_parts.append(brand_name)
            elif param_name := work_order.get('param_name'):
                name_parts.append(param_name)  # Ensures uniqueness if no brand name
            final_name = "_".join(name_parts) + "_mat"

            # Copy the old material to preserve its node tree, textures, and properties
            new_mat = old_mat.copy()
            new_mat.name = final_name
            new_i3d_attrs = new_mat.i3d_attributes
            params = new_i3d_attrs.shader_material_params
            textures = new_i3d_attrs.shader_material_textures

            # Set shader and variation first to ensure material properties is "initialized" correctly
            new_i3d_attrs.shader_name = ""  # Clear before setting, avoids potential conflicts
            new_i3d_attrs.shader_name = 'vehicleShader'
            migrate_variation(new_i3d_attrs, old_variation_name, True)

            base_template = get_template_by_name(template_name)
            brand_template = get_template_by_name(brand_name) if brand_name else None

            if brand_template:
                # Always apply base first, then overlay "only the declared values" from brand
                if base_template:
                    apply_template_to_material(params, textures, base_template)
                # Only apply explicit (non-default) values from brand template
                apply_template_to_material(params, textures, brand_template, overlay_only_declared=True)
            elif base_template:
                # Only base template (no brand overlay)
                apply_template_to_material(params, textures, base_template)
            else:
                print(f"WARNING: No base or brand template found for {template_name!r} or {brand_name!r}.")

            migrate_and_apply_parameters(new_i3d_attrs, old_i3d_attrs)
            migrate_material_textures(new_i3d_attrs, old_i3d_attrs)

            # If a color was extracted from colorMatN, set it on the new material
            if work_order['color']:
                if 'colorScale' in new_i3d_attrs.shader_material_params:
                    new_i3d_attrs.shader_material_params['colorScale'] = work_order['color']
                else:
                    print(f"WARNING: Could not find 'colorScale' on '{new_mat.name}' to apply color.")

            # Ensure new material has a base color texture
            ensure_base_color_texture(new_mat)

            # Remove any obsolete old keys from the new material
            for key in ['source', 'variation', 'variations', 'shader_parameters', 'shader_textures']:
                if key in new_i3d_attrs:
                    del new_i3d_attrs[key]

            work_order['new_material'] = new_mat

        print("Finished creating materials.")

        # Assign new materials to mesh polygons & update slots
        affected_objects: set[bpy.types.Object] = set()
        processed_old_mats: set[bpy.types.Material] = set()
        for (old_mat, udim), work_order in new_material_work_orders.items():
            processed_old_mats.add(old_mat)
            for obj in work_order['objects']:
                affected_objects.add(obj)

        print(f"Updating {len(affected_objects)} affected objects...")

        # For each object, assign polygons to their correct new material, update material slots
        for obj in affected_objects:
            mesh = obj.data
            uv_layer = mesh.uv_layers[0]  # Needed for UV remapping later (to tile 0-1 space)

            # Map poly index -> new material for this object
            poly_to_new_mat_map: dict[int, bpy.types.Material] = {}
            for (old_mat, udim), work_order in new_material_work_orders.items():
                if obj in work_order['objects']:
                    new_mat = work_order['new_material']
                    for poly_idx, _loop_indices in work_order['objects'][obj]:
                        poly_to_new_mat_map[poly_idx] = new_mat

            # Ensure all new materials are present in mesh.materials slots and
            # map each material to its slot index for fast assignment to polygons.
            needed_new_mats = set(poly_to_new_mat_map.values())
            new_mat_to_slot_idx = {}
            for new_mat in needed_new_mats:
                slot_idx = mesh.materials.find(new_mat.name)
                if slot_idx == -1:
                    mesh.materials.append(new_mat)
                    slot_idx = len(mesh.materials) - 1
                new_mat_to_slot_idx[new_mat] = slot_idx

            print(f"Assigned {len(new_mat_to_slot_idx)} new materials to slots in {obj.name}")

            # Reassign each polygon to use the correct new material slot based on the conversion mapping.
            for poly_idx, new_mat in poly_to_new_mat_map.items():
                mesh.polygons[poly_idx].material_index = new_mat_to_slot_idx[new_mat]

            used_slot_indices = {p.material_index for p in mesh.polygons}

            # Remove unused materials slots (reverse order to avoid index issues)
            for i in range(len(mesh.materials) - 1, -1, -1):
                if i not in used_slot_indices:
                    mesh.materials.pop(index=i)

        print("Finished assigning materials to polygons.")

        remap_wetness_uvs(new_material_work_orders)

        print("Unused material cleanup")
        for old_mat in processed_old_mats:
            if old_mat.users == 0:
                print(f"Removing unused old material data-block: {old_mat.name}")
                bpy.data.materials.remove(old_mat)
                continue
            # Remove any temporary attributes on still-used materials
            if 'temp_old_variation_name' in old_mat.i3d_attributes:
                del old_mat.i3d_attributes['temp_old_variation_name']

        if active_object and original_mode:
            context.view_layer.objects.active = active_object
            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode=original_mode)
        self.report({'INFO'}, "UDIM converted to material template")
        return {'FINISHED'}

    def invoke(self, context: bpy.types.Context, _event):
        return context.window_manager.invoke_props_dialog(self, width=500)

    def draw(self, _context):
        layout = self.layout
        layout.label(text="This will convert legacy UDIM-based materials to FS25 material templates.")
        layout.label(text="It will go through all mesh objects in the scene and remap their materials accordingly.")
        layout.label(text="After running, this file is not compatible with FS19/22 anymore.", icon='ERROR')


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _register()


def unregister():
    _unregister()
