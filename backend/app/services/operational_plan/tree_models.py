from __future__ import annotations
from typing import Optional, List, Literal, Any
from uuid import uuid4
from pydantic import BaseModel, Field
from datetime import datetime


NodeType = Literal["preamble", "toc", "section", "subsection", "appendix"]


class TreeNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: NodeType = "section"
    title_ne: str = ""
    title_en: str = ""
    number: Optional[str] = None
    level: int = 0
    content_type: Literal["richtext", "chart", "table", "map", "static_table"] = "richtext"
    content: str = ""
    chart_type: Optional[str] = None
    table_id: Optional[str] = None
    map_type: Optional[str] = None
    static_table: Optional[dict] = None
    children: List[TreeNode] = []
    is_locked: bool = False
    hidden_in_export: bool = False
    deleted: bool = False
    last_modified: Optional[str] = None

    def touch(self):
        self.last_modified = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> TreeNode:
        if "children" in data:
            data["children"] = [cls.from_dict(c) if isinstance(c, dict) else c for c in data["children"]]
        return cls(**data)


class DocumentTree(BaseModel):
    tree: List[TreeNode] = []
    metadata: dict = Field(default_factory=lambda: {
        "auto_numbering": True,
        "language": "NP",
        "version": "2.0"
    })


class TreeOperations:

    @staticmethod
    def find_node(tree: List[TreeNode], node_id: str) -> Optional[TreeNode]:
        for node in tree:
            if node.id == node_id:
                return node
            found = TreeOperations.find_node(node.children, node_id)
            if found:
                return found
        return None

    @staticmethod
    def find_parent(tree: List[TreeNode], node_id: str) -> Optional[TreeNode]:
        for node in tree:
            if any(c.id == node_id for c in node.children):
                return node
            found = TreeOperations.find_parent(node.children, node_id)
            if found:
                return found
        return None

    @staticmethod
    def add_node(tree: List[TreeNode], parent_id: Optional[str], new_node: TreeNode, position: int = -1) -> List[TreeNode]:
        if parent_id is None:
            if position < 0 or position >= len(tree):
                tree.append(new_node)
            else:
                tree.insert(position, new_node)
            return tree
        parent = TreeOperations.find_node(tree, parent_id)
        if parent is None:
            raise ValueError(f"Parent node {parent_id} not found")
        if position < 0 or position >= len(parent.children):
            parent.children.append(new_node)
        else:
            parent.children.insert(position, new_node)
        return tree

    @staticmethod
    def update_node(tree: List[TreeNode], node_id: str, updates: dict) -> List[TreeNode]:
        node = TreeOperations.find_node(tree, node_id)
        if node is None:
            raise ValueError(f"Node {node_id} not found")
        for key, value in updates.items():
            if key in ("id", "children"):
                continue
            setattr(node, key, value)
        node.touch()
        return tree

    @staticmethod
    def delete_node(tree: List[TreeNode], node_id: str) -> List[TreeNode]:
        for i, node in enumerate(tree):
            if node.id == node_id:
                if node.is_locked:
                    raise ValueError(f"Cannot delete locked node {node_id}")
                tree.pop(i)
                return tree
            try:
                TreeOperations.delete_node(node.children, node_id)
                return tree
            except ValueError:
                continue
        raise ValueError(f"Node {node_id} not found")

    @staticmethod
    def move_node(tree: List[TreeNode], node_id: str, new_parent_id: Optional[str], new_position: int = -1) -> List[TreeNode]:
        node_data = TreeOperations.find_node(tree, node_id)
        if node_data is None:
            raise ValueError(f"Node {node_id} not found")
        if node_data.is_locked:
            raise ValueError(f"Cannot move locked node {node_id}")

        tree = TreeOperations.delete_node(tree, node_id)
        tree = TreeOperations.add_node(tree, new_parent_id, node_data, new_position)
        return tree

    @staticmethod
    def flatten(tree: List[TreeNode]) -> List[TreeNode]:
        result = []
        for node in tree:
            result.append(node)
            result.extend(TreeOperations.flatten(node.children))
        return result
