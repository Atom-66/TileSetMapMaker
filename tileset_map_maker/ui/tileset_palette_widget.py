import os
import logging
from typing import Optional, Tuple, List, Set, Dict, Any
from PyQt6.QtCore import (
    Qt, QRect, QRectF, QPointF, pyqtSignal, QSize, QSettings, QByteArray, QTimer,
    QMimeData, QItemSelectionModel,
)
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QToolButton,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QMenu,
    QSplitter,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QSpinBox,
    QLineEdit,
    QDialogButtonBox,
    QPushButton,
    QApplication,
)
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QPaintEvent,
    QKeySequence,
    QIcon,
    QDragEnterEvent,
    QDropEvent,
    QPixmap,
    QImage,
    QShowEvent,
    QDrag,
)

from ..models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from ..models.category import CategoryTree, CategoryNode
from ..core.asset_manager import AssetManager
from ..core.config_manager import ConfigManager
from ..core.rpg_autotile import RPGAutotile, SelectedAutotile
from .styles import get_canvas_theme_colors
from .tileset_slicer_dialog import TilesetSlicerDialog
from .dialogs.tileset_import_dialog import TilesetImportDialog
from .widgets.switch_toggle import SwitchToggle
from .icons import IconFactory
from ..core.localization import tr, get_localization

logger = logging.getLogger("TilesetPalette")


class ElidedLabel(QLabel):
    """
    Compact QLabel that gracefully accommodates tight dock panels
    without forcing excessive layout expansion via minimumSizeHint.
    """
    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._full_text = text
        if text:
            self.setToolTip(text)

    def setText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        super().setText(text)

    def text(self) -> str:
        return self._full_text

    def minimumSizeHint(self) -> QSize:
        return QSize(40, super().minimumSizeHint().height())


