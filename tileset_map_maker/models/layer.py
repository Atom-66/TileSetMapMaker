import uuid
import copy
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any


class ItemType(str, Enum):
    TILE = "tile"
    OBJECT = "object"


class ObjectPropertyType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


class CollisionShape(str, Enum):
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"


class CollisionObject:
    """Runtime-independent collision or trigger geometry in map pixels."""

    def __init__(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        shape: CollisionShape = CollisionShape.RECTANGLE,
        collision_id: Optional[str] = None,
        blocking: bool = True,
        trigger: bool = False,
        interaction_label: str = "",
        properties: Optional[Dict[str, Any]] = None,
    ):
        self.id = collision_id or str(uuid.uuid4())
        self.x = float(x)
        self.y = float(y)
        self.width = max(1.0, float(width))
        self.height = max(1.0, float(height))
        self.shape = shape if isinstance(shape, CollisionShape) else CollisionShape(shape)
        self.blocking = bool(blocking)
        self.trigger = bool(trigger)
        self.interaction_label = interaction_label
        self.properties = dict(properties or {})

    def clone(self) -> "CollisionObject":
        return CollisionObject(
            self.x, self.y, self.width, self.height,
            shape=self.shape,
            blocking=self.blocking,
            trigger=self.trigger,
            interaction_label=self.interaction_label,
            properties=self.properties,
        )

    def intersects_point(self, x: float, y: float) -> bool:
        left, top = self.x, self.y
        right, bottom = self.x + self.width, self.y + self.height
        if not (left <= x <= right and top <= y <= bottom):
            return False
        if self.shape == CollisionShape.ELLIPSE:
            rx = self.width / 2
            ry = self.height / 2
            nx = (x - (left + rx)) / max(rx, 0.0001)
            ny = (y - (top + ry)) / max(ry, 0.0001)
            return nx * nx + ny * ny <= 1.0
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "shape": self.shape.value,
            "blocking": self.blocking,
            "trigger": self.trigger,
            "interaction_label": self.interaction_label,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CollisionObject":
        return cls(
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width", 1),
            height=data.get("height", 1),
            shape=data.get("shape", CollisionShape.RECTANGLE.value),
            collision_id=data.get("id"),
            blocking=data.get("blocking", True),
            trigger=data.get("trigger", False),
            interaction_label=data.get("interaction_label", ""),
            properties=data.get("properties", {}),
        )


class MapItem:
    """An individual tile or prop placed on a layer with full transform support."""

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
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        anchor_x: float = 0.5,
        anchor_y: float = 0.5,
        free_x: Optional[float] = None,
        free_y: Optional[float] = None,
        z_index: int = 0,
        group_id: Optional[str] = None,
        terrain_type: Optional[str] = None,
        is_auto_tiled: bool = False,
        object_type: str = "",
        properties: Optional[Dict[str, Any]] = None,
        property_types: Optional[Dict[str, str]] = None,
        interaction_label: str = "",
        interaction_radius: float = 0.0,
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
        self.rotation = float(rotation)
        self.scale_x = float(scale_x)
        self.scale_y = float(scale_y)
        self.anchor_x = float(anchor_x)
        self.anchor_y = float(anchor_y)
        self.free_x = float(free_x) if free_x is not None else None
        self.free_y = float(free_y) if free_y is not None else None
        self.z_index = int(z_index)
        self.group_id = group_id
        self.terrain_type = terrain_type
        self.is_auto_tiled = is_auto_tiled
        self.object_type = object_type
        self.properties = dict(properties or {})
        self.property_types = dict(property_types or {})
        self.interaction_label = interaction_label
        self.interaction_radius = max(0.0, float(interaction_radius))

    def get_pixel_pos(self, tile_size: int) -> Tuple[float, float]:
        """Returns pixel (x, y) accounting for free_x/y or grid alignment."""
        if self.free_x is not None and self.free_y is not None:
            return self.free_x, self.free_y
        return float(self.col * tile_size + self.offset_x), float(self.row * tile_size + self.offset_y)

    def clone(self, preserve_id: bool = False) -> "MapItem":
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
            item_id=self.id if preserve_id else None,
            rotation=self.rotation,
            scale_x=self.scale_x,
            scale_y=self.scale_y,
            anchor_x=self.anchor_x,
            anchor_y=self.anchor_y,
            free_x=self.free_x,
            free_y=self.free_y,
            z_index=self.z_index,
            group_id=self.group_id,
            terrain_type=self.terrain_type,
            is_auto_tiled=self.is_auto_tiled,
            object_type=self.object_type,
            properties=copy.deepcopy(self.properties),
            property_types=copy.deepcopy(self.property_types),
            interaction_label=self.interaction_label,
            interaction_radius=self.interaction_radius,
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
            "rotation": self.rotation,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "anchor_x": self.anchor_x,
            "anchor_y": self.anchor_y,
            "free_x": self.free_x,
            "free_y": self.free_y,
            "z_index": self.z_index,
            "group_id": self.group_id,
            "terrain_type": self.terrain_type,
            "is_auto_tiled": self.is_auto_tiled,
            "object_type": self.object_type,
            "properties": self.properties,
            "property_types": self.property_types,
            "interaction_label": self.interaction_label,
            "interaction_radius": self.interaction_radius,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MapItem":
        return cls(
            asset_id=data["asset_id"],
            col=data.get("col", 0),
            row=data.get("row", 0),
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
            rotation=data.get("rotation", 0.0),
            scale_x=data.get("scale_x", 1.0),
            scale_y=data.get("scale_y", 1.0),
            anchor_x=data.get("anchor_x", 0.5),
            anchor_y=data.get("anchor_y", 0.5),
            free_x=data.get("free_x"),
            free_y=data.get("free_y"),
            z_index=data.get("z_index", 0),
            group_id=data.get("group_id"),
            terrain_type=data.get("terrain_type"),
            is_auto_tiled=data.get("is_auto_tiled", False),
            object_type=data.get("object_type", ""),
            properties=data.get("properties", {}),
            property_types=data.get("property_types", {}),
            interaction_label=data.get("interaction_label", ""),
            interaction_radius=data.get("interaction_radius", 0.0),
        )


