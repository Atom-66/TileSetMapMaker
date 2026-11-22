import math
from typing import List, Optional, Tuple
from PyQt6.QtCore import QPointF, QRectF
from .base import BaseTool, ToolContext
from ...models.layer import MapItem, Layer, ItemType
from ..history import Command


class ObjectTransformCommand(Command):
    """Command recording object transforms and moves for undo/redo."""

    def __init__(
        self,
        layer: Layer,
        obj_id: str,
        before_state: dict,
        after_state: dict,
        description: str = "Transformacja obiektu",
    ):
        super().__init__(description)
        self.layer = layer
        self.obj_id = obj_id
        self.before_state = before_state
        self.after_state = after_state

    def _apply_state(self, state: dict) -> None:
        obj = self.layer.get_object(self.obj_id)
        if obj:
            obj.free_x = state.get("free_x")
            obj.free_y = state.get("free_y")
            obj.col = state.get("col", obj.col)
            obj.row = state.get("row", obj.row)
            obj.offset_x = state.get("offset_x", obj.offset_x)
            obj.offset_y = state.get("offset_y", obj.offset_y)
            obj.rotation = state.get("rotation", obj.rotation)
            obj.scale_x = state.get("scale_x", obj.scale_x)
            obj.scale_y = state.get("scale_y", obj.scale_y)
            obj.flip_x = state.get("flip_x", obj.flip_x)
            obj.flip_y = state.get("flip_y", obj.flip_y)
            obj.anchor_x = state.get("anchor_x", obj.anchor_x)
            obj.anchor_y = state.get("anchor_y", obj.anchor_y)

    def execute(self) -> None:
        self._apply_state(self.after_state)

    def undo(self) -> None:
        self._apply_state(self.before_state)


class ObjectTool(BaseTool):
    """Tool for selecting, moving, rotating, scaling, aligning, and duplicating freeform objects."""

    def __init__(self):
        super().__init__("Obiekt", shortcut="V")
        self.selected_ids: List[str] = []
        self.drag_start_pos: Optional[QPointF] = None
        self.initial_states: dict = {}
        self.snap_to_grid: bool = False

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        layer = context.active_layer
        if not layer or layer.locked:
            return

        ts = context.project.tile_size
        click_px_x = context.cursor_pixel_x
        click_px_y = context.cursor_pixel_y
        self.drag_start_pos = QPointF(click_px_x, click_px_y)

        # Hit test objects from top to bottom
        hit_obj: Optional[MapItem] = None
        for obj in reversed(layer.objects):
            ox, oy = obj.get_pixel_pos(ts)
            w = obj.dest_w * abs(obj.scale_x)
            h = obj.dest_h * abs(obj.scale_y)
            if ox <= click_px_x <= ox + w and oy <= click_px_y <= oy + h:
                hit_obj = obj
                break

        if hit_obj:
            if hit_obj.id not in self.selected_ids:
                self.selected_ids = [hit_obj.id]
            self.is_active = True
            # Record initial states for undo
            self.initial_states = {
                oid: self._capture_state(layer.get_object(oid))
                for oid in self.selected_ids
                if layer.get_object(oid)
            }
        else:
            self.selected_ids.clear()
            self.is_active = False

        context.selected_object_ids = list(self.selected_ids)

    def on_drag(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active or not self.drag_start_pos or not context.active_layer:
            return

        layer = context.active_layer
        dx = context.cursor_pixel_x - self.drag_start_pos.x()
        dy = context.cursor_pixel_y - self.drag_start_pos.y()
        ts = context.project.tile_size

        for oid in self.selected_ids:
            obj = layer.get_object(oid)
            init = self.initial_states.get(oid)
            if obj and init:
                init_x = init["free_x"] if init["free_x"] is not None else init["col"] * ts + init["offset_x"]
                init_y = init["free_y"] if init["free_y"] is not None else init["row"] * ts + init["offset_y"]

                target_x = init_x + dx
                target_y = init_y + dy

                if self.snap_to_grid:
                    target_x = round(target_x / ts) * ts
                    target_y = round(target_y / ts) * ts

                obj.free_x = target_x
                obj.free_y = target_y
                obj.col = int(target_x // ts)
                obj.row = int(target_y // ts)
                obj.offset_x = int(target_x % ts)
                obj.offset_y = int(target_y % ts)

    def on_release(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active or not context.active_layer:
            return
        self.is_active = False
        layer = context.active_layer

        for oid in self.selected_ids:
            obj = layer.get_object(oid)
            init = self.initial_states.get(oid)
            if obj and init:
                current_state = self._capture_state(obj)
                if current_state != init:
                    cmd = ObjectTransformCommand(layer, oid, init, current_state, "Przesunięcie obiektu")
                    context.history_manager.push(cmd)

        self.initial_states.clear()

    def rotate_selected(self, delta_degrees: float, context: ToolContext) -> None:
        if not context.active_layer:
            return
        for oid in self.selected_ids:
            obj = context.active_layer.get_object(oid)
            if obj:
                before = self._capture_state(obj)
                obj.rotation = (obj.rotation + delta_degrees) % 360
                after = self._capture_state(obj)
                cmd = ObjectTransformCommand(context.active_layer, oid, before, after, "Obrót obiektu")
                context.history_manager.push(cmd)

    def scale_selected(self, factor: float, context: ToolContext) -> None:
        if not context.active_layer:
            return
        for oid in self.selected_ids:
            obj = context.active_layer.get_object(oid)
            if obj:
                before = self._capture_state(obj)
                obj.scale_x = max(0.1, min(10.0, obj.scale_x * factor))
                obj.scale_y = max(0.1, min(10.0, obj.scale_y * factor))
                after = self._capture_state(obj)
                cmd = ObjectTransformCommand(context.active_layer, oid, before, after, "Skalowanie obiektu")
                context.history_manager.push(cmd)

    def flip_selected(self, horizontal: bool, context: ToolContext) -> None:
        if not context.active_layer:
            return
        for oid in self.selected_ids:
            obj = context.active_layer.get_object(oid)
            if obj:
                before = self._capture_state(obj)
                if horizontal:
                    obj.flip_x = not obj.flip_x
                else:
                    obj.flip_y = not obj.flip_y
                after = self._capture_state(obj)
                cmd = ObjectTransformCommand(context.active_layer, oid, before, after, "Odbicie obiektu")
                context.history_manager.push(cmd)

    def duplicate_selected(self, context: ToolContext) -> List[MapItem]:
        if not context.active_layer:
            return []
        new_items = []
        for oid in self.selected_ids:
            obj = context.active_layer.get_object(oid)
            if obj:
                clone = obj.clone()
                clone.id = None  # regenerate uuid
                if clone.free_x is not None:
                    clone.free_x += 16
                    clone.free_y += 16
                else:
                    clone.offset_x += 16
                    clone.offset_y += 16
                context.active_layer.add_object(clone)
                new_items.append(clone)
        self.selected_ids = [it.id for it in new_items]
        context.selected_object_ids = list(self.selected_ids)
        return new_items

    @staticmethod
    def _capture_state(obj: Optional[MapItem]) -> dict:
        if not obj:
            return {}
        return {
            "free_x": obj.free_x,
            "free_y": obj.free_y,
            "col": obj.col,
            "row": obj.row,
            "offset_x": obj.offset_x,
            "offset_y": obj.offset_y,
            "rotation": obj.rotation,
            "scale_x": obj.scale_x,
            "scale_y": obj.scale_y,
            "flip_x": obj.flip_x,
            "flip_y": obj.flip_y,
            "anchor_x": obj.anchor_x,
            "anchor_y": obj.anchor_y,
        }
