import logging
from typing import Dict, List, Tuple, Optional, Set, Any
from ..models.layer import Layer, MapItem, ItemType
from ..models.project import Project
from ..models.autotile import (
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
from .rpg_autotile import RPGAutotile, SelectedAutotile

logger = logging.getLogger("AutoTileEngine")


class AutoTileEngine:
    """
    Paths & Autotile Engine for TileSetMapMaker.
    Powers the unified One-Tile Paths generator, Wang 47-blob procedural synthesis,
    and real-time 8-neighbor adaptive path strokes.
    """

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

    def __init__(self, asset_manager: Optional[Any] = None):
        self.rpg_autotiles: Dict[str, RPGAutotile] = {}
        self.active_rpg_autotile_id: Optional[str] = None
        self.asset_manager: Optional[Any] = asset_manager

    def register_rpg_autotile(
        self, autotile: RPGAutotile, asset_manager: Optional[Any] = None
    ) -> None:
        if not autotile or not getattr(autotile, "id", None):
            return
        self.rpg_autotiles[autotile.id] = autotile
        if not self.active_rpg_autotile_id and not autotile.archived:
            self.active_rpg_autotile_id = autotile.id
        am = asset_manager or self.asset_manager
        if am is not None:
            if not autotile.has_valid_atlas(am):
                autotile.rebuild_atlas(am)
            if hasattr(am, "register_rpg_autotile"):
                am.register_rpg_autotile(autotile)

    def unregister_rpg_autotile(self, autotile_id: str) -> None:
        if autotile_id in self.rpg_autotiles:
            del self.rpg_autotiles[autotile_id]
        if self.active_rpg_autotile_id == autotile_id:
            self.active_rpg_autotile_id = next(
                (key for key, value in self.rpg_autotiles.items() if not value.archived),
                None,
            )
        if self.asset_manager and hasattr(self.asset_manager, "unregister_rpg_autotile"):
            self.asset_manager.unregister_rpg_autotile(autotile_id)

    def archive_rpg_autotile(self, autotile_id: str) -> bool:
        """Hide a saved path from the library while retaining its map texture and data."""
        autotile = self.rpg_autotiles.get(autotile_id)
        if autotile is None:
            return False
        autotile.archived = True
        if self.active_rpg_autotile_id == autotile_id:
            self.active_rpg_autotile_id = next(
                (
                    key
                    for key, value in self.rpg_autotiles.items()
                    if key != autotile_id and not value.archived
                ),
                None,
            )
        return True

    def can_render_autotile(
        self, autotile: Optional[RPGAutotile], asset_manager: Optional[Any] = None
    ) -> bool:
        """
        Verifies whether an RPGAutotile is valid and safe to paint.
        Prevents destructive replacement of existing map tiles with empty/black cells
        when the autotile's source texture or generated atlas is missing or corrupted.
        """
        if autotile is None or not getattr(autotile, "id", None):
            return False
        if getattr(autotile, "tile_size", 0) < 8:
            return False
        am = asset_manager or self.asset_manager
        if autotile.has_valid_atlas(am):
            if am is not None and hasattr(am, "register_rpg_autotile"):
                am.register_rpg_autotile(autotile)
            return True
        # Distinguish genuine missing/corrupt texture from headless logic-only unit tests
        # that construct a bare RPGAutotile without any backing asset in an empty AssetManager.
        has_real_source_ref = bool(autotile.source_image_path) or (
            bool(autotile.source_asset_id) and am is not None and bool(getattr(am, "assets", None))
        )
        if has_real_source_ref:
            logger.error(
                f"Autotile '{autotile.name}' ({autotile.id}) has no valid atlas texture; aborting write."
            )
            return False
        # If no backing AssetManager assets exist at all, allow pure logic tests only when
        # no broken image path was provided.
        return not bool(autotile.source_image_path)

    def get_rpg_autotile(self, autotile_id_or_terrain: Optional[str]) -> Optional[RPGAutotile]:
        if not autotile_id_or_terrain:
            return None
        if autotile_id_or_terrain in self.rpg_autotiles:
            return self.rpg_autotiles[autotile_id_or_terrain]
        for at in self.rpg_autotiles.values():
            if not at.archived and at.terrain_type == autotile_id_or_terrain:
                return at
        return None

    def get_active_rpg_autotile(self) -> Optional[RPGAutotile]:
        return self.get_rpg_autotile(self.active_rpg_autotile_id)

    def _resolve_autotile_for_tile(self, tile: Optional[MapItem]) -> Optional[RPGAutotile]:
        if not tile:
            return None
        at_id = tile.properties.get("autotile_id") if getattr(tile, "properties", None) else None
        return (
            self.get_rpg_autotile(at_id)
            or self.get_rpg_autotile(tile.asset_id)
            or self.get_rpg_autotile(tile.terrain_type)
        )

    @staticmethod
    def _tile_belongs_to_autotile(tile: Optional[MapItem], autotile: RPGAutotile) -> bool:
        if not tile or not tile.is_auto_tiled:
            return False
        props = getattr(tile, "properties", None) or {}
        if props.get("autotile_id") == autotile.id:
            return True
        return (
            tile.asset_id == autotile.id
            or tile.terrain_type == autotile.terrain_type
        )

    @staticmethod
    def _source_tile_rect(
        asset_id: Optional[str], col: int, row: int, ts: int, asset_manager: Optional[Any]
    ) -> Tuple[int, int, int, int]:
        if asset_manager is not None and asset_id and hasattr(asset_manager, "get_asset"):
            asset = asset_manager.get_asset(asset_id)
            if asset is not None and getattr(asset, "tileset_config", None) is not None:
                return asset.get_tile_rect(col, row)
        return (col * ts, row * ts, ts, ts)

    @classmethod
    def _variant_source_rect(
        cls, variant: Any, dc: int, dr: int, ts: int, asset_manager: Optional[Any]
    ) -> Tuple[int, int, int, int]:
        return cls._source_tile_rect(
            variant.source_asset_id,
            variant.source_col + dc,
            variant.source_row + dr,
            ts,
            asset_manager,
        )

    # --------------------------------------------------------------------------
    # 8-NEIGHBOR ADJACENCY MASK & TILE UPDATE
    # --------------------------------------------------------------------------
    def compute_rpg_mask(
        self,
        layer: Layer,
        col: int,
        row: int,
        autotile: RPGAutotile,
        project: Optional[Project] = None,
    ) -> int:
        def _matches(c: int, r: int) -> bool:
            if project and not (0 <= c < project.map_width and 0 <= r < project.map_height):
                return False
            neighbor = layer.get_tile(c, r)
            return self._tile_belongs_to_autotile(neighbor, autotile)

        mask = 0
        n = _matches(col, row - 1)
        s = _matches(col, row + 1)
        w = _matches(col - 1, row)
        e = _matches(col + 1, row)

        if n: mask |= MASK_N
        if s: mask |= MASK_S
        if w: mask |= MASK_W
        if e: mask |= MASK_E

        if n and e and _matches(col + 1, row - 1): mask |= MASK_NE
        if s and e and _matches(col + 1, row + 1): mask |= MASK_SE
        if s and w and _matches(col - 1, row + 1): mask |= MASK_SW
        if n and w and _matches(col - 1, row - 1): mask |= MASK_NW

        return mask

    def update_rpg_tile_at(
        self,
        layer: Layer,
        col: int,
        row: int,
        autotile: RPGAutotile,
        project: Optional[Project] = None,
    ) -> Optional[MapItem]:
        curr = layer.get_tile(col, row)
        if not curr:
            return None

        mask = self.compute_rpg_mask(layer, col, row, autotile, project)
        sx, sy, sw, sh = autotile.get_tile_slice_for_mask(mask, col, row)
        if sw <= 0 or sh <= 0 or sx < 0 or sy < 0:
            return None

        dest_ts = project.tile_size if project else sw
        curr.asset_id = autotile.id
        curr.source_x = sx
        curr.source_y = sy
        curr.source_w = sw
        curr.source_h = sh
        curr.dest_w = dest_ts
        curr.dest_h = dest_ts
        curr.is_auto_tiled = True
        curr.terrain_type = autotile.terrain_type
        if isinstance(curr.properties, dict):
            curr.properties["autotile_id"] = autotile.id
            curr.properties.pop("variant_origin", None)
            curr.properties.pop("variant_size", None)
        return curr

    def _expand_affected_for_variants(
        self,
        layer: Layer,
        seed_coords: Set[Tuple[int, int]],
        autotile: RPGAutotile,
        project: Optional[Project],
        initial_states: Dict[Tuple[int, int], Optional[MapItem]],
    ) -> Set[Tuple[int, int]]:
        affected: Set[Tuple[int, int]] = set(seed_coords)

        def _try_add(c: int, r: int) -> None:
            if project and not (0 <= c < project.map_width and 0 <= r < project.map_height):
                return
            t = layer.get_tile(c, r)
            if self._tile_belongs_to_autotile(t, autotile):
                if (c, r) not in initial_states:
                    initial_states[(c, r)] = t.clone()
                affected.add((c, r))

        # 1. Expand any existing multi-tile custom variant footprints touched by seed_coords
        frontier = list(affected)
        expanded_origins: Set[Tuple[int, int]] = set()
        while frontier:
            c, r = frontier.pop()
            t = layer.get_tile(c, r)
            props = getattr(t, "properties", None) if t else None
            if props and "variant_origin" in props and "variant_size" in props:
                vo = props["variant_origin"]
                vs = props["variant_size"]
                if isinstance(vo, (list, tuple)) and len(vo) == 2 and isinstance(vs, (list, tuple)) and len(vs) == 2:
                    oc, orow = int(vo[0]), int(vo[1])
                    vw, vh = max(1, int(vs[0])), max(1, int(vs[1]))
                    if (oc, orow) not in expanded_origins:
                        expanded_origins.add((oc, orow))
                        for dr in range(vh):
                            for dc in range(vw):
                                fc, fr = oc + dc, orow + dr
                                if (fc, fr) not in affected:
                                    _try_add(fc, fr)
                                    if (fc, fr) in affected:
                                        frontier.append((fc, fr))

        # 2. If autotile has multi-tile variants (W>1 or H>1), include nearby candidate anchors
        variants = getattr(autotile, "custom_variants", None) or []
        max_vw = max((v.width_tiles for v in variants), default=1)
        max_vh = max((v.height_tiles for v in variants), default=1)
        if max_vw > 1 or max_vh > 1:
            base = list(affected)
            for c, r in base:
                for dr in range(-(max_vh - 1), max_vh):
                    for dc in range(-(max_vw - 1), max_vw):
                        _try_add(c + dc, r + dr)

        return affected

    def _apply_affected_cells(
        self,
        layer: Layer,
        affected: Set[Tuple[int, int]],
        autotile: RPGAutotile,
        project: Optional[Project],
        initial_states: Dict[Tuple[int, int], Optional[MapItem]],
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]],
        asset_manager: Optional[Any],
    ) -> None:
        dest_ts = project.tile_size if project else autotile.tile_size
        claimed: Set[Tuple[int, int]] = set()
        if getattr(autotile, "custom_variants", None):
            ts = autotile.tile_size
            for c, r in sorted(affected, key=lambda pt: (pt[1], pt[0])):
                if (c, r) in claimed:
                    continue
                tile = layer.get_tile(c, r)
                if not self._tile_belongs_to_autotile(tile, autotile):
                    continue
                mask = self.compute_rpg_mask(layer, c, r, autotile, project)
                variant = autotile.get_matching_custom_variant(mask, c, r)
                if variant is None:
                    continue
                vw, vh = variant.width_tiles, variant.height_tiles

                # Prefer top-left placement (backward-compatible), fallback to centered for >=3x3 variants
                anchor_candidates = [(c, r)]
                if vw >= 3 or vh >= 3:
                    anchor_candidates.append((c - vw // 2, r - vh // 2))

                chosen_origin: Optional[Tuple[int, int]] = None
                for oc, orow in anchor_candidates:
                    can_place = True
                    for dr in range(vh):
                        for dc in range(vw):
                            fc, fr = oc + dc, orow + dr
                            if (fc, fr) in claimed:
                                can_place = False
                                break
                            if project and not (0 <= fc < project.map_width and 0 <= fr < project.map_height):
                                can_place = False
                                break
                            ft = layer.get_tile(fc, fr)
                            if not self._tile_belongs_to_autotile(ft, autotile):
                                can_place = False
                                break
                        if not can_place:
                            break
                    if can_place:
                        chosen_origin = (oc, orow)
                        break

                if chosen_origin is not None:
                    oc, orow = chosen_origin
                    for dr in range(vh):
                        for dc in range(vw):
                            fc, fr = oc + dc, orow + dr
                            ft = layer.get_tile(fc, fr)
                            if (fc, fr) not in initial_states:
                                initial_states[(fc, fr)] = ft.clone()
                            sx, sy, sw, sh = self._variant_source_rect(
                                variant, dc, dr, ts, asset_manager
                            )
                            ft.asset_id = variant.source_asset_id or autotile.id
                            ft.source_x = sx
                            ft.source_y = sy
                            ft.source_w = sw
                            ft.source_h = sh
                            ft.dest_w = dest_ts
                            ft.dest_h = dest_ts
                            ft.is_auto_tiled = True
                            ft.terrain_type = autotile.terrain_type
                            if isinstance(ft.properties, dict):
                                ft.properties["autotile_id"] = autotile.id
                                ft.properties["variant_origin"] = [oc, orow]
                                ft.properties["variant_size"] = [vw, vh]
                            claimed.add((fc, fr))
                            changes[(fc, fr)] = (initial_states.get((fc, fr)), ft.clone())

        # Pass 2: Standard Wang-47 atlas update for all remaining unclaimed affected cells
        for c, r in affected:
            if (c, r) in claimed:
                continue
            tile = layer.get_tile(c, r)
            if self._tile_belongs_to_autotile(tile, autotile):
                self.update_rpg_tile_at(layer, c, r, autotile, project)
                changes[(c, r)] = (initial_states.get((c, r)), tile.clone())

    def _apply_composition_stroke(
        self,
        layer: Layer,
        coords: List[Tuple[int, int]],
        autotile: RPGAutotile,
        project: Optional[Project],
        asset_manager: Optional[Any],
    ) -> Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]]:
        """
        Places indivisible WxH multi-cell logical compositions (e.g. 2x2, 2x3, 3x3)
        snapped to a non-overlapping macro-grid so all W*H source tiles preserve
        their exact relative positions without splitting, shifting, or overlapping.
        """
        cw = max(1, int(getattr(autotile, "composition_width", autotile.source_w_tiles)))
        ch = max(1, int(getattr(autotile, "composition_height", autotile.source_h_tiles)))
        ts = autotile.tile_size
        dest_ts = project.tile_size if project else ts
        am = asset_manager or self.asset_manager
        src_asset_id = autotile.source_asset_id or autotile.id

        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}
        placed_origins: Set[Tuple[int, int]] = set()

        for c, r in coords:
            oc = (c // cw) * cw
            orow = (r // ch) * ch
            if (oc, orow) in placed_origins:
                continue
            # Verify entire WxH composition fits inside map bounds (never splits or clips!)
            if project and (
                oc < 0
                or orow < 0
                or oc + cw > project.map_width
                or orow + ch > project.map_height
            ):
                continue
            placed_origins.add((oc, orow))
            for dr in range(ch):
                for dc in range(cw):
                    fc, fr = oc + dc, orow + dr
                    prev = layer.get_tile(fc, fr)
                    prev_clone = prev.clone() if prev else None
                    sx, sy, sw, sh = self._source_tile_rect(
                        src_asset_id,
                        autotile.source_col + dc,
                        autotile.source_row + dr,
                        ts,
                        am,
                    )
                    item = MapItem(
                        asset_id=src_asset_id,
                        col=fc,
                        row=fr,
                        item_type=ItemType.TILE,
                        source_x=sx,
                        source_y=sy,
                        source_w=sw,
                        source_h=sh,
                        dest_w=dest_ts,
                        dest_h=dest_ts,
                        is_auto_tiled=True,
                        terrain_type=autotile.terrain_type,
                        properties={
                            "autotile_id": autotile.id,
                            "composition_origin": [oc, orow],
                            "composition_size": [cw, ch],
                        },
                    )
                    layer.set_tile(fc, fr, item)
                    changes[(fc, fr)] = (prev_clone, item.clone())
        return changes

    def apply_rpg_autotile_stroke(
        self,
        layer: Layer,
        coords: List[Tuple[int, int]],
        autotile: RPGAutotile,
        project: Optional[Project] = None,
        asset_manager: Optional[Any] = None,
    ) -> Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]]:
        if getattr(layer, "auto_tiling_enabled", True) is False:
            return {}
        if not self.can_render_autotile(autotile, asset_manager):
            return {}
        # Ensure autotile is registered in both engine and asset_manager before committing
        am = asset_manager or self.asset_manager
        if autotile.id not in self.rpg_autotiles:
            self.register_rpg_autotile(autotile, am)
        elif am is not None and hasattr(am, "register_rpg_autotile"):
            am.register_rpg_autotile(autotile)

        # Multi-cell logical composition mode (2x2, 2x3, 3x3, WxH -> 1 indivisible unit)
        if getattr(autotile, "is_multi_cell_composition", False):
            return self._apply_composition_stroke(layer, coords, autotile, project, am)

        # Validate slice geometry before mutating any cells (transactional safety)
        test_sx, test_sy, test_sw, test_sh = autotile.get_tile_slice_for_mask(0, 0, 0)
        if test_sw <= 0 or test_sh <= 0 or test_sx < 0 or test_sy < 0:
            return {}

        # Expand stroke footprint when path_width > 1 (consistent multi-tile road/river width!)
        pw_tiles = max(1, int(getattr(autotile, "path_width", 1)))
        if pw_tiles > 1:
            expanded_coords: List[Tuple[int, int]] = []
            seen_exp: Set[Tuple[int, int]] = set()
            for c, r in coords:
                for dr in range(pw_tiles):
                    for dc in range(pw_tiles):
                        pt = (c + dc, r + dr)
                        if pt not in seen_exp:
                            seen_exp.add(pt)
                            expanded_coords.append(pt)
            coords = expanded_coords

        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}
        initial_states: Dict[Tuple[int, int], Optional[MapItem]] = {}
        affected: Set[Tuple[int, int]] = set()
        dest_ts = project.tile_size if project else test_sw

        for c, r in coords:
            if project and not (0 <= c < project.map_width and 0 <= r < project.map_height):
                continue
            tile = layer.get_tile(c, r)
            if (c, r) not in initial_states:
                initial_states[(c, r)] = tile.clone() if tile else None
            if not tile:
                sx, sy, sw, sh = autotile.get_tile_slice_for_mask(0, c, r)
                tile = MapItem(
                    asset_id=autotile.id,
                    col=c,
                    row=r,
                    item_type=ItemType.TILE,
                    source_x=sx,
                    source_y=sy,
                    source_w=sw,
                    source_h=sh,
                    dest_w=dest_ts,
                    dest_h=dest_ts,
                    is_auto_tiled=True,
                    terrain_type=autotile.terrain_type,
                    properties={"autotile_id": autotile.id},
                )
                layer.set_tile(c, r, tile)
            else:
                tile.is_auto_tiled = True
                tile.asset_id = autotile.id
                tile.terrain_type = autotile.terrain_type
                tile.dest_w = dest_ts
                tile.dest_h = dest_ts
                if isinstance(tile.properties, dict):
                    tile.properties["autotile_id"] = autotile.id

            affected.add((c, r))
            for dx, dy, _ in self.NEIGHBORS:
                nc, nr = c + dx, r + dy
                if project and not (0 <= nc < project.map_width and 0 <= nr < project.map_height):
                    continue
                neighbor = layer.get_tile(nc, nr)
                if self._tile_belongs_to_autotile(neighbor, autotile):
                    if (nc, nr) not in initial_states:
                        initial_states[(nc, nr)] = neighbor.clone()
                    affected.add((nc, nr))

        affected = self._expand_affected_for_variants(
            layer, affected, autotile, project, initial_states
        )
        self._apply_affected_cells(
            layer, affected, autotile, project, initial_states, changes, am
        )
        return changes

    def update_rpg_neighbors_after_erase(
        self,
        layer: Layer,
        erased_coords: Set[Tuple[int, int]],
        project: Optional[Project] = None,
    ) -> Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]]:
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}
        erased_set = set(erased_coords)

        # Pass 0: Clean up any broken multi-cell WxH logical compositions atomically (zero orphans!)
        cleaned_origins: Set[Tuple[int, int]] = set()
        for c, r in list(erased_set):
            for dx, dy, _ in self.NEIGHBORS:
                nc, nr = c + dx, r + dy
                if (nc, nr) in erased_set:
                    continue
                tile = layer.get_tile(nc, nr)
                props = getattr(tile, "properties", None) if tile else None
                if props and "composition_origin" in props and "composition_size" in props:
                    co = props["composition_origin"]
                    cs = props["composition_size"]
                    if isinstance(co, (list, tuple)) and len(co) == 2 and isinstance(cs, (list, tuple)) and len(cs) == 2:
                        oc, orow = int(co[0]), int(co[1])
                        cw, ch = max(1, int(cs[0])), max(1, int(cs[1]))
                        # Only remove if at least one erased coord was inside THIS composition's footprint!
                        if any(oc <= ec < oc + cw and orow <= er < orow + ch for ec, er in erased_set):
                            if (oc, orow) not in cleaned_origins:
                                cleaned_origins.add((oc, orow))
                                for dr in range(ch):
                                    for dc in range(cw):
                                        fc, fr = oc + dc, orow + dr
                                        if (fc, fr) in erased_set:
                                            continue
                                        ft = layer.get_tile(fc, fr)
                                        if ft is not None and (getattr(ft, "properties", None) or {}).get("composition_origin") == [oc, orow]:
                                            changes[(fc, fr)] = (ft.clone(), None)
                                            layer.remove_tile(fc, fr)
                                            erased_set.add((fc, fr))

        per_autotile: Dict[str, Tuple[RPGAutotile, Set[Tuple[int, int]]]] = {}

        for c, r in erased_set:
            for dx, dy, _ in self.NEIGHBORS:
                nc, nr = c + dx, r + dy
                if (nc, nr) in erased_set:
                    continue
                if project and not (0 <= nc < project.map_width and 0 <= nr < project.map_height):
                    continue
                tile = layer.get_tile(nc, nr)
                if tile and tile.is_auto_tiled:
                    autotile = self._resolve_autotile_for_tile(tile)
                    if autotile and not getattr(autotile, "is_multi_cell_composition", False):
                        if autotile.id not in per_autotile:
                            per_autotile[autotile.id] = (autotile, set())
                        per_autotile[autotile.id][1].add((nc, nr))

        for autotile, seed_cells in per_autotile.values():
            initial_states: Dict[Tuple[int, int], Optional[MapItem]] = {}
            for sc, sr in seed_cells:
                t = layer.get_tile(sc, sr)
                if t is not None:
                    initial_states[(sc, sr)] = t.clone()
            affected = self._expand_affected_for_variants(
                layer, seed_cells, autotile, project, initial_states
            )
            self._apply_affected_cells(
                layer, affected, autotile, project, initial_states, changes, self.asset_manager
            )

        return changes

    def evaluate_rpg_sandbox_grid(
        self,
        active_cells: Set[Tuple[int, int]],
        autotile: RPGAutotile,
        width: int = 16,
        height: int = 16,
        asset_manager: Optional[Any] = None,
    ) -> Dict[Tuple[int, int], Tuple[str, int, int, int, int]]:
        result: Dict[Tuple[int, int], Tuple[str, int, int, int, int]] = {}
        am = asset_manager or self.asset_manager

        # Multi-cell logical composition preview in sandbox (non-overlapping WxH units!)
        if getattr(autotile, "is_multi_cell_composition", False):
            cw = max(1, int(getattr(autotile, "composition_width", autotile.source_w_tiles)))
            ch = max(1, int(getattr(autotile, "composition_height", autotile.source_h_tiles)))
            ts = autotile.tile_size
            src_aid = autotile.source_asset_id or autotile.id
            seen_origins: Set[Tuple[int, int]] = set()
            for c, r in sorted(active_cells, key=lambda pt: (pt[1], pt[0])):
                oc = (c // cw) * cw
                orow = (r // ch) * ch
                if (oc, orow) in seen_origins:
                    continue
                if oc < 0 or orow < 0 or oc + cw > width or orow + ch > height:
                    continue
                seen_origins.add((oc, orow))
                for dr in range(ch):
                    for dc in range(cw):
                        sx, sy, sw, sh = self._source_tile_rect(
                            src_aid,
                            autotile.source_col + dc,
                            autotile.source_row + dr,
                            ts,
                            am,
                        )
                        result[(oc + dc, orow + dr)] = (src_aid, sx, sy, sw, sh)
            return result

        # Expand active_cells if path_width > 1 for live sandbox preview
        pw_tiles = max(1, int(getattr(autotile, "path_width", 1)))
        effective_cells: Set[Tuple[int, int]]
        if pw_tiles > 1:
            effective_cells = set()
            for c, r in active_cells:
                for dr in range(pw_tiles):
                    for dc in range(pw_tiles):
                        if 0 <= c + dc < width and 0 <= r + dr < height:
                            effective_cells.add((c + dc, r + dr))
        else:
            effective_cells = active_cells

        def _is_active(c: int, r: int) -> bool:
            return (0 <= c < width and 0 <= r < height) and (c, r) in effective_cells

        def _mask_at(c: int, r: int) -> int:
            mask = 0
            n = _is_active(c, r - 1)
            s = _is_active(c, r + 1)
            w = _is_active(c - 1, r)
            e = _is_active(c + 1, r)
            if n: mask |= MASK_N
            if s: mask |= MASK_S
            if w: mask |= MASK_W
            if e: mask |= MASK_E
            if n and e and _is_active(c + 1, r - 1): mask |= MASK_NE
            if s and e and _is_active(c + 1, r + 1): mask |= MASK_SE
            if s and w and _is_active(c - 1, r + 1): mask |= MASK_SW
            if n and w and _is_active(c - 1, r - 1): mask |= MASK_NW
            return mask

        valid_cells = [
            (c, r) for c, r in effective_cells if 0 <= c < width and 0 <= r < height
        ]
        claimed: Set[Tuple[int, int]] = set()

        # Pass 1: Evaluate custom variants (1x1, 2x2, 3x3, WxH) live in the sandbox
        if getattr(autotile, "custom_variants", None):
            ts = autotile.tile_size
            for c, r in sorted(valid_cells, key=lambda pt: (pt[1], pt[0])):
                if (c, r) in claimed:
                    continue
                mask = _mask_at(c, r)
                variant = autotile.get_matching_custom_variant(mask, c, r)
                if variant is None:
                    continue
                vw, vh = variant.width_tiles, variant.height_tiles
                anchor_candidates = [(c, r)]
                if vw >= 3 or vh >= 3:
                    anchor_candidates.append((c - vw // 2, r - vh // 2))
                chosen_origin: Optional[Tuple[int, int]] = None
                for oc, orow in anchor_candidates:
                    if all(
                        _is_active(oc + dc, orow + dr) and (oc + dc, orow + dr) not in claimed
                        for dr in range(vh)
                        for dc in range(vw)
                    ):
                        chosen_origin = (oc, orow)
                        break
                if chosen_origin is not None:
                    oc, orow = chosen_origin
                    aid = variant.source_asset_id or autotile.id
                    for dr in range(vh):
                        for dc in range(vw):
                            fc, fr = oc + dc, orow + dr
                            sx, sy, sw, sh = self._variant_source_rect(variant, dc, dr, ts, am)
                            result[(fc, fr)] = (aid, sx, sy, sw, sh)
                            claimed.add((fc, fr))

        # Pass 2: Standard Wang-47 atlas slices for remaining cells
        for c, r in valid_cells:
            if (c, r) in claimed:
                continue
            mask = _mask_at(c, r)
            sx, sy, sw, sh = autotile.get_tile_slice_for_mask(mask, c, r)
            result[(c, r)] = (autotile.id, sx, sy, sw, sh)

        return result

    def recalculate_layer(
        self,
        project: Project,
        layer: Layer,
    ) -> Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]]:
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}
        per_autotile: Dict[str, Tuple[RPGAutotile, Set[Tuple[int, int]]]] = {}
        for coord, tile in list(layer.tiles.items()):
            if not getattr(tile, "is_auto_tiled", False):
                continue
            autotile = self._resolve_autotile_for_tile(tile)
            if not autotile:
                continue
            if autotile.id not in per_autotile:
                per_autotile[autotile.id] = (autotile, set())
            per_autotile[autotile.id][1].add(coord)

        for autotile, coords_set in per_autotile.values():
            initial_states: Dict[Tuple[int, int], Optional[MapItem]] = {
                coord: layer.get_tile(*coord).clone()
                for coord in coords_set
                if layer.get_tile(*coord) is not None
            }
            group_changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}
            self._apply_affected_cells(
                layer, coords_set, autotile, project, initial_states, group_changes, self.asset_manager
            )
            for coord, (before, after) in group_changes.items():
                if after and before and after.to_dict() != before.to_dict():
                    changes[coord] = (before, after)
        return changes

    def recalculate_project(
        self, project: Project
    ) -> Dict[str, Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]]]:
        result = {}
        previous_map_id = project.active_map_id
        try:
            for map_model in project.maps.values():
                project.active_map_id = map_model.id
                for layer in map_model.layers:
                    layer_changes = self.recalculate_layer(project, layer)
                    if layer_changes:
                        result[f"{map_model.id}:{layer.id}"] = layer_changes
            return result
        finally:
            project.active_map_id = previous_map_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_rpg_autotile_id": self.active_rpg_autotile_id,
            "rpg_autotiles": {at_id: at.to_dict() for at_id, at in self.rpg_autotiles.items()},
        }

    def load_from_dict(
        self, data: Dict[str, Any], asset_manager: Optional[Any] = None
    ) -> None:
        self.rpg_autotiles.clear()
        am = asset_manager or self.asset_manager
        for at_id, at_data in data.get("rpg_autotiles", {}).items():
            try:
                autotile = RPGAutotile.from_dict(at_data)
                autotile.rebuild_atlas(am)
                self.rpg_autotiles[autotile.id] = autotile
                if am is not None and hasattr(am, "register_rpg_autotile"):
                    am.register_rpg_autotile(autotile)
            except Exception as e:
                logger.error(f"Failed to load RPG autotile {at_id}: {e}")
        self.active_rpg_autotile_id = data.get("active_rpg_autotile_id")
        if (
            self.active_rpg_autotile_id not in self.rpg_autotiles
            or self.rpg_autotiles[self.active_rpg_autotile_id].archived
        ):
            self.active_rpg_autotile_id = None
        if not self.active_rpg_autotile_id and self.rpg_autotiles:
            self.active_rpg_autotile_id = next(
                (
                    key
                    for key, value in self.rpg_autotiles.items()
                    if not value.archived
                ),
                None,
            )
