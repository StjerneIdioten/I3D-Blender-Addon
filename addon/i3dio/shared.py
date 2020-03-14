"""This module contains shared functionality between the different modules of the i3dio addon"""
from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing
from typing import (Union)

import bpy


class Node:
    def __init__(self,
                 id_: int or None = None,
                 parent: Node or None = None):
        self.children = {}
        self.id = id_
        self.parent = parent
        self.i3d_elements = {'indexed_triangle_set': None,
                             'scene_node': None}
        self.indexed_triangle_element = None
        self.node_element = None

        if parent is not None:
            parent.add_child(self)

    def __str__(self):
        return f"{self.id}"

    def add_child(self, node: Node):
        self.children[node.id] = node
