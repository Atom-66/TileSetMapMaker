from typing import Dict, List, Optional, Tuple, Any

# ==============================================================================
# BITMASK DIRECTIONAL CONSTANTS (8-NEIGHBOR ADJACENCY)
# ==============================================================================
# Standard Clockwise 8-direction bit positions:
#  NW(128)  N(1)   NE(2)
#   W(64)   [C]     E(4)
#  SW(32)   S(16)  SE(8)
# ==============================================================================
MASK_N  = 1    # 1 << 0
MASK_NE = 2    # 1 << 1
MASK_E  = 4    # 1 << 2
MASK_SE = 8    # 1 << 3
MASK_S  = 16   # 1 << 4
MASK_SW = 32   # 1 << 5
MASK_W  = 64   # 1 << 6
MASK_NW = 128  # 1 << 7

CARDINAL_MASK = MASK_N | MASK_E | MASK_S | MASK_W  # 85
DIAGONAL_MASK = MASK_NE | MASK_SE | MASK_SW | MASK_NW  # 170

# Cardinal values for 3x3 box positions
CARD_CORNER_TL   = MASK_E | MASK_S                # 20
CARD_EDGE_TOP    = MASK_E | MASK_S | MASK_W       # 84
CARD_CORNER_TR   = MASK_W | MASK_S                # 80
CARD_EDGE_LEFT   = MASK_N | MASK_S | MASK_E       # 21
CARD_CENTER      = CARDINAL_MASK                  # 85
CARD_EDGE_RIGHT  = MASK_N | MASK_S | MASK_W       # 81
CARD_CORNER_BL   = MASK_N | MASK_E                # 5
CARD_EDGE_BOTTOM = MASK_N | MASK_E | MASK_W       # 69
CARD_CORNER_BR   = MASK_N | MASK_W                # 65

# Full 8-neighbor values with diagonals for 3x3 outer box
MASK_ISOLATED    = 0
MASK_CENTER      = 255
MASK_EDGE_TOP    = CARD_EDGE_TOP | MASK_SE | MASK_SW        # 124
MASK_EDGE_BOTTOM = CARD_EDGE_BOTTOM | MASK_NE | MASK_NW     # 199
MASK_EDGE_LEFT   = CARD_EDGE_LEFT | MASK_NE | MASK_SE       # 31
MASK_EDGE_RIGHT  = CARD_EDGE_RIGHT | MASK_NW | MASK_SW      # 241
MASK_CORNER_TL   = CARD_CORNER_TL | MASK_SE                 # 28
MASK_CORNER_TR   = CARD_CORNER_TR | MASK_SW                 # 112
MASK_CORNER_BL   = CARD_CORNER_BL | MASK_NE                 # 7
MASK_CORNER_BR   = CARD_CORNER_BR | MASK_NW                 # 193


# ==============================================================================
# CANONICAL WANG 47 BLOB REDUCTION
# ==============================================================================
def canonicalize_blob_mask(mask: int) -> int:
    """
    Masks out diagonal neighbors whose flanking cardinal neighbors are not both present.
    Topologically, an inner corner (concave) can only form if both cardinal edges meet.
    This projects any arbitrary 8-neighbor bitmask (0..255) onto the exact 47 canonical
    Wang blob configurations.
    """
    has_n = bool(mask & MASK_N)
    has_s = bool(mask & MASK_S)
    has_e = bool(mask & MASK_E)
    has_w = bool(mask & MASK_W)

    c_mask = mask & CARDINAL_MASK
    if has_n and has_e and (mask & MASK_NE):
        c_mask |= MASK_NE
    if has_s and has_e and (mask & MASK_SE):
        c_mask |= MASK_SE
    if has_s and has_w and (mask & MASK_SW):
        c_mask |= MASK_SW
    if has_n and has_w and (mask & MASK_NW):
        c_mask |= MASK_NW
    return c_mask


# ==============================================================================
# DETERMINISTIC PSEUDO-RANDOM CELL HASH
# ==============================================================================
def deterministic_cell_hash(seed: int, col: int, row: int, salt: int = 0) -> int:
    """
    Fast, uniform, deterministic hash based on coordinates, seed, and optional salt.
    Guarantees stable random variation across reloads, undo/redo, and brush strokes.
    """
    h = (int(col) * 374761393 + int(row) * 668265263 + int(seed or 42) * 961748941 + int(salt) * 421081) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return h ^ (h >> 16)

