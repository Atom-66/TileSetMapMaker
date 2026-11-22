from typing import List, Dict, Tuple, Optional
from .base import BaseTool, ToolContext
from ...models.layer import MapItem
from ..history import TileBatchCommand


class LineTool(BaseTool):
    """Draws a straight line of tiles using Bresenham's algorithm."""

    def __init__(self):
        super().__init__("Linia", shortcut="L")
        self.start_col: int = 0
        self.start_row: int = 0
        self.current_col: int = 0
        self.current_row: int = 0

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        if not context.active_layer or context.active_layer.locked:
            return
        self.is_active = True
        self.start_col = col
        self.start_row = row
        self.current_col = col
        self.current_row = row

    def on_drag(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        self.current_col = col
        self.current_row = row

    def _get_line_coords(self) -> List[Tuple[int, int]]:
        x0, y0 = self.start_col, self.start_row
        x1, y1 = self.current_col, self.current_row
        points = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            points.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
        return points

    def on_release(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active or not context.active_layer:
            return
        self.is_active = False
        self.current_col = col
        self.current_row = row

        template = self.create_item_from_selection(col, row, context)
        if not template:
            return

        points = self._get_line_coords()
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}

        w = context.project.map_width
        h = context.project.map_height
        for px, py in points:
            if 0 <= px < w and 0 <= py < h:
                prev = context.active_layer.get_tile(px, py)
                prev_clone = prev.clone() if prev else None
                new_tile = template.clone()
                new_tile.col = px
                new_tile.row = py
                context.active_layer.set_tile(px, py, new_tile)
                changes[(px, py)] = (prev_clone, new_tile.clone())

        if changes:
            cmd = TileBatchCommand(
                context.project,
                context.active_layer.id,
                changes,
                description="Rysowanie linii",
            )
            context.history_manager.push(cmd)

    def get_preview_items(self, context: ToolContext) -> List[MapItem]:
        if not self.is_active:
            item = self.create_item_from_selection(context.cursor_col, context.cursor_row, context)
            return [item] if item else []

        template = self.create_item_from_selection(self.start_col, self.start_row, context)
        if not template:
            return []

        previews = []
        for px, py in self._get_line_coords():
            it = template.clone()
            it.col = px
            it.row = py
            previews.append(it)
        return previews


class RectTool(BaseTool):
    """Draws a rectangular area of tiles (filled or outline)."""

    def __init__(self, filled: bool = True):
        super().__init__("Prostokąt", shortcut="U")
        self.filled = filled
        self.start_col: int = 0
        self.start_row: int = 0
        self.current_col: int = 0
        self.current_row: int = 0

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        if not context.active_layer or context.active_layer.locked:
            return
        self.is_active = True
        self.start_col = col
        self.start_row = row
        self.current_col = col
        self.current_row = row

    def on_drag(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        self.current_col = col
        self.current_row = row

    def _get_rect_coords(self) -> List[Tuple[int, int]]:
        c1, c2 = min(self.start_col, self.current_col), max(self.start_col, self.current_col)
        r1, r2 = min(self.start_row, self.current_row), max(self.start_row, self.current_row)
        coords = []
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                if self.filled or (r == r1 or r == r2 or c == c1 or c == c2):
                    coords.append((c, r))
        return coords

    def on_release(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active or not context.active_layer:
            return
        self.is_active = False
        self.current_col = col
        self.current_row = row

        template = self.create_item_from_selection(col, row, context)
        if not template:
            return

        coords = self._get_rect_coords()
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}
        w = context.project.map_width
        h = context.project.map_height

        for px, py in coords:
            if 0 <= px < w and 0 <= py < h:
                prev = context.active_layer.get_tile(px, py)
                prev_clone = prev.clone() if prev else None
                new_tile = template.clone()
                new_tile.col = px
                new_tile.row = py
                context.active_layer.set_tile(px, py, new_tile)
                changes[(px, py)] = (prev_clone, new_tile.clone())

        if changes:
            cmd = TileBatchCommand(
                context.project,
                context.active_layer.id,
                changes,
                description="Rysowanie prostokąta",
            )
            context.history_manager.push(cmd)

    def get_preview_items(self, context: ToolContext) -> List[MapItem]:
        if not self.is_active:
            item = self.create_item_from_selection(context.cursor_col, context.cursor_row, context)
            return [item] if item else []

        template = self.create_item_from_selection(self.start_col, self.start_row, context)
        if not template:
            return []

        previews = []
        for px, py in self._get_rect_coords():
            it = template.clone()
            it.col = px
            it.row = py
            previews.append(it)
        return previews
