from typing import Optional, Tuple
from PyQt6.QtCore import Qt, QRect, QRectF, QPointF, pyqtSignal
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
)
from PyQt6.QtGui import QPainter, QColor, QPen, QPixmap, QMouseEvent

from ..models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from ..core.asset_manager import AssetManager


class TilesetPreviewWidget(QWidget):
    """Interactive preview canvas for slicing and selecting tiles in a tileset."""
    tile_picked = pyqtSignal(int, int)  # col, row

    def __init__(self, asset: Asset, asset_manager: AssetManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.asset = asset
        self.asset_manager = asset_manager
        self.pixmap = asset_manager.get_pixmap(asset.id)
        self.scale_factor = 2.0  # 200% zoom for easy viewing
        self.selected_col = 0
        self.selected_row = 0

        w = int(asset.width * self.scale_factor) if asset.width > 0 else 200
        h = int(asset.height * self.scale_factor) if asset.height > 0 else 200
        self.setFixedSize(w, h)

    def set_scale(self, scale: float) -> None:
        self.scale_factor = scale
        w = int(self.asset.width * self.scale_factor)
        h = int(self.asset.height * self.scale_factor)
        self.setFixedSize(w, h)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.asset.tileset_config:
            return
        cfg = self.asset.tileset_config
        px_x = event.position().x() / self.scale_factor - cfg.margin
        px_y = event.position().y() / self.scale_factor - cfg.margin

        step_w = cfg.tile_width + cfg.spacing
        step_h = cfg.tile_height + cfg.spacing
        if step_w > 0 and step_h > 0:
            col = int(px_x // step_w)
            row = int(px_y // step_h)
            cols, rows = self.asset.get_tileset_dimensions()
            if 0 <= col < cols and 0 <= row < rows:
                self.selected_col = col
                self.selected_row = row
                self.tile_picked.emit(col, row)
                self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#16171b"))

        if not self.pixmap or self.pixmap.isNull():
            return

        # Draw scaled tileset image
        target_rect = QRectF(0, 0, self.asset.width * self.scale_factor, self.asset.height * self.scale_factor)
        source_rect = QRectF(0, 0, self.asset.width, self.asset.height)
        painter.drawPixmap(target_rect, self.pixmap, source_rect)

        # Draw slice grid
        if self.asset.tileset_config:
            cfg = self.asset.tileset_config
            cols, rows = self.asset.get_tileset_dimensions()

            pen = QPen(QColor(80, 140, 255, 160))
            pen.setWidth(1)
            painter.setPen(pen)

            for c in range(cols):
                for r in range(rows):
                    sx, sy, sw, sh = self.asset.get_tile_rect(c, r)
                    rx = int(sx * self.scale_factor)
                    ry = int(sy * self.scale_factor)
                    rw = int(sw * self.scale_factor)
                    rh = int(sh * self.scale_factor)
                    painter.drawRect(rx, ry, rw, rh)

            # Highlight selected tile
            sx, sy, sw, sh = self.asset.get_tile_rect(self.selected_col, self.selected_row)
            rx = int(sx * self.scale_factor)
            ry = int(sy * self.scale_factor)
            rw = int(sw * self.scale_factor)
            rh = int(sh * self.scale_factor)

            sel_fill = QColor(255, 215, 0, 70)
            painter.fillRect(rx, ry, rw, rh, sel_fill)

            sel_pen = QPen(QColor(255, 215, 0, 240))
            sel_pen.setWidth(2)
            painter.setPen(sel_pen)
            painter.drawRect(rx, ry, rw, rh)


class TilesetSlicerDialog(QDialog):
    """Configuration dialog for tileset slicing, margin, spacing, and tile picking."""

    def __init__(self, asset: Asset, asset_manager: AssetManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.asset = asset
        self.asset_manager = asset_manager
        self.setWindowTitle(f"Konfigurator Tilesetu – {asset.name}")
        self.resize(800, 600)

        if not self.asset.tileset_config:
            self.asset.tileset_config = asset_manager.auto_detect_tileset_config(asset)
            self.asset.asset_type = AssetType.TILESET

        self.cfg = self.asset.tileset_config
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # Left panel: Settings controls
        ctrl_panel = QWidget()
        ctrl_panel.setFixedWidth(260)
        ctrl_layout = QVBoxLayout(ctrl_panel)

        group = QGroupBox("Parametry kafelków")
        form = QFormLayout(group)

        self.spin_w = QSpinBox()
        self.spin_w.setRange(4, 512)
        self.spin_w.setValue(self.cfg.tile_width)
        self.spin_w.valueChanged.connect(self._on_param_changed)
        form.addRow("Szerokość (px):", self.spin_w)

        self.spin_h = QSpinBox()
        self.spin_h.setRange(4, 512)
        self.spin_h.setValue(self.cfg.tile_height)
        self.spin_h.valueChanged.connect(self._on_param_changed)
        form.addRow("Wysokość (px):", self.spin_h)

        self.spin_margin = QSpinBox()
        self.spin_margin.setRange(0, 128)
        self.spin_margin.setValue(self.cfg.margin)
        self.spin_margin.valueChanged.connect(self._on_param_changed)
        form.addRow("Margines (px):", self.spin_margin)

        self.spin_spacing = QSpinBox()
        self.spin_spacing.setRange(0, 128)
        self.spin_spacing.setValue(self.cfg.spacing)
        self.spin_spacing.valueChanged.connect(self._on_param_changed)
        form.addRow("Odstęp (px):", self.spin_spacing)

        ctrl_layout.addWidget(group)

        # Auto detect button
        btn_autodetect = QPushButton("⚡ Wykryj automatycznie")
        btn_autodetect.clicked.connect(self._autodetect)
        ctrl_layout.addWidget(btn_autodetect)

        # Info labels
        self.lbl_info = QLabel()
        self.lbl_info.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        ctrl_layout.addWidget(self.lbl_info)

        ctrl_layout.addStretch()

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Wybierz i zastosuj")
        btn_ok.setProperty("class", "primary")
        btn_ok.clicked.connect(self._on_apply)

        btn_cancel = QPushButton("Anuluj")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        ctrl_layout.addLayout(btn_layout)

        main_layout.addWidget(ctrl_panel)

        # Right panel: Interactive visual preview
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.preview_widget = TilesetPreviewWidget(self.asset, self.asset_manager)
        self.preview_widget.tile_picked.connect(self._on_tile_picked)
        scroll.setWidget(self.preview_widget)

        main_layout.addWidget(scroll, 1)

        self._update_info()

    def _on_param_changed(self) -> None:
        self.cfg.tile_width = self.spin_w.value()
        self.cfg.tile_height = self.spin_h.value()
        self.cfg.margin = self.spin_margin.value()
        self.cfg.spacing = self.spin_spacing.value()
        self._update_info()
        self.preview_widget.update()

    def _autodetect(self) -> None:
        auto_cfg = self.asset_manager.auto_detect_tileset_config(self.asset)
        self.spin_w.setValue(auto_cfg.tile_width)
        self.spin_h.setValue(auto_cfg.tile_height)
        self.spin_margin.setValue(auto_cfg.margin)
        self.spin_spacing.setValue(auto_cfg.spacing)

    def _on_tile_picked(self, col: int, row: int) -> None:
        self._update_info()

    def _update_info(self) -> None:
        cols, rows = self.asset.get_tileset_dimensions()
        total = cols * rows
        c = self.preview_widget.selected_col
        r = self.preview_widget.selected_row
        self.lbl_info.setText(
            f"Rozmiar pliku: {self.asset.width}x{self.asset.height} px\n"
            f"Siatka: {cols} kolumn x {rows} wierszy\n"
            f"Kafelki łącznie: {total}\n\n"
            f"Wybrany kafelek:\nKolumna: {c}, Wiersz: {r}"
        )

    def _on_apply(self) -> None:
        self.asset.asset_type = AssetType.TILESET
        c = self.preview_widget.selected_col
        r = self.preview_widget.selected_row
        sx, sy, sw, sh = self.asset.get_tile_rect(c, r)

        sub_tile = SelectedSubTile(
            asset_id=self.asset.id,
            col=c,
            row=r,
            sub_x=sx,
            sub_y=sy,
            sub_w=sw,
            sub_h=sh,
        )
        self.asset_manager.select_asset(self.asset, sub_tile)
        self.accept()
