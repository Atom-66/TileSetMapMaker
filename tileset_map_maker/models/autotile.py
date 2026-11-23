import uuid
from typing import Dict, List, Optional, Tuple, Any

# Bitmask flags for 8-neighbor adjacency
MASK_N = 1
MASK_NE = 2
MASK_E = 4
MASK_SE = 8
MASK_S = 16
MASK_SW = 32
MASK_W = 64
MASK_NW = 128

# Cardinal mask (N, E, S, W)
CARDINAL_MASK = MASK_N | MASK_E | MASK_S | MASK_W  # 85

# Cardinal values for 3x3 box positions
CARD_CORNER_TL = MASK_E | MASK_S  # 20
CARD_EDGE_TOP = MASK_E | MASK_S | MASK_W  # 84
CARD_CORNER_TR = MASK_W | MASK_S  # 80

CARD_EDGE_LEFT = MASK_N | MASK_S | MASK_E  # 21
CARD_CENTER = MASK_N | MASK_S | MASK_E | MASK_W  # 85
CARD_EDGE_RIGHT = MASK_N | MASK_S | MASK_W  # 81

CARD_CORNER_BL = MASK_N | MASK_E  # 5
CARD_EDGE_BOTTOM = MASK_N | MASK_E | MASK_W  # 69
CARD_CORNER_BR = MASK_N | MASK_W  # 65

# Full 8-neighbor values with diagonals
MASK_ISOLATED = 0
MASK_CENTER = 255  # All 8 neighbors present
MASK_EDGE_TOP = CARD_EDGE_TOP | MASK_SE | MASK_SW  # 124
MASK_EDGE_BOTTOM = CARD_EDGE_BOTTOM | MASK_NE | MASK_NW  # 199
MASK_EDGE_LEFT = CARD_EDGE_LEFT | MASK_NE | MASK_SE  # 31
MASK_EDGE_RIGHT = CARD_EDGE_RIGHT | MASK_NW | MASK_SW  # 241
MASK_CORNER_TL = CARD_CORNER_TL | MASK_SE  # 28
MASK_CORNER_TR = CARD_CORNER_TR | MASK_SW  # 112
MASK_CORNER_BL = CARD_CORNER_BL | MASK_NE  # 7
MASK_CORNER_BR = CARD_CORNER_BR | MASK_NW  # 193


