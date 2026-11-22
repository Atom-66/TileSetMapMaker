from typing import Dict, List, Tuple, Optional, Set
from ..models.layer import Layer, MapItem, ItemType
from ..models.project import Project
from ..models.autotile import (
    AutoTileRuleSet,
    MASK_N,
    MASK_NE,
    MASK_E,
    MASK_SE,
    MASK_S,
    MASK_SW,
    MASK_W,
    MASK_NW,
)


class AutoTileEngine:
    """Computes neighborhood adjacency masks and applies auto-tiling rules."""

    # 8-neighbor offsets and their corresponding bit flags
    NEIGHBORS: List[Tuple[int, int, int]] = [
        (0, -1, MASK_N),
        (1, -1, MASK_NE),
        (1, 0, MASK_E),
        (1, 1, MASK_SE),
        (0, 1, MASK_S),
        (-1, 1, MASK_SW),
        (-1, 0, MASK_W),
        (-1, -1, MASK_NW),
    ]

    def __init__(self):
        self.rulesets: Dict[str, AutoTileRuleSet] = {}
        self.active_ruleset_id: Optional[str] = None

    def register_ruleset(self, ruleset: AutoTileRuleSet) -> None:
        self.rulesets[ruleset.id] = ruleset
        if not self.active_ruleset_id:
            self.active_ruleset_id = ruleset.id

    def get_ruleset(self, ruleset_id: Optional[str]) -> Optional[AutoTileRuleSet]:
        if not ruleset_id:
            return None
        return self.rulesets.get(ruleset_id)

    def get_active_ruleset(self) -> Optional[AutoTileRuleSet]:
        return self.get_ruleset(self.active_ruleset_id)

    def compute_mask(
        self,
        layer: Layer,
        col: int,
        row: int,
        ruleset: AutoTileRuleSet,
        project: Project,
    ) -> int:
        """Calculates 8-neighbor bitmask for (col, row)."""
        mask = 0
        w = project.map_width
        h = project.map_height

        # Helper to check if neighbor matches
        def _matches(nc: int, nr: int) -> bool:
            if not (0 <= nc < w and 0 <= nr < h):
                return True  # Treat map boundaries as connected
            neighbor_item = layer.get_tile(nc, nr)
            if not neighbor_item:
                return False
            # Check terrain_type or asset_id
            if neighbor_item.terrain_type and neighbor_item.terrain_type in ruleset.connects_with:
                return True
            return False

        # Check cardinal neighbors first
        n = _matches(col, row - 1)
        s = _matches(col, row + 1)
        w_flag = _matches(col - 1, row)
        e = _matches(col + 1, row)

        if n:
            mask |= MASK_N
        if s:
            mask |= MASK_S
        if w_flag:
            mask |= MASK_W
        if e:
            mask |= MASK_E

        # Diagonals only count if adjacent cardinals match
        if n and e and _matches(col + 1, row - 1):
            mask |= MASK_NE
        if s and e and _matches(col + 1, row + 1):
            mask |= MASK_SE
        if s and w_flag and _matches(col - 1, row + 1):
            mask |= MASK_SW
        if n and w_flag and _matches(col - 1, row - 1):
            mask |= MASK_NW

        return mask

    def update_tile_at(
        self,
        layer: Layer,
        col: int,
        row: int,
        ruleset: AutoTileRuleSet,
        project: Project,
    ) -> Optional[MapItem]:
        """Recalculates tile slice for (col, row) according to neighborhood mask."""
        curr = layer.get_tile(col, row)
        if not curr or not curr.is_auto_tiled:
            return None

        mask = self.compute_mask(layer, col, row, ruleset, project)
        tile_data = ruleset.get_tile_for_mask(mask)
        if not tile_data:
            return None

        aid, sx, sy, sw, sh = tile_data
        curr.asset_id = aid
        curr.source_x = sx
        curr.source_y = sy
        curr.source_w = sw
        curr.source_h = sh
        curr.dest_w = project.tile_size
        curr.dest_h = project.tile_size
        curr.terrain_type = ruleset.terrain_type
        return curr

    def apply_autotile_stroke(
        self,
        layer: Layer,
        coords: List[Tuple[int, int]],
        ruleset: AutoTileRuleSet,
        project: Project,
    ) -> Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]]:
        """
        Updates placed coordinates and their 8 neighbors, returning before/after dict.
        """
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}
        if not layer.auto_tiling_enabled:
            return changes

        # Find all coordinates needing recalculation (points + neighbors)
        affected: Set[Tuple[int, int]] = set(coords)
        for c, r in coords:
            for dx, dy, _ in self.NEIGHBORS:
                nc, nr = c + dx, r + dy
                if 0 <= nc < project.map_width and 0 <= nr < project.map_height:
                    tile = layer.get_tile(nc, nr)
                    if tile and tile.is_auto_tiled and tile.terrain_type == ruleset.terrain_type:
                        affected.add((nc, nr))

        for c, r in affected:
            tile = layer.get_tile(c, r)
            if tile and tile.is_auto_tiled:
                prev_clone = tile.clone()
                self.update_tile_at(layer, c, r, ruleset, project)
                changes[(c, r)] = (prev_clone, tile.clone())

        return changes
