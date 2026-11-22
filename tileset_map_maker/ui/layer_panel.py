from typing import Optional, List
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QSlider,
    QInputDialog,
    QMessageBox,
    QToolButton,
    QMenu,
)
from PyQt6.QtGui import QColor

from ..models.project import Project
from ..models.layer import Layer
from ..core.history import HistoryManager, LayerAddCommand, LayerRemoveCommand, LayerMoveCommand


class LayerPanel(QWidget):
    """
    Advanced hierarchical layer and group manager supporting nested groups,
    group-wide visibility and opacity, locking, and auto-tiling toggle.
    """
    layer_changed = pyqtSignal()

    def __init__(
        self,
        project: Project,
        history_manager: HistoryManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.project = project
        self.history_manager = history_manager

        self._init_ui()
        self.refresh_layers()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header with Opacity Slider
        op_layout = QHBoxLayout()
        lbl_op = QLabel("Krycie:")
        lbl_op.setStyleSheet("font-size: 11px; color: #a1a1aa;")
        op_layout.addWidget(lbl_op)

        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.valueChanged.connect(self._on_opacity_changed)
        op_layout.addWidget(self.slider_opacity)

        self.lbl_op_val = QLabel("100%")
        self.lbl_op_val.setStyleSheet("font-size: 11px; color: #a1a1aa; min-width: 35px;")
        op_layout.addWidget(self.lbl_op_val)
        layout.addLayout(op_layout)

        # Hierarchical Layer Tree Widget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Warstwa / Grupa", "Widoczność", "Blokada", "Auto-Tile"])
        self.tree_widget.setColumnWidth(0, 140)
        self.tree_widget.setColumnWidth(1, 40)
        self.tree_widget.setColumnWidth(2, 40)
        self.tree_widget.setColumnWidth(3, 40)
        self.tree_widget.itemClicked.connect(self._on_item_clicked)
        self.tree_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.tree_widget)

        # Action Buttons Toolbar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        btn_add = QToolButton()
        btn_add.setText("➕")
        btn_add.setToolTip("Dodaj nową warstwę")
        btn_add.clicked.connect(self._add_layer)

        btn_add_grp = QToolButton()
        btn_add_grp.setText("📁")
        btn_add_grp.setToolTip("Dodaj nową grupę warstw")
        btn_add_grp.clicked.connect(self._add_group)

        btn_dup = QToolButton()
        btn_dup.setText("📋")
        btn_dup.setToolTip("Duplikuj aktywną warstwę")
        btn_dup.clicked.connect(self._duplicate_layer)

        btn_del = QToolButton()
        btn_del.setText("🗑️")
        btn_del.setToolTip("Usuń wybraną warstwę lub grupę")
        btn_del.clicked.connect(self._delete_layer)

        btn_clear = QToolButton()
        btn_clear.setText("🧹")
        btn_clear.setToolTip("Wyczyść zawartość aktywnej warstwy")
        btn_clear.clicked.connect(self._clear_layer)

        btn_up = QToolButton()
        btn_up.setText("⬆️")
        btn_up.setToolTip("Przesuń w górę")
        btn_up.clicked.connect(self._move_up)

        btn_down = QToolButton()
        btn_down.setText("⬇️")
        btn_down.setToolTip("Przesuń w dół")
        btn_down.clicked.connect(self._move_down)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_add_grp)
        btn_layout.addWidget(btn_dup)
        btn_layout.addWidget(btn_del)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_up)
        btn_layout.addWidget(btn_down)

        layout.addLayout(btn_layout)

    def set_project(self, project: Project) -> None:
        self.project = project
        self.refresh_layers()

    def refresh_layers(self) -> None:
        self.tree_widget.blockSignals(True)
        self.tree_widget.clear()

        # Build tree of groups and layers
        # Group root items (layers without group_id)
        roots = [l for l in reversed(self.project.layers) if not l.group_id]

        def _populate(layer: Layer, parent_item: Optional[QTreeWidgetItem]):
            item = QTreeWidgetItem(parent_item or self.tree_widget)
            item.setData(0, Qt.ItemDataRole.UserRole, layer.id)

            prefix = "📁 " if layer.is_group else "📄 "
            count = len(layer.tiles) + len(layer.objects)
            count_str = f" ({count})" if not layer.is_group else ""
            item.setText(0, f"{prefix}{layer.name}{count_str}")

            # Visibility button / text
            vis_icon = "👁️" if layer.visible else "🚫"
            item.setText(1, vis_icon)
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)

            # Lock button / text
            lock_icon = "🔒" if layer.locked else "🔓"
            item.setText(2, lock_icon)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)

            # Auto-tiling indicator
            if not layer.is_group:
                at_icon = "⚡" if layer.auto_tiling_enabled else "—"
                item.setText(3, at_icon)
                item.setTextAlignment(3, Qt.AlignmentFlag.AlignCenter)

            # Highlight active layer
            if layer.id == self.project.active_layer_id:
                self.tree_widget.setCurrentItem(item)
                self.slider_opacity.setValue(int(layer.opacity * 100))
                self.lbl_op_val.setText(f"{int(layer.opacity * 100)}%")

            # Children if group
            if layer.is_group:
                children = [l for l in reversed(self.project.layers) if l.group_id == layer.id]
                for child in children:
                    _populate(child, item)

        for root in roots:
            _populate(root, None)

        self.tree_widget.expandAll()
        self.tree_widget.blockSignals(False)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        layer_id = item.data(0, Qt.ItemDataRole.UserRole)
        layer = self.project.get_layer(layer_id)
        if not layer:
            return

        if column == 1:
            # Toggle visibility
            layer.visible = not layer.visible
            self.refresh_layers()
            self.layer_changed.emit()
            return
        elif column == 2:
            # Toggle lock
            layer.locked = not layer.locked
            self.refresh_layers()
            self.layer_changed.emit()
            return
        elif column == 3 and not layer.is_group:
            # Toggle auto-tiling
            layer.auto_tiling_enabled = not layer.auto_tiling_enabled
            self.refresh_layers()
            self.layer_changed.emit()
            return

        # Select layer
        if not layer.is_group:
            self.project.set_active_layer(layer_id)
        self.slider_opacity.blockSignals(True)
        self.slider_opacity.setValue(int(layer.opacity * 100))
        self.lbl_op_val.setText(f"{int(layer.opacity * 100)}%")
        self.slider_opacity.blockSignals(False)
        self.layer_changed.emit()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        layer_id = item.data(0, Qt.ItemDataRole.UserRole)
        layer = self.project.get_layer(layer_id)
        if not layer:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Zmień nazwę",
            "Nowa nazwa:",
            text=layer.name,
        )
        if ok and new_name.strip():
            layer.name = new_name.strip()
            self.refresh_layers()
            self.layer_changed.emit()

    def _on_opacity_changed(self, val: int) -> None:
        item = self.tree_widget.currentItem()
        layer_id = item.data(0, Qt.ItemDataRole.UserRole) if item else self.project.active_layer_id
        layer = self.project.get_layer(layer_id)
        if layer:
            layer.opacity = val / 100.0
            self.lbl_op_val.setText(f"{val}%")
            self.layer_changed.emit()

    def _add_layer(self) -> None:
        item = self.tree_widget.currentItem()
        parent_group_id = None
        if item:
            lid = item.data(0, Qt.ItemDataRole.UserRole)
            target = self.project.get_layer(lid)
            if target and target.is_group:
                parent_group_id = target.id
            elif target and target.group_id:
                parent_group_id = target.group_id

        name, ok = QInputDialog.getText(
            self,
            "Nowa warstwa",
            "Nazwa warstwy:",
            text=f"Warstwa {len(self.project.layers) + 1}",
        )
        if ok and name.strip():
            new_layer = Layer(name=name.strip(), group_id=parent_group_id)
            cmd = LayerAddCommand(self.project, new_layer)
            self.history_manager.push(cmd)
            self.refresh_layers()
            self.layer_changed.emit()

    def _add_group(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            "Nowa grupa warstw",
            "Nazwa grupy:",
            text="Nowa grupa",
        )
        if ok and name.strip():
            grp = self.project.add_group(name=name.strip())
            self.refresh_layers()
            self.layer_changed.emit()

    def _duplicate_layer(self) -> None:
        item = self.tree_widget.currentItem()
        lid = item.data(0, Qt.ItemDataRole.UserRole) if item else self.project.active_layer_id
        if lid:
            cloned = self.project.duplicate_layer(lid)
            if cloned:
                self.refresh_layers()
                self.layer_changed.emit()

    def _delete_layer(self) -> None:
        if len(self.project.layers) <= 1:
            QMessageBox.warning(self, "Uwaga", "Projekt musi posiadać co najmniej jedną warstwę.")
            return
        item = self.tree_widget.currentItem()
        lid = item.data(0, Qt.ItemDataRole.UserRole) if item else self.project.active_layer_id
        target = self.project.get_layer(lid)
        if target:
            msg = f"Czy usunąć grupę '{target.name}' wraz z zawartymi w niej warstwami?" if target.is_group else f"Czy usunąć warstwę '{target.name}'?"
            confirm = QMessageBox.question(
                self,
                "Potwierdź usunięcie",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                cmd = LayerRemoveCommand(self.project, target.id)
                self.history_manager.push(cmd)
                self.refresh_layers()
                self.layer_changed.emit()

    def _clear_layer(self) -> None:
        item = self.tree_widget.currentItem()
        lid = item.data(0, Qt.ItemDataRole.UserRole) if item else self.project.active_layer_id
        target = self.project.get_layer(lid)
        if target and not target.is_group:
            confirm = QMessageBox.question(
                self,
                "Wyczyść warstwę",
                f"Czy wyczyścić kafelki z warstwy '{target.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                target.clear()
                self.refresh_layers()
                self.layer_changed.emit()

    def _move_up(self) -> None:
        item = self.tree_widget.currentItem()
        lid = item.data(0, Qt.ItemDataRole.UserRole) if item else self.project.active_layer_id
        if not lid:
            return
        idx = self.project.get_layer_index(lid)
        if idx is not None and idx < len(self.project.layers) - 1:
            cmd = LayerMoveCommand(self.project, idx, idx + 1)
            self.history_manager.push(cmd)
            self.refresh_layers()
            self.layer_changed.emit()

    def _move_down(self) -> None:
        item = self.tree_widget.currentItem()
        lid = item.data(0, Qt.ItemDataRole.UserRole) if item else self.project.active_layer_id
        if not lid:
            return
        idx = self.project.get_layer_index(lid)
        if idx is not None and idx > 0:
            cmd = LayerMoveCommand(self.project, idx, idx - 1)
            self.history_manager.push(cmd)
            self.refresh_layers()
            self.layer_changed.emit()

    def _on_context_menu(self, pos) -> None:
        item = self.tree_widget.itemAt(pos)
        if not item:
            return
        lid = item.data(0, Qt.ItemDataRole.UserRole)
        layer = self.project.get_layer(lid)
        if not layer:
            return

        menu = QMenu(self)
        menu.addAction("✏️ Zmień nazwę", lambda: self._on_item_double_clicked(item, 0))

        if not layer.is_group:
            groups = [l for l in self.project.layers if l.is_group and l.id != layer.id]
            if groups:
                grp_menu = menu.addMenu("📁 Przenieś do grupy...")
                grp_menu.addAction("Brak grupy (główny poziom)", lambda: self._set_parent_group(layer, None))
                for g in groups:
                    grp_menu.addAction(f"Grupa: {g.name}", lambda g_id=g.id: self._set_parent_group(layer, g_id))

        menu.addSeparator()
        menu.addAction("🗑️ Usuń", self._delete_layer)
        menu.exec(self.tree_widget.mapToGlobal(pos))

    def _set_parent_group(self, layer: Layer, parent_id: Optional[str]) -> None:
        layer.group_id = parent_id
        self.refresh_layers()
        self.layer_changed.emit()
