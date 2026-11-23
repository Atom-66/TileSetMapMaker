from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any, Set
from ...models.layer import MapItem, Layer, ItemType
from ...models.project import Project
from ...models.asset import Asset, SelectedSubTile, AssetType
from ...models.brush_preset import BrushSettings


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
    ) -> List[MapItem]:
        """
        Creates one or more MapItems from selection.
        If a multi-tile block is selected (Tiled-style), returns all tiles
        in the block relative to (col, row).
        """
        bs = context.brush_settings
        sel = override_asset if override_asset is not None else context.selected_asset
        if not sel and context.asset_manager:
            sel = context.asset_manager.selected_item
        if not sel:
            if bs.random_variant and bs.variants:
                sel = bs.pick_variant(None)

        if not sel:
            if bs.auto_tile_enabled and context.autotile_engine:
                ruleset = context.autotile_engine.get_active_ruleset()
                if ruleset:
                    init_tile = ruleset.default_tile or ruleset.get_tile_for_mask(0)
                    aid = ruleset.asset_id or (init_tile[0] if init_tile else "")
                    ts = getattr(context.project, "tile_size", 32)
                    sx, sy, sw, sh = (init_tile[1], init_tile[2], init_tile[3], init_tile[4]) if init_tile else (0, 0, ts, ts)
                    item = MapItem(
                        asset_id=aid,
                        col=col,
                        row=row,
                        item_type=ItemType.TILE,
                        terrain_type=ruleset.terrain_type,
                        is_auto_tiled=True,
                        source_x=sx,
                        source_y=sy,
                        source_w=sw,
                        source_h=sh,
                        dest_w=sw or ts,
                        dest_h=sh or ts,
                    )
                    return [item]
            return []

        rot, fx, fy, jx, jy = bs.get_random_transform()

        if isinstance(sel, SelectedSubTile):
            items = []
            for dr in range(sel.rows_count):
                for dc in range(sel.cols_count):
                    sx, sy, sw, sh = sel.get_tile_slice(dc, dr)
                    # Use selection cell size or project tile size
                    dw = sel.tile_width
                    dh = sel.tile_height
                    item = MapItem(
                        asset_id=sel.asset_id,
                        col=col + dc,
                        row=row + dr,
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
