from typing import Dict, Tuple, Optional, List
from PyQt6.QtCore import QRect, QPoint, Qt
from PyQt6.QtGui import QRegion, QTransform
from .base import BaseTool, ToolContext
from ...models.layer import MapItem, ItemType
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
        self.region = QRegion()
        self.selection_owner = None
        self._initial_region = QRegion()
        self._selection_mode = "replace"
        self.pasting = False
        self.last_error = ""

    def _region(self) -> QRegion:
        if not self.region.isEmpty():
            return QRegion(self.region)
        if self.selection_cells:
            result = QRegion()
            for col, row in self.selection_cells:
                result = result.united(QRegion(QRect(col, row, 1, 1)))
            return result
        return QRegion(self.selection_rect) if self.selection_rect else QRegion()

    def _set_region(self, region: QRegion, context: ToolContext) -> None:
        self.region = QRegion(region)
        self.selection_rect = None if region.isEmpty() else region.boundingRect()
        self.selection_cells.clear()
        self.polygon_points.clear()
        context.selected_cells.clear()
        if self.selection_rect and self.selection_rect.width() * self.selection_rect.height() <= 10000:
            r = self.selection_rect
            context.selected_cells = {
                (col, row) for row in range(r.top(), r.bottom() + 1)
                for col in range(r.left(), r.right() + 1)
                if region.contains(QPoint(col, row))
            }

    def _valid_layer(self, context: ToolContext, edit: bool = False) -> bool:
        layer = context.active_layer
        return bool(
            layer and layer.layer_type == "tile" and not layer.is_group
            and layer is context.project.get_active_layer()
            and context.project.get_effective_visible(layer)
            and (not edit or not context.project.get_effective_locked(layer))
            and (self.selection_owner is None or self.selection_owner == (context.project.active_map_id, layer.id))
        )

    def _bind(self, context: ToolContext) -> None:
        layer = context.active_layer
        self.selection_owner = (context.project.active_map_id, layer.id) if layer else None

    @staticmethod
    def _position_item(item: MapItem, col: int, row: int, tile_size: int) -> None:
        if item.free_x is not None:
            item.free_x += (col - item.col) * tile_size
        if item.free_y is not None:
            item.free_y += (row - item.row) * tile_size
        item.col, item.row = col, row

    def _bounded_rect(self, col: int, row: int, context: ToolContext) -> QRect:
        x1 = max(0, min(self.start_col, col))
        y1 = max(0, min(self.start_row, row))
        x2 = min(context.project.map_width - 1, max(self.start_col, col))
        y2 = min(context.project.map_height - 1, max(self.start_row, row))
        return QRect(x1, y1, max(0, x2 - x1 + 1), max(0, y2 - y1 + 1))

    def _update_selection(self, col: int, row: int, context: ToolContext) -> None:
        area = QRegion(self._bounded_rect(col, row, context))
        if self._selection_mode == "add":
            area = self._initial_region.united(area)
        elif self._selection_mode == "subtract":
            area = self._initial_region.subtracted(area)
        self._set_region(area, context)

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        self.last_error = ""
        if self.pasting:
            if not self.paste_at(col, row, context):
                self.last_error = "selection.invalid_paste"
            return
        if not self._valid_layer(context) or not (
            0 <= col < context.project.map_width and 0 <= row < context.project.map_height
        ):
            return
        self.is_active = True
        self.start_col = col
        self.start_row = row
        self.current_col = col
        self.current_row = row
        self._bind(context)
        self._initial_region = self._region()
        modifiers = context.selection_modifiers
        self._selection_mode = (
            "subtract" if modifiers & Qt.KeyboardModifier.AltModifier else
            "add" if modifiers & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier)
            else "replace"
        )
        self.moving_selection = (
            self._selection_mode == "replace" and self._initial_region.contains(QPoint(col, row))
        )
        self.move_preview = (0, 0)
        if not self.moving_selection:
            self._update_selection(col, row, context)

    def on_drag(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        if self.moving_selection:
            self.move_preview = (col - self.start_col, row - self.start_row)
            return
        self._update_selection(col, row, context)

    def on_release(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        self.is_active = False
        if self.moving_selection:
            dx, dy = col - self.start_col, row - self.start_row
            self.moving_selection = False
            self.move_preview = (0, 0)
            if dx or dy:
                if not self.move_selection(dx, dy, context):
                    self.last_error = "selection.invalid_move"
            return
        self._update_selection(col, row, context)

    def clear_selection(self, context: Optional[ToolContext] = None) -> None:
        self.selection_rect = None
        self.polygon_points.clear()
        self.selection_cells.clear()
        self.moving_selection = False
        self.move_preview = (0, 0)
        self.region = QRegion()
        self.selection_owner = None
        if context:
            context.selected_cells.clear()

    def cancel(self, context: ToolContext) -> None:
        if self.is_active and not self.moving_selection:
            self._set_region(self._initial_region, context)
        self.is_active = False
        self.moving_selection = False
        self.move_preview = (0, 0)
        self.pasting = False

    def select_all(self, context: ToolContext) -> None:
        if self._valid_layer(context):
            self.pasting = False
            self._bind(context)
            self._set_region(QRegion(QRect(0, 0, context.project.map_width, context.project.map_height)), context)

    def select_layer_contents(self, context: ToolContext) -> None:
        if not self._valid_layer(context):
            return
        self.pasting = False
        region = QRegion()
        for col, row in context.active_layer.tiles:
            region = region.united(QRegion(QRect(col, row, 1, 1)))
        self._bind(context)
        self._set_region(region, context)

    def select_cells(self, cells: set[Tuple[int, int]], context: ToolContext) -> None:
        region = QRegion()
        for col, row in cells:
            region = region.united(QRegion(QRect(col, row, 1, 1)))
        self._bind(context)
        self._set_region(region, context)

    def invert_selection(self, context: ToolContext) -> None:
        if self._valid_layer(context):
            self.pasting = False
            self._bind(context)
            full = QRegion(QRect(0, 0, context.project.map_width, context.project.map_height))
            self._set_region(full.subtracted(self._region()), context)

    def set_polygon_selection(self, points: List[Tuple[int, int]]) -> bool:
        if len(points) < 3:
            return False
        min_col = min(point[0] for point in points)
        max_col = max(point[0] for point in points)
        min_row = min(point[1] for point in points)
        max_row = max(point[1] for point in points)
        self.polygon_points = list(points)
        self.region = QRegion()
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
        if not self.region.isEmpty():
            rect = self.region.boundingRect()
            return {(col, row) for row in range(rect.top(), rect.bottom() + 1)
                    for col in range(rect.left(), rect.right() + 1)
                    if self.region.contains(QPoint(col, row))}
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

    def copy_selection(self, context: ToolContext) -> bool:
        """Copies tiles in the selection rectangle to the clipboard."""
        if not self.selection_rect or not self._valid_layer(context):
            return False
        r = self.selection_rect
        context.clipboard_tiles.clear()
        region = self._region()
        context.clipboard_region = region.translated(-r.left(), -r.top())
        for (col, row), item in context.active_layer.tiles.items():
            if region.contains(QPoint(col, row)):
                rel_col = col - r.left()
                rel_row = row - r.top()
                context.clipboard_tiles[(rel_col, rel_row)] = item.clone()
        return True

    def get_preview_items(self, context: ToolContext) -> List[MapItem]:
        if self.pasting:
            previews = []
            for (col, row), item in context.clipboard_tiles.items():
                clone = item.clone()
                self._position_item(clone, context.cursor_col + col, context.cursor_row + row,
                                    context.project.tile_size)
                previews.append(clone)
            return previews
        if not self.moving_selection or not context.active_layer:
            return []
        dx, dy = self.move_preview
        if not dx and not dy:
            return []
        previews = []
        region = self._region()
        for (col, row), item in context.active_layer.tiles.items():
            if region.contains(QPoint(col, row)):
                preview = item.clone()
                self._position_item(preview, col + dx, row + dy, context.project.tile_size)
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

    def delete_selection(self, context: ToolContext) -> bool:
        """Deletes all tiles in the selection rectangle from the active layer."""
        if not self.selection_rect or not self._valid_layer(context, edit=True):
            return False
        layer = context.active_layer
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}

        region = self._region()
        for (col, row), tile in layer.tiles.items():
            if region.contains(QPoint(col, row)):
                changes[(col, row)] = (tile.clone(preserve_id=True), None)

        return self._commit(context, changes, "Usunięcie zaznaczenia")

    def _commit(self, context: ToolContext, changes, description: str) -> bool:
        if not changes or not context.history_manager:
            return False
        cmd = TileBatchCommand(context.project, context.active_layer.id, changes, description)
        cmd.execute()
        context.history_manager.push(cmd)
        return True

    def cut_selection(self, context: ToolContext) -> bool:
        if self._valid_layer(context, edit=True) and self.selection_rect:
            self.copy_selection(context)
            return self.delete_selection(context)
        return False

    def start_paste(self, context: ToolContext) -> bool:
        if context.clipboard_region.isEmpty() and context.clipboard_tiles:
            region = QRegion()
            for col, row in context.clipboard_tiles:
                region = region.united(QRegion(QRect(col, row, 1, 1)))
            context.clipboard_region = region
        self.pasting = not context.clipboard_region.isEmpty()
        self.last_error = ""
        return self.pasting

    def paste_at(self, col: int, row: int, context: ToolContext) -> bool:
        layer = context.active_layer
        if not layer or layer is not context.project.get_active_layer() or context.project.get_effective_locked(layer) or layer.layer_type != "tile" or layer.is_group or not context.project.get_effective_visible(layer):
            return False
        target = context.clipboard_region.translated(col, row)
        bounds = target.boundingRect()
        if target.isEmpty() or bounds.left() < 0 or bounds.top() < 0 or bounds.right() >= context.project.map_width or bounds.bottom() >= context.project.map_height:
            return False
        changes = {}
        for pos, item in layer.tiles.items():
            if target.contains(QPoint(*pos)):
                changes[pos] = (item.clone(preserve_id=True), None)
        for (dc, dr), item in context.clipboard_tiles.items():
            pos = (col + dc, row + dr)
            previous = layer.get_tile(*pos)
            new_item = item.clone()
            self._position_item(new_item, *pos, context.project.tile_size)
            changes[pos] = (previous.clone(preserve_id=True) if previous else None, new_item)
        result = self._commit(context, changes, "Wklejenie zaznaczenia")
        if result:
            self._bind(context)
            self._set_region(target, context)
        return result

    def fill_selection(self, context: ToolContext) -> bool:
        if not self.selection_rect or not self._valid_layer(context, edit=True):
            return False
        region = self._region()
        rect = region.boundingRect()
        changes = {}
        for row in range(rect.top(), rect.bottom() + 1):
            for col in range(rect.left(), rect.right() + 1):
                if not region.contains(QPoint(col, row)):
                    continue
                item = self.create_item_from_selection(col, row, context)
                if item is None or item.item_type != ItemType.TILE:
                    return False
                old = context.active_layer.get_tile(col, row)
                changes[(col, row)] = (old.clone(preserve_id=True) if old else None, item)
        return self._commit(context, changes, "Wypełnienie zaznaczenia")

    def _transform_selection(
        self,
        context: ToolContext,
        position_transform,
        item_transform,
        description: str,
        target_region: QRegion,
    ) -> bool:
        if not self.selection_rect or not self._valid_layer(context, edit=True):
            return False
        layer = context.active_layer
        bounds = target_region.boundingRect()
        if bounds.left() < 0 or bounds.top() < 0 or bounds.right() >= context.project.map_width or bounds.bottom() >= context.project.map_height:
            return False

        changes: Dict[
            Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]
        ] = {}
        selected: Dict[Tuple[int, int], MapItem] = {}
        region = self._region()
        for (col, row), item in layer.tiles.items():
            if region.contains(QPoint(col, row)):
                selected[(col, row)] = item.clone(preserve_id=True)
        if not selected:
            return False

        transformed: Dict[Tuple[int, int], MapItem] = {}
        for position, item in selected.items():
            new_col, new_row = position_transform(*position)
            if not (
                0 <= new_col < context.project.map_width
                and 0 <= new_row < context.project.map_height
            ):
                return False
            clone = item_transform(item.clone(preserve_id=True))
            self._position_item(clone, new_col, new_row, context.project.tile_size)
            transformed[(new_col, new_row)] = clone

        affected = set(selected) | set(transformed)
        affected.update(
            position for position in layer.tiles if target_region.contains(QPoint(*position))
        )
        for position in affected:
            before = layer.get_tile(*position)
            changes[position] = (
                before.clone(preserve_id=True) if before else None,
                transformed[position].clone(preserve_id=True) if position in transformed else None,
            )

        if not changes:
            return False
        return self._commit(context, changes, description)

    def move_selection(self, dx: int, dy: int, context: ToolContext) -> bool:
        if not self.selection_rect or not self._valid_layer(context, edit=True):
            return False
        source = self._region()
        target = source.translated(dx, dy)
        bounds = target.boundingRect()
        if bounds.left() < 0 or bounds.top() < 0 or bounds.right() >= context.project.map_width or bounds.bottom() >= context.project.map_height:
            return False
        layer = context.active_layer
        changes = {}
        moved = {}
        for pos, item in layer.tiles.items():
            if source.contains(QPoint(*pos)):
                clone = item.clone(preserve_id=True)
                self._position_item(clone, pos[0] + dx, pos[1] + dy, context.project.tile_size)
                moved[(clone.col, clone.row)] = clone
            if source.contains(QPoint(*pos)) or target.contains(QPoint(*pos)):
                changes[pos] = (item.clone(preserve_id=True), None)
        if not moved:
            return False
        for pos, item in moved.items():
            old = layer.get_tile(*pos)
            changes[pos] = (old.clone(preserve_id=True) if old else None, item)
        if not self._commit(context, changes, "Przesunięcie zaznaczenia"):
            return False
        self._set_region(target, context)
        return True

    def rotate_selection_clockwise(self, context: ToolContext) -> bool:
        if not self.selection_rect:
            return False
        rect = self.selection_rect
        transform = QTransform(0, 1, -1, 0,
                               rect.left() + rect.height() + rect.top(),
                               rect.top() - rect.left())
        target = transform.map(self._region())

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
            target,
        )
        if rotated:
            self._set_region(target, context)
        return rotated

    def flip_selection_horizontal(self, context: ToolContext) -> bool:
        if not self.selection_rect:
            return False
        rect = self.selection_rect
        transform = QTransform(-1, 0, 0, 1, rect.left() + rect.right() + 1, 0)
        target = transform.map(self._region())
        changed = self._transform_selection(
            context,
            lambda col, row: (rect.right() - (col - rect.left()), row),
            lambda item: self._toggle_flip(item, "x"),
            "Odbicie zaznaczenia poziomo",
            target,
        )
        if changed:
            self._set_region(target, context)
        return changed

    def flip_selection_vertical(self, context: ToolContext) -> bool:
        if not self.selection_rect:
            return False
        rect = self.selection_rect
        transform = QTransform(1, 0, 0, -1, 0, rect.top() + rect.bottom() + 1)
        target = transform.map(self._region())
        changed = self._transform_selection(
            context,
            lambda col, row: (col, rect.bottom() - (row - rect.top())),
            lambda item: self._toggle_flip(item, "y"),
            "Odbicie zaznaczenia pionowo",
            target,
        )
        if changed:
            self._set_region(target, context)
        return changed

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
