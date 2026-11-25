import uuid
from typing import List, Optional, Dict, Any
from .layer import Layer


class MapModel:
    """
    Represents an individual 2D tilemap with layers, dimensions, and settings.
    Multiple MapModels can belong to a single Project.
    """

    def __init__(
        self,
        name: str = "Nowa Mapa",
        map_width: int = 30,
        map_height: int = 20,
        tile_size: int = 32,
        background_color: str = "#22242a",
        is_bg_transparent: bool = False,
        map_id: Optional[str] = None,
    ):
        self.id = map_id or str(uuid.uuid4())
        self.name = name
        self.map_width = max(1, map_width)
        self.map_height = max(1, map_height)
        self.tile_size = max(4, tile_size)
        self.background_color = background_color
        self.is_bg_transparent = is_bg_transparent
        self.is_modified = False

        self.layers: List[Layer] = []
        self.active_layer_id: Optional[str] = None
        self.isolated_layer_id: Optional[str] = None
        self.properties: Dict[str, Any] = {}

        self.ensure_default_layers()

    def ensure_default_layers(self) -> None:
        if not self.layers:
            ground = self.add_layer("Warstwa 1")
            self.active_layer_id = ground.id

    def add_layer(
        self,
        name: str = "Warstwa",
        at_index: Optional[int] = None,
        group_id: Optional[str] = None,
        is_group: bool = False,
        layer_type: str = "tile",
    ) -> Layer:
        layer = Layer(
            name=name,
            group_id=group_id,
            is_group=is_group,
            layer_type=layer_type,
        )
        if at_index is not None and 0 <= at_index <= len(self.layers):
            self.layers.insert(at_index, layer)
        else:
            self.layers.append(layer)
        if not is_group:
            self.active_layer_id = layer.id
        self.is_modified = True
        return layer

    def add_group(self, name: str = "Grupa", parent_group_id: Optional[str] = None) -> Layer:
        return self.add_layer(name=name, is_group=True, group_id=parent_group_id)

    def remove_layer(self, layer_id: str) -> bool:
        if len(self.layers) <= 1:
            return False
        idx = self.get_layer_index(layer_id)
        if idx is not None:
            target = self.layers[idx]
            child_ids = [l.id for l in self.layers if l.group_id == target.id]
            for cid in child_ids:
                cidx = self.get_layer_index(cid)
                if cidx is not None:
                    self.layers.pop(cidx)

            idx = self.get_layer_index(layer_id)
            if idx is not None:
                self.layers.pop(idx)

            if not self.layers:
                self.ensure_default_layers()

            if self.active_layer_id == layer_id:
                non_groups = [l for l in self.layers if not l.is_group]
                self.active_layer_id = non_groups[0].id if non_groups else self.layers[0].id

            self.is_modified = True
            return True
        return False

    def duplicate_layer(self, layer_id: str) -> Optional[Layer]:
        idx = self.get_layer_index(layer_id)
        if idx is not None:
            source = self.layers[idx]
            clone = source.clone(f"{source.name} (Kopia)")
            self.layers.insert(idx + 1, clone)
            if not clone.is_group:
                self.active_layer_id = clone.id
            self.is_modified = True
            return clone
        return None

    def move_layer(self, from_index: int, to_index: int) -> bool:
        if 0 <= from_index < len(self.layers) and 0 <= to_index < len(self.layers):
            layer = self.layers.pop(from_index)
            self.layers.insert(to_index, layer)
            self.is_modified = True
            return True
        return False

    def get_layer(self, layer_id: Optional[str]) -> Optional[Layer]:
        if not layer_id:
            return None
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def get_layer_index(self, layer_id: str) -> Optional[int]:
        for i, layer in enumerate(self.layers):
            if layer.id == layer_id:
                return i
        return None

    def get_active_layer(self) -> Optional[Layer]:
        layer = self.get_layer(self.active_layer_id)
        if (not layer or layer.is_group) and self.layers:
            non_groups = [l for l in self.layers if not l.is_group]
            if non_groups:
                self.active_layer_id = non_groups[0].id
                return non_groups[0]
            self.active_layer_id = self.layers[0].id
            return self.layers[0]
        return layer

    def set_active_layer(self, layer_id: str) -> bool:
        layer = self.get_layer(layer_id)
        if layer and not layer.is_group:
            self.active_layer_id = layer_id
            return True
        return False

    def get_effective_visible(self, layer: Layer) -> bool:
        curr: Optional[Layer] = layer
        while curr:
            if not curr.visible:
                return False
            curr = self.get_layer(curr.group_id) if curr.group_id else None
        return True

    def get_effective_opacity(self, layer: Layer) -> float:
        op = layer.opacity
        curr: Optional[Layer] = self.get_layer(layer.group_id) if layer.group_id else None
        while curr:
            op *= curr.opacity
            curr = self.get_layer(curr.group_id) if curr.group_id else None
        return max(0.0, min(1.0, op))

    def get_effective_locked(self, layer: Layer) -> bool:
        curr: Optional[Layer] = layer
        while curr:
            if curr.locked:
                return True
            curr = self.get_layer(curr.group_id) if curr.group_id else None
        return False

    def get_render_order_layers(self) -> List[Layer]:
        return [l for l in self.layers if not l.is_group]

    def isolate_layer(self, layer_id: Optional[str]) -> bool:
        if layer_id is not None and not self.get_layer(layer_id):
            return False
        self.isolated_layer_id = layer_id
        self.is_modified = True
        return True

    def resize_map(self, new_width: int, new_height: int, anchor: str = "top_left") -> None:
        new_width = max(1, new_width)
        new_height = max(1, new_height)
        if new_width == self.map_width and new_height == self.map_height:
            return

        dx = 0
        dy = 0
        if anchor == "center":
            dx = (new_width - self.map_width) // 2
            dy = (new_height - self.map_height) // 2
        elif anchor == "bottom_right":
            dx = new_width - self.map_width
            dy = new_height - self.map_height

        if dx != 0 or dy != 0:
            for layer in self.layers:
                new_tiles = {}
                for (c, r), item in layer.tiles.items():
                    nc = c + dx
                    nr = r + dy
                    if 0 <= nc < new_width and 0 <= nr < new_height:
                        item.col = nc
                        item.row = nr
                        new_tiles[(nc, nr)] = item
                layer.tiles = new_tiles
                retained_objects = []
                for obj in layer.objects:
                    obj.col += dx
                    obj.row += dy
                    if obj.free_x is not None:
                        obj.free_x += dx * self.tile_size
                    if obj.free_y is not None:
                        obj.free_y += dy * self.tile_size
                    if (
                        -1 <= obj.col <= new_width
                        and -1 <= obj.row <= new_height
                    ):
                        retained_objects.append(obj)
                layer.objects = retained_objects
                layer.collisions = [
                    collision
                    for collision in layer.collisions
                    if 0 <= collision.x + dx * self.tile_size < new_width * self.tile_size
                    and 0 <= collision.y + dy * self.tile_size < new_height * self.tile_size
                ]
                for collision in layer.collisions:
                    collision.x += dx * self.tile_size
                    collision.y += dy * self.tile_size
        else:
            for layer in self.layers:
                layer.tiles = {
                    (c, r): item
                    for (c, r), item in layer.tiles.items()
                    if c < new_width and r < new_height
                }
                layer.objects = [
                    obj
                    for obj in layer.objects
                    if -1 <= obj.col < new_width + 1
                    and -1 <= obj.row < new_height + 1
                ]
                layer.collisions = [
                    collision
                    for collision in layer.collisions
                    if collision.x < new_width * self.tile_size
                    and collision.y < new_height * self.tile_size
                ]

        self.map_width = new_width
        self.map_height = new_height
        self.is_modified = True

    def clone(self, new_name: Optional[str] = None) -> "MapModel":
        c = MapModel(
            name=new_name or f"{self.name} (Kopia)",
            map_width=self.map_width,
            map_height=self.map_height,
            tile_size=self.tile_size,
            background_color=self.background_color,
            is_bg_transparent=self.is_bg_transparent,
        )
        id_map = {}
        c.layers = []
        for source in self.layers:
            cloned = source.clone(source.name)
            id_map[source.id] = cloned.id
            c.layers.append(cloned)
        for layer in c.layers:
            if layer.group_id in id_map:
                layer.group_id = id_map[layer.group_id]
        c.active_layer_id = id_map.get(self.active_layer_id)
        c.properties = dict(self.properties)
        return c

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "map_width": self.map_width,
            "map_height": self.map_height,
            "tile_size": self.tile_size,
            "background_color": self.background_color,
            "is_bg_transparent": self.is_bg_transparent,
            "active_layer_id": self.active_layer_id,
            "isolated_layer_id": self.isolated_layer_id,
            "properties": self.properties,
            "layers": [layer.to_dict() for layer in self.layers],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MapModel":
        m = cls(
            name=data.get("name", "Mapa"),
            map_width=data.get("map_width", 30),
            map_height=data.get("map_height", 20),
            tile_size=data.get("tile_size", 32),
            background_color=data.get("background_color", "#22242a"),
            is_bg_transparent=data.get("is_bg_transparent", False),
            map_id=data.get("id"),
        )
        m.layers = [Layer.from_dict(l_data) for l_data in data.get("layers", [])]
        m.active_layer_id = data.get("active_layer_id")
        m.isolated_layer_id = data.get("isolated_layer_id")
        m.properties = dict(data.get("properties", {}))
        if not m.get_layer(m.isolated_layer_id):
            m.isolated_layer_id = None
        if not m.layers:
            m.ensure_default_layers()
        if not m.get_active_layer() and m.layers:
            non_groups = [l for l in m.layers if not l.is_group]
            m.active_layer_id = non_groups[0].id if non_groups else m.layers[0].id
        return m
