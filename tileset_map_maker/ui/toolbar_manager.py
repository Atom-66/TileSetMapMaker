import copy
import json
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Tuple

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QSize, QPoint, QRect, QEvent, QMimeData
from PyQt6.QtGui import (
    QAction,
    QIcon,
    QDrag,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QPolygon,
    QMouseEvent,
    QResizeEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QWidget,
    QToolBar,
    QHBoxLayout,
    QVBoxLayout,
    QLayout,
    QSizePolicy,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QComboBox,
    QLabel,
    QFrame,
    QMenu,
    QToolButton,
    QAbstractItemView,
    QTabWidget,
    QTabBar,
    QCheckBox,
    QLineEdit,
)
from PyQt6 import sip

from .icons import IconFactory
from ..core.localization import tr
from ..core.config_manager import ConfigManager

logger = logging.getLogger("ToolbarManager")

TOOLBAR_LAYOUT_VERSION: int = 3

TOOLBAR_BUTTON_STYLE = """
    QToolButton {
        background: #27272a;
        color: #e4e4e7;
        border: 1px solid #3f3f46;
        border-radius: 4px;
        padding: 0px 4px;
        font-size: 11px;
        font-weight: 500;
        height: 24px;
        max-height: 24px;
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


@dataclass
class ToolbarItemDef:
    id: str
    label: str
    category_id: str
    default_category_id: str
    icon_name: str
    tooltip: str = ""
    visible: bool = True
    order: int = 0
    action: Optional[QAction] = None
    widget: Optional[QWidget] = None
    button: Optional[QToolButton] = None


@dataclass
class ToolbarCategoryDef:
    id: str
    title: str
    icon_name: str
    visible: bool = True
    order: int = 0
    toolbar_id: str = "main"  # "main" or "secondary"
    default_toolbar_id: str = "main"
    item_ids: List[str] = field(default_factory=list)
    default_item_ids: List[str] = field(default_factory=list)


def create_toolbar_separator() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    sep.setFixedHeight(20)
    sep.setStyleSheet("color: #3f3f46; background-color: #3f3f46; width: 1px; max-height: 20px;")
    return sep


class ToolbarCategoryWidget(QWidget):
    """Container widget grouping all controls of a single toolbar category."""

    def __init__(self, category_def: ToolbarCategoryDef, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.category_def = category_def
        self.setObjectName(f"CategoryWidget_{category_def.id}")
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(2, 1, 2, 1)
        self.main_layout.setSpacing(3)
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(2)
        self.layout_box = QHBoxLayout()
        self.layout_box.setContentsMargins(0, 0, 0, 0)
        self.layout_box.setSpacing(3)
        self.main_layout.addLayout(self.header_layout, 0)
        self.main_layout.addLayout(self.layout_box)
        self.item_widgets: Dict[str, QWidget] = {}
        self.setStyleSheet("""
            ToolbarCategoryWidget {
                background: #1d1e24;
                border: 1px solid #34363e;
                border-radius: 5px;
            }
        """)

    def set_grip(self, grip: "CategoryGripWidget") -> None:
        self.header_layout.addWidget(grip)

    def add_item_widget(self, item_id: str, widget: QWidget) -> None:
        self.item_widgets[item_id] = widget
        self.layout_box.addWidget(widget)

    def remove_item_widget(self, item_id: str) -> Optional[QWidget]:
        w = self.item_widgets.pop(item_id, None)
        if w:
            self.layout_box.removeWidget(w)
        return w

    def clear_widgets(self) -> None:
        for w in list(self.item_widgets.values()):
            self.layout_box.removeWidget(w)
        self.item_widgets.clear()


class CategoryGripWidget(QWidget):
    """
    Drag grip chip for an entire toolbar category.
    Visible in edit mode to allow dragging the whole category as a unit.
    """

    def __init__(self, category_def: ToolbarCategoryDef, manager: "ToolbarManager", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.category_def = category_def
        self.manager = manager
        self.drag_start_pos: Optional[QPoint] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(3)
        self.setFixedHeight(22)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setToolTip(f"Kategoria: {self.category_def.title}")

        self.lbl_grip = QLabel("⋮⋮")
        self.lbl_grip.setStyleSheet("color: #71717a; font-size: 10px; font-weight: bold; background: transparent;")
        layout.addWidget(self.lbl_grip)

        self.lbl_title = QLabel(self.category_def.title)
        self.lbl_title.setStyleSheet("color: #b8bac2; font-size: 10px; font-weight: 600; background: transparent;")
        layout.addWidget(self.lbl_title)

        self.setStyleSheet("""
            CategoryGripWidget {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
            }
            CategoryGripWidget:hover {
                background-color: #30323a;
                border: 1px solid #4b4d58;
            }
        """)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            self.manager.is_edit_mode
            and event.button() == Qt.MouseButton.LeftButton
        ):
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            self.drag_start_pos = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self.manager.is_edit_mode
            and (event.buttons() & Qt.MouseButton.LeftButton)
            and self.drag_start_pos is not None
        ):
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if (pos - self.drag_start_pos).manhattanLength() >= QApplication.startDragDistance():
                self._start_category_drag()
                self.drag_start_pos = None
                self.setCursor(
                    Qt.CursorShape.OpenHandCursor
                    if self.manager.is_edit_mode
                    else Qt.CursorShape.ArrowCursor
                )
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.drag_start_pos = None
        self.setCursor(
            Qt.CursorShape.OpenHandCursor
            if self.manager.is_edit_mode
            else Qt.CursorShape.ArrowCursor
        )
        super().mouseReleaseEvent(event)

    def _start_category_drag(self) -> None:
        if not self.manager.is_edit_mode:
            return
        drag = QDrag(self)
        mime = QMimeData()
        request = self.manager.create_category_drag_request(
            self.category_def.id, DragContext.TOOLBAR
        )
        if request is None:
            return
        mime.setData("application/x-toolbar-category", request.to_bytes())
        drag.setMimeData(mime)

        preview_widget = self.parentWidget()
        pix = preview_widget.grab() if isinstance(preview_widget, ToolbarCategoryWidget) else self.grab()
        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(pix.width() // 2, pix.height() // 2))

        operation_id = f"category:{self.category_def.id}:{id(drag)}"
        drag_safety = getattr(self.manager, "drag_safety", None)
        if drag_safety is not None and not drag_safety.begin(
            operation_id, self.manager.on_category_drag_finished
        ):
            return
        try:
            self.manager.on_category_drag_started(self.category_def.id)
            drag.exec(Qt.DropAction.MoveAction)
        except Exception:
            logger.exception("Category drag failed for %s", self.category_def.id)
        finally:
            self.manager.on_category_drag_finished()
            if drag_safety is not None:
                drag_safety.finish(operation_id)


class ToolbarDragPhase(Enum):
    IDLE = auto()
    PRESSED = auto()
    DRAGGING = auto()
    DROPPING = auto()
    CANCELLED = auto()


class DragElementType(Enum):
    CATEGORY = "category"
    BUTTON = "button"


class DragContext(Enum):
    TOOLBAR = "toolbar"
    CUSTOMIZER = "customizer"


class ToolbarDragOperation(Enum):
    CATEGORY_REORDER = "category_reorder"
    CATEGORY_MOVE = "category_move"
    BUTTON_REORDER = "button_reorder"
    BUTTON_REASSIGN = "button_reassign"


@dataclass(frozen=True)
class ToolbarDragRequest:
    element_type: DragElementType
    element_id: str
    context: DragContext
    allowed_operations: Tuple[ToolbarDragOperation, ...]
    source_category_id: Optional[str] = None
    source_toolbar_id: Optional[str] = None
    target_id: Optional[str] = None
    target_toolbar_id: Optional[str] = None

    def to_bytes(self) -> bytes:
        return json.dumps({
            "element_type": self.element_type.value,
            "element_id": self.element_id,
            "context": self.context.value,
            "allowed_operations": [operation.value for operation in self.allowed_operations],
            "source_category_id": self.source_category_id,
            "source_toolbar_id": self.source_toolbar_id,
            "target_id": self.target_id,
            "target_toolbar_id": self.target_toolbar_id,
        }).encode("utf-8")

    @classmethod
    def from_bytes(cls, payload: bytes) -> Optional["ToolbarDragRequest"]:
        try:
            data = json.loads(payload.decode("utf-8"))
            if not isinstance(data, dict):
                return None
            element_id = data.get("element_id")
            allowed_operations = data.get("allowed_operations")
            if not isinstance(element_id, str) or not element_id:
                return None
            if not isinstance(allowed_operations, list):
                return None
            return cls(
                element_type=DragElementType(data["element_type"]),
                element_id=element_id,
                context=DragContext(data["context"]),
                allowed_operations=tuple(
                    ToolbarDragOperation(operation)
                    for operation in allowed_operations
                ),
                source_category_id=data.get("source_category_id"),
                source_toolbar_id=data.get("source_toolbar_id"),
                target_id=data.get("target_id"),
                target_toolbar_id=data.get("target_toolbar_id"),
            )
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return None

    def at_target(self, target_id: str, target_toolbar_id: str) -> "ToolbarDragRequest":
        return ToolbarDragRequest(
            element_type=self.element_type,
            element_id=self.element_id,
            context=self.context,
            allowed_operations=self.allowed_operations,
            source_category_id=self.source_category_id,
            source_toolbar_id=self.source_toolbar_id,
            target_id=target_id,
            target_toolbar_id=target_toolbar_id,
        )


class ToolbarItemEditFilter(QObject):
    """Starts a category-local button drag in toolbar edit mode."""

    def __init__(
        self,
        item_id: str,
        manager: "ToolbarManager",
        drag_widget: QWidget,
    ):
        super().__init__(drag_widget)
        self.item_id = item_id
        self.manager = manager
        self.drag_widget = drag_widget
        self.phase = ToolbarDragPhase.IDLE
        self.press_global_pos: Optional[QPoint] = None
        self._suppress_release = False
        self._watched_widgets: List[QWidget] = []
        self._original_cursors: Dict[QWidget, Any] = {}

    def install(self) -> None:
        self._watched_widgets = [self.drag_widget, *self.drag_widget.findChildren(QWidget)]
        for widget in self._watched_widgets:
            self._original_cursors[widget] = widget.cursor()
            widget.installEventFilter(self)
            self._update_cursor(widget)

    def uninstall(self) -> None:
        self.cancel()
        for widget in self._watched_widgets:
            if not sip.isdeleted(widget):
                widget.removeEventFilter(self)
                self._restore_cursor(widget)
        self._watched_widgets.clear()
        self._original_cursors.clear()
        self.deleteLater()

    def update_cursors(self) -> None:
        for widget in self._watched_widgets:
            if not sip.isdeleted(widget):
                self._update_cursor(widget)

    def _update_cursor(self, widget: QWidget) -> None:
        self._restore_cursor(widget)

    def _restore_cursor(self, widget: QWidget) -> None:
        cursor = self._original_cursors.get(widget)
        if cursor is not None:
            widget.setCursor(cursor)

    @staticmethod
    def _global_position(event: QMouseEvent) -> QPoint:
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        return event.globalPos()

    def cancel(self) -> None:
        if self.phase in (
            ToolbarDragPhase.PRESSED,
            ToolbarDragPhase.DRAGGING,
            ToolbarDragPhase.CANCELLED,
        ):
            self._suppress_release = True
        if self.phase is not ToolbarDragPhase.IDLE:
            self.phase = ToolbarDragPhase.CANCELLED
        self.press_global_pos = None
        self.phase = ToolbarDragPhase.IDLE

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        evt_type = event.type()
        if not self.manager.is_edit_mode:
            if (
                evt_type == QEvent.Type.MouseButtonPress
                and isinstance(event, QMouseEvent)
                and event.button() == Qt.MouseButton.LeftButton
            ):
                self._suppress_release = False
            if (
                evt_type == QEvent.Type.MouseButtonRelease
                and isinstance(event, QMouseEvent)
                and event.button() == Qt.MouseButton.LeftButton
                and self._suppress_release
            ):
                self._suppress_release = False
                if isinstance(self.drag_widget, QToolButton):
                    self.drag_widget.setDown(False)
                return True
            if evt_type == QEvent.Type.FocusOut:
                self.cancel()
            return False

        if evt_type == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self.press_global_pos = self._global_position(event)
                self.phase = ToolbarDragPhase.PRESSED
                if isinstance(watched, QWidget):
                    watched.setCursor(Qt.CursorShape.ClosedHandCursor)
            return False

        if evt_type == QEvent.Type.MouseButtonDblClick and isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self.press_global_pos = self._global_position(event)
                self.phase = ToolbarDragPhase.PRESSED
            return True

        if evt_type == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
            if (
                self.phase is ToolbarDragPhase.PRESSED
                and self.press_global_pos is not None
                and event.buttons() & Qt.MouseButton.LeftButton
                and (self._global_position(event) - self.press_global_pos).manhattanLength()
                >= QApplication.startDragDistance()
            ):
                self.phase = ToolbarDragPhase.DRAGGING
                self.press_global_pos = None
                if isinstance(self.drag_widget, QToolButton):
                    self.drag_widget.setDown(False)
                self._suppress_release = True
                self._start_button_drag()
                self.phase = ToolbarDragPhase.IDLE
                self._suppress_release = False
                if isinstance(watched, QWidget):
                    self._update_cursor(watched)
                return True
            return self.phase in (
                ToolbarDragPhase.DRAGGING,
                ToolbarDragPhase.CANCELLED,
            )

        if evt_type == QEvent.Type.MouseButtonRelease and isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                if self.phase is ToolbarDragPhase.PRESSED:
                    self.cancel()
                if isinstance(self.drag_widget, QToolButton):
                    self.drag_widget.setDown(False)
                if isinstance(watched, QWidget):
                    self._update_cursor(watched)
                self.press_global_pos = None
                self._suppress_release = False
                self.phase = ToolbarDragPhase.IDLE
                return True

        if evt_type in (QEvent.Type.FocusOut, QEvent.Type.WindowDeactivate):
            self.cancel()
        return False

    def _start_button_drag(self) -> None:
        request = self.manager.create_button_drag_request(
            self.item_id, DragContext.TOOLBAR
        )
        if request is None:
            return
        drag = QDrag(self.drag_widget)
        mime_data = QMimeData()
        mime_data.setData("application/x-toolbar-button", request.to_bytes())
        drag.setMimeData(mime_data)
        pixmap = self.drag_widget.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        try:
            drag.exec(Qt.DropAction.MoveAction)
        except Exception:
            logger.exception("Toolbar button drag failed for %s", self.item_id)


ToolbarItemDragFilter = ToolbarItemEditFilter


class FlowLayout(QLayout):
    """
    Standard responsive wrapping layout (FlowLayout) for Qt.
    Dynamically arranges widgets in horizontal rows, wrapping to subsequent
    rows when width is constrained, with automatic heightForWidth computation.
    """

    def __init__(self, parent: Optional[QWidget] = None, margin: int = 4, h_spacing: int = 4, v_spacing: int = 4):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._item_list: List[Any] = []

    def addItem(self, item: Any) -> None:
        self._item_list.append(item)

    def count(self) -> int:
        return len(self._item_list)

    def itemAt(self, index: int) -> Optional[Any]:
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index: int) -> Optional[Any]:
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return max(self._do_layout(QRect(0, 0, width, 0), apply_geometry=False), 48)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, apply_geometry=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        sz = QSize()
        for item in self._item_list:
            sz = sz.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        sz += QSize(m.left() + m.right(), m.top() + m.bottom())
        return sz

    def _do_layout(self, rect: QRect, apply_geometry: bool = True) -> int:
        m = self.contentsMargins()
        effective_rect = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        h_spacing = self._h_spacing
        v_spacing = self._v_spacing

        for item in self._item_list:
            wid = item.widget()
            if wid and wid.isHidden():
                continue
            item_sz = item.sizeHint()
            item_w = item_sz.width()
            item_h = max(item_sz.height(), 26)
            next_x = x + item_w + h_spacing
            if next_x - h_spacing > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + v_spacing
                next_x = x + item_w + h_spacing
                line_height = 0
            if apply_geometry:
                item.setGeometry(QRect(x, y, item_w, item_h))
            x = next_x
            line_height = max(line_height, item_h)
        return y + line_height - rect.y() + m.bottom()


class FlowContainerWidget(QWidget):
    """Internal container hosting the FlowLayout inside CustomizableToolBar."""

    def __init__(self, toolbar: "CustomizableToolBar", parent: Optional[QWidget] = None):
        super().__init__(parent or toolbar)
        self.toolbar = toolbar
        self.setObjectName(f"FlowContainer_{toolbar.toolbar_id}")
        self.setStyleSheet("background: transparent;")

    def event(self, event: QEvent) -> bool:
        res = super().event(event)
        # Children changed size/visibility -> toolbar must re-evaluate its height
        if event.type() == QEvent.Type.LayoutRequest and self.toolbar is not None:
            self.toolbar._sync_container()
        return res

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        if (
            self.toolbar
            and self.toolbar.drop_indicator_x is not None
            and (self.toolbar.is_edit_mode or self.toolbar.is_category_drag)
        ):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.toolbar._render_drop_indicator(painter)
            painter.end()


class CustomizableToolBar(QToolBar):
    """
    Enhanced QToolBar supporting whole-category drag and drop, responsive FlowLayout
    multi-row wrapping, a category insertion indicator, and edit mode styling.
    """

    def __init__(self, title: str = "", toolbar_id: str = "main", parent: Optional[QWidget] = None):
        super().__init__(title, parent)
        self.toolbar_id = toolbar_id
        self.manager: Optional["ToolbarManager"] = None
        self.is_edit_mode: bool = False
        self.drop_indicator_x: Optional[int] = None
        self.drop_indicator_y: Optional[int] = None
        self.drop_indicator_h: Optional[int] = None
        self.target_cat_id: Optional[str] = None
        self.target_item_index: Optional[int] = None
        self.target_cat_index: Optional[int] = None
        self.target_flat_index: Optional[int] = None
        self.is_category_drag: bool = False
        self._drop_request: Optional[ToolbarDragRequest] = None
        self._drop_operation: Optional[ToolbarDragOperation] = None
        self.category_grips: Dict[str, CategoryGripWidget] = {}
        self.category_widgets: Dict[str, ToolbarCategoryWidget] = {}
        self.item_widgets_map: Dict[str, QWidget] = {}
        self._action_widgets: Dict[QAction, QWidget] = {}
        self._actions_list: List[QAction] = []

        self.setMovable(False)
        self.setFloatable(False)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        # Embedded flow container.
        # NOTE: the container is intentionally NOT added through QToolBar's internal
        # layout. QToolBarLayout sizes embedded widgets to their (narrow) sizeHint every
        # time any child requests a relayout (e.g. a button changing its checked style),
        # which collapsed the FlowLayout into a ~125px column after every click.
        # We position the container ourselves to always fill the whole toolbar.
        self._syncing_container = False
        self._last_flow_height = -1
        self.container = FlowContainerWidget(self, parent=self)
        self.flow_layout = FlowLayout(self.container, margin=3, h_spacing=4, v_spacing=4)
        self.container.show()

    def set_manager(self, manager: "ToolbarManager") -> None:
        self.manager = manager

    def set_edit_mode(self, active: bool) -> None:
        self.is_edit_mode = active
        self.drop_indicator_x = None
        self.drop_indicator_y = None
        self.drop_indicator_h = None
        self.target_cat_index = None
        self.target_cat_id = None
        self.target_item_index = None
        self.is_category_drag = False
        if active:
            self.setStyleSheet("""
                QToolBar {
                    background-color: #1a1b22;
                    border: 1px dashed #3b82f6;
                    border-radius: 4px;
                    padding: 2px;
                }
            """)
        else:
            self.setStyleSheet("")
        self.update()
        if hasattr(self, "container"):
            self.container.update()

    def addWidget(self, widget: QWidget) -> None:
        if widget == self.container:
            return
        widget.setParent(self.container)
        self.flow_layout.addWidget(widget)
        widget.show()
        self._sync_container()

    def addAction(self, action: QAction) -> QAction:
        btn = QToolButton(self.container)
        btn.setDefaultAction(action)
        btn.setFixedSize(26, 26)
        btn.setStyleSheet(TOOLBAR_BUTTON_STYLE)
        self._action_widgets[action] = btn
        self._actions_list.append(action)
        self.flow_layout.addWidget(btn)
        btn.show()
        self._sync_container()
        return action

    def widgetForAction(self, action: QAction) -> Optional[QWidget]:
        return self._action_widgets.get(action)

    def actions(self) -> List[QAction]:
        return list(self._actions_list)

    def clear(self) -> None:
        self.category_grips.clear()
        self.category_widgets.clear()
        self.item_widgets_map.clear()
        self._action_widgets.clear()
        self._actions_list.clear()
        persistent = set()
        if self.manager is not None:
            persistent = {id(it.widget) for it in self.manager.items.values() if it.widget is not None}
        while self.flow_layout.count() > 0:
            item = self.flow_layout.takeAt(0)
            w = item.widget() if item else None
            if w is None:
                continue
            w.hide()
            w.setParent(None)
            # Toolbar-owned helpers (action buttons, separators, grips) are recreated on
            # every rebuild; delete them instead of leaking orphan top-level widgets.
            if id(w) not in persistent:
                w.deleteLater()

    def addSeparator(self) -> QAction:
        sep = create_toolbar_separator()
        sep.setParent(self.container)
        self.flow_layout.addWidget(sep)
        sep.show()
        act = QAction(self)
        act.setSeparator(True)
        self._actions_list.append(act)
        return act

    def _flow_height(self, width: int) -> int:
        # Preserve a stable toolbar band even when the currently visible item set
        # fits in one short row.  Its height is then independent of rebuild timing.
        return max(self.flow_layout.heightForWidth(max(width, 100)), 48)

    def sizeHint(self) -> QSize:
        w = max(self.width(), 100)
        return QSize(w, self._flow_height(w))

    def minimumSizeHint(self) -> QSize:
        # Height must follow the wrapped rows, otherwise QMainWindow may squash the bar
        return QSize(100, self._flow_height(max(self.width(), 100)))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._flow_height(width)

    def _sync_container(self) -> None:
        """Keeps the flow container covering the full toolbar and the bar height in sync."""
        if not hasattr(self, "container") or self._syncing_container:
            return
        self._syncing_container = True
        try:
            r = self.rect()
            if self.container.geometry() != r:
                self.container.setGeometry(r)
            else:
                self.flow_layout.setGeometry(self.container.rect())
            self.container.raise_()
            h = self._flow_height(r.width())
            if h != self._last_flow_height:
                self._last_flow_height = h
                self.updateGeometry()
        finally:
            self._syncing_container = False

    def event(self, event: QEvent) -> bool:
        res = super().event(event)
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.Show, QEvent.Type.StyleChange):
            self._sync_container()
        return res

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._sync_container()

    def dragEnterEvent(self, event: Any) -> None:
        category_request = self._toolbar_category_request(event.mimeData())
        button_request = self._toolbar_button_request(event.mimeData())
        if self.manager is not None and self.manager.is_edit_mode and (
            category_request or button_request
        ):
            event.acceptProposedAction()
            self.update()
            if hasattr(self, "container"):
                self.container.update()
        else:
            self._clear_drop_indicator()
            event.ignore()

    def dragMoveEvent(self, event: Any) -> None:
        mime = event.mimeData()
        if not self.manager:
            self._clear_drop_indicator()
            event.ignore()
            return

        if (
            not self.manager.is_edit_mode
        ):
            self._clear_drop_indicator()
            event.ignore()
            return

        category_resolved = self._toolbar_category_request(mime)
        if category_resolved is not None:
            request, operation = category_resolved
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            slot_x, cat_idx = self.calculate_category_drop_slot(pos, request.element_id)
            self.drop_indicator_x = slot_x
            self.drop_indicator_y = 2
            self.drop_indicator_h = self.height() - 4
            self.target_cat_index = cat_idx
            self.is_category_drag = True
            self._drop_request = request.at_target(self.toolbar_id, self.toolbar_id)
            self._drop_operation = operation
            self.update()
            self.container.update()
            event.acceptProposedAction()
            return

        button_resolved = self._toolbar_button_request(mime)
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        container_pos = self.container.mapFrom(self, pos)
        if button_resolved is not None:
            request, operation = button_resolved
            source_category_id = request.source_category_id
            slot = self._item_drop_slot_in_category(
                container_pos, source_category_id or "", request.element_id
            )
            if slot is not None:
                slot_x, slot_y, item_index = slot
                self.drop_indicator_x = slot_x
                self.drop_indicator_y = slot_y
                self.drop_indicator_h = 26
                self.target_cat_id = source_category_id
                self.target_item_index = item_index
                self.is_category_drag = False
                self._drop_request = request.at_target(
                    source_category_id or "", self.toolbar_id
                )
                self._drop_operation = operation
                self.container.update()
                event.acceptProposedAction()
                return

        self._clear_drop_indicator()
        event.ignore()

    def dragLeaveEvent(self, event: Any) -> None:
        self._clear_drop_indicator()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: Any) -> None:
        if not self.manager:
            self._clear_drop_indicator()
            event.ignore()
            return

        category_resolved = self._toolbar_category_request(event.mimeData())
        if (
            self.manager.is_edit_mode
            and category_resolved is not None
            and self.target_cat_index is not None
            and self.is_category_drag
            and self._drop_request is not None
            and self._drop_operation is not None
            and self.manager.validate_drag_operation(
                self._drop_request,
                self._drop_operation,
                target_id=self.toolbar_id,
                target_toolbar_id=self.toolbar_id,
            )
        ):
            request, operation = category_resolved
            if request.element_id == self._drop_request.element_id and operation is self._drop_operation:
                self.manager.move_category_to_toolbar_slot(
                    request.element_id, self.target_cat_index, self.toolbar_id
                )
                event.acceptProposedAction()
            else:
                event.ignore()
        elif self.manager.is_edit_mode:
            button_resolved = self._toolbar_button_request(event.mimeData())
            request = button_resolved[0] if button_resolved else None
            if (
                request is not None
                and not self.is_category_drag
                and self.target_cat_id == request.source_category_id
                and self.target_item_index is not None
                and self._drop_request is not None
                and self._drop_request.element_id == request.element_id
                and self._drop_operation is ToolbarDragOperation.BUTTON_REORDER
                and self.manager.validate_drag_operation(
                    self._drop_request,
                    ToolbarDragOperation.BUTTON_REORDER,
                    target_id=request.source_category_id or "",
                    target_toolbar_id=self.toolbar_id,
                )
            ):
                self.manager.move_item(
                    request.element_id,
                    request.source_category_id,
                    self.target_item_index,
                )
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

        self._clear_drop_indicator()

    def _toolbar_category_request(
        self, mime: QMimeData
    ) -> Optional[Tuple[ToolbarDragRequest, ToolbarDragOperation]]:
        if not mime.hasFormat("application/x-toolbar-category"):
            return None
        request = ToolbarDragRequest.from_bytes(
            bytes(mime.data("application/x-toolbar-category"))
        )
        if (
            request is None
            or request.element_type is not DragElementType.CATEGORY
            or request.context is not DragContext.TOOLBAR
            or self.manager is None
        ):
            return None
        operation = (
            ToolbarDragOperation.CATEGORY_REORDER
            if request.source_toolbar_id == self.toolbar_id
            else ToolbarDragOperation.CATEGORY_MOVE
        )
        targeted = request.at_target(self.toolbar_id, self.toolbar_id)
        if not self.manager.validate_drag_operation(
            targeted,
            operation,
            target_id=self.toolbar_id,
            target_toolbar_id=self.toolbar_id,
        ):
            return None
        return request, operation

    def _toolbar_button_request(
        self, mime: QMimeData
    ) -> Optional[Tuple[ToolbarDragRequest, ToolbarDragOperation]]:
        if (
            not mime.hasFormat("application/x-toolbar-button")
            or self.manager is None
            or not self.manager.is_edit_mode
        ):
            return None
        request = ToolbarDragRequest.from_bytes(
            bytes(mime.data("application/x-toolbar-button"))
        )
        if (
            request is None
            or request.element_type is not DragElementType.BUTTON
            or request.context is not DragContext.TOOLBAR
        ):
            return None
        operation = ToolbarDragOperation.BUTTON_REORDER
        targeted = request.at_target(
            request.source_category_id or "", self.toolbar_id
        )
        if not self.manager.validate_drag_operation(
            targeted,
            operation,
            target_id=request.source_category_id or "",
            target_toolbar_id=self.toolbar_id,
        ):
            return None
        return request, operation

    def _item_drop_slot_in_category(
        self, pos: QPoint, category_id: str, dragged_item_id: str
    ) -> Optional[Tuple[int, int, int]]:
        if self.manager is None:
            return None
        category = self.manager.categories.get(category_id)
        category_widget = self.category_widgets.get(category_id)
        if (
            category is None
            or category_widget is None
            or category.toolbar_id != self.toolbar_id
            or not category.visible
        ):
            return None
        category_rect = category_widget.geometry()
        if not category_rect.contains(pos):
            return None

        visible_items: List[Tuple[str, int, QRect]] = []
        for item_index, item_id in enumerate(category.item_ids):
            if item_id == dragged_item_id:
                continue
            item = self.manager.items.get(item_id)
            widget = category_widget.item_widgets.get(item_id)
            if item is None or not item.visible or widget is None or widget.isHidden():
                continue
            item_pos = widget.mapTo(self.container, QPoint(0, 0))
            visible_items.append(
                (item_id, item_index, QRect(item_pos, widget.size()))
            )

        visible_items.sort(key=lambda entry: (entry[2].top(), entry[2].left()))
        if not visible_items:
            dragged_index = (
                category.item_ids.index(dragged_item_id)
                if dragged_item_id in category.item_ids
                else 0
            )
            return (category_rect.left() + 8, category_rect.top() + 2, dragged_index)

        rows: List[List[Tuple[str, int, QRect]]] = []
        for entry in visible_items:
            for row in rows:
                if abs(row[0][2].center().y() - entry[2].center().y()) < 14:
                    row.append(entry)
                    break
            else:
                rows.append([entry])
        rows.sort(key=lambda row: row[0][2].center().y())
        best_row = min(rows, key=lambda row: abs(row[0][2].center().y() - pos.y()))
        best_row.sort(key=lambda entry: entry[2].left())

        for _item_id, item_index, rect in best_row:
            if pos.x() < rect.center().x():
                return (max(category_rect.left() + 4, rect.left() - 2), rect.top(), item_index)
        last_rect = best_row[-1][2]
        return (
            last_rect.right() + 2,
            last_rect.top(),
            best_row[-1][1] + 1,
        )

    def _clear_drop_indicator(self) -> None:
        self.drop_indicator_x = None
        self.drop_indicator_y = None
        self.drop_indicator_h = None
        self.target_flat_index = None
        self.target_cat_index = None
        self.target_cat_id = None
        self.target_item_index = None
        self.is_category_drag = False
        self._drop_request = None
        self._drop_operation = None
        self.update()
        if hasattr(self, "container"):
            self.container.update()

    def calculate_item_drop_slot(self, pos: QPoint, dragged_item_id: str) -> Tuple[int, str, int]:
        if not self.manager:
            return (10, "project", 0)

        item_geoms: List[Tuple[str, str, QRect]] = []
        for category in self.manager.get_ordered_categories():
            if (
                category.toolbar_id != self.toolbar_id
                or not category.visible
                or category.id not in self.category_widgets
            ):
                continue
            category_widget = self.category_widgets[category.id]
            for item_id in category.item_ids:
                widget = category_widget.item_widgets.get(item_id)
                if (
                    item_id == dragged_item_id
                    or item_id not in self.manager.items
                    or not self.manager.items[item_id].visible
                    or widget is None
                    or widget.isHidden()
                ):
                    continue
                top_left = widget.mapTo(self.container, QPoint(0, 0))
                item_geoms.append(
                    (item_id, category.id, QRect(top_left, widget.size()))
                )

        if not item_geoms:
            fallback = next(
                (
                    category for category in self.manager.get_ordered_categories()
                    if category.toolbar_id == self.toolbar_id
                    and category.visible
                    and category.id in self.category_widgets
                ),
                None,
            )
            if fallback is None:
                return (10, "", 0)
            self.drop_indicator_x = 10
            self.drop_indicator_y = 2
            self.drop_indicator_h = 26
            self.target_flat_index = 0
            return (10, fallback.id, 0)

        rows: List[Dict[str, Any]] = []
        for idx, (i_id, category_id, r) in enumerate(item_geoms):
            cy = r.center().y()
            placed = False
            for row in rows:
                if abs(row["cy"] - cy) < 14:
                    row["items"].append((idx, i_id, category_id, r))
                    placed = True
                    break
            if not placed:
                rows.append({
                    "cy": cy,
                    "top": r.top(),
                    "height": r.height(),
                    "items": [(idx, i_id, category_id, r)],
                })
        rows.sort(key=lambda rw: rw["cy"])

        best_row = min(rows, key=lambda rw: abs(rw["cy"] - pos.y()))
        row_items = sorted(best_row["items"], key=lambda entry: entry[3].left())

        target_idx: Optional[int] = None
        for idx, _item_id, _category_id, r in row_items:
            if pos.x() < r.center().x():
                slot_x = max(4, r.left() - 2)
                target_idx = idx
                break
        if target_idx is None:
            last_idx, _last_id, _last_cat_id, last_r = row_items[-1]
            slot_x = last_r.right() + 2
            target_idx = last_idx + 1

        self.drop_indicator_x = slot_x
        self.drop_indicator_y = best_row["top"]
        self.drop_indicator_h = best_row["height"]

        if target_idx < len(item_geoms):
            ref_id, target_cat, _rect = item_geoms[target_idx]
            category_items = self.manager.categories[target_cat].item_ids
            target_item_index = category_items.index(ref_id)
        else:
            _ref_id, target_cat, _rect = item_geoms[-1]
            target_item_index = len(self.manager.categories[target_cat].item_ids)

        self.target_flat_index = None
        return (slot_x, target_cat, target_item_index)

    def calculate_category_drop_slot(self, pos: QPoint, dragged_cat_id: str) -> Tuple[int, int]:
        if not self.manager:
            return (10, 0)

        cats = [
            cat for cat in self.manager.get_ordered_categories()
            if cat.id != dragged_cat_id
            and cat.visible
            and cat.toolbar_id == self.toolbar_id
            and (
                self.manager.is_edit_mode
                or any(
                    item_id in self.manager.items and self.manager.items[item_id].visible
                    for item_id in cat.item_ids
                )
            )
        ]
        if not cats:
            return (10, 0)

        entries: List[Tuple[str, QRect, int]] = []
        for local_idx, cat in enumerate(cats):
            widget = getattr(self, "category_widgets", {}).get(cat.id)
            if widget and widget.isVisible():
                entries.append((cat.id, widget.geometry(), local_idx))

        if not entries:
            return (10, 0)

        rows: List[List[Tuple[str, QRect, int]]] = []
        for entry in entries:
            rect = entry[1]
            for row in rows:
                if abs(row[0][1].center().y() - rect.center().y()) < 16:
                    row.append(entry)
                    break
            else:
                rows.append([entry])
        rows.sort(key=lambda row: row[0][1].center().y())
        best_row = min(rows, key=lambda row: abs(row[0][1].center().y() - pos.y()))

        best_row.sort(key=lambda entry: entry[1].left())
        for cat_id, rect, global_idx in best_row:
            if pos.x() < rect.center().x():
                return (max(4, rect.left() - 3), global_idx)
        last_cat_id, last_rect, last_global_idx = best_row[-1]
        return (last_rect.right() + 4, last_global_idx + 1)

    def _render_drop_indicator(self, painter: QPainter) -> None:
        if self.drop_indicator_x is None:
            return

        x = self.drop_indicator_x
        top_y = self.drop_indicator_y if self.drop_indicator_y is not None else 2
        h = self.drop_indicator_h if self.drop_indicator_h is not None else (self.height() - 4)
        bot_y = top_y + h

        # Outer subtle glow
        glow_pen = QPen(QColor(147, 197, 253, 110), 7)
        painter.setPen(glow_pen)
        painter.drawLine(x, top_y, x, bot_y)

        # Center vivid insertion line
        line_pen = QPen(QColor("#3b82f6"), 3)
        painter.setPen(line_pen)
        painter.drawLine(x, top_y, x, bot_y)

        # Arrowheads
        painter.setBrush(QBrush(QColor("#60a5fa")))
        painter.setPen(QPen(QColor("#ffffff"), 1))

        arrow_w = 5
        arrow_h = 6

        # Top downward arrow
        top_poly = QPolygon([
            QPoint(x - arrow_w, top_y),
            QPoint(x + arrow_w, top_y),
            QPoint(x, top_y + arrow_h),
        ])
        painter.drawPolygon(top_poly)

        # Bottom upward arrow
        bot_poly = QPolygon([
            QPoint(x - arrow_w, bot_y),
            QPoint(x + arrow_w, bot_y),
            QPoint(x, bot_y - arrow_h),
        ])
        painter.drawPolygon(bot_poly)

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        if (
            self.drop_indicator_x is not None
            and (self.is_edit_mode or self.is_category_drag)
            and not hasattr(self, "container")
        ):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._render_drop_indicator(painter)
            painter.end()


class ToolbarEditModeBanner(QFrame):
    """
    Prominent notification banner displayed while toolbar customization mode is active.
    Provides clear instructions, 'Zakończ personalizację', and 'Przywróć domyślne' buttons.
    """

    def __init__(self, manager: "ToolbarManager", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.manager = manager
        self.setFixedHeight(36)
        self.setStyleSheet("""
            ToolbarEditModeBanner {
                background-color: #1e293b;
                border-top: 1px solid #3b82f6;
                border-bottom: 1px solid #3b82f6;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 11px;
                font-weight: 500;
                background: transparent;
            }
            QPushButton {
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 12px;
                min-height: 24px;
            }
            QPushButton#btn_done {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #60a5fa;
            }
            QPushButton#btn_done:hover {
                background-color: #1d4ed8;
                border-color: #93c5fd;
            }
            QPushButton#btn_reset {
                background-color: #334155;
                color: #e2e8f0;
                border: 1px solid #475569;
            }
            QPushButton#btn_reset:hover {
                background-color: #475569;
                color: #ffffff;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(IconFactory.get_icon("layout", 16).pixmap(16, 16))
        layout.addWidget(icon_lbl)

        info_lbl = QLabel(
            "<b>TRYB PERSONALIZACJI PASKÓW:</b> "
            "Przeciągaj przyciski, aby zmienić ich kolejność w tej samej kategorii; "
            "uchwyt (⋮⋮) przenosi całą kategorię. "
            "Pozostałe ustawienia oraz pełny układ zmienisz w „Dostosuj paski narzędzi”."
        )
        layout.addWidget(info_lbl, 1)

        btn_reset = QPushButton("↺ Przywróć domyślne")
        btn_reset.setObjectName("btn_reset")
        btn_reset.setToolTip(tr("toolbar.reset_tooltip"))
        btn_reset.clicked.connect(lambda: self.manager.reset_to_default(save=True))
        layout.addWidget(btn_reset)

        btn_done = QPushButton("✓ Zakończ personalizację")
        btn_done.setObjectName("btn_done")
        btn_done.setToolTip(tr("toolbar.done_tooltip"))
        btn_done.clicked.connect(lambda: self.manager.set_edit_mode(False))
        layout.addWidget(btn_done)

        self.hide()


