import logging
import os
from mathutils import Vector
import math
logger = logging.getLogger(__name__)

import bpy, bmesh
from bpy.types import (
    Menu,
    WindowManager,
    Operator
)

from bpy.props import (
    EnumProperty,
    IntVectorProperty,
    BoolProperty
)

# Stored in UDIM index order, starting from top-left corner (Makes it easy to show index order in ui)
# Will be valid as long as dictionaries are ordered (Which they are from CPython 3.6 and above)
udim_mapping = {
    '33_GraphiteBlackPaintedMetal.png': {'name': 'Graphite Black Painted Metal',    'offset': [0, 4]},
    '33_HalfMetalNoise.png': {'name': 'Half Metal Noise',                           'offset': [1, 4]},
    '34_GrayShinyPlastic.png': {'name': 'Gray Shiny Plastic',                       'offset': [2, 4]},
    '35_Gold.png': {'name': 'Gold',                                                 'offset': [3, 4]},
    '36_RoughPaintedMetal.png': {'name': 'Rough Painted Metal',                     'offset': [4, 4]},
    '37_PerforatedSyntheticFabric02.png': {'name': 'Perforated Synthetic Fabric',   'offset': [5, 4]},
    '38_Fell.png': {'name': 'Fell',                                                 'offset': [6, 4]},
    '39_CorrugatedMetal.png': {'name': 'Corrugated Metal',                          'offset': [7, 4]},
    '24_GearShiftStickPlastic.png': {'name': 'Gear Shift Stick Plastic',            'offset': [0, 3]},
    '25_Leather.png': {'name': 'Leather',                                           'offset': [1, 3]},
    '26_PerforatedPlastic.png': {'name': 'Perforated Synthetic Fabric',             'offset': [2, 3]},
    '27_GlassClear.png': {'name': 'Glass Clear',                                    'offset': [3, 3]},
    '28_GlassSquare.png': {'name': 'Glass Square',                                  'offset': [4, 3]},
    '29_GlassLine.png': {'name': 'Glass Lines',                                     'offset': [5, 3]},
    '30_Palladium.png': {'name': 'Palladium',                                       'offset': [6, 3]},
    '31_Bronze.png': {'name': 'Bronze',                                             'offset': [7, 3]},
    '16_PaintedMetal.png': {'name': 'Painted Metal',                                'offset': [0, 2]},
    '17_PaintedPlastic.png': {'name': 'PaintedPlastic',                             'offset': [1, 2]},
    '18_SilverRough.png': {'name': 'Silver Rough',                                  'offset': [2, 2]},
    '19_BrassScratched.png': {'name': 'Brass Scratched',                            'offset': [3, 2]},
    '20_ReflectorWhite.png': {'name': 'Reflector White',                            'offset': [4, 2]},
    '21_ReflectorRed.png': {'name': 'Reflector Red',                                'offset': [5, 2]},
    '22_Reflector_Yellow.png': {'name': 'Reflector Yellow',                         'offset': [6, 2]},
    '23_ReflectorDaylight.png': {'name': 'Reflector Daylight',                      'offset': [7, 2]},
    '08_SilverScratched.png': {'name': 'Silver Scratched',                          'offset': [0, 1]},
    '09_SilverBumpy.png': {'name': 'Silver Bumpy',                                  'offset': [1, 1]},
    '10_Fabric.png': {'name': 'Fabric',                                             'offset': [2, 1]},
    '11_Fabric.png': {'name': 'Fabric',                                             'offset': [3, 1]},
    '12_Leather.png': {'name': 'Leather',                                           'offset': [4, 1]},
    '13_Leather.png': {'name': 'Leather',                                           'offset': [5, 1]},
    '14_Wood.png': {'name': 'Wood',                                                 'offset': [6, 1]},
    '15_Dirt.png': {'name': 'Dirt',                                                 'offset': [7, 1]},
    '00_PaintedMetal.png': {'name': 'Painted Metal',                                'offset': [0, 0]},
    '01_PaintedPlastic.png': {'name': 'Painted Plastic',                            'offset': [1, 0]},
    '02_Chrome.png': {'name': 'Chrome',                                             'offset': [2, 0]},
    '03_Copper.png': {'name': 'Copper',                                             'offset': [3, 0]},
    '04_GalvanizedMetal.png': {'name': 'Galvanized Metal',                          'offset': [4, 0]},
    '05_Rubber.png': {'name': 'Rubber',                                             'offset': [5, 0]},
    '06_PaintedMetalOld.png': {'name': 'Painted Metal Old',                         'offset': [6, 0]},
    '07_Fabric.png': {'name': 'Fabric',                                             'offset': [7, 0]},
    '0_ColorMaterial.png': {'name': 'Color Material 0',                             'offset': [0, -1]},
    '1_ColorMaterial.png': {'name': 'Color Material 1',                             'offset': [1, -1]},
    '2_ColorMaterial.png': {'name': 'Color Material 2',                             'offset': [2, -1]},
    '3_ColorMaterial.png': {'name': 'Color Material 3',                             'offset': [3, -1]},
    '4_ColorMaterial.png': {'name': 'Color Material 4',                             'offset': [4, -1]},
    '5_ColorMaterial.png': {'name': 'Color Material 5',                             'offset': [5, -1]},
    '6_ColorMaterial.png': {'name': 'Color Material 6',                             'offset': [6, -1]},
    '7_ColorMaterial.png': {'name': 'Color Material 7',                             'offset': [7, -1]},
}


