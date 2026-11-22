import random
from typing import List, Tuple, Optional, Dict, Any


class BrushSettings:
    """Configurable brush parameters including size, variants, random rotations, and seed."""

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
    ):
        self.size = max(1, min(size, 10))
        self.spacing = max(1, spacing)
        self.random_variant = random_variant
        self.random_rotation = random_rotation
        self.random_flip_x = random_flip_x
        self.random_flip_y = random_flip_y
        self.jitter = max(0.0, min(1.0, jitter))
        self.density = max(0.1, min(1.0, density))
        self.seed = seed
        self.auto_tile_enabled = auto_tile_enabled

        self.variants: List[Any] = []  # List of Assets or SelectedSubTiles
        self._rng = random.Random(seed) if seed is not None else random.Random()

    def reset_rng(self) -> None:
        if self.seed is not None:
            self._rng = random.Random(self.seed)

    def pick_variant(self, default_item: Any) -> Any:
        if self.random_variant and self.variants:
            return self._rng.choice(self.variants)
        return default_item

    def get_random_transform(self) -> Tuple[float, bool, bool, int, int]:
        """Returns (rotation_deg, flip_x, flip_y, offset_x, offset_y)."""
        rot = self._rng.choice([0.0, 90.0, 180.0, 270.0]) if self.random_rotation else 0.0
        fx = self._rng.choice([True, False]) if self.random_flip_x else False
        fy = self._rng.choice([True, False]) if self.random_flip_y else False
        ox = int(self._rng.uniform(-16, 16) * self.jitter) if self.jitter > 0 else 0
        oy = int(self._rng.uniform(-16, 16) * self.jitter) if self.jitter > 0 else 0
        return rot, fx, fy, ox, oy
