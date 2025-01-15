from typing import Optional
import bpy

from .node import SceneGraphNode
from .shape import (ShapeNode, EvaluatedMesh)
from ..i3d import I3D

MERGE_CHILDREN_DIVIDER = 32768


class MergeChildrenRoot(ShapeNode):
    def __init__(self, id_: int, merge_children_object: bpy.types.Object, i3d: I3D,
                 parent: Optional[SceneGraphNode] = None):
        name = merge_children_object.name
        if merge_children_object.name.endswith('_dummy'):
            name = merge_children_object.name.replace('_dummy', '')
        super().__init__(id_=id_, shape_object=merge_children_object, i3d=i3d, parent=parent, custom_name=name)

    def add_shape(self):
        """Override to add the merged mesh as the shape."""
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object), is_generic=True,
                                           tangent=self.tangent)
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def add_children_meshes(self, empty_object: bpy.types.Object):
        """Collect and evaluate all child meshes of the empty object"""
        apply_transforms = empty_object.i3d_merge_children.apply_transforms
        root_matrix = empty_object.matrix_world
        interpolation_steps = empty_object.i3d_merge_children.interpolation_steps

        self.logger.debug(f"Collecting children meshes for {empty_object.name}, "
                          f"with {interpolation_steps} interpolation steps.")

        child_meshes = [child for child in empty_object.children if child.type == 'MESH']

        g_increase = 0
        for child in child_meshes:
            g_value = g_increase / MERGE_CHILDREN_DIVIDER
            self.logger.debug(f"Child object: {child.name} (g={g_value}), interpolation steps: {interpolation_steps}")

            if apply_transforms:
                # Bake the child's entire transform (location, rotation, scale) into its mesh data.
                # In the exported file, the child will no longer have any local transform relative to the root object,
                # and it will appear as it has been directly aligned with the root's transform.
                reference_frame = root_matrix
            else:
                # Preserve the child's local transform (location, rotation, scale) as it is in Blender.
                # In the exported file, the child will maintain the same relative position, orientation and scale
                # to the root object as seen in Blender.
                reference_frame = child.matrix_world

            self.i3d.shapes[self.shape_id].append_from_evaluated_mesh_generic(
                EvaluatedMesh(self.i3d, child, reference_frame=reference_frame), g_value)
            g_increase += interpolation_steps

    def populate_xml_element(self):
        self.logger.debug("Populating XML element for MergeChildrenRoot")
        super().populate_xml_element()