class Layer:
    """A single layer or layer group in the map."""

    def __init__(
        self,
        name: str = "Layer",
        layer_id: Optional[str] = None,
        visible: bool = True,
        locked: bool = False,
        opacity: float = 1.0,
        group_id: Optional[str] = None,
        is_group: bool = False,
        auto_tiling_enabled: bool = True,
        autotile_ruleset_id: Optional[str] = None,
        blend_mode: str = "normal",
        layer_type: str = "tile",
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        properties: Optional[Dict[str, Any]] = None,
    ):
        self.id = layer_id or str(uuid.uuid4())
        self.name = name
        self.visible = visible
        self.locked = locked
        self.opacity = max(0.0, min(1.0, opacity))
        self.group_id = group_id
        self.is_group = is_group
        self.auto_tiling_enabled = auto_tiling_enabled
        self.autotile_ruleset_id = autotile_ruleset_id
        self.blend_mode = blend_mode.lower() if blend_mode else "normal"
        self.layer_type = layer_type if layer_type in ("tile", "object", "collision") else "tile"
        self.offset_x = float(offset_x)
        self.offset_y = float(offset_y)
        self.properties = copy.deepcopy(properties or {})

        # Tiles indexed by (col, row)
        self.tiles: Dict[Tuple[int, int], MapItem] = {}
        # Freeform objects / props
        self.objects: List[MapItem] = []
        self.collisions: List[CollisionObject] = []

    def set_tile(self, col: int, row: int, item: Optional[MapItem]) -> Optional[MapItem]:
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

    def get_object(self, obj_id: str) -> Optional[MapItem]:
        for obj in self.objects:
            if obj.id == obj_id:
                return obj
        return None

    def add_collision(self, collision: CollisionObject) -> None:
        self.collisions.append(collision)

    def remove_collision(self, collision_id: str) -> Optional[CollisionObject]:
        for index, collision in enumerate(self.collisions):
            if collision.id == collision_id:
                return self.collisions.pop(index)
        return None

    def get_collision(self, collision_id: str) -> Optional[CollisionObject]:
        for collision in self.collisions:
            if collision.id == collision_id:
                return collision
        return None

    def is_walkable(self, x: float, y: float) -> bool:
        return not any(
            collision.blocking and collision.intersects_point(x, y)
            for collision in self.collisions
        )

    def clear(self) -> None:
        self.tiles.clear()
        self.objects.clear()
        self.collisions.clear()

    def clone(self, new_name: Optional[str] = None) -> "Layer":
        cloned = Layer(
            name=new_name or f"{self.name} (Kopia)",
            visible=self.visible,
            locked=self.locked,
            opacity=self.opacity,
            group_id=self.group_id,
            is_group=self.is_group,
            auto_tiling_enabled=self.auto_tiling_enabled,
            autotile_ruleset_id=self.autotile_ruleset_id,
            blend_mode=self.blend_mode,
            layer_type=self.layer_type,
            offset_x=self.offset_x,
            offset_y=self.offset_y,
            properties=self.properties,
        )
        for coord, item in self.tiles.items():
            cloned.tiles[coord] = item.clone()
        for obj in self.objects:
            cloned.objects.append(obj.clone())
        for collision in self.collisions:
            cloned.collisions.append(collision.clone())
        return cloned

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "visible": self.visible,
            "locked": self.locked,
            "opacity": self.opacity,
            "group_id": self.group_id,
            "is_group": self.is_group,
            "auto_tiling_enabled": self.auto_tiling_enabled,
            "autotile_ruleset_id": self.autotile_ruleset_id,
            "blend_mode": self.blend_mode,
            "layer_type": self.layer_type,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "properties": self.properties,
            "tiles": [
                {"col": c, "row": r, "item": item.to_dict()}
                for (c, r), item in self.tiles.items()
            ],
            "objects": [obj.to_dict() for obj in self.objects],
            "collisions": [collision.to_dict() for collision in self.collisions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Layer":
        layer = cls(
            name=data.get("name", "Layer"),
            layer_id=data.get("id"),
            visible=data.get("visible", True),
            locked=data.get("locked", False),
            opacity=data.get("opacity", 1.0),
            group_id=data.get("group_id"),
            is_group=data.get("is_group", False),
            auto_tiling_enabled=data.get("auto_tiling_enabled", True),
            autotile_ruleset_id=data.get("autotile_ruleset_id"),
            blend_mode=data.get("blend_mode", "normal"),
            layer_type=data.get("layer_type", "tile"),
            offset_x=data.get("offset_x", 0.0),
            offset_y=data.get("offset_y", 0.0),
            properties=data.get("properties", {}),
        )
        for tile_data in data.get("tiles", []):
            item = MapItem.from_dict(tile_data["item"])
            layer.tiles[(tile_data["col"], tile_data["row"])] = item
        for obj_data in data.get("objects", []):
            layer.objects.append(MapItem.from_dict(obj_data))
        for collision_data in data.get("collisions", []):
            layer.collisions.append(CollisionObject.from_dict(collision_data))
        return layer
