import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ...models.autotile import canonicalize_blob_mask

EDGE_DIRECTIONS: Tuple[str, str, str, str] = ("N", "E", "S", "W")
OPPOSITE_EDGE: Dict[str, str] = {"N": "S", "S": "N", "E": "W", "W": "E"}

VARIANT_ROLES: Tuple[str, ...] = (
    "auto",
    "center",
    "straight_h",
    "straight_v",
    "corner_tl",
    "corner_tr",
    "corner_bl",
    "corner_br",
    "t_n",
    "t_e",
    "t_s",
    "t_w",
    "cross",
    "end_n",
    "end_e",
    "end_s",
    "end_w",
    "isolated",
    "edge",
    "composition",
    "decoration",
)


@dataclass
class EdgeSignature:
    """
    Pixel-level structural signature of one side (N/E/S/W) of a PathVariant.
    Captures navigable surface span & width, edge contour class, texture
    activity, and an 8-bin quantized color/alpha strip so compatibility never
    relies solely on average RGB color.
    """

    has_surface: bool = False
    surface_span: Tuple[int, int] = (0, 0)
    surface_width_px: int = 0
    surface_ratio: float = 0.0
    edge_type: str = "unknown"  # open_full | open_path | closed_outer | closed_transparent | bank_cliff | mixed
    mean_rgb: Tuple[int, int, int] = (0, 0, 0)
    texture_activity: float = 0.0
    sample_strip: Tuple[Tuple[int, int, int, int], ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_surface": self.has_surface,
            "surface_span": list(self.surface_span),
            "surface_width_px": self.surface_width_px,
            "surface_ratio": round(float(self.surface_ratio), 4),
            "edge_type": self.edge_type,
            "mean_rgb": list(self.mean_rgb),
            "texture_activity": round(float(self.texture_activity), 4),
            "sample_strip": [list(px) for px in self.sample_strip],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EdgeSignature":
        span = data.get("surface_span", [0, 0])
        rgb = data.get("mean_rgb", [0, 0, 0])
        strip = tuple(
            (int(p[0]), int(p[1]), int(p[2]), int(p[3]))
            for p in data.get("sample_strip", [])
            if isinstance(p, (list, tuple)) and len(p) == 4
        )
        return cls(
            has_surface=bool(data.get("has_surface", False)),
            surface_span=(int(span[0]), int(span[1])) if len(span) == 2 else (0, 0),
            surface_width_px=int(data.get("surface_width_px", 0)),
            surface_ratio=float(data.get("surface_ratio", 0.0)),
            edge_type=str(data.get("edge_type", "unknown")),
            mean_rgb=(int(rgb[0]), int(rgb[1]), int(rgb[2])) if len(rgb) == 3 else (0, 0, 0),
            texture_activity=float(data.get("texture_activity", 0.0)),
            sample_strip=strip,
        )


class CustomPathVariant:
    """
    Logical multi-tile or single-tile Path variant describing an indivisible
    source composition in a tileset (1x1, 2x2, 2x3, 3x2, 3x3, 4x4, or any WxH).
    Explicitly separates:
      - tileset coordinates & pixel rect (source_asset_id, source_col, source_row, source_rect)
      - logical variant metadata (width_tiles, height_tiles, role, mask, surface_width_px, edge_type)
      - graphical edge signatures (edges: N/E/S/W)
      - compatibility rules (compatible_neighbors, allow_connections, alternatives, priority, weight)
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
        source_rect: Optional[Tuple[int, int, int, int]] = None,
        role: str = "auto",
        compatible_neighbors: Optional[Any] = None,
        surface_width_px: int = 0,
        surface_width_tiles: int = 1,
        edge_type: str = "auto",
        edges: Optional[Dict[str, EdgeSignature]] = None,
        allow_connections: bool = True,
        alternatives: Optional[List[str]] = None,
    ):
        self.id = variant_id or str(uuid.uuid4())
        self.mask = -1 if int(mask) < 0 else canonicalize_blob_mask(int(mask))
        self.source_asset_id = str(source_asset_id)
        self.source_col = max(0, int(source_col))
        self.source_row = max(0, int(source_row))
        self.width_tiles = max(1, int(width_tiles))
        self.height_tiles = max(1, int(height_tiles))
        self.source_rect = (
            tuple(int(v) for v in source_rect)
            if source_rect and len(source_rect) == 4
            else None
        )
        self.role = str(role or "auto")
        self.surface_width_px = max(0, int(surface_width_px))
        self.surface_width_tiles = max(1, int(surface_width_tiles))
        self.edge_type = str(edge_type or "auto")
        self.edges: Dict[str, EdgeSignature] = dict(edges or {})
        self.allow_connections = bool(allow_connections) and self.role != "decoration"
        self.alternatives: List[str] = [str(a) for a in (alternatives or [])]

        # Directional compatibility: Dict[str, List[str]] (e.g. {"N": [id1, ...]})
        # Backward compatible with legacy List[int] mask lists
        if isinstance(compatible_neighbors, dict):
            self.compatible_neighbors: Dict[str, List[str]] = {
                str(k): [str(v) for v in vals]
                for k, vals in compatible_neighbors.items()
                if str(k) in EDGE_DIRECTIONS
            }
            self.compatible_masks: List[int] = []
        elif isinstance(compatible_neighbors, list):
            self.compatible_neighbors = {}
            self.compatible_masks = [int(v) for v in compatible_neighbors if isinstance(v, (int, float))]
        else:
            self.compatible_neighbors = {}
            self.compatible_masks = []

        self.priority = int(priority)
        self.weight = max(0.01, float(weight))
        self.name = name or f"Wariant {self.width_tiles}x{self.height_tiles} (maska {self.mask})"

    @property
    def is_multi_tile(self) -> bool:
        return self.width_tiles > 1 or self.height_tiles > 1

    def clone(self, preserve_id: bool = True) -> "CustomPathVariant":
        return CustomPathVariant.from_dict(self.to_dict()) if preserve_id else CustomPathVariant(
            mask=self.mask,
            source_asset_id=self.source_asset_id,
            source_col=self.source_col,
            source_row=self.source_row,
            width_tiles=self.width_tiles,
            height_tiles=self.height_tiles,
            priority=self.priority,
            weight=self.weight,
            name=self.name,
            source_rect=self.source_rect,
            role=self.role,
            compatible_neighbors={k: list(v) for k, v in self.compatible_neighbors.items()},
            surface_width_px=self.surface_width_px,
            surface_width_tiles=self.surface_width_tiles,
            edge_type=self.edge_type,
            edges={k: EdgeSignature.from_dict(e.to_dict()) for k, e in self.edges.items()},
            allow_connections=self.allow_connections,
            alternatives=list(self.alternatives),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mask": self.mask,
            "source_asset_id": self.source_asset_id,
            "source_col": self.source_col,
            "source_row": self.source_row,
            "width_tiles": self.width_tiles,
            "height_tiles": self.height_tiles,
            "source_rect": list(self.source_rect) if self.source_rect else None,
            "role": self.role,
            "surface_width_px": self.surface_width_px,
            "surface_width_tiles": self.surface_width_tiles,
            "edge_type": self.edge_type,
            "edges": {d: sig.to_dict() for d, sig in self.edges.items()},
            "compatible_neighbors": {d: list(ids) for d, ids in self.compatible_neighbors.items()},
            "compatible_masks": list(self.compatible_masks),
            "allow_connections": self.allow_connections,
            "alternatives": list(self.alternatives),
            "priority": self.priority,
            "weight": self.weight,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CustomPathVariant":
        sr = data.get("source_rect")
        raw_edges = data.get("edges") or {}
        edges = {
            str(d): EdgeSignature.from_dict(ed)
            for d, ed in raw_edges.items()
            if isinstance(ed, dict) and str(d) in EDGE_DIRECTIONS
        }
        v = cls(
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
            source_rect=tuple(sr) if sr and len(sr) == 4 else None,
            role=str(data.get("role", "auto")),
            compatible_neighbors=data.get("compatible_neighbors"),
            surface_width_px=int(data.get("surface_width_px", 0)),
            surface_width_tiles=int(data.get("surface_width_tiles", 1)),
            edge_type=str(data.get("edge_type", "auto")),
            edges=edges,
            allow_connections=bool(data.get("allow_connections", True)),
            alternatives=data.get("alternatives"),
        )
        if data.get("compatible_masks"):
            v.compatible_masks = [int(m) for m in data["compatible_masks"]]
        return v


PathVariant = CustomPathVariant


@dataclass
class CompatibilityResult:
    compatible: bool
    score: float
    reasons: List[str] = field(default_factory=list)


@dataclass
class Placement:
    """
    Logical placement of a single-tile or multi-tile WxH variant on the map.
    Strictly separates tileset source rectangles from map cell coordinates.
    """

    autotile_id: str
    origin_col: int
    origin_row: int
    width_tiles: int
    height_tiles: int
    source_asset_id: str
    cell_slices: Dict[Tuple[int, int], Tuple[int, int, int, int]]
    variant_id: Optional[str] = None
    is_composition: bool = False
    is_fallback: bool = False

    def occupied_cells(self) -> List[Tuple[int, int]]:
        return [
            (self.origin_col + dc, self.origin_row + dr)
            for dr in range(self.height_tiles)
            for dc in range(self.width_tiles)
        ]


@dataclass
class SheetAnalysis:
    """Cached result of scanning an imported tileset sheet for path structures."""

    cols: int
    rows: int
    tile_width: int
    tile_height: int
    proposed_variants: List[PathVariant] = field(default_factory=list)
    detected_3x3_blocks: List[Tuple[int, int, bool]] = field(default_factory=list)
    detected_2x2_blocks: List[Tuple[int, int, bool]] = field(default_factory=list)
    summary: str = ""