# A place to store preview collections, should perhaps be outside in overall package scope
preview_collections = {}
# Name of the udim picker collection within the preview collections
udim_picker_preview_collection = 'udim_picker'

addon_keymaps = []
classes = []


def generate_udim_previews():
    def no_number(name):
        """Return name without number prefix"""
        return name.split('_', 1)[1]

    preview_collection = preview_collections[udim_picker_preview_collection]
    image_paths = []
    # Get all icons from folder
    directory = os.path.join(os.path.dirname(__file__), 'icons')
    for path in os.listdir(directory):
        if path.lower().endswith('.png'):
            image_paths.append(path)

    image_paths = sorted(image_paths, key=no_number)

    # Generate icons and build enum
    for i, filename in enumerate(image_paths):
        filepath = os.path.join(directory, filename)
        thumbnail = preview_collection.load(filename, filepath, 'IMAGE')
        name = udim_mapping[filename]['name']
        preview_collection.udim_previews.append((filename, name, name, thumbnail.icon_id, i))


def register(cls):
    classes.append(cls)
    return cls


@register
class I3D_IO_OT_udim_mover(Operator):
    bl_idname = 'i3dio.udim_mover'
    bl_label = "Move UV's"
    bl_description = "Move UV's to a specific position or by an offset if relative is true"
    bl_options = {'INTERNAL'}

    uv_offset: IntVectorProperty(default=(0, 0), size=2)
    relative_move: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.mode == 'EDIT'

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        b_mesh = bmesh.from_edit_mesh(mesh)
        uv_layer = b_mesh.loops.layers.uv.verify()

        if self.relative_move:
            for face in b_mesh.faces:
                for loop in face.loops:
                    loop_uv = loop[uv_layer]
                    if loop_uv.select: #or loop.vert.select:
                        loop_uv.uv += Vector(self.uv_offset)
        else:
            cumulative_uv_position = Vector((0.0, 0.0))
            uvs_to_move = []

            for face in b_mesh.faces:
                for loop in face.loops:
                    loop_uv = loop[uv_layer]
                    if loop_uv.select: #or loop.vert.select:
                        uvs_to_move.append(loop_uv)
                        cumulative_uv_position += loop_uv.uv

            if len(uvs_to_move):
                cumulative_uv_position = Vector([math.floor(x) for x in (cumulative_uv_position / len(uvs_to_move))])

                for uv in uvs_to_move:
                    uv.uv -= cumulative_uv_position
                    uv.uv += Vector(self.uv_offset)

        bmesh.update_edit_mesh(mesh)

        return {'FINISHED'}


