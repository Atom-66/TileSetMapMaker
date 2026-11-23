from collections import deque
from typing import Dict, Tuple, Optional, Set
from PyQt6.QtCore import QRect
from .base import BaseTool, ToolContext
from ...models.layer import MapItem
from ..history import TileBatchCommand


class WandTool(BaseTool):
    """
    Magic Wand tool (TASK-606).
    Selects contiguous matching tiles (or empty cells) using 4-connected flood fill.
    Supports copying, deleting, and filling the selected area.
    """

    def __init__(self):
        super().__init__("Różdżka", shortcut="W")
        self.selected_cells: Set[Tuple[int, int]] = set()
        self.selection_rect: Optional[QRect] = None

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        layer = context.active_layer
        if not layer or layer.locked or not context.project.get_effective_visible(layer):
            return

        w = context.project.map_width
        h = context.project.map_height
        if not (0 <= col < w and 0 <= row < h):
            return

        target_tile = layer.get_tile(col, row)

        def is_match(c: int, r: int) -> bool:
            curr = layer.get_tile(c, r)
            if target_tile is None:
                return curr is None
            if curr is None:
                return False
            return (
                curr.asset_id == target_tile.asset_id
                and curr.source_x == target_tile.source_x
                and curr.source_y == target_tile.source_y
            )

        queue = deque([(col, row)])
        visited: Set[Tuple[int, int]] = {(col, row)}

        while queue:
            cx, cy = queue.popleft()
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                    if is_match(nx, ny):
                        visited.add((nx, ny))
                        queue.append((nx, ny))

        self.selected_cells = visited
        context.selected_cells = set(self.selected_cells)

        if visited:
            min_c = min(c for c, r in visited)
            max_c = max(c for c, r in visited)
            min_r = min(r for c, r in visited)
            max_r = max(r for c, r in visited)
            self.selection_rect = QRect(min_c, min_r, max_c - min_c + 1, max_r - min_r + 1)
        else:
            self.selection_rect = None

    def clear_selection(self, context: Optional[ToolContext] = None) -> None:
        self.selected_cells.clear()
        self.selection_rect = None
        if context:
            context.selected_cells.clear()

    def delete_selection(self, context: ToolContext) -> None:
        """Deletes all selected cells on the active layer."""
        if not self.selected_cells or not context.active_layer or context.active_layer.locked:
            return
        layer = context.active_layer
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}

        for col, row in self.selected_cells:
            tile = layer.get_tile(col, row)
            if tile:
                changes[(col, row)] = (tile.clone(), None)
                layer.remove_tile(col, row)

        if changes:
            cmd = TileBatchCommand(
                context.project,
                layer.id,
                changes,
                description="Usunięcie zaznaczenia różdżką",
            )
            context.history_manager.push(cmd)

    def copy_selection(self, context: ToolContext) -> None:
        """Copies tiles in the wand selection to the clipboard."""
        if not self.selected_cells or not context.active_layer:
            return
        min_c = min(c for c, r in self.selected_cells)
        min_r = min(r for c, r in self.selected_cells)
        context.clipboard_tiles.clear()

        for col, row in self.selected_cells:
            item = context.active_layer.get_tile(col, row)
            if item:
                context.clipboard_tiles[(col - min_c, row - min_r)] = item.clone()
