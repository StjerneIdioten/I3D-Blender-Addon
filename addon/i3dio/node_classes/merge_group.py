import logging
from typing import (OrderedDict, Optional, List)
import bpy

from .node import (SceneGraphNode, TransformGroupNode)
from .shape import (ShapeNode, EvaluatedMesh)

from .. import (
            debugging,
            xml_i3d
)

from ..i3d import I3D


class MergeGroupChild(TransformGroupNode):
    pass


class MergeGroupRoot(ShapeNode):

    def __init__(self, id_: int, merge_group_object: [bpy.types.Object, None], i3d: I3D,
                 parent: [SceneGraphNode or None] = None):
        self.merge_group_name = i3d.merge_groups[merge_group_object.i3d_merge_group_index].name
        self.skin_bind_ids = f"{id_:d} "
        super().__init__(id_=id_, shape_object=merge_group_object, i3d=i3d, parent=parent)

    # Override default shape behaviour to use the merge group mesh name instead of the blender objects name
    def add_shape(self):
        self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object), self.merge_group_name, True)
        self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    def add_mergegroup_child(self, child: MergeGroupChild):
        self.logger.debug("Adding Child")
        self.skin_bind_ids += f"{child.id:d} "
        self._write_attribute('skinBindNodeIds', self.skin_bind_ids[:-1])
        self.i3d.shapes[self.shape_id].append_from_evaluated_mesh(
            EvaluatedMesh(self.i3d, child.blender_object, reference_frame=self.blender_object.matrix_world))

    def populate_xml_element(self):
        super().populate_xml_element()
        self._write_attribute('skinBindNodeIds', self.skin_bind_ids[:-1])


class MergeGroup:
    def __init__(self, name: str):
        self.name = name
        self.root_node: [MergeGroupRoot, None] = None
        self.child_nodes: List[MergeGroupChild] = list()  # List of child nodes for the merge group
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
