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
        self.polygon_points: List[Tuple[int, int]] = []
        self.selection_cells: set[Tuple[int, int]] = set()
        self.moving_selection = False
        self.move_preview = (0, 0)

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        self.is_active = True
        self.start_col = col
        self.start_row = row
        self.current_col = col
        self.current_row = row
        self.moving_selection = False
        context.selected_cells.clear()
        self.selection_rect = QRect(col, row, 1, 1)
        context.selected_cells = {(col, row)}
        self.polygon_points.clear()
        self.selection_cells.clear()

    def on_drag(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        if self.moving_selection:
            self.move_preview = (col - self.start_col, row - self.start_row)
            return
        self.current_col = col
        self.current_row = row
        c1, c2 = min(self.start_col, self.current_col), max(self.start_col, self.current_col)
        r1, r2 = min(self.start_row, self.current_row), max(self.start_row, self.current_row)
        self.selection_rect = QRect(c1, r1, c2 - c1 + 1, r2 - r1 + 1)
        context.selected_cells = self._selected_cells()

    def on_release(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        self.is_active = False
        if self.moving_selection:
            dx, dy = col - self.start_col, row - self.start_row
            self.moving_selection = False
            self.move_preview = (0, 0)
            if dx or dy:
                self.move_selection(dx, dy, context)
            return
        self.current_col = col
        self.current_row = row
        c1, c2 = min(self.start_col, self.current_col), max(self.start_col, self.current_col)
        r1, r2 = min(self.start_row, self.current_row), max(self.start_row, self.current_row)
        self.selection_rect = QRect(c1, r1, c2 - c1 + 1, r2 - r1 + 1)
        context.selected_cells = self._selected_cells()

    def clear_selection(self) -> None:
        self.selection_rect = None
        self.polygon_points.clear()
        self.selection_cells.clear()
        self.moving_selection = False
        self.move_preview = (0, 0)

    def set_polygon_selection(self, points: List[Tuple[int, int]]) -> bool:
        if len(points) < 3:
            return False
        min_col = min(point[0] for point in points)
        max_col = max(point[0] for point in points)
        min_row = min(point[1] for point in points)
        max_row = max(point[1] for point in points)
        self.polygon_points = list(points)
        self.selection_rect = QRect(
            min_col, min_row, max_col - min_col + 1, max_row - min_row + 1
        )
        self.selection_cells = {
            (col, row)
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
            if self._point_in_polygon(col + 0.5, row + 0.5, points)
        }
        return bool(self.selection_cells)

    @staticmethod
    def _point_in_polygon(
        x: float, y: float, polygon: List[Tuple[int, int]]
    ) -> bool:
        inside = False
        previous = polygon[-1]
        for current in polygon:
            x1, y1 = previous
            x2, y2 = current
            if (y1 > y) != (y2 > y):
                crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
                if x < crossing_x:
                    inside = not inside
            previous = current
        return inside

    def _selected_cells(self) -> set[Tuple[int, int]]:
        if self.selection_cells:
            return set(self.selection_cells)
        if not self.selection_rect:
            return set()
        rect = self.selection_rect
        return {
            (col, row)
            for row in range(rect.top(), rect.bottom() + 1)
            for col in range(rect.left(), rect.right() + 1)
        }

    def copy_selection(self, context: ToolContext) -> None:
        """Copies tiles in the selection rectangle to the clipboard."""
        if not self.selection_rect or not context.active_layer:
            return
        r = self.selection_rect
        context.clipboard_tiles.clear()
        for col, row in self._selected_cells():
            item = context.active_layer.get_tile(col, row)
            if item:
                rel_col = col - r.left()
                rel_row = row - r.top()
                context.clipboard_tiles[(rel_col, rel_row)] = item.clone()

    def get_preview_items(self, context: ToolContext) -> List[MapItem]:
        if not self.moving_selection or not context.active_layer:
            return []
        dx, dy = self.move_preview
        if not dx and not dy:
            return []
        previews = []
        for col, row in self._selected_cells():
            item = context.active_layer.get_tile(col, row)
            if item:
                preview = item.clone()
                preview.col = col + dx
                preview.row = row + dy
                previews.append(preview)
        return previews

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

        for col, row in self._selected_cells():
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

    def _transform_selection(
        self,
        context: ToolContext,
        position_transform,
        item_transform,
        description: str,
    ) -> bool:
        if not self.selection_rect or not context.active_layer:
            return False
        layer = context.active_layer
        if layer.locked:
            return False

        changes: Dict[
            Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]
        ] = {}
        selected: Dict[Tuple[int, int], MapItem] = {}
        for col, row in self._selected_cells():
            item = layer.get_tile(col, row)
            if item:
                selected[(col, row)] = item.clone()

        transformed: Dict[Tuple[int, int], MapItem] = {}
        for position, item in selected.items():
            new_col, new_row = position_transform(*position)
            if not (
                0 <= new_col < context.project.map_width
                and 0 <= new_row < context.project.map_height
            ):
                return False
            transformed[(new_col, new_row)] = item_transform(item.clone())

        for position in set(selected) | set(transformed):
            before = layer.get_tile(*position)
            changes[position] = (
                before.clone() if before else None,
                transformed[position].clone() if position in transformed else None,
            )
            if position in transformed:
                layer.set_tile(*position, transformed[position])
            else:
                layer.remove_tile(*position)

        if not changes:
            return False
        if self.selection_cells:
            self.selection_cells = {
                position_transform(col, row) for col, row in self.selection_cells
            }
            self.polygon_points = [
                position_transform(col, row) for col, row in self.polygon_points
            ]
        context.history_manager.push(
            TileBatchCommand(context.project, layer.id, changes, description)
        )
        return True

    def move_selection(self, dx: int, dy: int, context: ToolContext) -> bool:
        if not self.selection_rect:
            return False
        moved = self._transform_selection(
            context,
            lambda col, row: (col + dx, row + dy),
            lambda item: item,
            "Przesunięcie zaznaczenia",
        )
        if moved:
            self.selection_rect.translate(dx, dy)
        return moved

    def rotate_selection_clockwise(self, context: ToolContext) -> bool:
        if not self.selection_rect:
            return False
        rect = self.selection_rect

        def rotate_position(col: int, row: int) -> Tuple[int, int]:
            rel_col, rel_row = col - rect.left(), row - rect.top()
            return rect.left() + rect.height() - 1 - rel_row, rect.top() + rel_col

        def rotate_item(item: MapItem) -> MapItem:
            item.rotation = (item.rotation + 90.0) % 360.0
            return item

        rotated = self._transform_selection(
            context,
            rotate_position,
            rotate_item,
            "Obrót zaznaczenia",
        )
        if rotated:
            self.selection_rect = QRect(
                rect.left(), rect.top(), rect.height(), rect.width()
            )
        return rotated

    def flip_selection_horizontal(self, context: ToolContext) -> bool:
        if not self.selection_rect:
            return False
        rect = self.selection_rect
        return self._transform_selection(
            context,
            lambda col, row: (rect.right() - (col - rect.left()), row),
            lambda item: self._toggle_flip(item, "x"),
            "Odbicie zaznaczenia poziomo",
        )

    def flip_selection_vertical(self, context: ToolContext) -> bool:
        if not self.selection_rect:
            return False
        rect = self.selection_rect
        return self._transform_selection(
            context,
            lambda col, row: (col, rect.bottom() - (row - rect.top())),
            lambda item: self._toggle_flip(item, "y"),
            "Odbicie zaznaczenia pionowo",
        )

    @staticmethod
    def _toggle_flip(item: MapItem, axis: str) -> MapItem:
        if axis == "x":
            item.flip_x = not item.flip_x
        else:
            item.flip_y = not item.flip_y
        return item


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