@register
class I3D_IO_OT_udim_picker_move_relative(Operator):
    bl_idname = 'i3dio.udim_picker_move_relative'
    bl_label = ""

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.alignment = 'CENTER'
        row.split()
        row.split()
        row.split()
        row.label(text="Move Relative")

        grid = layout.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=True, align=True)

        # Left & Up
        op = grid.operator('i3dio.udim_mover', text='', icon='KEYTYPE_KEYFRAME_VEC')
        op.uv_offset = [-1, 1]
        op.relative_move = True

        # Up
        op = grid.operator('i3dio.udim_mover', text='', icon='TRIA_UP')
        op.uv_offset = [0, 1]
        op.relative_move = True

        # Right & Up
        op = grid.operator('i3dio.udim_mover', text='', icon='KEYTYPE_KEYFRAME_VEC')
        op.uv_offset = [1, 1]
        op.relative_move = True

        # Left
        op = grid.operator('i3dio.udim_mover', text='', icon='TRIA_LEFT')
        op.uv_offset = [-1, 0]
        op.relative_move = True

        # Zero
        op = grid.operator('i3dio.udim_mover', text='', icon='HANDLETYPE_VECTOR_VEC')
        op.uv_offset = [0, 0]
        op.relative_move = False

        # Right
        op = grid.operator('i3dio.udim_mover', text='', icon='TRIA_RIGHT')
        op.uv_offset = [1, 0]
        op.relative_move = True

        # Left & Down
        op = grid.operator('i3dio.udim_mover', text='', icon='KEYTYPE_KEYFRAME_VEC')
        op.uv_offset = [-1, -1]
        op.relative_move = True

        # Down
        op = grid.operator('i3dio.udim_mover', text='', icon='TRIA_DOWN')
        op.uv_offset = [0, -1]
        op.relative_move = True

        # Right & Down
        op = grid.operator('i3dio.udim_mover', text='', icon='KEYTYPE_KEYFRAME_VEC')
        op.uv_offset = [1, -1]
        op.relative_move = True

        layout.label(text='')

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


@register
class I3D_IO_OT_udim_picker_grid_order(Operator):
    bl_idname = 'i3dio.udim_picker_grid_order'
    bl_label = ""

    def draw(self, context):
        layout = self.layout
        grid = layout.grid_flow(row_major=True, columns=8, even_columns=True, even_rows=False)

        for udim_id, udim_item in udim_mapping.items():
            cell = grid.column().box()
            cell.alignment = 'CENTER'
            cell.label(text=udim_item['name'])
            cell.template_icon(icon_value=preview_collections[udim_picker_preview_collection][udim_id].icon_id, scale=3)
            o = cell.operator('i3dio.udim_mover', text='Select')
            o.uv_offset = udim_item['offset']
            o.relative_move = False

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=800)


@register
class I3D_IO_MT_PIE_UDIM_picker(Menu):
    bl_idname = 'I3D_IO_MT_PIE_UDIM_picker'
    bl_label = 'UDIM Picker'

    def draw(self, context):
        layout = self.layout

        wm = context.window_manager

        pie = layout.menu_pie()

        pie.operator('i3dio.udim_picker_grid_order', text="Pick UDIMs")

        # Relative movement operators
        pie.operator('i3dio.udim_picker_move_relative', text="Move UDIM's Relatively")

        #pie.template_icon_view(wm, "udim_previews", show_labels=True, scale=5.0, scale_popup=4.0)


def add_hotkey():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    if not kc:
        logger.warning(f"Keymap Error")
        return

    km = kc.keymaps.new(name='UV Editor', space_type='EMPTY')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'U', 'PRESS', ctrl=True, shift=False)
    kmi.properties.name = I3D_IO_MT_PIE_UDIM_picker.bl_idname
    addon_keymaps.append((km, kmi))


def remove_hotkey():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)

    addon_keymaps.clear()


def udim_selected(self, context):
    uv_offset = udim_mapping[context.window_manager.udim_previews]['offset']
    bpy.ops.i3dio.udim_mover(uv_offset=uv_offset, relative_move=False)


def register():
    import bpy.utils.previews
    preview_collection = bpy.utils.previews.new()
    preview_collection.udim_previews = []
    preview_collections[udim_picker_preview_collection] = preview_collection

    generate_udim_previews()

    for cls in classes:
        bpy.utils.register_class(cls)

    WindowManager.udim_previews = EnumProperty(items=preview_collection.udim_previews, update=udim_selected)

    add_hotkey()


def unregister():
    remove_hotkey()
    for cls in classes:
        bpy.utils.unregister_class(cls)

    for preview_collection in preview_collections.values():
        bpy.utils.previews.remove(preview_collection)
        preview_collection.udim_previews.clear()
    preview_collections.clear()

