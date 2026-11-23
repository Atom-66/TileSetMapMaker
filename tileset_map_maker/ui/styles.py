"""
Modern Dark Theme QSS and UI Styles.
Inspired by Godot Editor, Aseprite, and professional digital content creation tools.
"""

import re

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QApplication, QWidget

DARK_THEME_QSS = """
QMainWindow {
    background-color: #121316;
    color: #e4e4e7;
}

QWidget {
    background-color: #18191d;
    color: #e4e4e7;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
}

/* Toolbars */
QToolBar {
    background-color: #1c1d22;
    border-bottom: 1px solid #27272f;
    padding: 4px 8px;
    spacing: 6px;
}

QToolButton {
    background-color: transparent;
    color: #d4d4d8;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 500;
}

QToolButton:hover {
    background-color: #2b2c34;
    border: 1px solid #3f404d;
    color: #ffffff;
}

QToolButton:pressed {
    background-color: #1d4ed8;
    border: 1px solid #2563eb;
    color: #ffffff;
}

QToolButton:checked {
    background-color: #2563eb;
    border: 1px solid #93c5fd;
    color: #ffffff;
}

QToolButton:checked:hover {
    background-color: #1d4ed8;
    border: 1px solid #bfdbfe;
    color: #ffffff;
}

/* Menus */
QMenuBar {
    background-color: #18191d;
    border-bottom: 1px solid #27272f;
    padding: 2px 4px;
}

QMenuBar::item {
    background-color: transparent;
    padding: 6px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #27272f;
}

QMenu {
    background-color: #1f2026;
    border: 1px solid #32333d;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #3b82f6;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #2e2f38;
    margin: 4px 6px;
}

/* Status Bar */
QStatusBar {
    background-color: #141518;
    border-top: 1px solid #23242a;
    color: #a1a1aa;
    font-size: 12px;
}

QStatusBar QLabel {
    background: transparent;
    padding: 2px 8px;
}

/* Dock Widgets & Panels (Photoshop / Professional Studio Style) */
QDockWidget {
    color: #e4e4e7;
    font-weight: 600;
    border: 1px solid #282932;
    border-radius: 4px;
}

QDockWidget::title {
    background-color: #1e1f26;
    border-bottom: 1px solid #2d2e38;
    padding: 6px 10px;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-weight: 600;
    color: #e4e4e7;
}

QDockWidget::title:hover {
    background-color: #272834;
}

QDockWidget::close-button, QDockWidget::float-button {
    background: transparent;
    border: none;
    border-radius: 3px;
    padding: 2px;
    subcontrol-position: top right;
}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background: #373847;
}

QDockWidget::close-button {
    subcontrol-origin: margin;
    right: 4px;
}

QDockWidget::float-button {
    subcontrol-origin: margin;
    right: 22px;
}

/* RubberBand (Photoshop / Tiled style docking target preview) */
QRubberBand {
    background-color: rgba(59, 130, 246, 85);
    border: 2px solid #3b82f6;
    border-radius: 4px;
}

/* Main Window Dock Separators */
QMainWindow::separator {
    background-color: #1c1d22;
    width: 6px;
    height: 6px;
}

QMainWindow::separator:hover {
    background-color: #3b82f6;
}

/* Docked Tab Bars (Photoshop Style Tabs at the Top of Dock Groups) */
QMainWindow > QTabBar, QDockWidget QTabBar {
    background-color: #141519;
    border-bottom: 1px solid #27272f;
    padding-top: 2px;
}

QMainWindow > QTabBar::tab, QDockWidget QTabBar::tab {
    background-color: #1a1b22;
    border: 1px solid #2a2b36;
    border-bottom: 2px solid transparent;
    padding: 5px 12px;
    margin-right: 2px;
    font-size: 11px;
    font-weight: 500;
    color: #a1a1aa;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QMainWindow > QTabBar::tab:hover, QDockWidget QTabBar::tab:hover {
    background-color: #242530;
    color: #ffffff;
}

QMainWindow > QTabBar::tab:selected, QDockWidget QTabBar::tab:selected {
    background-color: #1e1f28;
    color: #ffffff;
    font-weight: 600;
    border-bottom: 2px solid #3b82f6;
}

/* Push Buttons */
QPushButton {
    background-color: #272831;
    color: #e4e4e7;
    border: 1px solid #373844;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #323440;
    border-color: #484a5a;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #202128;
    border-color: #373844;
}

QPushButton:disabled {
    background-color: #1a1a20;
    color: #52525b;
    border-color: #23242a;
}

QPushButton.primary {
    background-color: #3b82f6;
    color: #ffffff;
    border: 1px solid #2563eb;
}

QPushButton.primary:hover {
    background-color: #60a5fa;
    border-color: #3b82f6;
}

/* Inputs and LineEdits */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #141518;
    border: 1px solid #2e2f38;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f4f4f5;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
    background-color: #18191e;
}

/* Trees and Lists */
QTreeWidget, QListWidget, QTableView {
    background-color: #16171b;
    border: 1px solid #27272f;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}

QTreeWidget::item, QListWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
}

QTreeWidget::item:hover, QListWidget::item:hover {
    background-color: #22232a;
}

QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #2b3954;
    color: #93c5fd;
}

/* Scrollbars */
QScrollBar:vertical {
    background-color: #141518;
    width: 10px;
    border-radius: 5px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #2f303b;
    border-radius: 5px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background-color: #434453;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #141518;
    height: 10px;
    border-radius: 5px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #2f303b;
    border-radius: 5px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #434453;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #27272f;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #3b82f6;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #3b82f6;
    width: 14px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 7px;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #27272f;
    background-color: #18191d;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #16171a;
    border: 1px solid #27272f;
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #a1a1aa;
}

QTabBar::tab:selected {
    background-color: #1e1f25;
    color: #ffffff;
    font-weight: 600;
}

/* Splitter */
QSplitter::handle {
    background-color: #1c1d22;
}

QSplitter::handle:hover {
    background-color: #3b82f6;
}
"""

