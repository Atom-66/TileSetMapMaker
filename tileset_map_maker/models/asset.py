import os
import hashlib
import uuid
from enum import Enum
from typing import Optional, Dict, Any, Tuple, List
from PIL import Image


class AssetType(str, Enum):
    SINGLE_IMAGE = "single_image"
    TILESET = "tileset"


class TilesetConfig:
    """
    Configuration for a uniform, regular grid tileset.
    Every tileset strictly uses one cell size (tile_width x tile_height)
    across the entire image sheet.
    """

    def __init__(
        self,
        tile_width: int = 32,
        tile_height: int = 32,
        margin_x: int = 0,
        margin_y: int = 0,
        spacing_x: int = 0,
        spacing_y: int = 0,
        start_x: int = 0,
        start_y: int = 0,
        margin: Optional[int] = None,
        spacing: Optional[int] = None,
        auto_detected: bool = False,
    ):
        self.tile_width = max(1, tile_width)
        self.tile_height = max(1, tile_height)
        self.margin_x = max(0, margin if margin is not None else margin_x)
        self.margin_y = max(0, margin if margin is not None else margin_y)
        self.spacing_x = max(0, spacing if spacing is not None else spacing_x)
        self.spacing_y = max(0, spacing if spacing is not None else spacing_y)
        self.start_x = max(0, start_x)
        self.start_y = max(0, start_y)
        self.auto_detected = auto_detected

    @property
    def margin(self) -> int:
        return self.margin_x

    @property
    def spacing(self) -> int:
        return self.spacing_x

    def compute_grid(self, img_w: int, img_h: int) -> Dict[str, Any]:
        """
        Calculates the exact regular grid division of the image.
        Returns cols, rows, total_cells, and remainder edge fragments.
        """
        if img_w <= 0 or img_h <= 0:
            return {
                "cols": 0,
                "rows": 0,
                "total_cells": 0,
                "remainder_x": 0,
                "remainder_y": 0,
                "has_incomplete_edges": False,
            }

        # Available space after grid start and outer margins
        avail_w = img_w - self.start_x - (self.margin_x * 2)
        avail_h = img_h - self.start_y - (self.margin_y * 2)

        # Standard step between cell start positions
        step_w = self.tile_width + self.spacing_x
        step_h = self.tile_height + self.spacing_y

        if avail_w < self.tile_width:
            cols = 0
            remainder_x = max(0, avail_w)
        else:
            cols = 1 + (avail_w - self.tile_width) // step_w
            used_w = (cols - 1) * step_w + self.tile_width
            remainder_x = max(0, avail_w - used_w)

        if avail_h < self.tile_height:
            rows = 0
            remainder_y = max(0, avail_h)
        else:
            rows = 1 + (avail_h - self.tile_height) // step_h
            used_h = (rows - 1) * step_h + self.tile_height
            remainder_y = max(0, avail_h - used_h)

        return {
            "cols": cols,
            "rows": rows,
            "total_cells": cols * rows,
            "remainder_x": remainder_x,
            "remainder_y": remainder_y,
            "has_incomplete_edges": remainder_x > 0 or remainder_y > 0,
        }

    def get_tile_rect(self, col: int, row: int) -> Tuple[int, int, int, int]:
        """Calculates exact (x, y, w, h) in pixels for the given col, row."""
        x = self.start_x + self.margin_x + col * (self.tile_width + self.spacing_x)
        y = self.start_y + self.margin_y + row * (self.tile_height + self.spacing_y)
        return x, y, self.tile_width, self.tile_height

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tile_width": self.tile_width,
            "tile_height": self.tile_height,
            "margin_x": self.margin_x,
            "margin_y": self.margin_y,
            "spacing_x": self.spacing_x,
            "spacing_y": self.spacing_y,
            "start_x": self.start_x,
            "start_y": self.start_y,
            "margin": self.margin_x,
            "spacing": self.spacing_x,
            "auto_detected": self.auto_detected,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TilesetConfig":
        margin = data.get("margin", 0)
        spacing = data.get("spacing", 0)
        return cls(
            tile_width=data.get("tile_width", 32),
            tile_height=data.get("tile_height", 32),
            margin_x=data.get("margin_x", margin),
            margin_y=data.get("margin_y", margin),
            spacing_x=data.get("spacing_x", spacing),
            spacing_y=data.get("spacing_y", spacing),
            start_x=data.get("start_x", 0),
            start_y=data.get("start_y", 0),
            auto_detected=data.get("auto_detected", False),
        )


