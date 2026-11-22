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


class ShortcutsDialog(QDialog):
    """Reference dialog showing all keyboard shortcuts."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Skróty klawiszowe")
        self.resize(500, 480)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        lbl = QLabel("Konfigurowalne skróty klawiszowe w edytorze:")
        lbl.setStyleSheet("font-weight: 600; color: #a1a1aa;")
        layout.addWidget(lbl)

        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Działanie", "Skrót klawiszowy"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        shortcuts = [
            ("Nowy projekt", "Ctrl + N"),
            ("Otwórz projekt", "Ctrl + O"),
            ("Zapisz projekt", "Ctrl + S"),
            ("Cofnij operację", "Ctrl + Z"),
            ("Ponów operację", "Ctrl + Y"),
            ("Pędzel", "B"),
            ("Gumka", "E"),
            ("Wypełnianie (wiadro)", "G"),
            ("Linia", "L"),
            ("Prostokąt", "U"),
            ("Zaznaczanie", "S"),
            ("Swobodny obiekt", "V"),
            ("Pipeta", "I"),
            ("Stempel", "T"),
            ("Obrót obiektu / stempla", "R"),
            ("Odbicie obiektu w poziomie", "H"),
            ("Odbicie obiektu w pionie", "V"),
            ("Skalowanie obiektu w górę / dół", "+ / -"),
            ("Duplikuj obiekt", "Ctrl + D"),
            ("Przesuwanie widoku (Pan)", "Spacja + Przeciąganie / Środkowy przycisk myszy"),
            ("Powiększenie / Pomniejszenie", "Rolka myszy"),
            ("Kopiuj zaznaczenie", "Ctrl + C"),
            ("Wklej (stempel)", "Ctrl + V"),
            ("Usuń zaznaczenie / obiekt", "Delete"),
            ("Przełącz siatkę kafelków", "Ctrl + G"),
            ("Dopasuj mapę do okna", "Ctrl + F"),
            ("Eksport PNG", "Ctrl + E"),
        ]

        table.setRowCount(len(shortcuts))
        for row, (action, key) in enumerate(shortcuts):
            item_act = QTableWidgetItem(action)
            item_key = QTableWidgetItem(key)
            item_key.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, item_act)
            table.setItem(row, 1, item_key)

        layout.addWidget(table)

        btn_close = QPushButton("Zamknij")
        btn_close.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
