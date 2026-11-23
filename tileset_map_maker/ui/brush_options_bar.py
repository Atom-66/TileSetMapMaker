from typing import Optional, Any, Dict
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QToolButton,
    QLineEdit,
    QComboBox,
    QMessageBox,
    QFrame,
)
from ..models.brush_preset import BrushSettings
from ..models.asset import SelectedSubTile
from .widgets.switch_toggle import SwitchToggle, ToolbarToggleButton
from .icons import IconFactory
from .dialogs.tile_randomizer_dialog import TileRandomizerDialog
from .dialogs.path_generator_dialog import PathGeneratorDialog
from ..core.localization import tr, get_localization


class BrushOptionsBar(QWidget):
    """Integrated toolbar component for brush & editing options: size, auto-tiling, path generator, variants, transforms, and seed."""
    options_changed = pyqtSignal()

    def __init__(
        self,
        brush_settings: BrushSettings,
        autotile_engine: Optional[Any] = None,
        asset_manager: Optional[Any] = None,
        project: Optional[Any] = None,
        history_manager: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.settings = brush_settings
        self.autotile_engine = autotile_engine
        self.asset_manager = asset_manager
        self.project = project
        self.history_manager = history_manager
        self.active_tool_name = "brush"

        self._init_ui()
        self.refresh_rulesets()
        self.update_variants_summary()
        get_localization().languageChanged.connect(self._apply_language)

    def _apply_language(self, _language: str) -> None:
        if hasattr(self, "lbl_size"):
            self.set_active_tool(self.active_tool_name)
        if hasattr(self, "chk_autotile"):
            self.chk_autotile.setText(tr("tile.autotile"))
            self.chk_autotile.setToolTip(tr("brush.autotile_tooltip"))
            self.combo_rules.setToolTip(tr("brush.rules_combo_tooltip"))
        if hasattr(self, "btn_autotile"):
            self.btn_autotile.setText(" " + tr("brush.rules"))
            self.btn_autotile.setToolTip(tr("brush.rules_tooltip"))
        if hasattr(self, "btn_path_gen"):
            self.btn_path_gen.setText(" " + tr("brush.paths"))
            self.btn_path_gen.setToolTip(tr("brush.path_tooltip"))
        if hasattr(self, "chk_variants"):
            self.chk_variants.setText(tr("brush.randomizer"))
            self.chk_variants.setToolTip(tr("brush.variant_tooltip"))
            self.lbl_variant_count.setToolTip(tr("brush.variant_count_tooltip"))
            self.btn_add_selection_variants.setText(" " + tr("brush.add_selection"))
            self.btn_add_selection_variants.setToolTip(tr("brush.add_selection_tooltip"))
            self.btn_randomizer.setText(" " + tr("brush.options"))
            self.btn_randomizer.setToolTip(tr("brush.randomizer_tooltip"))
        if hasattr(self, "chk_avoid"):
            self.chk_avoid.setText(tr("brush.no_repeat"))
            self.chk_avoid.setToolTip(tr("brush.avoid_tooltip"))
        if hasattr(self, "chk_rot"):
            self.chk_rot.setText(tr("brush.rotation"))
            self.chk_rot.setToolTip(tr("brush.rotation_tooltip"))
        if hasattr(self, "chk_flip"):
            self.chk_flip.setText(tr("brush.flip"))
            self.chk_flip.setToolTip(tr("brush.flip_tooltip"))
        if hasattr(self, "lbl_seed"):
            self.lbl_seed.setText(tr("brush.seed"))
            self.txt_seed.setPlaceholderText(tr("brush.seed_placeholder"))
            self.txt_seed.setToolTip(tr("brush.seed_tooltip"))

    def set_active_tool(self, tool_key: str) -> None:
        """Adapts the size label and spinbox to the currently selected active tool (Brush or Eraser)."""
        self.active_tool_name = tool_key
        self.spin_size.blockSignals(True)
        if tool_key == "eraser":
            self.lbl_size.setText(tr("tool.eraser") + ":")
            self.spin_size.setToolTip(tr("brush.eraser_size_tooltip"))
            self.spin_size.setValue(getattr(self.settings, "eraser_size", 1))
        else:
            self.lbl_size.setText(tr("tool.brush") + ":")
            self.spin_size.setToolTip(tr("brush.size_tooltip"))
            self.spin_size.setValue(getattr(self.settings, "size", 1))
        self.spin_size.blockSignals(False)

    def _create_separator(self) -> QFrame:
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setStyleSheet("color: #3f3f46; background-color: #3f3f46; max-height: 20px; width: 1px;")
        return sep

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(6)
        self.setStyleSheet("background: transparent;")

        # 1. Rozmiar pędzla
        self.widget_brush_size = QWidget()
        lay_size = QHBoxLayout(self.widget_brush_size)
        lay_size.setContentsMargins(0, 0, 0, 0)
        lay_size.setSpacing(4)

        self.lbl_size = QLabel(tr("brush.size"))
        self.lbl_size.setStyleSheet("font-size: 11px; color: #a1a1aa; font-weight: 500;")
        lay_size.addWidget(self.lbl_size)

        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 10)
        self.spin_size.setValue(self.settings.size)
        self.spin_size.setFixedWidth(44)
        self.spin_size.setFixedHeight(26)
        self.spin_size.setStyleSheet(self._input_style())
        self.spin_size.setToolTip(tr("brush.size_tooltip"))
        self.spin_size.valueChanged.connect(self._on_size_changed)
        lay_size.addWidget(self.spin_size)

        layout.addWidget(self.widget_brush_size)

        layout.addWidget(self._create_separator())

        # 2. Auto-Tiling & Ścieżki
        self.chk_autotile = ToolbarToggleButton(tr("tile.autotile"), checked=self.settings.auto_tile_enabled, icon_name="autotile")
        self.chk_autotile.setToolTip(tr("brush.autotile_tooltip"))
        self.chk_autotile.toggled.connect(self._on_autotile_toggled)
        layout.addWidget(self.chk_autotile)

        self.combo_rules = QComboBox()
        self.combo_rules.setToolTip(tr("brush.rules_combo_tooltip"))
        self.combo_rules.setEnabled(self.settings.auto_tile_enabled)
        self.combo_rules.setFixedHeight(26)
        self.combo_rules.setMaximumWidth(125)
        self.combo_rules.setStyleSheet(self._combo_style())
        self.combo_rules.currentIndexChanged.connect(self._on_rule_changed)
        layout.addWidget(self.combo_rules)

        self.btn_autotile = QToolButton()
        self.btn_autotile.setIcon(IconFactory.get_icon("autotile", 14))
        self.btn_autotile.setText(" " + tr("brush.rules"))
        self.btn_autotile.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_autotile.setToolTip(tr("brush.rules_tooltip"))
        self.btn_autotile.setFixedHeight(26)
        self.btn_autotile.setStyleSheet(self._button_style())
        self.btn_autotile.clicked.connect(self.open_autotile_dialog)
        layout.addWidget(self.btn_autotile)

        self.btn_path_gen = QToolButton()
        self.btn_path_gen.setIcon(IconFactory.get_icon("path", 14))
        self.btn_path_gen.setText(" " + tr("brush.paths"))
        self.btn_path_gen.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_path_gen.setToolTip(tr("brush.path_tooltip"))
        self.btn_path_gen.setFixedHeight(26)
        self.btn_path_gen.setStyleSheet(self._button_style())
        self.btn_path_gen.clicked.connect(self.open_path_generator_dialog)
        layout.addWidget(self.btn_path_gen)

        layout.addWidget(self._create_separator())

        # 3. Losowe warianty kafelków (Tile Randomizer)
        self.chk_variants = ToolbarToggleButton(tr("brush.randomizer"), checked=self.settings.random_variant, icon_name="randomizer")
        self.chk_variants.setToolTip(tr("brush.variant_tooltip"))
        self.chk_variants.toggled.connect(self._on_variants_toggled)
        layout.addWidget(self.chk_variants)

        self.lbl_variant_count = QLabel("(0)")
        self.lbl_variant_count.setStyleSheet("font-size: 11px; color: #60a5fa; font-weight: bold; background: #27272a; border: 1px solid #3f3f46; border-radius: 4px; padding: 2px 6px;")
        self.lbl_variant_count.setFixedHeight(26)
        self.lbl_variant_count.setToolTip(tr("brush.variant_count_tooltip"))
        layout.addWidget(self.lbl_variant_count)

        self.btn_add_selection_variants = QToolButton()
        self.btn_add_selection_variants.setIcon(IconFactory.get_icon("plus", 14))
        self.btn_add_selection_variants.setText(" " + tr("brush.add_selection"))
        self.btn_add_selection_variants.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_add_selection_variants.setToolTip(tr("brush.add_selection_tooltip"))
        self.btn_add_selection_variants.setFixedHeight(26)
        self.btn_add_selection_variants.setStyleSheet(self._button_style())
        self.btn_add_selection_variants.clicked.connect(self._add_current_selection_as_variants)
        layout.addWidget(self.btn_add_selection_variants)

        self.chk_avoid = ToolbarToggleButton(tr("brush.no_repeat"), checked=self.settings.avoid_adjacent, icon_name="sparkles")
        self.chk_avoid.setToolTip(tr("brush.avoid_tooltip"))
        self.chk_avoid.toggled.connect(self._on_avoid_toggled)
        layout.addWidget(self.chk_avoid)

        self.btn_randomizer = QToolButton()
        self.btn_randomizer.setIcon(IconFactory.get_icon("randomizer", 14))
        self.btn_randomizer.setText(" " + tr("brush.options"))
        self.btn_randomizer.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_randomizer.setToolTip(tr("brush.randomizer_tooltip"))
        self.btn_randomizer.setFixedHeight(26)
        self.btn_randomizer.setStyleSheet(self._button_style())
        self.btn_randomizer.clicked.connect(self.open_randomizer_dialog)
        layout.addWidget(self.btn_randomizer)

        layout.addWidget(self._create_separator())

        # 4. Losowy obrót, odbicie i ziarno (Seed)
        self.chk_rot = ToolbarToggleButton(tr("brush.rotation"), checked=self.settings.random_rotation, icon_name="rotate")
        self.chk_rot.setToolTip(tr("brush.rotation_tooltip"))
        self.chk_rot.toggled.connect(self._on_rot_toggled)
        layout.addWidget(self.chk_rot)

        self.chk_flip = ToolbarToggleButton(tr("brush.flip"), checked=self.settings.random_flip_x, icon_name="flip-horizontal")
        self.chk_flip.setToolTip(tr("brush.flip_tooltip"))
        self.chk_flip.toggled.connect(self._on_flip_toggled)
        layout.addWidget(self.chk_flip)

        self.widget_seed = QWidget()
        lay_seed = QHBoxLayout(self.widget_seed)
        lay_seed.setContentsMargins(0, 0, 0, 0)
        lay_seed.setSpacing(4)

        self.lbl_seed = QLabel(tr("brush.seed"))
        self.lbl_seed.setStyleSheet("font-size: 11px; color: #a1a1aa; font-weight: 500;")
        lay_seed.addWidget(self.lbl_seed)

        self.txt_seed = QLineEdit()
        self.txt_seed.setPlaceholderText(tr("brush.seed_placeholder"))
        self.txt_seed.setFixedWidth(54)
        self.txt_seed.setFixedHeight(26)
        self.txt_seed.setStyleSheet(self._input_style())
        self.txt_seed.setToolTip(tr("brush.seed_tooltip"))
        if self.settings.seed is not None:
            self.txt_seed.setText(str(self.settings.seed))
        self.txt_seed.textChanged.connect(self._on_seed_changed)
        lay_seed.addWidget(self.txt_seed)

        layout.addWidget(self.widget_seed)

    def get_toolbar_items(self) -> Dict[str, Dict[str, Any]]:
        """Provides all brush and generation controls for modular toolbar categories."""
        return {
            "brush_size": {
                "label": "Rozmiar pędzla",
                "category": "brush",
                "widget": self.widget_brush_size,
                "icon": "brush",
                "tooltip": "Rozmiar pędzla (1-10 kafelków)",
            },
            "autotile_toggle": {
                "label": "Auto-Tile",
                "category": "autotile",
                "widget": self.chk_autotile,
                "icon": "autotile",
                "tooltip": "Automatycznie dopasowuj brzegi i narożniki terenu podczas malowania",
            },
            "autotile_rules": {
                "label": "Zestaw reguł Auto-Tile",
                "category": "autotile",
                "widget": self.combo_rules,
                "icon": "autotile",
                "tooltip": "Wybierz aktywny zestaw reguł Auto-Tiling / Ścieżek dla pędzla",
            },
            "autotile_dialog": {
                "label": "Konfigurator reguł Auto-Tile",
                "category": "autotile",
                "widget": self.btn_autotile,
                "icon": "autotile",
                "tooltip": "Otwórz konfigurator reguł Auto-Tiling",
            },
            "path_gen_dialog": {
                "label": "Generator Ścieżek",
                "category": "paths",
                "widget": self.btn_path_gen,
                "icon": "path",
                "tooltip": "Otwórz Generator Ścieżek (konfigurator kafelków ścieżki i podgląd na żywo)",
            },
            "variants_toggle": {
                "label": "Randomizer",
                "category": "randomizer",
                "widget": self.chk_variants,
                "icon": "randomizer",
                "tooltip": "Włącz losowy wybór kafelków (Tile Randomizer)",
            },
            "variants_count": {
                "label": "Licznik wariantów Randomizera",
                "category": "randomizer",
                "widget": self.lbl_variant_count,
                "icon": "randomizer",
                "tooltip": "Liczba aktywnych wariantów pędzla w Randomizerze",
            },
            "variants_add": {
                "label": "Dodaj zaznaczenie do Randomizera",
                "category": "randomizer",
                "widget": self.btn_add_selection_variants,
                "icon": "plus",
                "tooltip": "Dodaj aktualnie zaznaczony kafelek lub blok kafelków do Randomizera",
            },
            "variants_avoid": {
                "label": "Bez powtórzeń (Avoid Adjacent)",
                "category": "randomizer",
                "widget": self.chk_avoid,
                "icon": "sparkles",
                "tooltip": "Zapobiega umieszczaniu identycznych wariantów bezpośrednio obok siebie",
            },
            "variants_dialog": {
                "label": "Konfigurator Randomizera",
                "category": "randomizer",
                "widget": self.btn_randomizer,
                "icon": "randomizer",
                "tooltip": "Otwórz konfigurator wariantów, wag i seeda (Tile Randomizer)",
            },
            "rot_toggle": {
                "label": "Losowy obrót (Rotation)",
                "category": "transforms",
                "widget": self.chk_rot,
                "icon": "rotate",
                "tooltip": "Losuj rotację kafelka (0, 90, 180, 270 stopni)",
            },
            "flip_toggle": {
                "label": "Losowe odbicie (Flip)",
                "category": "transforms",
                "widget": self.chk_flip,
                "icon": "flip-horizontal",
                "tooltip": "Losuj odbicie lustrzane kafelka",
            },
            "seed_group": {
                "label": "Ziarno generatora (Seed)",
                "category": "transforms",
                "widget": self.widget_seed,
                "icon": "sparkles",
                "tooltip": "Ziarno generatora losowego (puste = w pełni losowe)",
            },
        }

    def _button_style(self) -> str:
        return """
            QToolButton {
                background: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 2px 7px;
                font-size: 11px;
                font-weight: 500;
            }
            QToolButton:hover {
                background: #3f3f46;
                color: #ffffff;
                border-color: #60a5fa;
            }
            QToolButton:pressed {
                background: #1d4ed8;
                border-color: #2563eb;
            }
            QToolButton:checked {
                background: #2563eb;
                color: #ffffff;
                border: 1px solid #93c5fd;
            }
            QToolButton:checked:hover {
                background: #1d4ed8;
                border-color: #bfdbfe;
            }
            QToolButton:disabled {
                background: #18181b;
                color: #52525b;
                border-color: #27272a;
            }
        """

    def _combo_style(self) -> str:
        return """
            QComboBox {
                background: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #60a5fa;
            }
            QComboBox:disabled {
                background: #18181b;
                color: #52525b;
                border-color: #27272a;
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
            }
            QComboBox QAbstractItemView {
                background: #27272a;
                color: #e4e4e7;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
                border: 1px solid #3f3f46;
            }
        """

    def _input_style(self) -> str:
        return """
            QLineEdit, QSpinBox {
                background: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 2px 4px;
                font-size: 11px;
            }
            QLineEdit:hover, QSpinBox:hover {
                border-color: #60a5fa;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #3b82f6;
            }
        """

    def _on_size_changed(self, val: int) -> None:
        if getattr(self, "active_tool_name", "brush") == "eraser":
            self.settings.eraser_size = val
        else:
            self.settings.size = val
        self.options_changed.emit()

    def _on_autotile_toggled(self, checked: bool) -> None:
        self.settings.auto_tile_enabled = checked
        if hasattr(self, "combo_rules"):
            self.combo_rules.setEnabled(checked)
        self.options_changed.emit()

    def _on_rule_changed(self, idx: int) -> None:
        if not self.autotile_engine or idx < 0:
            return
        rid = self.combo_rules.currentData()
        if rid:
            self.autotile_engine.active_ruleset_id = rid
        self.options_changed.emit()

    def refresh_rulesets(self) -> None:
        if not hasattr(self, "combo_rules") or not self.autotile_engine:
            return
        self.combo_rules.blockSignals(True)
        self.combo_rules.clear()
        active_idx = 0
        for i, (rid, r) in enumerate(self.autotile_engine.rulesets.items()):
            icon = "🛣️" if getattr(r, "is_path_ruleset", False) else "⚡"
            self.combo_rules.addItem(f"{icon} {r.name} ({r.terrain_type})", rid)
            if rid == self.autotile_engine.active_ruleset_id:
                active_idx = i

        if self.combo_rules.count() > 0:
            self.combo_rules.setCurrentIndex(active_idx)
        else:
            self.combo_rules.addItem("(Brak reguł)", "")

        self.combo_rules.blockSignals(False)

    def _on_variants_toggled(self, checked: bool) -> None:
        self.settings.random_variant = checked
        self.options_changed.emit()

    def _on_avoid_toggled(self, checked: bool) -> None:
        self.settings.avoid_adjacent = checked
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
            self.settings.set_seed(int(text.strip()))
        else:
            self.settings.set_seed(None)
        self.options_changed.emit()

    def _add_current_selection_as_variants(self) -> None:
        if not self.asset_manager:
            return
        sel = self.asset_manager.selected_item
        if not sel:
            QMessageBox.information(
                self,
                tr("dialog.randomizer.no_selection_title"),
                tr("dialog.randomizer.select_tiles"),
            )
            return

        count = 0
        if isinstance(sel, SelectedSubTile):
            singles = sel.extract_single_tiles()
            for s in singles:
                self.settings.add_variant(s, weight=10.0)
                count += 1
        else:
            self.settings.add_variant(sel, weight=10.0)
            count += 1

        self.settings.random_variant = True
        self.update_variants_summary()
        self.options_changed.emit()

    def update_variants_summary(self) -> None:
        if hasattr(self, "lbl_variant_count"):
            n = len(self.settings.variants)
            self.lbl_variant_count.setText(f"({n})")
        if hasattr(self, "chk_variants"):
            self.chk_variants.blockSignals(True)
            self.chk_variants.setChecked(self.settings.random_variant)
            self.chk_variants.blockSignals(False)
        if hasattr(self, "chk_avoid"):
            self.chk_avoid.blockSignals(True)
            self.chk_avoid.setChecked(self.settings.avoid_adjacent)
            self.chk_avoid.blockSignals(False)
        if hasattr(self, "txt_seed"):
            self.txt_seed.blockSignals(True)
            if self.settings.seed is not None:
                self.txt_seed.setText(str(self.settings.seed))
            else:
                self.txt_seed.clear()
            self.txt_seed.blockSignals(False)

    def open_autotile_dialog(self) -> None:
        if not self.autotile_engine or not self.asset_manager:
            return
        from .dialogs.autotile_dialog import AutoTileDialog
        dlg = AutoTileDialog(
            autotile_engine=self.autotile_engine,
            asset_manager=self.asset_manager,
            parent=self,
        )
        if dlg.exec():
            self.refresh_rulesets()
            if self.combo_rules.count() > 0:
                self.settings.auto_tile_enabled = True
                self.chk_autotile.setChecked(True)
            self.options_changed.emit()

    def open_path_generator_dialog(self) -> None:
        if not self.autotile_engine or not self.asset_manager:
            return
        dlg = PathGeneratorDialog(
            autotile_engine=self.autotile_engine,
            asset_manager=self.asset_manager,
            parent=self,
        )
        if dlg.exec():
            self.refresh_rulesets()
            if self.combo_rules.count() > 0:
                self.settings.auto_tile_enabled = True
                self.chk_autotile.setChecked(True)
            self.options_changed.emit()

    def open_randomizer_dialog(self) -> None:
        dlg = TileRandomizerDialog(
            brush_settings=self.settings,
            asset_manager=self.asset_manager,
            project=self.project,
            history_manager=self.history_manager,
            parent=self,
        )
        dlg.variants_updated.connect(self.update_variants_summary)
        dlg.variants_updated.connect(self.options_changed.emit)
        dlg.exec()
        self.update_variants_summary()
        self.options_changed.emit()
