#!/usr/bin/env python3

if "bpy" in locals():
    import importlib
    importlib.reload(test_op)
    importlib.reload(test_panel)
    print("Reloaded multifiles")
else:
    from . import test_op, test_panel
    print("Imported multifiles")

import bpy

print(__file__)

bl_info = {
    "name": "Test_addon",
    "author": "StjerneIdioten",
    "description": "Simple test addon",
    "blender": (2, 80, 0),
    "location": "View3D",
    "warning": "",
    "category": "Generic"
}

classes = (test_op.TEST_ADDON_OT_center,
           test_panel.TEST_ADDON_PT_center,
           test_op.TEST_ADDON_OT_export_i3d)

factory_register, factory_unregister = bpy.utils.register_classes_factory(classes)


def menu_func_export(self, context):
    self.layout.operator(test_op.TEST_ADDON_OT_export_i3d.bl_idname, text="I3D (.i3d)")


def register():
    factory_register()
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    factory_unregister()
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
