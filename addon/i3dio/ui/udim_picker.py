import logging
logger = logging.getLogger(__name__)

import bpy
from bpy.types import (
    Panel,
    Operator,
    Menu
)

from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    FloatProperty,
    IntProperty,
    CollectionProperty,
)

addon_keymaps = []
classes = []


def register(cls):
    classes.append(cls)
    return cls


@register
class I3D_IO_MT_PIE_UDIM_picker(Menu):
    bl_idname = 'I3D_IO_MT_PIE_UDIM_picker'
    bl_label = 'UDIM Picker'

    def draw(self, context):
        print("test")
        layout = self.layout
        prefs = context.preferences
        inputs = prefs.inputs

        pie = layout.menu_pie()
        pie.prop(inputs, "view_rotate_method", expand=True)


def add_hotkey():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    if not kc:
        logger.warning(f"Keymap Error")
        return

    km = kc.keymaps.new(name='UV Editor', space_type='EMPTY')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'D', 'PRESS', ctrl=True, shift=False)
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
    for cls in classes:
        bpy.utils.unregister_class(cls)
    remove_hotkey()
