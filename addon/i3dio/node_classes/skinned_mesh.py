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
                 parent: SceneGraphNode | None, root_node: SkinnedMeshRootNode):
        self.i3d = i3d
        self.is_child_of = False
        self.parent = parent
        self.root_node = root_node
        # Store child of target for transformation calculations in case its not processed yet
        self.deferred_target: bpy.types.Object | None = None

        if pose_bone := self.root_node.blender_object.pose.bones.get(bone_object.name):
            child_of = next((c for c in pose_bone.constraints if c.type == 'CHILD_OF'), None)
            if child_of and (target := child_of.target) and target in i3d.all_objects_to_export:
                self.is_child_of = True
                if target in i3d.processed_objects:
                    self.parent = i3d.processed_objects[target]
                else:
                    i3d.logger.debug(f"Deferring CHILD_OF constraint for {bone_object}, target: {target}")
                    self.deferred_target = target
                    i3d.deferred_constraints.append((self, target))

        super().__init__(id_=id_, empty_object=bone_object, i3d=i3d, parent=self.parent)

    def _matrix_to_i3d_space(self, matrix: mathutils.Matrix, skip_inversion: bool = False) -> mathutils.Matrix:
        if skip_inversion:
            # Bones are already in their armature's local space, so no need to apply the inverse transformation.
            return self.i3d.conversion_matrix @ matrix
        return self.i3d.conversion_matrix @ matrix @ self.i3d.conversion_matrix.inverted()

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        """
        Compute the bone's transformation matrix in I3D space, considering different parenting scenarios:
        - Direct parenting to another bone.
        - CHILD_OF constraints targeting other objects.
        - Collapsed armatures where the armature itself is removed.
        """
        if isinstance(self.parent, SkinnedMeshBoneNode):
            # Bone is parented to another bone; its local transform is already correct.
            return self.blender_object.parent.matrix_local.inverted() @ self.blender_object.matrix_local

        bone_matrix = self._matrix_to_i3d_space(self.blender_object.matrix_local, skip_inversion=True)
        armature_matrix = self._matrix_to_i3d_space(self.root_node.blender_object.matrix_local)

        if self.is_child_of or self.deferred_target is not None:
            # Handle CHILD_OF constraint to preserve the bone’s visual transform.
            # 1. Convert target's world matrix to I3D space.
            # 2. Invert it to move the bone into the target's local space.
            # 3. Apply the armature transform and the bone’s local matrix to retain offsets.
            target = self.deferred_target or self.parent.blender_object
            target_matrix = self._matrix_to_i3d_space(target.matrix_world)
            return target_matrix.inverted() @ armature_matrix @ bone_matrix

        # Default case: Bones inherit their transform directly from the armature.
        if self.root_node.is_collapsed:
            # When collapsing armatures, the armature itself is removed from the hierarchy.
            # Root bones effectively take its place, so we apply the armature's transform to the bone.
            return armature_matrix @ bone_matrix

        # Otherwise, the bone's matrix is already relative to the armature.
        return bone_matrix

    def reparent(self, new_parent: SceneGraphNode | None) -> None:
        """Reparents bone node to a new parent in the scene graph or moves it to the scene root."""
        self.logger.debug(f"Reparenting bone {self.blender_object.name} from {self.parent} to {new_parent}")
        # Detach from the current parent if it exists
        if self.parent is not None:
            self.parent.element.remove(self.element)
            self.parent.children.remove(self)
        # Assign new parent or move to scene root
        if new_parent:
            new_parent.add_child(self)
            new_parent.element.append(self.element)
        else:
            self.i3d.scene_root_nodes.append(self)
            self.i3d.xml_elements['Scene'].append(self.element)
        self.parent = new_parent


class SkinnedMeshRootNode(TransformGroupNode):
    def __init__(self, id_: int, armature_object: bpy.types.Object, i3d: I3D, parent: SceneGraphNode | None = None):
        # The skinBindID mapped with bone names for easy reference. An ordered dict is important,
        # but dicts are ordered in Python 3.7+
        self.bones: List[SkinnedMeshBoneNode] = list()
        self.bone_mapping: Dict[str, int] = {}
        self.armature_object = armature_object
        self.is_collapsed = armature_object.i3d_attributes.collapse_armature
        super().__init__(id_=id_, empty_object=armature_object, i3d=i3d, parent=None if self.is_collapsed else parent)

        bone_parent = parent if self.is_collapsed else self
        for bone in armature_object.data.bones:
            # Only add root bones, bone children will be added recursively
            if bone.parent is None:
                self._add_bone(bone, bone_parent)

    def _add_bone(self, bone_object: bpy.types.Bone, parent: SceneGraphNode | None) -> None:
        """Recursively adds a bone and its children to the scene graph."""
        self.logger.debug(f"Adding bone {bone_object.name} hey to {parent}")
        bone_node = self.i3d.add_bone(bone_object, parent, self)
        self.bones.append(bone_node)
        self.bone_mapping[bone_object.name] = bone_node.id

        for child_bone in bone_object.children:
            self._add_bone(child_bone, bone_node)

    def organize_armature_hierarchy(self, parent: SceneGraphNode | None) -> None:
        """Solves the parenting of the armature and its bones in the scene graph."""
        if self.is_collapsed:
            # When collapsing armatures, the armature itself is removed from the hierarchy.
            # Root bones take its place and must be reparented.
            for bone in self.bones:
                if not bone.deferred_target and bone.parent in {None, self}:
                    bone.reparent(parent)
            return  # No further processing needed for collapsed armatures

        # Non-collapsed armatures remain in the hierarchy
        if self.parent is None:
            self.parent = parent  # If the armature was created via a modifier, its parent was not set.

        if self.parent is parent and self.parent is not None:
            return  # Already in the correct hierarchy

        if parent is not None:
            parent.add_child(self)
            parent.element.append(self.element)
        else:  # No parent -> move the armature to the scene root
            self.i3d.scene_root_nodes.append(self)
            self.i3d.xml_elements['Scene'].append(self.element)
        self.i3d.processed_objects[self.blender_object] = self

    def add_i3d_mapping_to_xml(self):
        # Skip exporting i3d mapping if 'collapse_armature' setting is enabled, because the armature is not exported
        if not self.is_collapsed:
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
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object, node=self),
                                           self.skinned_mesh_name, bone_mapping=self.bone_mapping)
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def populate_xml_element(self):
        super().populate_xml_element()

        skin_bind_ids = " ".join(map(str, self.i3d.shapes[self.shape_id].final_skin_bind_node_ids))
        self.logger.debug(f"Skin bind IDs: {skin_bind_ids}")
        self._write_attribute('skinBindNodeIds', skin_bind_ids)
