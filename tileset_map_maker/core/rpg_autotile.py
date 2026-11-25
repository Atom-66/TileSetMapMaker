import os
import uuid
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

from PyQt6.QtCore import Qt, QRect, QRectF
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor

from ..models.autotile import (
    MASK_N, MASK_NE, MASK_E, MASK_SE, MASK_S, MASK_SW, MASK_W, MASK_NW,
    CARDINAL_MASK, DIAGONAL_MASK,
    canonicalize_blob_mask,
    deterministic_cell_hash,
)


class AutotileFormat(str, Enum):
    VX_ACE_2X3  = "vx_ace_2x3"   # Standard RPG Maker VX / VX Ace / MV / MZ ground autotile (2x3 full tiles = 4x6 half-tiles)
    XP_3X4      = "xp_3x4"       # RPG Maker XP autotile (3x4 full tiles = 6x8 half-tiles)
    WANG_47     = "wang_47"      # Pre-assembled 47-blob Wang tilesheet
    SIMPLE_3X3  = "simple_3x3"   # 3x3 tilesheet (9 full tiles)
    BLOCK_2X2   = "block_2x2"    # 2x2 tilesheet (4 full tiles: corners/edges/center)


class CustomPathVariant:
    """
    User-defined or auto-suggested path variant bound to a specific canonical
    8-neighbor bitmask. Supports 1x1, 2x1, 1x2, 2x2, 3x3, and arbitrary WxH
    multi-tile regions from any imported tileset, with priority and weighted
    random selection.
    """

    def __init__(
        self,
        mask: int,
        source_asset_id: str,
        source_col: int,
        source_row: int,
        width_tiles: int = 1,
        height_tiles: int = 1,
        priority: int = 10,
        weight: float = 1.0,
        name: str = "",
        variant_id: Optional[str] = None,
    ):
        self.id = variant_id or str(uuid.uuid4())
        self.mask = canonicalize_blob_mask(int(mask))
        self.source_asset_id = str(source_asset_id)
        self.source_col = max(0, int(source_col))
        self.source_row = max(0, int(source_row))
        self.width_tiles = max(1, int(width_tiles))
        self.height_tiles = max(1, int(height_tiles))
        self.priority = int(priority)
        self.weight = max(0.01, float(weight))
        self.name = name or f"Wariant {self.width_tiles}x{self.height_tiles} (maska {self.mask})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mask": self.mask,
            "source_asset_id": self.source_asset_id,
            "source_col": self.source_col,
            "source_row": self.source_row,
            "width_tiles": self.width_tiles,
            "height_tiles": self.height_tiles,
            "priority": self.priority,
            "weight": self.weight,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CustomPathVariant":
        return cls(
            mask=int(data.get("mask", 0)),
            source_asset_id=str(data.get("source_asset_id", "")),
            source_col=int(data.get("source_col", 0)),
            source_row=int(data.get("source_row", 0)),
            width_tiles=int(data.get("width_tiles", 1)),
            height_tiles=int(data.get("height_tiles", 1)),
            priority=int(data.get("priority", 10)),
            weight=float(data.get("weight", 1.0)),
            name=str(data.get("name", "")),
            variant_id=data.get("id"),
        )


# ==============================================================================
# SUB-TILE (QUADRANT) STATES
# ==============================================================================
# Each quadrant (TL, TR, BL, BR) has only 5 possible geometric states:
QUAD_OUTER_CORNER = 0   # Neither cardinal neighbor is present
QUAD_EDGE_H       = 1   # Horizontal neighbor is present, vertical is not
QUAD_EDGE_V       = 2   # Vertical neighbor is present, horizontal is not
QUAD_INNER_CORNER = 3   # Both cardinal neighbors are present, but diagonal is NOT
QUAD_CENTER       = 4   # Both cardinal neighbors and the diagonal are present


def resolve_quadrant_states(
    has_n: bool, has_s: bool, has_w: bool, has_e: bool,
    has_nw: bool, has_ne: bool, has_sw: bool, has_se: bool,
) -> Tuple[int, int, int, int]:
    """
    Computes the 5-state representation for each of the 4 quadrants (TL, TR, BL, BR).
    This is the core mathematical engine of RPG Maker Autotiles.
    """
    # 1. Top-Left (TL)
    if not has_n and not has_w:
        tl = QUAD_OUTER_CORNER
    elif has_w and not has_n:
        tl = QUAD_EDGE_H
    elif has_n and not has_w:
        tl = QUAD_EDGE_V
    elif not has_nw:
        tl = QUAD_INNER_CORNER
    else:
        tl = QUAD_CENTER

    # 2. Top-Right (TR)
    if not has_n and not has_e:
        tr = QUAD_OUTER_CORNER
    elif has_e and not has_n:
        tr = QUAD_EDGE_H
    elif has_n and not has_e:
        tr = QUAD_EDGE_V
    elif not has_ne:
        tr = QUAD_INNER_CORNER
    else:
        tr = QUAD_CENTER

    # 3. Bottom-Left (BL)
    if not has_s and not has_w:
        bl = QUAD_OUTER_CORNER
    elif has_w and not has_s:
        bl = QUAD_EDGE_H
    elif has_s and not has_w:
        bl = QUAD_EDGE_V
    elif not has_sw:
        bl = QUAD_INNER_CORNER
    else:
        bl = QUAD_CENTER

    # 4. Bottom-Right (BR)
    if not has_s and not has_e:
        br = QUAD_OUTER_CORNER
    elif has_e and not has_s:
        br = QUAD_EDGE_H
    elif has_s and not has_e:
        br = QUAD_EDGE_V
    elif not has_se:
        br = QUAD_INNER_CORNER
    else:
        br = QUAD_CENTER

    return (tl, tr, bl, br)


def mask_to_quadrant_states(mask: int) -> Tuple[int, int, int, int]:
    """Converts an 8-neighbor bitmask (0..255) to 4 quadrant states."""
    c_mask = canonicalize_blob_mask(mask)
    return resolve_quadrant_states(
        has_n=bool(c_mask & MASK_N),
        has_s=bool(c_mask & MASK_S),
        has_w=bool(c_mask & MASK_W),
        has_e=bool(c_mask & MASK_E),
        has_nw=bool(c_mask & MASK_NW),
        has_ne=bool(c_mask & MASK_NE),
        has_sw=bool(c_mask & MASK_SW),
        has_se=bool(c_mask & MASK_SE),
    )


# ==============================================================================
# SUB-TILE COORDINATE MAPPINGS PER FORMAT
# ==============================================================================
# Sub-tile coordinates (hx, hy) in half-tile grid units (H = T // 2):

# RPG Maker VX / VX Ace / MV / MZ (2x3 tiles = 4x6 half-tiles):
SUBTILES_VX_ACE: Dict[int, Dict[int, Tuple[int, int]]] = {
    # Quadrant 0: TL
    0: {
        QUAD_OUTER_CORNER: (0, 2),
        QUAD_EDGE_H:       (1, 2),
        QUAD_EDGE_V:       (0, 3),
        QUAD_INNER_CORNER: (2, 0),
        QUAD_CENTER:       (1, 3),
    },
    # Quadrant 1: TR
    1: {
        QUAD_OUTER_CORNER: (3, 2),
        QUAD_EDGE_H:       (2, 2),
        QUAD_EDGE_V:       (3, 3),
        QUAD_INNER_CORNER: (3, 0),
        QUAD_CENTER:       (2, 3),
    },
    # Quadrant 2: BL
    2: {
        QUAD_OUTER_CORNER: (0, 5),
        QUAD_EDGE_H:       (1, 5),
        QUAD_EDGE_V:       (0, 4),
        QUAD_INNER_CORNER: (2, 1),
        QUAD_CENTER:       (1, 4),
    },
    # Quadrant 3: BR
    3: {
        QUAD_OUTER_CORNER: (3, 5),
        QUAD_EDGE_H:       (2, 5),
        QUAD_EDGE_V:       (3, 4),
        QUAD_INNER_CORNER: (3, 1),
        QUAD_CENTER:       (2, 4),
    },
}