HIGH_CONTRAST_THEME_COLORS = {
    "#121316": "#000000",
    "#18191d": "#050505",
    "#e4e4e7": "#ffffff",
    "#3b82f6": "#00e5ff",
    "#1c1d22": "#080808",
    "#27272f": "#1a1a1a",
    "#d4d4d8": "#ffffff",
    "#2b2c34": "#181818",
    "#3f404d": "#666666",
    "#1d4ed8": "#0057ff",
    "#2563eb": "#0057ff",
    "#bfdbfe": "#aefcff",
    "#1f2026": "#0b0b0b",
    "#32333d": "#555555",
    "#2e2f38": "#333333",
    "#141518": "#000000",
    "#23242a": "#292929",
    "#a1a1aa": "#e6e6e6",
    "#282932": "#555555",
    "#1e1f26": "#0d0d0d",
    "#2d2e38": "#4a4a4a",
    "#272834": "#1c1c1c",
    "#373847": "#333333",
    "rgba(59, 130, 246, 85)": "rgba(0, 229, 255, 100)",
    "#141519": "#000000",
    "#1a1b22": "#0a0a0a",
    "#2a2b36": "#444444",
    "#242530": "#191919",
    "#1e1f28": "#111111",
    "#272831": "#141414",
    "#373844": "#555555",
    "#323440": "#202020",
    "#484a5a": "#777777",
    "#202128": "#090909",
    "#1a1a20": "#030303",
    "#52525b": "#cccccc",
    "#60a5fa": "#33aaff",
    "#f4f4f5": "#ffffff",
    "#18191e": "#0a0a0a",
    "#16171b": "#050505",
    "#22232a": "#181818",
    "#2b3954": "#003b4a",
    "#2f303b": "#444444",
    "#434453": "#777777",
    "#93c5fd": "#00ffff",
    "#16171a": "#050505",
    "#1e1f25": "#111111",
}


def _apply_theme_colors(colors: dict[str, str]) -> str:
    stylesheet = DARK_THEME_QSS
    for source, target in colors.items():
        stylesheet = stylesheet.replace(source, target)
    return stylesheet


