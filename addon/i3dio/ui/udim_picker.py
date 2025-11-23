import logging
import math
from collections import defaultdict
from itertools import chain, product

import bmesh
import bpy
from bpy.props import (
    EnumProperty,
    IntVectorProperty,
)
from bpy.types import Menu, Operator
from mathutils import Vector

logger = logging.getLogger(__name__)

addon_keymaps = []
classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class I3D_IO_OT_udim_mover(Operator):
    bl_idname = "i3dio.udim_mover"
    bl_label = "Move UV's"
    bl_description = "Move UV's to a specific position or by an offset if relative is true"
    bl_options = {"INTERNAL", "UNDO"}

    uv_offset: IntVectorProperty(default=(0, 0), size=2)
    mode: EnumProperty(items=[("RELATIVE", "", ""), ("ABSOLUTE", "", "")], default="ABSOLUTE")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == "MESH" and obj.mode == "EDIT"

    def execute(self, context):
        # Grab the current sync setting, instead of looking it up all the time
        sync_enabled = bpy.context.scene.tool_settings.use_uv_select_sync
        if not sync_enabled and "UV Editing" not in [screen.name for screen in context.workspace.screens]:
            self.report({"INFO"}, "UDIM Picker was used within mesh editor, but UV sync is disabled!")
            # Technically I could return the operator, but I will allow it to run just in case someone has some
            # other way of selecting uv's outside of the uv-editor screen

        # Grabs only unique meshes (no instances) and weeds out any objects without selected vertices
        objects = [obj for obj in bpy.context.objects_in_mode_unique_data if obj.data.total_vert_sel]
        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()
            if self.mode == "RELATIVE":
                for face in [face for face in bm.faces if face.select]:
                    for loop in face.loops:
                        loop_uv = loop[uv_layer]
                        # If sync is enabled, loop_uv.select isn't set on selection
                        if loop.vert.select and (sync_enabled or loop_uv.select):
                            loop_uv.uv += Vector(self.uv_offset)
            elif self.mode == "ABSOLUTE":
                # Could use a bidict for this, if I want to install the extra dependency
                faces_to_verts = defaultdict(set)
                verts_to_faces = defaultdict(set)
                for face in [face for face in bm.faces if face.select]:
                    # print(f"Face {face.index}")
                    # Calculate lists of unique vert uv's and make a reverse lookup between faces and verts
                    for loop in face.loops:
                        loop_uv = loop[uv_layer]
                        if loop.vert.select and (sync_enabled or loop_uv.select):
                            unique_uv_id = loop_uv.uv.to_tuple(5), loop.vert.index
                            faces_to_verts[face.index].add(unique_uv_id)
                            verts_to_faces[unique_uv_id].add(face.index)
                            # print(f"\tUV: {unique_uv_id}")

                uv_islands = []
                # A list of all the selected faces
                faces_left = set(faces_to_verts.keys())
                while len(faces_left) > 0:
                    current_island = []
                    # Sets aren't indexable and we don't care about which value we get. So this is the easiest way.
                    faces_idx = next(iter(faces_left))
                    self.parse_island(bm, faces_idx, faces_left, current_island, faces_to_verts, verts_to_faces)
                    uv_islands.append(current_island)

                for island in uv_islands:
                    cumulative_uv_position = Vector((0.0, 0.0))
                    uvs_to_move = []
                    for face in island:
                        for loop in face.loops:
                            loop_uv = loop[uv_layer]
                            if loop.vert.select and (sync_enabled or loop_uv.select):
                                uvs_to_move.append(loop_uv)
                                cumulative_uv_position += loop_uv.uv

                    if len(uvs_to_move):
                        cumulative_uv_position = Vector(
                            [math.floor(x) for x in (cumulative_uv_position / len(uvs_to_move))]
                        )

                        for uv in uvs_to_move:
                            uv.uv -= cumulative_uv_position
                            uv.uv += Vector(self.uv_offset)

            bmesh.update_edit_mesh(obj.data)

        return {"FINISHED"}

    def parse_island(self, bm, face_idx, faces_left, island, faces_to_verts, verts_to_faces):
        faces_to_visit = [face_idx]

        # Use iterative stack to avoid recursion errors on dense meshes
        while faces_to_visit:
            current_face_idx = faces_to_visit.pop()

            if current_face_idx not in faces_left:
                continue

            faces_left.remove(current_face_idx)
            island.append(bm.faces[current_face_idx])

            # Find all faces connected through the shared vertices
            for v in faces_to_verts[current_face_idx]:
                connected_faces = verts_to_faces[v]
                for connected_face_idx in connected_faces:
                    if connected_face_idx in faces_left:
                        faces_to_visit.append(connected_face_idx)


@register
class I3D_IO_OT_udim_picker_move_relative(Operator):
    bl_idname = "i3dio.udim_picker_move_relative"
    bl_label = "Move UDIM's Relatively"
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
    bl_description = "Move selected UV-faces to a specific UDIM-tile, it does not pack them."

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