class ToolbarVisibilityDialog(QDialog):
    """
    Dedicated dialog for managing individual toolbar button visibility.
    Displays all available buttons in their current order, allows independent
    toggling, real-time search filtering, mass show/hide, and restoring defaults.
    """

    def __init__(self, manager: "ToolbarManager", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle(tr("toolbar.visibility_title"))
        self.setMinimumSize(480, 560)
        self.resize(520, 600)
        self.setModal(True)

        # Working copy of visibility state {item_id: bool}
        self.working_visibility: Dict[str, bool] = {
            i_id: item.visible for i_id, item in self.manager.items.items()
        }

        self._init_ui()
        self._populate_list()
        self._update_summary()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #18181b;
                color: #e4e4e7;
            }
            QLabel {
                color: #e4e4e7;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #27272a;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
            QListWidget {
                background-color: #202024;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 4px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
                margin-bottom: 1px;
            }
            QListWidget::item:hover {
                background-color: #2e2e33;
            }
            QListWidget::item:selected {
                background-color: #1e3a5f;
                color: #ffffff;
            }
            QPushButton {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                color: #ffffff;
                border-color: #60a5fa;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QPushButton#btn_primary {
                background-color: #2563eb;
                border-color: #3b82f6;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton#btn_primary:hover {
                background-color: #1d4ed8;
                border-color: #60a5fa;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header description
        lbl_title = QLabel(tr("toolbar.visibility_header"))
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f4f4f5;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(tr("toolbar.visibility_description"))
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        layout.addWidget(lbl_desc)

        # Search filter input
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 " + tr("toolbar.search"))
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self._filter_list)
        layout.addWidget(self.txt_search)

        # Action buttons bar: Show all / Hide all / Reset
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        btn_show_all = QPushButton("👁 " + tr("toolbar.show_all"))
        btn_show_all.setToolTip(tr("toolbar.show_all_tooltip"))
        btn_show_all.clicked.connect(self._show_all)
        action_bar.addWidget(btn_show_all)

        btn_hide_all = QPushButton("🚫 " + tr("toolbar.hide_all"))
        btn_hide_all.setToolTip(tr("toolbar.hide_all_tooltip"))
        btn_hide_all.clicked.connect(self._hide_all)
        action_bar.addWidget(btn_hide_all)

        btn_reset = QPushButton("↺ " + tr("toolbar.restore_defaults"))
        btn_reset.setToolTip(tr("toolbar.reset_visibility_tooltip"))
        btn_reset.clicked.connect(self._reset_defaults)
        action_bar.addWidget(btn_reset)

        action_bar.addStretch()
        layout.addLayout(action_bar)

        # Buttons list
        self.list_widget = QListWidget()
        self.list_widget.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget, 1)

        # Footer: Summary & Apply / OK / Cancel
        footer_layout = QHBoxLayout()
        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet("color: #93c5fd; font-weight: 500; font-size: 11px;")
        footer_layout.addWidget(self.lbl_summary)

        footer_layout.addStretch()

        btn_apply = QPushButton("Zastosuj")
        btn_apply.setToolTip(tr("toolbar.apply_tooltip"))
        btn_apply.clicked.connect(self._apply_changes)
        footer_layout.addWidget(btn_apply)

        btn_cancel = QPushButton("Anuluj")
        btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(btn_cancel)

        btn_ok = QPushButton("Zapisz")
        btn_ok.setObjectName("btn_primary")
        btn_ok.clicked.connect(self._accept_and_save)
        footer_layout.addWidget(btn_ok)

        layout.addLayout(footer_layout)

    def _populate_list(self) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        # Display buttons in current item_order
        for i_id in self.manager.item_order:
            item_def = self.manager.items.get(i_id)
            if not item_def:
                continue

            icon = IconFactory.get_icon(item_def.icon_name, 20)
            list_item = QListWidgetItem(icon, f"  {item_def.label}")
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

            is_visible = self.working_visibility.get(i_id, item_def.visible)
            list_item.setCheckState(Qt.CheckState.Checked if is_visible else Qt.CheckState.Unchecked)
            list_item.setData(Qt.ItemDataRole.UserRole, i_id)
            list_item.setToolTip(f"{item_def.label} — {'Widoczny na pasku' if is_visible else 'Ukryty'}")

            self.list_widget.addItem(list_item)

        self.list_widget.blockSignals(False)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        i_id = item.data(Qt.ItemDataRole.UserRole)
        if i_id:
            is_checked = item.checkState() == Qt.CheckState.Checked
            self.working_visibility[i_id] = is_checked
            label = item.text().strip()
            item.setToolTip(f"{label} — {'Widoczny na pasku' if is_checked else 'Ukryty'}")
            self._update_summary()

    def _update_summary(self) -> None:
        total = len(self.working_visibility)
        vis_count = sum(1 for v in self.working_visibility.values() if v)
        self.lbl_summary.setText(f"Widoczne: {vis_count} / {total} przycisków")

    def _filter_list(self, query: str) -> None:
        q = query.strip().lower()
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            i_id = it.data(Qt.ItemDataRole.UserRole) or ""
            text = it.text().lower()
            match = not q or q in text or q in i_id.lower()
            it.setHidden(not match)

    def _show_all(self) -> None:
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            it.setCheckState(Qt.CheckState.Checked)
            i_id = it.data(Qt.ItemDataRole.UserRole)
            if i_id:
                self.working_visibility[i_id] = True
        self.list_widget.blockSignals(False)
        self._update_summary()

    def _hide_all(self) -> None:
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            it.setCheckState(Qt.CheckState.Unchecked)
            i_id = it.data(Qt.ItemDataRole.UserRole)
            if i_id:
                self.working_visibility[i_id] = False
        self.list_widget.blockSignals(False)
        self._update_summary()

    def _reset_defaults(self) -> None:
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            it.setCheckState(Qt.CheckState.Checked)
            i_id = it.data(Qt.ItemDataRole.UserRole)
            if i_id:
                self.working_visibility[i_id] = True
        self.list_widget.blockSignals(False)
        self._update_summary()

    def _apply_changes(self) -> None:
        self.manager.set_items_visibility(self.working_visibility, save=False)

    def _accept_and_save(self) -> None:
        self.manager.set_items_visibility(self.working_visibility, save=True)
        self.accept()


