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

from ...core.localization import get_localization, tr


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

        self.setWindowTitle(tr("dialog.import_png.title"))
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Preview & resolution info
        self.info_box = QGroupBox(tr("dialog.import_png.analysis_group"), self)
        info_layout = QHBoxLayout(self.info_box)

        lbl_thumb = QLabel(self.info_box)
        lbl_thumb.setFixedSize(96, 96)
        lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_thumb.setStyleSheet("border: 1px solid #3f3f46; background: #18181b;")
        if not self.pixmap.isNull():
            lbl_thumb.setPixmap(
                self.pixmap.scaled(92, 92, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        info_layout.addWidget(lbl_thumb)

        meta_layout = QVBoxLayout()
        self.lbl_file = QLabel()
        self.lbl_res = QLabel()
        self.lbl_alpha = QLabel()
        self.lbl_grid_dims = QLabel("")
        meta_layout.addWidget(self.lbl_file)
        meta_layout.addWidget(self.lbl_res)
        meta_layout.addWidget(self.lbl_alpha)
        meta_layout.addWidget(self.lbl_grid_dims)
        info_layout.addLayout(meta_layout, 1)
        layout.addWidget(self.info_box)

        # Mode selection
        self.mode_box = QGroupBox(tr("dialog.import_png.mode_group"), self)
        mode_layout = QVBoxLayout(self.mode_box)
        self.rb_reference = QRadioButton(tr("dialog.import_png.mode_reference"), self.mode_box)
        self.rb_raster = QRadioButton(tr("dialog.import_png.mode_raster"), self.mode_box)
        self.rb_reference.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_reference)
        self.mode_group.addButton(self.rb_raster)
        mode_layout.addWidget(self.rb_reference)
        mode_layout.addWidget(self.rb_raster)

        op_row = QHBoxLayout()
        self.lbl_opacity_title = QLabel(tr("dialog.import_png.opacity_label"))
        op_row.addWidget(self.lbl_opacity_title)
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal, self.mode_box)
        self.slider_opacity.setRange(10, 100)
        self.slider_opacity.setValue(55)
        self.lbl_opacity = QLabel("55%")
        self.slider_opacity.valueChanged.connect(lambda v: self.lbl_opacity.setText(f"{v}%"))
        op_row.addWidget(self.slider_opacity, 1)
        op_row.addWidget(self.lbl_opacity)
        mode_layout.addLayout(op_row)
        self.rb_reference.toggled.connect(self.slider_opacity.setEnabled)
        layout.addWidget(self.mode_box)

        # Grid & target
        self.cfg_box = QGroupBox(tr("dialog.import_png.grid_group"), self)
        self.cfg_form = QFormLayout(self.cfg_box)
        self.cmb_tile_size = QComboBox(self.cfg_box)
        for sz in (16, 24, 32, 48, 64):
            self.cmb_tile_size.addItem(f"{sz} × {sz} px", sz)
        idx = self.cmb_tile_size.findData(default_tile_size)
        self.cmb_tile_size.setCurrentIndex(idx if idx >= 0 else 2)
        self.cmb_tile_size.currentIndexChanged.connect(self._update_grid_info)
        self.cfg_form.addRow(tr("dialog.import_png.tile_size_label"), self.cmb_tile_size)

        self.chk_add_to_current = QCheckBox(tr("dialog.import_png.add_to_current"), self.cfg_box)
        self.chk_add_to_current.setChecked(False)
        self.cfg_form.addRow("", self.chk_add_to_current)
        layout.addWidget(self.cfg_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._apply_language()
        get_localization().languageChanged.connect(self._apply_language)

    def _apply_language(self, *_args) -> None:
        self.setWindowTitle(tr("dialog.import_png.title"))
        self.info_box.setTitle(tr("dialog.import_png.analysis_group"))
        self.lbl_file.setText(tr("dialog.import_png.file_label", name=os.path.basename(self.file_path)))
        self.lbl_res.setText(tr("dialog.import_png.resolution_label", width=self.img_w, height=self.img_h))
        alpha_str = tr("dialog.import_png.yes") if self.has_alpha else tr("dialog.import_png.no")
        self.lbl_alpha.setText(tr("dialog.import_png.alpha_label", value=alpha_str))
        self.mode_box.setTitle(tr("dialog.import_png.mode_group"))
        self.rb_reference.setText(tr("dialog.import_png.mode_reference"))
        self.rb_raster.setText(tr("dialog.import_png.mode_raster"))
        self.lbl_opacity_title.setText(tr("dialog.import_png.opacity_label"))
        self.cfg_box.setTitle(tr("dialog.import_png.grid_group"))
        lbl_ts = self.cfg_form.labelForField(self.cmb_tile_size)
        if lbl_ts is not None:
            lbl_ts.setText(tr("dialog.import_png.tile_size_label"))
        self.chk_add_to_current.setText(tr("dialog.import_png.add_to_current"))
        self._update_grid_info()

    def _update_grid_info(self) -> None:
        ts = int(self.cmb_tile_size.currentData() or 32)
        cols = max(1, math.ceil(self.img_w / ts)) if self.img_w > 0 else 1
        rows = max(1, math.ceil(self.img_h / ts)) if self.img_h > 0 else 1
        self.lbl_grid_dims.setText(tr("dialog.import_png.grid_dims", cols=cols, rows=rows))

    def get_options(self):
        return {
            "mode": "reference" if self.rb_reference.isChecked() else "raster",
            "tile_size": int(self.cmb_tile_size.currentData() or 32),
            "opacity": self.slider_opacity.value() / 100.0,
            "add_to_current": self.chk_add_to_current.isChecked(),
        }
