from typing import Optional, List, Tuple, Any
from PyQt6.QtCore import Qt, QRect, QRectF, QPointF, QPoint, pyqtSignal
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QPaintEvent,
    QDragEnterEvent,
    QDropEvent,
    QCursor,
    QFocusEvent,
)

from ..models.project import Project
from ..models.layer import MapItem, Layer
from ..core.render_engine import RenderEngine, RenderOptions
from ..core.asset_manager import AssetManager
from ..core.history import HistoryManager
from ..core.tools.base import BaseTool, ToolContext
from ..core.tools.eraser import EraserTool
from ..core.tools.object_tool import ObjectTool
from ..core.tools.select_tool import StampTool
from .quick_action_menu import QuickActionMenu


class MapCanvas(QWidget):
    """
    Interactive 2D map viewport supporting smooth zoom, pan,
    left-click tool execution, right-click temporary eraser,
    object transforms, live previews, and robust focus/leave handling.
    """
    cursor_moved = pyqtSignal(int, int)  # col, row
    zoom_changed = pyqtSignal(float)      # zoom factor
    files_dropped = pyqtSignal(list)      # paths of dropped files/folders
    viewport_changed = pyqtSignal()
    quick_tool_requested = pyqtSignal(str)

    def __init__(
        self,
        project: Project,
        render_engine: RenderEngine,
        asset_manager: AssetManager,
        history_manager: HistoryManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.project = project
        self.render_engine = render_engine
        self.asset_manager = asset_manager
        self.history_manager = history_manager

        self.active_tool: Optional[BaseTool] = None
        self.eraser_tool = EraserTool()
        self.is_right_erasing = False

        self.tool_context = ToolContext(
            project=self.project,
            asset_manager=self.asset_manager,
            history_manager=self.history_manager,
            active_layer=self.project.get_active_layer(),
            selected_asset=self.asset_manager.selected_item,
        )

        # Viewport navigation state
        self.zoom: float = 2.0
        self.pan_offset = QPointF(50.0, 50.0)
        self.is_panning = False
        self.space_pressed = False
        self.last_mouse_pos = QPointF()

        # Canvas options
        self.show_grid = True
        self.grid_color = QColor(255, 255, 255, 35)
        self.show_hud = True
        self.cursor_tile_col: int = 0
        self.cursor_tile_row: int = 0
        self.cursor_px_x: float = 0.0
        self.cursor_px_y: float = 0.0

        self.quick_menu = QuickActionMenu(self)
        self.quick_menu.tool_selected.connect(self.quick_tool_requested.emit)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

        self.asset_manager.asset_selected.connect(self._on_asset_selected)

    def set_project(self, project: Project) -> None:
        self.project = project
        self.tool_context.project = project
        self.tool_context.active_layer = project.get_active_layer()
        self.fit_to_view()
        self.update()

    def set_tool(self, tool: BaseTool) -> None:
        if self.active_tool and self.active_tool.is_active:
            self.active_tool.cancel(self.tool_context)
        self.active_tool = tool
        self.update()

    def _on_asset_selected(self, item: Any) -> None:
        self.tool_context.selected_asset = item
        self.update()

    def set_active_layer(self, layer: Optional[Layer]) -> None:
        self.tool_context.active_layer = layer
        self.update()

    def toggle_grid(self, visible: Optional[bool] = None) -> bool:
        if visible is None:
            self.show_grid = not self.show_grid
        else:
            self.show_grid = visible
        self.update()
        return self.show_grid

    def fit_to_view(self) -> None:
        w_px, h_px = self.render_engine.get_map_dimensions_px(self.project)
        if w_px <= 0 or h_px <= 0 or self.width() <= 0 or self.height() <= 0:
            return

        margin = 40
        available_w = max(10, self.width() - margin * 2)
        available_h = max(10, self.height() - margin * 2)

        scale_x = available_w / w_px
        scale_y = available_h / h_px
        fit_zoom = min(scale_x, scale_y)

        self.zoom = max(0.25, min(fit_zoom, 4.0))

        cx = (self.width() - w_px * self.zoom) / 2
        cy = (self.height() - h_px * self.zoom) / 2
        self.pan_offset = QPointF(cx, cy)

        self.zoom_changed.emit(self.zoom)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.viewport_changed.emit()

    def center_on_world_pos(self, world_x: float, world_y: float) -> None:
        """Centers viewport on world coordinates."""
        self.pan_offset = QPointF(
            self.width() / 2.0 - world_x * self.zoom,
            self.height() / 2.0 - world_y * self.zoom,
        )
        self.viewport_changed.emit()
        self.update()

    def show_quick_menu(self, global_pos: Optional[QPoint] = None) -> None:
        """Displays quick action radial/grid tool menu."""
        if not global_pos:
            global_pos = QCursor.pos()
        self.quick_menu.show_at(global_pos)

    def pan_to_tile(self, col: int, row: int) -> None:
        """Centers the camera viewport on the given tile coordinates."""
        ts = self.project.tile_size
        px = col * ts + ts / 2
        py = row * ts + ts / 2
        self.pan_offset = QPointF(self.width() / 2 - px * self.zoom, self.height() / 2 - py * self.zoom)
        self.viewport_changed.emit()
        self.update()

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(0.1, min(zoom, 32.0))
        self.zoom_changed.emit(self.zoom)
        self.viewport_changed.emit()
        self.update()

    def screen_to_world(self, screen_pos: QPointF) -> QPointF:
        return (screen_pos - self.pan_offset) / self.zoom

    def screen_to_tile(self, screen_pos: QPointF) -> Tuple[int, int]:
        world = self.screen_to_world(screen_pos)
        ts = self.project.tile_size
        col = int(world.x() // ts)
        row = int(world.y() // ts)
        return col, row

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#121316"))

        painter.save()
        painter.translate(self.pan_offset)
        painter.scale(self.zoom, self.zoom)

        previews = []
        effective_tool = self.eraser_tool if self.is_right_erasing else self.active_tool
        if effective_tool and self.underMouse() and not self.is_right_erasing:
            previews = effective_tool.get_preview_items(self.tool_context)

        sel_rect = getattr(effective_tool, "selection_rect", None)

        options = RenderOptions(
            show_grid=self.show_grid,
            grid_color=self.grid_color,
            show_selection=True,
            selection_rect=sel_rect,
            selected_object_ids=self.tool_context.selected_object_ids,
            preview_items=previews,
            render_checkerboard=True,
        )

        top_left = self.screen_to_world(QPointF(0, 0))
        bot_right = self.screen_to_world(QPointF(self.width(), self.height()))
        clip_rect = QRectF(top_left, bot_right)

        self.render_engine.render(painter, self.project, options, clip_rect=clip_rect)
        painter.restore()

        # TASK-203: Floating HUD Overlay
        if self.show_hud:
            hud_text = f"Tile: ({self.cursor_tile_col}, {self.cursor_tile_row})  |  Pos: ({int(self.cursor_px_x)}, {int(self.cursor_px_y)})  |  Zoom: {int(self.zoom * 100)}%"
            painter.save()
            font = painter.font()
            font.setPointSize(9)
            font.setFamily("Consolas")
            painter.setFont(font)
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(hud_text)
            text_h = fm.height()
            pad_x, pad_y = 12, 6
            box_w = text_w + pad_x * 2
            box_h = text_h + pad_y * 2
            box_x = self.width() - box_w - 14
            box_y = self.height() - box_h - 14
            hud_rect = QRectF(box_x, box_y, box_w, box_h)

            painter.setPen(QPen(QColor(63, 63, 70, 200), 1))
            painter.setBrush(QBrush(QColor(24, 24, 27, 215)))
            painter.drawRoundedRect(hud_rect, 6, 6)

            painter.setPen(QColor(228, 228, 231))
            painter.drawText(hud_rect, Qt.AlignmentFlag.AlignCenter, hud_text)
            painter.restore()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return

        factor = 1.15 if delta > 0 else (1.0 / 1.15)
        old_zoom = self.zoom
        new_zoom = max(0.1, min(self.zoom * factor, 32.0))
        if new_zoom == old_zoom:
            return

        mouse_pos = event.position()
        world_before = self.screen_to_world(mouse_pos)

        self.zoom = new_zoom
        world_after = self.screen_to_world(mouse_pos)
        self.pan_offset += (world_after - world_before) * self.zoom

        self.zoom_changed.emit(self.zoom)
        self.viewport_changed.emit()
        self.update()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        self.last_mouse_pos = pos

        # Alt + Right Click: Quick Action Menu (TASK-204)
        if event.button() == Qt.MouseButton.RightButton and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
            self.show_quick_menu(event.globalPosition().toPoint())
            event.accept()
            return

        # Pan on Middle Click or Space + Left Click
        if (
            event.button() == Qt.MouseButton.MiddleButton
            or (event.button() == Qt.MouseButton.LeftButton and self.space_pressed)
        ):
            self.is_panning = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        # Update cursor coordinates accurately
        self.tool_context.active_layer = self.project.get_active_layer()
        layer = self.tool_context.active_layer

        world = self.screen_to_world(pos)
        col, row = self.screen_to_tile(pos)
        self.cursor_tile_col = col
        self.cursor_tile_row = row
        self.cursor_px_x = world.x()
        self.cursor_px_y = world.y()
        self.tool_context.cursor_col = col
        self.tool_context.cursor_row = row
        self.tool_context.cursor_pixel_x = world.x()
        self.tool_context.cursor_pixel_y = world.y()

        # Right Click: Temporarily activate Eraser!
        if event.button() == Qt.MouseButton.RightButton:
            if not layer or layer.locked or not self.project.get_effective_visible(layer):
                event.accept()
                return
            self.is_right_erasing = True
            self.eraser_tool.on_press(col, row, self.tool_context)
            self.update()
            event.accept()
            return

        # Left Click: Standard Tool execution
        if event.button() == Qt.MouseButton.LeftButton:
            if self.active_tool:
                self.active_tool.on_press(col, row, self.tool_context)
                self.update()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        world = self.screen_to_world(pos)
        col, row = self.screen_to_tile(pos)

        self.cursor_tile_col = col
        self.cursor_tile_row = row
        self.cursor_px_x = world.x()
        self.cursor_px_y = world.y()
        self.tool_context.cursor_col = col
        self.tool_context.cursor_row = row
        self.tool_context.cursor_pixel_x = world.x()
        self.tool_context.cursor_pixel_y = world.y()
        self.cursor_moved.emit(col, row)

        if self.is_panning:
            diff = pos - self.last_mouse_pos
            self.pan_offset += diff
            self.last_mouse_pos = pos
            self.viewport_changed.emit()
            self.update()
            event.accept()
            return

        # Right Mouse Drag Erasing
        if self.is_right_erasing and (event.buttons() & Qt.MouseButton.RightButton):
            self.eraser_tool.on_drag(col, row, self.tool_context)
            self.update()
            event.accept()
            return

        # Left Mouse Drag Tool
        if event.buttons() & Qt.MouseButton.LeftButton:
            if self.active_tool and self.active_tool.is_active:
                self.active_tool.on_drag(col, row, self.tool_context)
                self.update()
            event.accept()
        else:
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        world = self.screen_to_world(pos)
        col, row = self.screen_to_tile(pos)
        self.tool_context.cursor_col = col
        self.tool_context.cursor_row = row
        self.tool_context.cursor_pixel_x = world.x()
        self.tool_context.cursor_pixel_y = world.y()

        if event.button() in [Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton] and self.is_panning:
            self.is_panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor if self.space_pressed else Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        # Right Click Release: End Eraser and restore previous tool automatically!
        if event.button() == Qt.MouseButton.RightButton and self.is_right_erasing:
            self.is_right_erasing = False
            self.eraser_tool.on_release(col, row, self.tool_context)
            self.update()
            event.accept()
            return

        # Left Click Release: Tool commit
        if event.button() == Qt.MouseButton.LeftButton:
            if self.active_tool and self.active_tool.is_active:
                self.active_tool.on_release(col, row, self.tool_context)
                self.update()
            event.accept()

    def contextMenuEvent(self, event) -> None:
        # Suppress context menu so Right Click erases seamlessly without popup
        event.accept()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        # Prevent eraser or panning from being stuck when window loses focus
        if self.is_right_erasing:
            self.is_right_erasing = False
            self.eraser_tool.on_release(self.tool_context.cursor_col, self.tool_context.cursor_row, self.tool_context)
            self.update()
        if self.is_panning:
            self.is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self.space_pressed = False
        super().focusOutEvent(event)

    def leaveEvent(self, event) -> None:
        # Check if right button was released outside the window
        if self.is_right_erasing and not (QApplication.mouseButtons() & Qt.MouseButton.RightButton):
            self.is_right_erasing = False
            self.eraser_tool.on_release(self.tool_context.cursor_col, self.tool_context.cursor_row, self.tool_context)
            self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.space_pressed = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        elif event.key() == Qt.Key.Key_Q:
            self.show_quick_menu()
            event.accept()
        elif event.key() == Qt.Key.Key_R:
            if isinstance(self.active_tool, ObjectTool):
                self.active_tool.rotate_selected(90.0, self.tool_context)
                self.update()
            elif isinstance(self.active_tool, StampTool):
                self.active_tool.rotate_clockwise(self.tool_context)
                self.update()
        elif event.key() == Qt.Key.Key_H and isinstance(self.active_tool, ObjectTool):
            self.active_tool.flip_selected(horizontal=True, context=self.tool_context)
            self.update()
        elif event.key() == Qt.Key.Key_V and isinstance(self.active_tool, ObjectTool):
            self.active_tool.flip_selected(horizontal=False, context=self.tool_context)
            self.update()
        elif event.key() == Qt.Key.Key_Plus and isinstance(self.active_tool, ObjectTool):
            self.active_tool.scale_selected(1.2, self.tool_context)
            self.update()
        elif event.key() == Qt.Key.Key_Minus and isinstance(self.active_tool, ObjectTool):
            self.active_tool.scale_selected(0.8, self.tool_context)
            self.update()
        elif event.key() == Qt.Key.Key_D and (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and isinstance(self.active_tool, ObjectTool):
            self.active_tool.duplicate_selected(self.tool_context)
            self.update()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.space_pressed = False
            if not self.is_panning:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
