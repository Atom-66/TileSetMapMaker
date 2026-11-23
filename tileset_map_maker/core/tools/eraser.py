import math
from typing import Dict, Tuple, Optional, List
from .base import BaseTool, ToolContext
from ...models.layer import MapItem
from ..history import TileBatchCommand, ObjectRemoveCommand


class EraserTool(BaseTool):
    """
    High-precision eraser tool.
    Accurately removes tiles at exact cursor cell and single PNG objects
    using pixel-level alpha hit-testing.
    """

    def __init__(self):
        super().__init__("Gumka", shortcut="E")
        self.session_changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]] = {}
        self.removed_objects: List[MapItem] = []
        self.erased_coords: List[Tuple[int, int]] = []

    def on_press(self, col: int, row: int, context: ToolContext) -> None:
        layer = context.active_layer
        if not layer or layer.locked or not context.project.get_effective_visible(layer):
            return
        self.is_active = True
        self.session_changes.clear()
        self.removed_objects.clear()
        self.erased_coords.clear()
        self.erased_coords.clear()
        self._erase_at(col, row, context)

    def on_drag(self, col: int, row: int, context: ToolContext) -> None:
        layer = context.active_layer
        if not self.is_active or not layer or layer.locked or not context.project.get_effective_visible(layer):
            return
        self._erase_at(col, row, context)

    @staticmethod
    def is_point_inside_object(
        obj: MapItem,
        px: float,
        py: float,
        tile_size: int,
        asset_manager: any,
    ) -> bool:
        """
        Determines whether (px, py) hits the non-transparent visible area of a MapItem.
        Accounts for position, rotation, scaling, flip, anchor, and alpha threshold.
        """
        ox, oy = obj.get_pixel_pos(tile_size)

        has_transform = (
            abs(obj.rotation % 360) > 0.001
            or obj.scale_x != 1.0
            or obj.scale_y != 1.0
            or obj.flip_x
            or obj.flip_y
        )

        if has_transform:
            ax = ox + obj.dest_w * obj.anchor_x
            ay = oy + obj.dest_h * obj.anchor_y
            rel_x = px - ax
            rel_y = py - ay

            # Inverse rotation
            rad = math.radians(-obj.rotation)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            rot_x = rel_x * cos_a - rel_y * sin_a
            rot_y = rel_x * sin_a + rel_y * cos_a

            # Inverse scale and flip
            sx = obj.scale_x * (-1 if obj.flip_x else 1)
            sy = obj.scale_y * (-1 if obj.flip_y else 1)
            if abs(sx) < 0.001 or abs(sy) < 0.001:
                return False

            local_x = rot_x / sx + obj.dest_w * obj.anchor_x
            local_y = rot_y / sy + obj.dest_h * obj.anchor_y
        else:
            local_x = px - ox
            local_y = py - oy

        # Bounds check
        if not (0 <= local_x < obj.dest_w and 0 <= local_y < obj.dest_h):
            return False

        # Pixel alpha hit-testing
        if hasattr(asset_manager, "get_image"):
            img = asset_manager.get_image(obj.asset_id)
            if img and not img.isNull():
                img_x = int(obj.source_x + local_x * (obj.source_w / obj.dest_w))
                img_y = int(obj.source_y + local_y * (obj.source_h / obj.dest_h))
                if 0 <= img_x < img.width() and 0 <= img_y < img.height():
                    alpha = img.pixelColor(img_x, img_y).alpha()
                    return alpha > 10
        return True

    def _erase_at(self, col: int, row: int, context: ToolContext) -> None:
        layer = context.active_layer
        if not layer:
            return

        ts = context.project.tile_size
        px = context.cursor_pixel_x
        py = context.cursor_pixel_y
        w = context.project.map_width
        h = context.project.map_height
        eraser_size = getattr(context.brush_settings, "eraser_size", 1)

        radius = (eraser_size - 1) // 2
        extra = 1 if (eraser_size % 2 == 0) else 0

        # 1. Check and remove freeform objects within the eraser footprint
        if eraser_size == 1:
            hit_object: Optional[MapItem] = None
            for obj in reversed(layer.objects):
                if self.is_point_inside_object(obj, px, py, ts, context.asset_manager):
                    hit_object = obj
                    break

            if hit_object:
                layer.remove_object(hit_object.id)
                self.removed_objects.append(hit_object)
                context.project.is_modified = True
                return
        else:
            # Multi-tile eraser footprint object removal
            for dr in range(-radius, radius + extra + 1):
                for dc in range(-radius, radius + extra + 1):
                    cur_px = (col + dc + 0.5) * ts
                    cur_py = (row + dr + 0.5) * ts
                    for obj in list(reversed(layer.objects)):
                        if self.is_point_inside_object(obj, cur_px, cur_py, ts, context.asset_manager):
                            layer.remove_object(obj.id)
                            self.removed_objects.append(obj)
                            context.project.is_modified = True

        # 2. Erase grid tiles within the eraser footprint
        for dr in range(-radius, radius + extra + 1):
            for dc in range(-radius, radius + extra + 1):
                tc = col + dc
                tr = row + dr
                if 0 <= tc < w and 0 <= tr < h:
                    coord = (tc, tr)
                    if coord not in self.session_changes:
                        prev = layer.get_tile(tc, tr)
                        if prev:
                            layer.remove_tile(tc, tr)
                            self.session_changes[coord] = (prev.clone(), None)
                            self.erased_coords.append(coord)
                            context.project.is_modified = True

    def on_release(self, col: int, row: int, context: ToolContext) -> None:
        if not self.is_active:
            return
        self.is_active = False

        if context.autotile_engine and context.active_layer and self.erased_coords:
            ruleset = context.autotile_engine.get_active_ruleset()
            if ruleset:
                neighbor_changes = context.autotile_engine.update_neighbors_after_erase(
                    context.active_layer,
                    self.erased_coords,
                    ruleset,
                    context.project,
                )
                for ncoord, (nbefore, nafter) in neighbor_changes.items():
                    if ncoord not in self.session_changes:
                        self.session_changes[ncoord] = (nbefore, nafter)

        if self.session_changes and context.active_layer and context.history_manager:
            cmd = TileBatchCommand(
                context.project,
                context.active_layer.id,
                dict(self.session_changes),
                description="Użycie gumki",
            )
            context.history_manager.push(cmd)

        if context.history_manager:
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
        self.erased_coords.clear()
