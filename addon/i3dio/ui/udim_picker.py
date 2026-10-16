import math
from itertools import chain, product

import bmesh
import bpy
from bpy.props import EnumProperty, IntVectorProperty
from bpy.types import Menu, Operator
from bpy_extras.bmesh_utils import bmesh_linked_uv_islands
from mathutils import Vector

from .. import addon_logging

logger = addon_logging.get_logger(__name__)

addon_keymaps = []
classes = []


def register(cls):
    classes.append(cls)
    return cls


def uv_loop_selected(loop, uv_layer) -> bool:
    """Check UV vertex selection with UV Sync disabled (Blender 4.5+)."""
    return loop.uv_select_vert if hasattr(loop, "uv_select_vert") else loop[uv_layer].select


def uv_face_selected(face, uv_layer) -> bool:
    """Check UV face selection across Blender 4.5 and 5.0+."""
    if hasattr(face, "uv_select"):  # Blender 5.0+
        return face.uv_select
    # Blender 4.5
    return all(loop[uv_layer].select_edge for loop in face.loops)


def selected_uvs(face, uv_layer, sync_enabled, face_mode):
    """Yield UVs from fully selected faces, avoiding partial-face movement."""
    if face.hide or not face.select:
        return

    if not sync_enabled:
        if face_mode:
            if not uv_face_selected(face, uv_layer):
                return
        elif not all(uv_loop_selected(loop, uv_layer) for loop in face.loops):
            return

    for loop in face.loops:
        yield loop[uv_layer]


@register
class I3D_IO_OT_udim_mover(Operator):
    bl_idname = "i3dio.udim_mover"
    bl_label = "Move UVs"
    bl_description = "Move selected UV faces to a specific UDIM tile or by a relative tile offset"
    bl_options = {"INTERNAL", "UNDO"}

    uv_offset: IntVectorProperty(default=(0, 0), size=2)
    mode: EnumProperty(items=[("RELATIVE", "", ""), ("ABSOLUTE", "", "")], default="ABSOLUTE")

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        tool_settings = context.scene.tool_settings
        sync_enabled = tool_settings.use_uv_select_sync
        face_mode = not sync_enabled and tool_settings.uv_select_mode in {"FACE", "ISLAND"}

        objects = context.objects_in_mode_unique_data
        # If sync is OFF, user may have UV-only selection, so don't filter by total_vert_sel
        if sync_enabled:
            objects = (obj for obj in objects if obj.data.total_vert_sel)

        uv_offset = Vector(self.uv_offset)

        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            if self.mode == "RELATIVE":
                for face in bm.faces:
                    for loop_uv in selected_uvs(face, uv_layer, sync_enabled, face_mode):
                        loop_uv.uv += uv_offset

            elif self.mode == "ABSOLUTE":
                # Group by complete UV islands; disconnected selections within an island share an offset.
                for island in bmesh_linked_uv_islands(bm, uv_layer):
                    uvs = [uv for face in island for uv in selected_uvs(face, uv_layer, sync_enabled, face_mode)]
                    if not uvs:
                        continue

                    average = sum((uv.uv for uv in uvs), Vector((0.0, 0.0))) / len(uvs)
                    origin = Vector((math.floor(average.x), math.floor(average.y)))
                    offset = uv_offset - origin

                    for uv in uvs:
                        uv.uv += offset

            bmesh.update_edit_mesh(obj.data)

        return {"FINISHED"}


@register
class I3D_IO_OT_udim_picker_move_relative(Operator):
    bl_idname = "i3dio.udim_picker_move_relative"
    bl_label = "Move UVs Relatively"
    bl_description = "Move selected UV faces in relative UDIM-tile steps"

    _ICON_MAP = {
        (0, 0): "HANDLETYPE_VECTOR_VEC",
        (0, 1): "TRIA_UP",
        (0, -1): "TRIA_DOWN",
        (1, 0): "TRIA_RIGHT",
        (-1, 0): "TRIA_LEFT",
    }

    def draw(self, context):
        layout = self.layout
        grid = layout.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=True, align=True)

        for dy, dx in product((1, 0, -1), (-1, 0, 1)):
            icon = self._ICON_MAP.get((dx, dy), "KEYTYPE_KEYFRAME_VEC")
            op = grid.operator(I3D_IO_OT_udim_mover.bl_idname, text="", icon=icon)
            op.uv_offset = (dx, dy)
            op.mode = "ABSOLUTE" if (dx, dy) == (0, 0) else "RELATIVE"

        layout.row(align=True).template_popup_confirm("", text="", cancel_text="Close")

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


