from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QCheckBox,
    QSlider,
    QToolButton,
    QLineEdit,
)
from ..models.brush_preset import BrushSettings


class BrushOptionsBar(QWidget):
    """Horizontal top/context toolbar for brush options: size, auto-tile, random transforms, and seed."""
    options_changed = pyqtSignal()

    def __init__(self, brush_settings: BrushSettings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = brush_settings
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(10)

        # 1. Brush Size
        lbl_size = QLabel("Rozmiar pędzla:")
        lbl_size.setStyleSheet("font-size: 11px; color: #a1a1aa;")
        layout.addWidget(lbl_size)

        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 10)
        self.spin_size.setValue(self.settings.size)
        self.spin_size.setFixedWidth(50)
        self.spin_size.valueChanged.connect(self._on_size_changed)
        layout.addWidget(self.spin_size)

        layout.addSpacing(10)

        # 2. Auto-Tiling Toggle
        self.chk_autotile = QCheckBox("⚡ Auto-Tiling")
        self.chk_autotile.setToolTip("Automatycznie dopasowuj brzegi i narożniki terenu podczas malowania")
        self.chk_autotile.setChecked(self.settings.auto_tile_enabled)
        self.chk_autotile.toggled.connect(self._on_autotile_toggled)
        layout.addWidget(self.chk_autotile)

        layout.addSpacing(10)

        # 3. Random Variants
        self.chk_variants = QCheckBox("🎲 Losowe warianty")
        self.chk_variants.setToolTip("Losuj warianty przypisane do pędzla podczas malowania")
        self.chk_variants.setChecked(self.settings.random_variant)
        self.chk_variants.toggled.connect(self._on_variants_toggled)
        layout.addWidget(self.chk_variants)

        # 4. Random Rotation
        self.chk_rot = QCheckBox("🔄 Losowy obrót")
        self.chk_rot.setToolTip("Losuj rotację kafelka (0, 90, 180, 270 stopni)")
        self.chk_rot.setChecked(self.settings.random_rotation)
        self.chk_rot.toggled.connect(self._on_rot_toggled)
        layout.addWidget(self.chk_rot)

        # 5. Random Flip
        self.chk_flip = QCheckBox("↔️ Losowe odbicie")
        self.chk_flip.setChecked(self.settings.random_flip_x)
        self.chk_flip.toggled.connect(self._on_flip_toggled)
        layout.addWidget(self.chk_flip)

        layout.addSpacing(10)

        # 6. Random Seed
        lbl_seed = QLabel("Seed:")
        lbl_seed.setStyleSheet("font-size: 11px; color: #a1a1aa;")
        layout.addWidget(lbl_seed)

        self.txt_seed = QLineEdit()
        self.txt_seed.setPlaceholderText("losowy")
        self.txt_seed.setFixedWidth(70)
        self.txt_seed.textChanged.connect(self._on_seed_changed)
        layout.addWidget(self.txt_seed)

        layout.addStretch()

    def _on_size_changed(self, val: int) -> None:
        self.settings.size = val
        self.options_changed.emit()

    def _on_autotile_toggled(self, checked: bool) -> None:
        self.settings.auto_tile_enabled = checked
        self.options_changed.emit()

    def _on_variants_toggled(self, checked: bool) -> None:
        self.settings.random_variant = checked
        self.options_changed.emit()

    def _on_rot_toggled(self, checked: bool) -> None:
        self.settings.random_rotation = checked
        self.options_changed.emit()

    def _on_flip_toggled(self, checked: bool) -> None:
        self.settings.random_flip_x = checked
        self.settings.random_flip_y = checked
        self.options_changed.emit()

    def _on_seed_changed(self, text: str) -> None:
        if text.strip().isdigit():
            self.settings.seed = int(text.strip())
        else:
            self.settings.seed = None
        self.settings.reset_rng()
        self.options_changed.emit()
