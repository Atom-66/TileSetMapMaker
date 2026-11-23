import os
from typing import Optional, Tuple
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QDialogButtonBox,
)
from PyQt6.QtGui import QImage, QColor
from ..icons import IconFactory


class TilesetImportDialog(QDialog):
    """
    Dialog for configuring uniform regular grid cell dimensions (tile_w, tile_h)
    when importing a new tileset sheet PNG.
    """

    def __init__(
        self,
        file_path: str,
        default_tile_size: int = 32,
        parent: Optional[QDialog] = None,
    ):
        super().__init__(parent)
        self.file_path = file_path
        self.img_w = 0
        self.img_h = 0
        self.has_alpha = False

        self._read_image_metadata()

        self.setWindowTitle("Konfiguracja nowego tilesetu")
        self.setMinimumWidth(440)
        self.setStyleSheet("""
            QDialog {
                background-color: #18181b;
                color: #e4e4e7;
            }
            QGroupBox {
                border: 1px solid #27272a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
                color: #93c5fd;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel {
                color: #d4d4d8;
                font-size: 12px;
            }
            QSpinBox {
                background: #27272a;
                color: #ffffff;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton {
                background: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #3f3f46;
            }
            QPushButton#btn_primary {
                background: #2563eb;
                border: 1px solid #3b82f6;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#btn_primary:hover {
                background: #1d4ed8;
            }
            QPushButton#btn_preset {
                padding: 4px 8px;
                font-size: 11px;
                background: #202025;
            }
            QPushButton#btn_preset:hover {
                background: #2e2e38;
                border-color: #3b82f6;
            }
        """)

        self._init_ui(default_tile_size)
        self._update_calculation()

    def _read_image_metadata(self) -> None:
        if os.path.exists(self.file_path):
            img = QImage(self.file_path)
            if not img.isNull():
                self.img_w = img.width()
                self.img_h = img.height()
                self.has_alpha = img.hasAlphaChannel()

    def _init_ui(self, default_tile_size: int) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # 1. File Details Group
        grp_file = QGroupBox("Plik graficzny")
        form_file = QFormLayout(grp_file)
        form_file.setContentsMargins(12, 14, 12, 12)
        form_file.setSpacing(8)

        lbl_fname = QLabel(os.path.basename(self.file_path))
        lbl_fname.setStyleSheet("color: #60a5fa; font-weight: bold;")
        form_file.addRow("Nazwa pliku:", lbl_fname)

        lbl_dims = QLabel(f"{self.img_w} × {self.img_h} px")
        lbl_dims.setStyleSheet("font-weight: bold;")
        form_file.addRow("Wymiary arkusza:", lbl_dims)

        lbl_alpha = QLabel("Tak (RGBA)" if self.has_alpha else "Brak przezroczystości (RGB)")
        lbl_alpha.setStyleSheet("color: #34d399;" if self.has_alpha else "color: #a1a1aa;")
        form_file.addRow("Kanał alfa:", lbl_alpha)

        layout.addWidget(grp_file)

        # 2. Grid Dimensions Group
        grp_grid = QGroupBox("Rozmiar kafelka siatki (Uniform Regular Grid)")
        layout_grid = QVBoxLayout(grp_grid)
        layout_grid.setContentsMargins(12, 14, 12, 12)
        layout_grid.setSpacing(10)

        # Presets row
        lbl_presets = QLabel("Szybkie szablony:")
        layout_grid.addWidget(lbl_presets)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        presets = [
            ("16 × 16", 16, 16),
            ("24 × 24", 24, 24),
            ("32 × 32", 32, 32),
            ("32 × 48", 32, 48),
            ("48 × 48", 48, 48),
            ("64 × 64", 64, 64),
        ]
        for label, pw, ph in presets:
            btn = QPushButton(label)
            btn.setObjectName("btn_preset")
            btn.clicked.connect(lambda ch, w=pw, h=ph: self._apply_preset(w, h))
            preset_row.addWidget(btn)
        layout_grid.addLayout(preset_row)

        # Custom inputs
        spin_row = QHBoxLayout()
        spin_row.setSpacing(14)

        lbl_w = QLabel("Szerokość (px):")
        self.spin_w = QSpinBox()
        self.spin_w.setRange(4, max(512, self.img_w or 512))
        self.spin_w.setValue(default_tile_size)
        self.spin_w.valueChanged.connect(self._update_calculation)

        lbl_h = QLabel("Wysokość (px):")
        self.spin_h = QSpinBox()
        self.spin_h.setRange(4, max(512, self.img_h or 512))
        self.spin_h.setValue(default_tile_size)
        self.spin_h.valueChanged.connect(self._update_calculation)

        spin_row.addWidget(lbl_w)
        spin_row.addWidget(self.spin_w)
        spin_row.addSpacing(10)
        spin_row.addWidget(lbl_h)
        spin_row.addWidget(self.spin_h)
        spin_row.addStretch()
        layout_grid.addLayout(spin_row)

        layout.addWidget(grp_grid)

        # 3. Calculated Grid Info Box
        self.grp_calc = QGroupBox("Wynik podziału siatki")
        layout_calc = QVBoxLayout(self.grp_calc)
        layout_calc.setContentsMargins(12, 14, 12, 12)

        self.lbl_calc_main = QLabel("Obliczanie...")
        self.lbl_calc_main.setStyleSheet("font-size: 13px; font-weight: bold; color: #f4f4f5;")
        layout_calc.addWidget(self.lbl_calc_main)

        self.lbl_calc_rem = QLabel("")
        self.lbl_calc_rem.setStyleSheet("font-size: 11px; color: #fbbf24;")
        self.lbl_calc_rem.setWordWrap(True)
        layout_calc.addWidget(self.lbl_calc_rem)

        layout.addWidget(self.grp_calc)

        # 4. Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton(" Anuluj")
        btn_cancel.setIcon(IconFactory.get_icon("close", 14))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_import = QPushButton(" Zaimportuj tileset")
        btn_import.setIcon(IconFactory.get_icon("file-plus", 16))
        btn_import.setObjectName("btn_primary")
        btn_import.clicked.connect(self.accept)
        btn_layout.addWidget(btn_import)

        layout.addLayout(btn_layout)

    def _apply_preset(self, w: int, h: int) -> None:
        self.spin_w.setValue(w)
        self.spin_h.setValue(h)

    def _update_calculation(self) -> None:
        tw = self.spin_w.value()
        th = self.spin_h.value()
        if tw <= 0 or th <= 0 or self.img_w <= 0 or self.img_h <= 0:
            self.lbl_calc_main.setText("Nieprawidłowy rozmiar kafelka.")
            self.lbl_calc_rem.setText("")
            return

        cols = self.img_w // tw
        rows = self.img_h // th
        total = cols * rows
        rem_x = self.img_w % tw
        rem_y = self.img_h % th

        self.lbl_calc_main.setText(
            f"🗺️ Siatka: {cols} kolumn × {rows} wierszy = {total} kafelków ({tw} × {th} px)"
        )

        if rem_x > 0 or rem_y > 0:
            rem_parts = []
            if rem_x > 0:
                rem_parts.append(f"{rem_x} px po prawej")
            if rem_y > 0:
                rem_parts.append(f"{rem_y} px na dole")
            self.lbl_calc_rem.setText(
                f"ℹ️ Margines resztkowy: {', '.join(rem_parts)} zostanie automatycznie przyciemniony i wykluczony z siatki."
            )
        else:
            self.lbl_calc_rem.setText("✅ Idealne dopasowanie siatki (brak marginesów resztkowych).")

    def get_tile_dimensions(self) -> Tuple[int, int]:
        return self.spin_w.value(), self.spin_h.value()
