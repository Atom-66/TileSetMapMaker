import uuid
from typing import List, Optional, Dict, Any
from .layer import Layer
from .map_model import MapModel


class Project:
    """
    Represents a map project.
    Contains:
    - Multiple MapModels with tabbed/swappable editing
    - Full backward compatibility proxying the active map.
    """

    def __init__(
        self,
        name: str = "Nowy Projekt",
        map_width: int = 30,
        map_height: int = 20,
        tile_size: int = 32,
        background_color: str = "#22242a",
        is_bg_transparent: bool = False,
        file_path: Optional[str] = None,
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.file_path = file_path
        self.is_modified = False

        # Collection of maps
        self.maps: Dict[str, MapModel] = {}
        self.active_map_id: str = ""

        # Create initial primary map
        initial_map = MapModel(
            name="Główna Mapa",
            map_width=map_width,
            map_height=map_height,
            tile_size=tile_size,
            background_color=background_color,
            is_bg_transparent=is_bg_transparent,
        )
        self.maps[initial_map.id] = initial_map
        self.active_map_id = initial_map.id

    # ---------------------------------------------------------
    # Multi-Map Management
    # ---------------------------------------------------------

    def get_active_map(self) -> MapModel:
        if self.active_map_id in self.maps:
            return self.maps[self.active_map_id]
        if self.maps:
            self.active_map_id = next(iter(self.maps.keys()))
            return self.maps[self.active_map_id]
        # Fallback if empty
        new_m = MapModel("Główna Mapa")
        self.maps[new_m.id] = new_m
        self.active_map_id = new_m.id
        return new_m

    def set_active_map(self, map_id: str) -> bool:
        if map_id in self.maps:
            self.active_map_id = map_id
            return True
        return False

    def add_map(
        self,
        name: str = "Nowa Mapa",
        width: int = 30,
        height: int = 20,
        tile_size: int = 32,
    ) -> MapModel:
        m = MapModel(
            name=name,
            map_width=width,
            map_height=height,
            tile_size=tile_size,
        )
        self.maps[m.id] = m
        self.active_map_id = m.id
        self.is_modified = True
        return m

    def remove_map(self, map_id: str) -> bool:
        if len(self.maps) <= 1:
            return False  # Keep at least one map
        if map_id in self.maps:
            del self.maps[map_id]
            if self.active_map_id == map_id:
                self.active_map_id = next(iter(self.maps.keys()))
            self.is_modified = True
            return True
        return False

    def duplicate_map(self, map_id: str, new_name: Optional[str] = None) -> Optional[MapModel]:
        source = self.maps.get(map_id)
        if not source:
            return None
        clone = source.clone(new_name or f"{source.name} (Kopia)")
        self.maps[clone.id] = clone
        self.active_map_id = clone.id
        self.is_modified = True
        return clone

    def copy_layer_between_maps(
        self,
        source_map_id: str,
        layer_id: str,
        target_map_id: str,
        new_name: Optional[str] = None,
    ) -> Optional[Layer]:
        source = self.maps.get(source_map_id)
        target = self.maps.get(target_map_id)
        source_layer = source.get_layer(layer_id) if source else None
        if not source or not target or not source_layer:
            return None
        clone = source_layer.clone(new_name or source_layer.name)
        clone.group_id = None
        target.layers.append(clone)
        if not clone.is_group:
            target.active_layer_id = clone.id
        target.is_modified = True
        self.is_modified = True
        return clone

    def move_layer_between_maps(
        self,
        source_map_id: str,
        layer_id: str,
        target_map_id: str,
    ) -> bool:
        if source_map_id == target_map_id:
            return False
        source = self.maps.get(source_map_id)
        target = self.maps.get(target_map_id)
        if not source or not target:
            return False
        index = source.get_layer_index(layer_id)
        if index is None or len(source.layers) <= 1:
            return False
        layer = source.layers.pop(index)
        layer.group_id = None
        target.layers.append(layer)
        if not layer.is_group:
            target.active_layer_id = layer.id
        source.get_active_layer()
        source.is_modified = True
        target.is_modified = True
        self.is_modified = True
        return True

    def merge_layers(
        self,
        map_id: str,
        layer_ids: List[str],
        name: str = "Połączona warstwa",
    ) -> Optional[Layer]:
        map_model = self.maps.get(map_id)
        if not map_model:
            return None
        unique_ids = list(dict.fromkeys(layer_ids))
        layers = [map_model.get_layer(layer_id) for layer_id in unique_ids]
        selected = [layer for layer in layers if layer and not layer.is_group]
        if len(selected) < 2:
            return None

        merged = Layer(
            name=name,
            visible=any(layer.visible for layer in selected),
            locked=False,
            opacity=1.0,
            layer_type=selected[0].layer_type,
        )
        indices = [map_model.get_layer_index(layer.id) for layer in selected]
        insert_at = min(index for index in indices if index is not None)
        for layer in selected:
            for coord, item in layer.tiles.items():
                merged.tiles[coord] = item.clone()
            merged.objects.extend(item.clone() for item in layer.objects)
        for layer in selected:
            map_model.layers.remove(layer)
        map_model.layers.insert(insert_at, merged)
        map_model.active_layer_id = merged.id
        map_model.is_modified = True
        self.is_modified = True
        return merged

    def is_walkable(self, x: float, y: float) -> bool:
        return all(
            layer.is_walkable(x, y)
            for layer in self.get_active_map().layers
            if layer.layer_type == "collision"
        )

    def get_interactions_at(self, x: float, y: float) -> List[MapItem]:
        interactions = []
        tile_size = self.tile_size
        for layer in self.get_active_map().layers:
            for obj in layer.objects:
                if not obj.interaction_label or obj.interaction_radius <= 0:
                    continue
                ox, oy = obj.get_pixel_pos(tile_size)
                center_x = ox + obj.dest_w * abs(obj.scale_x) / 2
                center_y = oy + obj.dest_h * abs(obj.scale_y) / 2
                if (x - center_x) ** 2 + (y - center_y) ** 2 <= (
                    obj.interaction_radius ** 2
                ):
                    interactions.append(obj)
        return sorted(
            interactions,
            key=lambda obj: obj.z_index,
            reverse=True,
        )

    def save_map_template(self, map_id: str) -> Optional[Dict[str, Any]]:
        map_model = self.maps.get(map_id)
        return map_model.to_dict() if map_model else None

    def add_map_from_template(
        self, template: Dict[str, Any], new_name: Optional[str] = None
    ) -> MapModel:
        map_model = MapModel.from_dict(template)
        map_model = map_model.clone(new_name or map_model.name)
        self.maps[map_model.id] = map_model
        self.active_map_id = map_model.id
        self.is_modified = True
        return map_model

    def rename_map(self, map_id: str, new_name: str) -> bool:
        if map_id in self.maps and new_name.strip():
            self.maps[map_id].name = new_name.strip()
            self.is_modified = True
            return True
        return False

    # ---------------------------------------------------------
    # Backward Compatibility Proxies (Active Map forwarding)
    # ---------------------------------------------------------

    @property
    def active_map(self) -> MapModel:
        return self.get_active_map()

    @property
    def active_layer(self) -> Optional[Layer]:
        return self.get_active_layer()

    @property
    def map_width(self) -> int:
        return self.get_active_map().map_width

    @map_width.setter
    def map_width(self, val: int):
        self.get_active_map().map_width = max(1, val)

    @property
    def map_height(self) -> int:
        return self.get_active_map().map_height

    @map_height.setter
    def map_height(self, val: int):
        self.get_active_map().map_height = max(1, val)

    @property
    def tile_size(self) -> int:
        return self.get_active_map().tile_size

    @tile_size.setter
    def tile_size(self, val: int):
        self.get_active_map().tile_size = max(4, val)

    @property
    def background_color(self) -> str:
        return self.get_active_map().background_color

    @background_color.setter
    def background_color(self, val: str):
        self.get_active_map().background_color = val

    @property
    def is_bg_transparent(self) -> bool:
        return self.get_active_map().is_bg_transparent

    @is_bg_transparent.setter
    def is_bg_transparent(self, val: bool):
        self.get_active_map().is_bg_transparent = val

    @property
    def layers(self) -> List[Layer]:
        return self.get_active_map().layers

    @layers.setter
    def layers(self, val: List[Layer]):
        self.get_active_map().layers = val

    @property
    def active_layer_id(self) -> Optional[str]:
        return self.get_active_map().active_layer_id

    @active_layer_id.setter
    def active_layer_id(self, val: Optional[str]):
        self.get_active_map().active_layer_id = val

    def isolate_layer(self, layer_id: Optional[str]) -> bool:
        changed = self.get_active_map().isolate_layer(layer_id)
        if changed:
            self.is_modified = True
        return changed

    @property
    def isolated_layer_id(self) -> Optional[str]:
        return self.get_active_map().isolated_layer_id

    def get_active_layer(self) -> Optional[Layer]:
        return self.get_active_map().get_active_layer()

    def set_active_layer(self, layer_id: str) -> bool:
        return self.get_active_map().set_active_layer(layer_id)

    def add_layer(self, *args, **kwargs) -> Layer:
        return self.get_active_map().add_layer(*args, **kwargs)

    def add_group(self, *args, **kwargs) -> Layer:
        return self.get_active_map().add_group(*args, **kwargs)

    def remove_layer(self, layer_id: str) -> bool:
        return self.get_active_map().remove_layer(layer_id)

    def duplicate_layer(self, layer_id: str) -> Optional[Layer]:
        return self.get_active_map().duplicate_layer(layer_id)

    def move_layer(self, from_index: int, to_index: int) -> bool:
        return self.get_active_map().move_layer(from_index, to_index)

    def get_layer(self, layer_id: Optional[str]) -> Optional[Layer]:
        return self.get_active_map().get_layer(layer_id)

    def get_layer_index(self, layer_id: str) -> Optional[int]:
        return self.get_active_map().get_layer_index(layer_id)

    def get_effective_visible(self, layer: Layer) -> bool:
        return self.get_active_map().get_effective_visible(layer)

    def get_effective_opacity(self, layer: Layer) -> float:
        return self.get_active_map().get_effective_opacity(layer)

    def get_effective_locked(self, layer: Layer) -> bool:
        return self.get_active_map().get_effective_locked(layer)

    def get_render_order_layers(self) -> List[Layer]:
        return self.get_active_map().get_render_order_layers()

    def resize_map(self, new_width: int, new_height: int, anchor: str = "top_left") -> None:
        self.get_active_map().resize_map(new_width, new_height, anchor)
        self.is_modified = True

    # ---------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        active_m = self.get_active_map()
        return {
            "version": "2.0",
            "id": self.id,
            "name": self.name,
            "active_map_id": self.active_map_id,
            "maps": [m.to_dict() for m in self.maps.values()],
            # Legacy compatibility fields
            "map_width": active_m.map_width,
            "map_height": active_m.map_height,
            "tile_size": active_m.tile_size,
            "background_color": active_m.background_color,
            "is_bg_transparent": active_m.is_bg_transparent,
            "active_layer_id": active_m.active_layer_id,
            "layers": [l.to_dict() for l in active_m.layers],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        proj = cls(
            name=data.get("name", "Projekt"),
            map_width=data.get("map_width", 30),
            map_height=data.get("map_height", 20),
            tile_size=data.get("tile_size", 32),
            background_color=data.get("background_color", "#22242a"),
            is_bg_transparent=data.get("is_bg_transparent", False),
        )
        proj.id = data.get("id", proj.id)

        # 1. New multi-map format
        if "maps" in data and data["maps"]:
            proj.maps.clear()
            for m_data in data["maps"]:
                m = MapModel.from_dict(m_data)
                proj.maps[m.id] = m
            proj.active_map_id = data.get("active_map_id", next(iter(proj.maps.keys())))

        # 2. Legacy single-map format upgrade
        elif "layers" in data:
            legacy_map = MapModel.from_dict(data)
            legacy_map.name = data.get("name", "Główna Mapa")
            proj.maps.clear()
            proj.maps[legacy_map.id] = legacy_map
            proj.active_map_id = legacy_map.id

        return proj
