from typing import Optional, Dict
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QToolButton,
    QButtonGroup,
)

from ..core.tools import (
    BaseTool,
    BrushTool,
    EraserTool,
    FillTool,
    LineTool,
    RectTool,
    SelectTool,
    StampTool,
    EyedropperTool,
    ObjectTool,
    WandTool,
)
from .icons import IconFactory


class ToolPanel(QWidget):
    """Vertical tools ribbon on the left side of the canvas with crisp vector icons."""
    tool_changed = pyqtSignal(BaseTool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tools: Dict[str, BaseTool] = {
            "brush": BrushTool(),
            "eraser": EraserTool(),
            "fill": FillTool(),
            "line": LineTool(),
            "rect": RectTool(),
            "select": SelectTool(),
            "wand": WandTool(),
            "object": ObjectTool(),
            "eyedropper": EyedropperTool(),
            "stamp": StampTool(),
        }

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(6)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        tool_defs = [
            ("brush", "Pędzel (B)"),
            ("eraser", "Gumka (E / Prawy przycisk myszy)"),
            ("fill", "Wypełnianie (G)"),
            ("line", "Linia (L)"),
            ("rect", "Prostokąt (U)"),
            ("select", "Zaznaczanie (S)"),
            ("wand", "Różdżka (W)"),
            ("object", "Swobodny obiekt (V)"),
            ("eyedropper", "Pipeta (I)"),
            ("stamp", "Stempel (T)"),
        ]

        self.buttons: Dict[str, QToolButton] = {}

        tool_btn_style = """
            QToolButton {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #3b82f6;
                border-color: #60a5fa;
            }
            QToolButton:pressed {
                background-color: #1d4ed8;
                border-color: #2563eb;
            }
            QToolButton:checked {
                background-color: #2563eb;
                border: 2px solid #93c5fd;
            }
        """

        for key, tooltip in tool_defs:
            btn = QToolButton()
            btn.setIcon(IconFactory.get_icon(key, size=24))
            btn.setIconSize(QSize(22, 22))
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFixedSize(40, 40)
            btn.setStyleSheet(tool_btn_style)
            self.btn_group.addButton(btn)
            btn.clicked.connect(lambda checked, k=key: self._on_tool_clicked(k))
            layout.addWidget(btn)
            self.buttons[key] = btn

        self.buttons["brush"].setChecked(True)
        layout.addStretch()

    def _on_tool_clicked(self, key: str) -> None:
        tool = self.tools.get(key)
        if tool:
            self.tool_changed.emit(tool)

    def select_tool_by_key(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)
            self._on_tool_clicked(key)

    def get_tool(self, key: str) -> Optional[BaseTool]:
        return self.tools.get(key)
