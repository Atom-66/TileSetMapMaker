from typing import Dict, List, Optional, Any


class CategoryNode:
    """Represents a category or subcategory in the asset hierarchy."""

    def __init__(self, name: str, parent: Optional["CategoryNode"] = None):
        self.name = name.strip()
        self.parent = parent
        self.children: Dict[str, CategoryNode] = {}
        self.asset_ids: List[str] = []

    @property
    def path(self) -> str:
        if self.parent and self.parent.name:
            parent_path = self.parent.path
            return f"{parent_path}/{self.name}" if parent_path else self.name
        return self.name

    def add_child(self, name: str) -> "CategoryNode":
        name = name.strip()
        if name not in self.children:
            self.children[name] = CategoryNode(name, parent=self)
        return self.children[name]

    def remove_child(self, name: str) -> Optional["CategoryNode"]:
        return self.children.pop(name.strip(), None)

    def get_all_asset_ids(self) -> List[str]:
        result = list(self.asset_ids)
        for child in self.children.values():
            result.extend(child.get_all_asset_ids())
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "children": {name: child.to_dict() for name, child in self.children.items()},
            "asset_ids": self.asset_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent: Optional["CategoryNode"] = None) -> "CategoryNode":
        node = cls(name=data.get("name", ""), parent=parent)
        node.asset_ids = list(data.get("asset_ids", []))
        for child_name, child_data in data.get("children", {}).items():
            child_node = cls.from_dict(child_data, parent=node)
            node.children[child_name] = child_node
        return node


class CategoryTree:
    """Manages the full category tree."""

    def __init__(self, seed_defaults: bool = False):
        self.root = CategoryNode("")
        if seed_defaults:
            self.ensure_default_structure()

    def ensure_default_structure(self):
        defaults = [
            "Terrain/Grass",
            "Terrain/Dirt",
            "Terrain/Sand",
            "Terrain/Water",
            "Terrain/Stone",
            "Objects/Trees",
            "Objects/Rocks",
            "Objects/Plants",
            "Objects/Decorations",
            "Buildings/Houses",
            "Buildings/Walls",
            "Buildings/Doors",
            "Interior/Furniture",
            "Interior/Decorations",
            "Custom",
        ]
        for p in defaults:
            self.add_category_path(p)

    def add_category_path(self, path: str) -> CategoryNode:
        clean_path = path.strip("/").strip()
        if not clean_path:
            return self.root
        parts = [p.strip() for p in clean_path.split("/") if p.strip()]
        curr = self.root
        for part in parts:
            curr = curr.add_child(part)
        return curr

    def get_node(self, path: str) -> Optional[CategoryNode]:
        clean_path = path.strip("/").strip()
        if not clean_path:
            return self.root
        parts = [p.strip() for p in clean_path.split("/") if p.strip()]
        curr = self.root
        for part in parts:
            if part not in curr.children:
                return None
            curr = curr.children[part]
        return curr

    def delete_category(self, path: str) -> bool:
        clean_path = path.strip("/").strip()
        if not clean_path:
            return False
        parts = [p.strip() for p in clean_path.split("/") if p.strip()]
        parent_path = "/".join(parts[:-1])
        leaf_name = parts[-1]
        parent_node = self.get_node(parent_path)
        if parent_node and leaf_name in parent_node.children:
            del parent_node.children[leaf_name]
            return True
        return False

    def rename_category(self, old_path: str, new_name: str) -> Optional[str]:
        node = self.get_node(old_path)
        if not node or not node.parent:
            return None
        new_name = new_name.strip()
        if not new_name or new_name in node.parent.children:
            return None
        del node.parent.children[node.name]
        node.name = new_name
        node.parent.children[new_name] = node
        return node.path

    def move_category(self, src_path: str, dst_parent_path: str) -> Optional[str]:
        src_node = self.get_node(src_path)
        if not src_node or not src_node.parent:
            return None
        destination = dst_parent_path.strip("/")
        if destination == src_node.path or destination.startswith(src_node.path + "/"):
            return None
        dst_parent = self.get_node(dst_parent_path)
        if not dst_parent:
            dst_parent = self.add_category_path(dst_parent_path)
        # Check that destination is not a descendant of source
        temp = dst_parent
        while temp and temp != self.root:
            if temp == src_node:
                return None  # Cannot move a folder into its own child
            temp = temp.parent

        if src_node.parent == dst_parent:
            return src_node.path
        if src_node.name in dst_parent.children:
            return None
        del src_node.parent.children[src_node.name]
        src_node.parent = dst_parent
        dst_parent.children[src_node.name] = src_node
        return src_node.path

    def get_all_paths(self) -> List[str]:
        paths: List[str] = []

        def _traverse(node: CategoryNode):
            if node != self.root and node.path:
                paths.append(node.path)
            for child in sorted(node.children.values(), key=lambda c: c.name):
                _traverse(child)

        _traverse(self.root)
        return paths

    def to_dict(self) -> Dict[str, Any]:
        return self.root.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CategoryTree":
        tree = cls()
        tree.root = CategoryNode.from_dict(data)
        return tree
