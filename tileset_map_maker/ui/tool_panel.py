from typing import Optional, Dict, List, Tuple
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
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
    orientation_changed = pyqtSignal(object)

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
        self._dock_orientation: Optional[Qt.Orientation] = Qt.Orientation.Vertical
        self._orientation_update_pending = False

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
        if isinstance(self.layout(), QGridLayout):
            while self.layout().count():
                self.layout().takeAt(0)

    def _apply_orientation(self, orientation: Qt.Orientation) -> None:
        if self._orientation_update_in_progress or (
            self.current_layout is not None and orientation == self.current_orientation
        ):
            return
        self._orientation_update_in_progress = True
        self.current_orientation = orientation
        self._clear_current_layout()
        grid = self.layout()
        if not isinstance(grid, QGridLayout):
            grid = QGridLayout(self)
        self.current_layout = grid
        for index in range(len(self.TOOL_DEFS) + 1):
            grid.setRowStretch(index, 0)
            grid.setColumnStretch(index, 0)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        if orientation == Qt.Orientation.Horizontal:
            self.setMinimumWidth(404)
            self.setMinimumHeight(44)
            self.setMaximumHeight(16777215)
            self.setMaximumWidth(16777215)
            for column, (key, _) in enumerate(self.TOOL_DEFS):
                grid.addWidget(self.buttons[key], 0, column)
            grid.setColumnStretch(len(self.TOOL_DEFS), 1)
        else:
            self.setMinimumWidth(44)
            self.setMaximumWidth(16777215)
            self.setMinimumHeight(44)
            self.setMaximumHeight(16777215)
            for row, (key, _) in enumerate(self.TOOL_DEFS):
                grid.addWidget(self.buttons[key], row, 0)
            grid.setRowStretch(len(self.TOOL_DEFS), 1)

        self.updateGeometry()
        self._orientation_update_in_progress = False
        self.orientation_changed.emit(orientation)

    def _update_orientation(self) -> None:
        self._orientation_update_pending = False
        button_height = next(iter(self.buttons.values())).height()
        margins = self.layout().contentsMargins()
        vertical_height = (
            len(self.buttons) * button_height
            + (len(self.buttons) - 1) * self.layout().verticalSpacing()
            + margins.top() + margins.bottom()
        )
        if self._dock_orientation == Qt.Orientation.Horizontal:
            target = Qt.Orientation.Horizontal
        elif self._dock_orientation is None and self.width() > self.height():
            target = Qt.Orientation.Horizontal
        else:
            target = (
                Qt.Orientation.Horizontal
                if self.height() < vertical_height
                else Qt.Orientation.Vertical
            )
        if target != self.current_orientation:
            self._apply_orientation(target)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._orientation_update_pending:
            self._orientation_update_pending = True
            QTimer.singleShot(0, self._update_orientation)

    def on_dock_location_changed(self, area: Qt.DockWidgetArea) -> None:
        if area in (Qt.DockWidgetArea.TopDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea):
            self._dock_orientation = Qt.Orientation.Horizontal
        elif area in (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea):
            self._dock_orientation = Qt.Orientation.Vertical
        else:
            self._dock_orientation = None
        self._update_orientation()

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
