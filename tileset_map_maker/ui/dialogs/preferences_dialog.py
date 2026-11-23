from typing import Optional, Dict
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QDialog,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QSlider,
    QSpinBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QApplication,
)
from PyQt6.QtGui import QColor

from ...core.config_manager import ConfigManager
from ...core.localization import get_localization, tr
from ..widgets.switch_toggle import SwitchToggle
from ..icons import IconFactory
from ..styles import apply_application_theme


class PreferencesDialog(QDialog):
    """
    Central application preferences dialog (TASK-1301).
    Tabs: Appearance, Canvas & Grid, Tools, Keyboard Shortcuts.
    Persists configuration in QSettings.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.resize(650, 550)
        self.settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        self.config_manager = ConfigManager()
        self._init_ui()
        self._load_preferences()
        get_localization().languageChanged.connect(self._apply_language)

    def _apply_language(self, language: str) -> None:
        self.setWindowTitle(tr("settings.title"))
        self.tab_widget.setTabText(0, tr("tab.canvas"))
        self.tab_widget.setTabText(1, tr("tab.appearance"))
        self.tab_widget.setTabText(2, tr("tab.tools"))
        self.tab_widget.setTabText(3, tr("tab.import"))
        self.tab_widget.setTabText(4, tr("tab.shortcuts"))
        self.combo_language.blockSignals(True)
        self.combo_language.setItemText(0, tr("language.english"))
        self.combo_language.setItemText(1, tr("language.polish"))
        self.combo_language.setCurrentIndex(0 if get_localization().get_language() == "en" else 1)
        self.combo_language.blockSignals(False)
        self._retranslate_controls()
        self.table_shortcuts.setHorizontalHeaderLabels(
            [tr("dialog.shortcuts.tool_action"), tr("dialog.shortcuts.shortcut")]
        )
        for row in range(self.table_shortcuts.rowCount()):
            item = self.table_shortcuts.item(row, 0)
            if item:
                action_key = item.data(Qt.ItemDataRole.UserRole)
                item.setText(tr(f"dialog.shortcuts.{action_key}"))

    def _retranslate_controls(self) -> None:
        self.combo_tile_size.setItemText(0, "16x16")
        self.lbl_grid_op.setText(f"{self.slider_grid_opacity.value()}%")
        self.setWindowTitle(tr("settings.title"))
        self.tab_widget.setTabText(0, tr("tab.canvas"))
        self.tab_widget.setTabText(1, tr("tab.appearance"))
        self.tab_widget.setTabText(2, tr("tab.tools"))
        self.tab_widget.setTabText(3, tr("tab.import"))
        self.tab_widget.setTabText(4, tr("tab.shortcuts"))
        self.chk_show_grid.setText(tr("settings.show_grid"))
        self.chk_show_hud.setText(tr("settings.show_hud"))
        self.chk_checkerboard.setText(tr("settings.checkerboard"))
        self.combo_theme.setItemText(0, tr("theme.dark"))
        self.combo_theme.setItemText(1, tr("theme.light"))
        self.combo_theme.setItemText(2, tr("theme.contrast"))
        self.combo_theme.setItemText(3, tr("theme.forest"))
        self.combo_accent.setItemText(0, tr("accent.blue"))
        self.combo_accent.setItemText(1, tr("accent.emerald"))
        self.combo_accent.setItemText(2, tr("accent.violet"))
        self.combo_accent.setItemText(3, tr("accent.amber"))
        self.combo_font_size.setItemText(0, tr("font.small"))
        self.combo_font_size.setItemText(1, tr("font.standard"))
        self.combo_font_size.setItemText(2, tr("font.large"))
        self.chk_snap_default.setText(tr("settings.snap"))
        self.spin_brush_size.setToolTip(tr("settings.brush_size"))
        self.combo_autosave.setItemText(0, tr("autosave.minute"))
        self.combo_autosave.setItemText(1, tr("autosave.three"))
        self.combo_autosave.setItemText(2, tr("autosave.five"))
        self.combo_autosave.setItemText(3, tr("autosave.ten"))
        self.combo_autosave.setItemText(4, tr("autosave.off"))

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self.tab_widget = QTabWidget(self)

        # Tab 1: Siatka i Płótno
        self.tab_canvas = QWidget()
        c_layout = QFormLayout(self.tab_canvas)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.setSpacing(10)

        self.combo_tile_size = QComboBox()
        self.combo_tile_size.addItems(["16x16", "24x24", "32x32", "48x48", "64x64"])
        c_layout.addRow(tr("settings.tile_size"), self.combo_tile_size)

        self.slider_grid_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_grid_opacity.setRange(5, 100)
        self.slider_grid_opacity.setValue(35)
        self.lbl_grid_op = QLabel("35%")
        self.slider_grid_opacity.valueChanged.connect(lambda v: self.lbl_grid_op.setText(f"{v}%"))
        op_box = QHBoxLayout()
        op_box.addWidget(self.slider_grid_opacity)
        op_box.addWidget(self.lbl_grid_op)
        c_layout.addRow(tr("settings.grid_opacity"), op_box)

        self.chk_show_grid = SwitchToggle(tr("settings.show_grid"), checked=True)
        c_layout.addRow(self.chk_show_grid)

        self.chk_show_hud = SwitchToggle(tr("settings.show_hud"), checked=True)
        c_layout.addRow(self.chk_show_hud)

        self.chk_checkerboard = SwitchToggle(tr("settings.checkerboard"), checked=True)
        c_layout.addRow(self.chk_checkerboard)

        self.tab_widget.addTab(self.tab_canvas, IconFactory.get_icon("grid", 16), tr("tab.canvas"))

        # Tab 2: Wygląd
        self.tab_appearance = QWidget()
        a_layout = QFormLayout(self.tab_appearance)
        a_layout.setContentsMargins(12, 12, 12, 12)
        a_layout.setSpacing(10)

        self.combo_theme = QComboBox()
        self.combo_theme.addItems([
            tr("theme.dark"), tr("theme.light"), tr("theme.contrast"), tr("theme.forest")
        ])
        a_layout.addRow(tr("settings.theme"), self.combo_theme)

        self.combo_accent = QComboBox()
        self.combo_accent.addItems([tr("accent.blue"), tr("accent.emerald"), tr("accent.violet"), tr("accent.amber")])
        a_layout.addRow(tr("settings.accent"), self.combo_accent)

        self.combo_font_size = QComboBox()
        self.combo_font_size.addItems([tr("font.small"), tr("font.standard"), tr("font.large")])
        a_layout.addRow(tr("settings.font_size"), self.combo_font_size)

        # Language is intentionally located in Appearance, as requested.
        self.combo_language = QComboBox()
        self.combo_language.addItem(tr("language.english"), "en")
        self.combo_language.addItem(tr("language.polish"), "pl")
        current = get_localization().get_language()
        self.combo_language.setCurrentIndex(0 if current == "en" else 1)
        self.combo_language.currentIndexChanged.connect(
            lambda: get_localization().set_language(self.combo_language.currentData())
        )
        a_layout.addRow(tr("settings.language"), self.combo_language)
        a_layout.addRow("", QLabel(tr("settings.immediate")))

        self.tab_widget.addTab(self.tab_appearance, IconFactory.get_icon("palette", 16), tr("tab.appearance"))

        # Tab 3: Narzędzia
        self.tab_tools = QWidget()
        t_layout = QFormLayout(self.tab_tools)
        t_layout.setContentsMargins(12, 12, 12, 12)
        t_layout.setSpacing(10)

        self.spin_brush_size = QSpinBox()
        self.spin_brush_size.setRange(1, 10)
        self.spin_brush_size.setValue(1)
        t_layout.addRow(tr("settings.brush_size"), self.spin_brush_size)

        self.combo_rot_step = QComboBox()
        self.combo_rot_step.addItems(["90°", "45°", "15°"])
        t_layout.addRow(tr("settings.rotation"), self.combo_rot_step)

        self.chk_snap_default = SwitchToggle(tr("settings.snap"), checked=False)
        t_layout.addRow(self.chk_snap_default)

        self.combo_autosave = QComboBox()
        self.combo_autosave.addItems([
            tr("autosave.minute"), tr("autosave.three"), tr("autosave.five"),
            tr("autosave.ten"), tr("autosave.off"),
        ])
        self.combo_autosave.setCurrentIndex(1)
        t_layout.addRow(tr("settings.autosave"), self.combo_autosave)

        self.tab_widget.addTab(self.tab_tools, IconFactory.get_icon("brush", 16), tr("tab.tools"))

        # Tab 4: Domyślne parametry importu tilesetów
        self.tab_import = QWidget()
        i_layout = QFormLayout(self.tab_import)
        i_layout.setContentsMargins(12, 12, 12, 12)
        i_layout.setSpacing(10)

        self.spin_imp_width = QSpinBox()
        self.spin_imp_width.setRange(4, 512)
        self.spin_imp_width.setValue(32)
        i_layout.addRow(tr("settings.import_width"), self.spin_imp_width)

        self.spin_imp_height = QSpinBox()
        self.spin_imp_height.setRange(4, 512)
        self.spin_imp_height.setValue(32)
        i_layout.addRow(tr("settings.import_height"), self.spin_imp_height)

        # Quick preset buttons
        preset_box = QHBoxLayout()
        for w, h in [(16, 16), (24, 24), (32, 32), (32, 48), (48, 48), (64, 64)]:
            btn = QPushButton(f"{w}x{h}")
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda _, pw=w, ph=h: self._set_import_dims(pw, ph))
            preset_box.addWidget(btn)
        i_layout.addRow(tr("settings.import_presets"), preset_box)

        self.spin_imp_margin_x = QSpinBox()
        self.spin_imp_margin_x.setRange(0, 128)
        self.spin_imp_margin_x.setValue(0)
        i_layout.addRow(tr("settings.margin_x"), self.spin_imp_margin_x)

        self.spin_imp_margin_y = QSpinBox()
        self.spin_imp_margin_y.setRange(0, 128)
        self.spin_imp_margin_y.setValue(0)
        i_layout.addRow(tr("settings.margin_y"), self.spin_imp_margin_y)

        self.spin_imp_spacing_x = QSpinBox()
        self.spin_imp_spacing_x.setRange(0, 64)
        self.spin_imp_spacing_x.setValue(0)
        i_layout.addRow(tr("settings.spacing_x"), self.spin_imp_spacing_x)

        self.spin_imp_spacing_y = QSpinBox()
        self.spin_imp_spacing_y.setRange(0, 64)
        self.spin_imp_spacing_y.setValue(0)
        i_layout.addRow(tr("settings.spacing_y"), self.spin_imp_spacing_y)

        self.chk_imp_skip_single = SwitchToggle(tr("settings.skip_import"), checked=False)
        i_layout.addRow(self.chk_imp_skip_single)

        self.tab_widget.addTab(self.tab_import, IconFactory.get_icon("download", 16), tr("tab.import"))

        # Tab 5: Skróty klawiszowe
        self.tab_shortcuts = QWidget()
        s_layout = QVBoxLayout(self.tab_shortcuts)
        s_layout.setContentsMargins(8, 8, 8, 8)
        s_layout.setSpacing(6)

        self.filter_shortcuts = QLineEdit()
        self.filter_shortcuts.setPlaceholderText(tr("dialog.shortcuts.filter"))
        self.filter_shortcuts.textChanged.connect(self._filter_shortcuts_table)
        s_layout.addWidget(self.filter_shortcuts)

        self.table_shortcuts = QTableWidget()
        self.table_shortcuts.setColumnCount(2)
        self.table_shortcuts.setHorizontalHeaderLabels(
            [tr("dialog.shortcuts.tool_action"), tr("dialog.shortcuts.shortcut")]
        )
        self.table_shortcuts.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_shortcuts.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        s_layout.addWidget(self.table_shortcuts)

        self._populate_shortcuts_table()
        self.tab_widget.addTab(
            self.tab_shortcuts, IconFactory.get_icon("shortcuts", 16), tr("tab.shortcuts")
        )

        main_layout.addWidget(self.tab_widget)

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_save = QPushButton(f" {tr('dialog.shortcuts.save_apply')}")
        btn_save.setIcon(IconFactory.get_icon("save", 16))
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: 600;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        btn_save.clicked.connect(self._save_and_accept)
        btn_layout.addWidget(btn_save)

        btn_cancel = QPushButton(f" {tr('button.cancel')}")
        btn_cancel.setIcon(IconFactory.get_icon("close", 14))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        main_layout.addLayout(btn_layout)

    def _populate_shortcuts_table(self) -> None:
        shortcuts = [
            ("brush", "B"),
            ("eraser", "E"),
            ("fill", "G"),
            ("wand", "W"),
            ("selection", "S"),
            ("free_object", "V"),
            ("eyedropper", "I"),
            ("line", "L"),
            ("rectangle", "U"),
            ("stamp", "T"),
            ("radial", "Q"),
            ("undo", "Ctrl+Z"),
            ("redo", "Ctrl+Y"),
            ("copy", "Ctrl+C"),
            ("paste_stamp", "Ctrl+V"),
            ("delete", "Delete"),
            ("fullscreen", "F11"),
            ("save_project", "Ctrl+S"),
            ("open_project", "Ctrl+O"),
            ("export", "Ctrl+E"),
        ]
        self.table_shortcuts.setRowCount(len(shortcuts))
        for r, (action_key, key) in enumerate(shortcuts):
            it_act = QTableWidgetItem(tr(f"dialog.shortcuts.{action_key}"))
            it_act.setFlags(it_act.flags() & ~Qt.ItemFlag.ItemIsEditable)
            it_act.setData(Qt.ItemDataRole.UserRole, action_key)
            it_key = QTableWidgetItem(key)
            self.table_shortcuts.setItem(r, 0, it_act)
            self.table_shortcuts.setItem(r, 1, it_key)

    def _set_import_dims(self, w: int, h: int) -> None:
        self.spin_imp_width.setValue(w)
        self.spin_imp_height.setValue(h)

    def _filter_shortcuts_table(self, query: str) -> None:
        q = query.strip().lower()
        for r in range(self.table_shortcuts.rowCount()):
            act = self.table_shortcuts.item(r, 0).text().lower()
            key = self.table_shortcuts.item(r, 1).text().lower()
            visible = (q in act) or (q in key)
            self.table_shortcuts.setRowHidden(r, not visible)

    def _load_preferences(self) -> None:
        ts_idx = self.settings.value("default_tile_size_idx", 2, type=int)
        self.combo_tile_size.setCurrentIndex(ts_idx)

        op = self.settings.value("grid_opacity", 35, type=int)
        self.slider_grid_opacity.setValue(op)

        self.chk_show_grid.setChecked(self.settings.value("show_grid", True, type=bool))
        self.chk_show_hud.setChecked(self.settings.value("show_hud", True, type=bool))
        self.chk_checkerboard.setChecked(self.settings.value("render_checkerboard", True, type=bool))

        th_idx = self.settings.value("theme_idx", 0, type=int)
        self.combo_theme.setCurrentIndex(th_idx)

        rot_idx = self.settings.value("rot_step_idx", 0, type=int)
        self.combo_rot_step.setCurrentIndex(rot_idx)

        self.chk_snap_default.setChecked(self.settings.value("snap_default", False, type=bool))

        as_idx = self.settings.value("autosave_interval_idx", 1, type=int)
        self.combo_autosave.setCurrentIndex(as_idx)

        # Load Global Import Settings
        imp_cfg = self.config_manager.get_import_settings()
        self.spin_imp_width.setValue(imp_cfg.get("default_tile_width", 32))
        self.spin_imp_height.setValue(imp_cfg.get("default_tile_height", 32))
        self.spin_imp_margin_x.setValue(imp_cfg.get("default_margin_x", 0))
        self.spin_imp_margin_y.setValue(imp_cfg.get("default_margin_y", 0))
        self.spin_imp_spacing_x.setValue(imp_cfg.get("default_spacing_x", 0))
        self.spin_imp_spacing_y.setValue(imp_cfg.get("default_spacing_y", 0))
        self.chk_imp_skip_single.setChecked(imp_cfg.get("skip_dialog_on_single", False))

    def _save_and_accept(self) -> None:
        # Detect shortcut duplicates
        used_shortcuts: Dict[str, str] = {}
        for r in range(self.table_shortcuts.rowCount()):
            act = self.table_shortcuts.item(r, 0).text()
            key = self.table_shortcuts.item(r, 1).text().strip().upper()
            if key in used_shortcuts:
                QMessageBox.warning(
                    self,
                    tr("dialog.shortcuts.conflict_title"),
                    tr(
                        "dialog.shortcuts.conflict",
                        key=key,
                        first=used_shortcuts[key],
                        second=act,
                    ),
                )
                return
            if key:
                used_shortcuts[key] = act

        self.settings.setValue("default_tile_size_idx", self.combo_tile_size.currentIndex())
        self.settings.setValue("grid_opacity", self.slider_grid_opacity.value())
        self.settings.setValue("show_grid", self.chk_show_grid.isChecked())
        self.settings.setValue("show_hud", self.chk_show_hud.isChecked())
        self.settings.setValue("render_checkerboard", self.chk_checkerboard.isChecked())
        self.settings.setValue("theme_idx", self.combo_theme.currentIndex())
        app = QApplication.instance()
        if app is not None:
            apply_application_theme(app, self.combo_theme.currentIndex())
        self.settings.setValue("rot_step_idx", self.combo_rot_step.currentIndex())
        self.settings.setValue("snap_default", self.chk_snap_default.isChecked())
        self.settings.setValue("autosave_interval_idx", self.combo_autosave.currentIndex())

        language = self.combo_language.currentData()
        if language in ("en", "pl"):
            get_localization().set_language(language)

        # Save Global Import Settings
        self.config_manager.set_import_settings(
            tile_width=self.spin_imp_width.value(),
            tile_height=self.spin_imp_height.value(),
            margin_x=self.spin_imp_margin_x.value(),
            margin_y=self.spin_imp_margin_y.value(),
            spacing_x=self.spin_imp_spacing_x.value(),
            spacing_y=self.spin_imp_spacing_y.value(),
            skip_dialog_on_single=self.chk_imp_skip_single.isChecked(),
        )

        self.accept()
