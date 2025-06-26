import logging
import bpy

from .node import (SceneGraphNode, TransformGroupNode)
from .shape import (ShapeNode, EvaluatedMesh, IndexedTriangleSet)

from .. import debugging

from ..i3d import I3D


class MergeGroupChild(TransformGroupNode):
    pass


class MergeGroupRoot(ShapeNode):
    def __init__(self, id_: int, merge_group_object: bpy.types.Object, i3d: I3D,
                 parent: SceneGraphNode | None = None):
        self.merge_group_name = i3d.merge_groups[merge_group_object.i3d_merge_group_index].name
        self.skin_bind_node_ids: list[int] = []

        super().__init__(id_=id_, shape_object=merge_group_object, i3d=i3d, parent=parent)

        self.its: IndexedTriangleSet = self.i3d.shapes[self.shape_id]
        # Explicitly add this root object's mesh to its own IndexedTriangleSet
        self.its.append_from_evaluated_mesh(EvaluatedMesh(self.i3d, self.blender_object, node=self))
        self.register_skin_bind_id(self.id)  # Always include the root node in the skin bind IDs

    def _create_shape(self):
        """Overrides the base _create_shape to create a deferred IndexedTriangleSet specifically for a merge group."""
        self.logger.debug(f"Creating deferred shape for MergeGroupRoot '{self.merge_group_name}'")
        dummy_mesh = EvaluatedMesh(self.i3d, self.blender_object, node=self)
        self.shape_id = self.i3d.add_shape(dummy_mesh, self.merge_group_name, is_merge_group=True)
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def register_skin_bind_id(self, node_id: int):
        """Adds a node ID to the list for skin bind nodes."""
        if node_id not in self.skin_bind_node_ids:
            self.skin_bind_node_ids.append(node_id)
            self.skin_bind_node_ids.sort()
            id_string = " ".join(map(str, self.skin_bind_node_ids))
            self._write_attribute('skinBindNodeIds', id_string)
            self.logger.debug(f"Registered skin bind ID {node_id} for MergeGroup {self.merge_group_name!r}")

    def add_child(self, child: MergeGroupChild):
        """Adds a child mesh to the processing queue and registers its ID for skin binding."""
        self.logger.debug(f"Adding Child {child.blender_object.name!r} to MergeGroup {self.merge_group_name!r}")
        self.register_skin_bind_id(child.id)
        # Append the child's mesh data, transformed relative to this root's world matrix.
        self.its.append_from_evaluated_mesh(
            EvaluatedMesh(self.i3d, child.blender_object, reference_frame=self.blender_object.matrix_world)
        )

    def populate_xml_element(self):
        """Populates attributes known at creation time. `skinBindNodeIds` is handled by `register_skin_bind_id`"""
        super().populate_xml_element()


class MergeGroup:
    """Temporary collector to handle out-of-order processing of merge group nodes."""
    def __init__(self, name: str):
        self.name = name
        self.root_node: MergeGroupRoot | None = None
        self.child_nodes: list[MergeGroupChild] = []
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': self.name})
        self.logger.debug("Initialized merge group collector")

    # Should only be run once, when the root node is found.
    def set_root(self, root_node: MergeGroupRoot):
        """Assigns the root node and processes any children that were found before the root."""
        self.root_node = root_node
        self.logger.debug(f"Root node {root_node.name!r} set for merge group {self.name!r}.")
        # If there are any pre-existing children, register them with the root node.
        if self.child_nodes:
            self.logger.debug(f"Registering {len(self.child_nodes)} pre-existing children with the root.")
            for child in self.child_nodes:
                self.root_node.add_child(child)

    def add_child(self, child_node: MergeGroupChild) -> None:
        """Adds a child node to the collector and registers it with the root if the root already exists."""
        self.child_nodes.append(child_node)
        # If the root node is already set, immediately register the new child.
        if self.root_node is not None:
            self.root_node.add_child(child_node)
