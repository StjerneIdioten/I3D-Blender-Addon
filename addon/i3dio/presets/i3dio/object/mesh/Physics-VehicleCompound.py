import bpy
obj = bpy.context.object

obj.i3d_attributes.visibility = True
obj.i3d_attributes.clip_distance = 300
obj.i3d_attributes.rigid_body_type = 'dynamic'
obj.i3d_attributes.compound = True
obj.i3d_attributes.collision = True
obj.i3d_attributes.collision_mask = '203002'
obj.i3d_attributes.trigger = False
obj.i3d_attributes.density = 1
obj.data.i3d_attributes.casts_shadows = True
obj.data.i3d_attributes.receive_shadows = True
obj.data.i3d_attributes.non_renderable = True
obj.data.i3d_attributes.cpu_mesh = '0'
obj.data.i3d_attributes.decal_layer = 0
obj.data.i3d_attributes.fill_volume = False
