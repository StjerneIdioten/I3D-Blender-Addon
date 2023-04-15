import bpy
obj = bpy.context.object

if obj.type == 'LIGHT':
    obj.i3d_attributes.visibility = True
    obj.i3d_attributes.clip_distance = 75
else:
    obj.i3d_attributes.visibility = True
    obj.i3d_attributes.clip_distance = 75
