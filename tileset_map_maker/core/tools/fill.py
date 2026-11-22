from collections import deque
from typing import Dict, Tuple, Optional, Set
from .base import BaseTool, ToolContext
from ...models.layer import MapItem
from ..history import TileBatchCommand


class FillTool(BaseTool):
    """Fills a contiguous area of matching tiles or empty cells."""

    def __init__(self):
        super().__init__("Wypełnianie", shortcut="G")

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        layer = context.active_layer
        if not layer or layer.locked:
            return

        w = context.project.map_width
        h = context.project.map_height
        if not (0 <= col < w and 0 <= row < h):
            return

        replacement_template = self.create_item_from_selection(col, row, context)
        if not replacement_template:
            return

        target_tile = layer.get_tile(col, row)

        # Match criteria: same asset_id and source_rect, or both empty
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

        # Check if already the replacement
        if (
            target_tile
            and target_tile.asset_id == replacement_template.asset_id
            and target_tile.source_x == replacement_template.source_x
            and target_tile.source_y == replacement_template.source_y
        ):
            return

        queue = deque([(col, row)])
        visited: Set[Tuple[int, int]] = {(col, row)}
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}

        while queue:
            cx, cy = queue.popleft()
            prev_tile = layer.get_tile(cx, cy)
            prev_clone = prev_tile.clone() if prev_tile else None

            new_tile = replacement_template.clone()
            new_tile.col = cx
            new_tile.row = cy
            layer.set_tile(cx, cy, new_tile)
            changes[(cx, cy)] = (prev_clone, new_tile.clone())

            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                    if is_match(nx, ny):
                        visited.add((nx, ny))
                        queue.append((nx, ny))

        if changes:
            cmd = TileBatchCommand(
                context.project,
                layer.id,
                changes,
                description="Wypełnienie wiadrem",
            )
            context.history_manager.push(cmd)
