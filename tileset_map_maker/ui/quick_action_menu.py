from typing import Optional, Callable
from PyQt6.QtCore import Qt, QPoint, QSize, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QGridLayout,
    QToolButton,
    QLabel,
    QVBoxLayout,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtGui import QColor

from .icons import IconFactory
from ..core.localization import get_localization, tr


class QuickActionMenu(QWidget):
    """
    Floating radial/grid popup menu (inspired by Aseprite & Blender pie menus)
    allowing instant tool switching under the cursor with shortcuts.
    """
    tool_selected = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._init_ui()

    def _init_ui(self) -> None:
        container = QWidget(self)
        container.setStyleSheet("""
            QWidget {
                background-color: #1e1e24;
                border: 1px solid #3f3f46;
                border-radius: 8px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        container.setGraphicsEffect(shadow)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.addWidget(container)

        inner_layout = QVBoxLayout(container)
        inner_layout.setContentsMargins(8, 8, 8, 8)
        inner_layout.setSpacing(6)

        self.header = QLabel(tr("quick_menu.title"))
        self.header.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: 600; border: none; padding: 2px;")
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner_layout.addWidget(self.header)

        grid = QGridLayout()
        grid.setSpacing(6)

        self._tool_specs = [
            ("brush", "tool.brush", "B", 0, 0),
            ("eraser", "tool.eraser", "E", 0, 1),
            ("fill", "tool.fill", "G", 0, 2),
            ("eyedropper", "tool.eyedropper", "I", 1, 0),
            ("select", "tool.select", "S", 1, 1),
            ("wand", "tool.wand", "W", 1, 2),
            ("object", "tool.object", "V", 2, 0),
            ("line", "tool.line", "L", 2, 1),
            ("rect", "tool.rect", "U", 2, 2),
        ]
        self._tool_buttons = {}

        for key, label_key, shortcut, r, c in self._tool_specs:
            btn = QToolButton(container)
            btn.setIcon(IconFactory.get_icon(key, size=24))
            btn.setIconSize(QSize(22, 22))
            btn.setToolTip(f"{tr(label_key)} ({shortcut})")
            btn.setFixedSize(46, 46)
            btn.setStyleSheet("""
                QToolButton {
                    background-color: #27272a;
                    border: 1px solid #3f3f46;
                    border-radius: 6px;
                }
                QToolButton:hover {
                    background-color: #3b82f6;
                    border-color: #60a5fa;
                }
                QToolButton:pressed {
                    background-color: #2563eb;
                }
            """)
            btn.clicked.connect(lambda checked, k=key: self._on_select(k))
            grid.addWidget(btn, r, c)
            self._tool_buttons[key] = (btn, label_key, shortcut)

        inner_layout.addLayout(grid)
        get_localization().languageChanged.connect(self._apply_language)

    def _apply_language(self, _language: str) -> None:
        self.header.setText(tr("quick_menu.title"))
        for btn, label_key, shortcut in self._tool_buttons.values():
            btn.setToolTip(f"{tr(label_key)} ({shortcut})")

    def _on_select(self, key: str) -> None:
        self.tool_selected.emit(key)
        self.close()

    def show_at(self, global_pos: QPoint) -> None:
        """Positions menu centered at given global coordinates."""
        self.adjustSize()
        w = self.sizeHint().width()
        h = self.sizeHint().height()
        self.move(global_pos.x() - w // 2, global_pos.y() - h // 2)
        self.show()
