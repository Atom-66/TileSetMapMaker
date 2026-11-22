import uuid
from typing import List, Dict, Any, Optional


class AssetSet:
    """A logical collection of asset references across categories (e.g. 'Forest Location')."""

    def __init__(
        self,
        name: str = "Nowy zestaw",
        set_id: Optional[str] = None,
        asset_ids: Optional[List[str]] = None,
        is_favorite: bool = False,
        description: str = "",
    ):
        self.id = set_id or str(uuid.uuid4())
        self.name = name
        self.asset_ids = asset_ids or []
        self.is_favorite = is_favorite
        self.description = description

    def add_asset(self, asset_id: str) -> None:
        if asset_id not in self.asset_ids:
            self.asset_ids.append(asset_id)

    def remove_asset(self, asset_id: str) -> bool:
        if asset_id in self.asset_ids:
            self.asset_ids.remove(asset_id)
            return True
        return False

    def move_asset(self, from_idx: int, to_idx: int) -> bool:
        if 0 <= from_idx < len(self.asset_ids) and 0 <= to_idx < len(self.asset_ids):
            item = self.asset_ids.pop(from_idx)
            self.asset_ids.insert(to_idx, item)
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "asset_ids": self.asset_ids,
            "is_favorite": self.is_favorite,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetSet":
        return cls(
            name=data.get("name", "Zestaw"),
            set_id=data.get("id"),
            asset_ids=list(data.get("asset_ids", [])),
            is_favorite=data.get("is_favorite", False),
            description=data.get("description", ""),
        )
