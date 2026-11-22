import uuid
from typing import Dict, Tuple, List, Optional, Any
from .layer import MapItem


class StampPreset:
    """A named multi-tile or multi-object stamp preset with rotation and flip capabilities."""

    def __init__(
        self,
        name: str = "Stempel",
        preset_id: Optional[str] = None,
        items: Optional[Dict[Tuple[int, int], MapItem]] = None,
        width: int = 1,
        height: int = 1,
    ):
        self.id = preset_id or str(uuid.uuid4())
        self.name = name
        # (rel_col, rel_row) -> MapItem
        self.items: Dict[Tuple[int, int], MapItem] = items or {}
        self.width = max(1, width)
        self.height = max(1, height)

    def rotate_90(self) -> None:
        """Rotates stamp 90 degrees clockwise."""
        new_items: Dict[Tuple[int, int], MapItem] = {}
        for (c, r), item in self.items.items():
            nc = self.height - 1 - r
            nr = c
            clone = item.clone()
            clone.col = nc
            clone.row = nr
            clone.rotation = (clone.rotation + 90) % 360
            new_items[(nc, nr)] = clone
        self.items = new_items
        self.width, self.height = self.height, self.width

    def flip_horizontal(self) -> None:
        """Flips stamp horizontally."""
        new_items: Dict[Tuple[int, int], MapItem] = {}
        for (c, r), item in self.items.items():
            nc = self.width - 1 - c
            nr = r
            clone = item.clone()
            clone.col = nc
            clone.row = nr
            clone.flip_x = not clone.flip_x
            new_items[(nc, nr)] = clone
        self.items = new_items

    def flip_vertical(self) -> None:
        """Flips stamp vertically."""
        new_items: Dict[Tuple[int, int], MapItem] = {}
        for (c, r), item in self.items.items():
            nc = c
            nr = self.height - 1 - r
            clone = item.clone()
            clone.col = nc
            clone.row = nr
            clone.flip_y = not clone.flip_y
            new_items[(nc, nr)] = clone
        self.items = new_items

    def clone(self) -> "StampPreset":
        cloned = StampPreset(name=self.name, width=self.width, height=self.height)
        cloned.items = {k: v.clone() for k, v in self.items.items()}
        return cloned

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "items": [
                {"rel_col": c, "rel_row": r, "item": item.to_dict()}
                for (c, r), item in self.items.items()
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StampPreset":
        preset = cls(
            name=data.get("name", "Stempel"),
            preset_id=data.get("id"),
            width=data.get("width", 1),
            height=data.get("height", 1),
        )
        for it_data in data.get("items", []):
            item = MapItem.from_dict(it_data["item"])
            preset.items[(it_data["rel_col"], it_data["rel_row"])] = item
        return preset
