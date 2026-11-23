from typing import Optional, Tuple
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QPushButton,
    QScrollArea,
    QWidget,
    QGroupBox,
    QFormLayout,
    QSlider,
)
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QMouseEvent,
    QWheelEvent,
    QPaintEvent,
)

from ..models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from ..core.asset_manager import AssetManager
from ..core.localization import get_localization, tr
from .widgets.switch_toggle import SwitchToggle
from .icons import IconFactory
from ..core.localization import tr


class SlicerPreviewCanvas(QWidget):
    """
    Interactive sheet preview showing the full PNG, regular grid lines,
    incomplete edge fragments, cell hover details, and zoom/pan navigation.
    """
    cell_clicked = pyqtSignal(int, int)  # col, row
    cell_hovered = pyqtSignal(int, int)  # col, row

    def __init__(self, asset: Asset, asset_manager: AssetManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.asset = asset
        self.asset_manager = asset_manager
        self.pixmap = asset_manager.get_pixmap(asset.id)

        self.zoom: float = 1.0
        self.pan_offset = QPointF(20.0, 20.0)
        self.is_panning = False
        self.last_mouse_pos = QPointF()

        self.show_grid = True
        self.hover_cell: Optional[Tuple[int, int]] = None
        self.selected_col = 0
        self.selected_row = 0

        self.setMouseTracking(True)

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(0.2, min(zoom, 16.0))
        self.update()

    def fit_to_view(self) -> None:
        if self.width() <= 0 or self.height() <= 0 or self.asset.width <= 0 or self.asset.height <= 0:
            return
        margin = 30
        scale_x = (self.width() - margin * 2) / self.asset.width
        scale_y = (self.height() - margin * 2) / self.asset.height
        self.zoom = max(0.2, min(min(scale_x, scale_y), 4.0))

        cx = (self.width() - self.asset.width * self.zoom) / 2
        cy = (self.height() - self.asset.height * self.zoom) / 2
        self.pan_offset = QPointF(cx, cy)
        self.update()

    def screen_to_world(self, screen_pos: QPointF) -> QPointF:
        return (screen_pos - self.pan_offset) / self.zoom

    def world_to_cell(self, world_pos: QPointF) -> Optional[Tuple[int, int]]:
        if not self.asset.tileset_config:
            return None
        cfg = self.asset.tileset_config
        grid = cfg.compute_grid(self.asset.width, self.asset.height)

        x = world_pos.x() - cfg.start_x - cfg.margin_x
        y = world_pos.y() - cfg.start_y - cfg.margin_y
        step_w = cfg.tile_width + cfg.spacing_x
        step_h = cfg.tile_height + cfg.spacing_y

        if x < 0 or y < 0:
            return None

        col = int(x // step_w)
        row = int(y // step_h)

        if 0 <= col < grid["cols"] and 0 <= row < grid["rows"]:
            return col, row
        return None

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#121316"))

        if not self.pixmap or self.pixmap.isNull():
            painter.setPen(QColor("#ef4444"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                tr("dialog.slicer.error", path=self.asset.file_path),
            )
            return

        w = self.asset.width
        h = self.asset.height
        cfg = self.asset.tileset_config or TilesetConfig()
        grid = cfg.compute_grid(w, h)

        painter.save()
        painter.translate(self.pan_offset)
        painter.scale(self.zoom, self.zoom)

        # 1. Checkerboard
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

        # 2. Draw original PNG untouched
        painter.drawPixmap(QRectF(0, 0, w, h), self.pixmap, QRectF(0, 0, w, h))

        # 3. Incomplete edge remainder fragments (shaded hatched pattern)
        if grid["has_incomplete_edges"]:
            rem_brush = QBrush(QColor(0, 0, 0, 150))
            if grid["remainder_x"] > 0:
                rx = w - grid["remainder_x"]
                painter.fillRect(QRectF(rx, 0, grid["remainder_x"], h), rem_brush)
            if grid["remainder_y"] > 0:
                ry = h - grid["remainder_y"]
                painter.fillRect(QRectF(0, ry, w, grid["remainder_y"]), rem_brush)

        # 4. Regular Grid Lines (CRITICAL FIX: setBrush to NoBrush so cells are not filled with dark color)
        if self.show_grid:
            grid_pen = QPen(QColor(80, 140, 255, 140))
            grid_pen.setWidthF(1.0 / self.zoom)
            painter.setPen(grid_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            for c in range(grid["cols"]):
                for r in range(grid["rows"]):
                    tx, ty, tw, th = cfg.get_tile_rect(c, r)
                    painter.drawRect(QRectF(tx, ty, tw, th))

        # 5. Hover highlight
        if self.hover_cell:
            hc, hr = self.hover_cell
            hx, hy, hw, hh = cfg.get_tile_rect(hc, hr)
            hover_brush = QBrush(QColor(255, 255, 255, 40))
            painter.fillRect(QRectF(hx, hy, hw, hh), hover_brush)

        # 6. Selected cell highlight
        if 0 <= self.selected_col < grid["cols"] and 0 <= self.selected_row < grid["rows"]:
            sx, sy, sw, sh = cfg.get_tile_rect(self.selected_col, self.selected_row)
            painter.fillRect(QRectF(sx, sy, sw, sh), QColor(255, 215, 0, 70))
            sel_pen = QPen(QColor(255, 215, 0, 240))
            sel_pen.setWidthF(max(1.5, 2.0 / self.zoom))
            painter.setPen(sel_pen)
            painter.drawRect(QRectF(sx, sy, sw, sh))

        # Outer border
        painter.setPen(QPen(QColor(63, 63, 70), 1.0 / self.zoom))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0, 0, w, h))

        painter.restore()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else (1.0 / 1.15)
        old_zoom = self.zoom
        new_zoom = max(0.2, min(self.zoom * factor, 16.0))
        if new_zoom == old_zoom:
            return

        mouse_pos = event.position()
        world_before = self.screen_to_world(mouse_pos)
        self.zoom = new_zoom
        world_after = self.screen_to_world(mouse_pos)
        self.pan_offset += (world_after - world_before) * self.zoom

        self.update()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        self.last_mouse_pos = pos

        if event.button() == Qt.MouseButton.MiddleButton:
            self.is_panning = True
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            world = self.screen_to_world(pos)
            cell = self.world_to_cell(world)
            if cell:
                self.selected_col, self.selected_row = cell
                self.cell_clicked.emit(cell[0], cell[1])
                self.update()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        world = self.screen_to_world(pos)

        if self.is_panning:
            diff = pos - self.last_mouse_pos
            self.pan_offset += diff
            self.last_mouse_pos = pos
            self.update()
            event.accept()
            return

        prev_hover = self.hover_cell
        self.hover_cell = self.world_to_cell(world)
        if self.hover_cell != prev_hover:
            if self.hover_cell:
                self.cell_hovered.emit(self.hover_cell[0], self.hover_cell[1])
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.is_panning = False
            event.accept()


class TilesetSlicerDialog(QDialog):
    """
    Comprehensive Tileset Configuration & Grid Slicer Dialog.
    Enforces uniform regular grid cells, provides live info, and real-time interactive preview.
    """

    def __init__(self, asset: Asset, asset_manager: AssetManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.asset = asset
        self.asset_manager = asset_manager
        self.setWindowTitle(tr("dialog.slicer.title", name=asset.name))
        self.resize(1000, 700)

        if not self.asset.tileset_config:
            self.asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
            self.asset.asset_type = AssetType.TILESET

        self.cfg = self.asset.tileset_config
        self._init_ui()
        self._hover_cell: Optional[Tuple[int, int]] = None
        get_localization().languageChanged.connect(self._apply_language)

    def _apply_language(self, _language: str) -> None:
        self.setWindowTitle(tr("dialog.slicer.title", name=self.asset.name))
        self._update_info()
        if self._hover_cell:
            self._on_cell_hovered(*self._hover_cell)
        else:
            self.lbl_cursor_info.setText(tr("dialog.slicer.hover_hint"))
        self.canvas.update()

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # Left panel: Settings controls
        ctrl_panel = QWidget()
        ctrl_panel.setFixedWidth(320)
        ctrl_layout = QVBoxLayout(ctrl_panel)

        # 1. Quick presets
        preset_group = QGroupBox(tr("dialog.slicer.presets"))
        preset_layout = QHBoxLayout(preset_group)
        for w, h in [(16, 16), (24, 24), (32, 32), (32, 48), (48, 48), (64, 64)]:
            btn = QPushButton(f"{w}x{h}")
            btn.setFixedWidth(44)
            btn.clicked.connect(lambda checked, tw=w, th=h: self._set_preset_size(tw, th))
            preset_layout.addWidget(btn)
        ctrl_layout.addWidget(preset_group)

        # 2. Cell Dimensions
        dim_group = QGroupBox(tr("dialog.slicer.cell_size"))
        dim_form = QFormLayout(dim_group)

        self.spin_w = QSpinBox()
        self.spin_w.setRange(4, 512)
        self.spin_w.setValue(self.cfg.tile_width)
        self.spin_w.valueChanged.connect(self._on_param_changed)
        dim_form.addRow(tr("dialog.slicer.tile_width"), self.spin_w)

        self.spin_h = QSpinBox()
        self.spin_h.setRange(4, 512)
        self.spin_h.setValue(self.cfg.tile_height)
        self.spin_h.valueChanged.connect(self._on_param_changed)
        dim_form.addRow(tr("dialog.slicer.tile_height"), self.spin_h)

        ctrl_layout.addWidget(dim_group)

        # 3. Margins & Spacings
        extra_group = QGroupBox(tr("dialog.slicer.grid_params"))
        extra_form = QFormLayout(extra_group)

        self.spin_margin_x = QSpinBox()
        self.spin_margin_x.setRange(0, 256)
        self.spin_margin_x.setValue(self.cfg.margin_x)
        self.spin_margin_x.valueChanged.connect(self._on_param_changed)
        extra_form.addRow(tr("dialog.slicer.margin_x"), self.spin_margin_x)

        self.spin_margin_y = QSpinBox()
        self.spin_margin_y.setRange(0, 256)
        self.spin_margin_y.setValue(self.cfg.margin_y)
        self.spin_margin_y.valueChanged.connect(self._on_param_changed)
        extra_form.addRow(tr("dialog.slicer.margin_y"), self.spin_margin_y)

        self.spin_spacing_x = QSpinBox()
        self.spin_spacing_x.setRange(0, 256)
        self.spin_spacing_x.setValue(self.cfg.spacing_x)
        self.spin_spacing_x.valueChanged.connect(self._on_param_changed)
        extra_form.addRow(tr("dialog.slicer.spacing_x"), self.spin_spacing_x)

        self.spin_spacing_y = QSpinBox()
        self.spin_spacing_y.setRange(0, 256)
        self.spin_spacing_y.setValue(self.cfg.spacing_y)
        self.spin_spacing_y.valueChanged.connect(self._on_param_changed)
        extra_form.addRow(tr("dialog.slicer.spacing_y"), self.spin_spacing_y)

        self.spin_start_x = QSpinBox()
        self.spin_start_x.setRange(0, 512)
        self.spin_start_x.setValue(self.cfg.start_x)
        self.spin_start_x.valueChanged.connect(self._on_param_changed)
        extra_form.addRow(tr("dialog.slicer.start_x"), self.spin_start_x)

        self.spin_start_y = QSpinBox()
        self.spin_start_y.setRange(0, 512)
        self.spin_start_y.setValue(self.cfg.start_y)
        self.spin_start_y.valueChanged.connect(self._on_param_changed)
        extra_form.addRow(tr("dialog.slicer.start_y"), self.spin_start_y)

        ctrl_layout.addWidget(extra_group)

        # 4. Info box
        info_group = QGroupBox(tr("dialog.slicer.file_info"))
        info_layout = QVBoxLayout(info_group)
        self.lbl_info = QLabel()
        self.lbl_info.setStyleSheet("color: #d4d4d8; font-size: 12px; line-height: 1.4;")
        info_layout.addWidget(self.lbl_info)
        ctrl_layout.addWidget(info_group)

        # Reset defaults button
        btn_reset = QPushButton(f" {tr('dialog.slicer.reset')}")
        btn_reset.setIcon(IconFactory.get_icon("refresh", 14))
        btn_reset.clicked.connect(self._reset_defaults)
        ctrl_layout.addWidget(btn_reset)

        ctrl_layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton(f" {tr('dialog.slicer.cancel')}")
        btn_cancel.setIcon(IconFactory.get_icon("close", 14))
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton(f" {tr('dialog.slicer.apply')}")
        btn_ok.setIcon(IconFactory.get_icon("check", 16))
        btn_ok.setProperty("class", "primary")
        btn_ok.clicked.connect(self._on_apply)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        ctrl_layout.addLayout(btn_layout)

        main_layout.addWidget(ctrl_panel)

        # Right panel: Interactive Canvas
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Top Canvas toolbar
        canv_tools = QHBoxLayout()
        self.chk_grid = SwitchToggle(tr("dialog.slicer.show_grid"), checked=True)
        self.chk_grid.toggled.connect(self._toggle_grid)
        canv_tools.addWidget(self.chk_grid)

        btn_fit = QPushButton(f" {tr('dialog.slicer.fit')}")
        btn_fit.setIcon(IconFactory.get_icon("fit", 16))
        btn_fit.clicked.connect(self._fit_canvas)
        canv_tools.addWidget(btn_fit)

        canv_tools.addStretch()
        self.lbl_cursor_info = QLabel(tr("dialog.slicer.hover_hint"))
        self.lbl_cursor_info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        canv_tools.addWidget(self.lbl_cursor_info)
        right_layout.addLayout(canv_tools)

        self.canvas = SlicerPreviewCanvas(self.asset, self.asset_manager)
        self.canvas.cell_clicked.connect(self._on_cell_clicked)
        self.canvas.cell_hovered.connect(self._on_cell_hovered)
        right_layout.addWidget(self.canvas, 1)

        main_layout.addWidget(right_container, 1)

        self._update_info()

    def _set_preset_size(self, w: int, h: int) -> None:
        self.spin_w.setValue(w)
        self.spin_h.setValue(h)

    def _on_param_changed(self) -> None:
        self.cfg.tile_width = self.spin_w.value()
        self.cfg.tile_height = self.spin_h.value()
        self.cfg.margin_x = self.spin_margin_x.value()
        self.cfg.margin_y = self.spin_margin_y.value()
        self.cfg.spacing_x = self.spin_spacing_x.value()
        self.cfg.spacing_y = self.spin_spacing_y.value()
        self.cfg.start_x = self.spin_start_x.value()
        self.cfg.start_y = self.spin_start_y.value()

        self._update_info()
        self.canvas.update()

    def _reset_defaults(self) -> None:
        self.spin_w.setValue(32)
        self.spin_h.setValue(32)
        self.spin_margin_x.setValue(0)
        self.spin_margin_y.setValue(0)
        self.spin_spacing_x.setValue(0)
        self.spin_spacing_y.setValue(0)
        self.spin_start_x.setValue(0)
        self.spin_start_y.setValue(0)

    def _update_info(self) -> None:
        grid = self.cfg.compute_grid(self.asset.width, self.asset.height)
        fi = self.asset.file_info or {}
        mode = fi.get("mode", "RGBA")
        fmt = fi.get("format", "PNG")
        alpha = (
            tr("dialog.slicer.alpha_yes")
            if fi.get("has_alpha", True)
            else tr("dialog.slicer.alpha_no")
        )

        info_text = (
            f"<b>{tr('dialog.slicer.resolution')}</b> {self.asset.width} × {self.asset.height} px<br>"
            f"<b>{tr('dialog.slicer.format')}</b> {fmt} ({mode}, {alpha})<br>"
            f"<b>{tr('dialog.slicer.grid')}</b> {grid['cols']} × {grid['rows']}<br>"
            f"<b>{tr('dialog.slicer.full_cells')}</b> <b>{grid['total_cells']}</b><br>"
        )

        if grid["has_incomplete_edges"]:
            rem_details = []
            if grid["remainder_x"] > 0:
                rem_details.append(
                    tr("dialog.slicer.remainder_right", size=grid["remainder_x"])
                )
            if grid["remainder_y"] > 0:
                rem_details.append(
                    tr("dialog.slicer.remainder_bottom", size=grid["remainder_y"])
                )
            info_text += (
                "<span style='color: #f59e0b;'>"
                + tr("dialog.slicer.remainder", details=", ".join(rem_details))
                + "</span>"
            )
        else:
            info_text += (
                "<span style='color: #22c55e;'>"
                + tr("dialog.slicer.perfect")
                + "</span>"
            )

        self.lbl_info.setText(info_text)

    def _on_cell_clicked(self, col: int, row: int) -> None:
        grid = self.cfg.compute_grid(self.asset.width, self.asset.height)
        idx = row * grid["cols"] + col + 1
        self.lbl_cursor_info.setText(
            tr(
                "dialog.slicer.selected",
                col=col,
                row=row,
                index=idx,
                total=grid["total_cells"],
            )
        )

    def _on_cell_hovered(self, col: int, row: int) -> None:
        self._hover_cell = (col, row)
        grid = self.cfg.compute_grid(self.asset.width, self.asset.height)
        idx = row * grid["cols"] + col + 1
        self.lbl_cursor_info.setText(
            tr("dialog.slicer.cursor", col=col, row=row, index=idx)
        )

    def _toggle_grid(self, checked: bool) -> None:
        self.canvas.show_grid = checked
        self.canvas.update()

    def _fit_canvas(self) -> None:
        self.canvas.fit_to_view()

    def _on_apply(self) -> None:
        self.asset.asset_type = AssetType.TILESET
        c = self.canvas.selected_col
        r = self.canvas.selected_row
        sx, sy, sw, sh = self.asset.get_tile_rect(c, r)

        sub_tile = SelectedSubTile(
            asset_id=self.asset.id,
            col=c,
            row=r,
            sub_x=sx,
            sub_y=sy,
            sub_w=sw,
            sub_h=sh,
            tile_width=self.cfg.tile_width,
            tile_height=self.cfg.tile_height,
            spacing_x=self.cfg.spacing_x,
            spacing_y=self.cfg.spacing_y,
        )
        self.asset_manager.select_asset(self.asset, sub_tile)
        self.accept()
