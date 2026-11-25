import copy
import random
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple


class TerrainType(IntEnum):
    GRASS = 0
    FOREST = 1
    WATER = 2
    LAKE = 3
    MOUNTAIN = 4
    ROAD = 5


class TerrainConfig:
    def __init__(
        self,
        seed: int = 12345,
        scale: float = 18.0,
        water_level: float = 0.30,
        mountain_level: float = 0.76,
        forest_threshold: float = 0.59,
        river_count: int = 1,
        river_width: int = 1,
        road_count: int = 2,
        road_width: int = 1,
        tile_mappings: Optional[
            Dict[str, Tuple[str, int, int, int, int]]
        ] = None,
        ruleset_ids: Optional[Dict[str, str]] = None,
        autotile_ids: Optional[Dict[str, str]] = None,
    ):
        self.seed = int(seed)
        self.scale = max(2.0, float(scale))
        self.water_level = min(0.49, max(0.05, float(water_level)))
        self.mountain_level = min(0.95, max(0.51, float(mountain_level)))
        self.forest_threshold = min(0.95, max(0.51, float(forest_threshold)))
        self.river_count = max(0, int(river_count))
        self.river_width = max(1, int(river_width))
        self.road_count = max(0, int(road_count))
        self.road_width = max(1, int(road_width))
        self.tile_mappings = dict(tile_mappings or {})
        self.autotile_ids = dict(autotile_ids or ruleset_ids or {})
        self.ruleset_ids = self.autotile_ids

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "scale": self.scale,
            "water_level": self.water_level,
            "mountain_level": self.mountain_level,
            "forest_threshold": self.forest_threshold,
            "river_count": self.river_count,
            "river_width": self.river_width,
            "road_count": self.road_count,
            "road_width": self.road_width,
            "tile_mappings": {
                key: list(value) for key, value in self.tile_mappings.items()
            },
            "ruleset_ids": dict(self.ruleset_ids),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TerrainConfig":
        return cls(
            seed=data.get("seed", 12345),
            scale=data.get("scale", 18.0),
            water_level=data.get("water_level", 0.30),
            mountain_level=data.get("mountain_level", 0.76),
            forest_threshold=data.get("forest_threshold", 0.59),
            river_count=data.get("river_count", 1),
            river_width=data.get("river_width", 1),
            road_count=data.get("road_count", 2),
            road_width=data.get("road_width", 1),
            tile_mappings={
                key: tuple(value)
                for key, value in data.get("tile_mappings", {}).items()
            },
            ruleset_ids=data.get("ruleset_ids", {}),
        )


