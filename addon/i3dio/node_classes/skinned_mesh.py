"""
A lot of classes in this file is purely to have different classes for different objects that are functionally the same,
but it helps with debugging big trees and seeing the structure.
"""
from __future__ import annotations
from collections import ChainMap
import mathutils
import bpy

from .node import (TransformGroupNode, SceneGraphNode)
from .shape import (ShapeNode, EvaluatedMesh, IndexedTriangleSet)
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
            if child_of and (target := child_of.target) in i3d.all_objects_to_export:
                self.is_child_of = True
                if target in i3d.processed_objects:
                    self.parent = i3d.processed_objects[target]
                else:
                    i3d.logger.debug(f"Deferring CHILD_OF constraint for {bone_object}, target: {target}")
                    self.deferred_target = target
                    i3d.deferred_constraints.append((self, target))

        super().__init__(id_=id_, empty_object=bone_object, i3d=i3d, parent=self.parent)

        # Defer only when the final parent context is unknown/unstable:
        #   - CHILD_OF target not processed yet, OR
        #   - top-level bone of a collapsed armature (not child-of-bone, not resolved CHILD_OF)
        is_child_bone = isinstance(self.parent, SkinnedMeshBoneNode)
        has_resolved_childof = (self.is_child_of and self.deferred_target is None)
        self.defer_transform = (
            (self.deferred_target is not None)
            or (self.root_node.is_collapsed and not is_child_bone and not has_resolved_childof)
        )

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        """
        Computes the bone's final transformation matrix in I3D space.
        This is complex because it must handle multiple parenting scenarios correctly.
        """
        # Case 1: Bone is parented to another bone.
        # This is the simplest case. The bone's matrix_local is relative to its parent bone.
        if isinstance(self.parent, SkinnedMeshBoneNode):
            # Local relative to parent bone (already in i3d basis)
            return self.parent.blender_object.matrix_local.inverted_safe() @ self.blender_object.matrix_local

        # For all other cases, start with the bone's transform relative to the armature origin.
        # NOTE: skip_inversion=True because a bone's matrix is already in the armature's space.
        bone_in_armature_space = self.i3d.to_i3d_forward(self.blender_object.matrix_local)

        # Case 2: The bone has a CHILD_OF constraint to an external object.
        # The transform needs to be calculated relative to that external object.
        if self.is_child_of or self.deferred_target is not None:
            return self._get_child_of_transform(bone_in_armature_space)

        # Case 3: The armature is "collapsed" (not exported as a node in the scene).
        # The root bones must inherit the armature's world transform.
        if self.root_node.is_collapsed:
            if getattr(self.parent, "blender_object", None):
                parent_world = self.i3d.to_i3d(self.parent.blender_object.matrix_world)
            else:
                parent_world = mathutils.Matrix.Identity(4)
            armature_world = self.i3d.to_i3d(self.root_node.blender_object.matrix_world)
            # Apply bones new inverted parent transform into armature space and then into bone space.
            return parent_world.inverted_safe() @ armature_world @ bone_in_armature_space

        # Case 4 (Default): The bone is a root bone of a non-collapsed armature.
        # Its transform is already correct relative to the armature node.
        return bone_in_armature_space

    def _get_child_of_transform(self, bone_in_armature_space: mathutils.Matrix) -> mathutils.Matrix:
        """Calculates the bone's transform when it's constrained to an external object."""
        # The target object that the bone is a child of.
        target_object = self.deferred_target or self.parent.blender_object

        # Get the world matrices of the target and the armature, converted to I3D space.
        target_world_matrix = self.i3d.to_i3d(target_object.matrix_world)
        armature_world_matrix = self.i3d.to_i3d(self.root_node.blender_object.matrix_world)

        # To get the bone's final local transform relative to its new target parent, do:
        # (TargetWorld)^-1 * ArmatureWorld * BoneLocal
        # This effectively moves the bone from armature space to world space,
        # and then from world space into the target's local space.
        return target_world_matrix.inverted_safe() @ armature_world_matrix @ bone_in_armature_space

    def reparent(self, new_parent: SceneGraphNode | None) -> None:
        """Reparents bone node to a new parent in the scene graph or moves it to the scene root."""
        self.logger.debug(
            f"Reparenting bone '{self.blender_object.name}' from "
            f"'{self.parent.name if self.parent else 'Scene Root'}' to "
            f"'{new_parent.name if new_parent else 'Scene Root'}'"
        )
        super().reparent(new_parent)


