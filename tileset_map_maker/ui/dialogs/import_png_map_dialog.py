import math
import os
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QSlider,
    QCheckBox,
    QDialogButtonBox,
    QGroupBox,
)


class ImportPngMapDialog(QDialog):
    """
    Dialog configuring how a PNG file is imported as a map:
    - Raster map (1:1 original resolution, 100% opacity, full transparency)
    - Reference underlay (adjustable opacity + editable tile layer on top)
    - Tile grid size & new project vs new map in current project
    """

    def __init__(self, file_path: str, default_tile_size: int = 32, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.pixmap = QPixmap(file_path)
        self.img_w = self.pixmap.width() if not self.pixmap.isNull() else 0
        self.img_h = self.pixmap.height() if not self.pixmap.isNull() else 0
        self.has_alpha = self.pixmap.hasAlphaChannel() if not self.pixmap.isNull() else False

        self.setWindowTitle("Import mapy PNG")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Preview & resolution info
        info_box = QGroupBox("Analiza pliku PNG", self)
        info_layout = QHBoxLayout(info_box)

        lbl_thumb = QLabel(info_box)
        lbl_thumb.setFixedSize(96, 96)
        lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_thumb.setStyleSheet("border: 1px solid #3f3f46; background: #18181b;")
        if not self.pixmap.isNull():
            lbl_thumb.setPixmap(
                self.pixmap.scaled(92, 92, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        info_layout.addWidget(lbl_thumb)

        meta_layout = QVBoxLayout()
        meta_layout.addWidget(QLabel(f"<b>Plik:</b> {os.path.basename(file_path)}"))
        meta_layout.addWidget(QLabel(f"<b>Rozdzielczość:</b> {self.img_w} × {self.img_h} px"))
        meta_layout.addWidget(
            QLabel(f"<b>Przezroczystość (Alpha):</b> {'Tak' if self.has_alpha else 'Nie'}")
        )
        self.lbl_grid_dims = QLabel("")
        meta_layout.addWidget(self.lbl_grid_dims)
        info_layout.addLayout(meta_layout, 1)
        layout.addWidget(info_box)

        # Mode selection
        mode_box = QGroupBox("Tryb importu", self)
        mode_layout = QVBoxLayout(mode_box)
        self.rb_reference = QRadioButton("Podkład referencyjny (do odtworzenia mapy na warstwach kafelkowych)", mode_box)
        self.rb_raster = QRadioButton("Mapa rastrowa (pełne krycie 100%, oryginalna rozdzielczość 1:1)", mode_box)
        self.rb_reference.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_reference)
        self.mode_group.addButton(self.rb_raster)
        mode_layout.addWidget(self.rb_reference)
        mode_layout.addWidget(self.rb_raster)

        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("Przezroczystość podkładu:"))
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal, mode_box)
        self.slider_opacity.setRange(10, 100)
        self.slider_opacity.setValue(55)
        self.lbl_opacity = QLabel("55%")
        self.slider_opacity.valueChanged.connect(lambda v: self.lbl_opacity.setText(f"{v}%"))
        op_row.addWidget(self.slider_opacity, 1)
        op_row.addWidget(self.lbl_opacity)
        mode_layout.addLayout(op_row)
        self.rb_reference.toggled.connect(self.slider_opacity.setEnabled)
        layout.addWidget(mode_box)

        # Grid & target
        cfg_box = QGroupBox("Ustawienia siatki i projektu", self)
        form = QFormLayout(cfg_box)
        self.cmb_tile_size = QComboBox(cfg_box)
        for sz in (16, 24, 32, 48, 64):
            self.cmb_tile_size.addItem(f"{sz} × {sz} px", sz)
        idx = self.cmb_tile_size.findData(default_tile_size)
        self.cmb_tile_size.setCurrentIndex(idx if idx >= 0 else 2)
        self.cmb_tile_size.currentIndexChanged.connect(self._update_grid_info)
        form.addRow("Rozmiar kafelka siatki:", self.cmb_tile_size)

        self.chk_add_to_current = QCheckBox("Dodaj jako nową mapę w bieżącym projekcie (zamiast nowego projektu)", cfg_box)
        self.chk_add_to_current.setChecked(False)
        form.addRow("", self.chk_add_to_current)
        layout.addWidget(cfg_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_grid_info()

    def _update_grid_info(self) -> None:
        ts = int(self.cmb_tile_size.currentData() or 32)
        cols = max(1, math.ceil(self.img_w / ts)) if self.img_w > 0 else 1
        rows = max(1, math.ceil(self.img_h / ts)) if self.img_h > 0 else 1
        self.lbl_grid_dims.setText(f"<b>Wymiary siatki mapy:</b> {cols} × {rows} kafelków")

    def get_options(self):
        return {
            "mode": "reference" if self.rb_reference.isChecked() else "raster",
            "tile_size": int(self.cmb_tile_size.currentData() or 32),
            "opacity": self.slider_opacity.value() / 100.0,
            "add_to_current": self.chk_add_to_current.isChecked(),
        }
