from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QToolButton,
)
from ..core.history import HistoryManager
from .icons import IconFactory


class HistoryPanel(QWidget):
    """
    Undo/Redo command history panel (inspired by Photoshop & Aseprite).
    Displays operations list and allows jumping back and forth.
    """

    def __init__(self, history_manager: HistoryManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.history_manager = history_manager

        self._init_ui()
        self.history_manager.history_changed.connect(self.refresh)
        self.refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        lbl = QLabel("HISTORIA OPERACJI")
        lbl.setStyleSheet("font-weight: 600; font-size: 11px; color: #a1a1aa;")
        header.addWidget(lbl)
        header.addStretch()

        btn_undo = QToolButton(self)
        btn_undo.setIcon(IconFactory.get_icon("undo", 16))
        btn_undo.setToolTip("Cofnij (Ctrl+Z)")
        btn_undo.clicked.connect(lambda: self.history_manager.undo())
        header.addWidget(btn_undo)

        btn_redo = QToolButton(self)
        btn_redo.setIcon(IconFactory.get_icon("redo", 16))
        btn_redo.setToolTip("Ponów (Ctrl+Y)")
        btn_redo.clicked.connect(lambda: self.history_manager.redo())
        header.addWidget(btn_redo)

        layout.addLayout(header)

        self.list_history = QListWidget(self)
        self.list_history.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_history)

    def set_history_manager(self, history_manager: HistoryManager) -> None:
        """Switch active history manager when map changes."""
        try:
            self.history_manager.history_changed.disconnect(self.refresh)
        except Exception:
            pass
        self.history_manager = history_manager
        self.history_manager.history_changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *args) -> None:
        self.list_history.clear()
        # Initial base state
        init_item = QListWidgetItem("Stan początkowy")
        init_item.setIcon(IconFactory.get_icon("fit", 16))
        if not self.history_manager.undo_stack:
            init_item.setSelected(True)
        self.list_history.addItem(init_item)

        # Undo stack items
        for cmd in self.history_manager.undo_stack:
            item = QListWidgetItem(cmd.description)
            item.setIcon(IconFactory.get_icon("check", 16))
            self.list_history.addItem(item)

        # Highlight current state
        if self.history_manager.undo_stack:
            self.list_history.setCurrentRow(len(self.history_manager.undo_stack))

        # Redo stack items (dimmed)
        for cmd in reversed(self.history_manager.redo_stack):
            item = QListWidgetItem(f"{cmd.description} (cofnięto)")
            item.setIcon(IconFactory.get_icon("undo", 16))
            item.setForeground(Qt.GlobalColor.darkGray)
            self.list_history.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        target_row = self.list_history.row(item)
        current_row = len(self.history_manager.undo_stack)

        if target_row < current_row:
            # Need to undo (current_row - target_row) times
            for _ in range(current_row - target_row):
                self.history_manager.undo()
        elif target_row > current_row:
            # Need to redo (target_row - current_row) times
            for _ in range(target_row - current_row):
                self.history_manager.redo()
