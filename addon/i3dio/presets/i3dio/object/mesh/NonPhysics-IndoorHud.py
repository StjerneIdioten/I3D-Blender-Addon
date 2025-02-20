import bpy
obj = bpy.context.object

obj.i3d_attributes.visibility = True
obj.i3d_attributes.clip_distance = 20
obj.i3d_attributes.rigid_body_type = 'none'
obj.data.i3d_attributes.casts_shadows = True
obj.data.i3d_attributes.receive_shadows = True
obj.data.i3d_attributes.non_renderable = False
obj.data.i3d_attributes.cpu_mesh = '0'
obj.data.i3d_attributes.decal_layer = 0
obj.data.i3d_attributes.fill_volume = False
