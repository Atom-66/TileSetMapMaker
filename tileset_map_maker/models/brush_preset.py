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


def can_rotate_selection_90(selected_item: Any) -> Tuple[bool, int, int]:
    """
    Checks whether the current selection can be safely rotated by 90°/270°
    without stretching or clipping against the tile grid.
    Non-square tiles (tile_width != tile_height, e.g. 32x48) are blocked.
    """
    if selected_item is None:
        return True, 0, 0
    tw = getattr(selected_item, "tile_width", None)
    th = getattr(selected_item, "tile_height", None)
    if tw is not None and th is not None and int(tw) != int(th):
        return False, int(tw), int(th)
    return True, int(tw or 0), int(th or 0)


def transform_composition_cell(
    dc: int,
    dr: int,
    cols_count: int,
    rows_count: int,
    *,
    flip_x: bool = False,
    flip_y: bool = False,
    rotation: float = 0.0,
) -> Tuple[int, int]:
    """
    Maps a source cell offset (dc, dr) inside a (cols_count x rows_count) multi-tile
    composition to its transformed destination offset (dest_dc, dest_dr) under the
    exact same transform order used by RenderEngine.draw_item:
    1) Flip Horizontal (flip_x) and/or Flip Vertical (flip_y)
    2) Clockwise rotation by 0 / 90 / 180 / 270 degrees.
    """
    fc = (cols_count - 1 - dc) if flip_x else dc
    fr = (rows_count - 1 - dr) if flip_y else dr

    rot = int(round(rotation)) % 360
    if rot == 90:
        return rows_count - 1 - fr, fc
    if rot == 180:
        return cols_count - 1 - fc, rows_count - 1 - fr
    if rot == 270:
        return fr, cols_count - 1 - fc
    return fc, fr


class BrushSettings:
    """Configurable brush parameters including size, variants, deterministic mirror/rotation, weights, and seed."""

    def __init__(
        self,
        size: int = 1,
        spacing: int = 1,
        random_variant: bool = False,
        random_rotation: bool = False,
        flip_horizontal: bool = False,
        flip_vertical: bool = False,
        rotation: int = 0,
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
        # Deterministic Mirror & Rotation state (single source of truth)
        self.flip_horizontal = bool(flip_horizontal)
        self.flip_vertical = bool(flip_vertical)
        self.rotation = int(round(rotation / 90.0) * 90) % 360
        # Legacy fields kept disabled by default for backward-compatible serialization
        self.random_flip_x = bool(random_flip_x)
        self.random_flip_y = bool(random_flip_y)
        self.jitter = max(0.0, min(1.0, jitter))
        self.density = max(0.1, min(1.0, density))
        self.seed = seed
        self.auto_tile_enabled = auto_tile_enabled
        self.avoid_adjacent = avoid_adjacent
        self.selected_autotile: Optional[Any] = None

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

    def toggle_flip_horizontal(self) -> bool:
        """Applies screen-space horizontal flip using exact D4 group composition."""
        self.flip_horizontal = not self.flip_horizontal
        self.rotation = (-self.rotation) % 360
        return self.flip_horizontal

    def toggle_flip_vertical(self) -> bool:
        """Applies screen-space vertical flip using exact D4 group composition."""
        self.flip_vertical = not self.flip_vertical
        self.rotation = (-self.rotation) % 360
        return self.flip_vertical

    def set_flip_horizontal(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled != self.flip_horizontal:
            self.toggle_flip_horizontal()

    def set_flip_vertical(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled != self.flip_vertical:
            self.toggle_flip_vertical()

    def set_rotation(self, degrees: int) -> None:
        self.rotation = int(round(degrees / 90.0) * 90) % 360

    def rotate_cw(self) -> int:
        """Rotates brush orientation 90° clockwise (0 -> 90 -> 180 -> 270 -> 0)."""
        self.rotation = (self.rotation + 90) % 360
        return self.rotation

    def rotate_ccw(self) -> int:
        """Rotates brush orientation 90° counter-clockwise (0 -> 270 -> 180 -> 90 -> 0)."""
        self.rotation = (self.rotation - 90) % 360
        return self.rotation

    def reset_transform(self) -> None:
        self.rotation = 0
        self.flip_horizontal = False
        self.flip_vertical = False

    def get_brush_transform(
        self, *, for_preview: bool = False
    ) -> Tuple[float, bool, bool, int, int]:
        """
        Returns (rotation_deg, flip_x, flip_y, offset_x, offset_y).
        Both Rotation and Mirror are strictly deterministic and never randomized.
        """
        rot = float(self.rotation % 360)
        fx = bool(self.flip_horizontal)
        fy = bool(self.flip_vertical)
        if for_preview or self.jitter <= 0:
            ox, oy = 0, 0
        else:
            ox = int(self._rng.uniform(-16, 16) * self.jitter)
            oy = int(self._rng.uniform(-16, 16) * self.jitter)
        return rot, fx, fy, ox, oy

    def get_random_transform(self) -> Tuple[float, bool, bool, int, int]:
        """Returns (rotation_deg, flip_x, flip_y, offset_x, offset_y) with deterministic mirror."""
        return self.get_brush_transform(for_preview=False)

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
            "flip_horizontal": self.flip_horizontal,
            "flip_vertical": self.flip_vertical,
            "rotation": self.rotation,
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
        self.flip_horizontal = bool(data.get("flip_horizontal", False))
        self.flip_vertical = bool(data.get("flip_vertical", False))
        self.rotation = int(round(data.get("rotation", 0) / 90.0) * 90) % 360
        self.random_flip_x = bool(data.get("random_flip_x", False))
        self.random_flip_y = bool(data.get("random_flip_y", False))
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
