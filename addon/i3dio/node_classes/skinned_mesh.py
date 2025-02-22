"""
A lot of classes in this file is purely to have different classes for different objects that are functionally the same,
but it helps with debugging big trees and seeing the structure.
"""
from __future__ import annotations
from typing import (Dict, List)
from collections import (ChainMap, namedtuple)
import mathutils
import bpy
import math

from .node import (TransformGroupNode, SceneGraphNode)
from .shape import (ShapeNode, EvaluatedMesh)
from ..i3d import I3D
from .. import xml_i3d


AssignParentResult = namedtuple('AssignParentResult', ['parent', 'is_child_of', 'deferred'])


class SkinnedMeshBoneNode(TransformGroupNode):
    def __init__(self, id_: int, bone_object: bpy.types.Bone, i3d: I3D,
                 parent: SkinnedMeshRootNode | SkinnedMeshBoneNode,
                 armature_object: bpy.types.Object):
        self.is_child_of = False
        self.parent = parent
        self.armature_object = armature_object

        if type(self.parent) is SkinnedMeshRootNode:
            if pose_bone := self.parent.blender_object.pose.bones.get(bone_object.name):
                i3d.logger.debug(f"pose_bone {pose_bone.name} found")
                if child_of := next((c for c in pose_bone.constraints if c.type == 'CHILD_OF'), None):
                    i3d.logger.debug(f"child_of {child_of.name} found")
                    if (target := child_of.target) and target in i3d.all_objects_to_export:
                        if target in i3d.processed_objects:
                            self.parent = i3d.processed_objects[target]
                        self.is_child_of = True

        super().__init__(id_=id_, empty_object=bone_object, i3d=i3d, parent=self.parent)

    def _matrix_to_i3d_space(self, matrix: mathutils.Matrix) -> mathutils.Matrix:
        return self.i3d.conversion_matrix @ matrix @ self.i3d.conversion_matrix.inverted()

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        """
        Calculate the bone's transformation matrix in I3D space, considering parenting and deferred constraints.
        Handles scenarios like direct parenting, deferred CHILD_OF constraints, and collapsed armatures.
        """
        self.logger.debug(f"What is self here? {self}, is_child_of: {self.is_child_of}, target: {self.target}")
        self.logger.debug(f"Calculating transform for {self.blender_object.name}")
        if self.blender_object.parent and isinstance(self.blender_object.parent, bpy.types.Bone):
            # For bones parented to other bones, matrix_local is relative to the parent.
            # No transformation to I3D space is needed because the orientation is already relative to the parent bone.
            return self.blender_object.parent.matrix_local.inverted() @ self.blender_object.matrix_local

        # Get the bone's transformation in armature space
        bone_matrix = self._matrix_to_i3d_space(self.blender_object.matrix_local)
        # Giants Engine expects bones to point along the Z-axis (Blender's visual alignment).
        # However, root bones in Blender internally align along the Y-axis.
        # Rotate -90° around X-axis to correct root bone orientation. Child bones remain unaffected.
        rot_fix = mathutils.Matrix.Rotation(math.radians(-90.0), 4, 'X')
        translation = bone_matrix.to_translation()
        bone_matrix = rot_fix @ bone_matrix.to_3x3().to_4x4()
        bone_matrix.translation = translation

        self.logger.debug(f"bone settings: {self.is_child_of} {self.target}")

        if self.is_child_of and self.parent.blender_object is not None:
            # Bone is parented to a CHILD_OF constraint target, collapse_armature doesn't matter here
            # Multiply the bone's local transform with the inverse of the parent object's world matrix
            # to correctly position it relative to its new parent
            parent_matrix = self._matrix_to_i3d_space(self.parent.blender_object.matrix_world)
            if self.armature_object is not None:
                # If the armature object is also present, include its local matrix in the calculation
                armature_matrix = self._matrix_to_i3d_space(self.armature_object.matrix_local)
                return parent_matrix.inverted() @ armature_matrix @ bone_matrix
            return parent_matrix.inverted() @ bone_matrix
        elif self.target is not None:
            # Bone is parented to a deferred CHILD_OF constraint target
            # Multiply the bone's local transform with the inverse of the target's world matrix
            # to correctly position it relative to its new parent
            target_matrix = self._matrix_to_i3d_space(self.target.matrix_world)
            return target_matrix.inverted() @ bone_matrix

        # For bones parented directly to the armature, matrix_local already represents their transform
        # relative to the armature, so no additional adjustments are needed.
        if self.i3d.settings['collapse_armatures'] and self.parent.blender_object is not None:
            # If collapse_armatures is enabled, the armature is removed in the I3D.
            # The root bone replaces the armature in the hierarchy,
            # so multiply its matrix with the armature matrix to preserve the correct transformation.
            armature_matrix = self._matrix_to_i3d_space(self.parent.blender_object.matrix_local)
            return armature_matrix @ bone_matrix

        if self.armature_object is not None:
            # In some rare cases when armature is collapsed and bone ends up being parented to scene root,
            # we have to multiply the bone's matrix with its armature's world matrix to ensure correct positioning.
            armature_matrix = self._matrix_to_i3d_space(self.armature_object.matrix_world)
            return armature_matrix @ bone_matrix

        # Return the bone's local transform unchanged, as it is already correct relative to the armature.
        return bone_matrix


