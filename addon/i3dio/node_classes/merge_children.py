from typing import Optional
import bpy
import mathutils

from .node import SceneGraphNode
from .shape import (ShapeNode, EvaluatedMesh)
from ..i3d import I3D

MERGE_CHILDREN_DIVIDER = 32768


class MergeChildrenRoot(ShapeNode):
    def __init__(self, id_: int, merge_children_object: bpy.types.Object, i3d: I3D,
                 parent: Optional[SceneGraphNode] = None):
        self.merge_children_name = f"MergeChildren_{merge_children_object.name}"
        name = merge_children_object.name
        super().__init__(id_=id_, shape_object=merge_children_object, i3d=i3d, parent=parent, custom_name=name)

    def add_shape(self):
        """Override to add the merged mesh as the shape."""
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object), self.merge_children_name,
                                           is_generic=True, tangent=self.tangent)
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def add_children_meshes(self, empty_object: bpy.types.Object):
        """Collect and evaluate all mesh children starting from the root child."""
        self.logger.debug(f"Collecting children meshes for {self.blender_object.name}")
        self.logger.debug(f"Root object: {empty_object.name}")
        freeze_translation = empty_object.i3d_merge_children.freeze_translation
        freeze_rotation = empty_object.i3d_merge_children.freeze_rotation
        freeze_scale = empty_object.i3d_merge_children.freeze_scale

        from mathutils import Matrix

        for i, child in enumerate(empty_object.children):
            if child.type == 'MESH':
                g_value = i / MERGE_CHILDREN_DIVIDER

                # Freeze transformations where they currently are located in the world
                if any([freeze_translation, freeze_rotation, freeze_scale]):
                    self.logger.debug(f"Freeze settings: {freeze_translation}, {freeze_rotation}, {freeze_scale}")
                
                    # Decompose matrices
                    child_matrix = child.matrix_world
                    root_matrix = empty_object.matrix_world

                    self.logger.debug(f"Child translation: {child_matrix.translation}")

                    # Start with an identity matrix
                    reference_frame = Matrix.Identity(4)

                    # Apply transformations conditionally
                    if freeze_translation:
                        reference_frame.translation = root_matrix.translation
                    else:
                        reference_frame.translation = child_matrix.translation

                    if freeze_rotation:
                        # Apply only the rotation part from the root matrix
                        reference_frame @= root_matrix.to_3x3().to_4x4()
                    else:
                        # Apply only the rotation part from the child's matrix
                        reference_frame @= child_matrix.to_3x3().to_4x4()

                    if freeze_scale:
                        # Apply only the scale part from the root matrix
                        scale_matrix = Matrix.Diagonal(root_matrix.to_scale()).to_4x4()
                    else:
                        # Apply only the scale part from the child's matrix
                        scale_matrix = Matrix.Diagonal(child_matrix.to_scale()).to_4x4()

                    # Scale should be applied first, so prepend it
                    reference_frame = scale_matrix @ reference_frame
                    self.logger.debug(f"Freezed transformations, translation is: {reference_frame.translation}")
                else:
                    # When not freezing transformations, the reference frame is the child's matrix_world and the child
                    # will end up with same transformations as the root
                    self.logger.debug("Didn't freeze any transformations")
                    reference_frame = child.matrix_world

                self.logger.debug(f"child mesh: {child.name} with generic value: {g_value}")
                self.i3d.shapes[self.shape_id].append_from_evaluated_mesh_generic(
                    EvaluatedMesh(self.i3d, child, reference_frame=reference_frame), g_value)
                self.logger.debug(f"Collected child mesh: {child.name}")

                # Correct matrix reset for all transformations:
                # reference_frame = child.matrix_world @ empty_object.matrix_world @ empty_object.matrix_world.inverted()

    def populate_xml_element(self):
        self.logger.debug("Populating XML element for MergeChildrenRoot")
        super().populate_xml_element()