LIGHT_THEME_QSS = """
QMainWindow {
    background-color: #e9edf2;
    color: #1e293b;
}

QWidget {
    background-color: #f8fafc;
    color: #1e293b;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    font-size: 13px;
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
}

QToolBar, QMenuBar {
    background-color: #e2e8f0;
    color: #1e293b;
    border-bottom: 1px solid #94a3b8;
    padding: 4px 8px;
    spacing: 6px;
}

QToolButton {
    background-color: #e2e8f0;
    color: #1e293b;
    border: 1px solid #64748b;
    border-radius: 4px;
    padding: 5px 8px;
}

QToolButton:hover {
    background-color: #cbd5e1;
    border-color: #334155;
    color: #0f172a;
}

QToolButton:pressed, QToolButton:checked {
    background-color: #1d4ed8;
    border: 1px solid #1e40af;
    color: #ffffff;
}

QToolButton:checked:hover {
    background-color: #1e40af;
    border-color: #172554;
}

QMenuBar::item {
    background: transparent;
    color: #1e293b;
    padding: 6px 10px;
}

QMenuBar::item:selected {
    background-color: #cbd5e1;
    color: #0f172a;
}

QMenu {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #64748b;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
}

QMenu::item:selected {
    background-color: #1d4ed8;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #cbd5e1;
    margin: 4px 6px;
}

QStatusBar {
    background-color: #e2e8f0;
    color: #334155;
    border-top: 1px solid #94a3b8;
    font-size: 12px;
}

QStatusBar QLabel, QLabel {
    background: transparent;
    color: #1e293b;
}

QDockWidget {
    color: #1e293b;
    border: 1px solid #64748b;
}

QDockWidget::title {
    background-color: #e2e8f0;
    color: #1e293b;
    border-bottom: 1px solid #94a3b8;
    padding: 6px 10px;
    font-weight: 600;
}

QDockWidget::title:hover {
    background-color: #cbd5e1;
}

QDockWidget::close-button, QDockWidget::float-button {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 2px;
    subcontrol-position: top right;
    subcontrol-origin: margin;
    width: 14px;
    height: 14px;
}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background-color: #cbd5e1;
    border-color: #64748b;
}

QDockWidget::close-button:pressed, QDockWidget::float-button:pressed {
    background-color: #1d4ed8;
    border-color: #1e40af;
}

QDockWidget::close-button {
    right: 4px;
}

QDockWidget::float-button {
    right: 22px;
}

QMainWindow::separator, QSplitter::handle {
    background-color: #cbd5e1;
}

QMainWindow::separator:hover, QSplitter::handle:hover {
    background-color: #1d4ed8;
}

QTabBar::tab {
    background-color: #e2e8f0;
    color: #334155;
    border: 1px solid #94a3b8;
    padding: 6px 12px;
    margin-right: 2px;
}

QTabBar::tab:hover {
    background-color: #cbd5e1;
    color: #0f172a;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1d4ed8;
    border: 1px solid #1d4ed8;
    font-weight: 600;
}

QTabWidget::pane, QTreeWidget, QListWidget, QTableView, QTableWidget {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #64748b;
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
}

QTreeWidget::item, QListWidget::item {
    padding: 5px 7px;
}

QTreeWidget::item:hover, QListWidget::item:hover {
    background-color: #e2e8f0;
    color: #0f172a;
}

QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #1d4ed8;
    color: #ffffff;
}

QPushButton {
    background-color: #e2e8f0;
    color: #1e293b;
    border: 1px solid #64748b;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #cbd5e1;
    border-color: #334155;
    color: #0f172a;
}

QPushButton:pressed {
    background-color: #1d4ed8;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: #e5e7eb;
    color: #6b7280;
    border-color: #9ca3af;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #64748b;
    border-radius: 3px;
    padding: 5px 7px;
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QTextEdit:focus, QPlainTextEdit:focus {
    border: 2px solid #1d4ed8;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1e293b;
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
}

QCheckBox, QRadioButton {
    color: #1e293b;
    spacing: 6px;
}

QScrollBar:vertical {
    background-color: #e2e8f0;
    width: 12px;
}

QScrollBar:horizontal {
    background-color: #e2e8f0;
    height: 12px;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #94a3b8;
    border: 1px solid #64748b;
    min-height: 24px;
    min-width: 24px;
}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background-color: #64748b;
}

QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
}

QSlider::groove:horizontal {
    height: 6px;
    background-color: #cbd5e1;
}

QSlider::sub-page:horizontal {
    background-color: #1d4ed8;
}

QSlider::handle:horizontal {
    background-color: #ffffff;
    border: 2px solid #1d4ed8;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QToolTip {
    background-color: #0f172a;
    color: #ffffff;
    border: 1px solid #334155;
    padding: 4px;
}
"""
HIGH_CONTRAST_THEME_QSS = _apply_theme_colors(HIGH_CONTRAST_THEME_COLORS)

