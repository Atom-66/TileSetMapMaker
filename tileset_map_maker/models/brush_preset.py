import random
import uuid
from typing import List, Tuple, Optional, Dict, Any


class TileVariant:
    """
    Represents an individual tile variant in a randomization group.
    Holds reference to subtile slice coordinates and user-defined probability weight.
    """

    def __init__(
        self,
        sub_tile: Any,
        weight: float = 10.0,
        name: str = "",
        variant_id: Optional[str] = None,
    ):
        self.id = variant_id or str(uuid.uuid4())
        self.sub_tile = sub_tile
        self.weight = max(0.01, float(weight))
        col = getattr(sub_tile, "col", 0)
        row = getattr(sub_tile, "row", 0)
        self.name = name or f"Wariant ({col}, {row})"

    def to_dict(self) -> Dict[str, Any]:
        sub_dict = self.sub_tile.to_dict() if hasattr(self.sub_tile, "to_dict") else {}
        return {
            "id": self.id,
            "sub_tile": sub_dict,
            "weight": self.weight,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["TileVariant"]:
        try:
            from .asset import SelectedSubTile
            sub = SelectedSubTile.from_dict(data["sub_tile"])
            return cls(
                sub_tile=sub,
                weight=data.get("weight", 10.0),
                name=data.get("name", ""),
                variant_id=data.get("id"),
            )
        except Exception:
            return None


class BrushSettings:
    """Configurable brush parameters including size, variants, random rotations, weights, and seed."""

    def __init__(
        self,
        size: int = 1,
        spacing: int = 1,
        random_variant: bool = False,
        random_rotation: bool = False,
        random_flip_x: bool = False,
        random_flip_y: bool = False,
        jitter: float = 0.0,
        density: float = 1.0,
        seed: Optional[int] = None,
        auto_tile_enabled: bool = False,
        avoid_adjacent: bool = False,
        eraser_size: int = 1,
        gap_min: int = 0,
        gap_max: int = 0,
    ):
        self.size = max(1, min(size, 10))
        self.eraser_size = max(1, min(eraser_size, 10))
        self.gap_min = max(0, min(int(gap_min), 50))
        self.gap_max = max(self.gap_min, min(int(gap_max), 50))
        self._remaining_gap = 0
        self.spacing = max(1, spacing)
        self.random_variant = random_variant
        self.random_rotation = random_rotation
        self.random_flip_x = random_flip_x
        self.random_flip_y = random_flip_y
        self.jitter = max(0.0, min(1.0, jitter))
        self.density = max(0.1, min(1.0, density))
        self.seed = seed
        self.auto_tile_enabled = auto_tile_enabled
        self.avoid_adjacent = avoid_adjacent

        # List of TileVariant objects (also accepts raw SelectedSubTile or Asset for backward compatibility)
        self.variants: List[Any] = []
        self._rng = random.Random(seed) if seed is not None else random.Random()
        self._last_chosen_id: Optional[str] = None

    def reset_rng(self) -> None:
        """Resets the random number generator using the active seed."""
        if self.seed is not None:
            self._rng = random.Random(self.seed)
        else:
            self._rng = random.Random()
        self._last_chosen_id = None
        self._remaining_gap = 0

    def set_seed(self, seed: Optional[int]) -> None:
        self.seed = seed
        self.reset_rng()

    def add_variant(self, item: Any, weight: float = 10.0, name: str = "") -> TileVariant:
        """Adds a tile item as a variant, wrapping it in TileVariant if needed."""
        if isinstance(item, TileVariant):
            var = item
        else:
            var = TileVariant(sub_tile=item, weight=weight, name=name)
        self.variants.append(var)
        return var

    def remove_variant(self, index: int) -> bool:
        if 0 <= index < len(self.variants):
            self.variants.pop(index)
            return True
        return False

    def move_variant(self, from_idx: int, to_idx: int) -> bool:
        if 0 <= from_idx < len(self.variants) and 0 <= to_idx < len(self.variants):
            item = self.variants.pop(from_idx)
            self.variants.insert(to_idx, item)
            return True
        return False

    def clear_variants(self) -> None:
        self.variants.clear()
        self._last_chosen_id = None

    def set_equal_weights(self, weight: float = 10.0) -> None:
        """Sets equal probability weight for all configured variants."""
        for v in self.variants:
            if isinstance(v, TileVariant):
                v.weight = float(weight)

    def pick_variant(
        self,
        default_item: Any,
        avoid_adjacent_items: Optional[List[Any]] = None,
    ) -> Any:
        """
        Picks a random tile variant according to configured weights.
        Supports 'avoid_adjacent' to avoid placing identical variants immediately next to each other.
        """
        if not self.random_variant or not self.variants:
            return default_item

        # Normalize candidates to TileVariant wrappers
        normalized: List[TileVariant] = []
        for v in self.variants:
            if isinstance(v, TileVariant):
                normalized.append(v)
            else:
                normalized.append(TileVariant(sub_tile=v, weight=10.0))

        if len(normalized) == 1:
            self._last_chosen_id = normalized[0].id
            return normalized[0].sub_tile

        candidates = normalized

        # Avoid adjacent duplicates filter if requested
        if self.avoid_adjacent:
            avoid_keys = set()
            if self._last_chosen_id:
                avoid_keys.add(self._last_chosen_id)

            if avoid_adjacent_items:
                for adj in avoid_adjacent_items:
                    if adj is not None:
                        # Match by (source_x, source_y) or asset_id
                        sx = getattr(adj, "source_x", None)
                        sy = getattr(adj, "source_y", None)
                        if sx is not None and sy is not None:
                            avoid_keys.add((sx, sy))

            filtered = []
            for c in candidates:
                sub = c.sub_tile
                csx = getattr(sub, "sub_x", getattr(sub, "source_x", None))
                csy = getattr(sub, "sub_y", getattr(sub, "source_y", None))
                if c.id not in avoid_keys and (csx, csy) not in avoid_keys:
                    filtered.append(c)

            if filtered:
                candidates = filtered

        # Weighted selection
        weights = [c.weight for c in candidates]
        chosen = self._rng.choices(candidates, weights=weights, k=1)[0]
        self._last_chosen_id = chosen.id
        return chosen.sub_tile

    def get_random_transform(self) -> Tuple[float, bool, bool, int, int]:
        """Returns (rotation_deg, flip_x, flip_y, offset_x, offset_y)."""
        rot = self._rng.choice([0.0, 90.0, 180.0, 270.0]) if self.random_rotation else 0.0
        fx = self._rng.choice([True, False]) if self.random_flip_x else False
        fy = self._rng.choice([True, False]) if self.random_flip_y else False
        ox = int(self._rng.uniform(-16, 16) * self.jitter) if self.jitter > 0 else 0
        oy = int(self._rng.uniform(-16, 16) * self.jitter) if self.jitter > 0 else 0
        return rot, fx, fy, ox, oy

    def to_dict(self) -> Dict[str, Any]:
        vars_list = []
        for v in self.variants:
            if isinstance(v, TileVariant):
                vars_list.append(v.to_dict())
            elif hasattr(v, "to_dict"):
                vars_list.append({"sub_tile": v.to_dict(), "weight": 10.0, "name": ""})
        return {
            "size": self.size,
            "eraser_size": self.eraser_size,
            "random_variant": self.random_variant,
            "random_rotation": self.random_rotation,
            "random_flip_x": self.random_flip_x,
            "random_flip_y": self.random_flip_y,
            "seed": self.seed,
            "auto_tile_enabled": self.auto_tile_enabled,
            "avoid_adjacent": self.avoid_adjacent,
            "gap_min": self.gap_min,
            "gap_max": self.gap_max,
            "variants": vars_list,
        }

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        self.size = data.get("size", self.size)
        self.eraser_size = max(1, min(data.get("eraser_size", getattr(self, "eraser_size", 1)), 10))
        self.random_variant = data.get("random_variant", False)
        self.random_rotation = data.get("random_rotation", False)
        self.random_flip_x = data.get("random_flip_x", False)
        self.random_flip_y = data.get("random_flip_y", False)
        self.seed = data.get("seed", None)
        self.auto_tile_enabled = data.get("auto_tile_enabled", False)
        self.avoid_adjacent = data.get("avoid_adjacent", False)
        self.gap_min = max(0, int(data.get("gap_min", 0)))
        self.gap_max = max(
            self.gap_min, min(50, int(data.get("gap_max", self.gap_min)))
        )
        self.reset_rng()

        self.variants.clear()
        for v_data in data.get("variants", []):
            var = TileVariant.from_dict(v_data)
            if var:
                self.variants.append(var)

    def consume_gap(self) -> bool:
        """Return True when the current randomizer block should be skipped."""
        if self.gap_max <= 0:
            return False
        if self._remaining_gap > 0:
            self._remaining_gap -= 1
            return True
        self._remaining_gap = self._rng.randint(self.gap_min, self.gap_max)
        return False