class SelectedSubTile:
    """
    Represents a selected single tile or multi-tile rectangular block
    within a tileset sheet (Tiled-style selection).
    """

    def __init__(
        self,
        asset_id: str,
        col: int = 0,
        row: int = 0,
        cols_count: int = 1,
        rows_count: int = 1,
        sub_x: int = 0,
        sub_y: int = 0,
        sub_w: int = 32,
        sub_h: int = 32,
        tile_width: int = 32,
        tile_height: int = 32,
        spacing_x: int = 0,
        spacing_y: int = 0,
        asset_name: Optional[str] = None,
    ):
        self.asset_id = asset_id
        self.asset_name = asset_name
        self.col = col
        self.row = row
        self.cols_count = max(1, cols_count)
        self.rows_count = max(1, rows_count)
        self.sub_x = sub_x
        self.sub_y = sub_y
        self.sub_w = sub_w
        self.sub_h = sub_h
        self.tile_width = max(1, tile_width)
        self.tile_height = max(1, tile_height)
        self.spacing_x = spacing_x
        self.spacing_y = spacing_y

    @property
    def id(self) -> str:
        return self.asset_id

    def is_multi_tile(self) -> bool:
        return self.cols_count > 1 or self.rows_count > 1

    def get_tile_slice(self, dc: int, dr: int) -> Tuple[int, int, int, int]:
        """Returns pixel (x, y, w, h) for sub-cell (dc, dr) relative to selection origin."""
        x = self.sub_x + dc * (self.tile_width + self.spacing_x)
        y = self.sub_y + dr * (self.tile_height + self.spacing_y)
        return x, y, self.tile_width, self.tile_height

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "col": self.col,
            "row": self.row,
            "cols_count": self.cols_count,
            "rows_count": self.rows_count,
            "sub_x": self.sub_x,
            "sub_y": self.sub_y,
            "sub_w": self.sub_w,
            "sub_h": self.sub_h,
            "tile_width": self.tile_width,
            "tile_height": self.tile_height,
            "spacing_x": self.spacing_x,
            "spacing_y": self.spacing_y,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelectedSubTile":
        return cls(
            asset_id=data["asset_id"],
            col=data.get("col", 0),
            row=data.get("row", 0),
            cols_count=data.get("cols_count", 1),
            rows_count=data.get("rows_count", 1),
            sub_x=data.get("sub_x", 0),
            sub_y=data.get("sub_y", 0),
            sub_w=data.get("sub_w", 32),
            sub_h=data.get("sub_h", 32),
            tile_width=data.get("tile_width", 32),
            tile_height=data.get("tile_height", 32),
            spacing_x=data.get("spacing_x", 0),
            spacing_y=data.get("spacing_y", 0),
        )


class Asset:
    """Represents an imported asset: single PNG or uniform-grid tileset."""

    def __init__(
        self,
        file_path: str,
        name: Optional[str] = None,
        category_path: str = "Custom",
        asset_type: AssetType = AssetType.SINGLE_IMAGE,
        asset_id: Optional[str] = None,
        width: int = 0,
        height: int = 0,
        content_hash: Optional[str] = None,
        is_favorite: bool = False,
        last_used_time: float = 0.0,
        tileset_config: Optional[TilesetConfig] = None,
    ):
        self.id = asset_id or str(uuid.uuid4())
        self.file_path = os.path.abspath(file_path)
        self.name = name or os.path.splitext(os.path.basename(file_path))[0]
        self.category_path = category_path.strip("/") or "Custom"
        self.asset_type = asset_type
        self.width = width
        self.height = height
        self.content_hash = content_hash or self.calculate_hash(self.file_path)
        self.is_favorite = is_favorite
        self.last_used_time = last_used_time
        self.file_info: Dict[str, Any] = {}

        self.tileset_config = tileset_config or (
            TilesetConfig() if asset_type == AssetType.TILESET else None
        )

        if os.path.exists(self.file_path):
            self.analyze_file()

    @staticmethod
    def calculate_hash(path: str) -> str:
        if not os.path.exists(path):
            return ""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def analyze_file_path(cls, file_path: str) -> Dict[str, Any]:
        """
        Intelligently analyzes the imported file path:
        format, dimensions, color mode, alpha channel presence, and transparency.
        """
        try:
            with Image.open(file_path) as img:
                has_alpha = (
                    img.mode in ("RGBA", "LA")
                    or (img.mode == "P" and "transparency" in img.info)
                )
                return {
                    "format": img.format or "PNG",
                    "width": img.width,
                    "height": img.height,
                    "mode": img.mode,
                    "has_alpha": has_alpha,
                }
        except Exception as e:
            return {
                "format": "PNG",
                "width": 32,
                "height": 32,
                "mode": "RGBA",
                "has_alpha": True,
                "error": str(e),
            }

    def analyze_file(self) -> Dict[str, Any]:
        """
        Intelligently analyzes this asset's file:
        format, dimensions, color mode, alpha channel presence, and transparency.
        """
        res = self.analyze_file_path(self.file_path)
        self.width = res["width"]
        self.height = res["height"]
        self.file_info = res
        return self.file_info

    def get_tileset_dimensions(self) -> Tuple[int, int]:
        """Returns (cols, rows) count of full cells in this tileset."""
        if not self.tileset_config:
            return 1, 1
        grid = self.tileset_config.compute_grid(self.width, self.height)
        return grid["cols"], grid["rows"]

    def get_tile_rect(self, col: int, row: int) -> Tuple[int, int, int, int]:
        """Returns (x, y, w, h) in pixels for the specified col, row."""
        if not self.tileset_config:
            return 0, 0, self.width, self.height
        return self.tileset_config.get_tile_rect(col, row)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "file_path": self.file_path,
            "category_path": self.category_path,
            "asset_type": self.asset_type.value,
            "width": self.width,
            "height": self.height,
            "content_hash": self.content_hash,
            "is_favorite": self.is_favorite,
            "last_used_time": self.last_used_time,
            "tileset_config": self.tileset_config.to_dict() if self.tileset_config else None,
            "file_info": self.file_info,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Asset":
        ts_cfg = (
            TilesetConfig.from_dict(data["tileset_config"])
            if data.get("tileset_config")
            else None
        )
        asset = cls(
            file_path=data["file_path"],
            name=data["name"],
            category_path=data.get("category_path", "Custom"),
            asset_type=AssetType(data.get("asset_type", AssetType.SINGLE_IMAGE.value)),
            asset_id=data.get("id"),
            width=data.get("width", 0),
            height=data.get("height", 0),
            content_hash=data.get("content_hash"),
            is_favorite=data.get("is_favorite", False),
            last_used_time=data.get("last_used_time", 0.0),
            tileset_config=ts_cfg,
        )
        asset.file_info = data.get("file_info", {})
        return asset
