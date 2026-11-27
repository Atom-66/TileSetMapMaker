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
from ..core.localization import get_localization, tr


_HISTORY_DESCRIPTION_KEYS = {
    "Edycja kafelków": "history.command.tile_edit",
    "Dodaj obiekt": "history.command.object_add",
    "Usuń obiekt": "history.command.object_remove",
    "Zmień kolejność warstw": "history.command.layer_reorder",
    "Rysowanie pędzlem": "history.command.brush_paint",
    "Dodanie obiektu pędzlem": "history.command.brush_object",
    "Użycie gumki": "history.command.eraser",
    "Usunięcie obiektu gumką": "history.command.eraser_object",
    "Wypełnienie wiadrem": "history.command.fill",
    "Usunięcie zaznaczenia różdżką": "history.command.wand",
    "Usunięcie zaznaczenia": "history.command.selection_delete",
    "Użycie stempla": "history.command.stamp",
    "Rysowanie linii": "history.command.line",
    "Rysowanie prostokąta": "history.command.rectangle",
    "Przelosowanie wariantów kafelków": "history.command.randomize",
    "Wyrównanie obiektów": "history.command.object_align",
    "Przesunięcie obiektu": "history.command.object_move",
    "Obrót obiektu": "history.command.object_rotate",
    "Obrót gizmo": "history.command.gizmo_rotate",
    "Wypełnienie zaznaczenia": "history.command.selection_fill",
    "Przesunięcie zaznaczenia": "history.command.selection_move",
    "Obrót zaznaczenia": "history.command.selection_rotate",
}


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
        get_localization().languageChanged.connect(self._retranslate)
        self._retranslate()
        self.refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 11px; color: #a1a1aa;")
        header.addWidget(self.lbl_title)
        header.addStretch()

        self.btn_undo = QToolButton(self)
        self.btn_undo.setIcon(IconFactory.get_icon("undo", 16))
        self.btn_undo.clicked.connect(lambda: self.history_manager.undo())
        header.addWidget(self.btn_undo)

        self.btn_redo = QToolButton(self)
        self.btn_redo.setIcon(IconFactory.get_icon("redo", 16))
        self.btn_redo.clicked.connect(lambda: self.history_manager.redo())
        header.addWidget(self.btn_redo)

        layout.addLayout(header)

        self.list_history = QListWidget(self)
        self.list_history.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_history)

    def _retranslate(self, *_args) -> None:
        self.lbl_title.setText(tr("history.title"))
        self.btn_undo.setToolTip(tr("history.undo_tooltip"))
        self.btn_redo.setToolTip(tr("history.redo_tooltip"))
        self.refresh()

    @staticmethod
    def _translated_description(description: str) -> str:
        if description.startswith("Dodaj warstwę '") and description.endswith("'"):
            name = description[len("Dodaj warstwę '"):-1]
            return tr("history.command.layer_add", name=name)
        if description.startswith("Usuń warstwę '") and description.endswith("'"):
            name = description[len("Usuń warstwę '"):-1]
            return tr("history.command.layer_remove", name=name)
        if description.startswith("Wyczyść warstwę '") and description.endswith("'"):
            name = description[len("Wyczyść warstwę '"):-1]
            return tr("history.command.layer_clear", name=name)
        key = _HISTORY_DESCRIPTION_KEYS.get(description)
        return tr(key) if key else description

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
        init_item = QListWidgetItem(tr("history.initial"))
        init_item.setIcon(IconFactory.get_icon("fit", 16))
        if not self.history_manager.undo_stack:
            init_item.setSelected(True)
        self.list_history.addItem(init_item)

        # Undo stack items
        for cmd in self.history_manager.undo_stack:
            item = QListWidgetItem(self._translated_description(cmd.description))
            item.setIcon(IconFactory.get_icon("check", 16))
            self.list_history.addItem(item)

        # Highlight current state
        if self.history_manager.undo_stack:
            self.list_history.setCurrentRow(len(self.history_manager.undo_stack))

        # Redo stack items (dimmed)
        for cmd in reversed(self.history_manager.redo_stack):
            description = self._translated_description(cmd.description)
            item = QListWidgetItem(f"{description} {tr('history.undone_suffix')}")
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
