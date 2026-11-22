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

        if not target_item:
            return

        asset = context.asset_manager.get_asset(target_item.asset_id)
        if not asset:
            return

        if asset.asset_type == AssetType.TILESET and asset.tileset_config:
            cfg = asset.tileset_config
            sub_tile = SelectedSubTile(
                asset_id=asset.id,
                col=0,
                row=0,
                sub_x=target_item.source_x,
                sub_y=target_item.source_y,
                sub_w=target_item.source_w,
                sub_h=target_item.source_h,
            )
            context.asset_manager.select_asset(asset, sub_tile)
        else:
            context.asset_manager.select_asset(asset)
