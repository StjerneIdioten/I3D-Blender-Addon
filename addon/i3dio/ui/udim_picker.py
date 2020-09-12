import logging
import os
logger = logging.getLogger(__name__)

import bpy
from bpy.types import (
    Menu,
    WindowManager
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

# A place to store preview collections, should perhaps be outside in overall package scope
preview_collections = {}
# Name of the udim picker collection within the preview collections
udim_picker_preview_collection = 'udim_picker'

addon_keymaps = []
classes = []


def generate_udim_previews():
    preview_collection = preview_collections[udim_picker_preview_collection]
    image_paths = []
    # Get all icons from folder
    directory = os.path.join(os.path.dirname(__file__), 'icons')
    for path in os.listdir(directory):
        if path.lower().endswith('.png'):
            image_paths.append(path)

    # Generate icons and build enum
    for i, name in enumerate(image_paths):
        filepath = os.path.join(directory, name)
        thumbnail = preview_collection.load(name, filepath, 'IMAGE')
        preview_collection.udim_previews.append((name, name, "", thumbnail.icon_id, i))


def register(cls):
    classes.append(cls)
    return cls


@register
class I3D_IO_MT_PIE_UDIM_picker(Menu):
    bl_idname = 'I3D_IO_MT_PIE_UDIM_picker'
    bl_label = 'UDIM Picker'

    def draw(self, context):
        layout = self.layout

        wm = context.window_manager

        pie = layout.menu_pie()
        pie.template_icon_view(wm, "udim_previews", show_labels=True, scale=3.0, scale_popup=3.0)
        # pie.prop(wm, "udim_previews")


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
    import bpy.utils.previews
    preview_collection = bpy.utils.previews.new()
    preview_collection.udim_previews = []
    preview_collections[udim_picker_preview_collection] = preview_collection

    generate_udim_previews()

    WindowManager.udim_previews = EnumProperty(items=preview_collection.udim_previews)

    for cls in classes:
        bpy.utils.register_class(cls)
    add_hotkey()


def unregister():
    remove_hotkey()
    for cls in classes:
        bpy.utils.unregister_class(cls)

    for preview_collection in preview_collections.values():
        bpy.utils.previews.remove(preview_collection)
        preview_collection.udim_previews.clear()
    preview_collections.clear()

