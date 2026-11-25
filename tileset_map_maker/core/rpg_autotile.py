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
from .paths.models import (
    EDGE_DIRECTIONS,
    OPPOSITE_EDGE,
    VARIANT_ROLES,
    EdgeSignature,
    CustomPathVariant,
    PathVariant,
)


class AutotileFormat(str, Enum):
    VX_ACE_2X3  = "vx_ace_2x3"   # Standard RPG Maker VX / VX Ace / MV / MZ ground autotile (2x3 full tiles = 4x6 half-tiles)
    XP_3X4      = "xp_3x4"       # RPG Maker XP autotile (3x4 full tiles = 6x8 half-tiles)
    WANG_47     = "wang_47"      # Pre-assembled 47-blob Wang tilesheet
    SIMPLE_3X3  = "simple_3x3"   # 3x3 tilesheet (9 full tiles)
    BLOCK_2X2   = "block_2x2"    # 2x2 tilesheet (4 full tiles: corners/edges/center)


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
                    cx = x if inner_corner_dir in ("tl", "bl") else (w - 1 - x)
                    cy = y if inner_corner_dir in ("tl", "tr") else (h - 1 - y)
                    ic_radial = (cx * cx + cy * cy) ** 0.5
                    if edge_style == "organic":
                        # Match exact straight-edge organic_depth so intersection never pinches
                        if ic_radial < organic_depth:
                            img.setPixel(px, py, 0)
                    elif edge_style == "alpha_fade":
                        if ic_radial < 1.0:
                            fade_a = int(orig_a * 0.25)
                            img.setPixel(px, py, (fade_a << 24) | (orig & 0x00FFFFFF))
                        elif ic_radial < 2.0:
                            fade_a = int(orig_a * 0.65)
                            img.setPixel(px, py, (fade_a << 24) | (orig & 0x00FFFFFF))
                    elif edge_style == "dark_outline":
                        if cx == 0 and cy == 0:
                            img.setPixel(px, py, (orig_a << 24) | (shadow_r << 16) | (shadow_g << 8) | shadow_b)
                    else:
                        if ic_radial < organic_depth:
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


def extract_packed_tileset_image(
    sheet: QImage,
    tileset_config: Optional[Any] = None,
) -> Tuple[QImage, int, int]:
    """
    Returns a tightly packed 1:1 tileset QImage respecting TilesetConfig
    (tile_width, tile_height, margin_x/y, spacing_x/y, start_x/y) without
    scaling or blurring any original pixels. When margin/spacing/start are all 0,
    returns the original sheet directly with zero copy overhead.
    """
    if tileset_config is None:
        return sheet, 32, 32
    tw = max(8, int(getattr(tileset_config, "tile_width", 32)))
    th = max(8, int(getattr(tileset_config, "tile_height", tw)))
    mx = max(0, int(getattr(tileset_config, "margin_x", 0)))
    my = max(0, int(getattr(tileset_config, "margin_y", 0)))
    sx = max(0, int(getattr(tileset_config, "spacing_x", 0)))
    sy = max(0, int(getattr(tileset_config, "spacing_y", 0)))
    ox = max(0, int(getattr(tileset_config, "start_x", 0)))
    oy = max(0, int(getattr(tileset_config, "start_y", 0)))
    if mx == 0 and my == 0 and sx == 0 and sy == 0 and ox == 0 and oy == 0:
        return sheet, tw, th

    grid = tileset_config.compute_grid(sheet.width(), sheet.height())
    cols = max(0, int(grid.get("cols", 0)))
    rows = max(0, int(grid.get("rows", 0)))
    if cols <= 0 or rows <= 0:
        return sheet, tw, th

    packed = QImage(cols * tw, rows * th, QImage.Format.Format_ARGB32)
    packed.fill(QColor(0, 0, 0, 0))
    painter = QPainter(packed)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    for r in range(rows):
        for c in range(cols):
            rx, ry, rw, rh = tileset_config.get_tile_rect(c, r)
            painter.drawImage(c * tw, r * th, sheet, rx, ry, rw, rh)
    painter.end()
    return packed, tw, th


def _median_rgb(pixels: List[int]) -> Tuple[int, int, int]:
    if not pixels:
        return (128, 128, 128)
    rs = sorted((p >> 16) & 0xFF for p in pixels)
    gs = sorted((p >> 8) & 0xFF for p in pixels)
    bs = sorted(p & 0xFF for p in pixels)
    mid = len(rs) // 2
    return (rs[mid], gs[mid], bs[mid])


def _analyze_patch_materials(patch_3x3: QImage, ts: int) -> Dict[str, Any]:
    """
    Two-prototype material classifier for a 3x3 autotile block.
    Samples BOTH the inner core material (from center tile or immediate inner ring)
    and the outer rim material (from the outermost 2px of the 4 cardinal edge tiles).
    Accurately separates outer border pixels from interior highlights/tufts and outlines.
    """
    pw, ph = patch_3x3.width(), patch_3x3.height()
    center_px: List[int] = []
    for y in range(ts, min(2 * ts, ph)):
        for x in range(ts, min(2 * ts, pw)):
            p = patch_3x3.pixel(x, y)
            if ((p >> 24) & 0xFF) > 180:
                center_px.append(p)

    center_opaque_ratio = len(center_px) / float(max(1, ts * ts))
    if center_opaque_ratio >= 0.5:
        cr, cg, cb = _median_rgb(center_px)
    else:
        ring_px: List[int] = []
        for k in range(ts):
            for sx, sy in (
                (ts + k, ts - 1),
                (ts + k, 2 * ts),
                (ts - 1, ts + k),
                (2 * ts, ts + k),
            ):
                if 0 <= sx < pw and 0 <= sy < ph:
                    p = patch_3x3.pixel(sx, sy)
                    if ((p >> 24) & 0xFF) > 180:
                        ring_px.append(p)
        cr, cg, cb = _median_rgb(ring_px) if ring_px else (128, 128, 128)

    center_luma = 0.299 * cr + 0.587 * cg + 0.114 * cb

    outer_total = 0
    outer_opaque: List[int] = []
    for k in range(ts):
        for sx, sy in (
            (ts + k, 0),
            (ts + k, 1),
            (ts + k, 3 * ts - 1),
            (ts + k, 3 * ts - 2),
            (0, ts + k),
            (1, ts + k),
            (3 * ts - 1, ts + k),
            (3 * ts - 2, ts + k),
        ):
            if 0 <= sx < pw and 0 <= sy < ph:
                outer_total += 1
                p = patch_3x3.pixel(sx, sy)
                if ((p >> 24) & 0xFF) > 20:
                    outer_opaque.append(p)

    outer_is_transparent = len(outer_opaque) < outer_total * 0.5
    if outer_is_transparent:
        orr, org, orb = 0, 0, 0
        contrast = 1.0
    else:
        orr, org, orb = _median_rgb(outer_opaque)
        contrast = (abs(orr - cr) + abs(org - cg) + abs(orb - cb)) / (3.0 * 255.0)

    in_mean = (cr + cg + cb) / 3.0
    in_c = (cr - in_mean, cg - in_mean, cb - in_mean)
    in_chroma_mag = (abs(in_c[0]) + abs(in_c[1]) + abs(in_c[2])) / (3.0 * 255.0)
    out_mean = (orr + org + orb) / 3.0
    out_c = (orr - out_mean, org - out_mean, orb - out_mean)
    chroma_contrast = (
        abs(out_c[0] - in_c[0]) + abs(out_c[1] - in_c[1]) + abs(out_c[2] - in_c[2])
    ) / (3.0 * 255.0)

    def _chroma_dist(pixel: int, ref_c: Tuple[float, float, float]) -> float:
        r = (pixel >> 16) & 0xFF
        g = (pixel >> 8) & 0xFF
        b = pixel & 0xFF
        m = (r + g + b) / 3.0
        return (abs((r - m) - ref_c[0]) + abs((g - m) - ref_c[1]) + abs((b - m) - ref_c[2])) / (3.0 * 255.0)

    def is_outer(pixel: int) -> bool:
        a = (pixel >> 24) & 0xFF
        if outer_is_transparent:
            return a <= 20
        if a <= 20:
            return True
        if contrast < 0.08:
            return _pixel_dist_from_rgb(pixel, cr, cg, cb) > 0.08
        d_out = _pixel_dist_from_rgb(pixel, orr, org, orb)
        d_in = _pixel_dist_from_rgb(pixel, cr, cg, cb)
        if d_out < d_in * 0.85 and d_out < max(0.22, contrast * 0.65):
            return True
        # Catch shadowed/highlighted outer material (e.g. dark brown dirt shadow) via chroma
        if chroma_contrast >= 0.06:
            cd_out = _chroma_dist(pixel, out_c)
            cd_in = _chroma_dist(pixel, in_c)
            if cd_out < cd_in * 0.65 and cd_out < max(0.08, chroma_contrast * 0.50):
                return True
        return False

    def is_dark_outline(pixel: int) -> bool:
        if ((pixel >> 24) & 0xFF) <= 180:
            return False
        luma = (
            0.299 * ((pixel >> 16) & 0xFF)
            + 0.587 * ((pixel >> 8) & 0xFF)
            + 0.114 * (pixel & 0xFF)
        )
        return luma < center_luma * 0.70

    def is_pure_interior(pixel: int) -> bool:
        if ((pixel >> 24) & 0xFF) <= 180:
            return False
        if is_outer(pixel) or is_dark_outline(pixel):
            return False
        if contrast < 0.08:
            return _pixel_dist_from_rgb(pixel, cr, cg, cb) <= 0.14
        # Reject intermediate multi-layer bank/cliff/curb materials (e.g. brown cliff between grass and water!)
        if _pixel_dist_from_rgb(pixel, cr, cg, cb) > 0.22:
            return False
        if in_chroma_mag >= 0.04 and _chroma_dist(pixel, in_c) > 0.11:
            return False
        return True

    return {
        "cr": cr,
        "cg": cg,
        "cb": cb,
        "center_luma": center_luma,
        "center_opaque_ratio": center_opaque_ratio,
        "outer_is_transparent": outer_is_transparent,
        "orr": orr,
        "org": org,
        "orb": orb,
        "contrast": contrast,
        "is_outer": is_outer,
        "is_dark_outline": is_dark_outline,
        "is_pure_interior": is_pure_interior,
    }


