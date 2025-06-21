import logging
import bpy

from .node import (SceneGraphNode, TransformGroupNode)
from .shape import (ShapeNode, EvaluatedMesh)

from .. import debugging

from ..i3d import I3D


class MergeGroupChild(TransformGroupNode):
    pass


class MergeGroupRoot(ShapeNode):
    def __init__(self, id_: int, merge_group_object: bpy.types.Object, i3d: I3D,
                 parent: SceneGraphNode | None = None):
        self.merge_group_name = i3d.merge_groups[merge_group_object.i3d_merge_group_index].name
        self.skin_bind_ids = f"{id_:d} "
        super().__init__(id_=id_, shape_object=merge_group_object, i3d=i3d, parent=parent)

        self.add_shape()
        its = self.i3d.shapes[self.shape_id]
        if not hasattr(its, '_root_mesh_queued'):
            its.append_from_evaluated_mesh(
                EvaluatedMesh(self.i3d, self.blender_object, node=self)
            )
            its._root_mesh_queued = True

    def add_shape(self):
        """
        Overrides the base add_shape. Its only job is to create the shape
        with the correct name and flags. Safe to call multiple times.
        """
        if self.shape_id is not None:
            return

        self.logger.debug(f"Creating shape for MergeGroupRoot '{self.merge_group_name}'")
        self.shape_id = self.i3d.add_shape(
            EvaluatedMesh(self.i3d, self.blender_object, node=self),
            self.merge_group_name,
            is_merge_group=True
        )
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def add_mergegroup_child(self, child: MergeGroupChild):
        """
        Adds a child mesh to the processing queue.
        """
        # The shape is guaranteed to exist because the root's __init__ called add_shape.
        self.logger.debug(f"Adding Child '{child.blender_object.name}' to MergeGroup '{self.merge_group_name}'")
        self.skin_bind_ids += f"{child.id:d} "
        # For each child, add skinBindNodeIds, or else we will end up with "root" as the only skin bind node.
        self._write_attribute('skinBindNodeIds', self.skin_bind_ids[:-1])
        self.i3d.shapes[self.shape_id].append_from_evaluated_mesh(
            EvaluatedMesh(self.i3d, child.blender_object, reference_frame=self.blender_object.matrix_world)
        )

    def populate_xml_element(self):
        """
        This is called during the main traversal. Because the ITS for merge groups
        is deferred, this method only needs to handle the node-level attributes.
        """
        # The base class will call add_shape, which is fine.
        # It will also write shapeId and materialIds.
        super().populate_xml_element()
        # Write the specific attribute for this node type.
        self._write_attribute('skinBindNodeIds', self.skin_bind_ids[:-1])

        # self.logger.debug(f"Checking materialIds: {self.i3d.shapes[self.shape_id].material_ids}")
        # self._write_attribute('materialIds', ' '.join(map(str, self.i3d.shapes[self.shape_id].material_ids)))


class MergeGroup:
    def __init__(self, name: str):
        self.name = name
        self.root_node: [MergeGroupRoot, None] = None
        self.child_nodes: list[MergeGroupChild] = list()  # List of child nodes for the merge group
        self.logger = debugging.ObjectNameAdapter(logging.getLogger(f"{__name__}.{type(self).__name__}"),
                                                  {'object_name': self.name})
        self.logger.debug("Initialized merge group")

    # Should only be run once, when the root node is found.
    def set_root(self, root_node: MergeGroupRoot):
        self.root_node = root_node
        if self.child_nodes:
            self.logger.debug(f"{len(self.child_nodes)} were added before the root node was found")
            for child in self.child_nodes:
                self.root_node.add_mergegroup_child(child)
        else:
            self.logger.debug("No pre-added children before root was found")
        return self.root_node

    def add_child(self, child_node: MergeGroupChild):
        self.child_nodes.append(child_node)
        if self.root_node is not None:
            self.root_node.add_mergegroup_child(self.child_nodes[-1])
        return self.child_nodes[-1]
