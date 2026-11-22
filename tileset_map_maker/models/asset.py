import os
import hashlib
import uuid
from enum import Enum
from typing import Optional, Dict, Any, Tuple
from PIL import Image


class AssetType(str, Enum):
    SINGLE_IMAGE = "single_image"
    TILESET = "tileset"


class TilesetConfig:
    def __init__(
        self,
        tile_width: int = 32,
        tile_height: int = 32,
        margin: int = 0,
        spacing: int = 0,
        auto_detected: bool = False,
    ):
        self.tile_width = max(1, tile_width)
        self.tile_height = max(1, tile_height)
        self.margin = max(0, margin)
        self.spacing = max(0, spacing)
        self.auto_detected = auto_detected

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tile_width": self.tile_width,
            "tile_height": self.tile_height,
            "margin": self.margin,
            "spacing": self.spacing,
            "auto_detected": self.auto_detected,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TilesetConfig":
        return cls(
            tile_width=data.get("tile_width", 32),
            tile_height=data.get("tile_height", 32),
            margin=data.get("margin", 0),
            spacing=data.get("spacing", 0),
            auto_detected=data.get("auto_detected", False),
        )


class SelectedSubTile:
    """Represents a selected sub-tile or a rectangular selection within a tileset."""
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
    ):
        self.asset_id = asset_id
        self.col = col
        self.row = row
        self.cols_count = max(1, cols_count)
        self.rows_count = max(1, rows_count)
        self.sub_x = sub_x
        self.sub_y = sub_y
        self.sub_w = sub_w
        self.sub_h = sub_h

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
        )


class Asset:
    """Represents an imported asset: single PNG or tileset."""

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
        self.tileset_config = tileset_config or (
            TilesetConfig() if asset_type == AssetType.TILESET else None
        )

        if (self.width == 0 or self.height == 0) and os.path.exists(self.file_path):
            self.load_dimensions()

    @staticmethod
    def calculate_hash(path: str) -> str:
        if not os.path.exists(path):
            return ""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def load_dimensions(self) -> None:
        try:
            with Image.open(self.file_path) as img:
                self.width, self.height = img.size
        except Exception:
            self.width, self.height = 32, 32

    def get_tileset_dimensions(self) -> Tuple[int, int]:
        """Returns (cols, rows) count in this tileset."""
        if not self.tileset_config:
            return 1, 1
        cfg = self.tileset_config
        eff_w = self.width - 2 * cfg.margin + cfg.spacing
        eff_h = self.height - 2 * cfg.margin + cfg.spacing
        step_w = cfg.tile_width + cfg.spacing
        step_h = cfg.tile_height + cfg.spacing
        cols = max(1, eff_w // step_w) if step_w > 0 else 1
        rows = max(1, eff_h // step_h) if step_h > 0 else 1
        return cols, rows

    def get_tile_rect(self, col: int, row: int) -> Tuple[int, int, int, int]:
        """Returns (x, y, w, h) in pixels for the specified col, row."""
        if not self.tileset_config:
            return 0, 0, self.width, self.height
        cfg = self.tileset_config
        x = cfg.margin + col * (cfg.tile_width + cfg.spacing)
        y = cfg.margin + row * (cfg.tile_height + cfg.spacing)
        return x, y, cfg.tile_width, cfg.tile_height

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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Asset":
        ts_cfg = (
            TilesetConfig.from_dict(data["tileset_config"])
            if data.get("tileset_config")
            else None
        )
        return cls(
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