class SkinnedMeshRootNode(TransformGroupNode):
    def __init__(self, id_: int, armature_object: bpy.types.Object, i3d: I3D, parent: SceneGraphNode | None = None):
        # The skinBindID essentially, but mapped with the bone names for easy reference. An ordered dict is important
        # but dicts should be ordered going forwards in python
        self.bones: List[SkinnedMeshBoneNode] = list()
        self.bone_mapping: Dict[str, int] = {}
        self.armature_object = armature_object

        super().__init__(id_=id_, empty_object=armature_object, i3d=i3d, parent=parent)

        for bone in armature_object.data.bones:
            if bone.parent is None:
                self._add_bone(bone, self)

    def add_i3d_mapping_to_xml(self):
        """Wont export armature mapping, if 'collapsing armatures' is enabled"""
        if not self.i3d.settings['collapse_armatures']:
            super().add_i3d_mapping_to_xml()

    def _add_bone(self, bone_object: bpy.types.Bone, parent: SceneGraphNode):
        """Recursive function for adding a bone along with all of its children"""
        target = None
        is_child_of = False

        # Check for CHILD_OF constraint
        """ if (pose_bone := self.blender_object.pose.bones.get(bone_object.name)) is not None:
            child_of = next((c for c in pose_bone.constraints if c.type == 'CHILD_OF'), None)
            if child_of:
                if not child_of.target:
                    self.logger.warning(f"CHILD_OF constraint on {bone_object.name} has no target. Ignoring.")
                else:
                    target = child_of.target
                    result = self.assign_parent(bone_object, parent, target)
                    parent = result.parent
                    is_child_of = result.is_child_of

                    if result.deferred:
                        self.i3d.deferred_constraints.append((self.armature_object, bone_object, target))
                        self.logger.debug(f"Deferred constraint added for: {bone_object}, target: {target}") """

        self.bones.append(self.i3d.add_bone(bone_object, parent, is_child_of=is_child_of,
                                            armature_object=self.armature_object, target=target))
        current_bone = self.bones[-1]
        self.bone_mapping[bone_object.name] = current_bone.id

        for child_bone in bone_object.children:
            self._add_bone(child_bone, current_bone)

    def update_bone_parent(self, parent: SceneGraphNode = None,
                           custom_target: SceneGraphNode = None, bone: SkinnedMeshBoneNode = None):
        """Updates the parent of bones"""
        if custom_target is not None and bone is not None:
            self._assign_bone_parent(bone, custom_target)
        else:
            for bone in self.bones:
                if bone.parent == self:
                    new_parent = parent or None
                    self._assign_bone_parent(bone, new_parent)

    def _assign_bone_parent(self, bone: SkinnedMeshBoneNode, new_parent: SceneGraphNode):
        """Assigns a new parent to a bone and updates the scene graph"""
        self.logger.debug(f"Updating parent for {bone} to {new_parent}")
        # Remove bone from its current parent
        if bone.parent == self:
            self.logger.debug(f"Removing {bone} from current parent")
            self.element.remove(bone.element)
            self.children.remove(bone)

        # Add to the new parent or scene root
        if new_parent:
            if bone in self.i3d.scene_root_nodes:
                # If collapse armature is enabled the bone would have moved to the scene root,
                # but since we are now moving it to a new parent we have to remove it from the scene root
                # Or else we can get problems with i3dmappings
                self.logger.debug(f"Removing {bone} from scene root")
                self.i3d.scene_root_nodes.remove(bone)
                self.i3d.xml_elements['Scene'].remove(bone.element)
            self.logger.debug(f"Adding {bone} to {new_parent}")
            bone.parent = new_parent
            new_parent.add_child(bone)
            new_parent.element.append(bone.element)
        else:
            self.logger.debug(f"Adding {bone} to scene root")
            bone.parent = None
            self.i3d.scene_root_nodes.append(bone)
            self.i3d.xml_elements['Scene'].append(bone.element)

    def assign_parent(self, bone_object: bpy.types.Bone, parent: SceneGraphNode,
                      target: bpy.types.Object) -> AssignParentResult:
        """
        Assign the parent for a bone. Returns the assigned parent, whether the bone is a child of a target,
        and whether the assignment is deferred.
        """
        if target in self.i3d.processed_objects:
            # Target is processed, use it as the parent
            self.logger.debug(f"Target {target} is processed. Assigning as parent for {bone_object}.")
            return AssignParentResult(parent=self.i3d.processed_objects[target], is_child_of=True, deferred=False)

        if target not in self.i3d.all_objects_to_export:
            # Target is not in the export list, fallback to the original parent
            self.logger.debug(f"Target {target} is not in the export list. Using original parent for {bone_object}.")
            return AssignParentResult(parent=parent, is_child_of=False, deferred=False)

        # Defer the constraint and temporarily keep the original parent
        self.logger.debug(f"Deferring CHILD_OF constraint for {bone_object}, target: {target}")
        return AssignParentResult(parent=parent, is_child_of=False, deferred=True)


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
