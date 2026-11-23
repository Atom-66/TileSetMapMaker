from typing import Optional, Dict, List, Tuple
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QToolButton,
    QButtonGroup,
    QLayout,
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
from ..core.localization import tr, get_localization


class ToolPanel(QWidget):
    """
    Adaptive tools panel on the side of the canvas with crisp vector icons.
    Automatically transitions from vertical to horizontal layout when flattened
    or when docked to top/bottom dock areas.
    """
    tool_changed = pyqtSignal(BaseTool)

    TOOL_DEFS: List[Tuple[str, str]] = [
        ("brush", tr("tool.brush") + " (B)"),
        ("eraser", tr("tool.eraser") + " (E)"),
        ("fill", tr("tool.fill") + " (G)"),
        ("line", tr("tool.line") + " (L)"),
        ("rect", tr("tool.rect") + " (U)"),
        ("select", tr("tool.select") + " (S)"),
        ("wand", tr("tool.wand") + " (W)"),
        ("object", tr("tool.object") + " (V)"),
        ("eyedropper", tr("tool.eyedropper") + " (I)"),
        ("stamp", tr("tool.stamp") + " (T)"),
    ]

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

        self.buttons: Dict[str, QToolButton] = {}
        self.current_orientation = Qt.Orientation.Vertical
        self.current_layout: Optional[QLayout] = None
        self._layout_mode: Optional[str] = None
        self._orientation_update_in_progress = False

        self._create_buttons()
        self._apply_orientation(Qt.Orientation.Vertical)
        get_localization().languageChanged.connect(self._apply_language)

    def _apply_language(self, _language: str) -> None:
        labels = {
            "brush": tr("tool.brush") + " (B)",
            "eraser": tr("tool.eraser") + " (E)",
            "fill": tr("tool.fill") + " (G)",
            "line": tr("tool.line") + " (L)",
            "rect": tr("tool.rect") + " (U)",
            "select": tr("tool.select") + " (S)",
            "wand": tr("tool.wand") + " (W)",
            "object": tr("tool.object") + " (V)",
            "eyedropper": tr("tool.eyedropper") + " (I)",
            "stamp": tr("tool.stamp") + " (T)",
        }
        for key, button in self.buttons.items():
            button.setToolTip(labels[key])

    def _create_buttons(self) -> None:
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        tool_btn_style = """
            QToolButton {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #3f3f46;
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
            QToolButton:checked:hover {
                background-color: #1d4ed8;
                border-color: #bfdbfe;
            }
        """

        for key, tooltip in self.TOOL_DEFS:
            btn = QToolButton(self)
            btn.setIcon(IconFactory.get_icon(key, size=24))
            btn.setIconSize(QSize(22, 22))
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFixedSize(36, 36)
            btn.setStyleSheet(tool_btn_style)
            self.btn_group.addButton(btn)
            btn.clicked.connect(lambda checked, k=key: self._on_tool_clicked(k))
            self.buttons[key] = btn

        self.buttons["brush"].setChecked(True)

    def _clear_current_layout(self) -> None:
        if self.layout() is not None:
            old_layout = self.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(self)
            old_layout.deleteLater()

    def _apply_orientation(self, orientation: Qt.Orientation) -> None:
        self.current_orientation = orientation
        self._clear_current_layout()

        if orientation == Qt.Orientation.Horizontal:
            h = self.height()
            w = self.width()

            columns = max(1, min(5, (w - 8 + 4) // 40))
            if columns < len(self.TOOL_DEFS):
                grid = QGridLayout(self)
                grid.setContentsMargins(4, 4, 4, 4)
                grid.setHorizontalSpacing(4)
                grid.setVerticalSpacing(4)
                for idx, (key, _) in enumerate(self.TOOL_DEFS):
                    grid.addWidget(self.buttons[key], idx // columns, idx % columns)
                grid.setRowStretch((len(self.TOOL_DEFS) + columns - 1) // columns, 1)
                grid.setColumnStretch(columns, 1)
            else:
                h_layout = QHBoxLayout(self)
                h_layout.setContentsMargins(4, 4, 4, 4)
                h_layout.setSpacing(4)
                for key, _ in self.TOOL_DEFS:
                    h_layout.addWidget(self.buttons[key])
                h_layout.addStretch()
        else:
            w = self.width()
            h = self.height()

            if w >= 80 and h < 420:
                grid = QGridLayout(self)
                grid.setContentsMargins(4, 4, 4, 4)
                grid.setSpacing(4)
                for idx, (key, _) in enumerate(self.TOOL_DEFS):
                    row = idx % 5
                    column = idx // 5
                    grid.addWidget(self.buttons[key], row, column)
            else:
                v_layout = QVBoxLayout(self)
                v_layout.setContentsMargins(4, 8, 4, 8)
                v_layout.setSpacing(6)
                for key, _ in self.TOOL_DEFS:
                    v_layout.addWidget(self.buttons[key])
                v_layout.addStretch()

        self.updateGeometry()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        target = Qt.Orientation.Horizontal if (h < 250 or w > h * 1.15) else Qt.Orientation.Vertical
        if target != self.current_orientation:
            self._apply_orientation(target)

    def on_dock_location_changed(self, area: Qt.DockWidgetArea) -> None:
        if area in (Qt.DockWidgetArea.TopDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea):
            self._apply_orientation(Qt.Orientation.Horizontal)
        elif area in (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea):
            if self.height() >= 250 and self.height() >= self.width():
                self._apply_orientation(Qt.Orientation.Vertical)

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
