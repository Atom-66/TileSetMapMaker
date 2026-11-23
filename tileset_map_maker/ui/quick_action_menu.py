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

        header = QLabel("⚡ Szybkie Narzędzia")
        header.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: 600; border: none; padding: 2px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner_layout.addWidget(header)

        grid = QGridLayout()
        grid.setSpacing(6)

        tools = [
            ("brush", "Pędzel (B)", 0, 0),
            ("eraser", "Gumka (E)", 0, 1),
            ("fill", "Wypełnianie (G)", 0, 2),
            ("eyedropper", "Pipeta (I)", 1, 0),
            ("select", "Zaznaczanie (S)", 1, 1),
            ("wand", "Różdżka (W)", 1, 2),
            ("object", "Obiekt (V)", 2, 0),
            ("line", "Linia (L)", 2, 1),
            ("rect", "Prostokąt (U)", 2, 2),
        ]

        for key, label, r, c in tools:
            btn = QToolButton(container)
            btn.setIcon(IconFactory.get_icon(key, size=24))
            btn.setIconSize(QSize(22, 22))
            btn.setToolTip(label)
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

        inner_layout.addLayout(grid)

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
