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


class MultiObjectTransformCommand(Command):
    """Command recording multiple objects transforms and moves for undo/redo."""

    def __init__(
        self,
        layer: Layer,
        states_before: dict,
        states_after: dict,
        description: str = "Wyrównanie obiektów",
    ):
        super().__init__(description)
        self.layer = layer
        self.states_before = states_before
        self.states_after = states_after

    def _apply(self, states: dict) -> None:
        for oid, state in states.items():
            obj = self.layer.get_object(oid)
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

    def execute(self) -> None:
        self._apply(self.states_after)

    def undo(self) -> None:
        self._apply(self.states_before)


class ObjectTool(BaseTool):
    """Tool for selecting, moving, rotating, scaling, aligning, and duplicating freeform objects."""

    def __init__(self):
        super().__init__("Obiekt", shortcut="V")
        self.selected_ids: List[str] = []
        self.drag_start_pos: Optional[QPointF] = None
        self.initial_states: dict = {}
        self.snap_to_grid: bool = False
        self.drag_mode: str = "move"  # "move", "scale", "rotate"
        self.active_handle: Optional[str] = None

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        layer = context.active_layer
        if not layer or layer.locked:
            return

        ts = context.project.tile_size
        click_px_x = context.cursor_pixel_x
        click_px_y = context.cursor_pixel_y
        self.drag_start_pos = QPointF(click_px_x, click_px_y)

        # Check gizmo handles if single object is selected (TASK-803)
        self.drag_mode = "move"
        self.active_handle = None
        if len(self.selected_ids) == 1:
            primary = layer.get_object(self.selected_ids[0])
            if primary:
                ox, oy = primary.get_pixel_pos(ts)
                w = primary.dest_w * abs(primary.scale_x)
                h = primary.dest_h * abs(primary.scale_y)
                rect = QRectF(ox, oy, w, h)
                stem_top = QPointF(rect.center().x(), rect.top() - 16)

                # Check rotation knob (within 9px radius)
                if math.hypot(click_px_x - stem_top.x(), click_px_y - stem_top.y()) <= 9.0:
                    self.drag_mode = "rotate"
                    self.is_active = True
                    self.initial_states = {primary.id: self._capture_state(primary)}
                    return

                # Check corner scale handles
                corners = {
                    "tl": rect.topLeft(),
                    "tr": rect.topRight(),
                    "bl": rect.bottomLeft(),
                    "br": rect.bottomRight(),
                }
                for c_name, c_pt in corners.items():
                    if math.hypot(click_px_x - c_pt.x(), click_px_y - c_pt.y()) <= 8.0:
                        self.drag_mode = "scale"
                        self.active_handle = c_name
                        self.is_active = True
                        self.initial_states = {primary.id: self._capture_state(primary)}
                        return

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

        if self.drag_mode == "rotate" and len(self.selected_ids) == 1:
            primary = layer.get_object(self.selected_ids[0])
            init = self.initial_states.get(primary.id)
            if primary and init:
                init_x = init["free_x"] if init["free_x"] is not None else init["col"] * ts + init["offset_x"]
                init_y = init["free_y"] if init["free_y"] is not None else init["row"] * ts + init["offset_y"]
                cx = init_x + primary.dest_w * primary.anchor_x
                cy = init_y + primary.dest_h * primary.anchor_y
                angle = math.degrees(math.atan2(context.cursor_pixel_y - cy, context.cursor_pixel_x - cx)) + 90.0
                primary.rotation = angle % 360
            return

        if self.drag_mode == "scale" and len(self.selected_ids) == 1:
            primary = layer.get_object(self.selected_ids[0])
            init = self.initial_states.get(primary.id)
            if primary and init:
                base_w = max(1.0, primary.dest_w)
                h_mult = 1.0 if (self.active_handle and "r" in self.active_handle) else -1.0
                factor = 1.0 + (dx * h_mult) / base_w
                primary.scale_x = max(0.1, min(10.0, init["scale_x"] * factor))
                primary.scale_y = max(0.1, min(10.0, init["scale_y"] * factor))
            return

        # Move mode (default)
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

        desc = (
            "Obrót gizmo"
            if self.drag_mode == "rotate"
            else ("Skalowanie gizmo" if self.drag_mode == "scale" else "Przesunięcie obiektu")
        )

        for oid in self.selected_ids:
            obj = layer.get_object(oid)
            init = self.initial_states.get(oid)
            if obj and init:
                current_state = self._capture_state(obj)
                if current_state != init:
                    cmd = ObjectTransformCommand(layer, oid, init, current_state, desc)
                    context.history_manager.push(cmd)

        self.initial_states.clear()
        self.drag_mode = "move"
        self.active_handle = None

    def cancel(self, context: ToolContext) -> None:
        """Restore object transforms changed during an interrupted gizmo/drag operation."""
        if context.active_layer:
            for oid, state in self.initial_states.items():
                obj = context.active_layer.get_object(oid)
                if obj:
                    obj.free_x = state.get("free_x", obj.free_x)
                    obj.free_y = state.get("free_y", obj.free_y)
                    obj.col = state.get("col", obj.col)
                    obj.row = state.get("row", obj.row)
                    obj.offset_x = state.get("offset_x", obj.offset_x)
                    obj.offset_y = state.get("offset_y", obj.offset_y)
                    obj.dest_w = state.get("dest_w", obj.dest_w)
                    obj.dest_h = state.get("dest_h", obj.dest_h)
                    obj.scale_x = state.get("scale_x", obj.scale_x)
                    obj.scale_y = state.get("scale_y", obj.scale_y)
                    obj.rotation = state.get("rotation", obj.rotation)
                    obj.flip_x = state.get("flip_x", obj.flip_x)
                    obj.flip_y = state.get("flip_y", obj.flip_y)
        self.initial_states.clear()
        self.drag_start_pos = None
        self.drag_mode = "move"
        self.active_handle = None
        self.is_active = False

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

    def align_selected(self, alignment: str, context: ToolContext) -> None:
        """
        Aligns selected objects (TASK-804).
        alignment: "left", "right", "center_h", "top", "bottom", "center_v"
        """
        if not context.active_layer or len(self.selected_ids) < 2:
            return

        layer = context.active_layer
        ts = context.project.tile_size
        objs = [layer.get_object(oid) for oid in self.selected_ids if layer.get_object(oid)]
        if len(objs) < 2:
            return

        states_before = {o.id: self._capture_state(o) for o in objs}

        lefts = [o.get_pixel_pos(ts)[0] for o in objs]
        rights = [o.get_pixel_pos(ts)[0] + o.dest_w * abs(o.scale_x) for o in objs]
        tops = [o.get_pixel_pos(ts)[1] for o in objs]
        bottoms = [o.get_pixel_pos(ts)[1] + o.dest_h * abs(o.scale_y) for o in objs]

        min_left, max_right = min(lefts), max(rights)
        min_top, max_bottom = min(tops), max(bottoms)
        center_h = (min_left + max_right) / 2.0
        center_v = (min_top + max_bottom) / 2.0

        for o in objs:
            curr_x, curr_y = o.get_pixel_pos(ts)
            ow = o.dest_w * abs(o.scale_x)
            oh = o.dest_h * abs(o.scale_y)

            new_x, new_y = curr_x, curr_y
            if alignment == "left":
                new_x = min_left
            elif alignment == "right":
                new_x = max_right - ow
            elif alignment == "center_h":
                new_x = center_h - ow / 2.0
            elif alignment == "top":
                new_y = min_top
            elif alignment == "bottom":
                new_y = max_bottom - oh
            elif alignment == "center_v":
                new_y = center_v - oh / 2.0

            o.free_x = new_x
            o.free_y = new_y
            o.col = int(new_x // ts)
            o.row = int(new_y // ts)
            o.offset_x = int(new_x % ts)
            o.offset_y = int(new_y % ts)

        states_after = {o.id: self._capture_state(o) for o in objs}
        cmd = MultiObjectTransformCommand(layer, states_before, states_after, f"Wyrównanie: {alignment}")
        context.history_manager.push(cmd)

    def distribute_selected(self, direction: str, context: ToolContext) -> None:
        """
        Distributes selected objects evenly (TASK-804).
        direction: "horizontal", "vertical"
        """
        if not context.active_layer or len(self.selected_ids) < 3:
            return

        layer = context.active_layer
        ts = context.project.tile_size
        objs = [layer.get_object(oid) for oid in self.selected_ids if layer.get_object(oid)]
        if len(objs) < 3:
            return

        states_before = {o.id: self._capture_state(o) for o in objs}

        if direction == "horizontal":
            objs.sort(key=lambda o: o.get_pixel_pos(ts)[0])
            first_x = objs[0].get_pixel_pos(ts)[0]
            last_x = objs[-1].get_pixel_pos(ts)[0]
            total_span = last_x - first_x
            step = total_span / (len(objs) - 1)

            for i, o in enumerate(objs):
                new_x = first_x + i * step
                o.free_x = new_x
                o.col = int(new_x // ts)
                o.offset_x = int(new_x % ts)
        elif direction == "vertical":
            objs.sort(key=lambda o: o.get_pixel_pos(ts)[1])
            first_y = objs[0].get_pixel_pos(ts)[1]
            last_y = objs[-1].get_pixel_pos(ts)[1]
            total_span = last_y - first_y
            step = total_span / (len(objs) - 1)

            for i, o in enumerate(objs):
                new_y = first_y + i * step
                o.free_y = new_y
                o.row = int(new_y // ts)
                o.offset_y = int(new_y % ts)

        states_after = {o.id: self._capture_state(o) for o in objs}
        cmd = MultiObjectTransformCommand(layer, states_before, states_after, f"Dystrybucja: {direction}")
        context.history_manager.push(cmd)

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
