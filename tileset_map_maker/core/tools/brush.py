from typing import Dict, Tuple, Optional, List
from .base import BaseTool, ToolContext
from ...models.layer import MapItem, ItemType
from ..history import TileBatchCommand, ObjectAddCommand


class BrushTool(BaseTool):
    """
    Places tiles or objects on the active layer with click or drag.
    Supports adjustable brush size, multi-tile block selections (Tiled-style),
    random variants, random transforms, and auto-tiling.
    """

    def __init__(self):
        super().__init__("Pędzel", shortcut="B")
        self.session_changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}
        self.placed_objects: List[MapItem] = []
        self.painted_coords: set[Tuple[int, int]] = set()

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        layer = context.active_layer
        if not layer or layer.locked or not context.project.get_effective_visible(layer):
            return
        self.is_active = True
        self.session_changes.clear()
        self.placed_objects.clear()
        self.painted_coords.clear()
        self._apply_at(col, row, context)

    def on_drag(self, col: int, row: int, context: ToolContext) -> None:
        layer = context.active_layer
        if not self.is_active or not layer or layer.locked or not context.project.get_effective_visible(layer):
            return
        self._apply_at(col, row, context)

    def _apply_at(self, col: int, row: int, context: ToolContext) -> None:
        layer = context.active_layer
        if not layer:
            return

        bs = context.brush_settings
        if bs.random_variant and bs.consume_gap():
            return
        radius = (bs.size - 1) // 2

        # Footprint iteration (brush size)
        for dr in range(-radius, radius + (bs.size % 2 == 0) + 1):
            for dc in range(-radius, radius + (bs.size % 2 == 0) + 1):
                tc = col + dc
                tr = row + dr

                # Pick variant (with optional adjacent avoidance)
                adj = None
                if bs.avoid_adjacent:
                    adj = [
                        layer.get_tile(tc - 1, tr),
                        layer.get_tile(tc + 1, tr),
                        layer.get_tile(tc, tr - 1),
                        layer.get_tile(tc, tr + 1),
                    ]
                if getattr(bs, "selected_autotile", None):
                    variant = bs.selected_autotile
                else:
                    variant = bs.pick_variant(context.selected_asset, avoid_adjacent_items=adj)
                items = self.create_items_from_selection(tc, tr, context, override_asset=variant)

                for item in items:
                    # Map boundary check
                    if not (0 <= item.col < context.project.map_width and 0 <= item.row < context.project.map_height):
                        continue

                    if item.item_type == ItemType.OBJECT:
                        layer.add_object(item)
                        self.placed_objects.append(item)
                        context.project.is_modified = True
                    else:
                        coord = (item.col, item.row)
                        if coord not in self.session_changes:
                            prev = layer.get_tile(item.col, item.row)
                            prev_clone = prev.clone() if prev else None

                            rpg_at = None
                            if context.autotile_engine:
                                rpg_at = (
                                    context.autotile_engine.get_rpg_autotile(item.asset_id)
                                    or context.autotile_engine.get_rpg_autotile(item.terrain_type)
                                )
                                if rpg_at:
                                    # Transactional safety: never overwrite existing tiles if autotile cannot render
                                    if hasattr(context.autotile_engine, "can_render_autotile") and not context.autotile_engine.can_render_autotile(
                                        rpg_at, context.asset_manager
                                    ):
                                        continue
                                    if context.asset_manager and hasattr(context.asset_manager, "register_rpg_autotile"):
                                        context.asset_manager.register_rpg_autotile(rpg_at)
                                    item.is_auto_tiled = True
                                    item.asset_id = rpg_at.id
                                    item.terrain_type = rpg_at.terrain_type

                            layer.set_tile(item.col, item.row, item)
                            self.session_changes[coord] = (prev_clone, item.clone())
                            self.painted_coords.add(coord)

                            if rpg_at and context.autotile_engine:
                                stroke_changes = context.autotile_engine.apply_rpg_autotile_stroke(
                                    layer,
                                    [coord],
                                    rpg_at,
                                    context.project,
                                    asset_manager=context.asset_manager,
                                )
                                for ch_coord, (ch_before, ch_after) in stroke_changes.items():
                                    if ch_coord in self.session_changes:
                                        init_before, _ = self.session_changes[ch_coord]
                                        self.session_changes[ch_coord] = (init_before, ch_after)
                                    else:
                                        self.session_changes[ch_coord] = (ch_before, ch_after)

    def on_release(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        self.is_active = False

        # Apply auto-tiling ripple if enabled
        bs = context.brush_settings
        if context.autotile_engine and context.active_layer and self.painted_coords:
            sample_coord = next(iter(self.painted_coords))
            sample_tile = context.active_layer.get_tile(*sample_coord)
            rpg_at = None
            if sample_tile:
                rpg_at = (
                    context.autotile_engine.get_rpg_autotile(sample_tile.asset_id)
                    or context.autotile_engine.get_rpg_autotile(sample_tile.terrain_type)
                )
            if rpg_at:
                autotile_changes = context.autotile_engine.apply_rpg_autotile_stroke(
                    context.active_layer,
                    list(self.painted_coords),
                    rpg_at,
                    context.project,
                    asset_manager=context.asset_manager,
                )
                for coord, (before, after) in autotile_changes.items():
                    if coord in self.session_changes:
                        initial_before, _ = self.session_changes[coord]
                        self.session_changes[coord] = (initial_before, after)
                    else:
                        self.session_changes[coord] = (before, after)

        if self.session_changes and context.active_layer and context.history_manager:
            cmd = TileBatchCommand(
                context.project,
                context.active_layer.id,
                dict(self.session_changes),
                description="Rysowanie pędzlem",
            )
            context.history_manager.push(cmd)

        if context.active_layer and context.history_manager:
            for obj in self.placed_objects:
                cmd = ObjectAddCommand(
                    context.project,
                    context.active_layer.id,
                    obj,
                    description="Dodanie obiektu pędzlem",
                )
                context.history_manager.push(cmd)

        self.session_changes.clear()
        self.placed_objects.clear()
        self.painted_coords.clear()

    def get_preview_items(self, context: ToolContext) -> List[MapItem]:
        layer = context.active_layer
        if not layer or layer.locked or not context.project.get_effective_visible(layer):
            return []
        bs = context.brush_settings
        radius = (bs.size - 1) // 2
        previews = []
        for dr in range(-radius, radius + (bs.size % 2 == 0) + 1):
            for dc in range(-radius, radius + (bs.size % 2 == 0) + 1):
                tc = context.cursor_col + dc
                tr = context.cursor_row + dr
                items = self.create_items_from_selection(tc, tr, context)
                previews.extend(items)
        return previews
