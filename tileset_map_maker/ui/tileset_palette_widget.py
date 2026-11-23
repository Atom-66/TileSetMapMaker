import os
import logging
from typing import Optional, Tuple, List, Set
from PyQt6.QtCore import Qt, QRect, QRectF, QPointF, pyqtSignal, QSize, QSettings, QByteArray

logger = logging.getLogger("TilesetPalette")
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabBar,
    QLabel,
    QSlider,
    QToolButton,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QMenu,
    QScrollArea,
    QSplitter,
    QListWidget,
    QListWidgetItem,
    QFrame,
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
)

from ..models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from ..core.asset_manager import AssetManager
from .tileset_slicer_dialog import TilesetSlicerDialog
from .dialogs.tileset_import_dialog import TilesetImportDialog


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
            # Exclude spacing area
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

    def deselect(self) -> None:
        self.sel_start_col = 0
        self.sel_start_row = 0
        self.sel_end_col = 0
        self.sel_end_row = 0
        self._emit_selection()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#121316"))

        if not self.current_asset:
            painter.setPen(QColor("#71717a"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Brak wybranego tilesetu.\nDodaj lub wybierz arkusz tilesetu powyżej.",
            )
            return

        pixmap = self.asset_manager.get_pixmap(self.current_asset.id)
        if not pixmap or pixmap.isNull():
            painter.setPen(QColor("#ef4444"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                f"Błąd renderowania: Nie udało się wczytać tekstury.\nPlik: {self.current_asset.file_path}",
            )
            logger.error(f"[RENDER_ERROR] Null pixmap for tileset asset '{self.current_asset.name}' at {self.current_asset.file_path}")
            return

        cfg = self.current_asset.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
        grid = cfg.compute_grid(self.current_asset.width, self.current_asset.height)

        w = self.current_asset.width
        h = self.current_asset.height

        logger.debug(
            f"[RENDER_PASS] Tileset: '{self.current_asset.name}' | Dim: {w}x{h} px | "
            f"Grid: {grid['cols']}x{grid['rows']} cells ({cfg.tile_width}x{cfg.tile_height}px) | "
            f"Viewport: {self.width()}x{self.height()} | Zoom: {self.zoom:.2f} | Pan: ({self.pan_offset.x():.1f}, {self.pan_offset.y():.1f})"
        )

        painter.save()
        painter.translate(self.pan_offset)
        painter.scale(self.zoom, self.zoom)

        # 1. Transparency checkerboard behind the sheet
        c1 = QColor("#1c1c22")
        c2 = QColor("#26262e")
        painter.fillRect(QRectF(0, 0, w, h), c1)
        painter.setBrush(QBrush(c2))
        painter.setPen(Qt.PenStyle.NoPen)
        sq = 16
        for y in range(0, h, sq):
            offset = 0 if (y // sq) % 2 == 0 else sq
            for x in range(offset, w, sq * 2):
                bw = min(sq, w - x)
                bh = min(sq, h - y)
                if bw > 0 and bh > 0:
                    painter.drawRect(x, y, bw, bh)

        # 2. Draw original PNG image untouched
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPixmap(QRectF(0, 0, w, h), pixmap, QRectF(0, 0, w, h))

        # 3. Mark incomplete edge remainder fragments (dark overlay)
        if grid["has_incomplete_edges"]:
            rem_brush = QBrush(QColor(0, 0, 0, 140))
            if grid["remainder_x"] > 0:
                rx = w - grid["remainder_x"]
                painter.fillRect(QRectF(rx, 0, grid["remainder_x"], h), rem_brush)
            if grid["remainder_y"] > 0:
                ry = h - grid["remainder_y"]
                painter.fillRect(QRectF(0, ry, w, grid["remainder_y"]), rem_brush)

        # 4. Draw uniform regular grid lines (CRITICAL FIX: Brush must be NoBrush so cells are not filled with dark color!)
        if self.show_grid:
            grid_pen = QPen(QColor(255, 255, 255, 55))
            grid_pen.setWidthF(1.0 / self.zoom)
            painter.setPen(grid_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            for c in range(grid["cols"]):
                for r in range(grid["rows"]):
                    tx, ty, tw, th = cfg.get_tile_rect(c, r)
                    painter.drawRect(QRectF(tx, ty, tw, th))

        # 5. Hover cell highlight
        if self.hover_cell:
            hc, hr = self.hover_cell
            if 0 <= hc < grid["cols"] and 0 <= hr < grid["rows"]:
                hx, hy, hw, hh = cfg.get_tile_rect(hc, hr)
                hover_brush = QBrush(QColor(255, 255, 255, 35))
                painter.fillRect(QRectF(hx, hy, hw, hh), hover_brush)

        # 6. Selected cell or multi-tile block highlight (Tiled-style)
        c1 = min(self.sel_start_col, self.sel_end_col)
        c2 = max(self.sel_start_col, self.sel_end_col)
        r1 = min(self.sel_start_row, self.sel_end_row)
        r2 = max(self.sel_start_row, self.sel_end_row)

        if 0 <= c1 < grid["cols"] and 0 <= r1 < grid["rows"]:
            c2_clamped = min(c2, grid["cols"] - 1)
            r2_clamped = min(r2, grid["rows"] - 1)
            x1, y1, tw, th = cfg.get_tile_rect(c1, r1)
            x2, y2, _, _ = cfg.get_tile_rect(c2_clamped, r2_clamped)
            sel_w = (x2 + tw) - x1
            sel_h = (y2 + th) - y1
            sel_rect = QRectF(x1, y1, sel_w, sel_h)

            # Glowing selection fill
            painter.fillRect(sel_rect, QBrush(QColor(59, 130, 246, 75)))

            # Selection border
            sel_pen = QPen(QColor(96, 165, 250, 240))
            sel_pen.setWidthF(max(1.5, 2.0 / self.zoom))
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(sel_rect)

            # Badge showing block dimensions if multi-tile
            cols_count = c2_clamped - c1 + 1
            rows_count = r2_clamped - r1 + 1
            if cols_count > 1 or rows_count > 1:
                badge_text = f"{cols_count}x{rows_count}"
                badge_w = 32
                badge_h = 16
                badge_rect = QRectF(x1 + 2, y1 + 2, badge_w, badge_h)
                painter.fillRect(badge_rect, QColor(20, 20, 25, 220))
                painter.setPen(QColor("#60a5fa"))
                font = painter.font()
                font.setPixelSize(10)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # Outer border
        border_pen = QPen(QColor(63, 63, 70))
        border_pen.setWidthF(1.0 / self.zoom)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0, 0, w, h))

        painter.restore()

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
        if delta_x != 0:
            self.pan_offset.setX(self.pan_offset.x() + delta_x)
        self.update()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            self.space_pressed = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.key() == Qt.Key.Key_A and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.select_all()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.deselect()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            self.space_pressed = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        self.last_mouse_pos = pos

        # Pan with Middle Click or Space + Left Click
        if (
            event.button() == Qt.MouseButton.MiddleButton
            or (event.button() == Qt.MouseButton.LeftButton and self.space_pressed)
        ):
            self.is_panning = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        # Left Click: Select cell or multi-tile block
        if event.button() == Qt.MouseButton.LeftButton:
            world = self.screen_to_world(pos)
            cell = self.world_to_cell(world)
            if cell:
                col, row = cell
                # If Shift is held: extend selection to include this cell
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


class TilesetPaletteWidget(QWidget):
    """
    Two-section vertical layout for tileset management:
    - TOP SECTION: Tileset Canvas Preview & Tile Selector (occupies majority of height,
      uniform regular grid overlay, single & multi-tile rectangular selection, zoom & pan).
    - DRAGGABLE SPLITTER: Smooth vertical separator with state persistence and minimum heights.
    - BOTTOM SECTION: Tileset List (displays actually imported tilesets, thumbnails,
      names, cell stats, and buttons for adding, renaming, configuring grid and deleting).
    """
    tileset_tab_changed = pyqtSignal(str)  # asset_id

    def __init__(self, asset_manager: AssetManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.asset_manager = asset_manager
        self.active_asset_id: Optional[str] = None
        self.open_tileset_ids: List[str] = []

        self.setAcceptDrops(True)
        self._init_ui()
        self._connect_signals()
        self.restore_splitter_state()
        self.refresh_tilesets()

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

        # Header: Tabs & Quick Action buttons
        tab_header = QHBoxLayout()
        tab_header.setContentsMargins(0, 0, 0, 0)
        tab_header.setSpacing(2)

        self.tab_bar = QTabBar(self.top_widget)
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setUsesScrollButtons(True)
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setStyleSheet("""
            QTabBar::tab {
                background: #1c1c22;
                color: #a1a1aa;
                border: 1px solid #2e2e38;
                border-bottom: none;
                padding: 5px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 11px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: #272730;
                color: #60a5fa;
                border-color: #3b82f6;
                border-bottom: 2px solid #3b82f6;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected {
                background: #23232c;
                color: #e4e4e7;
            }
        """)
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        self.tab_bar.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(self._on_tab_context_menu)
        tab_header.addWidget(self.tab_bar, 1)

        # Quick config & fit & add buttons in preview header
        self.btn_config = QToolButton(self.top_widget)
        self.btn_config.setText("⚙️")
        self.btn_config.setToolTip("Konfiguruj parametry siatki tilesetu (Slicer)...")
        self.btn_config.setStyleSheet(self._button_style())
        self.btn_config.clicked.connect(self._open_slicer_dialog)
        tab_header.addWidget(self.btn_config)

        self.btn_fit = QToolButton(self.top_widget)
        self.btn_fit.setText("🎯")
        self.btn_fit.setToolTip("Dopasuj widok arkusza do okna podglądu")
        self.btn_fit.setStyleSheet(self._button_style())
        self.btn_fit.clicked.connect(self._fit_to_view)
        tab_header.addWidget(self.btn_fit)

        self.btn_add = QToolButton(self.top_widget)
        self.btn_add.setText("➕")
        self.btn_add.setToolTip("Zaimportuj nowy plik PNG/JPG jako tileset")
        self.btn_add.setStyleSheet(self._button_style())
        self.btn_add.clicked.connect(self._import_new_tileset_dialog)
        tab_header.addWidget(self.btn_add)

        top_layout.addLayout(tab_header)

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
        # 2. DOLNA SEKCJA – LISTA TILESETÓW
        # ==========================================
        self.bottom_widget = QWidget(self)
        self.bottom_widget.setMinimumHeight(100)
        bottom_layout = QVBoxLayout(self.bottom_widget)
        bottom_layout.setContentsMargins(4, 2, 4, 4)
        bottom_layout.setSpacing(4)

        # Header for the list section
        list_header = QHBoxLayout()
        list_header.setContentsMargins(2, 2, 2, 2)
        list_header.setSpacing(4)

        self.lbl_list_title = QLabel("🗂️ Zaimportowane tilesety (0)")
        self.lbl_list_title.setStyleSheet("color: #e4e4e7; font-size: 11px; font-weight: 600;")
        list_header.addWidget(self.lbl_list_title, 1)

        # Action buttons for tileset list management
        self.btn_list_add = QToolButton(self.bottom_widget)
        self.btn_list_add.setText("➕ Dodaj")
        self.btn_list_add.setToolTip("Zaimportuj nowy plik PNG/JPG jako tileset")
        self.btn_list_add.setStyleSheet(self._button_style())
        self.btn_list_add.clicked.connect(self._import_new_tileset_dialog)
        list_header.addWidget(self.btn_list_add)

        self.btn_list_rename = QToolButton(self.bottom_widget)
        self.btn_list_rename.setText("✏️ Nazwa")
        self.btn_list_rename.setToolTip("Zmień nazwę zaznaczonego tilesetu")
        self.btn_list_rename.setStyleSheet(self._button_style())
        self.btn_list_rename.clicked.connect(self._rename_selected_tileset)
        list_header.addWidget(self.btn_list_rename)

        self.btn_list_config = QToolButton(self.bottom_widget)
        self.btn_list_config.setText("⚙️ Siatka")
        self.btn_list_config.setToolTip("Konfiguruj siatkę zaznaczonego tilesetu")
        self.btn_list_config.setStyleSheet(self._button_style())
        self.btn_list_config.clicked.connect(self._open_slicer_dialog)
        list_header.addWidget(self.btn_list_config)

        self.btn_list_remove = QToolButton(self.bottom_widget)
        self.btn_list_remove.setText("🗑️ Usuń")
        self.btn_list_remove.setToolTip("Usuń zaznaczony tileset z biblioteki")
        self.btn_list_remove.setStyleSheet(self._button_style())
        self.btn_list_remove.clicked.connect(self._remove_selected_tileset)
        list_header.addWidget(self.btn_list_remove)

        bottom_layout.addLayout(list_header)

        # List Widget displaying all imported tilesets
        self.tileset_list = QListWidget(self.bottom_widget)
        self.tileset_list.setIconSize(QSize(28, 28))
        self.tileset_list.setStyleSheet("""
            QListWidget {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 4px;
                color: #e4e4e7;
                font-size: 11px;
                padding: 2px;
            }
            QListWidget::item {
                padding: 4px 6px;
                border-radius: 3px;
                margin: 1px 2px;
            }
            QListWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 600;
            }
            QListWidget::item:hover:!selected {
                background-color: #272730;
            }
        """)
        self.tileset_list.currentItemChanged.connect(self._on_list_item_changed)
        self.tileset_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tileset_list.customContextMenuRequested.connect(self._on_list_context_menu)
        self.tileset_list.itemDoubleClicked.connect(lambda item: self._open_slicer_dialog())
        bottom_layout.addWidget(self.tileset_list, 1)

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

    def save_splitter_state(self) -> None:
        """Persists the vertical splitter state to QSettings."""
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        settings.setValue("tileset_panel/splitter_state", self.splitter.saveState())

    def restore_splitter_state(self) -> None:
        """Restores the vertical splitter state from QSettings."""
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        state = settings.value("tileset_panel/splitter_state")
        if state:
            if isinstance(state, QByteArray) and not state.isEmpty():
                self.splitter.restoreState(state)
                return
            elif isinstance(state, (bytes, bytearray)) and len(state) > 0:
                self.splitter.restoreState(state)
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

    def refresh_tilesets(self) -> None:
        """Syncs tilesets with asset library and updates tabs and bottom list."""
        all_tilesets = [
            a for a in self.asset_manager.assets.values()
            if a.asset_type == AssetType.TILESET
        ]
        all_ids = {a.id for a in all_tilesets}

        # Keep open tabs that still exist, or add new tilesets (deduplicated)
        cleaned_open: List[str] = []
        for aid in self.open_tileset_ids:
            if aid in all_ids and aid not in cleaned_open:
                cleaned_open.append(aid)
        for aid in all_ids:
            if aid not in cleaned_open:
                cleaned_open.append(aid)
        self.open_tileset_ids = cleaned_open

        curr_id = self.active_asset_id

        # 1. Update Tab Bar
        self.tab_bar.blockSignals(True)
        while self.tab_bar.count() > 0:
            self.tab_bar.removeTab(0)

        active_idx = 0
        for i, aid in enumerate(self.open_tileset_ids):
            a = self.asset_manager.get_asset(aid)
            if a:
                idx = self.tab_bar.addTab(f"🗺️ {a.name}")
                self.tab_bar.setTabData(idx, a.id)
                if a.id == curr_id:
                    active_idx = idx

        # 2. Update Tileset List
        self.tileset_list.blockSignals(True)
        self.tileset_list.clear()

        active_list_row = -1
        for row, a in enumerate(all_tilesets):
            cfg = a.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
            grid = cfg.compute_grid(a.width, a.height)
            text = f"{a.name}  ({cfg.tile_width}×{cfg.tile_height} px | {grid['cols']}×{grid['rows']} kafelków)"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, a.id)

            # Thumbnail icon
            thumb = self.asset_manager.get_thumbnail(a.id, 28)
            if thumb and not thumb.isNull():
                item.setIcon(QIcon(thumb))

            self.tileset_list.addItem(item)
            if a.id == curr_id:
                active_list_row = row

        self.lbl_list_title.setText(f"🗂️ Zaimportowane tilesety ({len(all_tilesets)})")

        has_tilesets = len(all_tilesets) > 0
        self.btn_list_rename.setEnabled(has_tilesets)
        self.btn_list_remove.setEnabled(has_tilesets)
        self.btn_list_config.setEnabled(has_tilesets)
        self.btn_config.setEnabled(has_tilesets)
        self.btn_fit.setEnabled(has_tilesets)

        if self.tab_bar.count() > 0:
            self.tab_bar.setCurrentIndex(active_idx)
            chosen_id = self.tab_bar.tabData(active_idx)
            self.active_asset_id = chosen_id

            if active_list_row >= 0:
                self.tileset_list.setCurrentRow(active_list_row)
            elif self.tileset_list.count() > 0:
                self.tileset_list.setCurrentRow(0)

            asset = self.asset_manager.get_asset(chosen_id)
            if asset:
                if not asset.tileset_config:
                    asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
                self.canvas.set_asset(asset)
                self._update_info_label(asset)
        else:
            self.active_asset_id = None
            self.canvas.set_asset(None)
            self.lbl_info.setText("Brak dostępnych tilesetów. Kliknij [+] aby dodać.")

        self.tab_bar.blockSignals(False)
        self.tileset_list.blockSignals(False)

    def set_active_asset(self, asset: Optional[Asset], sub_tile: Optional[SelectedSubTile] = None) -> None:
        if not asset:
            return
        if asset.asset_type != AssetType.TILESET:
            self.asset_manager.set_asset_type(asset.id, AssetType.TILESET)

        if asset.id not in self.open_tileset_ids:
            self.open_tileset_ids.append(asset.id)
            self.refresh_tilesets()

        # Find tab
        for i in range(self.tab_bar.count()):
            if self.tab_bar.tabData(i) == asset.id:
                if self.tab_bar.currentIndex() != i:
                    self.tab_bar.blockSignals(True)
                    self.tab_bar.setCurrentIndex(i)
                    self.tab_bar.blockSignals(False)
                break

        # Find and select in tileset list
        for row in range(self.tileset_list.count()):
            item = self.tileset_list.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == asset.id:
                if self.tileset_list.currentRow() != row:
                    self.tileset_list.blockSignals(True)
                    self.tileset_list.setCurrentRow(row)
                    self.tileset_list.blockSignals(False)
                break

        self.active_asset_id = asset.id
        if not asset.tileset_config:
            asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

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

    def _on_tab_changed(self, index: int) -> None:
        if index < 0 or index >= self.tab_bar.count():
            return
        aid = self.tab_bar.tabData(index)
        asset = self.asset_manager.get_asset(aid)
        if asset:
            self.set_active_asset(asset)
            self.tileset_tab_changed.emit(asset.id)

    def _on_tab_close_requested(self, index: int) -> None:
        if index < 0 or index >= self.tab_bar.count():
            return
        aid = self.tab_bar.tabData(index)
        if aid in self.open_tileset_ids:
            self.open_tileset_ids.remove(aid)

        self.refresh_tilesets()

    def _on_list_item_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        if not current:
            return
        aid = current.data(Qt.ItemDataRole.UserRole)
        if not aid:
            return
        asset = self.asset_manager.get_asset(aid)
        if asset:
            self.set_active_asset(asset)
            self.tileset_tab_changed.emit(asset.id)

    def _on_list_context_menu(self, pos) -> None:
        item = self.tileset_list.itemAt(pos)
        menu = QMenu(self)
        if item:
            aid = item.data(Qt.ItemDataRole.UserRole)
            asset = self.asset_manager.get_asset(aid)
            if asset:
                self.set_active_asset(asset)
                act_rename = menu.addAction("✏️ Zmień nazwę tilesetu...")
                act_slicer = menu.addAction("⚙️ Konfiguruj siatkę (Slicer)...")
                menu.addSeparator()
                act_remove = menu.addAction("🗑️ Usuń tileset z biblioteki")
                menu.addSeparator()

        act_add = menu.addAction("➕ Zaimportuj nowy tileset...")

        action = menu.exec(self.tileset_list.mapToGlobal(pos))
        if item and action == act_rename:
            self._rename_selected_tileset()
        elif item and action == act_slicer:
            self._open_slicer_dialog()
        elif item and action == act_remove:
            self._remove_selected_tileset()
        elif action == act_add:
            self._import_new_tileset_dialog()

    def _on_tab_context_menu(self, pos) -> None:
        idx = self.tab_bar.tabAt(pos)
        if idx < 0:
            return
        aid = self.tab_bar.tabData(idx)
        asset = self.asset_manager.get_asset(aid)
        if not asset:
            return

        menu = QMenu(self)
        act_rename = menu.addAction("✏️ Zmień nazwę tilesetu...")
        act_slicer = menu.addAction("⚙️ Konfiguruj siatkę (Slicer)...")
        menu.addSeparator()
        act_close = menu.addAction("❌ Zamknij zakładkę")
        act_remove = menu.addAction("🗑️ Usuń tileset z biblioteki")

        action = menu.exec(self.tab_bar.mapToGlobal(pos))
        if action == act_rename:
            self._rename_selected_tileset()
        elif action == act_slicer:
            self._open_slicer_dialog()
        elif action == act_close:
            self._on_tab_close_requested(idx)
        elif action == act_remove:
            self._remove_selected_tileset()

    def _rename_selected_tileset(self) -> None:
        aid = self.active_asset_id
        if not aid:
            return
        asset = self.asset_manager.get_asset(aid)
        if not asset:
            return
        new_name, ok = QInputDialog.getText(self, "Nazwa tilesetu", "Nowa nazwa:", text=asset.name)
        if ok and new_name.strip():
            asset.name = new_name.strip()
            self.refresh_tilesets()

    def _remove_selected_tileset(self) -> None:
        aid = self.active_asset_id
        if not aid:
            return
        asset = self.asset_manager.get_asset(aid)
        if not asset:
            return
        confirm = QMessageBox.question(
            self,
            "Usuń tileset",
            f"Czy na pewno chcesz usunąć tileset '{asset.name}' z biblioteki?\n(Plik na dysku pozostanie nienaruszony)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.asset_manager.remove_asset(asset.id)
            if asset.id in self.open_tileset_ids:
                self.open_tileset_ids.remove(asset.id)
            self.refresh_tilesets()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        for u in urls:
            if u.isLocalFile():
                fpath = u.toLocalFile()
                if os.path.isfile(fpath):
                    self._import_new_tileset_dialog(file_path=fpath)
        event.acceptProposedAction()

    def _import_new_tileset_dialog(self, file_path: Optional[str] = None) -> None:
        if file_path:
            files = [file_path]
        else:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "Wybierz pliki arkuszy tilesetów (PNG/JPG)",
                "",
                "Grafiki (*.png *.jpg *.jpeg *.bmp *.webp);;Wszystkie pliki (*.*)",
            )
        if not files:
            return

        last_added_id = None
        for f in files:
            dlg = TilesetImportDialog(f, default_tile_size=32, parent=self)
            if dlg.exec():
                tile_w, tile_h = dlg.get_tile_dimensions()
                asset, is_dup, err = self.asset_manager.import_single_file(
                    f,
                    target_category_path="Terrain",
                    force_asset_type=AssetType.TILESET,
                )
                if asset:
                    asset.tileset_config = TilesetConfig(tile_width=tile_w, tile_height=tile_h)
                    last_added_id = asset.id
                    if asset.id not in self.open_tileset_ids:
                        self.open_tileset_ids.append(asset.id)

        if last_added_id:
            self.active_asset_id = last_added_id
            self.refresh_tilesets()

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
            self.canvas.update()

    def _fit_to_view(self) -> None:
        self.canvas.fit_to_view()
