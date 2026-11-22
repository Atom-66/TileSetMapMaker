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

# Cardinal masks
CARDINAL_MASK = MASK_N | MASK_E | MASK_S | MASK_W

# Common bitmask presets
MASK_ISOLATED = 0
MASK_CENTER = 255  # All 8 neighbors present
MASK_EDGE_TOP = MASK_E | MASK_SE | MASK_S | MASK_SW | MASK_W  # No North
MASK_EDGE_BOTTOM = MASK_W | MASK_NW | MASK_N | MASK_NE | MASK_E  # No South
MASK_EDGE_LEFT = MASK_N | MASK_NE | MASK_E | MASK_SE | MASK_S  # No West
MASK_EDGE_RIGHT = MASK_S | MASK_SW | MASK_W | MASK_NW | MASK_N  # No East
MASK_CORNER_TL = MASK_E | MASK_SE | MASK_S  # Top-left outer corner
MASK_CORNER_TR = MASK_W | MASK_SW | MASK_S  # Top-right outer corner
MASK_CORNER_BL = MASK_N | MASK_NE | MASK_E  # Bottom-left outer corner
MASK_CORNER_BR = MASK_W | MASK_NW | MASK_N  # Bottom-right outer corner


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

    def set_mapping(self, mask: int, tile: Tuple[str, int, int, int, int]) -> None:
        self.tile_mappings[mask] = tile

    def get_tile_for_mask(self, mask: int) -> Optional[Tuple[str, int, int, int, int]]:
        # 1. Exact match
        if mask in self.tile_mappings:
            return self.tile_mappings[mask]

        # 2. Match cardinal subset if diagonals are missing
        cardinal = mask & CARDINAL_MASK
        if cardinal in self.tile_mappings:
            return self.tile_mappings[cardinal]

        # 3. Fallback to default tile or center
        if self.default_tile:
            return self.default_tile
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
    ) -> None:
        """
        Quickly sets up standard 3x3 tileset layout:
        (0,0)=TL, (1,0)=Top,    (2,0)=TR
        (0,1)=L,  (1,1)=Center, (2,1)=R
        (0,2)=BL, (1,2)=Bottom, (2,2)=BR
        """
        def _t(cx, cy):
            return (asset_id, start_x + cx * tile_w, start_y + cy * tile_h, tile_w, tile_h)

        self.set_mapping(MASK_CORNER_TL, _t(0, 0))
        self.set_mapping(MASK_EDGE_TOP, _t(1, 0))
        self.set_mapping(MASK_CORNER_TR, _t(2, 0))

        self.set_mapping(MASK_EDGE_LEFT, _t(0, 1))
        self.set_mapping(MASK_CENTER, _t(1, 1))
        self.set_mapping(MASK_EDGE_RIGHT, _t(2, 1))

        self.set_mapping(MASK_CORNER_BL, _t(0, 2))
        self.set_mapping(MASK_EDGE_BOTTOM, _t(1, 2))
        self.set_mapping(MASK_CORNER_BR, _t(2, 2))

        self.default_tile = _t(1, 1)

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