FOREST_ADVENTURE_THEME_QSS = """
QMainWindow, QWidget {
    background-color: #172b22;
    color: #eee2c2;
    selection-background-color: #8b713d;
    selection-color: #fff8df;
}

QToolBar, QMenuBar, QStatusBar, QDockWidget::title {
    background-color: #60452d;
    color: #fff0c8;
    border: 1px solid #a48a53;
}

QToolBar {
    border-bottom: 2px solid #c1a05a;
    spacing: 4px;
    padding: 3px;
}

QToolButton, QPushButton {
    background-color: #294936;
    color: #eee2c2;
    border: 1px solid #9a824d;
    border-radius: 2px;
    padding: 4px 8px;
}

QToolButton:hover, QPushButton:hover {
    background-color: #3a6044;
    border-color: #dfc477;
    color: #fff8df;
}

QToolButton:pressed, QPushButton:pressed, QToolButton:checked {
    background-color: #806735;
    color: #fff8df;
    border-color: #dfc477;
}

QMenu {
    background-color: #1b3529;
    color: #eee2c2;
    border: 1px solid #b39a60;
    padding: 3px;
}

QMenu::item:selected, QMenuBar::item:selected {
    background-color: #806735;
    color: #fff8df;
}

QMenu::separator {
    height: 1px;
    background-color: #80683f;
    margin: 3px 5px;
}

QStatusBar {
    border-top: 1px solid #b39a60;
}

QDockWidget {
    color: #eee2c2;
    border: 1px solid #9a824d;
}

QDockWidget::title {
    border: none;
    border-bottom: 1px solid #b39a60;
    padding: 5px 8px;
}

QMainWindow::separator, QSplitter::handle {
    background-color: #705633;
}

QMainWindow::separator:hover, QSplitter::handle:hover {
    background-color: #c1a05a;
}

QTabBar::tab {
    background-color: #1b3529;
    color: #d8c99f;
    border: 1px solid #80683f;
    padding: 5px 9px;
}

QTabBar::tab:selected {
    background-color: #60452d;
    color: #fff0c8;
    border-color: #c1a05a;
}

QTabBar::tab:hover {
    background-color: #34543b;
    color: #fff8df;
}

QTabWidget::pane, QTreeWidget, QListWidget, QTableView, QTableWidget, QPlainTextEdit {
    background-color: #12241c;
    color: #eee2c2;
    border: 1px solid #8e794b;
    selection-background-color: #526638;
    selection-color: #fff8df;
}

QTreeWidget::item:hover, QListWidget::item:hover, QTableWidget::item:hover {
    background-color: #294735;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {
    background-color: #10231b;
    color: #f3e8c9;
    border: 1px solid #8e794b;
    border-radius: 2px;
    padding: 4px 6px;
    selection-background-color: #806735;
}

QComboBox QAbstractItemView {
    background-color: #1b3529;
    color: #eee2c2;
    selection-background-color: #526638;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #dfc477;
}

QLabel {
    background-color: transparent;
    color: #eee2c2;
}

QCheckBox, QRadioButton {
    color: #eee2c2;
    spacing: 6px;
}

QScrollBar:vertical {
    background-color: #10231b;
    width: 10px;
}

QScrollBar:horizontal {
    background-color: #10231b;
    height: 10px;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #80683f;
    border: 1px solid #b39a60;
    min-height: 20px;
    min-width: 20px;
}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background-color: #b69a57;
}

QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
}

QSlider::groove:horizontal {
    height: 5px;
    background-color: #46513a;
}

QSlider::sub-page:horizontal {
    background-color: #b69a57;
}

QSlider::handle:horizontal {
    background-color: #eee2c2;
    width: 12px;
    margin: -4px 0;
    border: 2px solid #b69a57;
    border-radius: 7px;
}

QToolTip {
    background-color: #10231b;
    color: #fff0c8;
    border: 1px solid #b39a60;
    padding: 3px;
}

QWidget:disabled {
    color: #8c8a77;
}
"""