light_udim_mapping = {
    1: {"name": "Default Light", "offset": (0, 0)},
    2: {"name": "Default Light & High Beam", "offset": (1, 0)},
    3: {"name": "High Beam", "offset": (2, 0)},
    4: {"name": "Bottom Light", "offset": (3, 0)},
    5: {"name": "Top Light", "offset": (4, 0)},
    6: {"name": "Day Time Running Light", "offset": (5, 0)},
    7: {"name": "Turn Light Left", "offset": (6, 0)},
    8: {"name": "Turn Light Right", "offset": (7, 0)},
    9: {"name": "Back Light", "offset": (0, 1)},
    10: {"name": "Brake Light", "offset": (1, 1)},
    11: {"name": "Back & Brake Light", "offset": (2, 1)},
    12: {"name": "Reverse Light", "offset": (3, 1)},
    13: {"name": "Work Light Front", "offset": (4, 1)},
    14: {"name": "Work Light Back", "offset": (5, 1)},
    15: {"name": "Work Light Additional", "offset": (6, 1)},
    16: {"name": "Work Light Additional 2", "offset": (7, 1)},
}


@register
class I3D_IO_OT_udim_picker_grid_order(Operator):
    bl_idname = "i3dio.udim_picker_grid_order"
    bl_label = "Pick UDIMs"
    bl_description = "Move selected UV faces to a specific UDIM tile without packing them"

    def draw(self, context):
        layout = self.layout
        grid = layout.grid_flow(row_major=True, columns=4, even_columns=True, even_rows=True, align=False)

        keys = sorted(light_udim_mapping)
        display_order = list(chain.from_iterable([keys[i : i + 4] for i in range(0, len(keys), 4)][::-1]))

        for k in display_order:
            udim_item = light_udim_mapping[k]
            op = grid.operator(I3D_IO_OT_udim_mover.bl_idname, text=f"{k}: {udim_item['name']}")
            op.uv_offset = udim_item["offset"]
            op.mode = "ABSOLUTE"

        layout.row(align=True).template_popup_confirm("", text="", cancel_text="Close")

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=570)


@register
class I3D_IO_OT_udim_setup(Operator):
    bl_idname = "i3dio.udim_setup"
    bl_label = "Setup UV Editor"
    bl_description = "This will change different settings in relation to having a good setup for FS UDIM's"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        context.area.spaces.active.uv_editor.tile_grid_shape = [8, 5]
        return {"FINISHED"}


@register
class I3D_IO_MT_PIE_UDIM_picker(Menu):
    bl_idname = "I3D_IO_MT_PIE_UDIM_picker"
    bl_label = "UDIM Picker"

    def draw(self, context):
        layout = self.layout

        pie = layout.menu_pie()
        pie.operator(I3D_IO_OT_udim_picker_grid_order.bl_idname)

        # Relative movement operators
        pie.operator(I3D_IO_OT_udim_picker_move_relative.bl_idname)

        # UV sync quick access, should probably move to some settings menu once more settings become available
        pie.prop(bpy.context.scene.tool_settings, "use_uv_select_sync")

        if context.space_data.type == "IMAGE_EDITOR":
            # General setup function for settings up parameters that makes UV-editing easier for FS
            pie.operator(I3D_IO_OT_udim_setup.bl_idname)


def add_hotkey():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    if not kc:
        logger.warning("Keymap Error")
        return

    km = kc.keymaps.new(name="UV Editor")
    kmi = km.keymap_items.new("wm.call_menu_pie", "U", "PRESS", ctrl=True, shift=False)
    kmi.properties.name = I3D_IO_MT_PIE_UDIM_picker.bl_idname
    addon_keymaps.append((km, kmi))

    km = kc.keymaps.new(name="Mesh")
    kmi = km.keymap_items.new("wm.call_menu_pie", "U", "PRESS", ctrl=True, shift=False)
    kmi.properties.name = I3D_IO_MT_PIE_UDIM_picker.bl_idname
    addon_keymaps.append((km, kmi))


def remove_hotkey():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    add_hotkey()


def unregister():
    remove_hotkey()
    for cls in classes:
        bpy.utils.unregister_class(cls)
