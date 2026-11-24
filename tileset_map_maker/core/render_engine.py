import math
from collections import OrderedDict
from typing import Optional, List, Tuple
from PyQt6.QtCore import QRect, QRectF, QPointF, Qt
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QImage,
    QPixmap,
    QPen,
    QBrush,
    QTransform,
    QRegion,
    QPainterPath,
)

from ..models.project import Project
from ..models.layer import Layer, MapItem, ItemType
from .asset_manager import AssetManager
from .performance_metrics import PerformanceMetrics


class RenderOptions:
    """Configuration options for map rendering."""

    def __init__(
        self,
        show_grid: bool = True,
        grid_color: QColor = QColor(255, 255, 255, 35),
        show_selection: bool = True,
        selection_rect: Optional[QRect] = None,
        selection_cells: Optional[List[Tuple[int, int]]] = None,
        selected_object_ids: Optional[List[str]] = None,
        preview_items: Optional[List[MapItem]] = None,
        preview_opacity: float = 0.65,
        only_layer_ids: Optional[List[str]] = None,
        ignore_hidden_layers: bool = True,
        transparent_bg: bool = False,
        custom_bg_color: Optional[QColor] = None,
        scale: float = 1.0,
        render_checkerboard: bool = True,
        selection_region: Optional[QRegion] = None,
    ):
        self.show_grid = show_grid
        self.grid_color = grid_color
        self.show_selection = show_selection
        self.selection_rect = selection_rect
        self.selection_cells = selection_cells
        self.selection_region = selection_region
        self.selected_object_ids = selected_object_ids or []
        self.preview_items = preview_items or []
        self.preview_opacity = preview_opacity
        self.only_layer_ids = only_layer_ids
        self.ignore_hidden_layers = ignore_hidden_layers
        self.transparent_bg = transparent_bg
        self.custom_bg_color = custom_bg_color
        self.scale = scale
        self.render_checkerboard = render_checkerboard