CANVAS_THEME_COLORS = {
    0: {
        "background": "#121316",
        "hud_background": "#18181b",
        "hud_border": "#3f3f46",
        "hud_text": "#e4e4e7",
        "grid": (255, 255, 255, 89),
    },
    1: {
        "background": "#dce1e8",
        "hud_background": "#ffffff",
        "hud_border": "#8993a1",
        "hud_text": "#252a33",
        "grid": (37, 99, 235, 65),
    },
    2: {
        "background": "#000000",
        "hud_background": "#080808",
        "hud_border": "#00e5ff",
        "hud_text": "#ffffff",
        "grid": (0, 229, 255, 100),
    },
    3: {
        "background": "#203326",
        "hud_background": "#12241c",
        "hud_border": "#b69a57",
        "hud_text": "#fff0c8",
        "grid": (214, 188, 112, 75),
    },
}

_INLINE_COLOR_MAPS = {
    1: {
        "#121316": "#e9edf2", "#18191d": "#f8fafc", "#18181b": "#ffffff",
        "#1e1e24": "#f8fafc", "#27272a": "#e2e8f0", "#272730": "#e2e8f0",
        "#3f3f46": "#64748b", "#2e2e38": "#64748b", "#3b82f6": "#1d4ed8",
        "#60a5fa": "#1d4ed8", "#2563eb": "#1d4ed8", "#1d4ed8": "#1d4ed8",
        "#93c5fd": "#1e40af", "#bfdbfe": "#1e40af", "#a1a1aa": "#475569",
        "#e4e4e7": "#1e293b", "#ffffff": "#ffffff", "#52525b": "#475569",
        "#27272f": "#cbd5e1", "#2b2b36": "#cbd5e1", "#25252d": "#e2e8f0",
        "#1d1e24": "#e2e8f0", "#34363e": "#64748b", "#71717a": "#475569",
        "#b8bac2": "#334155", "#30323a": "#cbd5e1", "#4b4d58": "#64748b",
        "#1a1b22": "#e2e8f0", "#202024": "#f1f5f9", "#2e2e33": "#e2e8f0",
        "#1f1f23": "#f1f5f9", "#1e3a5f": "#1d4ed8", "#f4f4f5": "#1e293b",
        "#475569": "#64748b",
    },
    2: {
        "#121316": "#000000", "#18191d": "#050505", "#18181b": "#050505",
        "#1e1e24": "#050505", "#27272a": "#141414", "#272730": "#141414",
        "#3f3f46": "#666666", "#2e2e38": "#444444", "#3b82f6": "#00e5ff",
        "#60a5fa": "#33aaff", "#2563eb": "#0057ff", "#1d4ed8": "#0057ff",
        "#93c5fd": "#00ffff", "#bfdbfe": "#aefcff", "#a1a1aa": "#e6e6e6",
        "#e4e4e7": "#ffffff", "#ffffff": "#ffffff", "#52525b": "#cccccc",
        "#27272f": "#1a1a1a", "#2b2b36": "#181818", "#25252d": "#181818",
    },
    3: {
        "#121316": "#172b22", "#18191d": "#1b3529", "#18181b": "#12241c",
        "#1e1e24": "#1b3529", "#27272a": "#294936", "#272730": "#294936",
        "#3f3f46": "#80683f", "#2e2e38": "#80683f", "#3b82f6": "#b69a57",
        "#60a5fa": "#dfc477", "#2563eb": "#806735", "#1d4ed8": "#60452d",
        "#93c5fd": "#fff0c8", "#bfdbfe": "#dfc477", "#a1a1aa": "#d8c99f",
        "#e4e4e7": "#eee2c2", "#ffffff": "#fff8df", "#52525b": "#8c8a77",
        "#27272f": "#80683f", "#2b2b36": "#34543b", "#25252d": "#34543b",
    },
}

_INLINE_COLOR_PATTERN = re.compile(
    "|".join(
        re.escape(color)
        for color in sorted(
            {color for mapping in _INLINE_COLOR_MAPS.values() for color in mapping},
            key=len,
            reverse=True,
        )
    ),
    re.IGNORECASE,
)


