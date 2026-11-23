from typing import Optional
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent

from ..models.project import Project
from ..core.render_engine import RenderEngine, RenderOptions
from .map_canvas import MapCanvas


class MinimapWidget(QWidget):
    """
    Interactive minimap dock widget showing full map overview
    with live camera viewport rectangle and click-to-pan navigation.
    """

    def __init__(
        self,
        project: Project,
        render_engine: RenderEngine,
        canvas: MapCanvas,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.project = project
        self.render_engine = render_engine
        self.canvas = canvas

        self.setMinimumSize(140, 120)
        self.setMouseTracking(True)
        self._is_dragging = False

        self.canvas.viewport_changed.connect(self.update)

    def set_project(self, project: Project) -> None:
        self.project = project
        self.update()

    def _get_transform_params(self):
        w_px = max(1, self.project.map_width * self.project.tile_size)
        h_px = max(1, self.project.map_height * self.project.tile_size)

        pad = 8.0
        avail_w = max(10.0, self.width() - pad * 2)
        avail_h = max(10.0, self.height() - pad * 2)

        scale = min(avail_w / w_px, avail_h / h_px)
        draw_w = w_px * scale
        draw_h = h_px * scale
        off_x = (self.width() - draw_w) / 2.0
        off_y = (self.height() - draw_h) / 2.0

        return w_px, h_px, scale, off_x, off_y, draw_w, draw_h

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#18181b"))

        w_px, h_px, scale, off_x, off_y, draw_w, draw_h = self._get_transform_params()
        map_rect = QRectF(off_x, off_y, draw_w, draw_h)

        # Background of map area
        painter.fillRect(map_rect, QColor("#121316"))

        # Render scaled map layers
        painter.save()
        painter.translate(off_x, off_y)
        painter.scale(scale, scale)

        options = RenderOptions(
            show_grid=False,
            show_selection=False,
            preview_items=[],
            render_checkerboard=False,
            ignore_hidden_layers=True,
        )
        self.render_engine.render(painter, self.project, options)
        painter.restore()

        # Border around map
        painter.setPen(QPen(QColor(63, 63, 70), 1))
        painter.drawRect(map_rect)

        # Live Camera Viewport Rectangle
        tl_world = self.canvas.screen_to_world(QPointF(0, 0))
        br_world = self.canvas.screen_to_world(QPointF(self.canvas.width(), self.canvas.height()))

        cam_x = off_x + tl_world.x() * scale
        cam_y = off_y + tl_world.y() * scale
        cam_w = (br_world.x() - tl_world.x()) * scale
        cam_h = (br_world.y() - tl_world.y()) * scale
        cam_rect = QRectF(cam_x, cam_y, cam_w, cam_h)

        # Draw translucent fill and crisp border for viewport box
        painter.fillRect(cam_rect, QColor(56, 189, 248, 45))
        cam_pen = QPen(QColor(56, 189, 248, 230))
        cam_pen.setWidth(2)
        painter.setPen(cam_pen)
        painter.drawRect(cam_rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._navigate_to_pos(event.position())
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self._navigate_to_pos(event.position())
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            event.accept()

    def focusOutEvent(self, event) -> None:
        self._is_dragging = False
        super().focusOutEvent(event)

    def leaveEvent(self, event) -> None:
        if not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            self._is_dragging = False
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._is_dragging = False
            event.accept()
            return
        super().keyPressEvent(event)

    def _navigate_to_pos(self, pos: QPointF) -> None:
        w_px, h_px, scale, off_x, off_y, draw_w, draw_h = self._get_transform_params()
        if scale <= 0:
            return

        world_x = (pos.x() - off_x) / scale
        world_y = (pos.y() - off_y) / scale

        # Clamp to map boundaries
        world_x = max(0.0, min(world_x, float(w_px)))
        world_y = max(0.0, min(world_y, float(h_px)))

        self.canvas.center_on_world_pos(world_x, world_y)
        self.update()