class ToolbarItemListWidget(QListWidget):
    """Item list whose drag payload is understood only by the toolbar customizer."""

    def __init__(self, dialog: "ToolbarCustomizerDialog", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.dialog = dialog
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def mimeData(self, items: List[QListWidgetItem]) -> QMimeData:
        mime_data = super().mimeData(items)
        if items:
            item_id = items[0].data(Qt.ItemDataRole.UserRole)
            item = self.dialog.working_items.get(str(item_id))
            category_id = item.category_id if item else None
            category = self.dialog.working_categories.get(category_id or "")
            if item_id and category:
                request = ToolbarDragRequest(
                    element_type=DragElementType.BUTTON,
                    element_id=str(item_id),
                    context=DragContext.CUSTOMIZER,
                    allowed_operations=(
                        ToolbarDragOperation.BUTTON_REORDER,
                        ToolbarDragOperation.BUTTON_REASSIGN,
                    ),
                    source_category_id=category.id,
                    source_toolbar_id=category.toolbar_id,
                )
                mime_data.setData(
                    "application/x-toolbar-config-item", request.to_bytes()
                )
        return mime_data

    def dragEnterEvent(self, event: Any) -> None:
        request = self.dialog.drag_request_from_mime(event.mimeData())
        category_id = request.source_category_id if request else None
        operation = self.dialog.operation_for_request(request, category_id)
        if (
            request is not None
            and operation is ToolbarDragOperation.BUTTON_REORDER
            and self.dialog.validate_customizer_drag(
                request, operation, category_id
            )
        ):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event: Any) -> None:
        request = self.dialog.drag_request_from_mime(event.mimeData())
        category_id = request.source_category_id if request else None
        operation = self.dialog.operation_for_request(request, category_id)
        if (
            request is not None
            and operation is ToolbarDragOperation.BUTTON_REORDER
            and self.dialog.validate_customizer_drag(
                request, operation, category_id
            )
        ):
            super().dragMoveEvent(event)
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: Any) -> None:
        request = self.dialog.drag_request_from_mime(event.mimeData())
        category_id = request.source_category_id if request else None
        operation = self.dialog.operation_for_request(request, category_id)
        if (
            request is None
            or operation is not ToolbarDragOperation.BUTTON_REORDER
            or not self.dialog.validate_customizer_drag(
                request, operation, category_id
            )
        ):
            event.ignore()
            return
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(pos)
        target_index = self.count()
        if target_item is not None:
            target_index = self.row(target_item)
            if pos.y() > self.visualItemRect(target_item).center().y():
                target_index += 1
        if not self.dialog.move_working_item_to_category(
            request.element_id, category_id, target_index
        ):
            event.ignore()
            return
        self.dialog._pending_category_id = category_id
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        self.dialog._item_drag_active = True
        try:
            super().startDrag(supported_actions)
        finally:
            self.dialog._item_drag_active = False
            selected_category = (
                self.dialog._pending_category_id
                or self.dialog._get_current_category_id()
            )
            self.dialog._pending_category_id = None
            self.dialog._populate_all(select_cat_id=selected_category)


