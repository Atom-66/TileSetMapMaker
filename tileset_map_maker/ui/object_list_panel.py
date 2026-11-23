from typing import Optional, List
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QToolButton,
    QLabel,
    QMessageBox,
)
from PyQt6.QtGui import QIcon

from ..models.project import Project
from ..models.layer import MapItem, ItemType
from ..core.history import HistoryManager, ObjectRemoveCommand
from .icons import IconFactory


class ObjectListPanel(QWidget):
    """
    Panel displaying free-placed objects on the current layer or map.
    Allows inspecting, selecting, centering on, and deleting objects.
    Designed to be docked and tabbed alongside LayerPanel ('Warstwy | Obiekty').
    """
    object_selected = pyqtSignal(str)   # object_id
    focus_requested = pyqtSignal(float, float)  # center_x, center_y

    def __init__(
        self,
        project: Project,
        history_manager: Optional[HistoryManager] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.project = project
        self.history_manager = history_manager

        self.setMinimumWidth(180)
        self.setMinimumHeight(120)
        self._init_ui()
        self.refresh()

    def set_project(self, project: Project) -> None:
        """Updates the active project reference and refreshes the object list."""
        self.project = project
        self.refresh()

    def set_history_manager(self, history_manager: Optional[HistoryManager]) -> None:
        """Updates the active history manager reference."""
        self.history_manager = history_manager

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header with counter and action buttons
        header = QHBoxLayout()
        header.setContentsMargins(2, 2, 2, 2)
        header.setSpacing(4)

        self.lbl_title = QLabel("Obiekty na warstwie (0)")
        self.lbl_title.setStyleSheet("color: #e4e4e7; font-size: 11px; font-weight: 600;")
        header.addWidget(self.lbl_title, 1)

        self.btn_focus = QToolButton(self)
        self.btn_focus.setIcon(IconFactory.get_icon("target", 16))
        self.btn_focus.setToolTip("Wyśrodkuj widok na zaznaczonym obiekcie")
        self.btn_focus.setStyleSheet(self._button_style())
        self.btn_focus.clicked.connect(self._focus_selected_object)
        header.addWidget(self.btn_focus)

        self.btn_delete = QToolButton(self)
        self.btn_delete.setIcon(IconFactory.get_icon("trash", 16))
        self.btn_delete.setToolTip("Usuń zaznaczony obiekt")
        self.btn_delete.setStyleSheet(self._button_style())
        self.btn_delete.clicked.connect(self._delete_selected_object)
        header.addWidget(self.btn_delete)

        self.btn_refresh = QToolButton(self)
        self.btn_refresh.setIcon(IconFactory.get_icon("refresh", 16))
        self.btn_refresh.setToolTip("Odśwież listę obiektów")
        self.btn_refresh.setStyleSheet(self._button_style())
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)

        layout.addLayout(header)

        # Tree/List Widget
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Nazwa / ID", "Poz. (px)", "Wymiary"])
        self.tree.setColumnWidth(0, 110)
        self.tree.setColumnWidth(1, 80)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 4px;
                color: #e4e4e7;
                font-size: 11px;
            }
            QTreeWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
        """)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.tree, 1)

    def _button_style(self) -> str:
        return """
            QToolButton {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QToolButton:hover {
                background-color: #3b82f6;
                color: #ffffff;
                border-color: #60a5fa;
            }
        """

    def refresh(self) -> None:
        """Refreshes the object list from the active layer."""
        self.tree.clear()
        layer = self.project.get_active_layer()
        if not layer:
            self.lbl_title.setText("Obiekty na warstwie (0)")
            return

        objects = [item for item in layer.objects if item.item_type == ItemType.OBJECT]
        self.lbl_title.setText(f"Obiekty na warstwie ({len(objects)})")

        for idx, obj in enumerate(objects):
            name = f"Obiekt #{idx + 1}"
            px, py = obj.get_pixel_pos(self.project.tile_size)
            pos_str = f"({int(px)}, {int(py)})"
            dim_str = f"{obj.dest_w}x{obj.dest_h}"

            item = QTreeWidgetItem([name, pos_str, dim_str])
            item.setIcon(0, IconFactory.get_icon("object", 16))
            item.setData(0, Qt.ItemDataRole.UserRole, obj.id)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, (px, py, obj.dest_w, obj.dest_h))
            self.tree.addTopLevelItem(item)

    def _on_selection_changed(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        obj_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        if obj_id:
            self.object_selected.emit(obj_id)

    def _focus_selected_object(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        rect = items[0].data(0, Qt.ItemDataRole.UserRole + 1)
        if rect:
            px, py, dw, dh = rect
            center_x = px + dw / 2.0
            center_y = py + dh / 2.0
            self.focus_requested.emit(center_x, center_y)

    def _delete_selected_object(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        obj_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not obj_id:
            return

        layer = self.project.get_active_layer()
        if not layer:
            return

        target_obj = next((o for o in layer.objects if o.id == obj_id), None)
        if not target_obj:
            return

        if self.history_manager:
            cmd = ObjectRemoveCommand(self.project, layer.id, target_obj)
            self.history_manager.push(cmd)
        else:
            layer.remove_object(obj_id)
            self.project.is_modified = True

        self.refresh()
