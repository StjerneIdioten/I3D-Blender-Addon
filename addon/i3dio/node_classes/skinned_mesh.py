"""
A lot of classes in this file is purely to have different classes for different objects that are functionally the same,
but it helps with debugging big trees and seeing the structure.
"""
from __future__ import annotations
from typing import (Dict, List)
from collections import ChainMap
import mathutils
import bpy

from .node import (TransformGroupNode, SceneGraphNode)
from .shape import (ShapeNode, EvaluatedMesh)
from ..i3d import I3D
from .. import xml_i3d


class SkinnedMeshBoneNode(TransformGroupNode):
    def __init__(self, id_: int, bone_object: bpy.types.Bone, i3d: I3D,
                 parent: SkinnedMeshRootNode | SkinnedMeshBoneNode | None,
                 root_node: SkinnedMeshRootNode):
        self.i3d = i3d
        self.is_child_of = False
        self.parent = parent
        self.armature_object = root_node.blender_object
        # Store child of target for transformation calculations in case its not processed yet
        self.deferred_target: bpy.types.Object | None = None

        if pose_bone := self.armature_object.pose.bones.get(bone_object.name):
            if child_of := next((c for c in pose_bone.constraints if c.type == 'CHILD_OF'), None):
                i3d.logger.debug("child_of constraint found")
                # Check if the target object is in the export list, if not it will just continue with original parent
                if (target := child_of.target) and target in i3d.all_objects_to_export:
                    self.is_child_of = True
                    if target in i3d.processed_objects:
                        self.parent = i3d.processed_objects[target]
                    else:
                        i3d.logger.debug(f"Deferring CHILD_OF constraint for {bone_object}, target: {target}")
                        self.deferred_target = target
                        i3d.deferred_constraints.append((self, target))

        super().__init__(id_=id_, empty_object=bone_object, i3d=i3d, parent=self.parent)

    def _matrix_to_i3d_space(self, matrix: mathutils.Matrix, is_bone: bool = False) -> mathutils.Matrix:
        if is_bone:
            # Bones are already in their armature's local space, so no need to apply the inverse transformation.
            return self.i3d.conversion_matrix @ matrix
        return self.i3d.conversion_matrix @ matrix @ self.i3d.conversion_matrix.inverted()

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        """
        Calculate the bone's transformation matrix in I3D space, considering parenting and deferred constraints.
        Handles scenarios like direct parenting, deferred CHILD_OF constraints, and collapsed armatures.
        """
        if isinstance(self.parent, SkinnedMeshBoneNode):
            # For bones parented to other bones, matrix_local is relative to the parent.
            # No transformation to I3D space is needed because the orientation is already relative to the parent bone.
            return self.blender_object.parent.matrix_local.inverted() @ self.blender_object.matrix_local

        bone_matrix = self._matrix_to_i3d_space(self.blender_object.matrix_local, is_bone=True)
        armature_matrix = self._matrix_to_i3d_space(self.armature_object.matrix_local)

        if (self.is_child_of and not self.deferred_target and self.parent is not None) \
                or self.deferred_target is not None:
            # Bone is parented to a CHILD_OF constraint target.
            # To maintain its visual position/orientation when re-parenting:
            #  1. Move the bone into the target’s local space by applying the inverse of its world matrix.
            #  2. Apply the armature’s local matrix (converted to I3D space) to include armature transformations.
            #  3. Multiply by the bone’s local matrix to retain its relative offsets and rotations.
            # This ensures the bone remains visually unchanged after re-parenting in I3D space.
            target = self.deferred_target or self.parent.blender_object
            target_matrix = self._matrix_to_i3d_space(target.matrix_world)
            return target_matrix.inverted() @ armature_matrix @ bone_matrix

        # For bones parented directly to the armature, matrix_local already represents their transform
        # relative to the armature, so no additional adjustments are needed.
        if self.i3d.settings['collapse_armatures']:
            # If collapse_armatures is enabled, the armature is not added to the scene graph.
            # The root bone(s) in the armature replace the armature in the hierarchy,
            # so multiply its matrix with the armature matrix to preserve the correct transformation.
            return armature_matrix @ bone_matrix

        # If armature is not collapsed, the bone's matrix is already relative to the armature.
        return bone_matrix

    def reparent(self, new_parent: SceneGraphNode) -> None:
        """Reparents bone node to a new parent in the scene graph."""
        if self.parent is not None:
            self.logger.debug(f"Detaching from {self.parent}")
            self.parent.element.remove(self.element)
            self.parent.children.remove(self)
        elif self in self.i3d.scene_root_nodes:
            self.logger.debug("Detaching from scene root")
            self.i3d.scene_root_nodes.remove(self)
            self.i3d.xml_elements['Scene'].remove(self.element)

        self.logger.debug(f"Attaching to {new_parent}")
        self.parent = new_parent
        new_parent.add_child(self)
        new_parent.element.append(self.element)


