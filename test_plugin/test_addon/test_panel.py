import bpy


class TEST_ADDON_PT_center(bpy.types.Panel):
    bl_idname = "TEST_ADDON_PT_Center"
    bl_label = "Test Panel"
    bl_category = "Test Addon"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.operator('view3d.cursor_center', text="Center 3D cursor")