class TilesetCanvas(QWidget):
    """
    Tiled-style 2D interactive canvas for viewing an entire tileset PNG sheet
    with a uniform regular grid overlay and selecting single tiles or multi-tile rectangular blocks.
    """
    selection_changed = pyqtSignal(object)  # SelectedSubTile
    zoom_changed = pyqtSignal(float)

    def __init__(self, asset_manager: AssetManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.asset_manager = asset_manager
        self.current_asset: Optional[Asset] = None

        self.zoom: float = 1.5
        self.pan_offset = QPointF(10.0, 10.0)
        self.is_panning = False
        self.space_pressed = False
        self.last_mouse_pos = QPointF()

        self.show_grid = True
        self.hover_cell: Optional[Tuple[int, int]] = None

        # Selection state: rectangular bounding block (start_c, start_r) to (end_c, end_r)
        self.is_selecting = False
        self.has_selection = True
        self.sel_start_col = 0
        self.sel_start_row = 0
        self.sel_end_col = 0
        self.sel_end_row = 0

        # View state cache per tileset asset ID: {asset_id: {"zoom": float, "pan_offset": QPointF, ...}}
        self.tileset_view_states: Dict[str, Dict[str, Any]] = {}
        self._has_init_shown = False

        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._has_init_shown:
            self._has_init_shown = True
            if self.current_asset and self.current_asset.id not in self.tileset_view_states:
                self.fit_to_view()

    def save_current_view_state(self) -> None:
        """Saves current zoom, pan offset and selection bounds for the active asset."""
        if self.current_asset and self.current_asset.id:
            self.tileset_view_states[self.current_asset.id] = {
                "zoom": self.zoom,
                "pan_offset": QPointF(self.pan_offset.x(), self.pan_offset.y()),
                "sel_start_col": self.sel_start_col,
                "sel_start_row": self.sel_start_row,
                "sel_end_col": self.sel_end_col,
                "sel_end_row": self.sel_end_row,
            }

    def restore_or_init_view_state(self, asset_id: str) -> None:
        """Restores previously saved zoom and pan for this tileset, or computes initial fit."""
        if asset_id in self.tileset_view_states:
            st = self.tileset_view_states[asset_id]
            self.zoom = st["zoom"]
            self.pan_offset = QPointF(st["pan_offset"].x(), st["pan_offset"].y())
            self.sel_start_col = st.get("sel_start_col", 0)
            self.sel_start_row = st.get("sel_start_row", 0)
            self.sel_end_col = st.get("sel_end_col", 0)
            self.sel_end_row = st.get("sel_end_row", 0)
            self.zoom_changed.emit(self.zoom)
        else:
            if self.width() > 0 and self.height() > 0:
                self.fit_to_view()
            else:
                self.zoom = 1.0
                self.pan_offset = QPointF(16.0, 16.0)
                self.zoom_changed.emit(self.zoom)
            self.sel_start_col = 0
            self.sel_start_row = 0
            self.sel_end_col = 0
            self.sel_end_row = 0
            self.save_current_view_state()

    def set_asset(self, asset: Optional[Asset]) -> None:
        if not asset:
            if self.current_asset:
                self.save_current_view_state()
            self.current_asset = None
            self.update()
            return

        if self.current_asset and self.current_asset.id == asset.id:
            # Same asset already active, keep zoom/pan/selection completely intact!
            self.current_asset = asset
            self.update()
            return

        # Switching to a different asset: save previous asset view state
        if self.current_asset:
            self.save_current_view_state()

        self.current_asset = asset
        self.restore_or_init_view_state(asset.id)
        self._emit_selection()
        self.update()

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(0.25, min(zoom, 16.0))
        self.save_current_view_state()
        self.zoom_changed.emit(self.zoom)
        self.update()

    def fit_to_view(self) -> None:
        if not self.current_asset or self.width() <= 0 or self.height() <= 0:
            return
        w = self.current_asset.width
        h = self.current_asset.height
        if w <= 0 or h <= 0:
            return

        margin = 16
        scale_x = (self.width() - margin * 2) / w
        scale_y = (self.height() - margin * 2) / h
        self.zoom = max(0.25, min(min(scale_x, scale_y), 4.0))

        cx = (self.width() - w * self.zoom) / 2
        cy = (self.height() - h * self.zoom) / 2
        self.pan_offset = QPointF(cx, cy)
        self.save_current_view_state()
        self.zoom_changed.emit(self.zoom)
        self.update()

    def screen_to_world(self, screen_pos: QPointF) -> QPointF:
        return (screen_pos - self.pan_offset) / self.zoom

    def world_to_cell(self, world_pos: QPointF) -> Optional[Tuple[int, int]]:
        if not self.current_asset:
            return None
        cfg = self.current_asset.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
        grid = cfg.compute_grid(self.current_asset.width, self.current_asset.height)

        x = world_pos.x() - cfg.start_x - cfg.margin_x
        y = world_pos.y() - cfg.start_y - cfg.margin_y
        step_w = cfg.tile_width + cfg.spacing_x
        step_h = cfg.tile_height + cfg.spacing_y

        if x < 0 or y < 0:
            return None

        col = int(x // step_w)
        row = int(y // step_h)

        if 0 <= col < grid["cols"] and 0 <= row < grid["rows"]:
            in_tile_x = x % step_w
            in_tile_y = y % step_h
            if in_tile_x < cfg.tile_width and in_tile_y < cfg.tile_height:
                return col, row
        return None

    def select_all(self) -> None:
        if not self.current_asset:
            return
        cfg = self.current_asset.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
        grid = cfg.compute_grid(self.current_asset.width, self.current_asset.height)
        if grid["cols"] > 0 and grid["rows"] > 0:
            self.has_selection = True
            self.sel_start_col = 0
            self.sel_start_row = 0
            self.sel_end_col = grid["cols"] - 1
            self.sel_end_row = grid["rows"] - 1
            self._emit_selection()
            self.save_current_view_state()
            self.update()

    def deselect(self) -> None:
        """Clears active selection box on the canvas."""
        self.has_selection = False
        self.is_selecting = False
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Background
        app = QApplication.instance()
        theme_index = int(app.property("theme_index") or 0) if app else 0
        painter.fillRect(
            self.rect(),
            QColor(get_canvas_theme_colors(theme_index)["background"]),
        )

        if not self.current_asset:
            painter.setPen(QColor("#71717a"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                tr("palette.canvas_empty"),
            )
            return

        pixmap = self.asset_manager.get_pixmap(self.current_asset.id)
        if not pixmap or pixmap.isNull():
            painter.setPen(QColor("#ef4444"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                tr("palette.canvas_load_error", path=self.current_asset.file_path),
            )
            return

        w = self.current_asset.width
        h = self.current_asset.height
        dest_rect = QRectF(
            self.pan_offset.x(),
            self.pan_offset.y(),
            w * self.zoom,
            h * self.zoom,
        )

        # Checkerboard background
        check_size = 12 * self.zoom
        c1 = QColor("#1e1e24")
        c2 = QColor("#282830")
        painter.setPen(Qt.PenStyle.NoPen)
        clip_rect = dest_rect.toRect()
        for cy in range(int(dest_rect.top()), int(dest_rect.bottom()), int(check_size)):
            for cx in range(int(dest_rect.left()), int(dest_rect.right()), int(check_size)):
                rw = min(int(check_size), int(dest_rect.right() - cx))
                rh = min(int(check_size), int(dest_rect.bottom() - cy))
                is_even = ((cx - int(dest_rect.left())) // int(check_size) + (cy - int(dest_rect.top())) // int(check_size)) % 2 == 0
                painter.fillRect(QRect(cx, cy, rw, rh), c1 if is_even else c2)

        # Draw sheet image
        painter.drawPixmap(dest_rect, pixmap, QRectF(0, 0, w, h))

        # Reset brush to NoBrush so grid drawing never fills cells with solid color
        painter.setBrush(Qt.BrushStyle.NoBrush)

        cfg = self.current_asset.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
        grid = cfg.compute_grid(w, h)

        # Grid overlay
        if self.show_grid:
            grid_pen = QPen(QColor(255, 255, 255, 75))
            grid_pen.setWidth(1)
            painter.setPen(grid_pen)

            for r in range(grid["rows"]):
                for c in range(grid["cols"]):
                    sx, sy, tw, th = cfg.get_tile_rect(c, r)
                    screen_x = self.pan_offset.x() + sx * self.zoom
                    screen_y = self.pan_offset.y() + sy * self.zoom
                    screen_w = tw * self.zoom
                    screen_h = th * self.zoom
                    painter.drawRect(QRectF(screen_x, screen_y, screen_w, screen_h))

        # Outer border
        border_pen = QPen(QColor("#3b82f6"))
        border_pen.setWidth(2)
        painter.setPen(border_pen)
        painter.drawRect(dest_rect)

        # Hover cell
        if self.hover_cell:
            hc, hr = self.hover_cell
            if 0 <= hc < grid["cols"] and 0 <= hr < grid["rows"]:
                hx, hy, hw, hh = cfg.get_tile_rect(hc, hr)
                hs_rect = QRectF(
                    self.pan_offset.x() + hx * self.zoom,
                    self.pan_offset.y() + hy * self.zoom,
                    hw * self.zoom,
                    hh * self.zoom,
                )
                painter.fillRect(hs_rect, QColor(255, 255, 255, 30))
                h_pen = QPen(QColor(255, 255, 255, 180))
                h_pen.setWidth(1)
                painter.setPen(h_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(hs_rect)

        # Selection block
        if getattr(self, "has_selection", True) and grid["cols"] > 0 and grid["rows"] > 0:
            c1 = max(0, min(self.sel_start_col, self.sel_end_col))
            c2 = min(grid["cols"] - 1, max(self.sel_start_col, self.sel_end_col))
            r1 = max(0, min(self.sel_start_row, self.sel_end_row))
            r2 = min(grid["rows"] - 1, max(self.sel_start_row, self.sel_end_row))

            x1, y1, _, _ = cfg.get_tile_rect(c1, r1)
            x2, y2, tw2, th2 = cfg.get_tile_rect(c2, r2)
            sel_world_rect = QRectF(x1, y1, (x2 + tw2) - x1, (y2 + th2) - y1)

            sel_screen = QRectF(
                self.pan_offset.x() + sel_world_rect.x() * self.zoom,
                self.pan_offset.y() + sel_world_rect.y() * self.zoom,
                sel_world_rect.width() * self.zoom,
                sel_world_rect.height() * self.zoom,
            )

            # Highlight fill
            painter.fillRect(sel_screen, QColor(59, 130, 246, 65))

            # Primary outer selection border
            sel_pen = QPen(QColor("#38bdf8"))
            sel_pen.setWidth(2)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(sel_screen)

            # Sub-tile internal cells
            if c1 != c2 or r1 != r2:
                inner_pen = QPen(QColor(56, 189, 248, 120))
                inner_pen.setWidth(1)
                inner_pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(inner_pen)
                for r in range(r1, r2 + 1):
                    for c in range(c1, c2 + 1):
                        ix, iy, iw, ih = cfg.get_tile_rect(c, r)
                        ic_rect = QRectF(
                            self.pan_offset.x() + ix * self.zoom,
                            self.pan_offset.y() + iy * self.zoom,
                            iw * self.zoom,
                            ih * self.zoom,
                        )
                        painter.drawRect(ic_rect)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        delta_x = event.angleDelta().x()
        if delta == 0 and delta_x == 0:
            return

        # 1. Ctrl + Wheel: Smooth Zoom centered at mouse cursor
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if delta > 0 else (1.0 / 1.15)
            old_zoom = self.zoom
            new_zoom = max(0.25, min(self.zoom * factor, 16.0))
            if new_zoom == old_zoom:
                return

            mouse_pos = event.position()
            world_before = self.screen_to_world(mouse_pos)
            self.zoom = new_zoom
            world_after = self.screen_to_world(mouse_pos)
            self.pan_offset += (world_after - world_before) * self.zoom

            self.save_current_view_state()
            self.zoom_changed.emit(self.zoom)
            self.update()
            event.accept()
            return

        # 2. Shift + Wheel: Horizontal scroll/pan
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            step = (delta if delta != 0 else delta_x)
            self.pan_offset.setX(self.pan_offset.x() + step)
            self.save_current_view_state()
            self.update()
            event.accept()
            return

        # 3. Standard Wheel: Vertical scroll/pan
        if delta != 0:
            self.pan_offset.setY(self.pan_offset.y() + delta)
            self.save_current_view_state()
            self.update()
            event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        # Middle click or Space+LMB -> Pan
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self.space_pressed
        ):
            self.is_panning = True
            self.last_mouse_pos = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        # Left Click: Select cell or multi-tile block
        if event.button() == Qt.MouseButton.LeftButton:
            world = self.screen_to_world(pos)
            cell = self.world_to_cell(world)
            if cell:
                self.has_selection = True
                col, row = cell
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.sel_end_col = col
                    self.sel_end_row = row
                else:
                    self.is_selecting = True
                    self.sel_start_col = col
                    self.sel_start_row = row
                    self.sel_end_col = col
                    self.sel_end_row = row

                self._emit_selection()
                self.save_current_view_state()
                self.update()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        world = self.screen_to_world(pos)

        # Pan Drag
        if self.is_panning:
            diff = pos - self.last_mouse_pos
            self.pan_offset += diff
            self.last_mouse_pos = pos
            self.save_current_view_state()
            self.update()
            event.accept()
            return

        # Selection Drag (Multi-tile rectangular block selection)
        if self.is_selecting and (event.buttons() & Qt.MouseButton.LeftButton):
            cell = self.world_to_cell(world)
            if cell:
                self.sel_end_col, self.sel_end_row = cell
                self._emit_selection()
                self.save_current_view_state()
                self.update()
            event.accept()
            return

        # Hover update
        prev_hover = self.hover_cell
        self.hover_cell = self.world_to_cell(world)
        if self.hover_cell != prev_hover:
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton) and self.is_panning:
            self.is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.save_current_view_state()
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self._emit_selection()
            self.save_current_view_state()
            self.update()
            event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.space_pressed = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif event.key() == Qt.Key.Key_A and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.select_all()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.space_pressed = False
            if not self.is_panning:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            super().keyReleaseEvent(event)

    def _emit_selection(self) -> None:
        if not self.current_asset:
            return

        cfg = self.current_asset.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
        grid = cfg.compute_grid(self.current_asset.width, self.current_asset.height)
        if grid["cols"] <= 0 or grid["rows"] <= 0:
            return

        c1 = max(0, min(self.sel_start_col, self.sel_end_col))
        c2 = min(grid["cols"] - 1, max(self.sel_start_col, self.sel_end_col))
        r1 = max(0, min(self.sel_start_row, self.sel_end_row))
        r2 = min(grid["rows"] - 1, max(self.sel_start_row, self.sel_end_row))

        cols_count = c2 - c1 + 1
        rows_count = r2 - r1 + 1

        sx, sy, _, _ = cfg.get_tile_rect(c1, r1)
        sub_w = cols_count * cfg.tile_width + (cols_count - 1) * cfg.spacing_x
        sub_h = rows_count * cfg.tile_height + (rows_count - 1) * cfg.spacing_y

        sub_tile = SelectedSubTile(
            asset_id=self.current_asset.id,
            col=c1,
            row=r1,
            cols_count=cols_count,
            rows_count=rows_count,
            sub_x=sx,
            sub_y=sy,
            sub_w=sub_w,
            sub_h=sub_h,
            tile_width=cfg.tile_width,
            tile_height=cfg.tile_height,
            spacing_x=cfg.spacing_x,
            spacing_y=cfg.spacing_y,
            asset_name=self.current_asset.name,
        )
        self.asset_manager.select_asset(self.current_asset, sub_tile)
        self.selection_changed.emit(sub_tile)


class TilesetTreeItem(QTreeWidgetItem):
    """QTreeWidgetItem with backwards-compatible parameterless .text() and .icon()."""
    def text(self, column: int = 0) -> str:
        return super().text(column)

    def icon(self, column: int = 0) -> QIcon:
        return super().icon(column)


class TilesetTreeWidget(QTreeWidget):
    """
    Hierarchical tree widget for managing imported tilesets inside custom user folders.
    Supports drag and drop reordering, external file/folder drop, renaming, and selection.
    """
    def __init__(self, palette_widget: "TilesetPaletteWidget", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.palette = palette_widget
        self.setHeaderHidden(True)
        self.setIndentation(16)
        self.setAnimated(False)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._drag_items: List[Tuple[str, str]] = []
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 4px;
                color: #e4e4e7;
                font-size: 11px;
                padding: 2px;
            }
            QTreeWidget::item {
                padding: 4px 4px;
                border-radius: 3px;
                margin: 1px 0px;
            }
            QTreeWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 600;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #272730;
            }
        """)

    def count(self) -> int:
        return len(self._get_all_tileset_items())

    def item(self, index: int) -> Optional[TilesetTreeItem]:
        items = self._get_all_tileset_items()
        if 0 <= index < len(items):
            return items[index]
        return None

    def setCurrentRow(self, row: int) -> None:
        it = self.item(row)
        if it:
            self.setCurrentItem(it)

    def _get_all_tileset_items(self) -> List[TilesetTreeItem]:
        res: List[TilesetTreeItem] = []
        def _collect(item: QTreeWidgetItem):
            if item.data(0, Qt.ItemDataRole.UserRole) == "tileset":
                res.append(item)  # type: ignore
            for i in range(item.childCount()):
                _collect(item.child(i))
        for i in range(self.topLevelItemCount()):
            _collect(self.topLevelItem(i))
        return res

    def selected_library_items(self) -> List[QTreeWidgetItem]:
        selected: List[QTreeWidgetItem] = []

        def collect(item: QTreeWidgetItem) -> None:
            if item.isSelected():
                selected.append(item)
            for index in range(item.childCount()):
                collect(item.child(index))

        for index in range(self.topLevelItemCount()):
            collect(self.topLevelItem(index))
        return selected

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (event.button() == Qt.MouseButton.LeftButton
                and not self.itemAt(event.position().toPoint())
                and not self._drag_items):
            self.palette._hidden_selection.clear()
        super().mousePressEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        self._drag_items = [
            (item.data(0, Qt.ItemDataRole.UserRole),
             item.data(0, Qt.ItemDataRole.UserRole + 1))
            for item in self.selected_library_items()
        ]
        self._drag_items.extend(
            key for key in self.palette._hidden_selection if key not in self._drag_items
        )
        if not self._drag_items:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-tmm-library-items", b"1")
        drag.setMimeData(mime)
        pixmap = QPixmap(100, 30)
        pixmap.fill(QColor("#2563eb"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, str(len(self._drag_items)))
        painter.end()
        drag.setPixmap(pixmap)
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self._drag_items = []

    def dropEvent(self, event: QDropEvent) -> None:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(pos)
        target_category = self.palette._get_category_path_for_item(target_item)

        # External file/folder drop from OS file manager
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            local_paths = [
                u.toLocalFile()
                for u in urls
                if u.isLocalFile()
                and os.path.exists(u.toLocalFile())
            ]
            for fpath in local_paths:
                try:
                    if os.path.isdir(fpath):
                        self.palette.import_folder_from_path(
                            fpath,
                            target_category=target_category,
                            show_message=len(local_paths) == 1,
                            refresh=False,
                        )
                    elif os.path.isfile(fpath):
                        self.palette.import_file_from_path(
                            fpath, target_category=target_category, refresh=False
                        )
                except Exception:
                    logger.exception(
                        "Nie udało się zaimportować przeciągniętej ścieżki: %s",
                        fpath,
                    )
                    QMessageBox.critical(
                        self,
                        "Błąd importu",
                        f"Nie udało się zaimportować: {fpath}",
                    )
            if local_paths:
                self.palette.refresh_tilesets()
                self.palette._auto_save_library()
            event.acceptProposedAction()
            return

        if event.source() == self and self._drag_items:
            if self.palette._move_library_items(self._drag_items, target_category):
                event.setDropAction(Qt.DropAction.MoveAction)
                event.accept()
            else:
                event.ignore()
            return
        event.ignore()


class GlobalImportSettingsDialog(QDialog):
    """Dialog for editing global tileset import default parameters."""
    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle(tr("dialog.import_settings.title"))
        self.setMinimumWidth(380)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        cfg = self.config_manager.get_import_settings()

        self.spin_width = QSpinBox()
        self.spin_width.setRange(4, 512)
        self.spin_width.setValue(cfg.get("default_tile_width", 32))
        form.addRow(tr("dialog.import_settings.default_width"), self.spin_width)

        self.spin_height = QSpinBox()
        self.spin_height.setRange(4, 512)
        self.spin_height.setValue(cfg.get("default_tile_height", 32))
        form.addRow(tr("dialog.import_settings.default_height"), self.spin_height)

        # Quick preset buttons
        preset_box = QHBoxLayout()
        for w, h in [(16, 16), (24, 24), (32, 32), (32, 48), (48, 48), (64, 64)]:
            btn = QPushButton(f"{w}x{h}")
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda _, pw=w, ph=h: self._set_dims(pw, ph))
            preset_box.addWidget(btn)
        form.addRow(tr("dialog.tileset_import.presets"), preset_box)

        self.spin_margin_x = QSpinBox()
        self.spin_margin_x.setRange(0, 128)
        self.spin_margin_x.setValue(cfg.get("default_margin_x", 0))
        form.addRow(tr("dialog.import_settings.margin_x"), self.spin_margin_x)

        self.spin_margin_y = QSpinBox()
        self.spin_margin_y.setRange(0, 128)
        self.spin_margin_y.setValue(cfg.get("default_margin_y", 0))
        form.addRow(tr("dialog.import_settings.margin_y"), self.spin_margin_y)

        self.spin_spacing_x = QSpinBox()
        self.spin_spacing_x.setRange(0, 64)
        self.spin_spacing_x.setValue(cfg.get("default_spacing_x", 0))
        form.addRow(tr("dialog.import_settings.spacing_x"), self.spin_spacing_x)

        self.spin_spacing_y = QSpinBox()
        self.spin_spacing_y.setRange(0, 64)
        self.spin_spacing_y.setValue(cfg.get("default_spacing_y", 0))
        form.addRow(tr("dialog.import_settings.spacing_y"), self.spin_spacing_y)

        self.chk_skip_single = SwitchToggle(
            tr("dialog.import_settings.skip_single"),
            checked=cfg.get("skip_dialog_on_single", False),
        )
        form.addRow(self.chk_skip_single)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save_settings)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _set_dims(self, w: int, h: int) -> None:
        self.spin_width.setValue(w)
        self.spin_height.setValue(h)

    def _save_settings(self) -> None:
        self.config_manager.set_import_settings(
            tile_width=self.spin_width.value(),
            tile_height=self.spin_height.value(),
            margin_x=self.spin_margin_x.value(),
            margin_y=self.spin_margin_y.value(),
            spacing_x=self.spin_spacing_x.value(),
            spacing_y=self.spin_spacing_y.value(),
            skip_dialog_on_single=self.chk_skip_single.isChecked(),
        )
        self.accept()


class TilesetPaletteWidget(QWidget):
    """
    Two-section vertical layout for tileset management:
    - TOP SECTION: Tileset Canvas Preview & Tile Selector (occupies majority of height,
      uniform regular grid overlay, single & multi-tile rectangular selection, zoom & pan).
      NO browser-like tabs. Selection happens strictly via the lower library tree.
    - DRAGGABLE SPLITTER: Smooth vertical separator with state persistence and minimum heights.
    - BOTTOM SECTION: Tileset Library Tree (hierarchical folders, subfolders, drag & drop,
      recursive folder import, global settings, renaming, safe deletion, and auto-save).
    """
    tileset_tab_changed = pyqtSignal(str)  # asset_id (signal retained for backwards compatibility)
    tileset_selected = pyqtSignal(str)     # asset_id

    def __init__(
        self,
        asset_manager: AssetManager,
        config_manager: Optional[ConfigManager] = None,
        parent: Optional[QWidget] = None,
        standalone: bool = True,
    ):
        super().__init__(parent)
        self.asset_manager = asset_manager
        self.config_manager = config_manager or ConfigManager()
        self.standalone = standalone
        self.active_asset_id: Optional[str] = None
        self.open_tileset_ids: List[str] = []  # For backward compatibility
        self.expanded_folders: List[str] = []
        self._hidden_selection: Set[Tuple[str, str]] = set()
        self.autotile_buttons: Dict[str, QToolButton] = {}
        self.selected_autotile_id: Optional[str] = None
        self.autotile_engine: Optional[Any] = None

        self.setAcceptDrops(True)
        self._init_ui()
        self._connect_signals()
        get_localization().languageChanged.connect(self._apply_language)
        if self.standalone:
            self.restore_splitter_state()
        self.refresh_tilesets()
        self.refresh_autotiles()

    def _apply_language(self, _language: str) -> None:
        self.btn_config.setToolTip(tr("palette.slicer_tooltip"))
        self.btn_fit.setToolTip(tr("palette.fit_tooltip"))
        self.preview_thumb.setToolTip(tr("palette.preview_tooltip"))
        self.btn_zoom_out.setToolTip(tr("palette.zoom_out_tooltip"))
        self.btn_zoom_in.setToolTip(tr("palette.zoom_in_tooltip"))
        self.btn_zoom_100.setToolTip(tr("palette.zoom_100_tooltip"))
        self.btn_add_files.setToolTip(tr("palette.add_files_tooltip"))
        self.btn_import_folder.setToolTip(tr("palette.add_folder_tooltip"))
        self.btn_new_folder.setToolTip(tr("palette.new_folder_tooltip"))
        self.btn_rename.setToolTip(tr("palette.rename_tooltip"))
        self.btn_delete.setToolTip(tr("palette.delete_tooltip"))
        self.btn_settings.setToolTip(tr("palette.settings_tooltip"))
        self.canvas.update()
        self.refresh_tilesets()

    @property
    def tab_bar(self):
        """
        Backward compatibility stub for tests checking tab_bar.count().
        There are NO visual tabs in the UI; selection is driven by the library tree.
        """
        class _DummyTabBar:
            def __init__(self, owner: "TilesetPaletteWidget"):
                self.owner = owner
            def count(self) -> int:
                return len([
                    a for a in self.owner.asset_manager.assets.values()
                    if a.asset_type == AssetType.TILESET
                ])
        return _DummyTabBar(self)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Vertical Splitter
        self.splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStyleSheet("""
            QSplitter::handle:vertical {
                background-color: #27272a;
                height: 5px;
                margin: 1px 0px;
                border-top: 1px solid #3f3f46;
                border-bottom: 1px solid #18181b;
            }
            QSplitter::handle:vertical:hover {
                background-color: #3b82f6;
            }
        """)

        # ==========================================
        # 1. GÓRNA SEKCJA – PODGLĄD TILESETU I WYBÓR KAFELKÓW
        # ==========================================
        self.top_widget = QWidget(self if self.standalone else None)
        self.top_widget.setMinimumHeight(140)
        top_layout = QVBoxLayout(self.top_widget)
        top_layout.setContentsMargins(4, 4, 4, 2)
        top_layout.setSpacing(4)

        # Header: Active tileset title & Quick Action buttons (NO TABS!)
        top_header = QHBoxLayout()
        top_header.setContentsMargins(2, 2, 2, 2)
        top_header.setSpacing(4)

        self.lbl_active_title = ElidedLabel(tr("palette.preview_empty"))
        self.lbl_active_title.setStyleSheet("color: #93c5fd; font-size: 11px; font-weight: bold;")
        top_header.addWidget(self.lbl_active_title, 1)

        self.btn_config = QToolButton(self.top_widget)
        self.btn_config.setIcon(IconFactory.get_icon("settings", 16))
        self.btn_config.setFixedSize(26, 26)
        self.btn_config.setToolTip(tr("palette.slicer_tooltip"))
        self.btn_config.setStyleSheet(self._button_style())
        self.btn_config.clicked.connect(self._open_slicer_dialog)
        top_header.addWidget(self.btn_config)

        self.btn_fit = QToolButton(self.top_widget)
        self.btn_fit.setIcon(IconFactory.get_icon("fit", 16))
        self.btn_fit.setFixedSize(26, 26)
        self.btn_fit.setToolTip(tr("palette.fit_tooltip"))
        self.btn_fit.setStyleSheet(self._button_style())
        self.btn_fit.clicked.connect(self._fit_to_view)
        top_header.addWidget(self.btn_fit)

        top_layout.addLayout(top_header)

        # RPG Maker Autotiles Quick Selection Strip
        self.autotile_strip = QWidget(self.top_widget)
        autotile_strip_layout = QHBoxLayout(self.autotile_strip)
        autotile_strip_layout.setContentsMargins(2, 0, 2, 2)
        autotile_strip_layout.setSpacing(4)

        self.lbl_autotiles_title = QLabel("Autotile:", self.autotile_strip)
        self.lbl_autotiles_title.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: 600;")
        autotile_strip_layout.addWidget(self.lbl_autotiles_title)

        self.autotiles_scroll = QScrollArea(self.autotile_strip)
        self.autotiles_scroll.setFixedHeight(34)
        self.autotiles_scroll.setWidgetResizable(True)
        self.autotiles_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.autotiles_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.autotiles_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.autotiles_content = QWidget()
        self.autotiles_layout = QHBoxLayout(self.autotiles_content)
        self.autotiles_layout.setContentsMargins(0, 0, 0, 0)
        self.autotiles_layout.setSpacing(4)
        self.autotiles_layout.addStretch(1)
        self.autotiles_scroll.setWidget(self.autotiles_content)
        autotile_strip_layout.addWidget(self.autotiles_scroll, 1)

        self.btn_add_autotile = QToolButton(self.autotile_strip)
        self.btn_add_autotile.setIcon(IconFactory.get_icon("plus", 14))
        self.btn_add_autotile.setFixedSize(26, 26)
        self.btn_add_autotile.setToolTip("Zaimportuj lub stwórz nowy RPG Maker Autotile...")
        self.btn_add_autotile.setStyleSheet(self._button_style())
        self.btn_add_autotile.clicked.connect(self._open_autotile_import_dialog)
        autotile_strip_layout.addWidget(self.btn_add_autotile)

        top_layout.addWidget(self.autotile_strip)

        # Central 2D Interactive Canvas
        self.canvas = TilesetCanvas(self.asset_manager, self.top_widget)
        self.canvas.selection_changed.connect(self._on_selection_changed)
        top_layout.addWidget(self.canvas, 1)

        # Bottom Info Bar inside top preview section
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(2, 2, 2, 2)
        info_layout.setSpacing(6)

        # Live tile selection preview thumbnail
        self.preview_thumb = QLabel(self.top_widget)
        self.preview_thumb.setFixedSize(26, 26)
        self.preview_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_thumb.setStyleSheet("""
            QLabel {
                background: #18181b;
                border: 1px solid #3f3f46;
                border-radius: 4px;
            }
        """)
        self.preview_thumb.setToolTip(tr("palette.preview_tooltip"))
        info_layout.addWidget(self.preview_thumb)

        self.lbl_info = ElidedLabel("Brak wyboru")
        self.lbl_info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        info_layout.addWidget(self.lbl_info, 1)

        # Zoom Controls
        self.btn_zoom_out = QToolButton(self.top_widget)
        self.btn_zoom_out.setIcon(IconFactory.get_icon("zoom-out", 14))
        self.btn_zoom_out.setFixedSize(26, 26)
        self.btn_zoom_out.setToolTip(tr("palette.zoom_out_tooltip"))
        self.btn_zoom_out.setStyleSheet(self._button_style())
        self.btn_zoom_out.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom / 1.25))
        info_layout.addWidget(self.btn_zoom_out)

        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(25, 400)
        self.slider_zoom.setValue(150)
        self.slider_zoom.setFixedWidth(55)
        self.slider_zoom.valueChanged.connect(lambda v: self.canvas.set_zoom(v / 100.0))
        info_layout.addWidget(self.slider_zoom)

        self.btn_zoom_in = QToolButton(self.top_widget)
        self.btn_zoom_in.setIcon(IconFactory.get_icon("zoom-in", 14))
        self.btn_zoom_in.setFixedSize(26, 26)
        self.btn_zoom_in.setToolTip(tr("palette.zoom_in_tooltip"))
        self.btn_zoom_in.setStyleSheet(self._button_style())
        self.btn_zoom_in.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom * 1.25))
        info_layout.addWidget(self.btn_zoom_in)

        self.btn_zoom_100 = QToolButton(self.top_widget)
        self.btn_zoom_100.setText("1:1")
        self.btn_zoom_100.setFixedSize(28, 26)
        self.btn_zoom_100.setToolTip(tr("palette.zoom_100_tooltip"))
        self.btn_zoom_100.setStyleSheet(self._button_style())
        self.btn_zoom_100.clicked.connect(lambda: self.canvas.set_zoom(1.0))
        info_layout.addWidget(self.btn_zoom_100)

        self.canvas.zoom_changed.connect(self._on_canvas_zoom_changed)
        top_layout.addLayout(info_layout)
        if self.standalone:
            self.splitter.addWidget(self.top_widget)

        # ==========================================
        # 2. DOLNA SEKCJA – BIBLIOTEKA ZAIMPORTOWANYCH TILESETÓW (DRZEWO)
        # ==========================================
        self.bottom_widget = QWidget(self if self.standalone else None)
        self.bottom_widget.setMinimumHeight(120)
        bottom_layout = QVBoxLayout(self.bottom_widget)
        bottom_layout.setContentsMargins(4, 2, 4, 4)
        bottom_layout.setSpacing(4)

        # Header for the library section
        lib_header = QHBoxLayout()
        lib_header.setContentsMargins(2, 2, 2, 2)
        lib_header.setSpacing(3)

        self.lbl_list_title = ElidedLabel(
            tr(
                "palette.library_title" if self.standalone else "palette.tilesets_title",
                count=0,
            )
        )
        self.lbl_list_title.setStyleSheet("color: #e4e4e7; font-size: 11px; font-weight: 600;")
        lib_header.addWidget(self.lbl_list_title)
        lib_header.addStretch(1)

        # Action buttons for library management - uniform 26x26 icon-only buttons
        self.btn_add_files = QToolButton(self.bottom_widget)
        self.btn_add_files.setIcon(IconFactory.get_icon("file-plus", 14))
        self.btn_add_files.setFixedSize(26, 26)
        self.btn_add_files.setToolTip(tr("palette.add_files_tooltip"))
        self.btn_add_files.setStyleSheet(self._button_style())
        self.btn_add_files.clicked.connect(lambda: self._import_files_action())
        lib_header.addWidget(self.btn_add_files)

        self.btn_import_folder = QToolButton(self.bottom_widget)
        self.btn_import_folder.setIcon(IconFactory.get_icon("folder-open", 14))
        self.btn_import_folder.setFixedSize(26, 26)
        self.btn_import_folder.setToolTip(tr("palette.add_folder_tooltip"))
        self.btn_import_folder.setStyleSheet(self._button_style())
        self.btn_import_folder.clicked.connect(lambda: self._import_folder_action())
        lib_header.addWidget(self.btn_import_folder)

        self.btn_new_folder = QToolButton(self.bottom_widget)
        self.btn_new_folder.setIcon(IconFactory.get_icon("folder-plus", 14))
        self.btn_new_folder.setFixedSize(26, 26)
        self.btn_new_folder.setToolTip(tr("palette.new_folder_tooltip"))
        self.btn_new_folder.setStyleSheet(self._button_style())
        self.btn_new_folder.clicked.connect(lambda: self._create_folder_action())
        lib_header.addWidget(self.btn_new_folder)

        self.btn_rename = QToolButton(self.bottom_widget)
        self.btn_rename.setIcon(IconFactory.get_icon("pencil", 14))
        self.btn_rename.setFixedSize(26, 26)
        self.btn_rename.setToolTip(tr("palette.rename_tooltip"))
        self.btn_rename.setStyleSheet(self._button_style())
        self.btn_rename.clicked.connect(self._rename_action)
        lib_header.addWidget(self.btn_rename)

        self.btn_delete = QToolButton(self.bottom_widget)
        self.btn_delete.setIcon(IconFactory.get_icon("trash", 14))
        self.btn_delete.setFixedSize(26, 26)
        self.btn_delete.setToolTip(tr("palette.delete_tooltip"))
        self.btn_delete.setStyleSheet(self._button_style())
        self.btn_delete.clicked.connect(self._delete_action)
        lib_header.addWidget(self.btn_delete)

        self.btn_settings = QToolButton(self.bottom_widget)
        self.btn_settings.setIcon(IconFactory.get_icon("settings", 14))
        self.btn_settings.setFixedSize(26, 26)
        self.btn_settings.setToolTip(tr("palette.settings_tooltip"))
        self.btn_settings.setStyleSheet(self._button_style())
        self.btn_settings.clicked.connect(self._open_global_settings_dialog)
        lib_header.addWidget(self.btn_settings)

        bottom_layout.addLayout(lib_header)
        self.txt_library_search = QLineEdit(self.bottom_widget)
        self.txt_library_search.setPlaceholderText("Szukaj w bibliotece…")
        self.txt_library_search.setClearButtonEnabled(True)
        self.library_search_timer = QTimer(self)
        self.library_search_timer.setSingleShot(True)
        self.library_search_timer.setInterval(75)
        self.library_search_timer.timeout.connect(self._apply_library_filter)
        self.txt_library_search.textChanged.connect(
            lambda _text: self.library_search_timer.start()
        )
        bottom_layout.addWidget(self.txt_library_search)

        # Hierarchical Tree Widget displaying folders, subfolders and tilesets
        self.tree = TilesetTreeWidget(self, self.bottom_widget)
        self.tileset_list = self.tree
        self.tree.currentItemChanged.connect(self._on_tree_item_changed)
        self.tree.itemSelectionChanged.connect(self._on_library_selection_changed)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_tree_double_clicked)
        bottom_layout.addWidget(self.tree, 1)

        if self.standalone:
            self.splitter.addWidget(self.bottom_widget)
            # Splitter proportion defaults (top gets ~70%, bottom gets ~30%)
            self.splitter.setStretchFactor(0, 7)
            self.splitter.setStretchFactor(1, 3)
            self.splitter.splitterMoved.connect(lambda pos, index: self.save_splitter_state())
            main_layout.addWidget(self.splitter)
        else:
            self.splitter.addWidget(QWidget())
            self.splitter.addWidget(QWidget())
            main_layout.addWidget(self.splitter)
            self.hide()

    def get_preview_widget(self) -> QWidget:
        """Returns the top section widget (interactive canvas & preview controls)."""
        return self.top_widget

    def get_library_widget(self) -> QWidget:
        """Returns the bottom section widget (tileset library & tree controls)."""
        return self.bottom_widget

    @staticmethod
    def _button_style() -> str:
        return """
            QToolButton {
                background: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 2px;
                font-size: 11px;
                font-weight: 500;
            }
            QToolButton:hover {
                background: #3f3f46;
                color: #ffffff;
                border-color: #60a5fa;
            }
            QToolButton:pressed {
                background: #1d4ed8;
                border-color: #2563eb;
            }
            QToolButton:disabled {
                color: #52525b;
                border-color: #27272a;
                background: #18181b;
            }
        """

    def _connect_signals(self) -> None:
        self.asset_manager.assets_changed.connect(self.refresh_tilesets)
        self.asset_manager.categories_changed.connect(self.refresh_tilesets)

    def save_splitter_state(self) -> None:
        """Persists the vertical splitter state to QSettings and ConfigManager."""
        state = self.splitter.saveState()
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        settings.setValue("tileset_panel/splitter_state", state)
        if self.config_manager:
            b64 = state.toBase64().data().decode("ascii")
            ws = self.config_manager.get_window_state()
            self.config_manager.save_window_state(
                geometry_b64=ws.get("geometry", ""),
                state_b64=ws.get("state", ""),
                splitter_state_b64=b64,
            )

    def restore_splitter_state(self) -> None:
        """Restores the vertical splitter state from QSettings or ConfigManager."""
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        state = settings.value("tileset_panel/splitter_state")
        if state:
            if isinstance(state, QByteArray) and not state.isEmpty():
                self.splitter.restoreState(state)
                return
            elif isinstance(state, (bytes, bytearray)) and len(state) > 0:
                self.splitter.restoreState(state)
                return

        if self.config_manager:
            ws = self.config_manager.get_window_state()
            b64 = ws.get("splitter_state", "")
            if b64:
                qba = QByteArray.fromBase64(b64.encode("ascii"))
                if not qba.isEmpty():
                    self.splitter.restoreState(qba)
                    return

        self.splitter.setSizes([450, 160])

    def reset_splitter_sizes(self) -> None:
        """Resets splitter to default 70/30 proportion."""
        self.splitter.setSizes([450, 160])
        self.save_splitter_state()

    def _on_canvas_zoom_changed(self, z: float) -> None:
        val = int(round(z * 100))
        self.slider_zoom.blockSignals(True)
        self.slider_zoom.setValue(max(self.slider_zoom.minimum(), min(val, self.slider_zoom.maximum())))
        self.slider_zoom.blockSignals(False)

    def _get_import_config(self) -> Dict[str, Any]:
        return self.config_manager.get_import_settings()

    def _auto_save_library(self) -> bool:
        if self.config_manager:
            return self.config_manager.save_tileset_library(
                asset_manager=self.asset_manager,
                active_asset_id=self.active_asset_id,
                expanded_folders=self.expanded_folders,
            )
        return False

    @staticmethod
    def _remap_folder_path(path: str, mapping: Dict[str, str]) -> str:
        for old, new in mapping.items():
            if path == old or path.startswith(old + "/"):
                return new + path[len(old):]
        return path

    def _move_library_items(self, items: List[Tuple[str, str]], destination: str) -> bool:
        old_expanded = list(self.expanded_folders)

        def persist(mapping: Dict[str, str]) -> bool:
            self.expanded_folders = [
                self._remap_folder_path(path, mapping) for path in old_expanded
            ]
            return self._auto_save_library()

        try:
            mapping = self.asset_manager.move_library_items(items, destination, persist)
        except (ValueError, OSError) as exc:
            self.expanded_folders = old_expanded
            logger.warning("Library move cancelled: %s", exc)
            QMessageBox.warning(self, tr("palette.move_error_title"), str(exc))
            return False
        except Exception as exc:
            self.expanded_folders = old_expanded
            logger.exception("Unexpected library move failure")
            QMessageBox.warning(self, tr("palette.move_error_title"), str(exc))
            return False

        def remap_item(item: QTreeWidgetItem) -> None:
            if item.data(0, Qt.ItemDataRole.UserRole) == "folder":
                path = item.data(0, Qt.ItemDataRole.UserRole + 1)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, self._remap_folder_path(path, mapping))
            for index in range(item.childCount()):
                remap_item(item.child(index))

        for index in range(self.tree.topLevelItemCount()):
            remap_item(self.tree.topLevelItem(index))
        self._hidden_selection = {
            (kind, self._remap_folder_path(value, mapping) if kind == "folder" else value)
            for kind, value in self._hidden_selection
        }
        self.asset_manager.categories_changed.emit()
        self.asset_manager.assets_changed.emit()
        return True

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        itype = item.data(0, Qt.ItemDataRole.UserRole)
        if itype == "folder":
            fpath = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if fpath and fpath not in self.expanded_folders:
                self.expanded_folders.append(fpath)
                self._auto_save_library()

    def _on_item_collapsed(self, item: QTreeWidgetItem) -> None:
        itype = item.data(0, Qt.ItemDataRole.UserRole)
        if itype == "folder":
            fpath = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if fpath in self.expanded_folders:
                self.expanded_folders.remove(fpath)
                self._auto_save_library()

    def _get_category_path_for_item(self, item: Optional[QTreeWidgetItem]) -> str:
        if not item:
            return ""
        itype = item.data(0, Qt.ItemDataRole.UserRole)
        if itype == "folder":
            return item.data(0, Qt.ItemDataRole.UserRole + 1) or ""
        elif itype == "tileset":
            parent = item.parent()
            if parent:
                return parent.data(0, Qt.ItemDataRole.UserRole + 1) or ""
            return ""
        return ""

    def refresh_tilesets(self) -> None:
        """Syncs tilesets and category tree into hierarchical QTreeWidget."""
        selected = {
            (item.data(0, Qt.ItemDataRole.UserRole), item.data(0, Qt.ItemDataRole.UserRole + 1))
            for item in self.tree.selected_library_items()
        } | self._hidden_selection
        current_item = self.tree.currentItem()
        current_key = (
            (current_item.data(0, Qt.ItemDataRole.UserRole),
             current_item.data(0, Qt.ItemDataRole.UserRole + 1))
            if current_item else None
        )
        had_items = self.tree.topLevelItemCount() > 0
        all_tilesets = [
            a for a in self.asset_manager.assets.values()
            if a.asset_type == AssetType.TILESET
        ]
        title_key = "palette.library_title" if self.standalone else "palette.tilesets_title"
        self.lbl_list_title.setText(tr(title_key, count=len(all_tilesets)))

        self.tree.blockSignals(True)
        self.tree.clear()

        # Track which assets have been placed in tree
        placed_asset_ids: Set[str] = set()

        def _add_category_nodes(cat_node: CategoryNode, parent_item: Optional[QTreeWidgetItem]) -> None:
            for child_name, child_node in sorted(cat_node.children.items(), key=lambda kv: kv[0].lower()):
                folder_item = TilesetTreeItem()
                folder_item.setData(0, Qt.ItemDataRole.UserRole, "folder")
                folder_item.setData(0, Qt.ItemDataRole.UserRole + 1, child_node.path)

                # Count tilesets in this subtree
                sub_count = len(child_node.get_all_asset_ids())
                folder_item.setIcon(0, IconFactory.get_icon("folder", 16))
                folder_item.setText(0, f"{child_node.name} ({sub_count})")
                folder_item.setToolTip(
                    0, tr("palette.folder_tooltip", path=child_node.path, count=sub_count)
                )

                if parent_item:
                    parent_item.addChild(folder_item)
                else:
                    self.tree.addTopLevelItem(folder_item)

                if child_node.path in self.expanded_folders:
                    folder_item.setExpanded(True)

                # Add subcategories
                _add_category_nodes(child_node, folder_item)

                # Add tilesets in this category
                for aid in child_node.asset_ids:
                    asset = self.asset_manager.get_asset(aid)
                    if asset and asset.asset_type == AssetType.TILESET:
                        placed_asset_ids.add(asset.id)
                        t_item = self._create_tileset_tree_item(asset)
                        folder_item.addChild(t_item)

        # 1. Populate category tree
        _add_category_nodes(self.asset_manager.category_tree.root, None)

        # 2. Add root-level tilesets or any unplaced tilesets
        for asset in all_tilesets:
            if asset.id not in placed_asset_ids:
                # Placed in root or its specified category
                cat_path = asset.category_path.strip("/")
                if not cat_path:
                    t_item = self._create_tileset_tree_item(asset)
                    self.tree.addTopLevelItem(t_item)
                    placed_asset_ids.add(asset.id)
                else:
                    node = self.asset_manager.category_tree.add_category_path(cat_path)
                    if asset.id not in node.asset_ids:
                        node.asset_ids.append(asset.id)
                    # Will be placed on next cycle or build now
                    t_item = self._create_tileset_tree_item(asset)
                    # Find folder item in tree
                    f_item = self._find_folder_item(cat_path)
                    if f_item:
                        f_item.addChild(t_item)
                    else:
                        self.tree.addTopLevelItem(t_item)
                    placed_asset_ids.add(asset.id)

        has_tilesets = len(all_tilesets) > 0
        self.btn_rename.setEnabled(has_tilesets or self.tree.topLevelItemCount() > 0)
        self.btn_delete.setEnabled(has_tilesets or self.tree.topLevelItemCount() > 0)
        self.btn_config.setEnabled(has_tilesets)
        self.btn_fit.setEnabled(has_tilesets)

        # Restore active asset
        active_asset = self.asset_manager.get_asset(self.active_asset_id) if self.active_asset_id else None
        if not active_asset and has_tilesets:
            active_asset = all_tilesets[0]
            self.active_asset_id = active_asset.id

        if active_asset:
            if not had_items and not selected:
                self._select_tree_item_for_asset(active_asset.id)
            self.canvas.set_asset(active_asset)
            self._update_info_label(active_asset)
            cfg = active_asset.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
            self.lbl_active_title.setText(
                tr(
                    "palette.sheet_title",
                    name=active_asset.name,
                    width=cfg.tile_width,
                    height=cfg.tile_height,
                )
            )
        else:
            self.active_asset_id = None
            self.canvas.set_asset(None)
            self.lbl_active_title.setText(tr("palette.preview_empty"))
            self.lbl_info.setText(tr("palette.no_tilesets_import_hint"))

        def restore_selection(item: QTreeWidgetItem) -> None:
            key = (item.data(0, Qt.ItemDataRole.UserRole), item.data(0, Qt.ItemDataRole.UserRole + 1))
            if key in selected:
                item.setSelected(True)
            if key == current_key:
                self.tree.setCurrentItem(item, 0, QItemSelectionModel.SelectionFlag.NoUpdate)
            for index in range(item.childCount()):
                restore_selection(item.child(index))

        for index in range(self.tree.topLevelItemCount()):
            restore_selection(self.tree.topLevelItem(index))
        self.tree.blockSignals(False)
        self._apply_library_filter()

    def _apply_library_filter(self) -> None:
        selected = {
            (item.data(0, Qt.ItemDataRole.UserRole), item.data(0, Qt.ItemDataRole.UserRole + 1))
            for item in self.tree.selected_library_items()
        } | self._hidden_selection
        self._hidden_selection = set()
        query = self.txt_library_search.text().strip().casefold()
        matching_ids = {
            asset.id
            for asset in self.asset_manager.search_assets(
                query=query, asset_type=AssetType.TILESET
            )
        }

        def filter_item(item: QTreeWidgetItem) -> bool:
            item_type = item.data(0, Qt.ItemDataRole.UserRole)
            key = (item_type, item.data(0, Qt.ItemDataRole.UserRole + 1))
            if item_type == "tileset":
                visible = not query or item.data(
                    0, Qt.ItemDataRole.UserRole + 1
                ) in matching_ids
                item.setHidden(not visible)
                if key in selected:
                    if visible:
                        item.setSelected(True)
                    else:
                        self._hidden_selection.add(key)
                return visible
            child_visible = False
            for child_index in range(item.childCount()):
                child_visible = filter_item(item.child(child_index)) or child_visible
            item.setHidden(bool(query) and not child_visible)
            if key in selected:
                if item.isHidden():
                    self._hidden_selection.add(key)
                else:
                    item.setSelected(True)
            if child_visible and query:
                item.setExpanded(True)
            return child_visible

        self.tree.blockSignals(True)
        for index in range(self.tree.topLevelItemCount()):
            filter_item(self.tree.topLevelItem(index))
        self.tree.blockSignals(False)

    def _on_library_selection_changed(self) -> None:
        modifiers = QApplication.keyboardModifiers()
        if not modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            self._hidden_selection.clear()

    def _create_tileset_tree_item(self, asset: Asset) -> TilesetTreeItem:
        cfg = asset.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
        grid = cfg.compute_grid(asset.width, asset.height)
        item = TilesetTreeItem()
        item.setData(0, Qt.ItemDataRole.UserRole, "tileset")
        item.setData(0, Qt.ItemDataRole.UserRole + 1, asset.id)
        item.setText(0, f"{asset.name}  ({cfg.tile_width}×{cfg.tile_height} px | {grid['cols']}×{grid['rows']})")
        item.setToolTip(
            0,
            tr(
                "palette.tileset_tooltip",
                name=asset.name,
                path=asset.file_path,
                width=asset.width,
                height=asset.height,
                cols=grid["cols"],
                rows=grid["rows"],
                count=grid["total_cells"],
            ),
        )

        thumb = self.asset_manager.get_thumbnail(asset.id, 24)
        if thumb and not thumb.isNull():
            item.setIcon(0, QIcon(thumb))
        else:
            item.setIcon(0, IconFactory.get_icon("map", 16))
        return item

    def _find_folder_item(self, path: str) -> Optional[QTreeWidgetItem]:
        def _search(item: QTreeWidgetItem) -> Optional[QTreeWidgetItem]:
            if item.data(0, Qt.ItemDataRole.UserRole) == "folder" and item.data(0, Qt.ItemDataRole.UserRole + 1) == path:
                return item
            for i in range(item.childCount()):
                res = _search(item.child(i))
                if res:
                    return res
            return None

        for idx in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(idx)
            res = _search(top)
            if res:
                return res
        return None

    def _select_tree_item_for_asset(self, asset_id: str) -> None:
        def _search(item: QTreeWidgetItem) -> Optional[QTreeWidgetItem]:
            if item.data(0, Qt.ItemDataRole.UserRole) == "tileset" and item.data(0, Qt.ItemDataRole.UserRole + 1) == asset_id:
                return item
            for i in range(item.childCount()):
                res = _search(item.child(i))
                if res:
                    return res
            return None

        for idx in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(idx)
            found = _search(top)
            if found:
                if found.isSelected():
                    self.tree.setCurrentItem(found, 0, QItemSelectionModel.SelectionFlag.NoUpdate)
                else:
                    self.tree.setCurrentItem(found)
                # Ensure parent folders are expanded
                p = found.parent()
                while p:
                    p.setExpanded(True)
                    p = p.parent()
                return

    def set_active_asset(self, asset: Optional[Asset], sub_tile: Optional[SelectedSubTile] = None) -> None:
        if not asset:
            self.active_asset_id = None
            self.canvas.set_asset(None)
            self.lbl_active_title.setText(tr("palette.preview_empty"))
            self.lbl_info.setText(tr("palette.no_tilesets"))
            return

        if asset.asset_type != AssetType.TILESET:
            self.asset_manager.set_asset_type(asset.id, AssetType.TILESET)

        is_different_asset = (self.active_asset_id != asset.id)
        self.active_asset_id = asset.id

        if not asset.tileset_config:
            asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

        cfg = asset.tileset_config
        self.lbl_active_title.setText(
            tr(
                "palette.sheet_title",
                name=asset.name,
                width=cfg.tile_width,
                height=cfg.tile_height,
            )
        )

        if is_different_asset:
            self.canvas.set_asset(asset)
            current = self.tree.currentItem()
            if not current or current.data(0, Qt.ItemDataRole.UserRole + 1) != asset.id:
                self._select_tree_item_for_asset(asset.id)
            self._auto_save_library()

        if sub_tile:
            self.canvas.sel_start_col = sub_tile.col
            self.canvas.sel_start_row = sub_tile.row
            self.canvas.sel_end_col = sub_tile.col + sub_tile.cols_count - 1
            self.canvas.sel_end_row = sub_tile.row + sub_tile.rows_count - 1
            self.canvas.save_current_view_state()
        elif is_different_asset and asset.id not in self.canvas.tileset_view_states:
            self.canvas.sel_start_col = 0
            self.canvas.sel_start_row = 0
            self.canvas.sel_end_col = 0
            self.canvas.sel_end_row = 0

        self._update_info_label(asset, sub_tile)
        self.canvas.update()

    def set_selected_sub_tile(self, sub_tile: SelectedSubTile) -> None:
        """Updates tile selection on the palette canvas without touching zoom or view position."""
        if not self.canvas.current_asset or self.canvas.current_asset.id != sub_tile.asset_id:
            asset = self.asset_manager.get_asset(sub_tile.asset_id)
            if asset:
                self.set_active_asset(asset, sub_tile)
            return

        self.canvas.sel_start_col = sub_tile.col
        self.canvas.sel_start_row = sub_tile.row
        self.canvas.sel_end_col = sub_tile.col + sub_tile.cols_count - 1
        self.canvas.sel_end_row = sub_tile.row + sub_tile.rows_count - 1
        self.canvas.save_current_view_state()
        self._update_info_label(self.canvas.current_asset, sub_tile)
        self.canvas.update()

    def _on_tree_item_changed(self, current: Optional[QTreeWidgetItem], previous: Optional[QTreeWidgetItem]) -> None:
        if not current:
            return
        itype = current.data(0, Qt.ItemDataRole.UserRole)
        if itype == "tileset":
            aid = current.data(0, Qt.ItemDataRole.UserRole + 1)
            asset = self.asset_manager.get_asset(aid)
            if asset and asset.id != self.active_asset_id:
                self.set_active_asset(asset)
                self.tileset_tab_changed.emit(asset.id)
                self.tileset_selected.emit(asset.id)
        elif itype == "folder":
            fpath = current.data(0, Qt.ItemDataRole.UserRole + 1)
            if not self.active_asset_id:
                self.lbl_active_title.setText(tr("palette.folder_title", path=fpath))

    def _on_tree_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        itype = item.data(0, Qt.ItemDataRole.UserRole)
        if itype == "tileset":
            aid = item.data(0, Qt.ItemDataRole.UserRole + 1)
            asset = self.asset_manager.get_asset(aid)
            if asset:
                self.set_active_asset(asset)
                self._open_slicer_dialog()

    def _on_tree_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        menu = QMenu(self)

        if item:
            if item.isSelected():
                self.tree.setCurrentItem(item, 0, QItemSelectionModel.SelectionFlag.NoUpdate)
            else:
                self.tree.setCurrentItem(item)
            itype = item.data(0, Qt.ItemDataRole.UserRole)
            val = item.data(0, Qt.ItemDataRole.UserRole + 1)

            if itype == "tileset":
                asset = self.asset_manager.get_asset(val)
                if asset:
                    self.set_active_asset(asset)
                    act_open = menu.addAction(
                        IconFactory.get_icon("eye", 16), tr("palette.folder_context_preview")
                    )
                    act_slicer = menu.addAction(
                        IconFactory.get_icon("slicer", 16), tr("palette.folder_context_slicer")
                    )
                    act_rename = menu.addAction(
                        IconFactory.get_icon("pencil", 16),
                        tr("palette.folder_context_rename_tileset"),
                    )
                    act_move = menu.addAction(
                        IconFactory.get_icon("folder-share", 16),
                        tr("palette.folder_context_move_tileset"),
                    )
                    menu.addSeparator()
                    act_del = menu.addAction(
                        IconFactory.get_icon("trash", 16),
                        tr("palette.folder_context_delete_tileset"),
                    )

                    action = menu.exec(self.tree.mapToGlobal(pos))
                    if action == act_open:
                        self.set_active_asset(asset)
                    elif action == act_slicer:
                        self._open_slicer_dialog()
                    elif action == act_rename:
                        self._rename_action()
                    elif action == act_move:
                        self._move_tileset_dialog(asset.id)
                    elif action == act_del:
                        self._delete_action()
                    return

            elif itype == "folder":
                folder_path = val
                act_add_files = menu.addAction(
                    IconFactory.get_icon("file-plus", 16),
                    tr("palette.folder_context_add_files"),
                )
                act_import_sub = menu.addAction(
                    IconFactory.get_icon("folder", 16),
                    tr("palette.folder_context_import_folder"),
                )
                act_new_sub = menu.addAction(
                    IconFactory.get_icon("folder-plus", 16),
                    tr("palette.folder_context_new_subfolder"),
                )
                menu.addSeparator()
                act_rename_f = menu.addAction(
                    IconFactory.get_icon("pencil", 16),
                    tr("palette.folder_context_rename"),
                )
                act_del_f = menu.addAction(
                    IconFactory.get_icon("trash", 16),
                    tr("palette.folder_context_delete"),
                )

                action = menu.exec(self.tree.mapToGlobal(pos))
                if action == act_add_files:
                    self._import_files_action(target_category=folder_path)
                elif action == act_import_sub:
                    self._import_folder_action(target_category=folder_path)
                elif action == act_new_sub:
                    self._create_folder_action(parent_path=folder_path)
                elif action == act_rename_f:
                    self._rename_action()
                elif action == act_del_f:
                    self._delete_action()
                return

        # Empty space context menu
        act_add = menu.addAction(
            IconFactory.get_icon("file-plus", 16),
            tr("palette.folder_context_import_files"),
        )
        act_imp_folder = menu.addAction(
            IconFactory.get_icon("folder", 16),
            tr("palette.folder_context_import_all"),
        )
        act_folder = menu.addAction(
            IconFactory.get_icon("folder-plus", 16),
            tr("palette.folder_context_new"),
        )
        menu.addSeparator()
        act_global = menu.addAction(
            IconFactory.get_icon("settings", 16),
            tr("palette.folder_context_settings"),
        )

        action = menu.exec(self.tree.mapToGlobal(pos))
        if action == act_add:
            self._import_files_action()
        elif action == act_imp_folder:
            self._import_folder_action()
        elif action == act_folder:
            self._create_folder_action()
        elif action == act_global:
            self._open_global_settings_dialog()

    def _create_folder_action(self, parent_path: Optional[str] = None) -> None:
        parent_path = parent_path or ""

        name, ok = QInputDialog.getText(
            self,
            "Nowy folder w bibliotece",
            f"Nazwa folderu{' (podfolder w ' + parent_path + ')' if parent_path else ''}:",
            text="Nowy folder",
        )
        if ok and name.strip():
            folder_name = name.strip().replace("/", "_")
            full_path = f"{parent_path}/{folder_name}" if parent_path else folder_name
            self.asset_manager.category_tree.add_category_path(full_path)
            if full_path not in self.expanded_folders:
                self.expanded_folders.append(full_path)
            self.refresh_tilesets()
            self._auto_save_library()

    def _rename_action(self) -> None:
        curr = self.tree.currentItem()
        if not curr:
            return
        itype = curr.data(0, Qt.ItemDataRole.UserRole)
        val = curr.data(0, Qt.ItemDataRole.UserRole + 1)

        if itype == "folder":
            old_path = val
            node = self.asset_manager.category_tree.get_node(old_path)
            if not node or not node.name:
                return
            new_name, ok = QInputDialog.getText(
                self,
                tr("dialog.library.rename_folder_title"),
                tr("dialog.library.rename_folder_prompt"),
                text=node.name,
            )
            if ok and new_name.strip():
                clean_name = new_name.strip().replace("/", "_")
                renamed_path = self.asset_manager.rename_category(old_path, clean_name)
                if renamed_path:
                    self.expanded_folders = [
                        p.replace(old_path, renamed_path, 1) if p.startswith(old_path) else p
                        for p in self.expanded_folders
                    ]
                    self.refresh_tilesets()
                    self._auto_save_library()

        elif itype == "tileset":
            asset = self.asset_manager.get_asset(val)
            if not asset:
                return
            new_name, ok = QInputDialog.getText(
                self,
                tr("dialog.library.rename_tileset_title"),
                tr("dialog.library.rename_tileset_prompt"),
                text=asset.name,
            )
            if ok and new_name.strip():
                self.asset_manager.rename_asset(asset.id, new_name.strip())
                self.refresh_tilesets()
                self._auto_save_library()

    def _delete_action(self) -> None:
        curr = self.tree.currentItem()
        if not curr:
            return
        itype = curr.data(0, Qt.ItemDataRole.UserRole)
        val = curr.data(0, Qt.ItemDataRole.UserRole + 1)

        if itype == "tileset":
            asset = self.asset_manager.get_asset(val)
            if not asset:
                return
            confirm = QMessageBox.question(
                self,
                tr("dialog.library.delete_tileset_title"),
                tr(
                    "dialog.library.delete_tileset_confirm",
                    name=asset.name,
                    path=asset.file_path,
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.asset_manager.remove_asset(asset.id)
                if self.active_asset_id == asset.id:
                    self.active_asset_id = None
                self.refresh_tilesets()
                self._auto_save_library()

        elif itype == "folder":
            folder_path = val
            node = self.asset_manager.category_tree.get_node(folder_path)
            if not node:
                return
            all_asset_ids = node.get_all_asset_ids()

            if len(all_asset_ids) > 0:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(tr("dialog.library.delete_folder_title"))
                msg_box.setText(
                    tr(
                        "dialog.library.delete_folder_contents",
                        name=node.name,
                        count=len(all_asset_ids),
                    )
                )
                btn_reparent = msg_box.addButton(
                    tr("dialog.library.move_tilesets_up"), QMessageBox.ButtonRole.ActionRole
                )
                btn_delete_all = msg_box.addButton(
                    tr("dialog.library.delete_tilesets"), QMessageBox.ButtonRole.DestructiveRole
                )
                btn_cancel = msg_box.addButton(
                    tr("button.cancel"), QMessageBox.ButtonRole.RejectRole
                )
                msg_box.setDefaultButton(btn_cancel)
                msg_box.exec()

                clicked = msg_box.clickedButton()
                if clicked == btn_cancel or clicked is None:
                    return
                delete_assets = (clicked == btn_delete_all)
                self.asset_manager.delete_category(folder_path, delete_assets=delete_assets)
            else:
                confirm = QMessageBox.question(
                    self,
                    tr("dialog.library.delete_empty_title"),
                    tr("dialog.library.delete_empty_confirm", name=node.name),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return
                self.asset_manager.delete_category(folder_path, delete_assets=False)

            if folder_path in self.expanded_folders:
                self.expanded_folders.remove(folder_path)
            self.refresh_tilesets()
            self._auto_save_library()

    def _move_tileset_dialog(self, asset_id: str) -> None:
        asset = self.asset_manager.get_asset(asset_id)
        if not asset:
            return
        root_label = tr("dialog.library.root_folder")
        paths = [root_label] + self.asset_manager.category_tree.get_all_paths()
        curr_idx = 0
        if asset.category_path in paths:
            curr_idx = paths.index(asset.category_path)

        chosen, ok = QInputDialog.getItem(
            self,
            tr("dialog.library.move_tileset_title"),
            tr("dialog.library.move_tileset_prompt", name=asset.name),
            paths,
            current=curr_idx,
            editable=False,
        )
        if ok and chosen:
            target = "" if chosen == root_label else chosen
            self._move_library_items([("tileset", asset.id)], target)

    def _import_files_action(self, target_category: Optional[str] = None) -> None:
        if target_category is None:
            curr = self.tree.currentItem()
            target_category = self._get_category_path_for_item(curr)

        files, _ = QFileDialog.getOpenFileNames(
            self,
            tr("dialog.library.select_files"),
            "",
            "Grafiki (*.png *.jpg *.jpeg *.bmp *.webp);;Wszystkie pliki (*.*)",
        )
        if not files:
            return

        import_cfg = self._get_import_config()
        first_added_asset = None
        imported_count = 0
        dup_count = 0

        # Single file import (can show slicer/import config if enabled)
        if len(files) == 1 and not import_cfg.get("skip_dialog_on_single", False):
            f = files[0]
            dlg = TilesetImportDialog(
                f,
                default_tile_size=import_cfg.get("default_tile_width", 32),
                parent=self,
            )
            if dlg.exec():
                tile_w, tile_h = dlg.get_tile_dimensions()
                asset, is_dup, err = self.asset_manager.import_single_file(
                    f,
                    target_category_path=target_category,
                    force_asset_type=AssetType.TILESET,
                )
                if asset:
                    asset.tileset_config = TilesetConfig(
                        tile_width=tile_w,
                        tile_height=tile_h,
                        margin_x=import_cfg.get("default_margin_x", 0),
                        margin_y=import_cfg.get("default_margin_y", 0),
                        spacing_x=import_cfg.get("default_spacing_x", 0),
                        spacing_y=import_cfg.get("default_spacing_y", 0),
                        start_x=import_cfg.get("default_start_x", 0),
                        start_y=import_cfg.get("default_start_y", 0),
                    )
                    first_added_asset = asset
                    imported_count += 1
                elif is_dup:
                    dup_count += 1
        else:
            # Multiple files (or skip dialog): apply global settings directly without prompting!
            def_cfg = TilesetConfig(
                tile_width=import_cfg.get("default_tile_width", 32),
                tile_height=import_cfg.get("default_tile_height", 32),
                margin_x=import_cfg.get("default_margin_x", 0),
                margin_y=import_cfg.get("default_margin_y", 0),
                spacing_x=import_cfg.get("default_spacing_x", 0),
                spacing_y=import_cfg.get("default_spacing_y", 0),
                start_x=import_cfg.get("default_start_x", 0),
                start_y=import_cfg.get("default_start_y", 0),
            )
            for f in files:
                asset, is_dup, err = self.asset_manager.import_single_file(
                    f,
                    target_category_path=target_category,
                    force_asset_type=AssetType.TILESET,
                )
                if asset:
                    asset.tileset_config = TilesetConfig(
                        tile_width=def_cfg.tile_width,
                        tile_height=def_cfg.tile_height,
                        margin_x=def_cfg.margin_x,
                        margin_y=def_cfg.margin_y,
                        spacing_x=def_cfg.spacing_x,
                        spacing_y=def_cfg.spacing_y,
                        start_x=def_cfg.start_x,
                        start_y=def_cfg.start_y,
                    )
                    if not first_added_asset:
                        first_added_asset = asset
                    imported_count += 1
                elif is_dup:
                    dup_count += 1

        if target_category and target_category not in self.expanded_folders:
            self.expanded_folders.append(target_category)

        self.refresh_tilesets()
        if first_added_asset:
            self.set_active_asset(first_added_asset)
        self._auto_save_library()

        if len(files) > 1:
            QMessageBox.information(
                self,
                tr("dialog.library.import_done_title"),
                tr(
                    "dialog.library.import_done",
                    imported=imported_count,
                    duplicates=dup_count,
                ),
            )

    def import_file_from_path(
        self,
        file_path: str,
        target_category: str = "",
        refresh: bool = True,
    ) -> None:
        """Direct file import from external drag & drop."""
        import_cfg = self._get_import_config()
        asset, is_dup, err = self.asset_manager.import_single_file(
            file_path,
            target_category_path=target_category,
            force_asset_type=AssetType.TILESET,
        )
        if asset:
            asset.tileset_config = TilesetConfig(
                tile_width=import_cfg.get("default_tile_width", 32),
                tile_height=import_cfg.get("default_tile_height", 32),
                margin_x=import_cfg.get("default_margin_x", 0),
                margin_y=import_cfg.get("default_margin_y", 0),
                spacing_x=import_cfg.get("default_spacing_x", 0),
                spacing_y=import_cfg.get("default_spacing_y", 0),
                start_x=import_cfg.get("default_start_x", 0),
                start_y=import_cfg.get("default_start_y", 0),
            )
            if target_category and target_category not in self.expanded_folders:
                self.expanded_folders.append(target_category)
            if refresh:
                self.refresh_tilesets()
            self.set_active_asset(asset)
            if refresh:
                self._auto_save_library()

    def _import_folder_action(self, target_category: Optional[str] = None) -> None:
        target_category = target_category or ""

        folder = QFileDialog.getExistingDirectory(
            self,
            tr("dialog.library.select_folder"),
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return

        self.import_folder_from_path(folder, target_category=target_category)

    def import_folder_from_path(
        self,
        folder_path: str,
        target_category: str = "",
        show_message: bool = True,
        refresh: bool = True,
    ) -> None:
        """Recursive folder import mirroring directory structure."""
        import_cfg = self._get_import_config()
        default_config = TilesetConfig(
            tile_width=import_cfg.get("default_tile_width", 32),
            tile_height=import_cfg.get("default_tile_height", 32),
            margin_x=import_cfg.get("default_margin_x", 0),
            margin_y=import_cfg.get("default_margin_y", 0),
            spacing_x=import_cfg.get("default_spacing_x", 0),
            spacing_y=import_cfg.get("default_spacing_y", 0),
            start_x=import_cfg.get("default_start_x", 0),
            start_y=import_cfg.get("default_start_y", 0),
        )

        res = self.asset_manager.import_folder(
            folder_path,
            target_category_path=target_category,
            force_asset_type=AssetType.TILESET,
            default_tileset_config=default_config,
        )

        # Auto-expand all categories
        for p in self.asset_manager.category_tree.get_all_paths():
            if p not in self.expanded_folders:
                self.expanded_folders.append(p)

        if refresh:
            self.refresh_tilesets()

        if res["imported"]:
            self.set_active_asset(res["imported"][0])

        if refresh:
            self._auto_save_library()

        error_count = res.get("error_count", len(res.get("errors", [])))
        if show_message:
            QMessageBox.information(
                self,
                tr("dialog.library.import_folder_done_title"),
                tr(
                    "dialog.library.import_folder_done",
                    folder=os.path.basename(folder_path),
                    imported=res.get("imported_count", 0),
                    skipped=res.get("skipped_count", 0),
                    duplicates=res.get("duplicates_count", 0),
                    errors=error_count,
                ),
            )

    def _open_global_settings_dialog(self) -> None:
        dlg = GlobalImportSettingsDialog(self.config_manager, self)
        dlg.exec()

    def _render_thumb(self, asset: Optional[Asset], sub_tile: Optional[SelectedSubTile] = None) -> None:
        if not hasattr(self, "preview_thumb"):
            return
        thumb = QPixmap(32, 32)
        thumb.fill(QColor("#18181b"))
        p = QPainter(thumb)
        for y in range(0, 32, 4):
            for x in range(0, 32, 4):
                col = QColor("#222226") if ((x // 4 + y // 4) % 2 == 0) else QColor("#18181c")
                p.fillRect(x, y, 4, 4, col)

        if asset and sub_tile:
            full_pix = self.asset_manager.get_pixmap(asset.id)
            if full_pix and not full_pix.isNull():
                cropped = full_pix.copy(sub_tile.sub_x, sub_tile.sub_y, sub_tile.sub_w, sub_tile.sub_h)
                scaled = cropped.scaled(
                    26,
                    26,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                ox = (32 - scaled.width()) // 2
                oy = (32 - scaled.height()) // 2
                p.drawPixmap(ox, oy, scaled)
                p.setPen(QColor("#3b82f6"))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(ox - 1, oy - 1, scaled.width() + 1, scaled.height() + 1)
        p.end()
        self.preview_thumb.setPixmap(thumb)

    def _update_info_label(self, asset: Asset, sub_tile: Optional[SelectedSubTile] = None) -> None:
        cfg = asset.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
        grid = cfg.compute_grid(asset.width, asset.height)
        if sub_tile:
            if sub_tile.is_multi_tile():
                info = tr(
                    "palette.selected_tiles_info",
                    cols=sub_tile.cols_count,
                    rows=sub_tile.rows_count,
                    width=sub_tile.sub_w,
                    height=sub_tile.sub_h,
                    col=sub_tile.col,
                    row=sub_tile.row,
                )
            else:
                idx = sub_tile.row * grid["cols"] + sub_tile.col + 1
                info = tr(
                    "palette.selected_tile_info",
                    col=sub_tile.col,
                    row=sub_tile.row,
                    index=idx,
                    count=grid["total_cells"],
                    width=cfg.tile_width,
                    height=cfg.tile_height,
                )
        else:
            info = tr(
                "palette.grid_info",
                cols=grid["cols"],
                rows=grid["rows"],
                count=grid["total_cells"],
                width=cfg.tile_width,
                height=cfg.tile_height,
            )

        if grid["has_incomplete_edges"]:
            rem_info = []
            if grid["remainder_x"] > 0:
                rem_info.append(tr("palette.remainder_x", size=grid["remainder_x"]))
            if grid["remainder_y"] > 0:
                rem_info.append(tr("palette.remainder_y", size=grid["remainder_y"]))
            info += f" ({', '.join(rem_info)})"

        self.lbl_info.setText(info)
        self._render_thumb(asset, sub_tile)

    def _on_selection_changed(self, sub_tile: SelectedSubTile) -> None:
        if self.selected_autotile_id:
            self.selected_autotile_id = None
            for btn in self.autotile_buttons.values():
                btn.setChecked(False)
        if self.canvas.current_asset:
            self._update_info_label(self.canvas.current_asset, sub_tile)

    def _open_slicer_dialog(self) -> None:
        if not self.canvas.current_asset:
            return
        dlg = TilesetSlicerDialog(self.canvas.current_asset, self.asset_manager, self)
        if dlg.exec():
            self._update_info_label(self.canvas.current_asset)
            self.refresh_tilesets()
            self.canvas.update()
            self._auto_save_library()

    def _fit_to_view(self) -> None:
        self.canvas.fit_to_view()

    # --------------------------------------------------------------------------
    # RPG MAKER AUTOTILES PALETTE INTEGRATION
    # --------------------------------------------------------------------------
    def refresh_autotiles(self) -> None:
        """Repopulates the autotiles strip from AssetManager and AutoTileEngine."""
        while self.autotiles_layout.count() > 1:
            item = self.autotiles_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.autotile_buttons.clear()

        autotiles = {}
        if hasattr(self.asset_manager, "rpg_autotiles"):
            autotiles.update(self.asset_manager.rpg_autotiles)
        if hasattr(self, "autotile_engine") and self.autotile_engine:
            autotiles.update(getattr(self.autotile_engine, "rpg_autotiles", {}))

        for at_id, at in autotiles.items():
            if at.archived:
                continue
            btn = QToolButton(self.autotiles_content)
            btn.setCheckable(True)
            btn.setFixedSize(28, 28)
            preview = at.get_preview_pixmap(24)
            btn.setIcon(QIcon(preview))
            btn.setIconSize(QSize(24, 24))
            btn.setToolTip(f"Autotile: {at.name}\nTyp: {at.terrain_type}\nFormat: {at.format.value}")
            btn.setStyleSheet("""
                QToolButton {
                    background: #27272a;
                    border: 1px solid #3f3f46;
                    border-radius: 4px;
                }
                QToolButton:hover {
                    background: #3f3f46;
                    border-color: #60a5fa;
                }
                QToolButton:checked {
                    background: #1e3a8a;
                    border: 2px solid #3b82f6;
                }
            """)
            btn.clicked.connect(lambda checked, autotile=at: self._select_autotile(autotile))
            self.autotiles_layout.insertWidget(self.autotiles_layout.count() - 1, btn)
            self.autotile_buttons[at_id] = btn

        if self.selected_autotile_id in self.autotile_buttons:
            self.autotile_buttons[self.selected_autotile_id].setChecked(True)

    def _select_autotile(self, autotile: RPGAutotile) -> None:
        self.selected_autotile_id = autotile.id
        if self.asset_manager and hasattr(self.asset_manager, "register_rpg_autotile"):
            self.asset_manager.register_rpg_autotile(autotile)
        for at_id, btn in self.autotile_buttons.items():
            btn.setChecked(at_id == autotile.id)

        selected = SelectedAutotile(autotile)
        self.asset_manager.selected_item = selected
        self.asset_manager.asset_selected.emit(selected)

        # Update preview thumbnail and info label
        self.preview_thumb.setPixmap(autotile.get_preview_pixmap(24))
        self.lbl_info.setText(f"Autotile: {autotile.name} [{autotile.terrain_type}]")
        if hasattr(self.canvas, "deselect"):
            self.canvas.deselect()

    def _open_autotile_import_dialog(self) -> None:
        win = self.window()
        if hasattr(win, "open_path_generator_dialog") and win is not self:
            win.open_path_generator_dialog()
            return

        engine = getattr(self, "autotile_engine", None)
        if not engine:
            if hasattr(self.parent(), "autotile_engine"):
                engine = self.parent().autotile_engine
            else:
                from ..core.autotile_engine import AutoTileEngine
                engine = AutoTileEngine()
                self.autotile_engine = engine

        initial_asset_id = self.canvas.current_asset.id if self.canvas.current_asset else None
        from .dialogs.path_generator_dialog import PathGeneratorDialog
        dlg = PathGeneratorDialog(
            engine,
            self.asset_manager,
            self,
            initial_asset_id=initial_asset_id,
            initial_col=getattr(self.canvas, "sel_start_col", 0),
            initial_row=getattr(self.canvas, "sel_start_row", 0),
        )
        if dlg.exec():
            self.refresh_autotiles()
            active_at = engine.get_active_rpg_autotile()
            if active_at:
                self._select_autotile(active_at)
