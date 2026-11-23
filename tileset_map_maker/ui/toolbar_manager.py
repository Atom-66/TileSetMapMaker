import copy
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QSize, QPoint, QRect, QEvent, QMimeData
from PyQt6.QtGui import (
    QAction,
    QIcon,
    QDrag,
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QPolygon,
    QMouseEvent,
    QKeySequence,
    QKeyEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QWidget,
    QToolBar,
    QHBoxLayout,
    QVBoxLayout,
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
    QCheckBox,
    QGraphicsOpacityEffect,
)

from .icons import IconFactory
from ..core.config_manager import ConfigManager

logger = logging.getLogger("ToolbarManager")

TOOLBAR_LAYOUT_VERSION: int = 2

TOOLBAR_BUTTON_STYLE = """
    QToolButton {
        background: #27272a;
        color: #e4e4e7;
        border: 1px solid #3f3f46;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
        font-weight: 500;
        min-height: 24px;
        max-height: 26px;
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
        self.layout_box = QHBoxLayout(self)
        self.layout_box.setContentsMargins(0, 0, 0, 0)
        self.layout_box.setSpacing(4)
        self.setStyleSheet("background: transparent;")
        self.item_widgets: Dict[str, QWidget] = {}

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
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(4)
        self.setFixedHeight(26)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(f"Kategoria: {self.category_def.title}\nPrzeciągnij, aby zmienić kolejność kategorii lub przenieść na inny pasek.")

        self.lbl_grip = QLabel("⋮⋮")
        self.lbl_grip.setStyleSheet("color: #60a5fa; font-size: 13px; font-weight: bold; background: transparent;")
        layout.addWidget(self.lbl_grip)

        self.lbl_title = QLabel(self.category_def.title)
        self.lbl_title.setStyleSheet("color: #e4e4e7; font-size: 11px; font-weight: 600; background: transparent;")
        layout.addWidget(self.lbl_title)

        self.setStyleSheet("""
            CategoryGripWidget {
                background-color: #27272a;
                border: 1px dashed #3b82f6;
                border-radius: 4px;
            }
            CategoryGripWidget:hover {
                background-color: #3f3f46;
                border: 1px solid #60a5fa;
            }
        """)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            self.drag_start_pos = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (event.buttons() & Qt.MouseButton.LeftButton) and self.drag_start_pos is not None:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if (pos - self.drag_start_pos).manhattanLength() >= QApplication.startDragDistance():
                self._start_category_drag()
                self.drag_start_pos = None
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.drag_start_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def _start_category_drag(self) -> None:
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-toolbar-category", self.category_def.id.encode("utf-8"))
        drag.setMimeData(mime)

        pix = self.grab()
        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(pix.width() // 2, pix.height() // 2))

        self.manager.on_category_drag_started(self.category_def.id)
        drag.exec(Qt.DropAction.MoveAction)
        self.manager.on_drag_finished()


class ToolbarItemDragFilter(QObject):
    """
    Event filter installed on buttons/widgets in toolbars to enable Drag & Drop
    when in edit mode, while guaranteeing 100% standard click behavior outside edit mode.
    """

    def __init__(self, item_id: str, manager: "ToolbarManager", parent: Optional[QObject] = None):
        super().__init__(parent)
        self.item_id = item_id
        self.manager = manager
        self.drag_start_pos: Optional[QPoint] = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if not getattr(self.manager, "is_edit_mode", False):
            return False

        evt_type = event.type()
        if evt_type == QEvent.Type.Enter:
            if isinstance(watched, QWidget):
                watched.setCursor(Qt.CursorShape.OpenHandCursor)
            return False
        elif evt_type == QEvent.Type.Leave:
            if isinstance(watched, QWidget):
                watched.unsetCursor()
            return False
        elif evt_type == QEvent.Type.MouseButtonPress:
            mouse_event: QMouseEvent = event  # type: ignore
            if mouse_event.button() == Qt.MouseButton.LeftButton:
                pos = mouse_event.position().toPoint() if hasattr(mouse_event, "position") else mouse_event.pos()
                self.drag_start_pos = pos
                if isinstance(watched, QWidget):
                    watched.setCursor(Qt.CursorShape.ClosedHandCursor)
                return True
        elif evt_type == QEvent.Type.MouseMove:
            mouse_event: QMouseEvent = event  # type: ignore
            if (mouse_event.buttons() & Qt.MouseButton.LeftButton) and self.drag_start_pos is not None:
                pos = mouse_event.position().toPoint() if hasattr(mouse_event, "position") else mouse_event.pos()
                if (pos - self.drag_start_pos).manhattanLength() >= QApplication.startDragDistance():
                    if isinstance(watched, QWidget):
                        self._start_item_drag(watched)
                        self.drag_start_pos = None
                        watched.setCursor(Qt.CursorShape.OpenHandCursor)
                        return True
        elif evt_type == QEvent.Type.MouseButtonRelease:
            self.drag_start_pos = None
            if isinstance(watched, QWidget):
                watched.setCursor(Qt.CursorShape.OpenHandCursor)
            return True

        return False

    def _start_item_drag(self, widget: QWidget) -> None:
        drag = QDrag(widget)
        mime = QMimeData()
        mime.setData("application/x-toolbar-item", self.item_id.encode("utf-8"))
        drag.setMimeData(mime)

        pix = widget.grab()
        ghost = QPixmap(pix.size())
        ghost.fill(Qt.GlobalColor.transparent)
        p = QPainter(ghost)
        p.setOpacity(0.85)
        p.drawPixmap(0, 0, pix)
        p.end()

        drag.setPixmap(ghost)
        drag.setHotSpot(QPoint(pix.width() // 2, pix.height() // 2))

        self.manager.on_item_drag_started(self.item_id, widget)
        drag.exec(Qt.DropAction.MoveAction)
        self.manager.on_drag_finished()


class CustomizableToolBar(QToolBar):
    """
    Enhanced QToolBar supporting direct in-place Drag & Drop customization of buttons
    and categories, visual drop indicator with top/bottom arrows, and edit mode styling.
    """

    def __init__(self, title: str = "", toolbar_id: str = "main", parent: Optional[QWidget] = None):
        super().__init__(title, parent)
        self.toolbar_id = toolbar_id
        self.manager: Optional["ToolbarManager"] = None
        self.is_edit_mode: bool = False
        self.drop_indicator_x: Optional[int] = None
        self.target_cat_id: Optional[str] = None
        self.target_item_index: Optional[int] = None
        self.target_cat_index: Optional[int] = None
        self.is_category_drag: bool = False
        self.category_grips: Dict[str, CategoryGripWidget] = {}
        self.item_widgets_map: Dict[str, QWidget] = {}
        self.setAcceptDrops(True)

    def set_manager(self, manager: "ToolbarManager") -> None:
        self.manager = manager

    def set_edit_mode(self, active: bool) -> None:
        self.is_edit_mode = active
        self.drop_indicator_x = None
        if active:
            self.setStyleSheet("""
                QToolBar {
                    background-color: #1a1b22;
                    border: 1px dashed #3b82f6;
                    border-radius: 4px;
                    padding: 4px 6px;
                    spacing: 4px;
                }
            """)
        else:
            self.setStyleSheet("")
        self.update()

    def dragEnterEvent(self, event: Any) -> None:
        mime = event.mimeData()
        if mime.hasFormat("application/x-toolbar-item") or mime.hasFormat("application/x-toolbar-category"):
            event.acceptProposedAction()
            self.update()
        else:
            event.ignore()

    def dragMoveEvent(self, event: Any) -> None:
        mime = event.mimeData()
        if not self.manager:
            event.ignore()
            return

        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if mime.hasFormat("application/x-toolbar-item"):
            item_id = bytes(mime.data("application/x-toolbar-item")).decode("utf-8")
            slot_x, cat_id, item_idx = self.calculate_item_drop_slot(pos, item_id)
            self.drop_indicator_x = slot_x
            self.target_cat_id = cat_id
            self.target_item_index = item_idx
            self.is_category_drag = False
            self.update()
            event.acceptProposedAction()
        elif mime.hasFormat("application/x-toolbar-category"):
            cat_id = bytes(mime.data("application/x-toolbar-category")).decode("utf-8")
            slot_x, cat_idx = self.calculate_category_drop_slot(pos, cat_id)
            self.drop_indicator_x = slot_x
            self.target_cat_index = cat_idx
            self.is_category_drag = True
            self.update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: Any) -> None:
        self.drop_indicator_x = None
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: Any) -> None:
        mime = event.mimeData()
        if not self.manager:
            event.ignore()
            return

        if mime.hasFormat("application/x-toolbar-item"):
            item_id = bytes(mime.data("application/x-toolbar-item")).decode("utf-8")
            if self.target_cat_id is not None and self.target_item_index is not None:
                self.manager.move_item(item_id, self.target_cat_id, self.target_item_index)
            event.acceptProposedAction()
        elif mime.hasFormat("application/x-toolbar-category"):
            cat_id = bytes(mime.data("application/x-toolbar-category")).decode("utf-8")
            if self.target_cat_index is not None:
                self.manager.move_category(cat_id, self.target_cat_index, self.toolbar_id)
            event.acceptProposedAction()

        self.drop_indicator_x = None
        self.update()

    def calculate_item_drop_slot(self, pos: QPoint, dragged_item_id: str) -> Tuple[int, str, int]:
        if not self.manager:
            return (10, "project", 0)

        cats = [
            cat for cat in self.manager.get_ordered_categories()
            if cat.visible and cat.toolbar_id == self.toolbar_id
        ]
        if not cats:
            this_tb_cats = [c for c in self.manager.categories.values() if c.toolbar_id == self.toolbar_id]
            fallback_cat = this_tb_cats[0].id if this_tb_cats else (self.manager.category_order[0] if self.manager.category_order else "project")
            return (10, fallback_cat, 0)

        slots: List[Tuple[int, str, int]] = []

        for cat in cats:
            cat_items = [
                i_id for i_id in cat.item_ids
                if i_id in self.manager.items and self.manager.items[i_id].visible
            ]
            grip = self.category_grips.get(cat.id)
            grip_r = grip.geometry() if (grip and grip.isVisible()) else None

            if not cat_items:
                if grip_r:
                    slots.append((grip_r.right() + 4, cat.id, 0))
                else:
                    slots.append((10, cat.id, 0))
                continue

            item_geoms: List[Tuple[str, QRect]] = []
            for i_id in cat_items:
                w = self.item_widgets_map.get(i_id)
                if w and w.isVisible():
                    item_geoms.append((i_id, w.geometry()))

            if not item_geoms:
                if grip_r:
                    slots.append((grip_r.right() + 4, cat.id, 0))
                else:
                    slots.append((10, cat.id, 0))
                continue

            # Slot 0 (before first item in this category)
            first_r = item_geoms[0][1]
            if grip_r:
                slot_0_x = (grip_r.right() + first_r.left()) // 2
            else:
                slot_0_x = max(4, first_r.left() - 3)
            slots.append((slot_0_x, cat.id, 0))

            # Slots between items
            for idx in range(len(item_geoms) - 1):
                r_left = item_geoms[idx][1]
                r_right = item_geoms[idx + 1][1]
                mid_x = (r_left.right() + r_right.left()) // 2
                slots.append((mid_x, cat.id, idx + 1))

            # Slot after last item in category
            last_r = item_geoms[-1][1]
            slots.append((last_r.right() + 4, cat.id, len(cat_items)))

        if not slots:
            return (10, cats[0].id, 0)

        closest = min(slots, key=lambda s: abs(s[0] - pos.x()))
        return closest

    def calculate_category_drop_slot(self, pos: QPoint, dragged_cat_id: str) -> Tuple[int, int]:
        if not self.manager:
            return (10, 0)

        cats = [
            cat for cat in self.manager.get_ordered_categories()
            if cat.visible and cat.toolbar_id == self.toolbar_id
        ]
        if not cats:
            return (10, len(self.manager.category_order))

        boundaries: List[Tuple[int, int]] = []

        for idx, cat in enumerate(cats):
            grip = self.category_grips.get(cat.id)
            rects: List[QRect] = []
            if grip and grip.isVisible():
                rects.append(grip.geometry())
            for i_id in cat.item_ids:
                w = self.item_widgets_map.get(i_id)
                if w and w.isVisible():
                    rects.append(w.geometry())

            if not rects:
                continue

            cat_left = min(r.left() for r in rects)
            cat_right = max(r.right() for r in rects)
            global_idx = self.manager.category_order.index(cat.id) if cat.id in self.manager.category_order else 0

            boundaries.append((max(4, cat_left - 3), global_idx))
            boundaries.append((cat_right + 4, global_idx + 1))

        if not boundaries:
            return (10, 0)

        closest = min(boundaries, key=lambda b: abs(b[0] - pos.x()))
        return closest

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        if self.is_edit_mode and self.drop_indicator_x is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            x = self.drop_indicator_x
            h = self.height()
            top_y = 2
            bot_y = h - 2

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

            arrow_w = 6
            arrow_h = 7

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
            "Chwyć i przeciągnij dowolny przycisk lub nagłówek kategorii (⋮⋮), "
            "aby wstawić go w wybranym miejscu lub przenieść między paskami."
        )
        layout.addWidget(info_lbl, 1)

        btn_reset = QPushButton("↺ Przywróć domyślne")
        btn_reset.setObjectName("btn_reset")
        btn_reset.setToolTip("Przywróć domyślny układ i kolejność przycisków na obu paskach")
        btn_reset.clicked.connect(lambda: self.manager.reset_to_default(save=True))
        layout.addWidget(btn_reset)

        btn_done = QPushButton("✓ Zakończ personalizację")
        btn_done.setObjectName("btn_done")
        btn_done.setToolTip("Zapisz aktualny układ i wróć do normalnego trybu pracy (Esc)")
        btn_done.clicked.connect(lambda: self.manager.set_edit_mode(False))
        layout.addWidget(btn_done)

        self.hide()


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
        self.tab_toolbars.currentChanged.connect(self._on_toolbar_tab_changed)

        # Tab: Main Toolbar
        tab_main_widget = QWidget()
        tab_main_lay = QVBoxLayout(tab_main_widget)
        tab_main_lay.setContentsMargins(4, 4, 4, 4)
        self.list_main_cats = QListWidget()
        self.list_main_cats.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_main_cats.itemSelectionChanged.connect(self._on_category_selected)
        self.list_main_cats.itemChanged.connect(self._on_category_item_changed)
        self.list_main_cats.model().rowsMoved.connect(self._on_categories_reordered)
        tab_main_lay.addWidget(self.list_main_cats)
        self.tab_toolbars.addTab(tab_main_widget, "Pasek główny (Górny)")

        # Tab: Secondary Toolbar
        tab_sec_widget = QWidget()
        tab_sec_lay = QVBoxLayout(tab_sec_widget)
        tab_sec_lay.setContentsMargins(4, 4, 4, 4)
        self.list_sec_cats = QListWidget()
        self.list_sec_cats.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
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

        self.list_items = QListWidget()
        self.list_items.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
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
        if not hasattr(self, "list_items"):
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
        if not item_id:
            return

        if item_id in self.working_categories[curr_cat_id].item_ids:
            self.working_categories[curr_cat_id].item_ids.remove(item_id)

        if target_cat_id in self.working_categories:
            self.working_categories[target_cat_id].item_ids.append(item_id)
            if item_id in self.working_items:
                self.working_items[item_id].category_id = target_cat_id

        self._populate_all(select_cat_id=curr_cat_id)

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
    - Real in-place Drag & Drop customization of buttons and categories directly on the toolbars
    - Insertion drop indicators with top & bottom arrowheads
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

        if hasattr(self.toolbar, "set_manager"):
            self.toolbar.set_manager(self)
        if self.secondary_toolbar and hasattr(self.secondary_toolbar, "set_manager"):
            self.secondary_toolbar.set_manager(self)

        self.categories: Dict[str, ToolbarCategoryDef] = {}
        self.category_order: List[str] = []
        self.default_category_order: List[str] = []
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

        return item_def

    def get_ordered_categories(self) -> List[ToolbarCategoryDef]:
        res = []
        for cat_id in self.category_order:
            if cat_id in self.categories:
                res.append(self.categories[cat_id])
        return res

    def set_edit_banner(self, banner: ToolbarEditModeBanner) -> None:
        self.edit_banner = banner
        banner.setVisible(self.is_edit_mode)

    def set_edit_mode(self, active: bool) -> None:
        if self.is_edit_mode == active:
            return
        self.is_edit_mode = active
        if hasattr(self.toolbar, "set_edit_mode"):
            self.toolbar.set_edit_mode(active)
        if self.secondary_toolbar and hasattr(self.secondary_toolbar, "set_edit_mode"):
            self.secondary_toolbar.set_edit_mode(active)
        if self.edit_banner:
            self.edit_banner.setVisible(active)
        self.build_toolbar()
        self.edit_mode_changed.emit(active)

    def toggle_edit_mode(self) -> None:
        self.set_edit_mode(not self.is_edit_mode)

    def move_item(self, item_id: str, target_category_id: str, target_index: int) -> None:
        """
        Moves an item to target_category_id at target_index with real in-place reordering.
        Supports reordering between any buttons, across categories, and across toolbars.
        """
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
            curr_idx = source_cat.item_ids.index(item_id)
            source_cat.item_ids.remove(item_id)
            if source_cat.id == target_category_id:
                if target_index > curr_idx:
                    target_index -= 1

        target_index = max(0, min(target_index, len(target_cat.item_ids)))
        target_cat.item_ids.insert(target_index, item_id)
        if item_id in self.items:
            self.items[item_id].category_id = target_category_id

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

        self.build_toolbar()
        self.save_layout()

    def on_item_drag_started(self, item_id: str, widget: QWidget) -> None:
        self.dragged_item_id = item_id
        self.dragged_widget = widget
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.3)
        widget.setGraphicsEffect(effect)
        self.item_drag_started.emit(item_id)

    def on_category_drag_started(self, cat_id: str) -> None:
        self.dragged_category_id = cat_id
        self.category_drag_started.emit(cat_id)

    def on_drag_finished(self) -> None:
        if self.dragged_widget:
            try:
                from PyQt6 import sip
                if not sip.isdeleted(self.dragged_widget):
                    self.dragged_widget.setGraphicsEffect(None)
            except Exception:
                pass
            self.dragged_widget = None
        self.dragged_item_id = None
        self.dragged_category_id = None
        if self.toolbar and hasattr(self.toolbar, "drop_indicator_x"):
            self.toolbar.drop_indicator_x = None
            self.toolbar.update()
        if self.secondary_toolbar and hasattr(self.secondary_toolbar, "drop_indicator_x"):
            self.secondary_toolbar.drop_indicator_x = None
            self.secondary_toolbar.update()
        self.drag_finished.emit()

    def build_toolbar(self) -> None:
        """Constructs or reconstructs the toolbar layout from current category & item states."""
        # Unparent custom widgets to avoid Qt destroying them when clear() is called
        for item in self.items.values():
            if item.widget:
                item.widget.setParent(None)

        self.toolbar.clear()
        if self.secondary_toolbar:
            self.secondary_toolbar.clear()

        # Group categories by target toolbar
        main_categories = [
            cat for cat in self.get_ordered_categories()
            if cat.visible and cat.toolbar_id == "main"
        ]

        # If secondary_toolbar is None, put all categories on main toolbar for fallback
        sec_categories = [
            cat for cat in self.get_ordered_categories()
            if cat.visible and cat.toolbar_id == "secondary"
        ] if self.secondary_toolbar else []

        if not self.secondary_toolbar:
            main_categories.extend(sec_categories)
            sec_categories = []

        # 1. Populate Main Toolbar
        self._populate_single_toolbar(self.toolbar, main_categories)

        # 2. Populate Secondary Toolbar
        if self.secondary_toolbar:
            if self.secondary_toolbar_visible and sec_categories:
                self._populate_single_toolbar(self.secondary_toolbar, sec_categories)
                self.secondary_toolbar.setVisible(True)
            else:
                self.secondary_toolbar.setVisible(False)

        self.layout_changed.emit()

    def _populate_single_toolbar(self, target_toolbar: QToolBar, categories: List[ToolbarCategoryDef]) -> None:
        if hasattr(target_toolbar, "category_grips"):
            target_toolbar.category_grips.clear()
        if hasattr(target_toolbar, "item_widgets_map"):
            target_toolbar.item_widgets_map.clear()

        for i, cat in enumerate(categories):
            visible_items = [
                self.items[item_id] for item_id in cat.item_ids
                if item_id in self.items and self.items[item_id].visible
            ]

            if not visible_items and not self.is_edit_mode:
                continue

            # In edit mode, add Category Grip
            if self.is_edit_mode:
                grip = CategoryGripWidget(cat, manager=self, parent=target_toolbar)
                if hasattr(target_toolbar, "category_grips"):
                    target_toolbar.category_grips[cat.id] = grip
                target_toolbar.addWidget(grip)

            for item in visible_items:
                w: Optional[QWidget] = None
                if item.action:
                    act = target_toolbar.addAction(item.action)
                    btn = target_toolbar.widgetForAction(act)
                    if btn:
                        btn.setFixedHeight(26)
                        btn.setStyleSheet(TOOLBAR_BUTTON_STYLE)
                        item.button = btn
                    w = btn or item.button
                elif item.widget:
                    item.widget.show()
                    target_toolbar.addWidget(item.widget)
                    item.widget.setVisible(True)
                    w = item.widget

                if w:
                    if hasattr(target_toolbar, "item_widgets_map"):
                        target_toolbar.item_widgets_map[item.id] = w
                    # Clean up any existing ToolbarItemDragFilter to avoid multiple stacked filters
                    for child in list(w.children()):
                        if isinstance(child, ToolbarItemDragFilter):
                            w.removeEventFilter(child)
                            child.setParent(None)
                    filter_obj = ToolbarItemDragFilter(item.id, manager=self, parent=w)
                    w.installEventFilter(filter_obj)

            # Add separator between categories if not the last category
            if i < len(categories) - 1:
                target_toolbar.addSeparator()

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
                # Support legacy item id mapping if any
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
        self.secondary_toolbar_visible = True
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

    def set_item_visible(self, item_id: str, visible: bool) -> None:
        if item_id in self.items:
            self.items[item_id].visible = visible
            self.build_toolbar()
            self.save_layout()

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

        # Edit Mode Toggle (Drag & Drop)
        act_edit = menu.addAction(
            IconFactory.get_icon("edit", 16),
            "✓ Zakończ tryb personalizacji pasków" if self.is_edit_mode else "🛠 Tryb personalizacji pasków (Drag & Drop)...",
        )
        act_edit.triggered.connect(self.toggle_edit_mode)

        menu.addSeparator()

        if self.secondary_toolbar:
            act_sec = menu.addAction("Pokaż dodatkowy pasek narzędzi (dolny)")
            act_sec.setCheckable(True)
            act_sec.setChecked(self.secondary_toolbar_visible)
            act_sec.toggled.connect(self.set_secondary_toolbar_visible)
            menu.addSeparator()

        act_customize = menu.addAction(IconFactory.get_icon("settings", 16), "Dostosuj paski narzędzi (Okno dialogowe)...")
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
