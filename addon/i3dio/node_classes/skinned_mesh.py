import bpy

from . import node
from .node import (TransformGroupNode, SceneGraphNode)
from .shape import (ShapeNode, EvaluatedMesh)


class SkinnedMeshBone(SceneGraphNode):
    pass


class SkinnedMesh(TransformGroupNode):
    pass


class SkinnedMeshNode(ShapeNode):
    pass