def _tile_texture_activity(
    img: QImage,
    cr: int,
    cg: int,
    cb: int,
    x0: int = 0,
    y0: int = 0,
    w: Optional[int] = None,
    h: Optional[int] = None,
) -> float:
    """Measures mean pixel color variation relative to median interior color."""
    rw = min(img.width() - x0, w if w is not None else img.width())
    rh = min(img.height() - y0, h if h is not None else img.height())
    if rw <= 0 or rh <= 0:
        return 0.0
    diff_sum = 0.0
    cnt = 0
    for y in range(y0, y0 + rh):
        for x in range(x0, x0 + rw):
            p = img.pixel(x, y)
            if ((p >> 24) & 0xFF) > 180:
                diff_sum += _pixel_dist_from_rgb(p, cr, cg, cb)
                cnt += 1
    return diff_sum / float(max(1, cnt))


def _measure_bank_depth(
    strip: QImage, is_inner_fn: Any, axis: str, from_start: bool
) -> int:
    """
    Measures median full bank/rim depth (outer background + any intermediate cliff,
    curb, or dark outline) from one edge until pixels reach the navigable inner surface.
    """
    return _measure_outer_rim(strip, lambda px: not is_inner_fn(px), axis, from_start)


def _measure_outer_rim(
    strip: QImage, is_outer_fn: Any, axis: str, from_start: bool
) -> int:
    """
    Measures median outer-material rim thickness (in pixels) from one edge of a
    tile or half-tile using the two-prototype outer-material classifier.
    """
    w, h = strip.width(), strip.height()
    limit = w if axis == "x" else h
    span = h if axis == "x" else w
    if limit <= 0 or span <= 0:
        return 0
    depths: List[int] = []
    for u in range(span):
        depth = 0
        for step in range(limit):
            if axis == "x":
                x = step if from_start else (w - 1 - step)
                y = u
            else:
                x = u
                y = step if from_start else (h - 1 - step)
            if is_outer_fn(strip.pixel(x, y)):
                depth = step + 1
            else:
                break
        depths.append(depth)
    depths.sort()
    return depths[len(depths) // 2]


def _find_companion_inner_corners(
    sheet: QImage,
    tl_col: int,
    tl_row: int,
    ts: int,
    mat: Dict[str, Any],
) -> Optional[QImage]:
    """
    Universally detects an artist-drawn 2x2 inner-corner companion block adjacent
    to a 3x3 terrain block (below, to the right, or above — e.g. LPC and custom
    sheets). Validated strictly by pixel material signature:
    - Outer perimeter of the 2x2 matches the 3x3 INNER material
    - Central junction around (ts, ts) matches the 3x3 OUTER material
    - All 4 quadrants contain both outer material near (ts, ts) and inner material away from it
    """
    if mat["contrast"] < 0.08:
        return None
    cr, cg, cb = mat["cr"], mat["cg"], mat["cb"]
    is_outer = mat["is_outer"]
    inner_tol = max(0.11, mat["contrast"] * 0.45)

    sw, sh = sheet.width(), sheet.height()
    candidates = (
        (tl_col, tl_row + 3),
        (tl_col + 3, tl_row),
        (tl_col, tl_row - 2),
        (tl_col + 1, tl_row + 3),
        (tl_col + 3, tl_row + 1),
    )

    for ic_col, ic_row in candidates:
        px_x = ic_col * ts
        px_y = ic_row * ts
        if px_x < 0 or px_y < 0 or px_x + 2 * ts > sw or px_y + 2 * ts > sh:
            continue
        cand = sheet.copy(px_x, px_y, 2 * ts, 2 * ts)

        # 1. Check outer perimeter matches inner material
        perim_pts = []
        step = max(2, ts // 4)
        for k in range(2, 2 * ts - 2, step):
            perim_pts.append((k, 1))
            perim_pts.append((k, 2 * ts - 2))
            perim_pts.append((1, k))
            perim_pts.append((2 * ts - 2, k))
        perim_ok = 0
        for x, y in perim_pts:
            p = cand.pixel(x, y)
            if (
                ((p >> 24) & 0xFF) > 180
                and not is_outer(p)
                and _pixel_dist_from_rgb(p, cr, cg, cb) <= inner_tol
            ):
                perim_ok += 1
        if perim_ok < len(perim_pts) * 0.80:
            continue

        # 2. Check central junction (ts-2..ts+1, ts-2..ts+1) matches outer material
        center_ok = 0
        center_tot = 0
        for dy in range(-2, 2):
            for dx in range(-2, 2):
                center_tot += 1
                if is_outer(cand.pixel(ts + dx, ts + dy)):
                    center_ok += 1
        if center_ok < center_tot * 0.80:
            continue

        # 3. Verify outer-material cutout extends reasonably in all 4 cardinal directions from (ts, ts)
        cardinal_radii = []
        for dx_dir, dy_dir in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rad = 0
            for d in range(1, ts):
                sx = ts + dx_dir * d - (1 if dx_dir < 0 else 0)
                sy = ts + dy_dir * d - (1 if dy_dir < 0 else 0)
                if is_outer(cand.pixel(sx, sy)):
                    rad = d
                else:
                    break
            cardinal_radii.append(rad)
        if min(cardinal_radii) < 2 or max(cardinal_radii) >= ts - 2:
            continue

        return cand

    return None


def _synthesize_interior_fill_from_ring(
    patch: QImage,
    ts: int,
    mat: Optional[Dict[str, Any]] = None,
    st: int = 0,
    sb: int = 0,
    target_rim: Optional[int] = None,
) -> QImage:
    """
    Reconstructs a clean, seamless ts x ts interior tile for a 3x3 ring whose
    center has a transparent gap. Uses ONLY original pixels (zero blurring or
    interpolation) from the pure interior rows bordering the shifted arm strips
    so the center texture matches the incoming arms continuously without
    chopped half-features or dead flat bands.
    """
    fill = QImage(ts, ts, QImage.Format.Format_ARGB32)
    pw, ph = patch.width(), patch.height()
    ht = ts // 2
    cx = (pw - ts) // 2
    cy = (ph - ts) // 2

    if mat is None:
        mat = _analyze_patch_materials(patch, ts)
    cr, cg, cb = mat["cr"], mat["cg"], mat["cb"]
    is_pure_inner = mat["is_pure_interior"]
    fallback_pixel = QColor(cr, cg, cb, 255).rgba()

    def _row_is_pure(sy: int) -> bool:
        if not (0 <= sy < ph):
            return False
        pure = 0
        for x in range(ts):
            if is_pure_inner(patch.pixel(cx + x, sy)):
                pure += 1
        return pure >= ts

    def _row_texture_activity(sy: int) -> float:
        diff_sum = 0.0
        for x in range(ts):
            diff_sum += _pixel_dist_from_rgb(patch.pixel(cx + x, sy), cr, cg, cb)
        return diff_sum / float(max(1, ts))

    t_rim = target_rim if target_rim is not None else max(3, int(round(ht * 0.40)))
    top_start = max(0, st + t_rim - 1)
    bot_end = min(ph, 3 * ts - sb - t_rim + 1)

    # Collect contiguous pure interior rows on Top and Bottom (zero outer/cliff/outline pixels)
    top_clean: List[int] = []
    for sy in range(cy - 1, top_start - 1, -1):
        if _row_is_pure(sy):
            top_clean.append(sy)
        else:
            break
    top_clean.reverse()

    bot_clean: List[int] = []
    for sy in range(cy + ts, bot_end):
        if _row_is_pure(sy):
            bot_clean.append(sy)
        else:
            break

    # Align to the texture zone actually visible at the inner edges of q_top / q_bot
    arm_top_edge = min(cy - 1, st + ht - 1)
    arm_bot_edge = max(cy + ts, 3 * ts - ht - sb)
    top_near = [sy for sy in top_clean if sy <= arm_top_edge + 2]
    bot_near = [sy for sy in bot_clean if sy >= arm_bot_edge - 2]

    def _filter_textured_rows(rows: List[int]) -> List[int]:
        if len(rows) <= 4:
            return rows
        acts = [_row_texture_activity(r) for r in rows]
        max_a = max(acts)
        if max_a < 0.015:
            return rows
        active = [r for r, a in zip(rows, acts) if a >= max_a * 0.25]
        return active if len(active) >= 4 else rows

    top_f = _filter_textured_rows(top_near) if top_near else _filter_textured_rows(top_clean)
    bot_f = _filter_textured_rows(bot_near) if bot_near else _filter_textured_rows(bot_clean)

    # Pick the single cleanest coherent band (prevents mosaicing disparate sides!)
    if top_f and bot_f:
        top_act = sum(_row_texture_activity(sy) for sy in top_f) / len(top_f)
        bot_act = sum(_row_texture_activity(sy) for sy in bot_f) / len(bot_f)
        if len(top_f) >= len(bot_f) and top_act >= bot_act * 0.85:
            band = top_f
        elif len(bot_f) > len(top_f) + 1:
            band = bot_f
        else:
            band = top_f if top_act >= bot_act else bot_f
    elif top_f:
        band = top_f
    elif bot_f:
        band = bot_f
    else:
        band = top_clean if len(top_clean) >= len(bot_clean) else bot_clean

    # Check if band has real pixel-art texture variation (stagger x-shift per cycle only when textured!)
    is_textured = bool(band) and (
        sum(_row_texture_activity(sy) for sy in band) / len(band) > 0.015
    )

    n_b = len(band)
    for y in range(ts):
        cycle = (y // n_b) if n_b > 0 else 0
        x_shift = ((cycle * ht) % ts) if is_textured else 0
        for x in range(ts):
            chosen: Optional[int] = None
            if n_b > 0:
                sy = band[y % n_b]
                cand = patch.pixel(cx + ((x + x_shift) % ts), sy)
                if is_pure_inner(cand):
                    chosen = cand

            if chosen is None:
                for sx, sy in (
                    (cx + x, cy - 1),
                    (cx + x, cy + ts),
                    (cx - 1, cy + y),
                    (cx + ts, cy + y),
                ):
                    if 0 <= sx < pw and 0 <= sy < ph:
                        cand = patch.pixel(sx, sy)
                        if is_pure_inner(cand):
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
    return _measure_outer_rim(
        strip,
        lambda px: _pixel_dist_from_rgb(px, cr, cg, cb) > thresh,
        axis,
        from_start,
    )


def _rgba_dist(p1: int, p2: int) -> float:
    """Alpha-aware normalized pixel distance (0.0 for transparent==transparent)."""
    a1 = (p1 >> 24) & 0xFF
    a2 = (p2 >> 24) & 0xFF
    if a1 <= 20 and a2 <= 20:
        return 0.0
    if (a1 <= 20) != (a2 <= 20):
        return 1.0
    r1, g1, b1 = (p1 >> 16) & 0xFF, (p1 >> 8) & 0xFF, p1 & 0xFF
    r2, g2, b2 = (p2 >> 16) & 0xFF, (p2 >> 8) & 0xFF, p2 & 0xFF
    return (abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)) / (3.0 * 255.0)


def _choose_balanced_strip_phase(
    tile_a: QImage,
    tile_b: QImage,
    is_inner: Any,
    axis: str,
    shift_a: int,
    shift_b: int,
    ts: int,
) -> int:
    """
    For a periodic, symmetric 3x3 edge strip pair (top+bottom for axis='h',
    left+right for axis='v'), selects a cyclic pixel phase offset in [0..ts-1]
    so that BOTH tile boundaries (pixel 0 meeting the center's right/bottom edge
    and pixel ts-1 meeting the center's left/top edge) preserve the strip's true
    median navigable surface width without landing on an asymmetric deep notch.

    Strictly preserves phase 0 when:
    - the strip is non-periodic (wrap seam error > 0.16), OR
    - the source strip is intentionally asymmetric (|half0_avg - half1_avg| > 3px), OR
    - phase 0 is already balanced and unpinched.
    Uses ONLY original unmodified pixels (zero scaling, stretching, or blurring).
    """
    ht = ts // 2
    if axis == "h":
        err_a = sum(
            _rgba_dist(tile_a.pixel(0, shift_a + y), tile_a.pixel(ts - 1, shift_a + y))
            for y in range(ht)
        ) / float(max(1, ht))
        err_b = sum(
            _rgba_dist(
                tile_b.pixel(0, ts - ht - shift_b + y),
                tile_b.pixel(ts - 1, ts - ht - shift_b + y),
            )
            for y in range(ht)
        ) / float(max(1, ht))
        wrap_err = 0.5 * (err_a + err_b)

        prof: List[Tuple[int, int, int]] = []
        for x in range(ts):
            da = next((y for y in range(ht) if is_inner(tile_a.pixel(x, shift_a + y))), ht)
            db = next(
                (y for y in range(ht) if is_inner(tile_b.pixel(x, ts - 1 - shift_b - y))),
                ht,
            )
            prof.append((da, db, ts - da - db))
    else:
        err_a = sum(
            _rgba_dist(tile_a.pixel(shift_a + x, 0), tile_a.pixel(shift_a + x, ts - 1))
            for x in range(ht)
        ) / float(max(1, ht))
        err_b = sum(
            _rgba_dist(
                tile_b.pixel(ts - ht - shift_b + x, 0),
                tile_b.pixel(ts - ht - shift_b + x, ts - 1),
            )
            for x in range(ht)
        ) / float(max(1, ht))
        wrap_err = 0.5 * (err_a + err_b)

        prof = []
        for y in range(ts):
            da = next((x for x in range(ht) if is_inner(tile_a.pixel(shift_a + x, y))), ht)
            db = next(
                (x for x in range(ht) if is_inner(tile_b.pixel(ts - 1 - shift_b - x, y))),
                ht,
            )
            prof.append((da, db, ts - da - db))

    med_w = sorted(w for _, _, w in prof)[ts // 2]
    half0_avg = sum(w for _, _, w in prof[:ht]) / float(max(1, ht))
    half1_avg = sum(w for _, _, w in prof[ht:]) / float(max(1, ts - ht))

    # Never alter non-periodic or intentionally asymmetric/tapered tilesets
    if wrap_err > 0.16 or abs(half0_avg - half1_avg) > 3.0 or med_w <= 4 or med_w >= ts - 1:
        return 0

    def _eval_phase(ph: int) -> Tuple[float, int, float, float]:
        w_r0 = prof[ph % ts][2]
        w_r1 = prof[(ph + 1) % ts][2]
        w_r2 = prof[(ph + 2) % ts][2]
        w_l0 = prof[(ph - 1) % ts][2]
        w_l1 = prof[(ph - 2) % ts][2]
        w_l2 = prof[(ph - 3) % ts][2]
        band_r = (w_r0 + w_r1 + w_r2) / 3.0
        band_l = (w_l0 + w_l1 + w_l2) / 3.0
        min_edge = min(w_r0, w_r1, w_l0, w_l1)
        pinch = (
            max(0.0, med_w - min_edge) * 2.5
            + max(0.0, med_w - min(band_r, band_l)) * 3.0
        )
        overshoot = (
            max(0.0, max(w_r0, w_l0) - (med_w + 3)) * 1.2
            + max(0.0, max(band_r, band_l) - (med_w + 2.5)) * 1.5
        )
        asym = (
            abs(band_r - band_l) * 1.5
            + abs(w_r0 - w_l0) * 0.8
            + abs(w_r1 - w_l1) * 0.4
        )
        da_r, db_r, _ = prof[ph % ts]
        da_l, db_l, _ = prof[(ph - 1) % ts]
        bank_skew = abs(da_r - da_l) * 0.4 + abs(db_r - db_l) * 0.4
        return pinch + overshoot + asym + bank_skew, min_edge, band_l, band_r

    sc0, mn0, bl0, br0 = _eval_phase(0)
    if mn0 >= med_w - 1 and abs(bl0 - br0) <= 1.5:
        return 0

    best_sc, best_ph = sc0, 0
    for ph in range(1, ts):
        sc, _, _, _ = _eval_phase(ph)
        if sc + 0.05 < best_sc:
            best_sc, best_ph = sc, ph
    return best_ph


def _copy_cyclic_strip(
    tile: QImage, x_start: int, y_start: int, w: int, h: int, axis: str, ts: int
) -> QImage:
    """Copies a (w x h) half-tile wrapping cyclically along 'h' (x) or 'v' (y)."""
    if (axis == "h" and x_start % ts == 0 and x_start + w <= ts) or (
        axis == "v" and y_start % ts == 0 and y_start + h <= ts
    ):
        return tile.copy(x_start % ts, y_start % ts, w, h)
    out = QImage(w, h, QImage.Format.Format_ARGB32)
    if axis == "h":
        for y in range(h):
            for x in range(w):
                out.setPixel(x, y, tile.pixel((x_start + x) % ts, y_start + y))
    else:
        for y in range(h):
            for x in range(w):
                out.setPixel(x, y, tile.pixel(x_start + x, (y_start + y) % ts))
    return out


def _evaluate_crossroad_coherence(
    inner_quads: List[QImage],
    q_top_l: QImage,
    q_top_r: QImage,
    q_bot_l: QImage,
    q_bot_r: QImage,
    q_left_t: QImage,
    q_left_b: QImage,
    q_right_t: QImage,
    q_right_b: QImage,
    is_inner: Any,
    ts: int,
) -> Dict[str, Any]:
    """
    Evaluates the ENTIRE 4-way crossroad (Left, Right, Top, Bottom arms + Center)
    simultaneously as ONE logical composition. Measures actual visible navigable
    surface width on both sides of all 4 junctions, contour step alignment across
    each seam, total pinch deficit, and opposite-arm symmetry (only enforced when
    the source arms themselves are symmetric).
    """
    ht = ts // 2
    itl, itr, ibl, ibr = inner_quads

    def _col_span(top_q: QImage, bot_q: QImage, x: int) -> Tuple[int, int, int]:
        dt = next((y for y in range(ht) if is_inner(top_q.pixel(x, y))), ht)
        db = next((y for y in range(ht) if is_inner(bot_q.pixel(x, ht - 1 - y))), ht)
        return max(0, ts - dt - db), dt, db

    def _row_span(left_q: QImage, right_q: QImage, y: int) -> Tuple[int, int, int]:
        dl = next((x for x in range(ht) if is_inner(left_q.pixel(x, y))), ht)
        dr = next((x for x in range(ht) if is_inner(right_q.pixel(ht - 1 - x, y))), ht)
        return max(0, ts - dl - dr), dl, dr

    # Physical seams:
    # Left arm (q_top_r/q_bot_r @ x=ht-1) <-> Center left (itl/ibl @ x=0)
    # Center right (itr/ibr @ x=ht-1)     <-> Right arm (q_top_l/q_bot_l @ x=0)
    # Top arm (q_left_b/q_right_b @ y=ht-1) <-> Center top (itl/itr @ y=0)
    # Center bottom (ibl/ibr @ y=ht-1)    <-> Bottom arm (q_left_t/q_right_t @ y=0)
    c_l = _col_span(itl, ibl, 0)
    a_l = _col_span(q_top_r, q_bot_r, ht - 1)
    c_r = _col_span(itr, ibr, ht - 1)
    a_r = _col_span(q_top_l, q_bot_l, 0)
    c_t = _row_span(itl, itr, 0)
    a_t = _row_span(q_left_b, q_right_b, ht - 1)
    c_b = _row_span(ibl, ibr, ht - 1)
    a_b = _row_span(q_left_t, q_right_t, 0)

    # Also inspect 1px inside center on all 4 sides to catch immediate sub-seam narrowing
    c_l1 = _col_span(itl, ibl, min(1, ht - 1))
    c_r1 = _col_span(itr, ibr, max(0, ht - 2))
    c_t1 = _row_span(itl, itr, min(1, ht - 1))
    c_b1 = _row_span(ibl, ibr, max(0, ht - 2))

    steps = (
        abs(c_l[1] - a_l[1]) + abs(c_l[2] - a_l[2])
        + abs(c_r[1] - a_r[1]) + abs(c_r[2] - a_r[2])
        + abs(c_t[1] - a_t[1]) + abs(c_t[2] - a_t[2])
        + abs(c_b[1] - a_b[1]) + abs(c_b[2] - a_b[2])
    )
    pinch_l = max(0, a_l[0] - min(c_l[0], c_l1[0]))
    pinch_r = max(0, a_r[0] - min(c_r[0], c_r1[0]))
    pinch_t = max(0, a_t[0] - min(c_t[0], c_t1[0]))
    pinch_b = max(0, a_b[0] - min(c_b[0], c_b1[0]))
    max_single_pinch = max(pinch_l, pinch_r, pinch_t, pinch_b)
    total_pinch = pinch_l + pinch_r + pinch_t + pinch_b

    lr_asym = abs(c_l[0] - c_r[0])
    tb_asym = abs(c_t[0] - c_b[0])
    arm_lr_sym = abs(a_l[0] - a_r[0]) <= 2
    arm_tb_sym = abs(a_t[0] - a_b[0]) <= 2

    coherent = (
        max_single_pinch <= 2
        and total_pinch <= 3
        and steps <= 8
        and (not arm_lr_sym or lr_asym <= 2)
        and (not arm_tb_sym or tb_asym <= 2)
    )
    return {
        "c_l": c_l[0], "a_l": a_l[0],
        "c_r": c_r[0], "a_r": a_r[0],
        "c_t": c_t[0], "a_t": a_t[0],
        "c_b": c_b[0], "a_b": a_b[0],
        "steps": steps,
        "pinch_l": pinch_l, "pinch_r": pinch_r, "pinch_t": pinch_t, "pinch_b": pinch_b,
        "max_single_pinch": max_single_pinch,
        "total_pinch": total_pinch,
        "lr_asym": lr_asym, "tb_asym": tb_asym,
        "arm_lr_sym": arm_lr_sym, "arm_tb_sym": arm_tb_sym,
        "coherent": coherent,
    }


def synthesize_vx_ace_from_3x3(
    patch_3x3: QImage,
    tile_size: int = 32,
    companion_2x2: Optional[QImage] = None,
    rim_balance: float = 0.40,
) -> QImage:
    """
    Converts a 3x3 tilesheet block into a full RPG Maker VX Ace (2x3 tiles = 4x6 half-tiles)
    source image with:
    - Three-zone material classification (outer background / intermediate bank, cliff or outline /
      navigable inner surface) — handles grass+dirt, grass+transparent, AND multi-layer water+cliff+grass!
    - Equalized full bank depth AND balanced periodic seam phase across all 4 cardinal directions so
      horizontal and vertical arms keep consistent, symmetric surface widths without pinching on any arm
      (while preserving intentionally asymmetric or non-periodic tilesets untouched!)
    - Texture-continuity check on the center tile: synthesizes a crisp pixel-art interior from the
      arms both when the 3x3 center is transparent AND when an opaque center tile is flat/featureless
      compared to richly textured incoming arms
    - Whole-intersection inner-corner composition: matches every inner corner against its TRUE
      physically adjacent arm half-tile seam and validates ALL 4 arms (L, R, T, B) + center
      simultaneously via _evaluate_crossroad_coherence so 3 good sides + 1 pinched side is never accepted!
    """
    import math

    ts = max(8, int(tile_size))
    ht = ts // 2
    src = patch_3x3.copy()
    mat = _analyze_patch_materials(src, ts)
    is_inner = mat["is_pure_interior"]
    cr, cg, cb = mat["cr"], mat["cg"], mat["cb"]

    # Measure full bank/rim depth (outer + intermediate cliff/curb/outline) up to navigable inner surface
    top_tile = src.copy(ts, 0, ts, ts)
    bot_tile = src.copy(ts, 2 * ts, ts, ts)
    left_tile = src.copy(0, ts, ts, ts)
    right_tile = src.copy(2 * ts, ts, ts, ts)

    bank_t = _measure_bank_depth(top_tile, is_inner, "y", True)
    bank_b = _measure_bank_depth(bot_tile, is_inner, "y", False)
    bank_l = _measure_bank_depth(left_tile, is_inner, "x", True)
    bank_r = _measure_bank_depth(right_tile, is_inner, "x", False)

    # Target bank depth inside each half-tile (default ~40% of ht -> ~6px bank, ~20px uniform path width!)
    clamped_balance = max(0.18, min(0.65, float(rim_balance)))
    target_bank = max(3, int(round(ht * clamped_balance)))
    max_shift = max(0, ts - ht)

    def _calc_shift(bank_px: int) -> int:
        if target_bank < bank_px < ts - 2:
            return min(max_shift, bank_px - target_bank)
        return 0

    st = _calc_shift(bank_t)
    sb = _calc_shift(bank_b)
    sl = _calc_shift(bank_l)
    sr = _calc_shift(bank_r)

    # Extract shifted outer corner half-tiles
    q_tl = src.copy(sl, st, ht, ht)
    q_tr = src.copy(3 * ts - ht - sr, st, ht, ht)
    q_bl = src.copy(sl, 3 * ts - ht - sb, ht, ht)
    q_br = src.copy(3 * ts - ht - sr, 3 * ts - ht - sb, ht, ht)

    # Align periodic symmetric edge strips so neither seam boundary lands on a deep tuft pinch
    dx_h = _choose_balanced_strip_phase(top_tile, bot_tile, is_inner, "h", st, sb, ts)
    dy_v = _choose_balanced_strip_phase(left_tile, right_tile, is_inner, "v", sl, sr, ts)

    q_top_l = _copy_cyclic_strip(top_tile, dx_h, st, ht, ht, "h", ts)
    q_top_r = _copy_cyclic_strip(top_tile, dx_h + ht, st, ht, ht, "h", ts)
    q_bot_l = _copy_cyclic_strip(bot_tile, dx_h, ts - ht - sb, ht, ht, "h", ts)
    q_bot_r = _copy_cyclic_strip(bot_tile, dx_h + ht, ts - ht - sb, ht, ht, "h", ts)

    q_left_t = _copy_cyclic_strip(left_tile, sl, dy_v, ht, ht, "v", ts)
    q_left_b = _copy_cyclic_strip(left_tile, sl, dy_v + ht, ht, ht, "v", ts)
    q_right_t = _copy_cyclic_strip(right_tile, ts - ht - sr, dy_v, ht, ht, "v", ts)
    q_right_b = _copy_cyclic_strip(right_tile, ts - ht - sr, dy_v + ht, ht, ht, "v", ts)

    # Check center tile: synthesize if transparent OR if flat/featureless while arm interiors are richly textured!
    center_tile = src.copy(ts, ts, ts, ts)
    c_alpha = _tile_alpha_ratio(center_tile)
    c_act = _tile_texture_activity(center_tile, cr, cg, cb) if c_alpha >= 0.999 else 0.0
    arm_inner_act = max(
        _tile_texture_activity(q_top_l, cr, cg, cb, 0, min(ht - 1, target_bank), ht, max(1, ht - target_bank)),
        _tile_texture_activity(q_bot_l, cr, cg, cb, 0, 0, ht, max(1, ht - target_bank)),
    )
    need_synth_center = (c_alpha < 0.999) or (c_act < 0.010 and arm_inner_act > 0.020)
    if need_synth_center:
        filled = _synthesize_interior_fill_from_ring(
            src, ts, mat=mat, st=st, sb=sb, target_rim=target_bank
        )
        if c_alpha < 0.999:
            for y in range(ts):
                for x in range(ts):
                    if ((center_tile.pixel(x, y) >> 24) & 0xFF) <= 20:
                        center_tile.setPixel(x, y, filled.pixel(x, y))
        else:
            center_tile = filled
        p_fix = QPainter(src)
        p_fix.drawImage(ts, ts, center_tile)
        p_fix.end()

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

    # Row 0-1 (cols 2..3): Build ALL 4 Inner Corners anchored to their TRUE physically adjacent arm seams!
    # Tuple: (dest_x, dest_y, v_adj_quad, v_adj_row, h_adj_quad, h_adj_col, c_quad, cut_left, cut_top)
    inner_specs = (
        (2 * ht, 0,  q_left_b,  ht - 1, q_top_r, ht - 1, center_tile.copy(0, 0, ht, ht),  True,  True),
        (3 * ht, 0,  q_right_b, ht - 1, q_top_l, 0,      center_tile.copy(ht, 0, ht, ht), False, True),
        (2 * ht, ht, q_left_t,  0,      q_bot_r, ht - 1, center_tile.copy(0, ht, ht, ht), True,  False),
        (3 * ht, ht, q_right_t, 0,      q_bot_l, 0,      center_tile.copy(ht, ht, ht, ht), False, False),
    )

    def _seam_depth_x(quad: QImage, row_y: int, from_left: bool) -> int:
        d = 0
        for step in range(ht):
            x = step if from_left else (ht - 1 - step)
            if not is_inner(quad.pixel(x, row_y)):
                d = step + 1
            else:
                break
        return d

    def _seam_depth_y(quad: QImage, col_x: int, from_top: bool) -> int:
        d = 0
        for step in range(ht):
            y = step if from_top else (ht - 1 - step)
            if not is_inner(quad.pixel(col_x, y)):
                d = step + 1
            else:
                break
        return d

    def _target_seam_radii(
        v_quad: QImage, v_row: int, h_quad: QImage, h_col: int, cut_left: bool, cut_top: bool
    ) -> Tuple[int, int]:
        rx_med = _measure_bank_depth(v_quad, is_inner, "x", cut_left)
        ry_med = _measure_bank_depth(h_quad, is_inner, "y", cut_top)
        rx_seam = _seam_depth_x(v_quad, v_row, cut_left)
        ry_seam = _seam_depth_y(h_quad, h_col, cut_top)
        rx = max(0, min(ht - 2, rx_seam if abs(rx_seam - rx_med) <= 2 else rx_med))
        ry = max(0, min(ht - 2, ry_seam if abs(ry_seam - ry_med) <= 2 else ry_med))
        return rx, ry

    def _build_radial_inner_quads() -> List[QImage]:
        quads: List[QImage] = []
        seam_band = max(2, min(4, ht // 4))
        for _, _, v_quad, v_row, h_quad, h_col, c_quad, cut_left, cut_top in inner_specs:
            rx, ry = _target_seam_radii(v_quad, v_row, h_quad, h_col, cut_left, cut_top)
            if rx == 0 and ry == 0:
                quads.append(c_quad.copy())
                continue
            q = QImage(ht, ht, QImage.Format.Format_ARGB32)
            rx_f = float(max(1, rx))
            ry_f = float(max(1, ry))
            for y in range(ht):
                for x in range(ht):
                    dx = x if cut_left else (ht - 1 - x)
                    dy = y if cut_top else (ht - 1 - y)
                    v_sy = (ht - 1 - dy) if v_row == ht - 1 else dy
                    h_sx = (ht - 1 - dx) if h_col == ht - 1 else dx
                    nx = dx / rx_f
                    ny = dy / ry_f
                    r_norm = math.sqrt(nx * nx + ny * ny)
                    if r_norm <= 1.25:
                        if nx >= ny:
                            sample_d = min(ht - 1, int(round(r_norm * rx_f)))
                            sx = sample_d if cut_left else (ht - 1 - sample_d)
                            cand = v_quad.pixel(sx, v_sy)
                        else:
                            sample_d = min(ht - 1, int(round(r_norm * ry_f)))
                            sy = sample_d if cut_top else (ht - 1 - sample_d)
                            cand = h_quad.pixel(h_sx, sy)
                        if r_norm <= 1.0 or not is_inner(cand):
                            q.setPixel(x, y, cand)
                        else:
                            if nx >= ny and is_inner(v_quad.pixel(x, v_sy)):
                                q.setPixel(x, y, v_quad.pixel(x, v_sy))
                            elif is_inner(h_quad.pixel(h_sx, y)):
                                q.setPixel(x, y, h_quad.pixel(h_sx, y))
                            else:
                                q.setPixel(x, y, c_quad.pixel(x, y))
                    else:
                        if dy < seam_band and is_inner(v_quad.pixel(x, v_sy)):
                            q.setPixel(x, y, v_quad.pixel(x, v_sy))
                        elif dx < seam_band and is_inner(h_quad.pixel(h_sx, y)):
                            q.setPixel(x, y, h_quad.pixel(h_sx, y))
                        else:
                            q.setPixel(x, y, c_quad.pixel(x, y))
            quads.append(q)
        return quads

    def _build_companion_inner_quads() -> Optional[List[QImage]]:
        if (
            companion_2x2 is None
            or companion_2x2.width() < 2 * ts
            or companion_2x2.height() < 2 * ts
        ):
            return None
        quads: List[QImage] = []
        max_ic_shift = max(0, ts - ht)
        for _, _, v_quad, v_row, h_quad, h_col, _, cut_left, cut_top in inner_specs:
            rx, ry = _target_seam_radii(v_quad, v_row, h_quad, h_col, cut_left, cut_top)
            best_off: Optional[Tuple[int, int, float]] = None
            best_score = 1e9
            for sy_off in range(max_ic_shift + 1):
                for sx_off in range(max_ic_shift + 1):
                    d_x = 0
                    for step in range(ht):
                        px_c = (ts + sx_off + step) if cut_left else (ts - 1 - sx_off - step)
                        py_c = (ts + sy_off) if cut_top else (ts - 1 - sy_off)
                        if not is_inner(companion_2x2.pixel(px_c, py_c)):
                            d_x = step + 1
                        else:
                            break
                    d_y = 0
                    for step in range(ht):
                        px_c = (ts + sx_off) if cut_left else (ts - 1 - sx_off)
                        py_c = (ts + sy_off + step) if cut_top else (ts - 1 - sy_off - step)
                        if not is_inner(companion_2x2.pixel(px_c, py_c)):
                            d_y = step + 1
                        else:
                            break
                    # Reject any offset that cuts significantly deeper than the arm's seam (prevents pinching!)
                    if d_x > rx + 1 or d_x < rx - 2 or d_y > ry + 1 or d_y < ry - 2:
                        continue
                    rgb_err = 0.0
                    for u in range(ht):
                        cx_v = (ts + sx_off + u) if cut_left else (ts - sx_off - ht + u)
                        cy_v = (ts + sy_off) if cut_top else (ts - 1 - sy_off)
                        rgb_err += _rgba_dist(
                            companion_2x2.pixel(cx_v, cy_v), v_quad.pixel(u, v_row)
                        )
                        cx_h = (ts + sx_off) if cut_left else (ts - 1 - sx_off)
                        cy_h = (ts + sy_off + u) if cut_top else (ts - sy_off - ht + u)
                        rgb_err += _rgba_dist(
                            companion_2x2.pixel(cx_h, cy_h), h_quad.pixel(h_col, u)
                        )
                    mean_err = rgb_err / float(2 * ht)
                    pinch_pen = max(0, d_x - rx) * 0.06 + max(0, d_y - ry) * 0.06
                    score = mean_err + (abs(d_x - rx) + abs(d_y - ry)) * 0.03 + pinch_pen
                    if score < best_score:
                        best_score = score
                        best_off = (sx_off, sy_off, mean_err)
            if best_off is None or best_off[2] > 0.12:
                return None
            sx_off, sy_off, _ = best_off
            q = QImage(ht, ht, QImage.Format.Format_ARGB32)
            for y in range(ht):
                for x in range(ht):
                    src_x = (ts + sx_off + x) if cut_left else (ts - sx_off - ht + x)
                    src_y = (ts + sy_off + y) if cut_top else (ts - sy_off - ht + y)
                    q.setPixel(x, y, companion_2x2.pixel(src_x, src_y))
            quads.append(q)
        return quads

    # Validate ALL 4 inner corners jointly as ONE coherent crossroad (never 3 good + 1 pinched!)
    rad_quads = _build_radial_inner_quads()
    comp_quads = _build_companion_inner_quads()
    chosen_quads = rad_quads
    if comp_quads is not None:
        comp_eval = _evaluate_crossroad_coherence(
            comp_quads,
            q_top_l, q_top_r, q_bot_l, q_bot_r,
            q_left_t, q_left_b, q_right_t, q_right_b,
            is_inner, ts,
        )
        if comp_eval["coherent"]:
            chosen_quads = comp_quads

    p_inner = QPainter(res)
    for (dest_x, dest_y, *_), quad in zip(inner_specs, chosen_quads):
        p_inner.drawImage(dest_x, dest_y, quad)
    p_inner.end()

    return res


def _is_closed_2x2_patch(patch_2x2: QImage, ts: int) -> Tuple[bool, Tuple[int, int, int, int]]:
    """
    Detects whether a 2x2 tilesheet block (2*ts x 2*ts) is a closed circular/tight
    central patch surrounded by a different outer background material (e.g. LPC 2x2
    dirt-in-grass or island-in-water inner-corner blocks), where naive half-tile
    duplication would leave outer-material walls on the horizontal/vertical edges.
    Returns (is_closed_tight_patch, (ix0, ix1, iy0, iy1)) of the central interior span.
    """
    ht = ts // 2
    inner_px = [
        patch_2x2.pixel(ts + dx, ts + dy)
        for dy in range(-3, 3)
        for dx in range(-3, 3)
        if ((patch_2x2.pixel(ts + dx, ts + dy) >> 24) & 0xFF) > 180
    ]
    if len(inner_px) < 18:
        return False, (ht, 3 * ht - 1, ht, 3 * ht - 1)

    cr, cg, cb = _median_rgb(inner_px)
    in_m = (cr + cg + cb) / 3.0
    in_c = (cr - in_m, cg - in_m, cb - in_m)
    in_chroma_mag = (abs(in_c[0]) + abs(in_c[1]) + abs(in_c[2])) / (3.0 * 255.0)
    center_luma = 0.299 * cr + 0.587 * cg + 0.114 * cb

    outer_px: List[int] = []
    for k in range(2 * ts):
        for sx, sy in ((k, 0), (k, 2 * ts - 1), (0, k), (2 * ts - 1, k)):
            p = patch_2x2.pixel(sx, sy)
            if ((p >> 24) & 0xFF) > 20:
                outer_px.append(p)
    if not outer_px:
        return False, (ht, 3 * ht - 1, ht, 3 * ht - 1)
    orr, org, orb = _median_rgb(outer_px)
    contrast = (abs(orr - cr) + abs(org - cg) + abs(orb - cb)) / (3.0 * 255.0)
    if contrast < 0.08:
        return False, (ht, 3 * ht - 1, ht, 3 * ht - 1)

    def _is_in(p: int) -> bool:
        if ((p >> 24) & 0xFF) <= 180:
            return False
        luma = 0.299 * ((p >> 16) & 0xFF) + 0.587 * ((p >> 8) & 0xFF) + 0.114 * (p & 0xFF)
        if luma < center_luma * 0.65:
            return False
        if _pixel_dist_from_rgb(p, orr, org, orb) < _pixel_dist_from_rgb(p, cr, cg, cb) * 0.90:
            return False
        if in_chroma_mag >= 0.04:
            r, g, b = (p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF
            m = (r + g + b) / 3.0
            cd = (abs((r - m) - in_c[0]) + abs((g - m) - in_c[1]) + abs((b - m) - in_c[2])) / (3.0 * 255.0)
            if cd > 0.11:
                return False
        return True

    ix0 = ts
    while ix0 > 0 and _is_in(patch_2x2.pixel(ix0 - 1, ts)):
        ix0 -= 1
    ix1 = ts
    while ix1 < 2 * ts - 1 and _is_in(patch_2x2.pixel(ix1 + 1, ts)):
        ix1 += 1
    iy0 = ts
    while iy0 > 0 and _is_in(patch_2x2.pixel(ts, iy0 - 1)):
        iy0 -= 1
    iy1 = ts
    while iy1 < 2 * ts - 1 and _is_in(patch_2x2.pixel(ts, iy1 + 1)):
        iy1 += 1

    # Tight/closed patch: interior does not extend past the half-tile boundaries (ht .. 3*ht-1)
    is_tight = (ix0 > ht - 2) or (ix1 < 3 * ht + 1) or (iy0 > ht - 2) or (iy1 < 3 * ht + 1)
    has_valid_core = (ix1 - ix0 >= 6) and (iy1 - iy0 >= 6)
    return (is_tight and has_valid_core), (ix0, ix1, iy0, iy1)


def synthesize_vx_ace_from_2x2(
    patch_2x2: QImage, tile_size: int = 32, rim_balance: float = 0.40
) -> QImage:
    """
    Converts a 2x2 tilesheet block (4 tiles = 4x4 half-tiles) into a complete
    RPG Maker VX Ace (2x3 tiles = 4x6 half-tiles) autotile source image.
    Handles BOTH standard full-width 2x2 blocks AND closed circular/tight 2x2
    patches (e.g. dirt-in-grass medallions), sampling edge strips strictly from
    the flat central tangent chord and the center strictly from the inscribed
    pure-interior core so paths connect continuously without repeating circles
    or outer-material divider walls.
    """
    ts = max(8, int(tile_size))
    ht = ts // 2
    virtual_3x3 = QImage(3 * ts, 3 * ts, QImage.Format.Format_ARGB32)
    virtual_3x3.fill(QColor(0, 0, 0, 0))
    p = QPainter(virtual_3x3)
    # Corners
    p.drawImage(0, 0, patch_2x2, 0, 0, ts, ts)                       # TL
    p.drawImage(2 * ts, 0, patch_2x2, ts, 0, ts, ts)                 # TR
    p.drawImage(0, 2 * ts, patch_2x2, 0, ts, ts, ts)                 # BL
    p.drawImage(2 * ts, 2 * ts, patch_2x2, ts, ts, ts, ts)           # BR

    is_tight, (ix0, ix1, iy0, iy1) = _is_closed_2x2_patch(patch_2x2, ts)
    if is_tight:
        p.end()
        # Use flat middle tangent chord (~55% of radius) for smooth straight edges (zero wavy scallops!)
        rx_core = max(2, int((ix1 - ix0) * 0.28))
        ry_core = max(2, int((iy1 - iy0) * 0.28))
        cx_mid = (ix0 + ix1) // 2
        cy_mid = (iy0 + iy1) // 2
        sx0, sx1 = max(ix0 + 1, cx_mid - rx_core), min(ix1 - 1, cx_mid + rx_core)
        sy0, sy1 = max(iy0 + 1, cy_mid - ry_core), min(iy1 - 1, cy_mid + ry_core)
        sw_span = max(1, sx1 - sx0 + 1)
        sh_span = max(1, sy1 - sy0 + 1)

        # Seamless Top & Bottom edges (strictly inside flat tangent chord -> zero vertical walls!)
        for x in range(ts):
            src_x = sx0 + _tri_wave(x, sw_span)
            for y in range(ts):
                virtual_3x3.setPixel(ts + x, y, patch_2x2.pixel(src_x, y))
                virtual_3x3.setPixel(ts + x, 2 * ts + y, patch_2x2.pixel(src_x, ts + y))
        # Seamless Left & Right edges (strictly inside flat tangent chord -> zero horizontal walls!)
        for y in range(ts):
            src_y = sy0 + _tri_wave(y, sh_span)
            for x in range(ts):
                virtual_3x3.setPixel(x, ts + y, patch_2x2.pixel(x, src_y))
                virtual_3x3.setPixel(2 * ts + x, ts + y, patch_2x2.pixel(ts + x, src_y))
        # Pure inscribed interior center (guaranteed 100% inside circular patch -> zero outer specks!)
        for y in range(ts):
            src_y = sy0 + _tri_wave(y, sh_span)
            for x in range(ts):
                src_x = sx0 + _tri_wave(x, sw_span)
                virtual_3x3.setPixel(ts + x, ts + y, patch_2x2.pixel(src_x, src_y))
        return synthesize_vx_ace_from_3x3(virtual_3x3, ts, rim_balance=rim_balance)

    # Standard full-width 2x2 block
    p.drawImage(ts, 0, patch_2x2, ht, 0, ht, ts)
    p.drawImage(ts + ht, 0, patch_2x2, ts, 0, ht, ts)
    p.drawImage(ts, 2 * ts, patch_2x2, ht, ts, ht, ts)
    p.drawImage(ts + ht, 2 * ts, patch_2x2, ts, ts, ht, ts)
    p.drawImage(0, ts, patch_2x2, 0, ht, ts, ht)
    p.drawImage(0, ts + ht, patch_2x2, 0, ts, ts, ht)
    p.drawImage(2 * ts, ts, patch_2x2, ts, ht, ts, ht)
    p.drawImage(2 * ts, ts + ht, patch_2x2, ts, ts, ts, ht)
    p.drawImage(ts, ts, patch_2x2, ht, ht, ts, ts)
    p.end()
    return synthesize_vx_ace_from_3x3(virtual_3x3, ts, rim_balance=rim_balance)


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
    rim_balance: float = 0.40,
) -> Tuple[QImage, AutotileFormat, str]:
    """
    Extracts a tile or WxH region from a tileset sheet and synthesizes an
    accurate 47-combination Autotile (or preserves a logical WxH multi-cell
    composition) with proper multi-layer inner corners, texture continuity,
    and transparent-center handling.
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

    # 0. Explicit multi-cell logical composition WxH (occupies WxH map cells as 1 indivisible unit!)
    if effective_mode == "composition_wxh" and (w_t > 1 or h_t > 1):
        comp_patch = sheet.copy(col * ts, row * ts, w_t * ts, h_t * ts)
        # Also synthesize a clean VX Ace fallback atlas (with representative 1x1 thumbnail from comp_patch)
        if w_t == 2 and h_t == 2:
            fallback_vx = synthesize_vx_ace_from_2x2(comp_patch, ts, rim_balance=rim_balance)
        elif w_t == 3 and h_t == 3:
            fallback_vx = synthesize_vx_ace_from_3x3(comp_patch, ts, rim_balance=rim_balance)
        else:
            fallback_vx = synthesize_from_single_tile(
                sheet.copy(col * ts, row * ts, ts, ts), ts, edge_style
            )
        return (
            fallback_vx,
            AutotileFormat.VX_ACE_2X3,
            f"Kompozycja wielokafelkowa {w_t}×{h_t} (1 wariant = {w_t * h_t} komórek mapy)",
        )

    # 1. Explicit or detected 2x2 block
    if effective_mode == "block_2x2" and (col + 2) * ts <= sheet.width() and (row + 2) * ts <= sheet.height():
        patch_2x2 = sheet.copy(col * ts, row * ts, 2 * ts, 2 * ts)
        is_tight, _ = _is_closed_2x2_patch(patch_2x2, ts)
        img = synthesize_vx_ace_from_2x2(patch_2x2, ts, rim_balance=rim_balance)
        extra = " (ciągła ścieżka z kompozycji 2×2)" if is_tight else ""
        return img, AutotileFormat.VX_ACE_2X3, f"Blok 2×2 z tilesetu{extra} ({analysis['summary']})"

    # 2. 3x3 block centered at (col, row) -> converted to full VX Ace with inner corners & transparent-center fix
    has_3x3_center = (
        col >= 1 and row >= 1 and
        (col + 2) * ts <= sheet.width() and
        (row + 2) * ts <= sheet.height()
    )
    if has_3x3_center and effective_mode == "block_3x3_center":
        patch_3x3 = sheet.copy((col - 1) * ts, (row - 1) * ts, 3 * ts, 3 * ts)
        mat = _analyze_patch_materials(patch_3x3, ts)
        comp = _find_companion_inner_corners(sheet, col - 1, row - 1, ts, mat)
        img = synthesize_vx_ace_from_3x3(patch_3x3, ts, companion_2x2=comp, rim_balance=rim_balance)
        ic_tag = "narożniki 2×2 z arkusza" if comp is not None else "narożniki wewn."
        return img, AutotileFormat.VX_ACE_2X3, f"Blok 3×3 (środek) + {ic_tag} ({analysis['summary']})"

    # 3. 3x3 block starting at (col, row) as Top-Left
    has_3x3_tl = (col + 3) * ts <= sheet.width() and (row + 3) * ts <= sheet.height()
    if has_3x3_tl and effective_mode == "block_3x3_tl":
        patch_3x3 = sheet.copy(col * ts, row * ts, 3 * ts, 3 * ts)
        mat = _analyze_patch_materials(patch_3x3, ts)
        comp = _find_companion_inner_corners(sheet, col, row, ts, mat)
        img = synthesize_vx_ace_from_3x3(patch_3x3, ts, companion_2x2=comp, rim_balance=rim_balance)
        ic_tag = "narożniki 2×2 z arkusza" if comp is not None else "narożniki wewn."
        return img, AutotileFormat.VX_ACE_2X3, f"Blok 3×3 z tilesetu (róg TL + {ic_tag})"

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
        img = synthesize_vx_ace_from_2x2(representative, ts, rim_balance=rim_balance)
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
        composition_width: int = 1,
        composition_height: int = 1,
        path_width: int = 1,
        rim_balance: float = 0.40,
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
        self.composition_width = max(1, int(composition_width))
        self.composition_height = max(1, int(composition_height))
        if self.generation_mode == "composition_wxh" and self.composition_width == 1 and self.composition_height == 1:
            self.composition_width = self.source_w_tiles
            self.composition_height = self.source_h_tiles
        self.path_width = max(1, min(6, int(path_width)))
        self.rim_balance = max(0.18, min(0.65, float(rim_balance)))
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

    @property
    def is_multi_cell_composition(self) -> bool:
        return self.generation_mode == "composition_wxh" and (
            self.composition_width > 1 or self.composition_height > 1
        )

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
                asset_obj = asset_manager.get_asset(self.source_asset_id) if hasattr(asset_manager, "get_asset") else None
                ts_cfg = getattr(asset_obj, "tileset_config", None) if asset_obj else None
                if ts_cfg is not None:
                    sheet, _, _ = extract_packed_tileset_image(sheet, ts_cfg)
                src_img, fmt, _ = synthesize_from_tileset_context(
                    sheet, self.source_col, self.source_row, self.tile_size,
                    mode=self.generation_mode,
                    edge_style=self.edge_style,
                    w_tiles=self.source_w_tiles,
                    h_tiles=self.source_h_tiles,
                    rim_balance=self.rim_balance,
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

    def clone_as_new_definition(self) -> "RPGAutotile":
        """
        Forks a fresh independent RPGAutotile definition with a new ID so editing
        a definition never retroactively mutates already-painted tiles on maps.
        """
        data = self.to_dict()
        data["id"] = str(uuid.uuid4())
        data["archived"] = False
        cloned = RPGAutotile.from_dict(data)
        if self._source_qimage and not self._source_qimage.isNull():
            cloned.set_source_qimage(self._source_qimage.copy())
        return cloned

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
            "composition_width": self.composition_width,
            "composition_height": self.composition_height,
            "path_width": self.path_width,
            "rim_balance": self.rim_balance,
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
            composition_width=int(data.get("composition_width", 1)),
            composition_height=int(data.get("composition_height", 1)),
            path_width=int(data.get("path_width", 1)),
            rim_balance=float(data.get("rim_balance", 0.40)),
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
    path_width: int = 1,
    rim_balance: float = 0.40,
) -> RPGAutotile:
    """
    Factory creating a ready-to-paint RPGAutotile from a selected tile or WxH region
    in an existing tileset.
    """
    src_img, fmt, desc = synthesize_from_tileset_context(
        sheet, col, row, tile_size, mode=mode, edge_style=edge_style,
        w_tiles=w_tiles, h_tiles=h_tiles, rim_balance=rim_balance,
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
        composition_width=w_tiles if mode == "composition_wxh" else 1,
        composition_height=h_tiles if mode == "composition_wxh" else 1,
        path_width=path_width,
        rim_balance=rim_balance,
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
