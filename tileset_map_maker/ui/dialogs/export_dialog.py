import os
from typing import Optional, List
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
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
from ..widgets.switch_toggle import SwitchToggle
from ..icons import IconFactory
from ...core.localization import tr


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
        self.setWindowTitle(tr("dialog.export.title"))
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

        btn_browse = QPushButton(" " + tr("button.browse"))
        btn_browse.setIcon(IconFactory.get_icon("folder-open", 14))
        btn_browse.clicked.connect(self._browse_path)
        path_layout.addWidget(btn_browse)
        form.addRow(tr("dialog.export.path"), path_layout)

        # Scale Factor (for retro games: 1x, 2x, 4x, etc.)
        self.combo_scale = QComboBox()
        self.combo_scale.addItems([
            tr("dialog.export.scale_1"), tr("dialog.export.scale_2"),
            tr("dialog.export.scale_4"), tr("dialog.export.scale_8"),
        ])
        form.addRow(tr("dialog.export.scale"), self.combo_scale)

        self.combo_scope = QComboBox()
        self.combo_scope.addItem("Aktywna mapa")
        self.combo_scope.addItem("Wszystkie mapy")
        form.addRow("Zakres:", self.combo_scope)

        # Export area
        self.combo_area = QComboBox()
        self.combo_area.addItems([
            tr("dialog.export.area_full"),
            tr("dialog.export.area_crop"),
        ])
        form.addRow("Obszar eksportu:", self.combo_area)

        # Layers selection
        self.combo_layers = QComboBox()
        self.combo_layers.addItem(tr("dialog.export.layers_all"))
        for layer in self.project.layers:
            self.combo_layers.addItem(
                tr("dialog.export.layer_only", name=layer.name), layer.id
            )
        form.addRow(tr("dialog.export.layers_label"), self.combo_layers)

        # Transparency option
        self.chk_transparent = SwitchToggle(tr("dialog.export.transparent"), checked=True)
        self.chk_transparent.toggled.connect(self._on_transparent_toggled)
        form.addRow("", self.chk_transparent)

        # Custom Background Color
        self.btn_bg_col = QPushButton(f" {tr('dialog.export.choose_bg')}")
        self.btn_bg_col.setIcon(IconFactory.get_icon("palette", 14))
        self.btn_bg_col.setEnabled(False)
        self.btn_bg_col.clicked.connect(self._choose_bg_color)
        form.addRow(tr("dialog.export.bg_label"), self.btn_bg_col)

        layout.addLayout(form)

        # Info summary
        w_px, h_px = self.render_engine.get_map_dimensions_px(self.project)
        self.lbl_info = QLabel(
            tr(
                "dialog.export.info",
                cols=self.project.map_width,
                rows=self.project.map_height,
                width=w_px,
                height=h_px,
                tile_size=self.project.tile_size,
            )
        )
        self.lbl_info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        layout.addWidget(self.lbl_info)

        layout.addStretch()

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton(f" {tr('dialog.map.cancel')}")
        btn_cancel.setIcon(IconFactory.get_icon("close", 14))
        btn_cancel.clicked.connect(self.reject)

        btn_export = QPushButton(f" {tr('dialog.export.action')}")
        btn_export.setIcon(IconFactory.get_icon("export", 16))
        btn_export.setProperty("class", "primary")
        btn_export.clicked.connect(self._do_export)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_export)
        layout.addLayout(btn_layout)

    def _browse_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("dialog.export.browse_title"),
            self.txt_path.text(),
            "Pliki PNG (*.png)",
        )
        if path:
            self.txt_path.setText(path)

    def _on_transparent_toggled(self, checked: bool) -> None:
        self.btn_bg_col.setEnabled(not checked)

    def _choose_bg_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self.custom_bg_hex), self, tr("dialog.export.choose_bg")
        )
        if color.isValid():
            self.custom_bg_hex = color.name()
            self.btn_bg_col.setStyleSheet(f"background-color: {self.custom_bg_hex}; color: #000;")

    def _do_export(self) -> None:
        out_path = self.txt_path.text().strip()
        if not out_path:
            QMessageBox.warning(
                self,
                tr("dialog.export.error_title"),
                tr("dialog.export.invalid_path"),
            )
            return
        missing_assets = ProjectIO.validate_project_assets(
            self.project, self.render_engine.asset_manager
        )
        if missing_assets:
            answer = QMessageBox.question(
                self,
                tr("dialog.export.error_title"),
                "Projekt odwołuje się do brakujących zasobów:\n"
                + "\n".join(missing_assets[:10])
                + "\n\nKontynuować eksport?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
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

        export_options = {
            "transparent_bg": trans,
            "custom_bg_color": None if trans else self.custom_bg_hex,
            "only_layer_ids": only_layers,
            "crop_to_content": crop,
            "scale": scale,
        }
        if self.combo_scope.currentIndex() == 1:
            ok = ProjectIO.export_maps_png(
                project=self.project,
                render_engine=self.render_engine,
                output_dir=os.path.dirname(out_path) or ".",
                **export_options,
            )
        else:
            ok = ProjectIO.export_png(
                project=self.project,
                render_engine=self.render_engine,
                file_path=out_path,
                **export_options,
            )

        if ok:
            QMessageBox.information(
                self,
                tr("dialog.export.success_title"),
                tr("dialog.export.success", path=out_path),
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                tr("dialog.export.error_title"),
                tr("dialog.export.failure"),
            )