class SkinnedMeshRootNode(TransformGroupNode):
    def __init__(self, id_: int, armature_object: bpy.types.Object, i3d: I3D, parent: SceneGraphNode | None = None):
        # The skinBindID mapped with bone names for easy reference. An ordered dict is important,
        # but dicts are ordered in Python 3.7+
        self.bones: List[SkinnedMeshBoneNode] = list()
        self.bone_mapping: Dict[str, int] = {}
        self.armature_object = armature_object
        self.collapsed = i3d.settings['collapse_armatures']
        super().__init__(id_=id_, empty_object=armature_object, i3d=i3d, parent=None if self.collapsed else parent)

        for bone in armature_object.data.bones:
            # Only add root bones, bone children will be added recursively
            if bone.parent is None:
                self._add_bone(bone, parent if self.collapsed else self)

    def _add_bone(self, bone_object: bpy.types.Bone, parent: SceneGraphNode | None):
        """Recursively adds a bone and its children to the scene graph."""
        self.logger.debug(f"Adding bone {bone_object.name} to {parent}")
        bone_node = self.i3d.add_bone(bone_object, parent, self)
        self.bones.append(bone_node)
        self.bone_mapping[bone_object.name] = bone_node.id

        for child_bone in bone_object.children:
            self._add_bone(child_bone, bone_node)

    def add_i3d_mapping_to_xml(self):
        # Skip exporting i3d mapping if 'collapse_armatures' setting is enabled, because the armature is not exported
        if not self.collapsed:
            super().add_i3d_mapping_to_xml()


class SkinnedMeshShapeNode(ShapeNode):
    def __init__(self, id_: int, skinned_mesh_object: bpy.types.Object, i3d: I3D, parent: SceneGraphNode | None = None):
        self.armature_nodes: list[SkinnedMeshRootNode] = [
            i3d.add_armature_from_modifier(modifier.object)
            for modifier in skinned_mesh_object.modifiers if modifier.type == 'ARMATURE'
        ]
        self.skinned_mesh_name = f"{xml_i3d.skinned_mesh_prefix}{skinned_mesh_object.data.name}"
        self.bone_mapping = ChainMap(*[armature.bone_mapping for armature in self.armature_nodes])
        super().__init__(id_=id_, shape_object=skinned_mesh_object, i3d=i3d, parent=parent)

    def add_shape(self):
        # Combine multiple bone mappings while ensuring unique bone names are handled correctly
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object), self.skinned_mesh_name,
                                           bone_mapping=self.bone_mapping)
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def populate_xml_element(self):
        super().populate_xml_element()
        vertex_group_binding = self.i3d.shapes[self.shape_id].vertex_group_ids
        self.logger.debug(f"Skinned groups: {vertex_group_binding}")

        skin_bind_ids = " ".join(
            str(self.bone_mapping[self.blender_object.vertex_groups[vertex_group_id].name])
            for vertex_group_id in sorted(vertex_group_binding, key=vertex_group_binding.get)
        )

        self._write_attribute('skinBindNodeIds', skin_bind_ids)