# RPG Maker XP (3x4 tiles = 6x8 half-tiles):
SUBTILES_XP: Dict[int, Dict[int, Tuple[int, int]]] = {
    # Quadrant 0: TL
    0: {
        QUAD_OUTER_CORNER: (0, 2),
        QUAD_EDGE_H:       (2, 2),
        QUAD_EDGE_V:       (0, 4),
        QUAD_INNER_CORNER: (4, 0),
        QUAD_CENTER:       (2, 4),
    },
    # Quadrant 1: TR
    1: {
        QUAD_OUTER_CORNER: (5, 2),
        QUAD_EDGE_H:       (3, 2),
        QUAD_EDGE_V:       (5, 4),
        QUAD_INNER_CORNER: (5, 0),
        QUAD_CENTER:       (3, 4),
    },
    # Quadrant 2: BL
    2: {
        QUAD_OUTER_CORNER: (0, 7),
        QUAD_EDGE_H:       (2, 7),
        QUAD_EDGE_V:       (0, 5),
        QUAD_INNER_CORNER: (4, 1),
        QUAD_CENTER:       (2, 5),
    },
    # Quadrant 3: BR
    3: {
        QUAD_OUTER_CORNER: (5, 7),
        QUAD_EDGE_H:       (3, 7),
        QUAD_EDGE_V:       (5, 5),
        QUAD_INNER_CORNER: (5, 1),
        QUAD_CENTER:       (3, 5),
    },
}

# Simple 3x3 (3x3 tiles = 6x6 half-tiles):
SUBTILES_SIMPLE_3X3: Dict[int, Dict[int, Tuple[int, int]]] = {
    0: {
        QUAD_OUTER_CORNER: (0, 0),
        QUAD_EDGE_H:       (2, 0),
        QUAD_EDGE_V:       (0, 2),
        QUAD_INNER_CORNER: (2, 2),
        QUAD_CENTER:       (2, 2),
    },
    1: {
        QUAD_OUTER_CORNER: (5, 0),
        QUAD_EDGE_H:       (3, 0),
        QUAD_EDGE_V:       (5, 2),
        QUAD_INNER_CORNER: (3, 2),
        QUAD_CENTER:       (3, 2),
    },
    2: {
        QUAD_OUTER_CORNER: (0, 5),
        QUAD_EDGE_H:       (2, 5),
        QUAD_EDGE_V:       (0, 3),
        QUAD_INNER_CORNER: (2, 3),
        QUAD_CENTER:       (2, 3),
    },
    3: {
        QUAD_OUTER_CORNER: (5, 5),
        QUAD_EDGE_H:       (3, 5),
        QUAD_EDGE_V:       (5, 3),
        QUAD_INNER_CORNER: (3, 3),
        QUAD_CENTER:       (3, 3),
    },
}


def detect_autotile_format(width: int, height: int, tile_size: int = 32) -> AutotileFormat:
    """
    Automatically detects the Autotile format based on image dimensions and tile size.
    """
    ts = max(8, tile_size)
    if width == 2 * ts and height == 3 * ts:
        return AutotileFormat.VX_ACE_2X3
    if width == 3 * ts and height == 4 * ts:
        return AutotileFormat.XP_3X4
    if width == 3 * ts and height == 3 * ts:
        return AutotileFormat.SIMPLE_3X3
    if width >= 8 * ts and height >= 6 * ts:
        return AutotileFormat.WANG_47

    # Ratio heuristics
    ratio = float(width) / float(height) if height > 0 else 1.0
    if abs(ratio - (2.0 / 3.0)) < 0.1:
        return AutotileFormat.VX_ACE_2X3
    if abs(ratio - (3.0 / 4.0)) < 0.1:
        return AutotileFormat.XP_3X4
    if abs(ratio - 1.0) < 0.1:
        return AutotileFormat.SIMPLE_3X3

    return AutotileFormat.VX_ACE_2X3


