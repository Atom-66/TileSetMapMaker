from typing import Optional, List
from .base import BaseTool, ToolContext
from ...models.asset import Asset, AssetType, SelectedSubTile
from ...models.layer import MapItem


class EyedropperTool(BaseTool):
    """Picks a tile or asset from the map canvas and sets it as the active asset."""

    def __init__(self):
        super().__init__("Pipeta", shortcut="I")

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        self._pick_at(col, row, context)

    def _pick_at(self, col: int, row: int, context: ToolContext) -> None:
        # Search active layer first, or scan visible layers top to bottom
        target_item: Optional[MapItem] = None
        if context.active_layer and not context.active_layer.locked:
            target_item = context.active_layer.get_tile(col, row)

        if not target_item:
            # Check other visible layers from top to bottom
            for layer in reversed(context.project.layers):
                if layer.visible and (col, row) in layer.tiles:
                    target_item = layer.tiles[(col, row)]
                    break

        # Also check freeform objects on layer
        if not target_item and context.active_layer:
            for obj in reversed(context.active_layer.objects):
                if obj.col == col and obj.row == row:
                    target_item = obj
                    break

        if not target_item:
            return

        asset = context.asset_manager.get_asset(target_item.asset_id)
        if not asset:
            return

        if asset.asset_type == AssetType.TILESET and asset.tileset_config:
            cfg = asset.tileset_config
            tw = target_item.source_w if target_item.source_w > 0 else cfg.tile_width
            th = target_item.source_h if target_item.source_h > 0 else cfg.tile_height
            step_w = cfg.tile_width + cfg.spacing_x
            step_h = cfg.tile_height + cfg.spacing_y
            col = max(0, (target_item.source_x - cfg.start_x - cfg.margin_x) // step_w) if step_w > 0 else 0
            row = max(0, (target_item.source_y - cfg.start_y - cfg.margin_y) // step_h) if step_h > 0 else 0
            sub_tile = SelectedSubTile(
                asset_id=asset.id,
                col=col,
                row=row,
                cols_count=1,
                rows_count=1,
                sub_x=target_item.source_x,
                sub_y=target_item.source_y,
                sub_w=tw,
                sub_h=th,
                tile_width=cfg.tile_width,
                tile_height=cfg.tile_height,
                spacing_x=cfg.spacing_x,
                spacing_y=cfg.spacing_y,
                asset_name=asset.name,
            )
            context.asset_manager.select_asset(asset, sub_tile)
        else:
            context.asset_manager.select_asset(asset)