def get_canvas_theme_colors(theme_index: int) -> dict:
    """Return canvas and HUD colors for the selected theme."""
    return CANVAS_THEME_COLORS.get(theme_index, CANVAS_THEME_COLORS[0])


def get_icon_palette(theme_index: int, mode, state) -> tuple[str, str]:
    """Return foreground and fallback detail colors for an icon state."""
    from PyQt6.QtGui import QIcon

    active = mode in (QIcon.Mode.Active, QIcon.Mode.Selected) or state == QIcon.State.On
    palettes = {
        0: {
            "normal": ("#d4d4d8", "#3f404d"),
            "active": ("#ffffff", "#4f80ff"),
            "disabled": ("#52525b", "#27272a"),
        },
        1: {
            "normal": ("#1e293b", "#475569"),
            "active": ("#ffffff", "#1d4ed8"),
            "disabled": ("#64748b", "#e2e8f0"),
        },
        2: {
            "normal": ("#ffffff", "#00e5ff"),
            "active": ("#000000", "#00e5ff"),
            "disabled": ("#a3a3a3", "#1a1a1a"),
        },
        3: {
            "normal": ("#eee2c2", "#b69a57"),
            "active": ("#fff8df", "#806735"),
            "disabled": ("#8c8a77", "#294936"),
        },
    }
    theme_palette = palettes.get(theme_index, palettes[0])
    return theme_palette["active" if active else "normal" if mode == QIcon.Mode.Normal else "disabled"]


def _recolor_inline_stylesheet(stylesheet: str, theme_index: int) -> str:
    replacements = _INLINE_COLOR_MAPS.get(theme_index, {})
    return _INLINE_COLOR_PATTERN.sub(
        lambda match: replacements.get(match.group(0).lower(), match.group(0)),
        stylesheet,
    )


def _apply_theme_to_widget(
    widget: QWidget, theme_index: int, recursive: bool = True
) -> None:
    apply_theme = getattr(widget, "_apply_application_theme", None)
    if callable(apply_theme):
        apply_theme(theme_index)
    else:
        original = widget.property("_tmm_original_theme_stylesheet")
        current = widget.styleSheet()
        last_applied = widget.property("_tmm_applied_theme_stylesheet")
        if original is None or (last_applied is not None and current != last_applied):
            original = current
            widget.setProperty("_tmm_original_theme_stylesheet", original)
        themed = _recolor_inline_stylesheet(original, theme_index)
        if current != themed:
            widget.setStyleSheet(themed)
        widget.setProperty("_tmm_applied_theme_stylesheet", themed)
    widget.update()
    if recursive:
        for child in widget.findChildren(
            QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
        ):
            _apply_theme_to_widget(child, theme_index)


class _ThemeStyleFilter(QObject):
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget):
            app = QApplication.instance()
            if app is not None:
                _apply_theme_to_widget(
                    watched, int(app.property("theme_index") or 0)
                )
        return False


def apply_application_theme(app: QApplication, theme_index: int) -> None:
    """Apply the selected theme to global widgets and their custom stylesheets."""
    theme_index = theme_index if theme_index in range(4) else 0
    app.setProperty("theme_index", theme_index)
    app.setStyleSheet(get_theme_stylesheet(theme_index))
    from .icons import IconFactory

    style_filter = getattr(app, "_tmm_theme_style_filter", None)
    if style_filter is None:
        style_filter = _ThemeStyleFilter()
        app.installEventFilter(style_filter)
        app._tmm_theme_style_filter = style_filter

    for widget in app.topLevelWidgets():
        _apply_theme_to_widget(widget, theme_index)
        IconFactory.refresh_widget_icons(widget, theme_index)


def get_theme_stylesheet(theme_index: int) -> str:
    """Return the stylesheet for a saved appearance theme selection."""
    return {
        0: DARK_THEME_QSS,
        1: LIGHT_THEME_QSS,
        2: HIGH_CONTRAST_THEME_QSS,
        3: FOREST_ADVENTURE_THEME_QSS,
    }.get(theme_index, DARK_THEME_QSS)
