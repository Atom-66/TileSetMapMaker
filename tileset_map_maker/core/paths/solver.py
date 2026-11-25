from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ...models.autotile import (
    MASK_E,
    MASK_N,
    MASK_NE,
    MASK_NW,
    MASK_S,
    MASK_SE,
    MASK_SW,
    MASK_W,
    canonicalize_blob_mask,
    deterministic_cell_hash,
)
from .connection_rules import ConnectionRuleEngine
from .models import OPPOSITE_EDGE, PathVariant, Placement


class PathSolver:
    """
    Constraint-based local Path Solver.
    Operates strictly on the affected neighborhood (never recalculates entire
    large maps!) and resolves:
      1. Indivisible WxH logical compositions (composition_wxh mode) on a
         non-overlapping grid preserving exact relative tile positions.
      2. Multi-tile (2x2, 2x3, 3x2, 3x3, 4x4, WxH) and 1x1 custom variants
         ranked by priority, connection mask match, AND ConnectionRuleEngine
         compatibility against neighboring placements (preventing random or
         mismatched tile picks!).
      3. Predictable, seamless Wang-47 fallback slices for remaining cells.
    """

    DIR_OFFSETS: Dict[str, Tuple[int, int]] = {
        "N": (0, -1),
        "E": (1, 0),
        "S": (0, 1),
        "W": (-1, 0),
    }

    @staticmethod
    def compute_mask(
        col: int,
        row: int,
        is_path_cell: Callable[[int, int], bool],
    ) -> int:
        mask = 0
        n = is_path_cell(col, row - 1)
        s = is_path_cell(col, row + 1)
        w = is_path_cell(col - 1, row)
        e = is_path_cell(col + 1, row)
        if n:
            mask |= MASK_N
        if s:
            mask |= MASK_S
        if w:
            mask |= MASK_W
        if e:
            mask |= MASK_E
        if n and e and is_path_cell(col + 1, row - 1):
            mask |= MASK_NE
        if s and e and is_path_cell(col + 1, row + 1):
            mask |= MASK_SE
        if s and w and is_path_cell(col - 1, row + 1):
            mask |= MASK_SW
        if n and w and is_path_cell(col - 1, row - 1):
            mask |= MASK_NW
        return mask

    @classmethod
    def solve_region(
        cls,
        target_cells: Set[Tuple[int, int]],
        is_path_cell: Callable[[int, int], bool],
        autotile: Any,
        source_rect_fn: Callable[[Optional[str], int, int, int], Tuple[int, int, int, int]],
        bounds: Optional[Tuple[int, int]] = None,
    ) -> List[Placement]:
        """
        Solves a local set of target cells into non-overlapping Placement objects.
        Guarantees deterministic, reproducible output seeded by autotile.seed + coords.
        """
        placements: List[Placement] = []
        ts = autotile.tile_size

        def _in_bounds(c: int, r: int) -> bool:
            if bounds is None:
                return c >= 0 and r >= 0
            return 0 <= c < bounds[0] and 0 <= r < bounds[1]

        # Mode A: Indivisible multi-cell logical composition (W x H)
        if getattr(autotile, "is_multi_cell_composition", False):
            cw = max(1, int(getattr(autotile, "composition_width", autotile.source_w_tiles)))
            ch = max(1, int(getattr(autotile, "composition_height", autotile.source_h_tiles)))
            src_aid = autotile.source_asset_id or autotile.id
            seen_origins: Set[Tuple[int, int]] = set()
            for c, r in sorted(target_cells, key=lambda pt: (pt[1], pt[0])):
                oc = (c // cw) * cw
                orow = (r // ch) * ch
                if (oc, orow) in seen_origins:
                    continue
                if not (_in_bounds(oc, orow) and _in_bounds(oc + cw - 1, orow + ch - 1)):
                    continue
                seen_origins.add((oc, orow))
                cell_slices: Dict[Tuple[int, int], Tuple[int, int, int, int]] = {}
                for dr in range(ch):
                    for dc in range(cw):
                        cell_slices[(oc + dc, orow + dr)] = source_rect_fn(
                            src_aid, autotile.source_col + dc, autotile.source_row + dr, ts
                        )
                placements.append(
                    Placement(
                        autotile_id=autotile.id,
                        origin_col=oc,
                        origin_row=orow,
                        width_tiles=cw,
                        height_tiles=ch,
                        source_asset_id=src_aid,
                        cell_slices=cell_slices,
                        variant_id=None,
                        is_composition=True,
                        is_fallback=False,
                    )
                )
            return placements

        # Mode B: Constraint-based solving with multi-tile & single-tile custom variants + Wang-47 fallback
        claimed: Set[Tuple[int, int]] = set()
        placed_variants_by_cell: Dict[Tuple[int, int], PathVariant] = {}
        variants: List[PathVariant] = list(getattr(autotile, "custom_variants", None) or [])

        if variants:
            # Sort candidate cells deterministically (top-left -> bottom-right)
            ordered_cells = sorted(
                (pt for pt in target_cells if _in_bounds(pt[0], pt[1]) and is_path_cell(pt[0], pt[1])),
                key=lambda pt: (pt[1], pt[0]),
            )
            for c, r in ordered_cells:
                if (c, r) in claimed:
                    continue
                mask = canonicalize_blob_mask(cls.compute_mask(c, r, is_path_cell))
                # Gather all connectable variants matching mask (or universal mask == -1)
                candidates = [
                    v
                    for v in variants
                    if v.allow_connections and (v.mask == mask or v.mask < 0)
                ]
                if not candidates:
                    continue

                # Score candidates by (priority, compatibility with already-placed neighbors, area)
                scored: List[Tuple[int, float, int, PathVariant, Tuple[int, int]]] = []
                for v in candidates:
                    vw, vh = v.width_tiles, v.height_tiles
                    anchors = [(c, r)]
                    if vw >= 3 or vh >= 3:
                        anchors.append((c - vw // 2, r - vh // 2))

                    chosen_origin: Optional[Tuple[int, int]] = None
                    for oc, orow in anchors:
                        if all(
                            _in_bounds(oc + dc, orow + dr)
                            and (oc + dc, orow + dr) not in claimed
                            and is_path_cell(oc + dc, orow + dr)
                            for dr in range(vh)
                            for dc in range(vw)
                        ):
                            chosen_origin = (oc, orow)
                            break
                    if chosen_origin is None:
                        continue

                    oc, orow = chosen_origin
                    # Verify constraint compatibility against placed neighbors AND (for junctions/crossroads)
                    # look ahead across ALL cardinal arms so 3 good sides + 1 pinched side is never accepted!
                    compat_ok = True
                    compat_scores: List[float] = []
                    cardinal_count = sum(
                        1 for bit in (MASK_N, MASK_E, MASK_S, MASK_W) if (mask & bit)
                    )
                    is_junction = (vw == 1 and vh == 1 and cardinal_count >= 3)

                    if is_junction:
                        arm_variants: Dict[str, PathVariant] = {}
                        for d_name, (dx, dy) in cls.DIR_OFFSETS.items():
                            nc, nr = oc + dx, orow + dy
                            if not (_in_bounds(nc, nr) and is_path_cell(nc, nr)):
                                continue
                            placed_n = placed_variants_by_cell.get((nc, nr))
                            if placed_n is not None:
                                arm_variants[d_name] = placed_n
                            else:
                                # Look ahead for any custom arm variant matching the neighbor's real mask
                                n_mask = canonicalize_blob_mask(cls.compute_mask(nc, nr, is_path_cell))
                                n_cands = [
                                    nv
                                    for nv in variants
                                    if nv.allow_connections and (nv.mask == n_mask or nv.mask < 0)
                                ]
                                if n_cands:
                                    # Pick the best-matching arm candidate for this center candidate
                                    best_nv = max(
                                        n_cands,
                                        key=lambda nv: (
                                            ConnectionRuleEngine.check_edge_compatibility(
                                                v, nv, d_name
                                            ).score,
                                            nv.priority,
                                        ),
                                    )
                                    arm_variants[d_name] = best_nv
                        if arm_variants:
                            inter_res = ConnectionRuleEngine.validate_intersection_composition(
                                v, arm_variants
                            )
                            if not inter_res.compatible:
                                compat_ok = False
                            else:
                                compat_scores.append(inter_res.score)
                    else:
                        for dr in range(vh):
                            for dc in range(vw):
                                fc, fr = oc + dc, orow + dr
                                for d_name, (dx, dy) in cls.DIR_OFFSETS.items():
                                    nc, nr = fc + dx, fr + dy
                                    # Skip internal cells of the same footprint
                                    if oc <= nc < oc + vw and orow <= nr < orow + vh:
                                        continue
                                    n_var = placed_variants_by_cell.get((nc, nr))
                                    if n_var is not None:
                                        res = ConnectionRuleEngine.check_edge_compatibility(
                                            v, n_var, d_name
                                        )
                                        if not res.compatible:
                                            compat_ok = False
                                            break
                                        compat_scores.append(res.score)
                                if not compat_ok:
                                    break
                            if not compat_ok:
                                break
                    if not compat_ok:
                        continue

                    avg_compat = sum(compat_scores) / len(compat_scores) if compat_scores else 1.0
                    scored.append((v.priority, avg_compat, vw * vh, v, chosen_origin))

                if not scored:
                    continue

                # Select highest priority tier, then weighted deterministic choice among compatible winners
                best_prio = max(item[0] for item in scored)
                top_tier = [item for item in scored if item[0] == best_prio]
                best_compat = max(item[1] for item in top_tier)
                finalists = [item for item in top_tier if item[1] >= best_compat - 0.05]

                if len(finalists) == 1:
                    _, _, _, chosen_v, (oc, orow) = finalists[0]
                else:
                    total_w = sum(item[3].weight for item in finalists)
                    h_val = deterministic_cell_hash(getattr(autotile, "seed", 42), c, r, salt=1337)
                    target_w = (h_val % 1000000) / 1000000.0 * total_w
                    accum = 0.0
                    chosen_v, (oc, orow) = finalists[-1][3], finalists[-1][4]
                    for item in finalists:
                        accum += item[3].weight
                        if accum >= target_w:
                            chosen_v, (oc, orow) = item[3], item[4]
                            break

                vw, vh = chosen_v.width_tiles, chosen_v.height_tiles
                aid = chosen_v.source_asset_id or autotile.id
                cell_slices = {}
                for dr in range(vh):
                    for dc in range(vw):
                        fc, fr = oc + dc, orow + dr
                        cell_slices[(fc, fr)] = source_rect_fn(
                            aid, chosen_v.source_col + dc, chosen_v.source_row + dr, ts
                        )
                        claimed.add((fc, fr))
                        placed_variants_by_cell[(fc, fr)] = chosen_v

                placements.append(
                    Placement(
                        autotile_id=autotile.id,
                        origin_col=oc,
                        origin_row=orow,
                        width_tiles=vw,
                        height_tiles=vh,
                        source_asset_id=aid,
                        cell_slices=cell_slices,
                        variant_id=chosen_v.id,
                        is_composition=False,
                        is_fallback=False,
                    )
                )

        # Pass 2: Seamless Wang-47 atlas placements for all remaining unclaimed cells
        for c, r in sorted(target_cells, key=lambda pt: (pt[1], pt[0])):
            if (c, r) in claimed or not _in_bounds(c, r) or not is_path_cell(c, r):
                continue
            mask = cls.compute_mask(c, r, is_path_cell)
            sx, sy, sw, sh = autotile.get_tile_slice_for_mask(mask, c, r)
            if sw <= 0 or sh <= 0 or sx < 0 or sy < 0:
                continue
            placements.append(
                Placement(
                    autotile_id=autotile.id,
                    origin_col=c,
                    origin_row=r,
                    width_tiles=1,
                    height_tiles=1,
                    source_asset_id=autotile.id,
                    cell_slices={(c, r): (sx, sy, sw, sh)},
                    variant_id=None,
                    is_composition=False,
                    is_fallback=True,
                )
            )
            claimed.add((c, r))

        return placements