# ==============================================================================
# SINGLE-TILE & TILESET CONTEXT SYNTHESIZERS
# ==============================================================================
def _fill_enclosed_transparency(tile: QImage) -> QImage:
    """Fills transparent holes inside a sprite while preserving transparent exterior."""
    from collections import deque

    image = tile.convertToFormat(QImage.Format.Format_ARGB32)
    width, height = image.width(), image.height()
    if width <= 0 or height <= 0:
        return image

    radius = max(2, min(6, min(width, height) // 8))
    opaque = bytearray(width * height)
    closed = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            opaque[y * width + x] = (
                (image.pixel(x, y) >> 24) & 0xFF
            ) > 20
    for y in range(height):
        for x in range(width):
            if opaque[y * width + x]:
                closed[y * width + x] = 1
                continue
            for dy in range(-radius, radius + 1):
                ny = y + dy
                if ny < 0 or ny >= height:
                    continue
                remaining = int((radius * radius - dy * dy) ** 0.5)
                for nx in range(max(0, x - remaining), min(width, x + remaining + 1)):
                    if opaque[ny * width + nx]:
                        closed[y * width + x] = 1
                        break
                if closed[y * width + x]:
                    break

    exterior = bytearray(width * height)
    queue = deque()

    def add_exterior(x: int, y: int) -> None:
        index = y * width + x
        if exterior[index] or closed[index]:
            return
        exterior[index] = 1
        queue.append((x, y))

    for x in range(width):
        add_exterior(x, 0)
        add_exterior(x, height - 1)
    for y in range(height):
        add_exterior(0, y)
        add_exterior(width - 1, y)

    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                add_exterior(nx, ny)

    opaque_pixels = [
        (x, y, image.pixel(x, y))
        for y in range(height)
        for x in range(width)
        if ((image.pixel(x, y) >> 24) & 0xFF) > 20
    ]
    if not opaque_pixels:
        return image

    for y in range(height):
        for x in range(width):
            index = y * width + x
            if exterior[index] or opaque[index]:
                continue
            _, _, nearest = min(
                opaque_pixels,
                key=lambda sample: (
                    (sample[0] - x) ** 2 + (sample[1] - y) ** 2
                ),
            )
            image.setPixel(x, y, nearest)
    return image


def synthesize_from_single_tile(
    tile: QImage,
    tile_size: int = 32,
    edge_style: str = "organic",
) -> QImage:
    """
    Synthesizes a complete RPG Maker VX Ace (2x3 tiles = 4x6 half-tiles)
    source image from a single material/texture tile.
    
    Generates all 5 canonical quadrant states:
    - Center (interior)
    - Outer edges (Top, Bottom, Left, Right)
    - Outer corners (TL, TR, BL, BR)
    - Inner corners (diagonal cutouts)
    - 1x1 Island (single isolated tile)
    """
    ts = max(8, int(tile_size))
    ht = ts // 2
    tile = _fill_enclosed_transparency(tile)
    res = QImage(2 * ts, 3 * ts, QImage.Format.Format_ARGB32)
    res.fill(QColor(0, 0, 0, 0))

    # Calculate average color
    r_sum, g_sum, b_sum, count = 0, 0, 0, 0
    for y in range(min(ts, tile.height())):
        for x in range(min(ts, tile.width())):
            c = tile.pixel(x, y)
            a = (c >> 24) & 0xFF
            if a > 20:
                r_sum += (c >> 16) & 0xFF
                g_sum += (c >> 8) & 0xFF
                b_sum += c & 0xFF
                count += 1
    if count == 0:
        count = 1
    ar, ag, ab = r_sum // count, g_sum // count, b_sum // count

    shadow_r = max(0, int(ar * 0.65))
    shadow_g = max(0, int(ag * 0.65))
    shadow_b = max(0, int(ab * 0.65))

    highlight_r = min(255, int(ar * 1.25) + 15)
    highlight_g = min(255, int(ag * 1.25) + 15)
    highlight_b = min(255, int(ab * 1.25) + 15)

    p = QPainter(res)
    for cy in range(3):
        for cx in range(2):
            p.drawImage(cx * ts, cy * ts, tile, 0, 0, ts, ts)
    p.end()

    depth = max(2, ts // 9)

    organic_depth = max(1, min(3, ts // 16))

    def mask_edge(img: QImage, ox: int, oy: int, w: int, h: int,
                  top: bool = False, bottom: bool = False,
                  left: bool = False, right: bool = False,
                  inner_corner_dir: Optional[str] = None):
        for y in range(h):
            for x in range(w):
                px = ox + x
                py = oy + y
                orig = img.pixel(px, py)
                orig_a = (orig >> 24) & 0xFF
                if orig_a == 0:
                    continue

                if edge_style == "organic" and not inner_corner_dir:
                    cut = (
                        top and y < organic_depth
                        or bottom and h - 1 - y < organic_depth
                        or left and x < organic_depth
                        or right and w - 1 - x < organic_depth
                    )
                    if cut:
                        img.setPixel(px, py, 0)
                    continue

                d_t = y if top else 999
                d_b = (h - 1 - y) if bottom else 999
                d_l = x if left else 999
                d_r = (w - 1 - x) if right else 999
                min_d = min(d_t, d_b, d_l, d_r)

                if inner_corner_dir:
                    if inner_corner_dir == "tl":
                        ic_dist = x + y
                    elif inner_corner_dir == "tr":
                        ic_dist = (w - 1 - x) + y
                    elif inner_corner_dir == "bl":
                        ic_dist = x + (h - 1 - y)
                    else:
                        ic_dist = (w - 1 - x) + (h - 1 - y)

                    if ic_dist < depth:
                        img.setPixel(px, py, 0)
                    continue

                if min_d == 0:
                    if edge_style == "alpha_fade":
                        fade_a = int(orig_a * 0.25)
                        img.setPixel(px, py, (fade_a << 24) | (orig & 0x00FFFFFF))
                    elif edge_style == "dark_outline":
                        img.setPixel(px, py, (orig_a << 24) | (shadow_r << 16) | (shadow_g << 8) | shadow_b)
                    else:
                        # Keep straight edges continuous; only trim the actual outer corner.
                        corner_x = x if left else (w - 1 - x if right else None)
                        corner_y = y if top else (h - 1 - y if bottom else None)
                        if (
                            corner_x is not None
                            and corner_y is not None
                            and corner_x + corner_y < depth
                        ):
                            img.setPixel(px, py, 0)
                elif min_d == 1:
                    if edge_style == "alpha_fade":
                        fade_a = int(orig_a * 0.65)
                        img.setPixel(px, py, (fade_a << 24) | (orig & 0x00FFFFFF))

    # 1. 1x1 Island at (0, 0) (half-tiles (0,0), (1,0), (0,1), (1,1))
    mask_edge(res, 0, 0, ht, ht, top=True, left=True)
    mask_edge(res, ht, 0, ht, ht, top=True, right=True)
    mask_edge(res, 0, ht, ht, ht, bottom=True, left=True)
    mask_edge(res, ht, ht, ht, ht, bottom=True, right=True)

    # 2. 4 Inner corners at (2, 0) to (3, 1)
    mask_edge(res, 2 * ht, 0, ht, ht, inner_corner_dir="tl")
    mask_edge(res, 3 * ht, 0, ht, ht, inner_corner_dir="tr")
    mask_edge(res, 2 * ht, ht, ht, ht, inner_corner_dir="bl")
    mask_edge(res, 3 * ht, ht, ht, ht, inner_corner_dir="br")

    # 3. Outer perimeter of the 2x2 block from (0, 2*ht) to (4*ht, 6*ht)
    # Row 2: Top edge
    mask_edge(res, 0, 2 * ht, ht, ht, top=True, left=True)
    mask_edge(res, ht, 2 * ht, ht, ht, top=True)
    mask_edge(res, 2 * ht, 2 * ht, ht, ht, top=True)
    mask_edge(res, 3 * ht, 2 * ht, ht, ht, top=True, right=True)

    # Row 3: Left and Right edges (center untouched)
    mask_edge(res, 0, 3 * ht, ht, ht, left=True)
    mask_edge(res, 3 * ht, 3 * ht, ht, ht, right=True)

    # Row 4: Left and Right edges (center untouched)
    mask_edge(res, 0, 4 * ht, ht, ht, left=True)
    mask_edge(res, 3 * ht, 4 * ht, ht, ht, right=True)

    # Row 5: Bottom edge
    mask_edge(res, 0, 5 * ht, ht, ht, bottom=True, left=True)
    mask_edge(res, ht, 5 * ht, ht, ht, bottom=True)
    mask_edge(res, 2 * ht, 5 * ht, ht, ht, bottom=True)
    mask_edge(res, 3 * ht, 5 * ht, ht, ht, bottom=True, right=True)

    return res


def _tile_alpha_ratio(img: QImage) -> float:
    """Returns fraction of non-transparent pixels (alpha > 20) in an image."""
    w, h = img.width(), img.height()
    if w <= 0 or h <= 0:
        return 0.0
    step = max(1, min(w, h) // 16)
    opaque = 0
    total = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            total += 1
            if ((img.pixel(x, y) >> 24) & 0xFF) > 20:
                opaque += 1
    return opaque / float(max(1, total))


def _border_continuity(tile_a: QImage, tile_b: QImage, direction: str) -> float:
    """
    Computes visual color continuity (0.0..1.0) across the shared border
    between two adjacent tiles ('right' means tile_b is right of tile_a,
    'bottom' means tile_b is below tile_a).
    """
    w = min(tile_a.width(), tile_b.width())
    h = min(tile_a.height(), tile_b.height())
    if w <= 0 or h <= 0:
        return 0.0
    diff_sum = 0.0
    samples = 0
    if direction == "right":
        for y in range(0, h, max(1, h // 12)):
            pa = tile_a.pixel(w - 1, y)
            pb = tile_b.pixel(0, y)
            alpha_a, alpha_b = (pa >> 24) & 0xFF, (pb >> 24) & 0xFF
            if alpha_a > 20 and alpha_b > 20:
                dr = abs(((pa >> 16) & 0xFF) - ((pb >> 16) & 0xFF))
                dg = abs(((pa >> 8) & 0xFF) - ((pb >> 8) & 0xFF))
                db = abs((pa & 0xFF) - (pb & 0xFF))
                diff_sum += (dr + dg + db) / (3.0 * 255.0)
            else:
                diff_sum += 1.0
            samples += 1
    else:
        for x in range(0, w, max(1, w // 12)):
            pa = tile_a.pixel(x, h - 1)
            pb = tile_b.pixel(x, 0)
            alpha_a, alpha_b = (pa >> 24) & 0xFF, (pb >> 24) & 0xFF
            if alpha_a > 20 and alpha_b > 20:
                dr = abs(((pa >> 16) & 0xFF) - ((pb >> 16) & 0xFF))
                dg = abs(((pa >> 8) & 0xFF) - ((pb >> 8) & 0xFF))
                db = abs((pa & 0xFF) - (pb & 0xFF))
                diff_sum += (dr + dg + db) / (3.0 * 255.0)
            else:
                diff_sum += 1.0
            samples += 1
    return max(0.0, 1.0 - (diff_sum / float(max(1, samples))))


def _tri_wave(idx: int, period: int) -> int:
    """Mirror-reflects an index smoothly within [0, period - 1] to avoid tiling seams."""
    if period <= 1:
        return 0
    span = 2 * (period - 1)
    m = idx % span
    return m if m < period else span - m


def _synthesize_interior_fill_from_ring(patch: QImage, ts: int) -> QImage:
    """
    Reconstructs a clean, seamless ts x ts interior tile for a 3x3 ring whose
    center has a transparent gap, sampling ONLY from the pure inner-facing rows
    of Top/Bottom (and Left/Right fallback) that are completely free of outer-rim
    or dark-outline pixels, tiled periodically without mirror artifacts.
    """
    fill = QImage(ts, ts, QImage.Format.Format_ARGB32)
    pw, ph = patch.width(), patch.height()
    ht = ts // 2
    cx = (pw - ts) // 2
    cy = (ph - ts) // 2

    # 1. Estimate pure interior color from the 1-pixel inner ring immediately bordering the center
    inner_rs: List[int] = []
    inner_gs: List[int] = []
    inner_bs: List[int] = []
    for k in range(ts):
        for sx, sy in (
            (cx + k, cy - 1),
            (cx + k, cy + ts),
            (cx - 1, cy + k),
            (cx + ts, cy + k),
        ):
            if 0 <= sx < pw and 0 <= sy < ph:
                px = patch.pixel(sx, sy)
                if ((px >> 24) & 0xFF) > 180:
                    inner_rs.append((px >> 16) & 0xFF)
                    inner_gs.append((px >> 8) & 0xFF)
                    inner_bs.append(px & 0xFF)

    if inner_rs:
        inner_rs.sort()
        inner_gs.sort()
        inner_bs.sort()
        mid = len(inner_rs) // 2
        ref_r, ref_g, ref_b = inner_rs[mid], inner_gs[mid], inner_bs[mid]
        fallback_pixel = QColor(ref_r, ref_g, ref_b, 255).rgba()
    else:
        ref_r, ref_g, ref_b = 150, 120, 80
        fallback_pixel = QColor(ref_r, ref_g, ref_b, 255).rgba()

    def _is_pure_inner(px: int) -> bool:
        if ((px >> 24) & 0xFF) <= 180:
            return False
        return _pixel_dist_from_rgb(px, ref_r, ref_g, ref_b) <= 0.14

    def _row_is_pure(sy: int) -> bool:
        if not (0 <= sy < ph):
            return False
        pure = 0
        for x in range(ts):
            if _is_pure_inner(patch.pixel(cx + x, sy)):
                pure += 1
        return pure >= int(ts * 0.85)

    # 2. Collect ONLY pure interior rows adjacent to the center (never touching outer rim/tufts!)
    max_band = max(4, ts // 3)
    bot_pure_rows: List[int] = []
    for dy in range(max_band):
        sy = cy + ts + dy
        if _row_is_pure(sy):
            bot_pure_rows.append(sy)
        else:
            break

    top_pure_rows: List[int] = []
    for dy in range(max_band):
        sy = cy - 1 - dy
        if _row_is_pure(sy):
            top_pure_rows.append(sy)
        else:
            break
    top_pure_rows.reverse()  # Top-to-bottom order ending at cy - 1

    # Combine into one coherent, periodic vertical band of pure interior texture
    pure_rows = bot_pure_rows + top_pure_rows

    for y in range(ts):
        for x in range(ts):
            chosen: Optional[int] = None
            if pure_rows:
                sy = pure_rows[y % len(pure_rows)]
                cand = patch.pixel(cx + x, sy)
                if _is_pure_inner(cand):
                    chosen = cand

            if chosen is None:
                # Fallback to nearest pure inner pixel from the 4 immediate borders
                for sx, sy in (
                    (cx + x, cy - 1),
                    (cx + x, cy + ts),
                    (cx - 1, cy + y),
                    (cx + ts, cy + y),
                ):
                    if 0 <= sx < pw and 0 <= sy < ph:
                        cand = patch.pixel(sx, sy)
                        if _is_pure_inner(cand):
                            chosen = cand
                            break

            fill.setPixel(x, y, chosen if chosen is not None else fallback_pixel)
    return fill


def _pixel_dist_from_rgb(pixel: int, ref_r: int, ref_g: int, ref_b: int) -> float:
    a = (pixel >> 24) & 0xFF
    if a <= 20:
        return 1.5  # Transparent counts as strongly outside opaque interior
    r = (pixel >> 16) & 0xFF
    g = (pixel >> 8) & 0xFF
    b = pixel & 0xFF
    return (abs(r - ref_r) + abs(g - ref_g) + abs(b - ref_b)) / (3.0 * 255.0)


def _avg_opaque_rgb(img: QImage) -> Tuple[int, int, int]:
    r_sum = g_sum = b_sum = count = 0
    for y in range(img.height()):
        for x in range(img.width()):
            p = img.pixel(x, y)
            if ((p >> 24) & 0xFF) > 20:
                r_sum += (p >> 16) & 0xFF
                g_sum += (p >> 8) & 0xFF
                b_sum += p & 0xFF
                count += 1
    if count == 0:
        return (128, 128, 128)
    return (r_sum // count, g_sum // count, b_sum // count)


def _measure_rim_thickness(
    strip: QImage, cr: int, cg: int, cb: int, axis: str, from_start: bool, thresh: float
) -> int:
    """
    Measures how many pixels from the outer border of an edge tile belong to the
    outer rim material (before reaching the inner center material).
    """
    w, h = strip.width(), strip.height()
    limit = w if axis == "x" else h
    samples = []
    if axis == "x":
        for y in range(0, h, max(1, h // 8)):
            depth = 0
            for step in range(limit):
                x = step if from_start else (w - 1 - step)
                if _pixel_dist_from_rgb(strip.pixel(x, y), cr, cg, cb) > thresh:
                    depth = step + 1
                else:
                    break
            samples.append(depth)
    else:
        for x in range(0, w, max(1, w // 8)):
            depth = 0
            for step in range(limit):
                y = step if from_start else (h - 1 - step)
                if _pixel_dist_from_rgb(strip.pixel(x, y), cr, cg, cb) > thresh:
                    depth = step + 1
                else:
                    break
            samples.append(depth)
    if not samples:
        return 0
    samples.sort()
    return samples[len(samples) // 2]


def synthesize_vx_ace_from_3x3(patch_3x3: QImage, tile_size: int = 32) -> QImage:
    """
    Converts a 3x3 tilesheet block into a full RPG Maker VX Ace (2x3 tiles = 4x6 half-tiles)
    source image with:
    - Pattern-preserving opaque center synthesis if the 3x3 center tile is transparent (LPC ring fix)
    - Balanced outer rim thickness (shifts sampling inward if the 3x3 border is >50% of a half-tile,
      so 1-tile peninsulas and 1x1 islands keep a lush interior instead of getting pinched)
    - Smoothly rounded edge-intersection 4 inner corners reproducing the exact outer material
      and organic transition tufts of the side tiles with zero black holes
    """
    import math

    ts = max(8, int(tile_size))
    ht = ts // 2
    src = patch_3x3.copy()
    center_tile = src.copy(ts, ts, ts, ts)
    if _tile_alpha_ratio(center_tile) < 0.999:
        filled = _synthesize_interior_fill_from_ring(src, ts)
        for y in range(ts):
            for x in range(ts):
                if ((center_tile.pixel(x, y) >> 24) & 0xFF) <= 20:
                    center_tile.setPixel(x, y, filled.pixel(x, y))
        p_fix = QPainter(src)
        p_fix.drawImage(ts, ts, center_tile)
        p_fix.end()

    cr, cg, cb = _avg_opaque_rgb(center_tile)

    # Measure outer rim thickness on the 4 cardinal edge tiles (full ts depth)
    # If the outer rim occupies >50% of a half-tile (common in LPC terrain transitions where
    # dirt takes ~13-14px of a 16px half-tile), shift the half-tile extraction window inward
    # so 1-tile strips and 1x1 islands retain a rich, balanced green/interior core!
    top_tile = src.copy(ts, 0, ts, ts)
    bot_tile = src.copy(ts, 2 * ts, ts, ts)
    left_tile = src.copy(0, ts, ts, ts)
    right_tile = src.copy(2 * ts, ts, ts, ts)

    rim_contrast = max(
        _pixel_dist_from_rgb(top_tile.pixel(ts // 2, 0), cr, cg, cb),
        _pixel_dist_from_rgb(left_tile.pixel(0, ts // 2), cr, cg, cb),
        _pixel_dist_from_rgb(bot_tile.pixel(ts // 2, ts - 1), cr, cg, cb),
        _pixel_dist_from_rgb(right_tile.pixel(ts - 1, ts // 2), cr, cg, cb),
    )
    thresh = max(0.06, min(0.18, rim_contrast * 0.35))

    rim_t = _measure_rim_thickness(top_tile, cr, cg, cb, "y", True, thresh)
    rim_b = _measure_rim_thickness(bot_tile, cr, cg, cb, "y", False, thresh)
    rim_l = _measure_rim_thickness(left_tile, cr, cg, cb, "x", True, thresh)
    rim_r = _measure_rim_thickness(right_tile, cr, cg, cb, "x", False, thresh)

    # Target rim depth inside each half-tile: ~45% of ht (e.g. ~7px on 32px tiles -> ~18px interior!)
    target_rim = max(3, int(ht * 0.45))
    max_shift = max(0, ts - ht)

    def _calc_shift(rim_px: int) -> int:
        # Only shift if rim actually ends inside the tile (rim_px < ts - 2) and exceeds target_rim
        if target_rim < rim_px < ts - 2:
            return min(max_shift, rim_px - target_rim)
        return 0

    st = _calc_shift(rim_t)
    sb = _calc_shift(rim_b)
    sl = _calc_shift(rim_l)
    sr = _calc_shift(rim_r)

    # Extract shifted outer corner and edge half-tiles
    q_tl = src.copy(sl, st, ht, ht)
    q_tr = src.copy(3 * ts - ht - sr, st, ht, ht)
    q_bl = src.copy(sl, 3 * ts - ht - sb, ht, ht)
    q_br = src.copy(3 * ts - ht - sr, 3 * ts - ht - sb, ht, ht)

    q_top_l = src.copy(ts, st, ht, ht)
    q_top_r = src.copy(ts + ht, st, ht, ht)
    q_bot_l = src.copy(ts, 3 * ts - ht - sb, ht, ht)
    q_bot_r = src.copy(ts + ht, 3 * ts - ht - sb, ht, ht)

    q_left_t = src.copy(sl, ts, ht, ht)
    q_left_b = src.copy(sl, ts + ht, ht, ht)
    q_right_t = src.copy(3 * ts - ht - sr, ts, ht, ht)
    q_right_b = src.copy(3 * ts - ht - sr, ts + ht, ht, ht)

    res = QImage(2 * ts, 3 * ts, QImage.Format.Format_ARGB32)
    res.fill(QColor(0, 0, 0, 0))
    p = QPainter(res)

    # Row 0-1 (cols 0..1): 1x1 Island composed from the balanced outer corners
    p.drawImage(0, 0, q_tl)
    p.drawImage(ht, 0, q_tr)
    p.drawImage(0, ht, q_bl)
    p.drawImage(ht, ht, q_br)

    # Row 2-5 (cols 0..3): Outer 2x2 perimeter + center
    p.drawImage(0, 2 * ht, q_tl)
    p.drawImage(ht, 2 * ht, q_top_l)
    p.drawImage(2 * ht, 2 * ht, q_top_r)
    p.drawImage(3 * ht, 2 * ht, q_tr)

    p.drawImage(0, 3 * ht, q_left_t)
    p.drawImage(ht, 3 * ht, center_tile, 0, 0, ht, ht)
    p.drawImage(2 * ht, 3 * ht, center_tile, ht, 0, ht, ht)
    p.drawImage(3 * ht, 3 * ht, q_right_t)

    p.drawImage(0, 4 * ht, q_left_b)
    p.drawImage(ht, 4 * ht, center_tile, 0, ht, ht, ht)
    p.drawImage(2 * ht, 4 * ht, center_tile, ht, ht, ht, ht)
    p.drawImage(3 * ht, 4 * ht, q_right_b)

    p.drawImage(0, 5 * ht, q_bl)
    p.drawImage(ht, 5 * ht, q_bot_l)
    p.drawImage(2 * ht, 5 * ht, q_bot_r)
    p.drawImage(3 * ht, 5 * ht, q_br)
    p.end()

    # Row 0-1 (cols 2..3): Synthesize the 4 Inner Corners with smooth organic rounding
    # matching the exact balanced side edges (zero square bulge, zero black holes!)
    inner_defs = (
        (2 * ht, 0, q_left_t, q_top_l, center_tile.copy(0, 0, ht, ht), True, True),
        (3 * ht, 0, q_right_t, q_top_r, center_tile.copy(ht, 0, ht, ht), False, True),
        (2 * ht, ht, q_left_b, q_bot_l, center_tile.copy(0, ht, ht, ht), True, False),
        (3 * ht, ht, q_right_b, q_bot_r, center_tile.copy(ht, ht, ht, ht), False, False),
    )

    for dest_x, dest_y, v_quad, h_quad, c_quad, cut_left, cut_top in inner_defs:
        rx = max(2, _measure_rim_thickness(v_quad, cr, cg, cb, "x", cut_left, thresh))
        ry = max(2, _measure_rim_thickness(h_quad, cr, cg, cb, "y", cut_top, thresh))

        # Detect the real dark outline/border color along the side edge transition
        # (e.g., dark forest green between brown dirt and green grass)
        center_luma = 0.299 * cr + 0.587 * cg + 0.114 * cb
        dark_border_pixel: Optional[int] = None
        darkest_luma = center_luma * 0.78  # Must be noticeably darker than center to count as outline
        for probe_img in (v_quad, h_quad):
            for py in range(ht):
                for px_i in range(ht):
                    p_val = probe_img.pixel(px_i, py)
                    if ((p_val >> 24) & 0xFF) <= 180:
                        continue
                    pr = (p_val >> 16) & 0xFF
                    pg = (p_val >> 8) & 0xFF
                    pb = p_val & 0xFF
                    luma = 0.299 * pr + 0.587 * pg + 0.114 * pb
                    if luma < darkest_luma:
                        darkest_luma = luma
                        dark_border_pixel = p_val

        # Track outer mask per pixel in this quadrant to close any 1px gap in the dark outline
        is_outer_grid = [[False] * ht for _ in range(ht)]

        for y in range(ht):
            for x in range(ht):
                dx = x if cut_left else (ht - 1 - x)
                dy = y if cut_top else (ht - 1 - y)
                pc = c_quad.pixel(x, y)

                # Smooth quarter-ellipse distance: equals 1.0 at (rx, 0) and (0, ry)
                # so it aligns 100% with adjacent side tiles while rounding off the sharp corner!
                r_norm = math.sqrt((dx / float(rx)) ** 2 + (dy / float(ry)) ** 2)
                if r_norm <= 1.08:
                    pv = v_quad.pixel(x, y)
                    ph = h_quad.pixel(x, y)
                    if r_norm <= 0.78:
                        # Deep inside inner corner: copy real outer texture (e.g. brown dirt pebbles)
                        chosen = pv if dx <= dy else ph
                        res.setPixel(dest_x + x, dest_y + y, chosen)
                        is_outer_grid[y][x] = True
                    else:
                        # Organic transition zone: sample the edge strip at the radial depth
                        # so the exact pixel-art grass tufts wrap smoothly around the curve!
                        sample_depth = min(ht - 1, int(r_norm * (rx if dx >= dy else ry)))
                        if dx >= dy:
                            sx = sample_depth if cut_left else (ht - 1 - sample_depth)
                            cand = v_quad.pixel(sx, y)
                        else:
                            sy = sample_depth if cut_top else (ht - 1 - sample_depth)
                            cand = h_quad.pixel(x, sy)
                        if _pixel_dist_from_rgb(cand, cr, cg, cb) > thresh:
                            res.setPixel(dest_x + x, dest_y + y, cand)
                            is_outer_grid[y][x] = True
                        else:
                            res.setPixel(dest_x + x, dest_y + y, pc)
                else:
                    res.setPixel(dest_x + x, dest_y + y, pc)

        # Ensure unbroken 1px dark outline wherever inner material directly touches outer material
        if dark_border_pixel is not None:
            for y in range(ht):
                for x in range(ht):
                    if is_outer_grid[y][x]:
                        continue
                    touches_outer = False
                    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nx, ny = x + ox, y + oy
                        if 0 <= nx < ht and 0 <= ny < ht and is_outer_grid[ny][nx]:
                            touches_outer = True
                            break
                    if touches_outer:
                        cur = res.pixel(dest_x + x, dest_y + y)
                        cur_luma = (
                            0.299 * ((cur >> 16) & 0xFF)
                            + 0.587 * ((cur >> 8) & 0xFF)
                            + 0.114 * (cur & 0xFF)
                        )
                        if cur_luma > center_luma * 0.80:
                            res.setPixel(dest_x + x, dest_y + y, dark_border_pixel)

    return res


def synthesize_vx_ace_from_2x2(patch_2x2: QImage, tile_size: int = 32) -> QImage:
    """
    Converts a 2x2 tilesheet block (4 tiles = 4x4 half-tiles) into a complete
    RPG Maker VX Ace (2x3 tiles = 4x6 half-tiles) autotile source image.
    Ideal for 2x2 corner/island/path blocks like LPC 2x2 terrain transitions.
    """
    ts = max(8, int(tile_size))
    ht = ts // 2
    # Upscale/extract 2x2 into a virtual 3x3 by duplicating middle strips for H/V edges
    virtual_3x3 = QImage(3 * ts, 3 * ts, QImage.Format.Format_ARGB32)
    virtual_3x3.fill(QColor(0, 0, 0, 0))
    p = QPainter(virtual_3x3)
    # Corners
    p.drawImage(0, 0, patch_2x2, 0, 0, ts, ts)                       # TL
    p.drawImage(2 * ts, 0, patch_2x2, ts, 0, ts, ts)                 # TR
    p.drawImage(0, 2 * ts, patch_2x2, 0, ts, ts, ts)                 # BL
    p.drawImage(2 * ts, 2 * ts, patch_2x2, ts, ts, ts, ts)           # BR
    # Top edge (middle strip of top half)
    p.drawImage(ts, 0, patch_2x2, ht, 0, ht, ts)
    p.drawImage(ts + ht, 0, patch_2x2, ts, 0, ht, ts)
    # Bottom edge
    p.drawImage(ts, 2 * ts, patch_2x2, ht, ts, ht, ts)
    p.drawImage(ts + ht, 2 * ts, patch_2x2, ts, ts, ht, ts)
    # Left edge
    p.drawImage(0, ts, patch_2x2, 0, ht, ts, ht)
    p.drawImage(0, ts + ht, patch_2x2, 0, ts, ts, ht)
    # Right edge
    p.drawImage(2 * ts, ts, patch_2x2, ts, ht, ts, ht)
    p.drawImage(2 * ts, ts + ht, patch_2x2, ts, ts, ts, ht)
    # Center (innermost 2x2 half-tiles)
    p.drawImage(ts, ts, patch_2x2, ht, ht, ts, ts)
    p.end()
    return synthesize_vx_ace_from_3x3(virtual_3x3, ts)


def analyze_tileset_region(
    sheet: QImage,
    col: int,
    row: int,
    w_tiles: int = 1,
    h_tiles: int = 1,
    tile_size: int = 32,
) -> Dict[str, Any]:
    """
    Analyzes actual pixel content, transparency, and border continuity of a
    selected tileset region to suggest the best autotile synthesis mode.
    """
    ts = max(8, int(tile_size))
    w_t = max(1, int(w_tiles))
    h_t = max(1, int(h_tiles))

    if (
        col < 0
        or row < 0
        or col * ts + w_t * ts > sheet.width()
        or row * ts + h_t * ts > sheet.height()
    ):
        return {
            "suggested_mode": "single_tile",
            "confidence": 0.2,
            "center_is_transparent": False,
            "continuity": 0.0,
            "summary": "Zaznaczenie wykracza poza arkusz — użyto bezpiecznego fallbacku.",
        }

    if w_t == 2 and h_t == 2:
        t00 = sheet.copy(col * ts, row * ts, ts, ts)
        t10 = sheet.copy((col + 1) * ts, row * ts, ts, ts)
        t01 = sheet.copy(col * ts, (row + 1) * ts, ts, ts)
        cont = (_border_continuity(t00, t10, "right") + _border_continuity(t00, t01, "bottom")) / 2.0
        if cont < 0.65:
            representative_col, representative_row = max(
                (
                    (col + dc, row + dr)
                    for dr in range(2)
                    for dc in range(2)
                ),
                key=lambda coordinate: _tile_alpha_ratio(
                    sheet.copy(
                        coordinate[0] * ts,
                        coordinate[1] * ts,
                        ts,
                        ts,
                    )
                ),
            )
            return {
                "suggested_mode": "single_tile",
                "confidence": round(1.0 - cont, 2),
                "center_is_transparent": _tile_alpha_ratio(t00) < 0.25,
                "continuity": round(cont, 2),
                "representative_col": representative_col,
                "representative_row": representative_row,
                "summary": (
                    "Pojedynczy kafelek z nieciągłego zaznaczenia 2×2; "
                    f"źródło ({representative_col}, {representative_row})"
                ),
            }
        return {
            "suggested_mode": "block_2x2",
            "confidence": round(min(1.0, 0.55 + cont * 0.45), 2),
            "center_is_transparent": False,
            "continuity": round(cont, 2),
            "summary": f"Wykryto blok 2×2 (ciągłość krawędzi: {int(cont * 100)}%)",
        }

    if w_t == 3 and h_t == 3:
        center = sheet.copy((col + 1) * ts, (row + 1) * ts, ts, ts)
        c_alpha = _tile_alpha_ratio(center)
        top = sheet.copy((col + 1) * ts, row * ts, ts, ts)
        left = sheet.copy(col * ts, (row + 1) * ts, ts, ts)
        cont = (_border_continuity(top, center, "bottom") + _border_continuity(left, center, "right")) / 2.0
        extra = " (automatyczne wypełnienie przezroczystego środka)" if c_alpha < 0.25 else ""
        return {
            "suggested_mode": "block_3x3_tl",
            "confidence": round(min(1.0, 0.65 + cont * 0.35), 2),
            "center_is_transparent": c_alpha < 0.25,
            "continuity": round(cont, 2),
            "summary": f"Wykryto blok 3×3{extra}",
        }

    if w_t == 2 and h_t == 3:
        return {
            "suggested_mode": "block_2x3_vx",
            "confidence": 0.9,
            "center_is_transparent": False,
            "continuity": 0.9,
            "summary": "Wykryto układ RPG Maker VX 2×3",
        }

    if w_t > 1 or h_t > 1:
        return {
            "suggested_mode": "custom_region",
            "confidence": 0.85,
            "center_is_transparent": False,
            "continuity": 0.85,
            "summary": f"Własny obszar wielokafelkowy {w_t}×{h_t}",
        }

    # Single tile selected: inspect surrounding 3x3 continuity before assuming it's a 3x3 block
    target = sheet.copy(col * ts, row * ts, ts, ts)
    has_3x3 = col >= 1 and row >= 1 and (col + 2) * ts <= sheet.width() and (row + 2) * ts <= sheet.height()
    if has_3x3:
        t_n = sheet.copy(col * ts, (row - 1) * ts, ts, ts)
        t_s = sheet.copy(col * ts, (row + 1) * ts, ts, ts)
        t_w = sheet.copy((col - 1) * ts, row * ts, ts, ts)
        t_e = sheet.copy((col + 1) * ts, row * ts, ts, ts)
        c_alpha = _tile_alpha_ratio(target)
        # Only suggest 3x3 if borders are actually continuous AND neighbors are opaque
        neighbors_opaque = all(_tile_alpha_ratio(n) > 0.2 for n in (t_n, t_s, t_w, t_e))
        cont = (
            _border_continuity(t_n, target, "bottom")
            + _border_continuity(target, t_s, "bottom")
            + _border_continuity(t_w, target, "right")
            + _border_continuity(target, t_e, "right")
        ) / 4.0
        if neighbors_opaque and (cont >= 0.45 or c_alpha < 0.25):
            extra = " + auto-wypełnienie środka" if c_alpha < 0.25 else ""
            return {
                "suggested_mode": "block_3x3_center",
                "confidence": round(min(1.0, 0.5 + cont * 0.5), 2),
                "center_is_transparent": c_alpha < 0.25,
                "continuity": round(cont, 2),
                "summary": f"Wykryto spójny blok 3×3 (ciągłość {int(cont * 100)}%{extra})",
            }

    return {
        "suggested_mode": "single_tile",
        "confidence": 0.8,
        "center_is_transparent": _tile_alpha_ratio(target) < 0.25,
        "continuity": 0.0,
        "summary": "Pojedynczy kafelek (synteza krawędzi i narożników)",
    }


def synthesize_from_tileset_context(
    sheet: QImage,
    col: int,
    row: int,
    tile_size: int = 32,
    mode: str = "auto",
    edge_style: str = "organic",
    w_tiles: int = 1,
    h_tiles: int = 1,
) -> Tuple[QImage, AutotileFormat, str]:
    """
    Extracts a tile or WxH region from a tileset sheet and synthesizes an
    accurate 47-combination Autotile with proper inner corners and transparent-center handling.
    """
    ts = max(8, int(tile_size))
    w_t = max(1, int(w_tiles))
    h_t = max(1, int(h_tiles))

    if (
        col < 0
        or row < 0
        or col * ts + w_t * ts > sheet.width()
        or row * ts + h_t * ts > sheet.height()
    ):
        blank = QImage(ts, ts, QImage.Format.Format_ARGB32)
        blank.fill(QColor("#3b82f6"))
        return (
            synthesize_from_single_tile(blank, ts, edge_style),
            AutotileFormat.VX_ACE_2X3,
            "Zaznaczenie poza zakresem arkusza",
        )

    effective_mode = mode
    analysis = analyze_tileset_region(sheet, col, row, w_t, h_t, ts)
    if mode == "auto":
        effective_mode = analysis["suggested_mode"]

    # 1. Explicit or detected 2x2 block
    if effective_mode == "block_2x2" and (col + 2) * ts <= sheet.width() and (row + 2) * ts <= sheet.height():
        patch_2x2 = sheet.copy(col * ts, row * ts, 2 * ts, 2 * ts)
        img = synthesize_vx_ace_from_2x2(patch_2x2, ts)
        return img, AutotileFormat.VX_ACE_2X3, f"Blok 2×2 z tilesetu ({analysis['summary']})"

    # 2. 3x3 block centered at (col, row) -> converted to full VX Ace with inner corners & transparent-center fix
    has_3x3_center = (
        col >= 1 and row >= 1 and
        (col + 2) * ts <= sheet.width() and
        (row + 2) * ts <= sheet.height()
    )
    if has_3x3_center and effective_mode == "block_3x3_center":
        patch_3x3 = sheet.copy((col - 1) * ts, (row - 1) * ts, 3 * ts, 3 * ts)
        img = synthesize_vx_ace_from_3x3(patch_3x3, ts)
        return img, AutotileFormat.VX_ACE_2X3, f"Blok 3×3 (środek) + narożniki wewn. ({analysis['summary']})"

    # 3. 3x3 block starting at (col, row) as Top-Left
    has_3x3_tl = (col + 3) * ts <= sheet.width() and (row + 3) * ts <= sheet.height()
    if has_3x3_tl and effective_mode == "block_3x3_tl":
        patch_3x3 = sheet.copy(col * ts, row * ts, 3 * ts, 3 * ts)
        img = synthesize_vx_ace_from_3x3(patch_3x3, ts)
        return img, AutotileFormat.VX_ACE_2X3, "Blok 3×3 z tilesetu (róg TL + narożniki wewn.)"

    # 4. 2x3 RPG Maker VX Ace block starting at (col, row)
    has_2x3 = (col + 2) * ts <= sheet.width() and (row + 3) * ts <= sheet.height()
    if has_2x3 and effective_mode == "block_2x3_vx":
        patch_2x3 = sheet.copy(col * ts, row * ts, 2 * ts, 3 * ts)
        return patch_2x3, AutotileFormat.VX_ACE_2X3, "Układ 2×3 RPG Maker VX z arkusza"

    # 5. Arbitrary WxH rectangular region (2x1, 1x2, 4x2, etc.)
    if effective_mode == "custom_region" and (w_t > 1 or h_t > 1):
        representative = QImage(2 * ts, 2 * ts, QImage.Format.Format_ARGB32)
        painter = QPainter(representative)
        corner_tiles = (
            (col, row),
            (col + w_t - 1, row),
            (col, row + h_t - 1),
            (col + w_t - 1, row + h_t - 1),
        )
        for (src_col, src_row), (dst_col, dst_row) in zip(
            corner_tiles, ((0, 0), (1, 0), (0, 1), (1, 1))
        ):
            painter.drawImage(
                dst_col * ts,
                dst_row * ts,
                sheet,
                src_col * ts,
                src_row * ts,
                ts,
                ts,
            )
        painter.end()
        img = synthesize_vx_ace_from_2x2(representative, ts)
        return img, AutotileFormat.VX_ACE_2X3, f"Obszar niestandardowy {w_t}×{h_t} z arkusza"

    # 6. Default: single tile organic/soft/outline synthesis
    source_col = col
    source_row = row
    if mode == "auto" and effective_mode == "single_tile":
        source_col = int(analysis.get("representative_col", col))
        source_row = int(analysis.get("representative_row", row))
    target_tile = sheet.copy(source_col * ts, source_row * ts, ts, ts)
    img = synthesize_from_single_tile(target_tile, ts, edge_style)
    description = (
        analysis["summary"]
        if mode == "auto" and effective_mode == "single_tile"
        else "Pojedynczy kafelek (synteza krawędzi)"
    )
    return img, AutotileFormat.VX_ACE_2X3, description


# ==============================================================================
# CANONICAL WANG 47 COMBINATIONS
# ==============================================================================
def generate_all_canonical_masks() -> List[int]:
    """Generates all 47 canonical Wang-blob bitmasks in deterministic order."""
    unique_masks: Dict[int, bool] = {}
    for raw in range(256):
        c = canonicalize_blob_mask(raw)
        unique_masks[c] = True
    return sorted(list(unique_masks.keys()))

CANONICAL_47_MASKS = generate_all_canonical_masks()
MASK_TO_CANONICAL_INDEX: Dict[int, int] = {
    m: i for i, m in enumerate(CANONICAL_47_MASKS)
}


# ==============================================================================
# RPG AUTOTILE CLASS (STANDALONE ONE-CLICK TERRAIN/PATH)
# ==============================================================================
class RPGAutotile:
    """
    Complete RPG Maker-style Autotile.
    Represents a full terrain or path type (grass, water, dirt, road, wall)
    that is selected with ONE click and automatically adapts to any painted shape.
    """

    def __init__(
        self,
        name: str = "Nowy Autotile",
        terrain_type: str = "Ground",
        autotile_format: AutotileFormat = AutotileFormat.VX_ACE_2X3,
        tile_size: int = 32,
        autotile_id: Optional[str] = None,
        source_image_path: Optional[str] = None,
        source_asset_id: Optional[str] = None,
        source_rect: Optional[Tuple[int, int, int, int]] = None,
        seed: int = 42,
        source_col: int = 0,
        source_row: int = 0,
        source_w_tiles: int = 1,
        source_h_tiles: int = 1,
        generation_mode: str = "auto",
        edge_style: str = "organic",
        id: Optional[str] = None,
        tileset_id: Optional[str] = None,
        archived: bool = False,
        **kwargs: Any,
    ):
        self.id = autotile_id or id or str(uuid.uuid4())
        self.name = name
        self.terrain_type = terrain_type
        self.format = (
            autotile_format
            if isinstance(autotile_format, AutotileFormat)
            else AutotileFormat(autotile_format)
        )
        self.tile_size = max(8, int(tile_size))
        self.source_image_path = source_image_path
        self.source_asset_id = source_asset_id or tileset_id
        self.source_rect = source_rect
        self.seed = seed
        self.source_col = source_col
        self.source_row = source_row
        self.source_w_tiles = max(1, int(source_w_tiles))
        self.source_h_tiles = max(1, int(source_h_tiles))
        self.generation_mode = generation_mode
        self.edge_style = edge_style
        self.archived = bool(archived)

        # Center / decorative variants: list of dicts with {"weight": float, "sub_coords": tuple}
        self.center_variants: List[Dict[str, Any]] = []
        # Custom multi-tile / single-tile rule overrides (1x1, 2x1, 1x2, 2x2, 3x3, WxH)
        self.custom_variants: List[CustomPathVariant] = []

        # Cached composite atlas: QImage of size (8 * tile_size, 6 * tile_size)
        self._atlas_image: Optional[QImage] = None
        self._atlas_pixmap: Optional[QPixmap] = None
        self._preview_pixmap: Optional[QPixmap] = None
        self._source_qimage: Optional[QImage] = None

    @property
    def is_autotile(self) -> bool:
        return True

    def get_half_tile_size(self) -> int:
        return self.tile_size // 2

    def load_source_image(self, asset_manager: Optional[Any] = None) -> Optional[QImage]:
        if self._source_qimage and not self._source_qimage.isNull():
            return self._source_qimage

        if self.source_image_path and os.path.exists(self.source_image_path):
            img = QImage(self.source_image_path)
            if not img.isNull():
                if self.source_rect:
                    rx, ry, rw, rh = self.source_rect
                    img = img.copy(rx, ry, rw, rh)
                self._source_qimage = img
                return img

        if self.source_asset_id and asset_manager:
            pm = asset_manager.get_pixmap(self.source_asset_id)
            if pm and not pm.isNull():
                sheet = pm.toImage()
                src_img, fmt, _ = synthesize_from_tileset_context(
                    sheet, self.source_col, self.source_row, self.tile_size,
                    mode=self.generation_mode,
                    edge_style=self.edge_style,
                    w_tiles=self.source_w_tiles,
                    h_tiles=self.source_h_tiles,
                )
                self.format = fmt
                self._source_qimage = src_img
                return src_img

        return None

    def set_source_qimage(self, img: QImage) -> None:
        self._source_qimage = img
        self.rebuild_atlas()

    # --------------------------------------------------------------------------
    # SYNTHESIS & ATLAS GENERATION
    # --------------------------------------------------------------------------
    def rebuild_atlas(self, asset_manager: Optional[Any] = None) -> bool:
        """
        Synthesizes all 47 seamless full-tile combinations from the source
        autotile fragments into a single fast composite atlas.
        """
        src = self.load_source_image(asset_manager)
        if not src or src.isNull():
            return False

        ts = self.tile_size
        ht = self.get_half_tile_size()

        # Atlas grid: 8 columns x 6 rows of full tiles (48 tiles total)
        cols = 8
        rows = 6
        atlas = QImage(cols * ts, rows * ts, QImage.Format.Format_ARGB32)
        atlas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(atlas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Select sub-tile mapping table
        if self.format == AutotileFormat.VX_ACE_2X3:
            sub_map = SUBTILES_VX_ACE
        elif self.format == AutotileFormat.XP_3X4:
            sub_map = SUBTILES_XP
        else:
            sub_map = SUBTILES_SIMPLE_3X3

        # Generate each of the 47 canonical tiles
        for idx, mask in enumerate(CANONICAL_47_MASKS):
            tx = (idx % cols) * ts
            ty = (idx // cols) * ts
            states = mask_to_quadrant_states(mask)

            # Paste 4 quarter-tiles
            quad_offsets = [
                (0, 0),       # TL
                (ht, 0),      # TR
                (0, ht),      # BL
                (ht, ht),     # BR
            ]

            for q_idx in range(4):
                state = states[q_idx]
                hx, hy = sub_map[q_idx].get(state, (0, 0))
                src_rect = QRect(hx * ht, hy * ht, ht, ht)
                dest_x = tx + quad_offsets[q_idx][0]
                dest_y = ty + quad_offsets[q_idx][1]
                painter.drawImage(dest_x, dest_y, src, src_rect.x(), src_rect.y(), ht, ht)

        # Slot 47 (last slot at bottom-right, (7, 5)): Representative / Preview tile!
        # In VX/Ace and XP, top-left 1x1 full tile of source is the designated preview tile!
        preview_dest_x = 7 * ts
        preview_dest_y = 5 * ts
        painter.drawImage(preview_dest_x, preview_dest_y, src, 0, 0, ts, ts)

        painter.end()

        self._atlas_image = atlas
        self._atlas_pixmap = QPixmap.fromImage(atlas)

        # Extract representative 1x1 preview tile
        prev_img = src.copy(0, 0, ts, ts)
        self._preview_pixmap = QPixmap.fromImage(prev_img)

        return True

    def get_preview_pixmap(
        self, size: Optional[int] = None, asset_manager: Optional[Any] = None
    ) -> QPixmap:
        """Returns the representative 1x1 thumbnail of this Autotile for the palette."""
        if not self._preview_pixmap or self._preview_pixmap.isNull():
            self.rebuild_atlas(asset_manager)

        if self._preview_pixmap and not self._preview_pixmap.isNull():
            if size and size != self.tile_size:
                return self._preview_pixmap.scaled(
                    size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            return self._preview_pixmap

        # Fallback
        pm = QPixmap(size or self.tile_size, size or self.tile_size)
        pm.fill(QColor("#2563eb"))
        return pm

    def get_tile_slice_for_mask(
        self, mask: int, col: int = 0, row: int = 0
    ) -> Tuple[int, int, int, int]:
        """
        Returns (source_x, source_y, tile_w, tile_h) on the composite atlas for the given mask.
        Supports deterministic center variant selection if configured.
        """
        c_mask = canonicalize_blob_mask(mask)
        idx = MASK_TO_CANONICAL_INDEX.get(c_mask, 0)
        ts = self.tile_size
        cols = 8

        # If solid center (mask 255) and center variants are configured, apply deterministic variant
        if c_mask == 255 and self.center_variants:
            candidates = [(1.0, idx), *[(v["weight"], v["idx"]) for v in self.center_variants]]
            total_w = sum(w for w, _ in candidates)
            h = deterministic_cell_hash(self.seed, col, row)
            target = (h % 1000000) / 1000000.0 * total_w
            accum = 0.0
            for w, variant_idx in candidates:
                accum += w
                if accum >= target:
                    idx = variant_idx
                    break

        sx = (idx % cols) * ts
        sy = (idx // cols) * ts
        return (sx, sy, ts, ts)

    @property
    def atlas_pixmap(self) -> QPixmap:
        return self.get_atlas_pixmap()

    def get_atlas_pixmap(self, asset_manager: Optional[Any] = None) -> QPixmap:
        if not self._atlas_pixmap or self._atlas_pixmap.isNull():
            self.rebuild_atlas(asset_manager)
        return self._atlas_pixmap or QPixmap()

    def has_valid_atlas(self, asset_manager: Optional[Any] = None) -> bool:
        pm = self.get_atlas_pixmap(asset_manager)
        if not pm or pm.isNull():
            return False
        return pm.width() >= 8 * self.tile_size and pm.height() >= 6 * self.tile_size

    def add_custom_variant(self, variant: CustomPathVariant) -> None:
        self.custom_variants.append(variant)

    def remove_custom_variant(self, variant_id: str) -> None:
        self.custom_variants = [v for v in self.custom_variants if v.id != variant_id]

    def get_matching_custom_variant(
        self, mask: int, col: int = 0, row: int = 0
    ) -> Optional[CustomPathVariant]:
        """
        Finds the highest-priority CustomPathVariant matching the canonical mask.
        If multiple variants share the highest priority, chooses deterministically
        using weighted random selection seeded by (self.seed, col, row).
        """
        if not self.custom_variants:
            return None
        c_mask = canonicalize_blob_mask(mask)
        matches = [v for v in self.custom_variants if v.mask == c_mask]
        if not matches:
            return None
        max_prio = max(v.priority for v in matches)
        top = [v for v in matches if v.priority == max_prio]
        if len(top) == 1:
            return top[0]
        total_w = sum(v.weight for v in top)
        h = deterministic_cell_hash(self.seed, col, row, salt=1337)
        target = (h % 1000000) / 1000000.0 * total_w
        accum = 0.0
        for v in top:
            accum += v.weight
            if accum >= target:
                return v
        return top[-1]

    # --------------------------------------------------------------------------
    # SERIALIZATION
    # --------------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "terrain_type": self.terrain_type,
            "format": self.format.value,
            "tile_size": self.tile_size,
            "source_image_path": self.source_image_path,
            "source_asset_id": self.source_asset_id,
            "source_rect": list(self.source_rect) if self.source_rect else None,
            "seed": self.seed,
            "source_col": self.source_col,
            "source_row": self.source_row,
            "source_w_tiles": self.source_w_tiles,
            "source_h_tiles": self.source_h_tiles,
            "generation_mode": self.generation_mode,
            "edge_style": self.edge_style,
            "archived": self.archived,
            "center_variants": self.center_variants,
            "custom_variants": [v.to_dict() for v in self.custom_variants],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RPGAutotile":
        autotile = cls(
            name=data.get("name", "Autotile"),
            terrain_type=data.get("terrain_type", "Ground"),
            autotile_format=AutotileFormat(data.get("format", AutotileFormat.VX_ACE_2X3.value)),
            tile_size=int(data.get("tile_size", 32)),
            autotile_id=data.get("id"),
            source_image_path=data.get("source_image_path"),
            source_asset_id=data.get("source_asset_id"),
            source_rect=tuple(data["source_rect"]) if data.get("source_rect") else None,
            seed=int(data.get("seed", 42)),
            source_col=int(data.get("source_col", 0)),
            source_row=int(data.get("source_row", 0)),
            source_w_tiles=int(data.get("source_w_tiles", 1)),
            source_h_tiles=int(data.get("source_h_tiles", 1)),
            generation_mode=data.get("generation_mode", "auto"),
            edge_style=data.get("edge_style", "organic"),
            archived=bool(data.get("archived", False)),
        )
        autotile.center_variants = list(data.get("center_variants", []))
        autotile.custom_variants = [
            CustomPathVariant.from_dict(v) for v in data.get("custom_variants", [])
        ]
        return autotile


def create_rpg_autotile_from_tile(
    name: str,
    source_asset_id: str,
    sheet: QImage,
    col: int,
    row: int,
    tile_size: int = 32,
    mode: str = "auto",
    edge_style: str = "organic",
    terrain_type: str = "path",
    seed: int = 42,
    w_tiles: int = 1,
    h_tiles: int = 1,
) -> RPGAutotile:
    """
    Factory creating a ready-to-paint RPGAutotile from a selected tile or WxH region
    in an existing tileset.
    """
    src_img, fmt, desc = synthesize_from_tileset_context(
        sheet, col, row, tile_size, mode=mode, edge_style=edge_style,
        w_tiles=w_tiles, h_tiles=h_tiles,
    )
    ts = max(8, int(tile_size))
    autotile = RPGAutotile(
        name=name,
        terrain_type=terrain_type,
        autotile_format=fmt,
        tile_size=ts,
        source_asset_id=source_asset_id,
        source_rect=(col * ts, row * ts, w_tiles * ts, h_tiles * ts),
        seed=seed,
        source_col=col,
        source_row=row,
        source_w_tiles=w_tiles,
        source_h_tiles=h_tiles,
        generation_mode=mode,
        edge_style=edge_style,
    )
    autotile.set_source_qimage(src_img)
    return autotile


# ==============================================================================
# SELECTED AUTOTILE PALETTE WRAPPER
# ==============================================================================
class SelectedAutotile:
    """
    Palette selection object representing a chosen RPG Maker Autotile.
    When this is selected, the Brush tool paints with this autotile.
    """

    def __init__(self, autotile: RPGAutotile):
        self.autotile = autotile
        self.id = autotile.id
        self.name = autotile.name
        self.terrain_type = autotile.terrain_type
        self.tile_size = autotile.tile_size

    @property
    def is_autotile(self) -> bool:
        return True

    @property
    def asset_id(self) -> str:
        return self.autotile.id
