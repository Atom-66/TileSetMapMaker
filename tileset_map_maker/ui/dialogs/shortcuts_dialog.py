from typing import Optional
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QWidget,
    QLabel,
)
from PyQt6.QtCore import Qt
from ..icons import IconFactory
from ...core.localization import tr


class ShortcutsDialog(QDialog):
    """Reference dialog showing all keyboard shortcuts."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.shortcuts.title"))
        self.resize(500, 480)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        lbl = QLabel(tr("dialog.shortcuts.description"))
        lbl.setStyleSheet("font-weight: 600; color: #a1a1aa;")
        layout.addWidget(lbl)

        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(
            [tr("dialog.shortcuts.action"), tr("dialog.shortcuts.shortcut")]
        )
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        shortcuts = [
            ("new_project", "Ctrl + N"),
            ("open_project", "Ctrl + O"),
            ("save_project", "Ctrl + S"),
            ("undo", "Ctrl + Z"),
            ("redo", "Ctrl + Y"),
            ("brush", "B"),
            ("eraser", "E"),
            ("fill", "G"),
            ("line", "L"),
            ("rectangle", "U"),
            ("selection", "S"),
            ("free_object", "V"),
            ("eyedropper", "I"),
            ("stamp", "T"),
            ("rotate", "R"),
            ("flip_h", "H"),
            ("flip_v", "V"),
            ("scale", "+ / -"),
            ("duplicate", "Ctrl + D"),
            ("pan", tr("dialog.shortcuts.key_pan")),
            ("zoom", tr("dialog.shortcuts.key_zoom")),
            ("copy", "Ctrl + C"),
            ("paste", "Ctrl + V"),
            ("delete", "Delete"),
            ("grid", "Ctrl + G"),
            ("fit", "Ctrl + F"),
            ("export", "Ctrl + E"),
        ]

        table.setRowCount(len(shortcuts))
        for row, (action_key, key) in enumerate(shortcuts):
            item_act = QTableWidgetItem(tr(f"dialog.shortcuts.{action_key}"))
            item_key = QTableWidgetItem(key)
            item_key.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, item_act)
            table.setItem(row, 1, item_key)

        layout.addWidget(table)

        btn_close = QPushButton(f" {tr('dialog.shortcuts.close')}")
        btn_close.setIcon(IconFactory.get_icon("close", 14))
        btn_close.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
