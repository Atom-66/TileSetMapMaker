import os
from typing import Optional, List
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QWidget,
    QLabel,
    QColorDialog,
)
from PyQt6.QtGui import QColor

from ...models.project import Project
from ...core.render_engine import RenderEngine
from ...core.project_io import ProjectIO


class ExportDialog(QDialog):
    """Dialog for configuring and executing high-resolution PNG exports."""

    def __init__(
        self,
        project: Project,
        render_engine: RenderEngine,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.project = project
        self.render_engine = render_engine
        self.setWindowTitle("Eksport do PNG")
        self.resize(480, 380)

        self.custom_bg_hex = "#ffffff"

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Destination file path
        path_layout = QHBoxLayout()
        self.txt_path = QLineEdit()
        default_dir = os.path.dirname(self.project.file_path) if self.project.file_path else os.getcwd()
        default_file = os.path.join(default_dir, f"{self.project.name.replace(' ', '_')}.png")
        self.txt_path.setText(default_file)
        path_layout.addWidget(self.txt_path)

        btn_browse = QPushButton("Przeglądaj...")
        btn_browse.clicked.connect(self._browse_path)
        path_layout.addWidget(btn_browse)
        form.addRow("Ścieżka pliku:", path_layout)

        # Scale Factor (for retro games: 1x, 2x, 4x, etc.)
        self.combo_scale = QComboBox()
        self.combo_scale.addItems(["1x (Oryginał)", "2x (200%)", "4x (400%)", "8x (800%)"])
        form.addRow("Skala eksportu:", self.combo_scale)

        # Export area
        self.combo_area = QComboBox()
        self.combo_area.addItems([
            "Cała mapa (pełne wymiary)",
            "Automatyczne przycięcie do zawartości (Bounding Box)",
        ])
        form.addRow("Obszar eksportu:", self.combo_area)

        # Layers selection
        self.combo_layers = QComboBox()
        self.combo_layers.addItem("Wszystkie widoczne warstwy")
        for layer in self.project.layers:
            self.combo_layers.addItem(f"Tylko warstwa: {layer.name}", layer.id)
        form.addRow("Eksportowane warstwy:", self.combo_layers)

        # Transparency option
        self.chk_transparent = QCheckBox("Przezroczyste tło (Alpha)")
        self.chk_transparent.setChecked(True)
        self.chk_transparent.toggled.connect(self._on_transparent_toggled)
        form.addRow("", self.chk_transparent)

        # Custom Background Color
        self.btn_bg_col = QPushButton("Wybierz kolor tła")
        self.btn_bg_col.setEnabled(False)
        self.btn_bg_col.clicked.connect(self._choose_bg_color)
        form.addRow("Własny kolor tła:", self.btn_bg_col)

        layout.addLayout(form)

        # Info summary
        w_px, h_px = self.render_engine.get_map_dimensions_px(self.project)
        self.lbl_info = QLabel(
            f"Wymiary mapy: {self.project.map_width}x{self.project.map_height} kafelków "
            f"({w_px}x{h_px} px przy kafelku {self.project.tile_size}px)\n"
            f"Ukryte warstwy zostaną automatycznie pominięte."
        )
        self.lbl_info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        layout.addWidget(self.lbl_info)

        layout.addStretch()

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Anuluj")
        btn_cancel.clicked.connect(self.reject)

        btn_export = QPushButton("Eksportuj PNG")
        btn_export.setProperty("class", "primary")
        btn_export.clicked.connect(self._do_export)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_export)
        layout.addLayout(btn_layout)

    def _browse_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Wybierz plik do eksportu PNG",
            self.txt_path.text(),
            "Pliki PNG (*.png)",
        )
        if path:
            self.txt_path.setText(path)

    def _on_transparent_toggled(self, checked: bool) -> None:
        self.btn_bg_col.setEnabled(not checked)

    def _choose_bg_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.custom_bg_hex), self, "Wybierz kolor tła eksportu")
        if color.isValid():
            self.custom_bg_hex = color.name()
            self.btn_bg_col.setStyleSheet(f"background-color: {self.custom_bg_hex}; color: #000;")

    def _do_export(self) -> None:
        out_path = self.txt_path.text().strip()
        if not out_path:
            QMessageBox.warning(self, "Błąd", "Wprowadź prawidłową ścieżkę pliku.")
            return

        scales = [1.0, 2.0, 4.0, 8.0]
        scale = scales[self.combo_scale.currentIndex()]
        crop = self.combo_area.currentIndex() == 1
        trans = self.chk_transparent.isChecked()

        only_layers = None
        if self.combo_layers.currentIndex() > 0:
            lid = self.combo_layers.currentData()
            if lid:
                only_layers = [lid]

        ok = ProjectIO.export_png(
            project=self.project,
            render_engine=self.render_engine,
            file_path=out_path,
            transparent_bg=trans,
            custom_bg_color=None if trans else self.custom_bg_hex,
            only_layer_ids=only_layers,
            crop_to_content=crop,
            scale=scale,
        )

        if ok:
            QMessageBox.information(self, "Sukces", f"Pomyślnie wyeksportowano mapę do pliku:\n{out_path}")
            self.accept()
        else:
            QMessageBox.critical(self, "Błąd", "Nie udało się wyeksportować mapy do pliku PNG.")
