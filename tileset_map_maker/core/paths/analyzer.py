from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtGui import QImage

from ...models.autotile import (
    MASK_E,
    MASK_N,
    MASK_S,
    MASK_W,
    canonicalize_blob_mask,
)
from .models import (
    EDGE_DIRECTIONS,
    EdgeSignature,
    PathVariant,
    SheetAnalysis,
)


def _rgb_dist(r1: int, g1: int, b1: int, r2: int, g2: int, b2: int) -> float:
    return (abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)) / 765.0


def _median_rgb(pixels: List[int]) -> Tuple[int, int, int]:
    if not pixels:
        return (0, 0, 0)
    rs = sorted((p >> 16) & 0xFF for p in pixels)
    gs = sorted((p >> 8) & 0xFF for p in pixels)
    bs = sorted(p & 0xFF for p in pixels)
    m = len(rs) // 2
    return (rs[m], gs[m], bs[m])


def _mask_to_role(mask: int, w_tiles: int, h_tiles: int, has_surface: bool) -> str:
    if w_tiles > 1 or h_tiles > 1:
        if mask == (MASK_N | MASK_E | MASK_S | MASK_W):
            return "cross"
        return "composition"
    if not has_surface:
        return "decoration"
    c_mask = mask & (MASK_N | MASK_E | MASK_S | MASK_W)
    role_map = {
        0: "isolated",
        MASK_N | MASK_E | MASK_S | MASK_W: "cross",
        MASK_W | MASK_E: "straight_h",
        MASK_N | MASK_S: "straight_v",
        MASK_E | MASK_S: "corner_tl",
        MASK_W | MASK_S: "corner_tr",
        MASK_N | MASK_E: "corner_bl",
        MASK_N | MASK_W: "corner_br",
        MASK_W | MASK_E | MASK_S: "t_s",
        MASK_W | MASK_E | MASK_N: "t_n",
        MASK_N | MASK_S | MASK_E: "t_e",
        MASK_N | MASK_S | MASK_W: "t_w",
        MASK_S: "end_n",
        MASK_N: "end_s",
        MASK_E: "end_w",
        MASK_W: "end_e",
    }
    return role_map.get(c_mask, "auto")


