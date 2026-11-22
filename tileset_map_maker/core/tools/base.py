from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any
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
        history_manager: Any,
        active_layer: Optional[Layer],
        selected_asset: Optional[Any],  # Asset or SelectedSubTile
        autotile_engine: Optional[Any] = None,
        stamp_manager: Optional[Any] = None,
        set_manager: Optional[Any] = None,
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

        self.brush_settings = BrushSettings()
        self.clipboard_tiles: Dict[Tuple[int, int], MapItem] = {}
        self.selected_object_ids: List[str] = []


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
    def create_item_from_selection(
        col: int,
        row: int,
        context: ToolContext,
        override_asset: Optional[Any] = None,
    ) -> Optional[MapItem]:
        sel = override_asset if override_asset is not None else context.selected_asset
        if not sel:
            return None

        # Brush settings random rotation/flip/jitter
        bs = context.brush_settings
        rot, fx, fy, jx, jy = bs.get_random_transform()

        if isinstance(sel, SelectedSubTile):
            return MapItem(
                asset_id=sel.asset_id,
                col=col,
                row=row,
                item_type=ItemType.TILE,
                offset_x=jx,
                offset_y=jy,
                source_x=sel.sub_x,
                source_y=sel.sub_y,
                source_w=sel.sub_w,
                source_h=sel.sub_h,
                dest_w=context.project.tile_size,
                dest_h=context.project.tile_size,
                rotation=rot,
                flip_x=fx,
                flip_y=fy,
            )
        elif isinstance(sel, Asset):
            if sel.asset_type == AssetType.TILESET and sel.tileset_config:
                sx, sy, sw, sh = sel.get_tile_rect(0, 0)
                return MapItem(
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
                    dest_w=context.project.tile_size,
                    dest_h=context.project.tile_size,
                    rotation=rot,
                    flip_x=fx,
                    flip_y=fy,
                )
            else:
                is_large = sel.width != context.project.tile_size or sel.height != context.project.tile_size
                return MapItem(
                    asset_id=sel.id,
                    col=col,
                    row=row,
                    item_type=ItemType.OBJECT if is_large else ItemType.TILE,
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
        return None