class ToolbarCustomizerTabBar(QTabBar):
    """Lets an item drag switch toolbar tabs before dropping onto a category."""

    def _customizer_drag_request(self, mime: QMimeData) -> Optional[ToolbarDragRequest]:
        for mime_type in (
            "application/x-toolbar-config-item",
            "application/x-toolbar-config-category",
        ):
            if mime.hasFormat(mime_type):
                request = ToolbarDragRequest.from_bytes(bytes(mime.data(mime_type)))
                if request is not None and request.context is DragContext.CUSTOMIZER:
                    return request
        return None

    def dragEnterEvent(self, event: Any) -> None:
        if self._customizer_drag_request(event.mimeData()) is not None:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: Any) -> None:
        if self._customizer_drag_request(event.mimeData()) is not None:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            tab_index = self.tabAt(pos)
            if tab_index >= 0:
                tab_widget = self.parentWidget()
                if isinstance(tab_widget, QTabWidget):
                    tab_widget.setCurrentIndex(tab_index)
                event.acceptProposedAction()
            else:
                event.ignore()
            return
        super().dragMoveEvent(event)


class ToolbarCategoryListWidget(QListWidget):
    """Category list handling typed category moves and button reassignment."""

    def __init__(self, dialog: "ToolbarCustomizerDialog", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.dialog = dialog
        self.toolbar_id = "main"
        self.setDragEnabled(True)
        self.setAcceptDrops(True)

    def mimeData(self, items: List[QListWidgetItem]) -> QMimeData:
        mime_data = super().mimeData(items)
        if items:
            category_id = items[0].data(Qt.ItemDataRole.UserRole)
            category = self.dialog.working_categories.get(category_id)
            if category:
                request = ToolbarDragRequest(
                    element_type=DragElementType.CATEGORY,
                    element_id=category.id,
                    context=DragContext.CUSTOMIZER,
                    allowed_operations=(
                        ToolbarDragOperation.CATEGORY_REORDER,
                        ToolbarDragOperation.CATEGORY_MOVE,
                    ),
                    source_category_id=category.id,
                    source_toolbar_id=category.toolbar_id,
                )
                mime_data.setData(
                    "application/x-toolbar-config-category", request.to_bytes()
                )
        return mime_data

    def dragEnterEvent(self, event: Any) -> None:
        request = self.dialog.drag_request_from_mime(event.mimeData())
        operation, target_id = self._operation_at(event, request)
        if (
            request is not None
            and operation is not None
            and self.dialog.validate_customizer_drag(
                request, operation, target_id, self.toolbar_id
            )
        ):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event: Any) -> None:
        request = self.dialog.drag_request_from_mime(event.mimeData())
        operation, target_id = self._operation_at(event, request)
        if (
            request is not None
            and operation is not None
            and self.dialog.validate_customizer_drag(
                request, operation, target_id, self.toolbar_id
            )
        ):
            super().dragMoveEvent(event)
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: Any) -> None:
        mime_data = event.mimeData()
        request = self.dialog.drag_request_from_mime(mime_data)
        operation, target_id = self._operation_at(event, request)
        if (
            request is None
            or operation is None
            or not self.dialog.validate_customizer_drag(
                request, operation, target_id, self.toolbar_id
            )
        ):
            event.ignore()
            return
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(pos)
        target_index = self.count()
        if target_item is not None:
            target_index = self.row(target_item)
            if pos.y() > self.visualItemRect(target_item).center().y():
                target_index += 1

        if request.element_type is DragElementType.BUTTON:
            if not self.dialog.move_working_item_to_category(
                request.element_id, target_id
            ):
                event.ignore()
                return
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return

        if not self.dialog.move_working_category(
            request.element_id, self.toolbar_id, target_index
        ):
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def _operation_at(
        self, event: Any, request: Optional[ToolbarDragRequest]
    ) -> Tuple[Optional[ToolbarDragOperation], Optional[str]]:
        if request is None:
            return None, None
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(pos)
        target_id = (
            target_item.data(Qt.ItemDataRole.UserRole)
            if target_item is not None
            else self.toolbar_id
        )
        if request.element_type is DragElementType.BUTTON:
            return None, target_id
        if request.element_type is DragElementType.CATEGORY:
            operation = (
                ToolbarDragOperation.CATEGORY_REORDER
                if request.source_toolbar_id == self.toolbar_id
                else ToolbarDragOperation.CATEGORY_MOVE
            )
            return operation, target_id
        return None, None

