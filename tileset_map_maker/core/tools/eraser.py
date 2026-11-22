from typing import Dict, Tuple, Optional, List
from .base import BaseTool, ToolContext
from ...models.layer import MapItem
from ..history import TileBatchCommand, ObjectRemoveCommand


class EraserTool(BaseTool):
    """Erases tiles or objects from active layer."""

    def __init__(self):
        super().__init__("Gumka", shortcut="E")
        self.session_changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}
        self.removed_objects: List[MapItem] = []

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        if not context.active_layer or context.active_layer.locked:
            return
        self.is_active = True
        self.session_changes.clear()
        self.removed_objects.clear()
        self._erase_at(col, row, context)

    def on_drag(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active or not context.active_layer or context.active_layer.locked:
            return
        self._erase_at(col, row, context)

    def _erase_at(self, col: int, row: int, context: ToolContext) -> None:
        layer = context.active_layer
        if not layer:
            return

        # 1. Erase grid tile
        coord = (col, row)
        if coord not in self.session_changes:
            prev = layer.get_tile(col, row)
            if prev:
                layer.remove_tile(col, row)
                self.session_changes[coord] = (prev.clone(), None)

        # 2. Erase objects intersecting cell
        ts = context.project.tile_size
        cell_x = col * ts
        cell_y = row * ts
        for obj in list(layer.objects):
            obj_x = obj.col * ts + obj.offset_x
            obj_y = obj.row * ts + obj.offset_y
            if (
                cell_x < obj_x + obj.dest_w
                and cell_x + ts > obj_x
                and cell_y < obj_y + obj.dest_h
                and cell_y + ts > obj_y
            ):
                layer.remove_object(obj.id)
                self.removed_objects.append(obj)

    def on_release(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        self.is_active = False

        if self.session_changes and context.active_layer:
            cmd = TileBatchCommand(
                context.project,
                context.active_layer.id,
                dict(self.session_changes),
                description="Użycie gumki",
            )
            context.history_manager.push(cmd)

        for obj in self.removed_objects:
            cmd = ObjectRemoveCommand(
                context.project,
                context.active_layer.id,
                obj,
                description="Usunięcie obiektu gumką",
            )
            context.history_manager.push(cmd)

        self.session_changes.clear()
        self.removed_objects.clear()
