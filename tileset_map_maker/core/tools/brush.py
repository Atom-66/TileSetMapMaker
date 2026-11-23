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
        self.painted_coords: List[Tuple[int, int]] = []

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
        radius = (bs.size - 1) // 2

        # Footprint iteration (brush size)
        for dr in range(-radius, radius + (bs.size % 2 == 0) + 1):
            for dc in range(-radius, radius + (bs.size % 2 == 0) + 1):
                tc = col + dc
                tr = row + dr

                # Pick variant
                variant = bs.pick_variant(context.selected_asset)
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

                            if bs.auto_tile_enabled and context.autotile_engine:
                                item.is_auto_tiled = True
                                ruleset = context.autotile_engine.get_active_ruleset()
                                if ruleset:
                                    item.terrain_type = ruleset.terrain_type

                            layer.set_tile(item.col, item.row, item)
                            self.session_changes[coord] = (prev_clone, item.clone())
                            self.painted_coords.append(coord)

    def on_release(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        self.is_active = False

        # Apply auto-tiling ripple if enabled
        bs = context.brush_settings
        if bs.auto_tile_enabled and context.autotile_engine and context.active_layer:
            ruleset = context.autotile_engine.get_active_ruleset()
            if ruleset:
                autotile_changes = context.autotile_engine.apply_autotile_stroke(
                    context.active_layer,
                    self.painted_coords,
                    ruleset,
                    context.project,
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
