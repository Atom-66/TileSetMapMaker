from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any, Set
from ...models.layer import MapItem, Layer, ItemType
from ...models.project import Project
from ...models.asset import Asset, SelectedSubTile, AssetType, TilesetConfig
from ...models.brush_preset import BrushSettings, transform_composition_cell
from PyQt6.QtGui import QRegion
from PyQt6.QtCore import Qt


class ToolContext:
    """Provides contextual data for active tool execution."""

    def __init__(
        self,
        project: Project,
        asset_manager: Any,
        history_manager: Optional[Any] = None,
        active_layer: Optional[Layer] = None,
        selected_asset: Optional[Any] = None,
        autotile_engine: Optional[Any] = None,
        stamp_manager: Optional[Any] = None,
        set_manager: Optional[Any] = None,
        brush_settings: Optional[BrushSettings] = None,
    ):
        self.project = project
        self.asset_manager = asset_manager
        self.history_manager = history_manager
        self.active_layer = active_layer
        self.selected_asset = selected_asset
        self.autotile_engine = autotile_engine
        self.stamp_manager = stamp_manager
        self.set_manager = set_manager

        self.cursor_col: int = 0
        self.cursor_row: int = 0
        self.cursor_pixel_x: float = 0.0
        self.cursor_pixel_y: float = 0.0

        self.brush_settings = brush_settings if brush_settings is not None else BrushSettings()
        self.clipboard_tiles: Dict[Tuple[int, int], MapItem] = {}
        self.clipboard_region = QRegion()
        self.selection_modifiers = Qt.KeyboardModifier.NoModifier
        self.selection_tool: Optional[Any] = None
        self.selected_object_ids: List[str] = []
        self.selected_cells: Set[Tuple[int, int]] = set()


class BaseTool(ABC):
    """Abstract base class for all map editor tools."""

    def __init__(self, name: str, shortcut: str = ""):
        self.name = name
        self.shortcut = shortcut
        self.is_active = False

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        pass

    def on_drag(self, col: int, row: int, context: ToolContext) -> None:
        pass

    def on_release(self, col: int, row: int, context: ToolContext) -> None:
        pass

    def get_preview_items(self, context: ToolContext) -> List[MapItem]:
        """Returns items to draw as hover/ghost preview."""
        return []

    def cancel(self, context: ToolContext) -> None:
        self.is_active = False

    @staticmethod
    def create_items_from_selection(
        col: int,
        row: int,
        context: ToolContext,
        override_asset: Optional[Any] = None,
        *,
        for_preview: bool = False,
    ) -> List[MapItem]:
        """
        Creates one or more MapItems from selection.
        If a multi-tile block is selected (Tiled-style), returns all tiles
        in the block relative to (col, row), with full composition-level
        mirror and rotation applied.
        """
        bs = context.brush_settings
        if getattr(bs, "selected_autotile", None):
            sel = bs.selected_autotile
        else:
            sel = override_asset if override_asset is not None else context.selected_asset
            if not sel and context.asset_manager:
                sel = context.asset_manager.selected_item
            if not sel:
                if bs.random_variant and bs.variants:
                    sel = bs.pick_variant(None)

        if not sel:
            return []

        rot, fx, fy, jx, jy = bs.get_brush_transform(for_preview=for_preview)

        if getattr(sel, "is_autotile", False) or hasattr(sel, "autotile"):
            autotile = getattr(sel, "autotile", sel)
            ts = getattr(autotile, "tile_size", None) or getattr(context.project, "tile_size", 32)
            dest_ts = getattr(context.project, "tile_size", ts)
            if context.autotile_engine and hasattr(context.autotile_engine, "can_render_autotile"):
                if not context.autotile_engine.can_render_autotile(autotile, context.asset_manager):
                    return []
            sx, sy, sw, sh = autotile.get_tile_slice_for_mask(0, col, row)
            if sw <= 0 or sh <= 0 or sx < 0 or sy < 0:
                return []
            if context.asset_manager and hasattr(context.asset_manager, "register_rpg_autotile"):
                context.asset_manager.register_rpg_autotile(autotile)
            item = MapItem(
                asset_id=autotile.id,
                col=col,
                row=row,
                item_type=ItemType.TILE,
                terrain_type=autotile.terrain_type,
                is_auto_tiled=True,
                source_x=sx,
                source_y=sy,
                source_w=sw,
                source_h=sh,
                dest_w=dest_ts,
                dest_h=dest_ts,
            )
            return [item]

        if isinstance(sel, SelectedSubTile):
            items = []
            for dr in range(sel.rows_count):
                for dc in range(sel.cols_count):
                    sx, sy, sw, sh = sel.get_tile_slice(dc, dr)
                    dest_dc, dest_dr = transform_composition_cell(
                        dc,
                        dr,
                        sel.cols_count,
                        sel.rows_count,
                        flip_x=fx,
                        flip_y=fy,
                        rotation=rot,
                    )
                    # Use selection cell size or project tile size
                    dw = sel.tile_width
                    dh = sel.tile_height
                    item = MapItem(
                        asset_id=sel.asset_id,
                        col=col + dest_dc,
                        row=row + dest_dr,
                        item_type=ItemType.TILE,
                        offset_x=jx,
                        offset_y=jy,
                        source_x=sx,
                        source_y=sy,
                        source_w=sw,
                        source_h=sh,
                        dest_w=dw,
                        dest_h=dh,
                        rotation=rot,
                        flip_x=fx,
                        flip_y=fy,
                    )
                    items.append(item)
            return items

        elif isinstance(sel, Asset):
            if sel.asset_type == AssetType.TILESET:
                cfg = sel.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
                sx, sy, sw, sh = cfg.get_tile_rect(0, 0)
                item = MapItem(
                    asset_id=sel.id,
                    col=col,
                    row=row,
                    item_type=ItemType.TILE,
                    offset_x=jx,
                    offset_y=jy,
                    source_x=sx,
                    source_y=sy,
                    source_w=sw,
                    source_h=sh,
                    dest_w=cfg.tile_width,
                    dest_h=cfg.tile_height,
                    rotation=rot,
                    flip_x=fx,
                    flip_y=fy,
                )
                return [item]
            else:
                # Single PNG graphic
                is_grid_tile = (sel.width == context.project.tile_size and sel.height == context.project.tile_size)
                item = MapItem(
                    asset_id=sel.id,
                    col=col,
                    row=row,
                    item_type=ItemType.TILE if is_grid_tile else ItemType.OBJECT,
                    offset_x=jx,
                    offset_y=jy,
                    source_x=0,
                    source_y=0,
                    source_w=sel.width,
                    source_h=sel.height,
                    dest_w=sel.width,
                    dest_h=sel.height,
                    rotation=rot,
                    flip_x=fx,
                    flip_y=fy,
                )
                return [item]
        return []

    @staticmethod
    def create_item_from_selection(
        col: int,
        row: int,
        context: ToolContext,
        override_asset: Optional[Any] = None,
    ) -> Optional[MapItem]:
        items = BaseTool.create_items_from_selection(col, row, context, override_asset)
        return items[0] if items else None


# Convenience module-level aliases
create_items_from_selection = BaseTool.create_items_from_selection
create_item_from_selection = BaseTool.create_item_from_selection
