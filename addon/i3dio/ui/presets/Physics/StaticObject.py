import bpy
obj = bpy.context.object

if obj.type == 'MESH':
    obj.i3d_attributes.visibility = True
    obj.i3d_attributes.clip_distance = 1000000.0
    obj.i3d_attributes.rigid_body_type = 'static'
    obj.i3d_attributes.compound = True
    obj.i3d_attributes.collision = True
    obj.i3d_attributes.collision_mask = 'ff'
    obj.i3d_attributes.trigger = False
    obj.i3d_attributes.density = 1
    obj.data.i3d_attributes.casts_shadows = True
    obj.data.i3d_attributes.receive_shadows = True
    obj.data.i3d_attributes.non_renderable = False
    obj.data.i3d_attributes.cpu_mesh = '0'
    obj.data.i3d_attributes.decal_layer = 0
    obj.data.i3d_attributes.fill_volume = False
else:
    obj.i3d_attributes.visibility = True
    obj.i3d_attributes.clip_distance = 1000000.0
