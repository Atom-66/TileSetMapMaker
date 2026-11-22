from typing import Dict, Tuple, Optional, List
from PyQt6.QtCore import QRect
from .base import BaseTool, ToolContext
from ...models.layer import MapItem
from ...models.stamp import StampPreset
from ..history import TileBatchCommand


class SelectTool(BaseTool):
    """Selects a rectangular area of tiles for copying, moving, saving as stamp, or deleting."""

    def __init__(self):
        super().__init__("Zaznaczanie", shortcut="S")
        self.start_col: int = 0
        self.start_row: int = 0
        self.current_col: int = 0
        self.current_row: int = 0
        self.selection_rect: Optional[QRect] = None

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        self.is_active = True
        self.start_col = col
        self.start_row = row
        self.current_col = col
        self.current_row = row
        self.selection_rect = QRect(col, row, 1, 1)

    def on_drag(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        self.current_col = col
        self.current_row = row
        c1, c2 = min(self.start_col, self.current_col), max(self.start_col, self.current_col)
        r1, r2 = min(self.start_row, self.current_row), max(self.start_row, self.current_row)
        self.selection_rect = QRect(c1, r1, c2 - c1 + 1, r2 - r1 + 1)

    def on_release(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        self.is_active = False
        self.current_col = col
        self.current_row = row
        c1, c2 = min(self.start_col, self.current_col), max(self.start_col, self.current_col)
        r1, r2 = min(self.start_row, self.current_row), max(self.start_row, self.current_row)
        self.selection_rect = QRect(c1, r1, c2 - c1 + 1, r2 - r1 + 1)

    def clear_selection(self) -> None:
        self.selection_rect = None

    def copy_selection(self, context: ToolContext) -> None:
        """Copies tiles in the selection rectangle to the clipboard."""
        if not self.selection_rect or not context.active_layer:
            return
        r = self.selection_rect
        context.clipboard_tiles.clear()
        for row in range(r.top(), r.bottom() + 1):
            for col in range(r.left(), r.right() + 1):
                item = context.active_layer.get_tile(col, row)
                if item:
                    rel_col = col - r.left()
                    rel_row = row - r.top()
                    context.clipboard_tiles[(rel_col, rel_row)] = item.clone()

    def save_as_stamp_preset(self, name: str, context: ToolContext) -> Optional[StampPreset]:
        """Saves current selection to the persistent StampManager."""
        self.copy_selection(context)
        if not context.clipboard_tiles or not context.stamp_manager or not self.selection_rect:
            return None

        preset = StampPreset(
            name=name,
            items=dict(context.clipboard_tiles),
            width=self.selection_rect.width(),
            height=self.selection_rect.height(),
        )
        context.stamp_manager.add_stamp(preset)
        return preset

    def delete_selection(self, context: ToolContext) -> None:
        """Deletes all tiles in the selection rectangle from the active layer."""
        if not self.selection_rect or not context.active_layer or context.active_layer.locked:
            return
        r = self.selection_rect
        layer = context.active_layer
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}

        for row in range(r.top(), r.bottom() + 1):
            for col in range(r.left(), r.right() + 1):
                tile = layer.get_tile(col, row)
                if tile:
                    changes[(col, row)] = (tile.clone(), None)
                    layer.remove_tile(col, row)

        if changes:
            cmd = TileBatchCommand(
                context.project,
                layer.id,
                changes,
                description="Usunięcie zaznaczenia",
            )
            context.history_manager.push(cmd)


class StampTool(BaseTool):
    """
    Stamps multi-tile patterns or saved presets onto the map.
    Supports rotation (R) and horizontal/vertical flipping (H/V).
    """

    def __init__(self):
        super().__init__("Stempel", shortcut="T")
        self.rotation: int = 0
        self.flip_x: bool = False
        self.flip_y: bool = False

    def rotate_clockwise(self, context: ToolContext) -> None:
        self.rotation = (self.rotation + 90) % 360
        active_stamp = context.stamp_manager.get_active_stamp() if context.stamp_manager else None
        if active_stamp:
            active_stamp.rotate_90()

    def flip_h(self, context: ToolContext) -> None:
        self.flip_x = not self.flip_x
        active_stamp = context.stamp_manager.get_active_stamp() if context.stamp_manager else None
        if active_stamp:
            active_stamp.flip_horizontal()

    def flip_v(self, context: ToolContext) -> None:
        self.flip_y = not self.flip_y
        active_stamp = context.stamp_manager.get_active_stamp() if context.stamp_manager else None
        if active_stamp:
            active_stamp.flip_vertical()

    def _get_items(self, context: ToolContext) -> Dict[Tuple[int, int], MapItem]:
        active_stamp = context.stamp_manager.get_active_stamp() if context.stamp_manager else None
        if active_stamp and active_stamp.items:
            return active_stamp.items
        return context.clipboard_tiles

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        if not context.active_layer or context.active_layer.locked:
            return
        items = self._get_items(context)
        if not items:
            return

        layer = context.active_layer
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}
        w = context.project.map_width
        h = context.project.map_height

        for (rel_c, rel_r), template in items.items():
            tc = col + rel_c
            tr = row + rel_r
            if 0 <= tc < w and 0 <= tr < h:
                prev = layer.get_tile(tc, tr)
                prev_clone = prev.clone() if prev else None
                new_item = template.clone()
                new_item.col = tc
                new_item.row = tr
                layer.set_tile(tc, tr, new_item)
                changes[(tc, tr)] = (prev_clone, new_item.clone())

        if changes:
            cmd = TileBatchCommand(
                context.project,
                layer.id,
                changes,
                description="Użycie stempla",
            )
            context.history_manager.push(cmd)

    def get_preview_items(self, context: ToolContext) -> List[MapItem]:
        items = self._get_items(context)
        if not items:
            return []
        previews = []
        for (rel_c, rel_r), item in items.items():
            clone = item.clone()
            clone.col = context.cursor_col + rel_c
            clone.row = context.cursor_row + rel_r
            previews.append(clone)
        return previews