class RenderEngine:
    """
    Renders map projects to QPainter or high-resolution QImage.
    Supports layer groups, opacity hierarchies, freeform objects with rotation and scaling.
    """

    def __init__(self, asset_manager: AssetManager):
        self.asset_manager = asset_manager
        self.metrics = PerformanceMetrics()
        self._tile_pixmap_cache: OrderedDict[
            Tuple[str, int, int, int, int], QPixmap
        ] = OrderedDict()
        self._tile_cache_limit = 2048
        self._tile_cache_limit_bytes = 64 * 1024 * 1024

    def get_map_dimensions_px(self, project: Project) -> Tuple[int, int]:
        w_px = project.map_width * project.tile_size
        h_px = project.map_height * project.tile_size
        return w_px, h_px

    def calculate_item_bounding_rect(self, item: MapItem, tile_size: int) -> QRectF:
        """Calculates transformed bounding box in pixel coordinates."""
        px, py = item.get_pixel_pos(tile_size)
        w = item.dest_w * abs(item.scale_x)
        h = item.dest_h * abs(item.scale_y)

        # Standard axis-aligned if no rotation
        if abs(item.rotation % 360) < 0.001:
            return QRectF(px, py, w, h)

        # Rotated bounding box
        rad = math.radians(item.rotation)
        cos_a = abs(math.cos(rad))
        sin_a = abs(math.sin(rad))
        rot_w = w * cos_a + h * sin_a
        rot_h = w * sin_a + h * cos_a
        cx = px + item.dest_w * item.anchor_x
        cy = py + item.dest_h * item.anchor_y
        return QRectF(cx - rot_w / 2, cy - rot_h / 2, rot_w, rot_h)

    def calculate_content_bounding_box(self, project: Project) -> QRect:
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")
        ts = project.tile_size
        found_any = False

        for layer in project.layers:
            if layer.is_group or not project.get_effective_visible(layer):
                continue
            for item in list(layer.tiles.values()) + layer.objects:
                rect = self.calculate_item_bounding_rect(item, ts)
                min_x = min(min_x, rect.left())
                min_y = min(min_y, rect.top())
                max_x = max(max_x, rect.right())
                max_y = max(max_y, rect.bottom())
                found_any = True

        if not found_any:
            w_px, h_px = self.get_map_dimensions_px(project)
            return QRect(0, 0, w_px, h_px)

        return QRect(int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y))

    def draw_checkerboard(self, painter: QPainter, rect: QRectF, square_size: int = 16) -> None:
        c1 = QColor("#1e1e24")
        c2 = QColor("#282830")
        painter.fillRect(rect, c1)

        painter.setBrush(QBrush(c2))
        painter.setPen(Qt.PenStyle.NoPen)
        first_y = math.floor(rect.top() / square_size) * square_size
        first_x = math.floor(rect.left() / square_size) * square_size
        painter.setClipRect(rect, Qt.ClipOperation.IntersectClip)
        for y in range(first_y, math.ceil(rect.bottom()), square_size):
            for x in range(first_x, math.ceil(rect.right()), square_size):
                if (x // square_size + y // square_size) % 2:
                    painter.drawRect(QRectF(x, y, square_size, square_size))

    def draw_item(self, painter: QPainter, item: MapItem, tile_size: int) -> None:
        self.metrics.count_drawn_item()
        pixmap = self.asset_manager.get_pixmap(item.asset_id)
        if not pixmap or pixmap.isNull():
            return

        px_x, px_y = item.get_pixel_pos(tile_size)
        source_rect = QRectF(
            item.source_x, item.source_y, item.source_w, item.source_h
        )
        cache_key = (
            item.asset_id,
            item.source_x,
            item.source_y,
            item.source_w,
            item.source_h,
        )

        has_transform = (
            abs(item.rotation % 360) > 0.001
            or item.scale_x != 1.0
            or item.scale_y != 1.0
            or item.flip_x
            or item.flip_y
        )

        if has_transform:
            painter.save()
            anchor_px_x = px_x + item.dest_w * item.anchor_x
            anchor_px_y = px_y + item.dest_h * item.anchor_y

            painter.translate(anchor_px_x, anchor_px_y)
            if item.rotation != 0.0:
                painter.rotate(item.rotation)

            sx = item.scale_x * (-1 if item.flip_x else 1)
            sy = item.scale_y * (-1 if item.flip_y else 1)
            painter.scale(sx, sy)

            target = QRectF(
                -item.dest_w * item.anchor_x,
                -item.dest_h * item.anchor_y,
                item.dest_w,
                item.dest_h,
            )
            if cache_key in self._tile_pixmap_cache:
                tile_pixmap = self._tile_pixmap_cache.pop(cache_key)
                self._tile_pixmap_cache[cache_key] = tile_pixmap
            else:
                tile_pixmap = pixmap.copy(
                    item.source_x,
                    item.source_y,
                    item.source_w,
                    item.source_h,
                )
                self._tile_pixmap_cache[cache_key] = tile_pixmap
                self._evict_tile_cache()
            painter.drawPixmap(target, tile_pixmap, QRectF(tile_pixmap.rect()))
            painter.restore()
        else:
            dest_rect = QRectF(px_x, px_y, item.dest_w, item.dest_h)
            painter.drawPixmap(dest_rect, pixmap, source_rect)

    def _evict_tile_cache(self) -> None:
        while len(self._tile_pixmap_cache) > 1 and (
            len(self._tile_pixmap_cache) > self._tile_cache_limit
            or sum(
                pixmap.width() * pixmap.height() * 4
                for pixmap in self._tile_pixmap_cache.values()
            )
            > self._tile_cache_limit_bytes
        ):
            self._tile_pixmap_cache.popitem(last=False)

    def render_layer(
        self,
        painter: QPainter,
        layer: Layer,
        project: Project,
        effective_opacity: float,
        clip_rect: Optional[QRectF] = None,
    ) -> None:
        if effective_opacity <= 0.0:
            return

        painter.save()
        if effective_opacity < 1.0:
            painter.setOpacity(painter.opacity() * effective_opacity)

        # Apply Blend Mode (TASK-704)
        bm = getattr(layer, "blend_mode", "normal")
        if bm == "multiply":
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        elif bm == "screen":
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        elif bm == "overlay":
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Overlay)
        elif bm == "add":
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)

        # 1. Grid tiles with Viewport Culling (TASK-1403)
        ts = project.tile_size
        if clip_rect is not None and len(layer.tiles) > 32:
            min_col = int(math.floor(clip_rect.left() / ts)) - 1
            max_col = int(math.ceil(clip_rect.right() / ts)) + 1
            min_row = int(math.floor(clip_rect.top() / ts)) - 1
            max_row = int(math.ceil(clip_rect.bottom() / ts)) + 1
            visible_cell_count = max(0, max_col - min_col + 1) * max(
                0, max_row - min_row + 1
            )
            if visible_cell_count < len(layer.tiles):
                for r in range(min_row, max_row + 1):
                    for c in range(min_col, max_col + 1):
                        item = layer.tiles.get((c, r))
                        if item:
                            self.draw_item(painter, item, ts)
            else:
                for item in layer.tiles.values():
                    rect = self.calculate_item_bounding_rect(item, ts)
                    if rect.intersects(clip_rect):
                        self.draw_item(painter, item, ts)
        else:
            sorted_tiles = sorted(layer.tiles.values(), key=lambda t: (t.row, t.col))
            for item in sorted_tiles:
                self.draw_item(painter, item, ts)

        # 2. Objects with culling
        sorted_objs = sorted(layer.objects, key=lambda o: (o.z_index, o.row, o.col))
        for obj in sorted_objs:
            if clip_rect is not None:
                ox, oy = obj.get_pixel_pos(ts)
                obj_rect = QRectF(ox, oy, obj.dest_w * obj.scale_x, obj.dest_h * obj.scale_y)
                if not obj_rect.intersects(clip_rect):
                    continue
            self.draw_item(painter, obj, ts)

        if layer.layer_type == "collision":
            painter.save()
            for collision in layer.collisions:
                collision_rect = QRectF(
                    collision.x,
                    collision.y,
                    collision.width,
                    collision.height,
                )
                if clip_rect is not None and not collision_rect.intersects(clip_rect):
                    continue
                color = QColor(
                    239, 68, 68, 90
                ) if collision.blocking else QColor(59, 130, 246, 70)
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color.lighter(150), 2))
                if collision.shape.value == "ellipse":
                    painter.drawEllipse(collision_rect)
                else:
                    painter.drawRect(collision_rect)
            painter.restore()

        painter.restore()

    def render(
        self,
        painter: QPainter,
        project: Project,
        options: RenderOptions,
        clip_rect: Optional[QRectF] = None,
    ) -> None:
        self.metrics.begin_render()
        try:
            self._render(
                painter=painter,
                project=project,
                options=options,
                clip_rect=clip_rect,
            )
        finally:
            self.metrics.end_render()

    def _render(
        self,
        painter: QPainter,
        project: Project,
        options: RenderOptions,
        clip_rect: Optional[QRectF] = None,
    ) -> None:
        w_px, h_px = self.get_map_dimensions_px(project)
        map_rect = QRectF(0, 0, w_px, h_px)
        visible_rect = map_rect.intersected(clip_rect) if clip_rect is not None else map_rect

        # 1. Background
        if options.transparent_bg or project.is_bg_transparent:
            if options.render_checkerboard:
                painter.save()
                self.draw_checkerboard(painter, visible_rect)
                painter.restore()
        else:
            bg_color = (
                options.custom_bg_color
                if options.custom_bg_color
                else QColor(project.background_color)
            )
            painter.fillRect(visible_rect, bg_color)

        # 2. Render Layers in ascending order
        for layer in project.layers:
            if layer.is_group:
                continue
            if (
                project.isolated_layer_id is not None
                and layer.id != project.isolated_layer_id
            ):
                continue
            if options.only_layer_ids and layer.id not in options.only_layer_ids:
                continue

            # Respect group hierarchy visibility and opacity
            is_visible = project.get_effective_visible(layer)
            if options.ignore_hidden_layers and not is_visible:
                continue

            effective_op = project.get_effective_opacity(layer)
            self.render_layer(painter, layer, project, effective_op, clip_rect=clip_rect)

        # 3. Tool Previews
        if options.preview_items:
            painter.save()
            painter.setOpacity(options.preview_opacity)
            for item in options.preview_items:
                self.draw_item(painter, item, project.tile_size)
            painter.restore()

        # 4. Grid overlay
        if options.show_grid:
            self.draw_grid(painter, project, options.grid_color, clip_rect)

        # 5. Selection overlay (Tile Marquee)
        if options.show_selection and (
            options.selection_region or options.selection_rect or options.selection_cells
        ):
            if options.selection_region and not options.selection_region.isEmpty():
                painter.save()
                painter.scale(project.tile_size, project.tile_size)
                path = QPainterPath()
                path.addRegion(options.selection_region)
                pen = QPen(QColor(79, 128, 255, 230))
                pen.setCosmetic(True)
                pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(QColor(79, 128, 255, 55))
                painter.drawPath(path)
                painter.restore()
            elif options.selection_cells:
                self.draw_selection_cells(
                    painter, options.selection_cells, project.tile_size
                )
            elif options.selection_rect:
                self.draw_selection(
                    painter, options.selection_rect, project.tile_size
                )

        # 6. Selected Objects Bounding Handles
        if options.selected_object_ids:
            self.draw_selected_objects(painter, project, options.selected_object_ids)

    def draw_grid(
        self,
        painter: QPainter,
        project: Project,
        grid_color: QColor,
        clip_rect: Optional[QRectF] = None,
    ) -> None:
        ts = project.tile_size
        w_px, h_px = self.get_map_dimensions_px(project)

        painter.save()
        pen = QPen(grid_color)
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        if clip_rect is None:
            min_x, max_x, min_y, max_y = 0, w_px, 0, h_px
        else:
            min_x = max(0, int(clip_rect.left() // ts) * ts)
            max_x = min(w_px, math.ceil(clip_rect.right() / ts) * ts)
            min_y = max(0, int(clip_rect.top() // ts) * ts)
            max_y = min(h_px, math.ceil(clip_rect.bottom() / ts) * ts)

        for x in range(min_x, max_x + 1, ts):
            painter.drawLine(QPointF(x, min_y), QPointF(x, max_y))

        for y in range(min_y, max_y + 1, ts):
            painter.drawLine(QPointF(min_x, y), QPointF(max_x, y))

        border_pen = QPen(QColor(80, 130, 255, 120))
        border_pen.setWidth(2)
        painter.setPen(border_pen)
        painter.drawRect(QRectF(0, 0, w_px, h_px))
        painter.restore()

    def draw_selection(self, painter: QPainter, sel_rect: QRect, tile_size: int) -> None:
        px_x = sel_rect.x() * tile_size
        px_y = sel_rect.y() * tile_size
        px_w = sel_rect.width() * tile_size
        px_h = sel_rect.height() * tile_size

        painter.save()
        fill_brush = QBrush(QColor(79, 128, 255, 60))
        rect = QRectF(px_x, px_y, px_w, px_h)
        painter.fillRect(rect, fill_brush)

        pen = QPen(QColor(79, 128, 255, 230))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(rect)
        painter.restore()

    def draw_selection_cells(
        self,
        painter: QPainter,
        cells,
        tile_size: int,
    ) -> None:
        painter.save()
        fill = QColor(59, 130, 246, 55)
        pen = QPen(QColor(96, 165, 250, 230))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(fill)
        for col, row in cells:
            painter.drawRect(
                QRectF(col * tile_size, row * tile_size, tile_size, tile_size)
            )
        painter.restore()

    def draw_selected_objects(
        self,
        painter: QPainter,
        project: Project,
        selected_ids: List[str],
    ) -> None:
        """Draws bounding boxes and transform gizmo handles (scale corners + rotation knob) around selected objects."""
        painter.save()
        pen = QPen(QColor(59, 130, 246, 240))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        handle_pen = QPen(QColor(30, 30, 36), 1)
        handle_brush = QBrush(QColor(255, 255, 255))

        for layer in project.layers:
            for obj in layer.objects:
                if obj.id in selected_ids:
                    rect = self.calculate_item_bounding_rect(obj, project.tile_size)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(rect)

                    # Rotation stem and handle knob
                    stem_top = QPointF(rect.center().x(), rect.top() - 16)
                    painter.drawLine(QPointF(rect.center().x(), rect.top()), stem_top)

                    painter.setPen(handle_pen)
                    painter.setBrush(handle_brush)
                    painter.drawEllipse(stem_top, 4.5, 4.5)

                    # 4 Corner scale handles
                    hs = 7.0
                    corners = [
                        rect.topLeft(),
                        rect.topRight(),
                        rect.bottomLeft(),
                        rect.bottomRight(),
                    ]
                    for pt in corners:
                        painter.drawRect(QRectF(pt.x() - hs / 2, pt.y() - hs / 2, hs, hs))
        painter.restore()

    def export_to_image(
        self,
        project: Project,
        options: Optional[RenderOptions] = None,
        crop_to_content: bool = False,
    ) -> QImage:
        if options is None:
            options = RenderOptions(
                show_grid=False,
                show_selection=False,
                selected_object_ids=[],
                preview_items=[],
                render_checkerboard=False,
                ignore_hidden_layers=True,
            )
        else:
            options.show_grid = False
            options.show_selection = False
            options.selected_object_ids = []
            options.preview_items = []
            options.render_checkerboard = False

        if crop_to_content:
            target_rect = self.calculate_content_bounding_box(project)
        else:
            w_px, h_px = self.get_map_dimensions_px(project)
            target_rect = QRect(0, 0, w_px, h_px)

        img = QImage(
            target_rect.width(),
            target_rect.height(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        img.fill(Qt.GlobalColor.transparent)

        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        if crop_to_content:
            painter.translate(-target_rect.x(), -target_rect.y())

        self.render(painter, project, options)
        painter.end()

        return img
