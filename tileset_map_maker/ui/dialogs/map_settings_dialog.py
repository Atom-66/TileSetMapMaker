from typing import Optional
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QPushButton,
    QColorDialog,
    QWidget,
)
from PyQt6.QtGui import QColor

from ...models.project import Project


class MapSettingsDialog(QDialog):
    """Dialog for editing map dimensions, tile size, and background."""

    def __init__(self, project: Project, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Ustawienia mapy")
        self.resize(380, 320)

        self.current_bg = project.background_color

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Map Width (in tiles)
        self.spin_width = QSpinBox()
        self.spin_width.setRange(1, 2000)
        self.spin_width.setValue(self.project.map_width)
        form.addRow("Szerokość mapy (kafelki):", self.spin_width)

        # Map Height (in tiles)
        self.spin_height = QSpinBox()
        self.spin_height.setRange(1, 2000)
        self.spin_height.setValue(self.project.map_height)
        form.addRow("Wysokość mapy (kafelki):", self.spin_height)

        # Tile Size (px)
        self.combo_tile_size = QComboBox()
        self.combo_tile_size.setEditable(True)
        common_sizes = ["16", "24", "32", "48", "64", "128"]
        self.combo_tile_size.addItems(common_sizes)
        self.combo_tile_size.setCurrentText(str(self.project.tile_size))
        form.addRow("Rozmiar kafelka (px):", self.combo_tile_size)

        # Anchor for resizing
        self.combo_anchor = QComboBox()
        self.combo_anchor.addItems(["Lewy górny róg", "Środek", "Prawy dolny róg"])
        form.addRow("Punkt zakotwiczenia przy zmianie rozmiaru:", self.combo_anchor)

        # Background color
        bg_layout = QHBoxLayout()
        self.btn_color = QPushButton("Wybierz kolor")
        self._update_color_btn()
        self.btn_color.clicked.connect(self._choose_color)
        bg_layout.addWidget(self.btn_color)
        form.addRow("Kolor tła:", bg_layout)

        # Transparent background toggle
        self.chk_transparent = QCheckBox("Przezroczyste tło (brak tła)")
        self.chk_transparent.setChecked(self.project.is_bg_transparent)
        form.addRow("", self.chk_transparent)

        layout.addLayout(form)
        layout.addStretch()

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Anuluj")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Zapisz zmiany")
        btn_save.setProperty("class", "primary")
        btn_save.clicked.connect(self._save_settings)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _choose_color(self) -> None:
        initial = QColor(self.current_bg)
        color = QColorDialog.getColor(initial, self, "Wybierz kolor tła mapy")
        if color.isValid():
            self.current_bg = color.name()
            self._update_color_btn()

    def _update_color_btn(self) -> None:
        self.btn_color.setStyleSheet(f"background-color: {self.current_bg}; color: #ffffff;")

    def _save_settings(self) -> None:
        new_w = self.spin_width.value()
        new_h = self.spin_height.value()
        try:
            new_ts = int(self.combo_tile_size.currentText())
        except ValueError:
            new_ts = 32

        anchors = ["top_left", "center", "bottom_right"]
        anchor_val = anchors[self.combo_anchor.currentIndex()]

        self.project.resize_map(new_w, new_h, anchor=anchor_val)
        self.project.tile_size = new_ts
        self.project.background_color = self.current_bg
        self.project.is_bg_transparent = self.chk_transparent.isChecked()
        self.accept()