class ToolbarCustomizerDialog(QDialog):
    """
    Dialog for customizing toolbar categories, secondary toolbar assignment,
    button order, category assignments, and individual element visibility.
    """

    def __init__(self, manager: "ToolbarManager", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Dostosuj paski narzędzi")
        self.setMinimumSize(750, 560)
        self.resize(780, 590)
        self.setModal(True)
        self._item_drag_active = False
        self._pending_category_id: Optional[str] = None

        self.working_category_order: List[str] = [cat.id for cat in self.manager.get_ordered_categories()]
        self.working_categories: Dict[str, ToolbarCategoryDef] = {}
        for cat_id, cat in self.manager.categories.items():
            self.working_categories[cat_id] = ToolbarCategoryDef(
                id=cat.id,
                title=cat.title,
                icon_name=cat.icon_name,
                visible=cat.visible,
                order=cat.order,
                toolbar_id=cat.toolbar_id,
                default_toolbar_id=cat.default_toolbar_id,
                item_ids=list(cat.item_ids),
                default_item_ids=list(cat.default_item_ids),
            )

        self.working_items: Dict[str, ToolbarItemDef] = {}
        for item_id, item in self.manager.items.items():
            self.working_items[item_id] = ToolbarItemDef(
                id=item.id,
                label=item.label,
                category_id=item.category_id,
                default_category_id=item.default_category_id,
                icon_name=item.icon_name,
                tooltip=item.tooltip,
                visible=item.visible,
                order=item.order,
                action=item.action,
                widget=item.widget,
                button=item.button,
            )

        self.working_secondary_visible = self.manager.secondary_toolbar_visible

        self._init_ui()
        self._populate_all()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #18181b;
                color: #e4e4e7;
            }
            QLabel {
                color: #e4e4e7;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #3f3f46;
                border-radius: 6px;
                background-color: #1f1f23;
                padding: 4px;
            }
            QTabBar::tab {
                background-color: #27272a;
                color: #a1a1aa;
                padding: 6px 14px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #1f1f23;
                color: #60a5fa;
                font-weight: bold;
                border: 1px solid #3f3f46;
                border-bottom: none;
            }
            QListWidget {
                background-color: #27272a;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 4px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #3f3f46;
            }
            QListWidget::item:selected {
                background-color: #1e3a5f;
                color: #ffffff;
                border: 1px solid #3b82f6;
            }
            QPushButton {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                color: #ffffff;
                border-color: #60a5fa;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QComboBox {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 12px;
            }
            QCheckBox {
                color: #f4f4f5;
                font-size: 12px;
                font-weight: 500;
                spacing: 8px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header with Secondary Toolbar toggle
        header_box = QHBoxLayout()
        lbl_info = QLabel("Dostosuj kolejność i widoczność kategorii na paskach narzędzi:")
        lbl_info.setStyleSheet("font-size: 13px; font-weight: bold; color: #f4f4f5;")
        header_box.addWidget(lbl_info)

        header_box.addStretch()

        self.chk_secondary_toolbar = QCheckBox("Pokaż dodatkowy pasek narzędzi (dolny)")
        self.chk_secondary_toolbar.setChecked(self.working_secondary_visible)
        self.chk_secondary_toolbar.toggled.connect(self._on_secondary_toolbar_toggled)
        header_box.addWidget(self.chk_secondary_toolbar)

        main_layout.addLayout(header_box)

        # Center split: Left (Categories by Toolbar Tab) | Right (Category Items)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # 1. Left panel: Tabs for Main and Secondary Toolbars
        cat_box = QVBoxLayout()
        cat_box.setSpacing(8)

        self.tab_toolbars = QTabWidget()
        self.tab_toolbars.setTabBar(ToolbarCustomizerTabBar())
        self.tab_toolbars.tabBar().setAcceptDrops(True)
        self.tab_toolbars.currentChanged.connect(self._on_toolbar_tab_changed)

        # Tab: Main Toolbar
        tab_main_widget = QWidget()
        tab_main_lay = QVBoxLayout(tab_main_widget)
        tab_main_lay.setContentsMargins(4, 4, 4, 4)
        self.list_main_cats = ToolbarCategoryListWidget(self)
        self.list_main_cats.toolbar_id = "main"
        self.list_main_cats.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.list_main_cats.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_main_cats.itemSelectionChanged.connect(self._on_category_selected)
        self.list_main_cats.itemChanged.connect(self._on_category_item_changed)
        self.list_main_cats.model().rowsMoved.connect(self._on_categories_reordered)
        tab_main_lay.addWidget(self.list_main_cats)
        self.tab_toolbars.addTab(tab_main_widget, "Pasek główny (Górny)")

        # Tab: Secondary Toolbar
        tab_sec_widget = QWidget()
        tab_sec_lay = QVBoxLayout(tab_sec_widget)
        tab_sec_lay.setContentsMargins(4, 4, 4, 4)
        self.list_sec_cats = ToolbarCategoryListWidget(self)
        self.list_sec_cats.toolbar_id = "secondary"
        self.list_sec_cats.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.list_sec_cats.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_sec_cats.itemSelectionChanged.connect(self._on_category_selected)
        self.list_sec_cats.itemChanged.connect(self._on_category_item_changed)
        self.list_sec_cats.model().rowsMoved.connect(self._on_categories_reordered)
        tab_sec_lay.addWidget(self.list_sec_cats)
        self.tab_toolbars.addTab(tab_sec_widget, "Pasek dodatkowy (Dolny)")

        cat_box.addWidget(self.tab_toolbars)

        # Category action buttons: Up/Down + Move to other toolbar
        cat_btn_layout = QHBoxLayout()
        self.btn_cat_up = QPushButton("▲ W górę")
        self.btn_cat_up.clicked.connect(self._move_category_up)
        self.btn_cat_down = QPushButton("▼ W dół")
        self.btn_cat_down.clicked.connect(self._move_category_down)
        cat_btn_layout.addWidget(self.btn_cat_up)
        cat_btn_layout.addWidget(self.btn_cat_down)
        cat_box.addLayout(cat_btn_layout)

        self.btn_switch_toolbar = QPushButton("⇄ Przenieś kategorię na drugi pasek")
        self.btn_switch_toolbar.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                border: 1px solid #3b82f6;
                color: #60a5fa;
            }
            QPushButton:hover {
                background-color: #1e3a5f;
                color: #ffffff;
            }
        """)
        self.btn_switch_toolbar.clicked.connect(self._switch_category_toolbar)
        cat_box.addWidget(self.btn_switch_toolbar)

        content_layout.addLayout(cat_box, 1)

        # 2. Right panel: Items of selected category
        item_box = QVBoxLayout()
        item_box.setSpacing(8)
        self.lbl_items_header = QLabel("Elementy w wybranej kategorii:")
        self.lbl_items_header.setStyleSheet("font-weight: 600; color: #a1a1aa;")
        item_box.addWidget(self.lbl_items_header)

        self.list_items = ToolbarItemListWidget(self)
        self.list_items.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.list_items.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_items.setDropIndicatorShown(True)
        self.list_items.itemChanged.connect(self._on_item_checkbox_changed)
        self.list_items.model().rowsMoved.connect(self._on_items_reordered)
        item_box.addWidget(self.list_items)

        # Item actions: Up/Down + Move to Category
        item_btn_layout = QHBoxLayout()
        self.btn_item_up = QPushButton("▲ W górę")
        self.btn_item_up.clicked.connect(self._move_item_up)
        self.btn_item_down = QPushButton("▼ W dół")
        self.btn_item_down.clicked.connect(self._move_item_down)
        item_btn_layout.addWidget(self.btn_item_up)
        item_btn_layout.addWidget(self.btn_item_down)
        item_box.addLayout(item_btn_layout)

        move_box = QHBoxLayout()
        move_box.setSpacing(6)
        lbl_move = QLabel("Przenieś do:")
        lbl_move.setStyleSheet("color: #a1a1aa;")
        move_box.addWidget(lbl_move)

        self.combo_target_cat = QComboBox()
        move_box.addWidget(self.combo_target_cat, 1)

        self.btn_move_to_cat = QPushButton("Przenieś")
        self.btn_move_to_cat.clicked.connect(self._move_item_to_target_category)
        move_box.addWidget(self.btn_move_to_cat)
        item_box.addLayout(move_box)

        content_layout.addLayout(item_box, 1)
        main_layout.addLayout(content_layout)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        self.btn_reset = QPushButton("Przywróć domyślne")
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #3f3f46;
                color: #f4f4f5;
            }
            QPushButton:hover {
                background-color: #52525b;
                border-color: #ef4444;
            }
        """)
        self.btn_reset.clicked.connect(self._reset_to_default)
        bottom_layout.addWidget(self.btn_reset)

        bottom_layout.addStretch()

        self.btn_apply = QPushButton("Zastosuj")
        self.btn_apply.clicked.connect(self._apply_changes)
        bottom_layout.addWidget(self.btn_apply)

        self.btn_cancel = QPushButton("Anuluj")
        self.btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton("OK")
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #60a5fa;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_ok.clicked.connect(self._accept_and_save)
        bottom_layout.addWidget(self.btn_ok)

        main_layout.addLayout(bottom_layout)

    def _get_active_cat_list(self) -> QListWidget:
        return self.list_main_cats if self.tab_toolbars.currentIndex() == 0 else self.list_sec_cats

    def _on_toolbar_tab_changed(self, idx: int) -> None:
        if not hasattr(self, "list_items") or self._item_drag_active:
            return
        self._on_category_selected()

    def _on_secondary_toolbar_toggled(self, checked: bool) -> None:
        self.working_secondary_visible = checked

    def _populate_all(self, select_cat_id: Optional[str] = None) -> None:
        self._populate_category_lists(select_cat_id)
        self._update_target_combobox()

    def _populate_category_lists(self, select_cat_id: Optional[str] = None) -> None:
        self.list_main_cats.blockSignals(True)
        self.list_sec_cats.blockSignals(True)
        self.list_main_cats.clear()
        self.list_sec_cats.clear()

        for cat_id in self.working_category_order:
            cat = self.working_categories.get(cat_id)
            if not cat:
                continue

            icon = IconFactory.get_icon(cat.icon_name, 16)
            item_count = len(cat.item_ids)
            label = f"{cat.title} ({item_count})"

            item = QListWidgetItem(icon, label)
            item.setData(Qt.ItemDataRole.UserRole, cat_id)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsDropEnabled
            )
            item.setCheckState(Qt.CheckState.Checked if cat.visible else Qt.CheckState.Unchecked)

            if cat.toolbar_id == "secondary":
                self.list_sec_cats.addItem(item)
            else:
                self.list_main_cats.addItem(item)

        self.list_main_cats.blockSignals(False)
        self.list_sec_cats.blockSignals(False)

        # Select category
        target_list = self._get_active_cat_list()
        if select_cat_id:
            for l_w, t_idx in [(self.list_main_cats, 0), (self.list_sec_cats, 1)]:
                for r in range(l_w.count()):
                    if l_w.item(r).data(Qt.ItemDataRole.UserRole) == select_cat_id:
                        self.tab_toolbars.setCurrentIndex(t_idx)
                        l_w.setCurrentRow(r)
                        return

        if target_list.count() > 0:
            target_list.setCurrentRow(0)
        else:
            other_list = self.list_sec_cats if target_list == self.list_main_cats else self.list_main_cats
            if other_list.count() > 0:
                self.tab_toolbars.setCurrentIndex(1 if other_list == self.list_sec_cats else 0)
                other_list.setCurrentRow(0)
            else:
                self._populate_items(None)

    def _get_current_category_id(self) -> Optional[str]:
        curr = self._get_active_cat_list().currentItem()
        if curr:
            return curr.data(Qt.ItemDataRole.UserRole)
        return None

    def drag_request_from_mime(self, mime: QMimeData) -> Optional[ToolbarDragRequest]:
        for mime_type in (
            "application/x-toolbar-config-item",
            "application/x-toolbar-config-category",
        ):
            if mime.hasFormat(mime_type):
                request = ToolbarDragRequest.from_bytes(bytes(mime.data(mime_type)))
                if request is not None and request.context is DragContext.CUSTOMIZER:
                    return request
        return None

    def operation_for_request(
        self, request: Optional[ToolbarDragRequest], target_id: Optional[str]
    ) -> Optional[ToolbarDragOperation]:
        if (
            request is None
            or request.context is not DragContext.CUSTOMIZER
            or not target_id
        ):
            return None
        if request.element_type is DragElementType.CATEGORY:
            target_category = self.working_categories.get(target_id)
            target_toolbar_id = (
                target_category.toolbar_id if target_category else target_id
            )
            if target_toolbar_id not in ("main", "secondary"):
                return None
            return (
                ToolbarDragOperation.CATEGORY_REORDER
                if request.source_toolbar_id == target_toolbar_id
                else ToolbarDragOperation.CATEGORY_MOVE
            )
        if request.element_type is DragElementType.BUTTON:
            target_category = self.working_categories.get(target_id)
            if target_category is None:
                return None
            return (
                ToolbarDragOperation.BUTTON_REORDER
                if request.source_category_id == target_category.id
                else ToolbarDragOperation.BUTTON_REASSIGN
            )
        return None

    def validate_customizer_drag(
        self,
        request: ToolbarDragRequest,
        operation: ToolbarDragOperation,
        target_id: Optional[str],
        target_toolbar_id: Optional[str] = None,
    ) -> bool:
        if not target_id:
            return False
        target_category = self.working_categories.get(target_id)
        resolved_toolbar_id = target_toolbar_id or (
            target_category.toolbar_id if target_category else target_id
        )
        if resolved_toolbar_id not in ("main", "secondary"):
            return False
        return self.manager.validate_drag_operation(
            request.at_target(target_id, resolved_toolbar_id),
            operation,
            target_id=target_id,
            target_toolbar_id=resolved_toolbar_id,
            categories=self.working_categories,
            items=self.working_items,
        )

    def _on_category_selected(self) -> None:
        if not hasattr(self, "list_items"):
            return
        cat_id = self._get_current_category_id()
        self._populate_items(cat_id)
        self._update_target_combobox()

    def _on_category_item_changed(self, item: QListWidgetItem) -> None:
        cat_id = item.data(Qt.ItemDataRole.UserRole)
        if cat_id in self.working_categories:
            self.working_categories[cat_id].visible = (item.checkState() == Qt.CheckState.Checked)

    def _on_categories_reordered(self, *args: Any) -> None:
        main_order = [self.list_main_cats.item(r).data(Qt.ItemDataRole.UserRole) for r in range(self.list_main_cats.count())]
        sec_order = [self.list_sec_cats.item(r).data(Qt.ItemDataRole.UserRole) for r in range(self.list_sec_cats.count())]
        self.working_category_order = main_order + sec_order

    def _switch_category_toolbar(self) -> None:
        cat_id = self._get_current_category_id()
        if not cat_id or cat_id not in self.working_categories:
            return

        cat = self.working_categories[cat_id]
        cat.toolbar_id = "secondary" if cat.toolbar_id == "main" else "main"
        self._populate_all(select_cat_id=cat_id)

    def _populate_items(self, cat_id: Optional[str]) -> None:
        self.list_items.blockSignals(True)
        self.list_items.clear()

        if not cat_id or cat_id not in self.working_categories:
            self.lbl_items_header.setText("Elementy w wybranej kategorii: (brak wyboru)")
            self.list_items.blockSignals(False)
            return

        cat = self.working_categories[cat_id]
        toolbar_name = "Pasek główny" if cat.toolbar_id == "main" else "Pasek dodatkowy"
        self.lbl_items_header.setText(f"Elementy w kategorii: {cat.title} ({toolbar_name})")

        for item_id in cat.item_ids:
            item_def = self.working_items.get(item_id)
            if not item_def:
                continue

            icon = IconFactory.get_icon(item_def.icon_name, 16)
            list_item = QListWidgetItem(icon, item_def.label)
            list_item.setData(Qt.ItemDataRole.UserRole, item_id)
            list_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsDropEnabled
            )
            list_item.setCheckState(Qt.CheckState.Checked if item_def.visible else Qt.CheckState.Unchecked)
            self.list_items.addItem(list_item)

        self.list_items.blockSignals(False)

    def _on_item_checkbox_changed(self, list_item: QListWidgetItem) -> None:
        item_id = list_item.data(Qt.ItemDataRole.UserRole)
        if item_id in self.working_items:
            self.working_items[item_id].visible = (list_item.checkState() == Qt.CheckState.Checked)

    def _on_items_reordered(self, *args: Any) -> None:
        cat_id = self._get_current_category_id()
        if not cat_id or cat_id not in self.working_categories:
            return

        new_item_order: List[str] = []
        for r in range(self.list_items.count()):
            item_id = self.list_items.item(r).data(Qt.ItemDataRole.UserRole)
            if item_id:
                new_item_order.append(item_id)
        self.working_categories[cat_id].item_ids = new_item_order
        for item_id in new_item_order:
            if item_id in self.working_items:
                self.working_items[item_id].category_id = cat_id

    def _update_target_combobox(self) -> None:
        curr_cat_id = self._get_current_category_id()
        self.combo_target_cat.clear()
        for cat_id in self.working_category_order:
            cat = self.working_categories.get(cat_id)
            if cat and cat_id != curr_cat_id:
                loc = "Główny" if cat.toolbar_id == "main" else "Dodatkowy"
                self.combo_target_cat.addItem(f"{cat.title} [{loc}]", cat_id)

    def _move_category_up(self) -> None:
        curr_list = self._get_active_cat_list()
        row = curr_list.currentRow()
        if row > 0:
            cat_id = curr_list.item(row).data(Qt.ItemDataRole.UserRole)
            above_id = curr_list.item(row - 1).data(Qt.ItemDataRole.UserRole)
            idx_cat = self.working_category_order.index(cat_id)
            idx_above = self.working_category_order.index(above_id)
            self.working_category_order[idx_cat], self.working_category_order[idx_above] = (
                self.working_category_order[idx_above],
                self.working_category_order[idx_cat],
            )
            self._populate_all(select_cat_id=cat_id)

    def _move_category_down(self) -> None:
        curr_list = self._get_active_cat_list()
        row = curr_list.currentRow()
        if 0 <= row < curr_list.count() - 1:
            cat_id = curr_list.item(row).data(Qt.ItemDataRole.UserRole)
            below_id = curr_list.item(row + 1).data(Qt.ItemDataRole.UserRole)
            idx_cat = self.working_category_order.index(cat_id)
            idx_below = self.working_category_order.index(below_id)
            self.working_category_order[idx_cat], self.working_category_order[idx_below] = (
                self.working_category_order[idx_below],
                self.working_category_order[idx_cat],
            )
            self._populate_all(select_cat_id=cat_id)

    def _move_item_up(self) -> None:
        cat_id = self._get_current_category_id()
        if not cat_id or cat_id not in self.working_categories:
            return
        row = self.list_items.currentRow()
        cat = self.working_categories[cat_id]
        if row > 0 and row < len(cat.item_ids):
            item_id = cat.item_ids.pop(row)
            cat.item_ids.insert(row - 1, item_id)
            self._populate_items(cat_id)
            self.list_items.setCurrentRow(row - 1)

    def _move_item_down(self) -> None:
        cat_id = self._get_current_category_id()
        if not cat_id or cat_id not in self.working_categories:
            return
        row = self.list_items.currentRow()
        cat = self.working_categories[cat_id]
        if 0 <= row < len(cat.item_ids) - 1:
            item_id = cat.item_ids.pop(row)
            cat.item_ids.insert(row + 1, item_id)
            self._populate_items(cat_id)
            self.list_items.setCurrentRow(row + 1)

    def _move_item_to_target_category(self) -> None:
        curr_cat_id = self._get_current_category_id()
        target_cat_id = self.combo_target_cat.currentData()
        curr_item = self.list_items.currentItem()

        if not curr_cat_id or not target_cat_id or not curr_item:
            return

        item_id = curr_item.data(Qt.ItemDataRole.UserRole)
        if item_id:
            self.move_working_item_to_category(item_id, target_cat_id)

    def move_working_item_to_category(
        self,
        item_id: str,
        target_category_id: str,
        target_index: Optional[int] = None,
    ) -> bool:
        item = self.working_items.get(item_id)
        source_category_id = item.category_id if item else None
        source_category = self.working_categories.get(source_category_id or "")
        target_category = self.working_categories.get(target_category_id)
        if item is None or source_category is None or target_category is None:
            return False

        operation = (
            ToolbarDragOperation.BUTTON_REORDER
            if source_category.id == target_category.id
            else ToolbarDragOperation.BUTTON_REASSIGN
        )
        request = ToolbarDragRequest(
            element_type=DragElementType.BUTTON,
            element_id=item_id,
            context=DragContext.CUSTOMIZER,
            allowed_operations=(
                ToolbarDragOperation.BUTTON_REORDER,
                ToolbarDragOperation.BUTTON_REASSIGN,
            ),
            source_category_id=source_category.id,
            source_toolbar_id=source_category.toolbar_id,
        )
        if not self.validate_customizer_drag(
            request, operation, target_category_id, target_category.toolbar_id
        ):
            return False

        source_items = source_category.item_ids
        try:
            old_index = source_items.index(item_id)
        except ValueError:
            return False

        if source_category is target_category:
            source_items.pop(old_index)
            insertion_index = len(source_items) if target_index is None else target_index
            insertion_index = max(0, min(insertion_index, len(source_items)))
            source_items.insert(insertion_index, item_id)
        else:
            source_items.pop(old_index)
            insertion_index = (
                len(target_category.item_ids)
                if target_index is None
                else max(0, min(target_index, len(target_category.item_ids)))
            )
            target_category.item_ids.insert(insertion_index, item_id)
            item.category_id = target_category_id

        if self._item_drag_active:
            self._pending_category_id = target_category_id
        else:
            self._populate_all(select_cat_id=target_category_id)
        return True

    def move_working_category(
        self, category_id: str, target_toolbar_id: str, target_index: int
    ) -> bool:
        category = self.working_categories.get(category_id)
        if category is None or target_toolbar_id not in ("main", "secondary"):
            return False
        operation = (
            ToolbarDragOperation.CATEGORY_REORDER
            if category.toolbar_id == target_toolbar_id
            else ToolbarDragOperation.CATEGORY_MOVE
        )
        request = ToolbarDragRequest(
            element_type=DragElementType.CATEGORY,
            element_id=category_id,
            context=DragContext.CUSTOMIZER,
            allowed_operations=(
                ToolbarDragOperation.CATEGORY_REORDER,
                ToolbarDragOperation.CATEGORY_MOVE,
            ),
            source_category_id=category_id,
            source_toolbar_id=category.toolbar_id,
        )
        if not self.validate_customizer_drag(
            request, operation, target_toolbar_id, target_toolbar_id
        ):
            return False

        target_order = [
            item_id for item_id in self.working_category_order
            if item_id != category_id
            and self.working_categories[item_id].toolbar_id == target_toolbar_id
        ]
        insertion_index = max(0, min(target_index, len(target_order)))
        if category.toolbar_id == target_toolbar_id:
            source_order = [
                item_id for item_id in self.working_category_order
                if self.working_categories[item_id].toolbar_id == target_toolbar_id
            ]
            source_index = source_order.index(category_id)
            if target_index > source_index:
                insertion_index = max(0, insertion_index - 1)
        target_order.insert(insertion_index, category_id)
        category.toolbar_id = target_toolbar_id
        main_order = [
            item_id for item_id in self.working_category_order
            if item_id != category_id
            and self.working_categories[item_id].toolbar_id == "main"
        ]
        secondary_order = [
            item_id for item_id in self.working_category_order
            if item_id != category_id
            and self.working_categories[item_id].toolbar_id == "secondary"
        ]
        if target_toolbar_id == "main":
            main_order = target_order
        else:
            secondary_order = target_order
        self.working_category_order = main_order + secondary_order
        self._populate_all(select_cat_id=category_id)
        return True

    def _build_layout_payload(self) -> Dict[str, Any]:
        categories_data = []
        for cat_id in self.working_category_order:
            cat = self.working_categories.get(cat_id)
            if cat:
                categories_data.append({
                    "id": cat.id,
                    "visible": cat.visible,
                    "toolbar_id": cat.toolbar_id,
                    "items": list(cat.item_ids),
                })

        item_vis = {item_id: item.visible for item_id, item in self.working_items.items()}

        return {
            "secondary_toolbar_visible": self.working_secondary_visible,
            "categories": categories_data,
            "item_visibility": item_vis,
        }

    def _apply_changes(self) -> None:
        payload = self._build_layout_payload()
        self.manager.apply_layout(payload)

    def _accept_and_save(self) -> None:
        payload = self._build_layout_payload()
        self.manager.apply_layout(payload)
        self.manager.save_layout()
        self.accept()

    def _reset_to_default(self) -> None:
        self.working_category_order = list(self.manager.default_category_order)
        self.working_categories = {}
        for cat_id, cat in self.manager.categories.items():
            self.working_categories[cat_id] = ToolbarCategoryDef(
                id=cat.id,
                title=cat.title,
                icon_name=cat.icon_name,
                visible=True,
                order=cat.order,
                toolbar_id=cat.default_toolbar_id,
                default_toolbar_id=cat.default_toolbar_id,
                item_ids=list(cat.default_item_ids),
                default_item_ids=list(cat.default_item_ids),
            )

        self.working_items = {}
        for item_id, item in self.manager.items.items():
            self.working_items[item_id] = ToolbarItemDef(
                id=item.id,
                label=item.label,
                category_id=item.default_category_id,
                default_category_id=item.default_category_id,
                icon_name=item.icon_name,
                tooltip=item.tooltip,
                visible=True,
                order=item.order,
                action=item.action,
                widget=item.widget,
                button=item.button,
            )

        self.working_secondary_visible = True
        self.chk_secondary_toolbar.setChecked(True)
        self._populate_all()
        self._apply_changes()


