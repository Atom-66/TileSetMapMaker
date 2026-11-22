import uuid
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any


class ItemType(str, Enum):
    TILE = "tile"
    OBJECT = "object"


class MapItem:
    """An individual tile or prop placed on a layer."""

    def __init__(
        self,
        asset_id: str,
        col: int,
        row: int,
        item_type: ItemType = ItemType.TILE,
        offset_x: int = 0,
        offset_y: int = 0,
        source_x: int = 0,
        source_y: int = 0,
        source_w: int = 32,
        source_h: int = 32,
        dest_w: int = 32,
        dest_h: int = 32,
        flip_x: bool = False,
        flip_y: bool = False,
        item_id: Optional[str] = None,
    ):
        self.id = item_id or str(uuid.uuid4())
        self.asset_id = asset_id
        self.col = col
        self.row = row
        self.item_type = item_type
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.source_x = source_x
        self.source_y = source_y
        self.source_w = max(1, source_w)
        self.source_h = max(1, source_h)
        self.dest_w = max(1, dest_w)
        self.dest_h = max(1, dest_h)
        self.flip_x = flip_x
        self.flip_y = flip_y

    def clone(self) -> "MapItem":
        return MapItem(
            asset_id=self.asset_id,
            col=self.col,
            row=self.row,
            item_type=self.item_type,
            offset_x=self.offset_x,
            offset_y=self.offset_y,
            source_x=self.source_x,
            source_y=self.source_y,
            source_w=self.source_w,
            source_h=self.source_h,
            dest_w=self.dest_w,
            dest_h=self.dest_h,
            flip_x=self.flip_x,
            flip_y=self.flip_y,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "col": self.col,
            "row": self.row,
            "item_type": self.item_type.value,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "source_x": self.source_x,
            "source_y": self.source_y,
            "source_w": self.source_w,
            "source_h": self.source_h,
            "dest_w": self.dest_w,
            "dest_h": self.dest_h,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MapItem":
        return cls(
            asset_id=data["asset_id"],
            col=data["col"],
            row=data["row"],
            item_type=ItemType(data.get("item_type", ItemType.TILE.value)),
            offset_x=data.get("offset_x", 0),
            offset_y=data.get("offset_y", 0),
            source_x=data.get("source_x", 0),
            source_y=data.get("source_y", 0),
            source_w=data.get("source_w", 32),
            source_h=data.get("source_h", 32),
            dest_w=data.get("dest_w", 32),
            dest_h=data.get("dest_h", 32),
            flip_x=data.get("flip_x", False),
            flip_y=data.get("flip_y", False),
            item_id=data.get("id"),
        )


class Layer:
    """A single layer in the map containing tiles and objects."""

    def __init__(
        self,
        name: str = "Layer",
        layer_id: Optional[str] = None,
        visible: bool = True,
        locked: bool = False,
        opacity: float = 1.0,
    ):
        self.id = layer_id or str(uuid.uuid4())
        self.name = name
        self.visible = visible
        self.locked = locked
        self.opacity = max(0.0, min(1.0, opacity))
        # tiles indexed by (col, row)
        self.tiles: Dict[Tuple[int, int], MapItem] = {}
        # objects list for freeform props/large images
        self.objects: List[MapItem] = []

    def set_tile(self, col: int, row: int, item: Optional[MapItem]) -> Optional[MapItem]:
        """Sets or removes a tile at (col, row). Returns previous item."""
        prev = self.tiles.get((col, row))
        if item is None:
            self.tiles.pop((col, row), None)
        else:
            item.col = col
            item.row = row
            item.item_type = ItemType.TILE
            self.tiles[(col, row)] = item
        return prev

    def get_tile(self, col: int, row: int) -> Optional[MapItem]:
        return self.tiles.get((col, row))

    def remove_tile(self, col: int, row: int) -> Optional[MapItem]:
        return self.tiles.pop((col, row), None)

    def add_object(self, obj: MapItem) -> None:
        obj.item_type = ItemType.OBJECT
        self.objects.append(obj)

    def remove_object(self, obj_id: str) -> Optional[MapItem]:
        for i, obj in enumerate(self.objects):
            if obj.id == obj_id:
                return self.objects.pop(i)
        return None

    def clear(self) -> None:
        self.tiles.clear()
        self.objects.clear()

    def clone(self, new_name: Optional[str] = None) -> "Layer":
        cloned = Layer(
            name=new_name or f"{self.name} (Copy)",
            visible=self.visible,
            locked=self.locked,
            opacity=self.opacity,
        )
        for coord, item in self.tiles.items():
            cloned.tiles[coord] = item.clone()
        for obj in self.objects:
            cloned.objects.append(obj.clone())
        return cloned

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "visible": self.visible,
            "locked": self.locked,
            "opacity": self.opacity,
            "tiles": [
                {"col": c, "row": r, "item": item.to_dict()}
                for (c, r), item in self.tiles.items()
            ],
            "objects": [obj.to_dict() for obj in self.objects],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Layer":
        layer = cls(
            name=data.get("name", "Layer"),
            layer_id=data.get("id"),
            visible=data.get("visible", True),
            locked=data.get("locked", False),
            opacity=data.get("opacity", 1.0),
        )
        for tile_data in data.get("tiles", []):
            item = MapItem.from_dict(tile_data["item"])
            layer.tiles[(tile_data["col"], tile_data["row"])] = item
        for obj_data in data.get("objects", []):
            layer.objects.append(MapItem.from_dict(obj_data))
        return layer