class AutoTileRuleSet:
    """Defines an auto-tiling ruleset for a specific terrain type."""

    def __init__(
        self,
        name: str = "Trawa – Brzegi",
        terrain_type: str = "Grass",
        ruleset_id: Optional[str] = None,
        connects_with: Optional[List[str]] = None,
        default_tile: Optional[Tuple[str, int, int, int, int]] = None,
    ):
        self.id = ruleset_id or str(uuid.uuid4())
        self.name = name
        self.terrain_type = terrain_type
        self.connects_with = connects_with or [terrain_type]
        # Map: bitmask (int) -> (asset_id, source_x, source_y, source_w, source_h)
        self.tile_mappings: Dict[int, Tuple[str, int, int, int, int]] = {}
        self.default_tile = default_tile

    @property
    def asset_id(self) -> str:
        if self.default_tile:
            return self.default_tile[0]
        for tile in self.tile_mappings.values():
            return tile[0]
        return ""

    def set_mapping(self, mask: int, tile: Tuple[str, int, int, int, int]) -> None:
        self.tile_mappings[mask] = tile

    def get_tile_for_mask(self, mask: int) -> Optional[Tuple[str, int, int, int, int]]:
        """
        Resolves the appropriate tile slice for a given 8-neighbor bitmask.
        Resolution pipeline:
        1. Exact 8-neighbor bitmask match
        2. Direct cardinal (4-neighbor N, S, W, E) match
        3. Smart geometric reduction (corners, edges, linear strips)
        4. Fallback to default / center tile
        """
        # 1. Exact match
        if mask in self.tile_mappings:
            return self.tile_mappings[mask]

        # 2. Match cardinal subset (N, E, S, W)
        cardinal = mask & CARDINAL_MASK
        if cardinal in self.tile_mappings:
            return self.tile_mappings[cardinal]

        # 3. Geometric reduction based on which cardinal sides are present
        has_n = bool(mask & MASK_N)
        has_s = bool(mask & MASK_S)
        has_e = bool(mask & MASK_E)
        has_w = bool(mask & MASK_W)

        # Corners
        if has_s and has_e and not has_n and not has_w:
            for k in (CARD_CORNER_TL, MASK_CORNER_TL):
                if k in self.tile_mappings:
                    return self.tile_mappings[k]
        if has_s and has_w and not has_n and not has_e:
            for k in (CARD_CORNER_TR, MASK_CORNER_TR):
                if k in self.tile_mappings:
                    return self.tile_mappings[k]
        if has_n and has_e and not has_s and not has_w:
            for k in (CARD_CORNER_BL, MASK_CORNER_BL):
                if k in self.tile_mappings:
                    return self.tile_mappings[k]
        if has_n and has_w and not has_s and not has_e:
            for k in (CARD_CORNER_BR, MASK_CORNER_BR):
                if k in self.tile_mappings:
                    return self.tile_mappings[k]

        # Edges
        if not has_n and has_s:
            for k in (CARD_EDGE_TOP, MASK_EDGE_TOP):
                if k in self.tile_mappings:
                    return self.tile_mappings[k]
        if not has_s and has_n:
            for k in (CARD_EDGE_BOTTOM, MASK_EDGE_BOTTOM):
                if k in self.tile_mappings:
                    return self.tile_mappings[k]
        if not has_w and has_e:
            for k in (CARD_EDGE_LEFT, MASK_EDGE_LEFT):
                if k in self.tile_mappings:
                    return self.tile_mappings[k]
        if not has_e and has_w:
            for k in (CARD_EDGE_RIGHT, MASK_EDGE_RIGHT):
                if k in self.tile_mappings:
                    return self.tile_mappings[k]

        # 4. Fallback to default tile or center
        if self.default_tile:
            return self.default_tile
        if CARD_CENTER in self.tile_mappings:
            return self.tile_mappings[CARD_CENTER]
        if MASK_CENTER in self.tile_mappings:
            return self.tile_mappings[MASK_CENTER]
        if self.tile_mappings:
            return next(iter(self.tile_mappings.values()))
        return None

    def setup_standard_3x3_box(
        self,
        asset_id: str,
        start_x: int,
        start_y: int,
        tile_w: int,
        tile_h: int,
        spacing_x: int = 0,
        spacing_y: int = 0,
    ) -> None:
        """
        Configures standard 3x3 tileset layout:
        (0,0)=TL, (1,0)=Top,    (2,0)=TR
        (0,1)=L,  (1,1)=Center, (2,1)=R
        (0,2)=BL, (1,2)=Bottom, (2,2)=BR
        Registers both 8-neighbor and 4-neighbor cardinal masks plus linear fallbacks.
        """
        def _t(cx: int, cy: int) -> Tuple[str, int, int, int, int]:
            sx = start_x + cx * (tile_w + spacing_x)
            sy = start_y + cy * (tile_h + spacing_y)
            return (asset_id, sx, sy, tile_w, tile_h)

        tl = _t(0, 0)
        top = _t(1, 0)
        tr = _t(2, 0)
        left = _t(0, 1)
        center = _t(1, 1)
        right = _t(2, 1)
        bl = _t(0, 2)
        bottom = _t(1, 2)
        br = _t(2, 2)

        # 1. 8-neighbor masks (solid area with diagonals)
        self.set_mapping(MASK_CORNER_TL, tl)
        self.set_mapping(MASK_EDGE_TOP, top)
        self.set_mapping(MASK_CORNER_TR, tr)
        self.set_mapping(MASK_EDGE_LEFT, left)
        self.set_mapping(MASK_CENTER, center)
        self.set_mapping(MASK_EDGE_RIGHT, right)
        self.set_mapping(MASK_CORNER_BL, bl)
        self.set_mapping(MASK_EDGE_BOTTOM, bottom)
        self.set_mapping(MASK_CORNER_BR, br)

        # 2. Cardinal masks (Crucial for any shape with open or missing diagonals!)
        self.set_mapping(CARD_CORNER_TL, tl)
        self.set_mapping(CARD_EDGE_TOP, top)
        self.set_mapping(CARD_CORNER_TR, tr)
        self.set_mapping(CARD_EDGE_LEFT, left)
        self.set_mapping(CARD_CENTER, center)
        self.set_mapping(CARD_EDGE_RIGHT, right)
        self.set_mapping(CARD_CORNER_BL, bl)
        self.set_mapping(CARD_EDGE_BOTTOM, bottom)
        self.set_mapping(CARD_CORNER_BR, br)

        # 3. Fallbacks for thin lines and endpoints
        self.set_mapping(MASK_E | MASK_W, top)          # Horizontal strip
        self.set_mapping(MASK_N | MASK_S, left)         # Vertical strip
        self.set_mapping(MASK_S, top)                   # Single top endpoint
        self.set_mapping(MASK_N, bottom)                # Single bottom endpoint
        self.set_mapping(MASK_E, left)                  # Single left endpoint
        self.set_mapping(MASK_W, right)                 # Single right endpoint
        self.set_mapping(0, center)                     # Isolated single tile

        self.default_tile = center

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "terrain_type": self.terrain_type,
            "connects_with": self.connects_with,
            "tile_mappings": {str(k): list(v) for k, v in self.tile_mappings.items()},
            "default_tile": list(self.default_tile) if self.default_tile else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutoTileRuleSet":
        rs = cls(
            name=data.get("name", "AutoTile Rule"),
            terrain_type=data.get("terrain_type", "Grass"),
            ruleset_id=data.get("id"),
            connects_with=data.get("connects_with", []),
            default_tile=tuple(data["default_tile"]) if data.get("default_tile") else None,
        )
        for k_str, val in data.get("tile_mappings", {}).items():
            rs.tile_mappings[int(k_str)] = tuple(val)
        return rs