class ToolbarManager(QObject):
    """
    Central manager for top toolbars:
    - Modular category widgets and button containers across Main and Secondary toolbars
    - Checkable icon buttons with blue border and active state
    - Separate whole-category and single-item Drag & Drop on the top toolbars
    - ToolbarCustomizerDialog remains a separate full configuration workflow
    - Category and item insertion drop indicators
    - Interactive toolbar edit mode with notification banner and Esc cancellation
    - Context menu for category toggling, edit mode, and reset
    - Persistent configuration via ConfigManager
    """

    layout_changed = pyqtSignal()
    edit_mode_changed = pyqtSignal(bool)
    item_drag_started = pyqtSignal(str)
    category_drag_started = pyqtSignal(str)
    drag_finished = pyqtSignal()

    is_edit_mode: bool = False

    DEFAULT_CATEGORIES: List[Tuple[str, str, str, str, List[str]]] = [
        ("project", "Projekt", "folder", "main", ["new", "open", "save", "export"]),
        ("history", "Historia", "undo", "main", ["undo", "redo"]),
        ("view", "Widok", "grid", "main", ["grid", "fit", "palette"]),
        ("brush", "Pędzel", "brush", "main", ["brush_size", "save_stamp"]),
        ("autotile", "Auto-Tiling", "autotile", "secondary", ["autotile_toggle", "autotile_rules", "autotile_dialog"]),
        ("paths", "Ścieżki", "path", "secondary", ["path_gen_dialog"]),
        ("randomizer", "Randomizer", "randomizer", "secondary", ["variants_toggle", "variants_count", "variants_add", "variants_avoid", "variants_dialog"]),
        ("transforms", "Transformacje", "rotate", "secondary", ["rot_toggle", "flip_toggle", "seed_group"]),
        ("system", "System", "settings", "main", ["settings", "shortcuts", "reset_ui"]),
    ]

    def __init__(
        self,
        toolbar: QToolBar,
        config_manager: ConfigManager,
        secondary_toolbar: Optional[QToolBar] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.toolbar = toolbar
        self.secondary_toolbar = secondary_toolbar
        self.config_manager = config_manager
        self.parent_widget = parent

        self._is_loading: bool = False
        self.secondary_toolbar_visible = True
        self.is_edit_mode = False
        self.edit_banner: Optional[ToolbarEditModeBanner] = None
        self.dragged_item_id: Optional[str] = None
        self.dragged_widget: Optional[QWidget] = None
        self.dragged_category_id: Optional[str] = None
        self.drag_safety = getattr(parent, "drag_safety", None)
        self._item_drag_filters: Dict[str, ToolbarItemEditFilter] = {}

        if hasattr(self.toolbar, "set_manager"):
            self.toolbar.set_manager(self)
        if self.secondary_toolbar and hasattr(self.secondary_toolbar, "set_manager"):
            self.secondary_toolbar.set_manager(self)

        self.categories: Dict[str, ToolbarCategoryDef] = {}
        self.category_order: List[str] = []
        self.default_category_order: List[str] = []
        self.item_order: List[str] = []
        self.default_item_order: List[str] = []
        self.items: Dict[str, ToolbarItemDef] = {}

        self.category_widgets: Dict[str, ToolbarCategoryWidget] = {}

        self._init_default_categories()
        self._setup_toolbar_context_menus()

    def _init_default_categories(self) -> None:
        for idx, (cat_id, title, icon_name, tb_id, default_items) in enumerate(self.DEFAULT_CATEGORIES):
            cat_def = ToolbarCategoryDef(
                id=cat_id,
                title=title,
                icon_name=icon_name,
                visible=True,
                order=idx,
                toolbar_id=tb_id,
                default_toolbar_id=tb_id,
                item_ids=list(default_items),
                default_item_ids=list(default_items),
            )
            self.categories[cat_id] = cat_def
            self.category_order.append(cat_id)
            self.default_category_order.append(cat_id)

            for item_id in default_items:
                if item_id not in self.item_order:
                    self.item_order.append(item_id)
                    self.default_item_order.append(item_id)
                if item_id not in self.items:
                    self.items[item_id] = ToolbarItemDef(
                        id=item_id,
                        label=item_id,
                        category_id=cat_id,
                        default_category_id=cat_id,
                        icon_name="grid",
                    )

    def register_item(
        self,
        item_id: str,
        label: str,
        category_id: str,
        action: Optional[QAction] = None,
        widget: Optional[QWidget] = None,
        icon_name: str = "grid",
        tooltip: str = "",
    ) -> ToolbarItemDef:
        """Registers a toolbar action or widget item."""
        btn = None
        if action:
            btn = QToolButton()
            btn.setObjectName(f"toolbar_btn_{item_id}")
            btn.setDefaultAction(action)
            btn.setFixedHeight(26)
            btn.setStyleSheet(TOOLBAR_BUTTON_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if not tooltip:
                tooltip = action.toolTip()

        if widget and hasattr(widget, "setFixedHeight"):
            widget.setFixedHeight(26)

        if item_id in self.items:
            item_def = self.items[item_id]
            item_def.label = label
            item_def.category_id = category_id
            item_def.default_category_id = category_id
            item_def.icon_name = icon_name
            item_def.tooltip = tooltip
            item_def.action = action
            item_def.widget = widget
            item_def.button = btn
        else:
            item_def = ToolbarItemDef(
                id=item_id,
                label=label,
                category_id=category_id,
                default_category_id=category_id,
                icon_name=icon_name,
                tooltip=tooltip,
                visible=True,
                action=action,
                widget=widget,
                button=btn,
            )
            self.items[item_id] = item_def

        if category_id in self.categories:
            cat = self.categories[category_id]
            if item_id not in cat.default_item_ids:
                cat.default_item_ids.append(item_id)
            already_in_any = any(item_id in c.item_ids for c in self.categories.values())
            if not already_in_any and item_id not in cat.item_ids:
                cat.item_ids.append(item_id)

        if item_id not in self.item_order:
            self.item_order.append(item_id)
        if item_id not in self.default_item_order:
            self.default_item_order.append(item_id)

        return item_def

    def get_ordered_categories(self) -> List[ToolbarCategoryDef]:
        res = []
        for cat_id in self.category_order:
            if cat_id in self.categories:
                res.append(self.categories[cat_id])
        return res

    def create_category_drag_request(
        self, category_id: str, context: DragContext
    ) -> Optional[ToolbarDragRequest]:
        category = self.categories.get(category_id)
        if category is None:
            return None
        return ToolbarDragRequest(
            element_type=DragElementType.CATEGORY,
            element_id=category_id,
            context=context,
            allowed_operations=(
                ToolbarDragOperation.CATEGORY_REORDER,
                ToolbarDragOperation.CATEGORY_MOVE,
            ),
            source_category_id=category_id,
            source_toolbar_id=category.toolbar_id,
        )

    def create_button_drag_request(
        self, item_id: str, context: DragContext
    ) -> Optional[ToolbarDragRequest]:
        item = self.items.get(item_id)
        category = self.categories.get(item.category_id) if item else None
        if (
            item is None
            or category is None
            or context is not DragContext.TOOLBAR
            or not self.is_edit_mode
            or item_id not in category.item_ids
        ):
            return None
        return ToolbarDragRequest(
            element_type=DragElementType.BUTTON,
            element_id=item_id,
            context=context,
            allowed_operations=(ToolbarDragOperation.BUTTON_REORDER,),
            source_category_id=category.id,
            source_toolbar_id=category.toolbar_id,
        )

    def validate_drag_operation(
        self,
        request: ToolbarDragRequest,
        operation: ToolbarDragOperation,
        *,
        target_id: str,
        target_toolbar_id: str,
        categories: Optional[Dict[str, ToolbarCategoryDef]] = None,
        items: Optional[Dict[str, ToolbarItemDef]] = None,
    ) -> bool:
        category_map = categories if categories is not None else self.categories
        item_map = items if items is not None else self.items
        if (
            operation not in request.allowed_operations
            or target_toolbar_id not in ("main", "secondary")
            or (
                request.target_id is not None
                and request.target_id != target_id
            )
            or (
                request.target_toolbar_id is not None
                and request.target_toolbar_id != target_toolbar_id
            )
        ):
            return False

        if request.element_type is DragElementType.CATEGORY:
            source = category_map.get(request.element_id)
            if (
                source is None
                or request.source_category_id != request.element_id
                or request.source_toolbar_id != source.toolbar_id
            ):
                return False
            if request.context is DragContext.TOOLBAR and not self.is_edit_mode:
                return False
            if request.context not in (DragContext.TOOLBAR, DragContext.CUSTOMIZER):
                return False
            target_category = category_map.get(target_id)
            if target_category is not None and target_category.toolbar_id != target_toolbar_id:
                return False
            expected = (
                ToolbarDragOperation.CATEGORY_REORDER
                if source.toolbar_id == target_toolbar_id
                else ToolbarDragOperation.CATEGORY_MOVE
            )
            return operation is expected

        if request.element_type is DragElementType.BUTTON:
            item = item_map.get(request.element_id)
            source_category = category_map.get(request.source_category_id or "")
            target_category = category_map.get(target_id)
            if request.context is DragContext.TOOLBAR:
                return (
                    self.is_edit_mode
                    and operation is ToolbarDragOperation.BUTTON_REORDER
                    and operation in request.allowed_operations
                    and item is not None
                    and source_category is not None
                    and target_category is source_category
                    and request.source_toolbar_id == source_category.toolbar_id
                    and target_toolbar_id == source_category.toolbar_id
                    and item.category_id == source_category.id
                    and request.element_id in source_category.item_ids
                )
            if request.context is not DragContext.CUSTOMIZER:
                return False
            if (
                item is None
                or source_category is None
                or target_category is None
                or request.source_toolbar_id != source_category.toolbar_id
                or item.category_id != source_category.id
                or request.element_id not in source_category.item_ids
                or target_category.toolbar_id != target_toolbar_id
            ):
                return False
            expected = (
                ToolbarDragOperation.BUTTON_REORDER
                if source_category.id == target_category.id
                else ToolbarDragOperation.BUTTON_REASSIGN
            )
            return operation is expected

        return False

    def set_edit_banner(self, banner: ToolbarEditModeBanner) -> None:
        self.edit_banner = banner
        banner.setVisible(self.is_edit_mode)

    def set_edit_mode(self, active: bool) -> None:
        if self.is_edit_mode == active:
            return
        if not active:
            for drag_filter in self._item_drag_filters.values():
                drag_filter.cancel()
        self.is_edit_mode = active
        if hasattr(self.toolbar, "set_edit_mode"):
            self.toolbar.set_edit_mode(active)
        if self.secondary_toolbar and hasattr(self.secondary_toolbar, "set_edit_mode"):
            self.secondary_toolbar.set_edit_mode(active)
        for drag_filter in self._item_drag_filters.values():
            drag_filter.update_cursors()
        for toolbar in (self.toolbar, self.secondary_toolbar):
            for grip in getattr(toolbar, "category_grips", {}).values():
                grip.setCursor(
                    Qt.CursorShape.OpenHandCursor
                    if active
                    else Qt.CursorShape.ArrowCursor
                )
                grip.setToolTip(
                    f"Kategoria: {grip.category_def.title}\n"
                    "Przeciągnij nagłówek, aby przenieść całą kategorię."
                    if active
                    else f"Kategoria: {grip.category_def.title}"
                )
        if self.edit_banner:
            self.edit_banner.setVisible(active)
        self.edit_mode_changed.emit(active)

    def toggle_edit_mode(self) -> None:
        self.set_edit_mode(not self.is_edit_mode)

    def move_item(
        self,
        item_id: str,
        target_category_id: Any,
        target_index: Optional[int] = None,
        *,
        rebuild: bool = True,
    ) -> None:
        """
        Moves an item with real in-place reordering.
        Supports both:
          - category reordering: move_item(item_id, target_cat_id, target_index)
          - flat list reordering: move_item(item_id, target_flat_index)
        """
        if isinstance(target_category_id, int) and target_index is None:
            self.move_item_flat(item_id, target_category_id)
            return

        if target_category_id not in self.categories:
            return

        source_cat: Optional[ToolbarCategoryDef] = None
        if item_id in self.items:
            source_cat = self.categories.get(self.items[item_id].category_id)
        if not source_cat:
            for cat in self.categories.values():
                if item_id in cat.item_ids:
                    source_cat = cat
                    break

        target_cat = self.categories[target_category_id]

        if source_cat and item_id in source_cat.item_ids:
            source_cat.item_ids.remove(item_id)

        idx = target_index if target_index is not None else len(target_cat.item_ids)
        idx = max(0, min(idx, len(target_cat.item_ids)))
        target_cat.item_ids.insert(idx, item_id)
        if item_id in self.items:
            self.items[item_id].category_id = target_category_id

        # Keep self.item_order in sync
        if item_id in self.item_order:
            self.item_order.remove(item_id)
        if idx == 0:
            if len(target_cat.item_ids) > 1:
                ref_id = target_cat.item_ids[1]
                ins = self.item_order.index(ref_id) if ref_id in self.item_order else len(self.item_order)
            else:
                ins = len(self.item_order)
        else:
            prev_id = target_cat.item_ids[idx - 1]
            ins = (self.item_order.index(prev_id) + 1) if prev_id in self.item_order else len(self.item_order)
        self.item_order.insert(ins, item_id)

        if rebuild:
            self.build_toolbar()
        self.save_layout()

    def _install_item_drag_filter(self, item_id: str, widget: QWidget) -> None:
        old_filter = self._item_drag_filters.pop(item_id, None)
        if old_filter is not None:
            old_filter.uninstall()
        drag_filter = ToolbarItemEditFilter(item_id, self, widget)
        self._item_drag_filters[item_id] = drag_filter
        drag_filter.install()

    def _clear_item_drag_filters(self) -> None:
        for drag_filter in self._item_drag_filters.values():
            drag_filter.uninstall()
        self._item_drag_filters.clear()

    def move_item_flat(self, item_id: str, target_flat_index: int) -> None:
        """Moves an item directly in the flat unified item order across rows."""
        if item_id not in self.items:
            return
        if item_id in self.item_order:
            curr_idx = self.item_order.index(item_id)
            self.item_order.remove(item_id)
            if target_flat_index > curr_idx:
                target_flat_index -= 1
        target_flat_index = max(0, min(target_flat_index, len(self.item_order)))
        self.item_order.insert(target_flat_index, item_id)

        item = self.items[item_id]
        if item.category_id in self.categories:
            c = self.categories[item.category_id]
            if item_id in c.item_ids:
                c.item_ids.remove(item_id)
            c.item_ids.append(item_id)

        self.build_toolbar()
        self.save_layout()

    def move_category(self, category_id: str, target_index: int, target_toolbar_id: Optional[str] = None) -> None:
        """
        Moves an entire category to target_index in category_order, optionally reassigning toolbar_id.
        """
        if category_id not in self.categories or category_id not in self.category_order:
            return

        curr_idx = self.category_order.index(category_id)
        self.category_order.pop(curr_idx)
        if target_index > curr_idx:
            target_index -= 1
        target_index = max(0, min(target_index, len(self.category_order)))
        self.category_order.insert(target_index, category_id)

        if target_toolbar_id in ("main", "secondary"):
            self.categories[category_id].toolbar_id = target_toolbar_id

        if not self._reposition_existing_category_widgets():
            self.build_toolbar()
        self.save_layout()

    def move_category_to_toolbar_slot(
        self, category_id: str, target_index: int, target_toolbar_id: str
    ) -> None:
        """Moves a category to a slot counted among categories on the target toolbar."""
        if (
            category_id not in self.categories
            or category_id not in self.category_order
            or target_toolbar_id not in ("main", "secondary")
        ):
            return

        remaining = [cat_id for cat_id in self.category_order if cat_id != category_id]
        target_categories = [
            cat_id for cat_id in remaining
            if self.categories[cat_id].visible
            and self.categories[cat_id].toolbar_id == target_toolbar_id
            and (
                self.is_edit_mode
                or any(
                    item_id in self.items and self.items[item_id].visible
                    for item_id in self.categories[cat_id].item_ids
                )
            )
        ]
        slot = max(0, min(target_index, len(target_categories)))
        if slot < len(target_categories):
            insertion_index = remaining.index(target_categories[slot])
        elif target_categories:
            insertion_index = remaining.index(target_categories[-1]) + 1
        else:
            insertion_index = len(remaining)

        self.category_order = remaining
        self.category_order.insert(insertion_index, category_id)
        self.categories[category_id].toolbar_id = target_toolbar_id

        if not self._reposition_existing_category_widgets():
            self.build_toolbar()
        self.save_layout()

    def _reposition_existing_category_widgets(self) -> bool:
        """Reorders/reparents category containers without rebuilding their contents."""
        if not isinstance(self.toolbar, CustomizableToolBar):
            return False
        toolbars = [self.toolbar]
        if isinstance(self.secondary_toolbar, CustomizableToolBar):
            toolbars.append(self.secondary_toolbar)

        widgets: Dict[str, ToolbarCategoryWidget] = {}
        for toolbar in toolbars:
            for cat_id, category_widget in toolbar.category_widgets.items():
                widgets[cat_id] = category_widget
            for index in range(toolbar.flow_layout.count()):
                layout_item = toolbar.flow_layout.itemAt(index)
                if layout_item and layout_item.widget() is not None:
                    widget = layout_item.widget()
                    if not isinstance(widget, ToolbarCategoryWidget):
                        return False

        desired_by_toolbar: Dict[str, List[ToolbarCategoryDef]] = {
            "main": [],
            "secondary": [],
        }
        for category in self.get_ordered_categories():
            if not category.visible:
                continue
            if category.toolbar_id == "secondary" and not self.secondary_toolbar_visible:
                continue
            if (
                not self.is_edit_mode
                and not any(
                    item_id in self.items and self.items[item_id].visible
                    for item_id in category.item_ids
                )
            ):
                continue
            desired_by_toolbar[category.toolbar_id].append(category)

        if any(cat.id not in widgets for cats in desired_by_toolbar.values() for cat in cats):
            return False

        for toolbar in toolbars:
            while toolbar.flow_layout.count():
                toolbar.flow_layout.takeAt(0)
            toolbar.category_widgets.clear()
            toolbar.category_grips.clear()
            toolbar.item_widgets_map.clear()
            toolbar._action_widgets.clear()
            toolbar._actions_list.clear()

        for toolbar in toolbars:
            for category in desired_by_toolbar[toolbar.toolbar_id]:
                category_widget = widgets[category.id]
                category_widget.category_def = category
                category_widget.setParent(toolbar.container)
                toolbar.flow_layout.addWidget(category_widget)
                category_widget.show()
                toolbar.category_widgets[category.id] = category_widget
                grip = next(
                    (
                        child for child in category_widget.children()
                        if isinstance(child, CategoryGripWidget)
                    ),
                    None,
                )
                if grip is not None:
                    grip.category_def = category
                    toolbar.category_grips[category.id] = grip
                for item_id, item_widget in category_widget.item_widgets.items():
                    toolbar.item_widgets_map[item_id] = item_widget
                    item = self.items.get(item_id)
                    if item and item.action:
                        toolbar._action_widgets[item.action] = item_widget
                        toolbar._actions_list.append(item.action)
            toolbar._sync_container()
            toolbar.updateGeometry()

        if self.secondary_toolbar and isinstance(self.secondary_toolbar, CustomizableToolBar):
            self.secondary_toolbar.setVisible(
                self.secondary_toolbar_visible and bool(desired_by_toolbar["secondary"])
            )
        if self.secondary_toolbar and isinstance(self.secondary_toolbar, CustomizableToolBar):
            self.toolbar.item_widgets_map.update(self.secondary_toolbar.item_widgets_map)

        self.layout_changed.emit()
        return True

    def on_item_drag_started(self, item_id: str, widget: QWidget) -> None:
        self.dragged_item_id = item_id
        self.dragged_widget = widget
        self.item_drag_started.emit(item_id)

    def on_category_drag_started(self, cat_id: str) -> None:
        self.dragged_category_id = cat_id
        self.category_drag_started.emit(cat_id)

    def on_category_drag_finished(self) -> None:
        was_active = self.dragged_category_id is not None
        self.dragged_category_id = None
        for toolbar in (self.toolbar, self.secondary_toolbar):
            if toolbar and hasattr(toolbar, "drop_indicator_x"):
                toolbar.drop_indicator_x = None
                toolbar.drop_indicator_y = None
                toolbar.drop_indicator_h = None
                toolbar.target_cat_index = None
                toolbar.is_category_drag = False
                toolbar.update()
        if was_active:
            self.drag_finished.emit()

    def on_item_drag_finished(self) -> None:
        was_active = self.dragged_item_id is not None or self.dragged_widget is not None
        self.dragged_widget = None
        self.dragged_item_id = None
        if was_active:
            self.drag_finished.emit()

    def on_drag_finished(self) -> None:
        """Compatibility alias for the retired toolbar-button drag lifecycle."""
        self.on_item_drag_finished()

    def build_toolbar(self) -> None:
        """Constructs or reconstructs the toolbar layout from current category & item states."""
        self._clear_item_drag_filters()
        # Unparent custom widgets to avoid Qt destroying them when clear() is called
        for item in self.items.values():
            if item.widget:
                item.widget.setParent(None)

        self.toolbar.clear()
        if self.secondary_toolbar:
            self.secondary_toolbar.clear()

        # 1. Populate Main Toolbar (unified wrapping flow toolbar)
        main_categories = [
            cat for cat in self.get_ordered_categories()
            if cat.visible and cat.toolbar_id == "main"
        ]
        self._populate_single_toolbar(self.toolbar, main_categories)

        # 2. Populate Secondary Toolbar if visible and has items
        if self.secondary_toolbar:
            sec_categories = [
                cat for cat in self.get_ordered_categories()
                if cat.visible and cat.toolbar_id == "secondary"
            ]
            if self.secondary_toolbar_visible and sec_categories:
                self._populate_single_toolbar(self.secondary_toolbar, sec_categories)
                self.secondary_toolbar.setVisible(True)
            else:
                self.secondary_toolbar.setVisible(False)

        # Keep the unified compatibility map complete across both top bars.
        for toolbar in (self.toolbar, self.secondary_toolbar):
            if toolbar and hasattr(toolbar, "item_widgets_map"):
                for item_id, widget in toolbar.item_widgets_map.items():
                    self.toolbar.item_widgets_map[item_id] = widget

        self.layout_changed.emit()

    def _populate_single_toolbar(self, target_toolbar: QToolBar, categories: List[ToolbarCategoryDef]) -> None:
        if hasattr(target_toolbar, "category_grips"):
            target_toolbar.category_grips.clear()
        if hasattr(target_toolbar, "category_widgets"):
            target_toolbar.category_widgets.clear()
        if hasattr(target_toolbar, "item_widgets_map"):
            target_toolbar.item_widgets_map.clear()

        if not hasattr(target_toolbar, "container"):
            for cat in categories:
                if not cat.visible:
                    continue
                for item_id in cat.item_ids:
                    item = self.items.get(item_id)
                    if not item or not item.visible:
                        continue
                    w: Optional[QWidget] = None
                    if item.action:
                        target_toolbar.addAction(item.action)
                        w = target_toolbar.widgetForAction(item.action)
                        item.button = w if isinstance(w, QToolButton) else item.button
                    elif item.widget:
                        target_toolbar.addWidget(item.widget)
                        w = item.widget
                    if w:
                        if hasattr(target_toolbar, "item_widgets_map"):
                            target_toolbar.item_widgets_map[item.id] = w
                        self._install_item_drag_filter(item.id, w)
            return

        for i, cat in enumerate(categories):
            visible_items = [
                self.items[item_id] for item_id in cat.item_ids
                if item_id in self.items and self.items[item_id].visible
            ]

            if not visible_items and not self.is_edit_mode:
                continue

            category_widget = ToolbarCategoryWidget(cat, parent=target_toolbar.container)
            target_toolbar.category_widgets[cat.id] = category_widget

            grip = CategoryGripWidget(cat, manager=self, parent=category_widget)
            grip.setFixedHeight(22)
            grip.setToolTip(
                f"Kategoria: {cat.title}\nPrzeciągnij nagłówek, aby przenieść całą kategorię."
            )
            grip.setEnabled(True)
            grip.setVisible(True)
            grip.setCursor(
                Qt.CursorShape.OpenHandCursor
                if self.is_edit_mode
                else Qt.CursorShape.ArrowCursor
            )
            grip.setToolTip(
                f"Kategoria: {cat.title}\nPrzeciągnij nagłówek, aby przenieść całą kategorię."
                if self.is_edit_mode
                else f"Kategoria: {cat.title}"
            )
            category_widget.set_grip(grip)
            if hasattr(target_toolbar, "category_grips"):
                target_toolbar.category_grips[cat.id] = grip

            for item in visible_items:
                w: Optional[QWidget] = None
                if item.action:
                    btn = QToolButton(category_widget)
                    btn.setDefaultAction(item.action)
                    btn.setFixedSize(26, 26)
                    btn.setStyleSheet(TOOLBAR_BUTTON_STYLE)
                    if btn:
                        item.button = btn
                    w = btn or item.button
                elif item.widget:
                    item.widget.show()
                    item.widget.setVisible(True)
                    w = item.widget

                if w:
                    if item.action:
                        target_toolbar._action_widgets[item.action] = w
                        if item.action not in target_toolbar._actions_list:
                            target_toolbar._actions_list.append(item.action)
                    if hasattr(target_toolbar, "item_widgets_map"):
                        target_toolbar.item_widgets_map[item.id] = w
                    self._install_item_drag_filter(item.id, w)
                    category_widget.add_item_widget(item.id, w)

            target_toolbar.addWidget(category_widget)

    def apply_layout(self, layout_data: Dict[str, Any]) -> None:
        """Applies configuration dictionary with version migration, deduplication, and atomic restoration."""
        if not isinstance(layout_data, dict):
            return

        self.secondary_toolbar_visible = bool(layout_data.get("secondary_toolbar_visible", True))
        categories_data = layout_data.get("categories", [])
        item_vis = layout_data.get("item_visibility", {})

        new_order: List[str] = []
        seen_cats = set()
        seen_items = set()

        for cat_entry in categories_data:
            if not isinstance(cat_entry, dict):
                continue
            cat_id = cat_entry.get("id")
            if not cat_id or cat_id not in self.categories or cat_id in seen_cats:
                continue

            new_order.append(cat_id)
            seen_cats.add(cat_id)
            cat_def = self.categories[cat_id]
            cat_def.visible = bool(cat_entry.get("visible", True))
            tid = cat_entry.get("toolbar_id")
            if tid not in ("main", "secondary"):
                tid = cat_def.default_toolbar_id
            cat_def.toolbar_id = tid

            items_in_cat = cat_entry.get("items", [])
            valid_items = []
            for i_id in items_in_cat:
                if not isinstance(i_id, str):
                    continue
                legacy_map = {"variants": "variants_toggle", "autotile": "autotile_toggle"}
                mapped_id = legacy_map.get(i_id, i_id)
                if mapped_id in self.items and mapped_id not in seen_items:
                    valid_items.append(mapped_id)
                    seen_items.add(mapped_id)
                    self.items[mapped_id].category_id = cat_id
            cat_def.item_ids = valid_items

        for cat_id in self.default_category_order:
            if cat_id in self.categories and cat_id not in seen_cats:
                new_order.append(cat_id)
                seen_cats.add(cat_id)

        for item_id, item_def in self.items.items():
            if item_id not in seen_items:
                target_cat = item_def.default_category_id
                if target_cat in self.categories:
                    if item_id not in self.categories[target_cat].item_ids:
                        self.categories[target_cat].item_ids.append(item_id)
                    item_def.category_id = target_cat
                    seen_items.add(item_id)

        # Restore flat item order
        saved_order = layout_data.get("item_order")
        if isinstance(saved_order, list):
            new_item_order: List[str] = []
            seen_order_items = set()
            for i_id in saved_order:
                if isinstance(i_id, str) and i_id in self.items and i_id not in seen_order_items:
                    new_item_order.append(i_id)
                    seen_order_items.add(i_id)
            for i_id in self.default_item_order:
                if i_id not in seen_order_items and i_id in self.items:
                    new_item_order.append(i_id)
                    seen_order_items.add(i_id)
            self.item_order = new_item_order
        else:
            migrated_order: List[str] = []
            for cat_id in new_order:
                if cat_id in self.categories:
                    for i_id in self.categories[cat_id].item_ids:
                        if i_id not in migrated_order:
                            migrated_order.append(i_id)
            for i_id in self.default_item_order:
                if i_id not in migrated_order and i_id in self.items:
                    migrated_order.append(i_id)
            self.item_order = migrated_order

        if isinstance(item_vis, dict):
            for item_id, item_def in self.items.items():
                if item_id in item_vis:
                    item_def.visible = bool(item_vis[item_id])

        self.category_order = new_order
        self.build_toolbar()

    def get_layout_dict(self) -> Dict[str, Any]:
        """Serializes current layout state to dictionary with schema versioning."""
        categories_data = []
        for cat_id in self.category_order:
            cat = self.categories.get(cat_id)
            if cat:
                categories_data.append({
                    "id": cat.id,
                    "visible": cat.visible,
                    "toolbar_id": cat.toolbar_id,
                    "items": list(cat.item_ids),
                })

        item_vis = {item_id: item.visible for item_id, item in self.items.items()}

        return {
            "version": TOOLBAR_LAYOUT_VERSION,
            "secondary_toolbar_visible": self.secondary_toolbar_visible,
            "item_order": list(self.item_order),
            "categories": categories_data,
            "item_visibility": item_vis,
        }

    def save_layout(self) -> bool:
        if getattr(self, "_is_loading", False):
            logger.debug("Skipping save_layout while loading configuration.")
            return False
        payload = self.get_layout_dict()
        return self.config_manager.save_toolbar_layout(payload)

    def load_layout(self) -> None:
        self._is_loading = True
        try:
            layout = self.config_manager.get_toolbar_layout()
            if layout and isinstance(layout, dict):
                try:
                    self.apply_layout(layout)
                    return
                except Exception as e:
                    logger.warning(f"Failed to restore toolbar layout ({e}), applying defaults.")

            self.reset_to_default(save=False)
        finally:
            self._is_loading = False

    def reset_to_default(self, save: bool = True) -> None:
        self.category_order = list(self.default_category_order)
        self.item_order = list(self.default_item_order)
        self.secondary_toolbar_visible = False
        for cat_id, cat in self.categories.items():
            cat.item_ids = list(cat.default_item_ids)
            cat.toolbar_id = cat.default_toolbar_id
            cat.visible = True

        for item_id, item in self.items.items():
            item.category_id = item.default_category_id
            item.visible = True

        self.build_toolbar()
        if save:
            self.save_layout()

    def set_secondary_toolbar_visible(self, visible: bool) -> None:
        self.secondary_toolbar_visible = visible
        self.build_toolbar()
        self.save_layout()

    def set_category_visible(self, category_id: str, visible: bool) -> None:
        if category_id in self.categories:
            self.categories[category_id].visible = visible
            self.build_toolbar()
            self.save_layout()

    def set_item_visible(self, item_id: str, visible: bool, save: bool = True) -> None:
        """Sets the visibility of a single toolbar item."""
        if item_id in self.items:
            self.items[item_id].visible = visible
            self.build_toolbar()
            if save:
                self.save_layout()
            self.layout_changed.emit()

    def set_items_visibility(self, visibility_map: Dict[str, bool], save: bool = True) -> None:
        """Sets visibility for multiple items in a batch, rebuilding toolbar once."""
        changed = False
        for item_id, vis in visibility_map.items():
            if item_id in self.items and self.items[item_id].visible != vis:
                self.items[item_id].visible = vis
                changed = True
        if changed:
            self.build_toolbar()
            if save:
                self.save_layout()
            self.layout_changed.emit()

    def hide_item(self, item_id: str, save: bool = True) -> None:
        """Hides a single toolbar item from the toolbar."""
        self.set_item_visible(item_id, False, save=save)

    def show_item(self, item_id: str, save: bool = True) -> None:
        """Shows a single toolbar item on the toolbar."""
        self.set_item_visible(item_id, True, save=save)

    def toggle_item_visibility(self, item_id: str, save: bool = True) -> bool:
        """Toggles the visibility of a single item and returns the new state."""
        if item_id in self.items:
            new_vis = not self.items[item_id].visible
            self.set_item_visible(item_id, new_vis, save=save)
            return new_vis
        return False

    def show_all_items(self, save: bool = True) -> None:
        """Restores visibility for all registered toolbar items."""
        for item in self.items.values():
            item.visible = True
        self.build_toolbar()
        if save:
            self.save_layout()
        self.layout_changed.emit()

    def restore_all_items(self, save: bool = True) -> None:
        """Alias for show_all_items."""
        self.show_all_items(save=save)

    def reset_visibility_to_default(self, save: bool = True) -> None:
        """Resets visibility of all items to default (all visible)."""
        self.show_all_items(save=save)

    def get_visible_items(self) -> List[ToolbarItemDef]:
        """Returns list of visible item definitions in current item_order."""
        return [
            self.items[i_id] for i_id in self.item_order
            if i_id in self.items and self.items[i_id].visible
        ]

    def get_hidden_items(self) -> List[ToolbarItemDef]:
        """Returns list of hidden item definitions in current item_order."""
        return [
            self.items[i_id] for i_id in self.item_order
            if i_id in self.items and not self.items[i_id].visible
        ]

    def open_visibility_dialog(self, parent: Optional[QWidget] = None) -> None:
        """Opens the dedicated ToolbarVisibilityDialog modal."""
        dlg = ToolbarVisibilityDialog(self, parent or self.parent_widget)
        dlg.exec()

    def open_customizer_dialog(self, parent: Optional[QWidget] = None) -> None:
        dlg = ToolbarCustomizerDialog(self, parent or self.parent_widget)
        dlg.exec()

    def _setup_toolbar_context_menus(self) -> None:
        for tb in [self.toolbar, self.secondary_toolbar]:
            if tb:
                tb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                tb.customContextMenuRequested.connect(lambda pos, sender=tb: self._show_context_menu(sender, pos))

    def _show_context_menu(self, source_toolbar: QToolBar, pos: Any) -> None:
        menu = QMenu(source_toolbar)
        menu.setStyleSheet("""
            QMenu {
                background-color: #18181b;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 24px 5px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1e3a5f;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: #3f3f46;
                margin: 4px 8px;
            }
        """)

        # Check if right click occurred directly over an item button
        clicked_item_id = None
        if hasattr(source_toolbar, "item_widgets_map"):
            glob_pos = source_toolbar.mapToGlobal(pos)
            for i_id, w in source_toolbar.item_widgets_map.items():
                if w and w.isVisible():
                    if w.rect().contains(w.mapFromGlobal(glob_pos)):
                        clicked_item_id = i_id
                        break

        if clicked_item_id and clicked_item_id in self.items:
            clicked_item = self.items[clicked_item_id]
            act_hide_this = menu.addAction(
                IconFactory.get_icon("eye-off", 16),
                f"Ukryj przycisk '{clicked_item.label}'",
            )
            act_hide_this.triggered.connect(lambda _, cid=clicked_item_id: self.hide_item(cid))
            menu.addSeparator()

        # Edit Mode Toggle (Drag & Drop)
        act_edit = menu.addAction(
            IconFactory.get_icon("edit", 16),
            "✓ Zakończ tryb personalizacji pasków" if self.is_edit_mode else "🛠 Tryb personalizacji pasków (Drag & Drop)...",
        )
        act_edit.triggered.connect(self.toggle_edit_mode)

        menu.addSeparator()

        # Submenu: Button Visibility
        menu_vis = menu.addMenu(IconFactory.get_icon("eye", 16), "Widoczność przycisków")
        menu_vis.setStyleSheet(menu.styleSheet())

        act_show_all = menu_vis.addAction(IconFactory.get_icon("check", 16), "Pokaż wszystkie przyciski")
        act_show_all.triggered.connect(lambda: self.show_all_items())

        act_vis_dlg = menu_vis.addAction(IconFactory.get_icon("settings", 16), "Zarządzaj widocznością...")
        act_vis_dlg.triggered.connect(lambda: self.open_visibility_dialog())

        menu_vis.addSeparator()

        for i_id in self.item_order:
            item_def = self.items.get(i_id)
            if not item_def:
                continue
            act_toggle = menu_vis.addAction(IconFactory.get_icon(item_def.icon_name, 16), item_def.label)
            act_toggle.setCheckable(True)
            act_toggle.setChecked(item_def.visible)
            act_toggle.toggled.connect(lambda chk, cid=i_id: self.set_item_visible(cid, chk))

        act_open_vis = menu.addAction(IconFactory.get_icon("eye", 16), "Zarządzaj widocznością przycisków...")
        act_open_vis.triggered.connect(lambda: self.open_visibility_dialog())

        menu.addSeparator()

        if self.secondary_toolbar:
            act_sec = menu.addAction("Pokaż dodatkowy pasek narzędzi (dolny)")
            act_sec.setCheckable(True)
            act_sec.setChecked(self.secondary_toolbar_visible)
            act_sec.toggled.connect(self.set_secondary_toolbar_visible)
            menu.addSeparator()

        act_customize = menu.addAction(IconFactory.get_icon("settings", 16), "Dostosuj paski narzędzi (Dialog)...")
        act_customize.triggered.connect(lambda: self.open_customizer_dialog())

        menu.addSeparator()

        menu_main_cats = menu.addMenu(IconFactory.get_icon("layout", 16), "Kategorie (Pasek główny)")
        menu_main_cats.setStyleSheet(menu.styleSheet())
        for cat in self.get_ordered_categories():
            if cat.toolbar_id == "main":
                act = menu_main_cats.addAction(IconFactory.get_icon(cat.icon_name, 16), cat.title)
                act.setCheckable(True)
                act.setChecked(cat.visible)
                act.toggled.connect(lambda chk, cid=cat.id: self.set_category_visible(cid, chk))

        if self.secondary_toolbar:
            menu_sec_cats = menu.addMenu(IconFactory.get_icon("layout", 16), "Kategorie (Pasek dodatkowy)")
            menu_sec_cats.setStyleSheet(menu.styleSheet())
            for cat in self.get_ordered_categories():
                if cat.toolbar_id == "secondary":
                    act = menu_sec_cats.addAction(IconFactory.get_icon(cat.icon_name, 16), cat.title)
                    act.setCheckable(True)
                    act.setChecked(cat.visible)
                    act.toggled.connect(lambda chk, cid=cat.id: self.set_category_visible(cid, chk))

        menu.addSeparator()

        act_reset = menu.addAction(IconFactory.get_icon("undo", 16), "Przywróć domyślny układ pasków")
        act_reset.triggered.connect(lambda: self.reset_to_default(save=True))

        menu.exec(source_toolbar.mapToGlobal(pos))
