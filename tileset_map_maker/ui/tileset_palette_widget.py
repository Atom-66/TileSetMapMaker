import os
import logging
from typing import Optional, Tuple, List, Set, Dict, Any
from PyQt6.QtCore import Qt, QRect, QRectF, QPointF, pyqtSignal, QSize, QSettings, QByteArray
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
    QTreeWidget,
    QTreeWidgetItem,
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QSpinBox,
    QCheckBox,
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
)

from ..models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from ..models.category import CategoryTree, CategoryNode
from ..core.asset_manager import AssetManager
from ..core.config_manager import ConfigManager
from .tileset_slicer_dialog import TilesetSlicerDialog
from .dialogs.tileset_import_dialog import TilesetImportDialog

logger = logging.getLogger("TilesetPalette")


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
        self.sel_start_col = 0
        self.sel_start_row = 0
        self.sel_end_col = 0
        self.sel_end_row = 0

        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_asset(self, asset: Optional[Asset]) -> None:
        self.current_asset = asset
        self.sel_start_col = 0
        self.sel_start_row = 0
        self.sel_end_col = 0
        self.sel_end_row = 0
        if self.width() > 0 and self.height() > 0:
            self.fit_to_view()
        self._emit_selection()
        self.update()

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(0.25, min(zoom, 16.0))
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
            self.sel_start_col = 0
            self.sel_start_row = 0
            self.sel_end_col = grid["cols"] - 1
            self.sel_end_row = grid["rows"] - 1
            self._emit_selection()
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Background
        painter.fillRect(self.rect(), QColor("#121214"))

        if not self.current_asset:
            painter.setPen(QColor("#71717a"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Brak załadowanego tilesetu.\nWybierz tileset z biblioteki poniżej lub zaimportuj plik (+)",
            )
            return

        pixmap = self.asset_manager.get_pixmap(self.current_asset.id)
        if not pixmap or pixmap.isNull():
            painter.setPen(QColor("#ef4444"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                f"Nie można załadować pliku graficznego:\n{self.current_asset.file_path}",
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
        c1 = max(0, min(self.sel_start_col, self.sel_end_col))
        c2 = min(grid["cols"] - 1, max(self.sel_start_col, self.sel_end_col))
        r1 = max(0, min(self.sel_start_row, self.sel_end_row))
        r2 = min(grid["rows"] - 1, max(self.sel_start_row, self.sel_end_row))

        if grid["cols"] > 0 and grid["rows"] > 0:
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

            self.zoom_changed.emit(self.zoom)
            self.update()
            event.accept()
            return

        # 2. Shift + Wheel: Horizontal scroll/pan
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            step = (delta if delta != 0 else delta_x)
            self.pan_offset.setX(self.pan_offset.x() + step)
            self.update()
            event.accept()
            return

        # 3. Standard Wheel: Vertical scroll/pan
        if delta != 0:
            self.pan_offset.setY(self.pan_offset.y() + delta)
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
            self.update()
            event.accept()
            return

        # Selection Drag (Multi-tile rectangular block selection)
        if self.is_selecting and (event.buttons() & Qt.MouseButton.LeftButton):
            cell = self.world_to_cell(world)
            if cell:
                self.sel_end_col, self.sel_end_row = cell
                self._emit_selection()
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
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self._emit_selection()
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
        self.setAnimated(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
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

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        pos = event.position().toPoint()
        target_item = self.itemAt(pos)
        target_category = self.palette._get_category_path_for_item(target_item)

        # External file/folder drop from OS file manager
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for u in urls:
                if u.isLocalFile():
                    fpath = u.toLocalFile()
                    if os.path.isdir(fpath):
                        self.palette.import_folder_from_path(fpath, target_category=target_category)
                    elif os.path.isfile(fpath):
                        self.palette.import_file_from_path(fpath, target_category=target_category)
            event.acceptProposedAction()
            return

        # Internal drag & drop
        source_item = self.currentItem()
        if source_item and source_item != target_item:
            item_type = source_item.data(0, Qt.ItemDataRole.UserRole)
            item_val = source_item.data(0, Qt.ItemDataRole.UserRole + 1)
            if item_type == "tileset":
                self.palette.asset_manager.move_asset(item_val, target_category)
                self.palette.refresh_tilesets()
                self.palette._auto_save_library()
                event.accept()
                return
            elif item_type == "folder":
                # Ensure destination is not source or its descendant
                if target_category != item_val and not target_category.startswith(item_val + "/"):
                    self.palette.asset_manager.move_category(item_val, target_category)
                    self.palette.refresh_tilesets()
                    self.palette._auto_save_library()
                    event.accept()
                    return

        super().dropEvent(event)


class GlobalImportSettingsDialog(QDialog):
    """Dialog for editing global tileset import default parameters."""
    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Domyślne ustawienia importu tilesetów")
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
        form.addRow("Domyślna szerokość kafelka (px):", self.spin_width)

        self.spin_height = QSpinBox()
        self.spin_height.setRange(4, 512)
        self.spin_height.setValue(cfg.get("default_tile_height", 32))
        form.addRow("Domyślna wysokość kafelka (px):", self.spin_height)

        # Quick preset buttons
        preset_box = QHBoxLayout()
        for w, h in [(16, 16), (24, 24), (32, 32), (32, 48), (48, 48), (64, 64)]:
            btn = QPushButton(f"{w}x{h}")
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda _, pw=w, ph=h: self._set_dims(pw, ph))
            preset_box.addWidget(btn)
        form.addRow("Szybkie szablony:", preset_box)

        self.spin_margin_x = QSpinBox()
        self.spin_margin_x.setRange(0, 128)
        self.spin_margin_x.setValue(cfg.get("default_margin_x", 0))
        form.addRow("Margines lewy (X, px):", self.spin_margin_x)

        self.spin_margin_y = QSpinBox()
        self.spin_margin_y.setRange(0, 128)
        self.spin_margin_y.setValue(cfg.get("default_margin_y", 0))
        form.addRow("Margines górny (Y, px):", self.spin_margin_y)

        self.spin_spacing_x = QSpinBox()
        self.spin_spacing_x.setRange(0, 64)
        self.spin_spacing_x.setValue(cfg.get("default_spacing_x", 0))
        form.addRow("Odstęp poziomy (Spacing X, px):", self.spin_spacing_x)

        self.spin_spacing_y = QSpinBox()
        self.spin_spacing_y.setRange(0, 64)
        self.spin_spacing_y.setValue(cfg.get("default_spacing_y", 0))
        form.addRow("Odstęp pionowy (Spacing Y, px):", self.spin_spacing_y)

        self.chk_skip_single = QCheckBox("Używaj automatycznie dla pojedynczych plików (bez okna konfiguracji)")
        self.chk_skip_single.setChecked(cfg.get("skip_dialog_on_single", False))
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
    ):
        super().__init__(parent)
        self.asset_manager = asset_manager
        self.config_manager = config_manager or ConfigManager()
        self.active_asset_id: Optional[str] = None
        self.open_tileset_ids: List[str] = []  # For backward compatibility
        self.expanded_folders: List[str] = []

        self.setAcceptDrops(True)
        self._init_ui()
        self._connect_signals()
        self.restore_splitter_state()
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
        self.top_widget = QWidget(self)
        self.top_widget.setMinimumHeight(140)
        top_layout = QVBoxLayout(self.top_widget)
        top_layout.setContentsMargins(4, 4, 4, 2)
        top_layout.setSpacing(4)

        # Header: Active tileset title & Quick Action buttons (NO TABS!)
        top_header = QHBoxLayout()
        top_header.setContentsMargins(2, 2, 2, 2)
        top_header.setSpacing(4)

        self.lbl_active_title = QLabel("🖼️ Podgląd tilesetu: (Brak wyboru)")
        self.lbl_active_title.setStyleSheet("color: #93c5fd; font-size: 11px; font-weight: bold;")
        top_header.addWidget(self.lbl_active_title, 1)

        self.btn_config = QToolButton(self.top_widget)
        self.btn_config.setText("⚙️")
        self.btn_config.setToolTip("Konfiguruj parametry siatki tilesetu (Slicer)...")
        self.btn_config.setStyleSheet(self._button_style())
        self.btn_config.clicked.connect(self._open_slicer_dialog)
        top_header.addWidget(self.btn_config)

        self.btn_fit = QToolButton(self.top_widget)
        self.btn_fit.setText("🎯")
        self.btn_fit.setToolTip("Dopasuj widok arkusza do okna podglądu")
        self.btn_fit.setStyleSheet(self._button_style())
        self.btn_fit.clicked.connect(self._fit_to_view)
        top_header.addWidget(self.btn_fit)

        top_layout.addLayout(top_header)

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
        self.preview_thumb.setFixedSize(32, 32)
        self.preview_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_thumb.setStyleSheet("""
            QLabel {
                background: #18181b;
                border: 1px solid #3f3f46;
                border-radius: 4px;
            }
        """)
        self.preview_thumb.setToolTip("Podgląd wybranego fragmentu tilesetu (pojedynczy kafelek lub blok)")
        info_layout.addWidget(self.preview_thumb)

        self.lbl_info = QLabel("Brak wyboru")
        self.lbl_info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        info_layout.addWidget(self.lbl_info, 1)

        # Zoom Controls
        self.btn_zoom_out = QToolButton(self.top_widget)
        self.btn_zoom_out.setText("➖")
        self.btn_zoom_out.setToolTip("Pomniejsz widok tilesetu")
        self.btn_zoom_out.setStyleSheet(self._button_style())
        self.btn_zoom_out.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom / 1.25))
        info_layout.addWidget(self.btn_zoom_out)

        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(25, 400)
        self.slider_zoom.setValue(150)
        self.slider_zoom.setFixedWidth(70)
        self.slider_zoom.valueChanged.connect(lambda v: self.canvas.set_zoom(v / 100.0))
        info_layout.addWidget(self.slider_zoom)

        self.btn_zoom_in = QToolButton(self.top_widget)
        self.btn_zoom_in.setText("➕")
        self.btn_zoom_in.setToolTip("Powiększ widok tilesetu")
        self.btn_zoom_in.setStyleSheet(self._button_style())
        self.btn_zoom_in.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom * 1.25))
        info_layout.addWidget(self.btn_zoom_in)

        self.btn_zoom_100 = QToolButton(self.top_widget)
        self.btn_zoom_100.setText("1:1")
        self.btn_zoom_100.setToolTip("Resetuj powiększenie do 100% (1:1)")
        self.btn_zoom_100.setStyleSheet(self._button_style())
        self.btn_zoom_100.clicked.connect(lambda: self.canvas.set_zoom(1.0))
        info_layout.addWidget(self.btn_zoom_100)

        self.canvas.zoom_changed.connect(self._on_canvas_zoom_changed)
        top_layout.addLayout(info_layout)
        self.splitter.addWidget(self.top_widget)

        # ==========================================
        # 2. DOLNA SEKCJA – BIBLIOTEKA ZAIMPORTOWANYCH TILESETÓW (DRZEWO)
        # ==========================================
        self.bottom_widget = QWidget(self)
        self.bottom_widget.setMinimumHeight(120)
        bottom_layout = QVBoxLayout(self.bottom_widget)
        bottom_layout.setContentsMargins(4, 2, 4, 4)
        bottom_layout.setSpacing(4)

        # Header for the library section
        lib_header = QHBoxLayout()
        lib_header.setContentsMargins(2, 2, 2, 2)
        lib_header.setSpacing(3)

        self.lbl_list_title = QLabel("🗂️ Biblioteka tilesetów (0)")
        self.lbl_list_title.setStyleSheet("color: #e4e4e7; font-size: 11px; font-weight: 600;")
        lib_header.addWidget(self.lbl_list_title, 1)

        # Action buttons for library management
        self.btn_add_files = QToolButton(self.bottom_widget)
        self.btn_add_files.setText("➕ Plik(i)")
        self.btn_add_files.setToolTip("Zaimportuj jeden lub więcej plików PNG/JPG jako tilesety")
        self.btn_add_files.setStyleSheet(self._button_style())
        self.btn_add_files.clicked.connect(lambda: self._import_files_action())
        lib_header.addWidget(self.btn_add_files)

        self.btn_import_folder = QToolButton(self.bottom_widget)
        self.btn_import_folder.setText("📁 Folder")
        self.btn_import_folder.setToolTip("Zaimportuj cały folder z dysku rekursywnie")
        self.btn_import_folder.setStyleSheet(self._button_style())
        self.btn_import_folder.clicked.connect(lambda: self._import_folder_action())
        lib_header.addWidget(self.btn_import_folder)

        self.btn_new_folder = QToolButton(self.bottom_widget)
        self.btn_new_folder.setText("📂 Nowy folder")
        self.btn_new_folder.setToolTip("Utwórz nowy folder w bibliotece tilesetów")
        self.btn_new_folder.setStyleSheet(self._button_style())
        self.btn_new_folder.clicked.connect(lambda: self._create_folder_action())
        lib_header.addWidget(self.btn_new_folder)

        self.btn_rename = QToolButton(self.bottom_widget)
        self.btn_rename.setText("✏️")
        self.btn_rename.setToolTip("Zmień nazwę zaznaczonego folderu lub tilesetu")
        self.btn_rename.setStyleSheet(self._button_style())
        self.btn_rename.clicked.connect(self._rename_action)
        lib_header.addWidget(self.btn_rename)

        self.btn_delete = QToolButton(self.bottom_widget)
        self.btn_delete.setText("🗑️")
        self.btn_delete.setToolTip("Usuń zaznaczony folder lub tileset z biblioteki")
        self.btn_delete.setStyleSheet(self._button_style())
        self.btn_delete.clicked.connect(self._delete_action)
        lib_header.addWidget(self.btn_delete)

        self.btn_settings = QToolButton(self.bottom_widget)
        self.btn_settings.setText("⚙️")
        self.btn_settings.setToolTip("Ustawienia domyślne importu tilesetów...")
        self.btn_settings.setStyleSheet(self._button_style())
        self.btn_settings.clicked.connect(self._open_global_settings_dialog)
        lib_header.addWidget(self.btn_settings)

        bottom_layout.addLayout(lib_header)

        # Hierarchical Tree Widget displaying folders, subfolders and tilesets
        self.tree = TilesetTreeWidget(self, self.bottom_widget)
        self.tileset_list = self.tree
        self.tree.currentItemChanged.connect(self._on_tree_item_changed)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_tree_double_clicked)
        bottom_layout.addWidget(self.tree, 1)

        self.splitter.addWidget(self.bottom_widget)

        # Splitter proportion defaults (top gets ~70%, bottom gets ~30%)
        self.splitter.setStretchFactor(0, 7)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.splitterMoved.connect(lambda pos, index: self.save_splitter_state())

        main_layout.addWidget(self.splitter)

    @staticmethod
    def _button_style() -> str:
        return """
            QToolButton {
                background: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: 500;
            }
            QToolButton:hover {
                background: #3b82f6;
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

    def _auto_save_library(self) -> None:
        if self.config_manager:
            self.config_manager.save_tileset_library(
                asset_manager=self.asset_manager,
                active_asset_id=self.active_asset_id,
                expanded_folders=self.expanded_folders,
            )

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
        all_tilesets = [
            a for a in self.asset_manager.assets.values()
            if a.asset_type == AssetType.TILESET
        ]
        self.lbl_list_title.setText(f"🗂️ Biblioteka tilesetów ({len(all_tilesets)})")

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
                folder_item.setText(0, f"📁 {child_node.name} ({sub_count})")
                folder_item.setToolTip(0, f"Folder: {child_node.path} ({sub_count} tilesetów)")

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
            self._select_tree_item_for_asset(active_asset.id)
            self.canvas.set_asset(active_asset)
            self._update_info_label(active_asset)
            cfg = active_asset.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
            self.lbl_active_title.setText(f"🗺️ Arkusz: {active_asset.name} ({cfg.tile_width}×{cfg.tile_height} px)")
        else:
            self.active_asset_id = None
            self.canvas.set_asset(None)
            self.lbl_active_title.setText("Podgląd tilesetu: (Brak wyboru)")
            self.lbl_info.setText("Brak dostępnych tilesetów. Kliknij [+ Plik(i)] aby zaimportować.")

        self.tree.blockSignals(False)

    def _create_tileset_tree_item(self, asset: Asset) -> TilesetTreeItem:
        cfg = asset.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
        grid = cfg.compute_grid(asset.width, asset.height)
        item = TilesetTreeItem()
        item.setData(0, Qt.ItemDataRole.UserRole, "tileset")
        item.setData(0, Qt.ItemDataRole.UserRole + 1, asset.id)
        item.setText(0, f"🗺️ {asset.name}  ({cfg.tile_width}×{cfg.tile_height} px | {grid['cols']}×{grid['rows']})")
        item.setToolTip(0, f"Tileset: {asset.name}\nPlik: {asset.file_path}\nRozmiar: {asset.width}x{asset.height} px\nKafelki: {grid['cols']}x{grid['rows']} ({grid['total_cells']})")

        thumb = self.asset_manager.get_thumbnail(asset.id, 24)
        if thumb and not thumb.isNull():
            item.setIcon(0, QIcon(thumb))
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
            self.lbl_active_title.setText("Podgląd tilesetu: (Brak wyboru)")
            self.lbl_info.setText("Brak dostępnych tilesetów.")
            return

        if asset.asset_type != AssetType.TILESET:
            self.asset_manager.set_asset_type(asset.id, AssetType.TILESET)

        self.active_asset_id = asset.id
        if not asset.tileset_config:
            asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

        cfg = asset.tileset_config
        self.lbl_active_title.setText(f"🗺️ Arkusz: {asset.name} ({cfg.tile_width}×{cfg.tile_height} px)")
        self.canvas.current_asset = asset

        if self.canvas.width() > 0 and self.canvas.height() > 0:
            self.canvas.fit_to_view()

        if sub_tile:
            self.canvas.sel_start_col = sub_tile.col
            self.canvas.sel_start_row = sub_tile.row
            self.canvas.sel_end_col = sub_tile.col + sub_tile.cols_count - 1
            self.canvas.sel_end_row = sub_tile.row + sub_tile.rows_count - 1
        else:
            self.canvas.sel_start_col = 0
            self.canvas.sel_start_row = 0
            self.canvas.sel_end_col = 0
            self.canvas.sel_end_row = 0

        self._update_info_label(asset, sub_tile)
        self.canvas.update()
        self._select_tree_item_for_asset(asset.id)
        self._auto_save_library()

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
                self.lbl_active_title.setText(f"📁 Folder: {fpath}")

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
            itype = item.data(0, Qt.ItemDataRole.UserRole)
            val = item.data(0, Qt.ItemDataRole.UserRole + 1)

            if itype == "tileset":
                asset = self.asset_manager.get_asset(val)
                if asset:
                    self.set_active_asset(asset)
                    act_open = menu.addAction("👁️ Pokaż w podglądzie")
                    act_slicer = menu.addAction("⚙️ Konfiguruj siatkę (Slicer)...")
                    act_rename = menu.addAction("✏️ Zmień nazwę tilesetu...")
                    act_move = menu.addAction("📁 Przenieś do innego folderu...")
                    menu.addSeparator()
                    act_del = menu.addAction("🗑️ Usuń tileset z biblioteki")

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
                act_add_files = menu.addAction("➕ Dodaj plik(i) tilesetu do tego folderu...")
                act_import_sub = menu.addAction("📁 Zaimportuj folder z dysku tutaj...")
                act_new_sub = menu.addAction("📂 Utwórz nowy podfolder...")
                menu.addSeparator()
                act_rename_f = menu.addAction("✏️ Zmień nazwę folderu...")
                act_del_f = menu.addAction("🗑️ Usuń folder...")

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
        act_add = menu.addAction("➕ Zaimportuj plik(i) tilesetu...")
        act_imp_folder = menu.addAction("📁 Zaimportuj cały folder z dysku...")
        act_folder = menu.addAction("📂 Utwórz nowy folder w bibliotece...")
        menu.addSeparator()
        act_global = menu.addAction("⚙️ Ustawienia domyślne importu...")

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
        if parent_path is None:
            curr = self.tree.currentItem()
            parent_path = self._get_category_path_for_item(curr)

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
                "Zmień nazwę folderu",
                "Nowa nazwa folderu:",
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
                "Zmień nazwę tilesetu",
                "Nowa nazwa tilesetu:",
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
                "Usuń tileset z biblioteki",
                f"Czy na pewno chcesz usunąć tileset '{asset.name}' z biblioteki?\n\n"
                f"(Plik na dysku '{asset.file_path}' pozostanie całkowicie nienaruszony)",
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
                msg_box.setWindowTitle("Usuwanie folderu")
                msg_box.setText(
                    f"Folder '{node.name}' zawiera {len(all_asset_ids)} tileset(ów).\n"
                    "Co chcesz zrobić z zawartością?\n\n"
                    "(Żadne pliki na dysku nie zostaną skasowane)"
                )
                btn_reparent = msg_box.addButton("Przenieś tilesety wyżej", QMessageBox.ButtonRole.ActionRole)
                btn_delete_all = msg_box.addButton("Usuń tilesety z biblioteki", QMessageBox.ButtonRole.DestructiveRole)
                btn_cancel = msg_box.addButton("Anuluj", QMessageBox.ButtonRole.RejectRole)
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
                    "Usuń pusty folder",
                    f"Czy na pewno chcesz usunąć pusty folder '{node.name}'?",
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
        paths = ["(Katalog główny)"] + self.asset_manager.category_tree.get_all_paths()
        curr_idx = 0
        if asset.category_path in paths:
            curr_idx = paths.index(asset.category_path)

        chosen, ok = QInputDialog.getItem(
            self,
            "Przenieś tileset",
            f"Wybierz docelowy folder dla tilesetu '{asset.name}':",
            paths,
            current=curr_idx,
            editable=False,
        )
        if ok and chosen:
            target = "" if chosen == "(Katalog główny)" else chosen
            self.asset_manager.move_asset(asset.id, target)
            self.refresh_tilesets()
            self._auto_save_library()

    def _import_files_action(self, target_category: Optional[str] = None) -> None:
        if target_category is None:
            curr = self.tree.currentItem()
            target_category = self._get_category_path_for_item(curr)

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Wybierz pliki arkuszy tilesetów (PNG/JPG)",
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
                "Import zakończony",
                f"Zaimportowano pomyślnie: {imported_count} tileset(ów)\n"
                f"Pominięte duplikaty: {dup_count}",
            )

    def import_file_from_path(self, file_path: str, target_category: str = "") -> None:
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
            self.refresh_tilesets()
            self.set_active_asset(asset)
            self._auto_save_library()

    def _import_folder_action(self, target_category: Optional[str] = None) -> None:
        if target_category is None:
            curr = self.tree.currentItem()
            target_category = self._get_category_path_for_item(curr)

        folder = QFileDialog.getExistingDirectory(
            self,
            "Wybierz folder z tilesetami do zaimportowania",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return

        self.import_folder_from_path(folder, target_category=target_category)

    def import_folder_from_path(self, folder_path: str, target_category: str = "") -> None:
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

        self.refresh_tilesets()

        if res["imported"]:
            self.set_active_asset(res["imported"][0])

        self._auto_save_library()

        error_count = res.get("error_count", len(res.get("errors", [])))
        QMessageBox.information(
            self,
            "Import folderu zakończony",
            f"Wynik importu folderu '{os.path.basename(folder_path)}':\n\n"
            f"✅ Zaimportowano: {res.get('imported_count', 0)} tileset(ów)\n"
            f"⏭️ Pominięto (pliki inne niż grafika): {res.get('skipped_count', 0)}\n"
            f"⚠️ Duplikaty: {res.get('duplicates_count', 0)}\n"
            f"❌ Błędy: {error_count}",
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
                info = f"Zaznaczenie: {sub_tile.cols_count}x{sub_tile.rows_count} kafelków ({sub_tile.sub_w}x{sub_tile.sub_h}px) od kol. {sub_tile.col}, wiersz {sub_tile.row}"
            else:
                idx = sub_tile.row * grid["cols"] + sub_tile.col + 1
                info = f"Kafelek: Kol {sub_tile.col}, Wiersz {sub_tile.row} (#{idx}/{grid['total_cells']}) [{cfg.tile_width}x{cfg.tile_height}px]"
        else:
            info = f"Siatka: {grid['cols']}x{grid['rows']} ({grid['total_cells']} kafelków) [{cfg.tile_width}x{cfg.tile_height}px]"

        if grid["has_incomplete_edges"]:
            rem_info = []
            if grid["remainder_x"] > 0:
                rem_info.append(f"+{grid['remainder_x']}px margines P")
            if grid["remainder_y"] > 0:
                rem_info.append(f"+{grid['remainder_y']}px margines D")
            info += f" ({', '.join(rem_info)})"

        self.lbl_info.setText(info)
        self._render_thumb(asset, sub_tile)

    def _on_selection_changed(self, sub_tile: SelectedSubTile) -> None:
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