class TerrainMask:
    """Compact editable mask used to force or protect terrain generation."""

    def __init__(self, width: int, height: int):
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.values = bytearray(self.width * self.height)

    def set_rect(
        self, x: int, y: int, width: int, height: int, enabled: bool = True
    ) -> None:
        value = 1 if enabled else 0
        for row in range(max(0, y), min(self.height, y + height)):
            start = row * self.width + max(0, x)
            end = row * self.width + min(self.width, x + width)
            if end > start:
                self.values[start:end] = bytes([value]) * (end - start)

    def set_cell(self, x: int, y: int, enabled: bool = True) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.values[y * self.width + x] = 1 if enabled else 0

    def __getitem__(self, coord: Tuple[int, int]) -> bool:
        x, y = coord
        return (
            0 <= x < self.width
            and 0 <= y < self.height
            and bool(self.values[y * self.width + x])
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "values": bytes(self.values).hex(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TerrainMask":
        mask = cls(data.get("width", 1), data.get("height", 1))
        raw = bytes.fromhex(data.get("values", ""))
        mask.values[: min(len(raw), len(mask.values))] = raw[: len(mask.values)]
        return mask


class TerrainResult:
    def __init__(self, width: int, height: int, seed: int):
        self.width = width
        self.height = height
        self.seed = seed
        self.cells = bytearray(width * height)

    def get(self, x: int, y: int) -> TerrainType:
        return TerrainType(self.cells[y * self.width + x])

    def set(self, x: int, y: int, terrain: TerrainType) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y * self.width + x] = int(terrain)

    def clone(self) -> "TerrainResult":
        result = TerrainResult(self.width, self.height, self.seed)
        result.cells[:] = self.cells
        return result


class TerrainPreset:
    def __init__(self, name: str, config: TerrainConfig):
        self.name = name
        self.config = copy.deepcopy(config)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "config": self.config.to_dict()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TerrainPreset":
        return cls(data.get("name", "Preset"), TerrainConfig.from_dict(data.get("config", {})))


class TerrainGenerator:
    """Deterministic, dependency-free multi-scale terrain generator."""

    PRESET_NAMES = ("Temperate", "Archipelago", "Alpine", "Dryland")

    def __init__(self):
        self.presets: Dict[str, TerrainPreset] = {}
        self.previous_result: Optional[TerrainResult] = None
        self.current_result: Optional[TerrainResult] = None
        self.last_config = TerrainConfig()
        self.masks: Dict[str, TerrainMask] = {}
        self._ensure_default_presets()

    def _ensure_default_presets(self) -> None:
        self.presets["temperate"] = TerrainPreset(
            "Temperate", TerrainConfig()
        )
        self.presets["archipelago"] = TerrainPreset(
            "Archipelago",
            TerrainConfig(
                scale=12,
                water_level=0.42,
                mountain_level=0.82,
                forest_threshold=0.62,
                river_count=3,
            ),
        )
        self.presets["alpine"] = TerrainPreset(
            "Alpine",
            TerrainConfig(
                scale=22,
                water_level=0.20,
                mountain_level=0.64,
                forest_threshold=0.48,
                river_count=0,
            ),
        )
        self.presets["dryland"] = TerrainPreset(
            "Dryland",
            TerrainConfig(
                scale=16,
                water_level=0.12,
                mountain_level=0.84,
                forest_threshold=0.72,
                river_count=1,
                road_count=3,
            ),
        )

    @staticmethod
    def _hash_noise(x: int, y: int, seed: int) -> float:
        value = (
            (x & 0xFFFFFFFF) * 0x8DA6B343
            ^ (y & 0xFFFFFFFF) * 0xD8163841
            ^ (seed & 0xFFFFFFFF) * 0xCB1AB31F
        ) & 0xFFFFFFFF
        value = ((value ^ (value >> 16)) * 0x7FEB352D) & 0xFFFFFFFF
        value = ((value ^ (value >> 15)) * 0x846CA68B) & 0xFFFFFFFF
        value ^= value >> 16
        return (value & 0xFFFFFFFF) / 0xFFFFFFFF

    @classmethod
    def _smooth_noise(
        cls,
        x: int,
        y: int,
        scale: float,
        seed: int,
        cache: Optional[Dict[Tuple[int, int], float]] = None,
    ) -> float:
        gx, gy = x / scale, y / scale
        x0, y0 = int(gx), int(gy)
        tx, ty = gx - x0, gy - y0
        tx = tx * tx * (3 - 2 * tx)
        ty = ty * ty * (3 - 2 * ty)
        if cache is None:
            a = cls._hash_noise(x0, y0, seed)
            b = cls._hash_noise(x0 + 1, y0, seed)
            c = cls._hash_noise(x0, y0 + 1, seed)
            d = cls._hash_noise(x0 + 1, y0 + 1, seed)
        else:
            def value(px: int, py: int) -> float:
                coord = (px, py)
                cached = cache.get(coord)
                if cached is None:
                    cached = cls._hash_noise(px, py, seed)
                    cache[coord] = cached
                return cached

            a = value(x0, y0)
            b = value(x0 + 1, y0)
            c = value(x0, y0 + 1)
            d = value(x0 + 1, y0 + 1)
        top = a * (1 - tx) + b * tx
        bottom = c * (1 - tx) + d * tx
        return top * (1 - ty) + bottom * ty

    def generate(
        self,
        width: int,
        height: int,
        config: Optional[TerrainConfig] = None,
        masks: Optional[Dict[str, TerrainMask]] = None,
    ) -> TerrainResult:
        config = config or self.last_config
        width, height = max(1, int(width)), max(1, int(height))
        result = TerrainResult(width, height, config.seed)
        rng = random.Random(config.seed)
        active_masks = masks or self.masks
        caches = ({}, {}, {}, {})

        for y in range(height):
            for x in range(width):
                elevation = (
                    self._smooth_noise(
                        x, y, config.scale, config.seed, caches[0]
                    ) * 0.65
                    + self._smooth_noise(
                        x, y, config.scale / 3.5, config.seed + 17, caches[1]
                    ) * 0.25
                    + self._smooth_noise(
                        x, y, max(1.0, config.scale * 2.5),
                        config.seed + 31, caches[2]
                    ) * 0.10
                )
                moisture = self._smooth_noise(
                    x + 101, y - 79, config.scale * 1.7,
                    config.seed + 97, caches[3],
                )
                if elevation < config.water_level:
                    terrain = TerrainType.LAKE
                elif elevation > config.mountain_level:
                    terrain = TerrainType.MOUNTAIN
                elif moisture > config.forest_threshold:
                    terrain = TerrainType.FOREST
                else:
                    terrain = TerrainType.GRASS
                result.set(x, y, terrain)

        for _ in range(config.river_count):
            self._carve_river(result, rng, config.river_width)
        for _ in range(config.road_count):
            self._carve_road(result, rng, config.road_width)

        for terrain_name, mask in active_masks.items():
            try:
                terrain = TerrainType[terrain_name.upper()]
            except KeyError:
                continue
            for y in range(min(height, mask.height)):
                offset = y * mask.width
                for x in range(min(width, mask.width)):
                    if mask.values[offset + x]:
                        result.set(x, y, terrain)

        if self.current_result is not None:
            self.previous_result = self.current_result.clone()
        self.current_result = result.clone()
        self.last_config = copy.deepcopy(config)
        return result

    @staticmethod
    def _stamp_line(
        result: TerrainResult,
        points: List[Tuple[int, int]],
        width: int,
        terrain: TerrainType,
    ) -> None:
        radius = max(0, (width - 1) // 2)
        for x, y in points:
            for oy in range(-radius, radius + 1):
                for ox in range(-radius, radius + 1):
                    if ox * ox + oy * oy <= radius * radius + 1:
                        result.set(x + ox, y + oy, terrain)

    @staticmethod
    def _bresenham(
        x0: int, y0: int, x1: int, y1: int
    ) -> List[Tuple[int, int]]:
        points = []
        dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
        dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            points.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += sx
            if doubled <= dx:
                error += dx
                y0 += sy
        return points

    def _carve_road(
        self, result: TerrainResult, rng: random.Random, width: int
    ) -> None:
        if result.width < 2 or result.height < 2:
            return
        start = (
            (0, rng.randrange(result.height))
            if rng.random() < 0.5
            else (rng.randrange(result.width), 0)
        )
        end = (
            (result.width - 1, rng.randrange(result.height))
            if start[0] == 0
            else (rng.randrange(result.width), result.height - 1)
        )
        midpoint = (
            (start[0] + end[0]) // 2 + rng.randint(-2, 2),
            (start[1] + end[1]) // 2 + rng.randint(-2, 2),
        )
        points = self._bresenham(*start, *midpoint)
        points.extend(self._bresenham(*midpoint, *end)[1:])
        self._stamp_line(result, points, width, TerrainType.ROAD)

    def _carve_river(
        self, result: TerrainResult, rng: random.Random, width: int
    ) -> None:
        points = []
        x = rng.randrange(result.width)
        direction = rng.choice((-1, 1))
        for y in range(result.height):
            x += direction if rng.random() < 0.38 else rng.choice((-1, 0, 1))
            x = max(0, min(result.width - 1, x))
            points.append((x, y))
        self._stamp_line(result, points, width, TerrainType.WATER)

    def restore_previous(self) -> Optional[TerrainResult]:
        if self.previous_result is None:
            return None
        restored = self.previous_result.clone()
        self.previous_result, self.current_result = self.current_result, restored
        return restored

    def add_preset(self, name: str, config: Optional[TerrainConfig] = None) -> str:
        preset_id = name.strip().casefold().replace(" ", "_")
        self.presets[preset_id] = TerrainPreset(
            name.strip(), copy.deepcopy(config or self.last_config)
        )
        return preset_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "presets": {
                key: preset.to_dict() for key, preset in self.presets.items()
            },
            "last_config": self.last_config.to_dict(),
            "masks": {
                key: mask.to_dict() for key, mask in self.masks.items()
            },
        }

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        self.presets = {
            key: TerrainPreset.from_dict(value)
            for key, value in data.get("presets", {}).items()
            if isinstance(value, dict)
        }
        self._ensure_default_presets()
        self.last_config = TerrainConfig.from_dict(
            data.get("last_config", {})
        )
        self.masks = {
            key: TerrainMask.from_dict(value)
            for key, value in data.get("masks", {}).items()
            if isinstance(value, dict)
        }
