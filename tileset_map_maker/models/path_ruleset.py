import uuid
from typing import Dict, Tuple, Optional, List, Any

# Bitmask directional constants from autotile system
from .autotile import (
    MASK_N,
    MASK_NE,
    MASK_E,
    MASK_SE,
    MASK_S,
    MASK_SW,
    MASK_W,
    MASK_NW,
    CARDINAL_MASK,
)

# Standard role identifiers for Path Generator
ROLE_STRAIGHT_H = "straight_h"    # Horizontal line (W + E)
ROLE_STRAIGHT_V = "straight_v"    # Vertical line (N + S)
ROLE_CORNER_TL = "corner_tl"      # Top-Left bend (connects E + S)
ROLE_CORNER_TR = "corner_tr"      # Top-Right bend (connects W + S)
ROLE_CORNER_BL = "corner_bl"      # Bottom-Left bend (connects E + N)
ROLE_CORNER_BR = "corner_br"      # Bottom-Right bend (connects W + N)
ROLE_CORNER_GENERIC = "corner_generic"  # Universal corner (used in 4-tile sets)
ROLE_T_JUNCTION = "t_junction"    # T-junction 3-way
ROLE_CROSS = "cross"              # 4-way intersection (N + S + W + E)
ROLE_END = "end"                  # Dead end / endpoint
ROLE_CENTER = "center"            # Solid path center (fallback / isolated)

ROLE_NAMES = {
    ROLE_STRAIGHT_H: "═ Prosta pozioma",
    ROLE_STRAIGHT_V: "║ Prosta pionowa",
    ROLE_CORNER_TL: "╔ Zakręt góra-lewo (E-S)",
    ROLE_CORNER_TR: "╗ Zakręt góra-prawo (W-S)",
    ROLE_CORNER_BL: "╚ Zakręt dół-lewo (E-N)",
    ROLE_CORNER_BR: "╝ Zakręt dół-prawo (W-N)",
    ROLE_CORNER_GENERIC: "🔄 Zakręt (uniwersalny)",
    ROLE_T_JUNCTION: "╦ Rozgałęzienie T (3-kierunkowe)",
    ROLE_CROSS: "╬ Skrzyżowanie (4-kierunkowe)",
    ROLE_END: "🛑 Zakończenie ścieżki",
    ROLE_CENTER: "⏹️ Środek / Izolowany",
}

TEMPLATE_4_TILE = [ROLE_STRAIGHT_H, ROLE_STRAIGHT_V, ROLE_CORNER_GENERIC, ROLE_CROSS]
TEMPLATE_6_TILE = [ROLE_STRAIGHT_H, ROLE_STRAIGHT_V, ROLE_CORNER_TL, ROLE_CORNER_TR, ROLE_CORNER_BL, ROLE_CORNER_BR]
TEMPLATE_CUSTOM = [
    ROLE_STRAIGHT_H,
    ROLE_STRAIGHT_V,
    ROLE_CORNER_TL,
    ROLE_CORNER_TR,
    ROLE_CORNER_BL,
    ROLE_CORNER_BR,
    ROLE_T_JUNCTION,
    ROLE_CROSS,
    ROLE_END,
    ROLE_CENTER,
]


