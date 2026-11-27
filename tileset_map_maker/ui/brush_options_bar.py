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
from ..models.brush_preset import BrushSettings, can_rotate_selection_90
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
        self.update_variants_summary()
        get_localization().languageChanged.connect(self._apply_language)

    def _apply_language(self, _language: str) -> None:
        if hasattr(self, "lbl_size"):
            self.set_active_tool(self.active_tool_name)
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
        if hasattr(self, "btn_rot"):
            self._update_rot_button()
            self.btn_rot.setToolTip(tr("brush.rotation_tooltip"))
        if hasattr(self, "chk_flip_h"):
            self.chk_flip_h.setText(tr("brush.flip_h"))
            self.chk_flip_h.setToolTip(tr("brush.flip_h_tooltip"))
        if hasattr(self, "chk_flip_v"):
            self.chk_flip_v.setText(tr("brush.flip_v"))
            self.chk_flip_v.setToolTip(tr("brush.flip_v_tooltip"))
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

        # 2. Generator Ścieżek (Paths)
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

        # 4. Trzy niezależne przyciski transformacji: Mirror Horizontal, Mirror Vertical, Rotation 90° (R) + Seed
        self.chk_flip_h = ToolbarToggleButton(
            tr("brush.flip_h"),
            checked=self.settings.flip_horizontal,
            icon_name="flip-horizontal",
        )
        self.chk_flip_h.setToolTip(tr("brush.flip_h_tooltip"))
        self.chk_flip_h.toggled.connect(self._on_flip_h_toggled)
        self.chk_flip = self.chk_flip_h  # Backward-compatible alias
        layout.addWidget(self.chk_flip_h)

        self.chk_flip_v = ToolbarToggleButton(
            tr("brush.flip_v"),
            checked=self.settings.flip_vertical,
            icon_name="flip-vertical",
        )
        self.chk_flip_v.setToolTip(tr("brush.flip_v_tooltip"))
        self.chk_flip_v.toggled.connect(self._on_flip_v_toggled)
        layout.addWidget(self.chk_flip_v)

        self.btn_rot = QToolButton()
        self.btn_rot.setIcon(IconFactory.get_icon("rotate", 14))
        self.btn_rot.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_rot.setToolTip(tr("brush.rotation_tooltip"))
        self.btn_rot.setFixedHeight(26)
        self.btn_rot.clicked.connect(lambda: self.rotate_brush(clockwise=True))
        self.chk_rot = self.btn_rot  # Backward-compatible alias
        self._update_rot_button()
        layout.addWidget(self.btn_rot)

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
                "label": tr("toolbar.item.brush_size"),
                "category": "brush",
                "widget": self.widget_brush_size,
                "icon": "brush",
                "tooltip": tr("brush.size_tooltip"),
            },
            "path_gen_dialog": {
                "label": tr("toolbar.item.path_gen_dialog"),
                "category": "paths",
                "widget": self.btn_path_gen,
                "icon": "path",
                "tooltip": tr("brush.path_tooltip"),
            },
            "variants_toggle": {
                "label": tr("toolbar.item.variants_toggle"),
                "category": "randomizer",
                "widget": self.chk_variants,
                "icon": "randomizer",
                "tooltip": tr("brush.variant_tooltip"),
            },
            "variants_count": {
                "label": tr("toolbar.item.variants_count"),
                "category": "randomizer",
                "widget": self.lbl_variant_count,
                "icon": "randomizer",
                "tooltip": tr("brush.variant_count_tooltip"),
            },
            "variants_add": {
                "label": tr("toolbar.item.variants_add"),
                "category": "randomizer",
                "widget": self.btn_add_selection_variants,
                "icon": "plus",
                "tooltip": tr("brush.add_selection_tooltip"),
            },
            "variants_avoid": {
                "label": tr("toolbar.item.variants_avoid"),
                "category": "randomizer",
                "widget": self.chk_avoid,
                "icon": "sparkles",
                "tooltip": tr("brush.avoid_tooltip"),
            },
            "variants_dialog": {
                "label": tr("toolbar.item.variants_dialog"),
                "category": "randomizer",
                "widget": self.btn_randomizer,
                "icon": "randomizer",
                "tooltip": tr("brush.randomizer_tooltip"),
            },
            "flip_toggle": {
                "label": tr("toolbar.item.flip_toggle"),
                "category": "transforms",
                "widget": self.chk_flip_h,
                "icon": "flip-horizontal",
                "tooltip": tr("brush.flip_h_tooltip"),
            },
            "flip_v_toggle": {
                "label": tr("toolbar.item.flip_v_toggle"),
                "category": "transforms",
                "widget": self.chk_flip_v,
                "icon": "flip-vertical",
                "tooltip": tr("brush.flip_v_tooltip"),
            },
            "rot_toggle": {
                "label": tr("toolbar.item.rot_toggle"),
                "category": "transforms",
                "widget": self.btn_rot,
                "icon": "rotate",
                "tooltip": tr("brush.rotation_tooltip"),
            },
            "seed_group": {
                "label": tr("toolbar.item.seed_group"),
                "category": "transforms",
                "widget": self.widget_seed,
                "icon": "sparkles",
                "tooltip": tr("brush.seed_tooltip"),
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

    def _on_variants_toggled(self, checked: bool) -> None:
        self.settings.random_variant = checked
        self.options_changed.emit()

    def _on_avoid_toggled(self, checked: bool) -> None:
        self.settings.avoid_adjacent = checked
        self.options_changed.emit()

    def _update_rot_button(self) -> None:
        if not hasattr(self, "btn_rot"):
            return
        angle = int(self.settings.rotation) % 360
        self.btn_rot.setText(f" {tr('brush.rotation')} {angle}°")
        if angle != 0:
            self.btn_rot.setStyleSheet("""
                QToolButton {
                    background: #2563eb;
                    color: #ffffff;
                    border: 1px solid #3b82f6;
                    border-radius: 4px;
                    padding: 2px 7px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QToolButton:hover {
                    background: #1d4ed8;
                    border-color: #60a5fa;
                }
            """)
        else:
            self.btn_rot.setStyleSheet(self._button_style())

    def rotate_brush(self, clockwise: bool = True) -> bool:
        """Rotates the active brush orientation by 90° CW (R) or CCW (Shift+R)."""
        sel = self.asset_manager.selected_item if self.asset_manager else None
        ok, tw, th = can_rotate_selection_90(sel)
        if not ok:
            msg = tr("brush.rotation_blocked_nonsquare", w=tw, h=th)
            win = self.window()
            if hasattr(win, "notification_banner") and win.notification_banner is not None:
                win.notification_banner.show_message(msg, "warning")
            elif hasattr(win, "statusBar") and win.statusBar() is not None:
                win.statusBar().showMessage(msg, 3500)
            return False
        if clockwise:
            self.settings.rotate_cw()
        else:
            self.settings.rotate_ccw()
        self.sync_transform_buttons()
        self.options_changed.emit()
        return True

    def _on_flip_h_toggled(self, checked: bool) -> None:
        self.settings.set_flip_horizontal(checked)
        self.sync_transform_buttons()
        self.options_changed.emit()

    def _on_flip_v_toggled(self, checked: bool) -> None:
        self.settings.set_flip_vertical(checked)
        self.sync_transform_buttons()
        self.options_changed.emit()

    def sync_transform_buttons(self) -> None:
        """Synchronizes Rotate angle label and Flip H / Flip V button states with BrushSettings."""
        self._update_rot_button()
        if hasattr(self, "chk_flip_h"):
            self.chk_flip_h.blockSignals(True)
            self.chk_flip_h.setChecked(self.settings.flip_horizontal)
            self.chk_flip_h.blockSignals(False)
        if hasattr(self, "chk_flip_v"):
            self.chk_flip_v.blockSignals(True)
            self.chk_flip_v.setChecked(self.settings.flip_vertical)
            self.chk_flip_v.blockSignals(False)

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
        self.sync_transform_buttons()

    def open_path_generator_dialog(self) -> None:
        win = self.window()
        if hasattr(win, "open_path_generator_dialog") and win is not self:
            win.open_path_generator_dialog()
            return

        if not self.autotile_engine or not self.asset_manager:
            return
        dlg = PathGeneratorDialog(
            autotile_engine=self.autotile_engine,
            asset_manager=self.asset_manager,
            parent=self,
        )
        if dlg.exec():
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