class SkinnedMeshRootNode(TransformGroupNode):
    def __init__(self, id_: int, armature_object: bpy.types.Object, i3d: I3D, parent: SceneGraphNode | None = None):
        self.bones: list[SkinnedMeshBoneNode] = list()
        self.bone_mapping: dict[str, int] = {}
        self.armature_object = armature_object
        self.is_collapsed = armature_object.i3d_attributes.collapse_armature

        # Collapsed = do not append armature XML (pass None to base so no SubElement is created)
        # Still keep the Python-side parent so children under the armature can be redirected properly.
        xml_parent = None if self.is_collapsed else parent
        super().__init__(id_=id_, empty_object=armature_object, i3d=i3d, parent=xml_parent)
        self.defer_transform = True

        # Keep Python-side parent even when collapsed (no XML append happened above).
        if self.is_collapsed and parent is not None:
            self.parent = parent
            parent.add_child(self)

        # Build the bone hierarchy from the armature's bones.
        # The parent for all root bones is initially set to the armature node itself.
        # The reparenting logic in finalize_armature_parenting will fix this later.
        for bone in armature_object.data.bones:
            if bone.parent is None:
                self._add_bone(bone, self)  # Keep parent as the armature for now (it will be adjusted later)

    def _add_bone(self, bone_object: bpy.types.Bone, parent: SceneGraphNode | None) -> None:
        """Recursively adds a bone and its children to the scene graph."""
        self.logger.debug(f"Adding bone {bone_object.name} to {parent}")
        bone_node = self.i3d.add_bone(bone_object, parent, self)
        self.bones.append(bone_node)
        self.bone_mapping[bone_object.name] = bone_node.id

        for child_bone in bone_object.children:
            self._add_bone(child_bone, bone_node)

    def finalize_armature_parenting(self, final_parent: SceneGraphNode | None):
        """
        Finalizes the parenting for the armature and its bones in the scene graph.
        This is called when the armature is processed by the main scene traversal.
        """
        self.logger.debug(f"Finalizing hierarchy for armature '{self.name}' with final parent "
                          f"'{final_parent.name if final_parent else 'Scene Root'}'.")

        if self.is_collapsed:
            # No armature element in XML, move each top-level bone under final parent and write transforms once.
            for bone_node in self.bones:
                # Skip bones parented through CHILD_OF constraints, they will be handled separately.
                if bone_node.parent == self and not bone_node.is_child_of:
                    bone_node.reparent(final_parent)
                    bone_node.finalize_transform()
        else:
            # Armature node included in the export: attach it directly to the final parent
            self.reparent(final_parent)
            self.finalize_transform()
            for bone_node in self.bones:
                bone_node.finalize_transform()

    def add_i3d_mapping_to_xml(self):
        # Skip exporting i3d mapping if 'collapse_armature' is enabled, because the armature is not exported
        if not self.is_collapsed:
            super().add_i3d_mapping_to_xml()


class SkinnedMeshShapeNode(ShapeNode):
    def __init__(self, id_: int, skinned_mesh_object: bpy.types.Object, i3d: I3D, parent: SceneGraphNode | None = None):
        self.armature_nodes: list[SkinnedMeshRootNode] = [
            i3d.add_armature_from_modifier(modifier.object)
            for modifier in skinned_mesh_object.modifiers if modifier.type == 'ARMATURE' and modifier.object
        ]
        self.skinned_mesh_name = f"{xml_i3d.skinned_mesh_prefix}{skinned_mesh_object.data.name}"
        self.bone_mapping = ChainMap(*[armature.bone_mapping for armature in self.armature_nodes])
        super().__init__(id_=id_, shape_object=skinned_mesh_object, i3d=i3d, parent=parent)

    def _create_shape(self):
        self.shape_id = self.i3d.add_shape(
            EvaluatedMesh(self.i3d, self.blender_object, node=self),
            self.skinned_mesh_name, bone_mapping=self.bone_mapping
        )
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def populate_xml_element(self):
        super().populate_xml_element()

        its: IndexedTriangleSet = self.i3d.shapes[self.shape_id]
        if its.final_skin_bind_node_ids:
            skin_bind_ids = " ".join(map(str, its.final_skin_bind_node_ids))
            self.logger.debug(f"Writing Skin bind IDs: {skin_bind_ids}")
            self._write_attribute('skinBindNodeIds', skin_bind_ids)
        else:
            self.logger.warning(f"Mesh '{self.name}' is skinned but no matching bones were found in vertex groups.")