class TileAnalyzer:
    """
    Cached pixel-level tileset & variant analyzer.
    Inspects color distribution, transparency, contours, edge profiles, texture
    activity, navigable path width, and coherent multi-tile blocks (2x2, 3x3, WxH)
    without scaling or modifying original tileset PNGs.
    """

    def __init__(self, max_cache_entries: int = 128):
        self._sheet_cache: OrderedDict[str, SheetAnalysis] = OrderedDict()
        self._variant_cache: OrderedDict[Tuple[Any, ...], PathVariant] = OrderedDict()
        self._max_cache_entries = max(16, int(max_cache_entries))

    def clear_cache(self) -> None:
        self._sheet_cache.clear()
        self._variant_cache.clear()

    def _put_cache(self, cache: OrderedDict, key: Any, value: Any) -> None:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > self._max_cache_entries:
            cache.popitem(last=False)

    @staticmethod
    def _sheet_fingerprint(sheet: QImage, cache_key: Optional[str] = None) -> str:
        if cache_key:
            return f"{cache_key}:{sheet.width()}x{sheet.height()}"
        # Lightweight deterministic pixel sample fingerprint (zero full-image copy)
        w, h = sheet.width(), sheet.height()
        samples = [
            sheet.pixel(min(w - 1, (w * i) // 7), min(h - 1, (h * j) // 7))
            for i in range(1, 7)
            for j in range(1, 7)
        ] if w > 0 and h > 0 else []
        return f"{w}x{h}:{hash(tuple(samples))}"

    @staticmethod
    def compute_edge_signature(
        region: QImage,
        side: str,
        inner_rgb: Tuple[int, int, int],
        outer_rgb: Optional[Tuple[int, int, int]],
        outer_is_transparent: bool,
        contrast: float,
    ) -> EdgeSignature:
        """
        Computes rich pixel-level EdgeSignature along side 'N', 'E', 'S', or 'W'
        of an arbitrary WxH region QImage.
        """
        w, h = region.width(), region.height()
        if w <= 0 or h <= 0:
            return EdgeSignature()

        # Sample a 2-pixel strip along the requested side
        length = w if side in ("N", "S") else h
        strip_pixels: List[int] = []
        for u in range(length):
            if side == "N":
                p = region.pixel(u, 0)
            elif side == "S":
                p = region.pixel(u, h - 1)
            elif side == "W":
                p = region.pixel(0, u)
            else:
                p = region.pixel(w - 1, u)
            strip_pixels.append(p)

        cr, cg, cb = inner_rgb
        in_luma = 0.299 * cr + 0.587 * cg + 0.114 * cb
        in_sum = float(max(1, cr + cg + cb))
        in_norm = (cr / in_sum, cg / in_sum, cb / in_sum)

        def _hue_diff(r: int, g: int, b: int) -> float:
            s = float(max(1, r + g + b))
            return (abs(r / s - in_norm[0]) + abs(g / s - in_norm[1]) + abs(b / s - in_norm[2])) / 2.0

        # Distinguish genuine two-material borders (e.g. dirt vs grass) from single-material shading
        two_materials = outer_is_transparent
        if not outer_is_transparent and outer_rgb is not None:
            out_hue_diff = _hue_diff(outer_rgb[0], outer_rgb[1], outer_rgb[2])
            two_materials = (out_hue_diff >= 0.10 and contrast >= 0.08) or contrast >= 0.25

        def _is_surface(px: int) -> bool:
            a = (px >> 24) & 0xFF
            if a <= 180:
                return False
            r, g, b = (px >> 16) & 0xFF, (px >> 8) & 0xFF, px & 0xFF
            luma = 0.299 * r + 0.587 * g + 0.114 * b
            if two_materials and luma < in_luma * 0.65:
                return False
            di = _rgb_dist(r, g, b, cr, cg, cb)
            if two_materials and outer_rgb is not None and not outer_is_transparent:
                do = _rgb_dist(r, g, b, outer_rgb[0], outer_rgb[1], outer_rgb[2])
                if do < di * 0.88:
                    return False
            if di > 0.24:
                return False
            if two_materials and _hue_diff(r, g, b) > 0.14:
                return False
            return True

        opaque_px = [p for p in strip_pixels if ((p >> 24) & 0xFF) > 20]
        surface_flags = [_is_surface(p) for p in strip_pixels]
        surface_indices = [i for i, ok in enumerate(surface_flags) if ok]
        surface_count = len(surface_indices)
        surface_ratio = surface_count / float(max(1, length))
        opaque_ratio = len(opaque_px) / float(max(1, length))

        if surface_indices:
            span = (surface_indices[0], surface_indices[-1] + 1)
            width_px = surface_count
        else:
            span = (0, 0)
            width_px = 0

        if opaque_ratio < 0.15:
            edge_type = "closed_transparent"
        elif surface_ratio >= 0.82:
            edge_type = "open_full"
        elif surface_ratio >= 0.28:
            edge_type = "open_path"
        elif surface_ratio <= 0.12:
            edge_type = "closed_outer"
        else:
            edge_type = "mixed"

        mean_rgb = _median_rgb(opaque_px) if opaque_px else (0, 0, 0)
        mr, mg, mb = mean_rgb
        if opaque_px:
            tex_act = sum(
                _rgb_dist((p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF, mr, mg, mb)
                for p in opaque_px
            ) / float(len(opaque_px))
        else:
            tex_act = 0.0

        # 8-bin quantized profile along the edge for pixel-level continuity scoring
        bins = 8
        sample_strip: List[Tuple[int, int, int, int]] = []
        for b_idx in range(bins):
            s0 = (b_idx * length) // bins
            s1 = max(s0 + 1, ((b_idx + 1) * length) // bins)
            seg = strip_pixels[s0:s1]
            r_avg = sum((p >> 16) & 0xFF for p in seg) // len(seg)
            g_avg = sum((p >> 8) & 0xFF for p in seg) // len(seg)
            b_avg = sum(p & 0xFF for p in seg) // len(seg)
            a_avg = sum((p >> 24) & 0xFF for p in seg) // len(seg)
            sample_strip.append((r_avg, g_avg, b_avg, a_avg))

        return EdgeSignature(
            has_surface=surface_ratio >= 0.25,
            surface_span=span,
            surface_width_px=width_px,
            surface_ratio=surface_ratio,
            edge_type=edge_type,
            mean_rgb=mean_rgb,
            texture_activity=tex_act,
            sample_strip=tuple(sample_strip),
        )

    def analyze_variant(
        self,
        sheet: QImage,
        asset_id: str,
        col: int,
        row: int,
        w_tiles: int = 1,
        h_tiles: int = 1,
        tile_size: int = 32,
        tileset_config: Optional[Any] = None,
        cache_key: Optional[str] = None,
        reference_inner_rgb: Optional[Tuple[int, int, int]] = None,
        reference_outer_rgb: Optional[Tuple[int, int, int]] = None,
        reference_outer_transparent: Optional[bool] = None,
    ) -> PathVariant:
        """
        Analyzes any rectangular WxH region of a tileset sheet and returns a
        PathVariant populated with edge signatures, surface width, role,
        connection mask, and exact pixel source_rect.
        """
        from ..rpg_autotile import extract_packed_tileset_image

        packed, tw, th = extract_packed_tileset_image(sheet, tileset_config)
        ts = max(8, int(tw if tileset_config is not None else tile_size))
        w_t = max(1, int(w_tiles))
        h_t = max(1, int(h_tiles))

        fp = self._sheet_fingerprint(packed, cache_key=cache_key or asset_id)
        v_key = (
            fp, col, row, w_t, h_t, ts,
            reference_inner_rgb, reference_outer_rgb, reference_outer_transparent,
        )
        cached = self._variant_cache.get(v_key)
        if cached is not None:
            self._variant_cache.move_to_end(v_key)
            return cached.clone(preserve_id=False)

        px_x, px_y, px_w, px_h = col * ts, row * ts, w_t * ts, h_t * ts
        if tileset_config is not None:
            rx0, ry0, rtw, rth = tileset_config.get_tile_rect(col, row)
            rx1, ry1, rtw2, rth2 = tileset_config.get_tile_rect(col + w_t - 1, row + h_t - 1)
            src_rect = (rx0, ry0, (rx1 + rtw2) - rx0, (ry1 + rth2) - ry0)
        else:
            src_rect = (px_x, px_y, px_w, px_h)

        if px_x < 0 or px_y < 0 or px_x + px_w > packed.width() or px_y + px_h > packed.height():
            return PathVariant(
                mask=0,
                source_asset_id=asset_id,
                source_col=col,
                source_row=row,
                width_tiles=w_t,
                height_tiles=h_t,
                source_rect=src_rect,
                role="auto",
            )

        region = packed.copy(px_x, px_y, px_w, px_h)

        # Estimate inner surface RGB from central band of the region (unless caller provided reference)
        if reference_inner_rgb is not None:
            inner_rgb = reference_inner_rgb
        else:
            cx0, cx1 = px_w // 4, max(px_w // 4 + 1, (3 * px_w) // 4)
            cy0, cy1 = px_h // 4, max(px_h // 4 + 1, (3 * px_h) // 4)
            center_px = [
                region.pixel(x, y)
                for y in range(cy0, cy1, max(1, (cy1 - cy0) // 8))
                for x in range(cx0, cx1, max(1, (cx1 - cx0) // 8))
                if ((region.pixel(x, y) >> 24) & 0xFF) > 180
            ]
            inner_rgb = _median_rgb(center_px)

        # Estimate outer material from 4 outer corners of the region (unless provided)
        if reference_outer_transparent is not None:
            outer_trans = reference_outer_transparent
            outer_rgb = reference_outer_rgb
        else:
            corner_px = [
                region.pixel(x, y)
                for x, y in (
                    (0, 0), (1, 0), (0, 1),
                    (px_w - 1, 0), (px_w - 2, 0),
                    (0, px_h - 1), (px_w - 1, px_h - 1),
                )
            ]
            opaque_corners = [p for p in corner_px if ((p >> 24) & 0xFF) > 20]
            outer_trans = len(opaque_corners) < len(corner_px) * 0.5
            outer_rgb = None if outer_trans else _median_rgb(opaque_corners)

        contrast = (
            1.0
            if outer_trans or outer_rgb is None
            else _rgb_dist(inner_rgb[0], inner_rgb[1], inner_rgb[2], outer_rgb[0], outer_rgb[1], outer_rgb[2])
        )

        edges: Dict[str, EdgeSignature] = {}
        for side in EDGE_DIRECTIONS:
            edges[side] = self.compute_edge_signature(
                region, side, inner_rgb, outer_rgb, outer_trans, contrast
            )

        mask = 0
        if edges["N"].has_surface:
            mask |= MASK_N
        if edges["E"].has_surface:
            mask |= MASK_E
        if edges["S"].has_surface:
            mask |= MASK_S
        if edges["W"].has_surface:
            mask |= MASK_W

        open_widths = [e.surface_width_px for e in edges.values() if e.has_surface]
        surf_width_px = int(sum(open_widths) / len(open_widths)) if open_widths else 0
        role = _mask_to_role(mask, w_t, h_t, bool(open_widths))
        if all(e.edge_type == "open_full" for e in edges.values()):
            role = "center"
            mask = 255

        edge_type = "transparent" if outer_trans else ("organic" if contrast >= 0.10 else "sharp")
        variant = PathVariant(
            mask=canonicalize_blob_mask(mask),
            source_asset_id=asset_id,
            source_col=col,
            source_row=row,
            width_tiles=w_t,
            height_tiles=h_t,
            source_rect=src_rect,
            role=role,
            surface_width_px=surf_width_px,
            surface_width_tiles=max(1, min(w_t, h_t)),
            edge_type=edge_type,
            edges=edges,
            allow_connections=(role != "decoration"),
            name=f"{role} [{w_t}×{h_t} @ {col},{row}]",
        )
        self._put_cache(self._variant_cache, v_key, variant)
        return variant.clone(preserve_id=False)

    def analyze_sheet(
        self,
        sheet: QImage,
        asset_id: str,
        tile_size: int = 32,
        tileset_config: Optional[Any] = None,
        cache_key: Optional[str] = None,
    ) -> SheetAnalysis:
        """
        Scans an entire tileset sheet (cached) to propose coherent 3x3 blocks,
        2x2 compositions, and individual variants with roles and edge profiles.
        """
        from ..rpg_autotile import (
            _analyze_patch_materials,
            _border_continuity,
            _find_companion_inner_corners,
            _is_closed_2x2_patch,
            _tile_alpha_ratio,
            extract_packed_tileset_image,
        )

        packed, tw, th = extract_packed_tileset_image(sheet, tileset_config)
        ts = max(8, int(tw if tileset_config is not None else tile_size))
        fp = self._sheet_fingerprint(packed, cache_key=cache_key or asset_id)
        if fp in self._sheet_cache:
            self._sheet_cache.move_to_end(fp)
            return self._sheet_cache[fp]

        cols = packed.width() // ts
        rows = packed.height() // ts
        detected_3x3: List[Tuple[int, int, bool]] = []
        detected_2x2: List[Tuple[int, int, bool]] = []
        proposed: List[PathVariant] = []
        claimed: set = set()

        # 1. Detect 3x3 blocks (solid or LPC transparent-center rings) + companion 2x2 inner corners
        for r in range(rows - 2):
            for c in range(cols - 2):
                if any((c + dc, r + dr) in claimed for dr in range(3) for dc in range(3)):
                    continue
                ring_tiles = [
                    packed.copy((c + dc) * ts, (r + dr) * ts, ts, ts)
                    for dr in range(3)
                    for dc in range(3)
                    if not (dc == 1 and dr == 1)
                ]
                if not all(_tile_alpha_ratio(t) > 0.30 for t in ring_tiles):
                    continue
                center = packed.copy((c + 1) * ts, (r + 1) * ts, ts, ts)
                c_alpha = _tile_alpha_ratio(center)
                top = packed.copy((c + 1) * ts, r * ts, ts, ts)
                bot = packed.copy((c + 1) * ts, (r + 2) * ts, ts, ts)
                left = packed.copy(c * ts, (r + 1) * ts, ts, ts)
                right = packed.copy((c + 2) * ts, (r + 1) * ts, ts, ts)
                cont = (
                    _border_continuity(top, center, "bottom")
                    + _border_continuity(center, bot, "bottom")
                    + _border_continuity(left, center, "right")
                    + _border_continuity(center, right, "right")
                ) / 4.0
                if c_alpha < 0.25 or cont >= 0.65:
                    patch = packed.copy(c * ts, r * ts, 3 * ts, 3 * ts)
                    mat = _analyze_patch_materials(patch, ts)
                    comp = _find_companion_inner_corners(packed, c, r, ts, mat)
                    detected_3x3.append((c, r, comp is not None))
                    v3 = self.analyze_variant(
                        sheet, asset_id, c, r, 3, 3, ts, tileset_config, cache_key=fp
                    )
                    v3.role = "composition"
                    v3.name = f"Blok 3×3 @ ({c},{r})" + (" + narożniki 2×2" if comp is not None else "")
                    proposed.append(v3)
                    for dr in range(3):
                        for dc in range(3):
                            claimed.add((c + dc, r + dr))

        # 2. Detect remaining 2x2 coherent compositions (e.g. closed islands / 2x2 inner corners / plazas)
        for r in range(rows - 1):
            for c in range(cols - 1):
                if any((c + dc, r + dr) in claimed for dr in range(2) for dc in range(2)):
                    continue
                t00 = packed.copy(c * ts, r * ts, ts, ts)
                t10 = packed.copy((c + 1) * ts, r * ts, ts, ts)
                t01 = packed.copy(c * ts, (r + 1) * ts, ts, ts)
                t11 = packed.copy((c + 1) * ts, (r + 1) * ts, ts, ts)
                if not all(_tile_alpha_ratio(t) > 0.30 for t in (t00, t10, t01, t11)):
                    continue
                cont = (
                    _border_continuity(t00, t10, "right")
                    + _border_continuity(t00, t01, "bottom")
                    + _border_continuity(t01, t11, "right")
                    + _border_continuity(t10, t11, "bottom")
                ) / 4.0
                if cont >= 0.72:
                    patch_2x2 = packed.copy(c * ts, r * ts, 2 * ts, 2 * ts)
                    is_closed, _ = _is_closed_2x2_patch(patch_2x2, ts)
                    detected_2x2.append((c, r, is_closed))
                    v2 = self.analyze_variant(
                        sheet, asset_id, c, r, 2, 2, ts, tileset_config, cache_key=fp
                    )
                    v2.role = "composition"
                    v2.name = f"Kompozycja 2×2 @ ({c},{r})" + (" (zamknięta)" if is_closed else "")
                    proposed.append(v2)
                    for dr in range(2):
                        for dc in range(2):
                            claimed.add((c + dc, r + dr))

        summary = (
            f"Przeanalizowano arkusz {cols}×{rows}: "
            f"{len(detected_3x3)} bloków 3×3, {len(detected_2x2)} kompozycji 2×2"
        )
        result = SheetAnalysis(
            cols=cols,
            rows=rows,
            tile_width=ts,
            tile_height=th if tileset_config is not None else ts,
            proposed_variants=proposed,
            detected_3x3_blocks=detected_3x3,
            detected_2x2_blocks=detected_2x2,
            summary=summary,
        )
        self._put_cache(self._sheet_cache, fp, result)
        return result
