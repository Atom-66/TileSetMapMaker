"""
Modern Dark Theme QSS and UI Styles.
Inspired by Godot Editor, Aseprite, and professional digital content creation tools.
"""

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

QToolButton:pressed, QToolButton:checked {
    background-color: #3b82f6;
    border: 1px solid #2563eb;
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

/* Dock Widgets & Panels */
QDockWidget {
    color: #e4e4e7;
    font-weight: 600;
    titlebar-close-icon: url(close.png);
    titlebar-normal-icon: url(undock.png);
}

QDockWidget::title {
    background-color: #1c1d22;
    border-bottom: 1px solid #27272f;
    padding: 8px 12px;
    font-size: 12px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
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
