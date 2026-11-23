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
    QCheckBox,
    QSpinBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QMessageBox,
)
from PyQt6.QtGui import QColor


class PreferencesDialog(QDialog):
    """
    Central application preferences dialog (TASK-1301).
    Tabs: Appearance, Canvas & Grid, Tools, Keyboard Shortcuts.
    Persists configuration in QSettings.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Ustawienia i Preferencje (Preferences)")
        self.resize(620, 520)
        self.settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        self._init_ui()
        self._load_preferences()

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
        c_layout.addRow("Domyślny rozmiar kafelka:", self.combo_tile_size)

        self.slider_grid_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_grid_opacity.setRange(5, 100)
        self.slider_grid_opacity.setValue(35)
        self.lbl_grid_op = QLabel("35%")
        self.slider_grid_opacity.valueChanged.connect(lambda v: self.lbl_grid_op.setText(f"{v}%"))
        op_box = QHBoxLayout()
        op_box.addWidget(self.slider_grid_opacity)
        op_box.addWidget(self.lbl_grid_op)
        c_layout.addRow("Przezroczystość siatki:", op_box)

        self.chk_show_grid = QCheckBox("Włącz siatkę kafelków na starcie")
        self.chk_show_grid.setChecked(True)
        c_layout.addRow(self.chk_show_grid)

        self.chk_show_hud = QCheckBox("Pokaż pływający wskaźnik HUD współrzędnych")
        self.chk_show_hud.setChecked(True)
        c_layout.addRow(self.chk_show_hud)

        self.chk_checkerboard = QCheckBox("Renderuj szachownicę przezroczystości tła")
        self.chk_checkerboard.setChecked(True)
        c_layout.addRow(self.chk_checkerboard)

        self.tab_widget.addTab(self.tab_canvas, "📐 Siatka i Płótno")

        # Tab 2: Wygląd
        self.tab_appearance = QWidget()
        a_layout = QFormLayout(self.tab_appearance)
        a_layout.setContentsMargins(12, 12, 12, 12)
        a_layout.setSpacing(10)

        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Ciemny profesjonalny (Domyślny)", "Jasny studyjny", "Wysoki kontrast (OLED)"])
        a_layout.addRow("Motyw graficzny:", self.combo_theme)

        self.combo_accent = QComboBox()
        self.combo_accent.addItems(["Błękit królewski (#3b82f6)", "Szmaragd (#10b981)", "Fiolet (#8b5cf6)", "Bursztyn (#f59e0b)"])
        a_layout.addRow("Kolor akcentu interfejsu:", self.combo_accent)

        self.combo_font_size = QComboBox()
        self.combo_font_size.addItems(["Mały (10 pt)", "Standardowy (12 pt)", "Duży (14 pt)"])
        a_layout.addRow("Wielkość czcionki UI:", self.combo_font_size)

        self.tab_widget.addTab(self.tab_appearance, "🎨 Wygląd")

        # Tab 3: Narzędzia
        self.tab_tools = QWidget()
        t_layout = QFormLayout(self.tab_tools)
        t_layout.setContentsMargins(12, 12, 12, 12)
        t_layout.setSpacing(10)

        self.spin_brush_size = QSpinBox()
        self.spin_brush_size.setRange(1, 10)
        self.spin_brush_size.setValue(1)
        t_layout.addRow("Domyślny rozmiar pędzla:", self.spin_brush_size)

        self.combo_rot_step = QComboBox()
        self.combo_rot_step.addItems(["90°", "45°", "15°"])
        t_layout.addRow("Krok obrotu obiektów (klawisz R):", self.combo_rot_step)

        self.chk_snap_default = QCheckBox("Domyślnie przyciągaj obiekty do siatki (Snap)")
        self.chk_snap_default.setChecked(False)
        t_layout.addRow(self.chk_snap_default)

        self.combo_autosave = QComboBox()
        self.combo_autosave.addItems(["Co 1 minutę", "Co 3 minuty (Zalecane)", "Co 5 minut", "Co 10 minut", "Wyłączony"])
        self.combo_autosave.setCurrentIndex(1)
        t_layout.addRow("Częstotliwość autozapisu:", self.combo_autosave)

        self.tab_widget.addTab(self.tab_tools, "🛠️ Narzędzia")

        # Tab 4: Skróty klawiszowe
        self.tab_shortcuts = QWidget()
        s_layout = QVBoxLayout(self.tab_shortcuts)
        s_layout.setContentsMargins(8, 8, 8, 8)
        s_layout.setSpacing(6)

        self.filter_shortcuts = QLineEdit()
        self.filter_shortcuts.setPlaceholderText("Filtruj skróty klawiszowe...")
        self.filter_shortcuts.textChanged.connect(self._filter_shortcuts_table)
        s_layout.addWidget(self.filter_shortcuts)

        self.table_shortcuts = QTableWidget()
        self.table_shortcuts.setColumnCount(2)
        self.table_shortcuts.setHorizontalHeaderLabels(["Narzędzie / Działanie", "Skrót klawiszowy"])
        self.table_shortcuts.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_shortcuts.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        s_layout.addWidget(self.table_shortcuts)

        self._populate_shortcuts_table()
        self.tab_widget.addTab(self.tab_shortcuts, "⌨️ Skróty klawiszowe")

        main_layout.addWidget(self.tab_widget)

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_save = QPushButton("💾 Zapisz i Zastosuj")
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

        btn_cancel = QPushButton("Anuluj")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        main_layout.addLayout(btn_layout)

    def _populate_shortcuts_table(self) -> None:
        shortcuts = [
            ("Pędzel", "B"),
            ("Gumka", "E"),
            ("Wypełnianie", "G"),
            ("Różdżka", "W"),
            ("Zaznaczanie", "S"),
            ("Swobodny obiekt", "V"),
            ("Pipeta", "I"),
            ("Linia", "L"),
            ("Prostokąt", "U"),
            ("Stempel", "T"),
            ("Szybkie menu (Radial)", "Q"),
            ("Cofnij operację", "Ctrl+Z"),
            ("Ponów operację", "Ctrl+Y"),
            ("Kopiuj zaznaczenie", "Ctrl+C"),
            ("Wklej stempel", "Ctrl+V"),
            ("Usuń zaznaczenie", "Delete"),
            ("Pełny obszar roboczy", "F11"),
            ("Zapisz projekt", "Ctrl+S"),
            ("Otwórz projekt", "Ctrl+O"),
            ("Eksport PNG", "Ctrl+E"),
        ]
        self.table_shortcuts.setRowCount(len(shortcuts))
        for r, (action, key) in enumerate(shortcuts):
            it_act = QTableWidgetItem(action)
            it_act.setFlags(it_act.flags() & ~Qt.ItemFlag.ItemIsEditable)
            it_key = QTableWidgetItem(key)
            self.table_shortcuts.setItem(r, 0, it_act)
            self.table_shortcuts.setItem(r, 1, it_key)

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

    def _save_and_accept(self) -> None:
        # Detect shortcut duplicates
        used_shortcuts: Dict[str, str] = {}
        for r in range(self.table_shortcuts.rowCount()):
            act = self.table_shortcuts.item(r, 0).text()
            key = self.table_shortcuts.item(r, 1).text().strip().upper()
            if key in used_shortcuts:
                QMessageBox.warning(
                    self,
                    "Konflikt skrótów",
                    f"Skrót '{key}' jest przypisany zarówno do '{used_shortcuts[key]}' jak i '{act}'.\nPopraw konflikt przed zapisaniem.",
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
        self.settings.setValue("rot_step_idx", self.combo_rot_step.currentIndex())
        self.settings.setValue("snap_default", self.chk_snap_default.isChecked())
        self.settings.setValue("autosave_interval_idx", self.combo_autosave.currentIndex())

        self.accept()