class PathRuleSet:
    """
    Defines a path ruleset where individual tile roles are manually assigned
    by the user from anywhere in the tileset (non-contiguous tiles supported).
    Seamlessly integrates with the Auto-Tiling neighbor analysis engine.
    """

    def __init__(
        self,
        name: str = "Nowa ścieżka",
        terrain_type: str = "Path",
        ruleset_id: Optional[str] = None,
        connects_with: Optional[List[str]] = None,
        template_type: str = "6_tile",
        id: Optional[str] = None,
    ):
        self.id = ruleset_id or id or str(uuid.uuid4())
        self.name = name
        self.terrain_type = terrain_type
        self.connects_with = connects_with or [terrain_type]
        self.template_type = template_type  # "4_tile", "6_tile", "custom"

        # Map: role_id -> (asset_id, source_x, source_y, source_w, source_h)
        self.roles: Dict[str, Optional[Tuple[str, int, int, int, int]]] = {}

        # Default tile mappings for bitmask engine
        self.default_tile: Optional[Tuple[str, int, int, int, int]] = None

    @property
    def is_path_ruleset(self) -> bool:
        return True

    @property
    def asset_id(self) -> str:
        """Returns the primary asset_id from assigned roles."""
        for tile in self.roles.values():
            if tile:
                return tile[0]
        return ""

    def set_role_tile(
        self,
        role: str,
        tile: Any,
    ) -> None:
        """Assigns or clears a specific tile for a path role. Accepts tuple or SelectedSubTile."""
        if tile is not None and hasattr(tile, "asset_id"):
            tile_tuple = (tile.asset_id, tile.sub_x, tile.sub_y, tile.sub_w, tile.sub_h)
        else:
            tile_tuple = tile
        self.roles[role] = tile_tuple
        if not self.default_tile and tile_tuple:
            self.default_tile = tile_tuple

    def get_role_tile(self, role: str) -> Optional[Tuple[str, int, int, int, int]]:
        return self.roles.get(role)

    def remove_role(self, role: str) -> None:
        """Removes an assignment for a given role."""
        if role in self.roles:
            del self.roles[role]

    def is_complete(self) -> bool:
        """Checks if all required roles for the active template are assigned."""
        req = self.get_template_roles()
        return all(self.roles.get(r) is not None for r in req)

    def get_template_roles(self) -> List[str]:
        if self.template_type == "4_tile":
            return TEMPLATE_4_TILE
        elif self.template_type == "6_tile":
            return TEMPLATE_6_TILE
        return TEMPLATE_CUSTOM

    def get_tile_for_mask(self, mask: int) -> Optional[Tuple[str, int, int, int, int]]:
        """
        Resolves the appropriate path tile based on neighbor bitmask.
        Maps the 4 cardinal connections (N, S, W, E) to path roles with smart fallbacks.
        """
        has_n = bool(mask & MASK_N)
        has_s = bool(mask & MASK_S)
        has_e = bool(mask & MASK_E)
        has_w = bool(mask & MASK_W)

        cardinal_count = sum([has_n, has_s, has_e, has_w])

        # 1. 4-way Cross Intersection (N, S, E, W)
        if cardinal_count == 4:
            if self.roles.get(ROLE_CROSS):
                return self.roles[ROLE_CROSS]
            if self.roles.get(ROLE_T_JUNCTION):
                return self.roles[ROLE_T_JUNCTION]
            if self.roles.get(ROLE_STRAIGHT_H):
                return self.roles[ROLE_STRAIGHT_H]
            if self.roles.get(ROLE_STRAIGHT_V):
                return self.roles[ROLE_STRAIGHT_V]

        # 2. 3-way T-Junctions
        if cardinal_count == 3:
            if self.roles.get(ROLE_T_JUNCTION):
                return self.roles[ROLE_T_JUNCTION]
            if self.roles.get(ROLE_CROSS):
                return self.roles[ROLE_CROSS]
            # Fallback: bend or straight
            if has_w and has_e and self.roles.get(ROLE_STRAIGHT_H):
                return self.roles[ROLE_STRAIGHT_H]
            if has_n and has_s and self.roles.get(ROLE_STRAIGHT_V):
                return self.roles[ROLE_STRAIGHT_V]

        # 3. 2-way Corners / Bends
        if has_e and has_s and not has_n and not has_w:
            # Top-Left turn (curves to East and South)
            return self._resolve_corner(ROLE_CORNER_TL)

        if has_w and has_s and not has_n and not has_e:
            # Top-Right turn (curves to West and South)
            return self._resolve_corner(ROLE_CORNER_TR)

        if has_e and has_n and not has_s and not has_w:
            # Bottom-Left turn (curves to East and North)
            return self._resolve_corner(ROLE_CORNER_BL)

        if has_w and has_n and not has_s and not has_e:
            # Bottom-Right turn (curves to West and North)
            return self._resolve_corner(ROLE_CORNER_BR)

        # 4. 2-way Straight Lines
        if has_w and has_e and not has_n and not has_s:
            if self.roles.get(ROLE_STRAIGHT_H):
                return self.roles[ROLE_STRAIGHT_H]
            if self.roles.get(ROLE_STRAIGHT_V):
                return self.roles[ROLE_STRAIGHT_V]

        if has_n and has_s and not has_w and not has_e:
            if self.roles.get(ROLE_STRAIGHT_V):
                return self.roles[ROLE_STRAIGHT_V]
            if self.roles.get(ROLE_STRAIGHT_H):
                return self.roles[ROLE_STRAIGHT_H]

        # 5. 1-way Endpoints / Dead ends
        if cardinal_count == 1:
            if self.roles.get(ROLE_END):
                return self.roles[ROLE_END]
            # Smart fallback for endpoints: straight segment matching line direction
            if (has_w or has_e) and self.roles.get(ROLE_STRAIGHT_H):
                return self.roles[ROLE_STRAIGHT_H]
            if (has_n or has_s) and self.roles.get(ROLE_STRAIGHT_V):
                return self.roles[ROLE_STRAIGHT_V]

        # 6. Isolated single cell or default fallback
        if self.roles.get(ROLE_CENTER):
            return self.roles[ROLE_CENTER]
        if self.roles.get(ROLE_END):
            return self.roles[ROLE_END]
        if self.roles.get(ROLE_STRAIGHT_H):
            return self.roles[ROLE_STRAIGHT_H]
        if self.roles.get(ROLE_STRAIGHT_V):
            return self.roles[ROLE_STRAIGHT_V]
        if self.default_tile:
            return self.default_tile

        # Any assigned tile in the set
        for tile in self.roles.values():
            if tile:
                return tile
        return None

    def _resolve_corner(self, specific_role: str) -> Optional[Tuple[str, int, int, int, int]]:
        """Resolves specific corner, falling back to generic corner or straight line."""
        if self.roles.get(specific_role):
            return self.roles[specific_role]
        if self.roles.get(ROLE_CORNER_GENERIC):
            return self.roles[ROLE_CORNER_GENERIC]
        # Fallback to straight segment if no corner assigned
        if self.roles.get(ROLE_STRAIGHT_H):
            return self.roles[ROLE_STRAIGHT_H]
        if self.roles.get(ROLE_STRAIGHT_V):
            return self.roles[ROLE_STRAIGHT_V]
        return self.default_tile

    def to_dict(self) -> Dict[str, Any]:
        roles_data = {}
        for role, tile in self.roles.items():
            roles_data[role] = list(tile) if tile else None
        return {
            "id": self.id,
            "name": self.name,
            "terrain_type": self.terrain_type,
            "connects_with": self.connects_with,
            "template_type": self.template_type,
            "roles": roles_data,
            "default_tile": list(self.default_tile) if self.default_tile else None,
            "is_path_ruleset": True,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PathRuleSet":
        prs = cls(
            name=data.get("name", "Ścieżka"),
            terrain_type=data.get("terrain_type", "Path"),
            ruleset_id=data.get("id"),
            connects_with=data.get("connects_with", ["Path"]),
            template_type=data.get("template_type", "6_tile"),
        )
        for role, tile_list in data.get("roles", {}).items():
            if tile_list:
                prs.roles[role] = tuple(tile_list)
            else:
                prs.roles[role] = None
        if data.get("default_tile"):
            prs.default_tile = tuple(data["default_tile"])
        return prs
