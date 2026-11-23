from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QTabBar,
    QToolButton,
    QInputDialog,
    QMessageBox,
    QMenu,
)
from ..models.project import Project
from .icons import IconFactory


class MapTabBar(QWidget):
    """
    Top tab bar above the map canvas for navigating between multiple maps (Aseprite & Tiled style).
    Supports:
    - Switching active map
    - Adding new map (+)
    - Closing / deleting map (x)
    - Context menu: Rename, Duplicate, Map Settings
    """
    map_selected = pyqtSignal(str)          # map_id
    new_map_requested = pyqtSignal()
    map_closed = pyqtSignal(str)            # map_id
    map_renamed = pyqtSignal(str, str)      # map_id, new_name
    map_duplicated = pyqtSignal(str)        # map_id

    def __init__(self, project: Project, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.project = project

        self._init_ui()
        self.refresh_tabs()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 0)
        layout.setSpacing(2)

        self.tab_bar = QTabBar(self)
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setStyleSheet("""
            QTabBar::tab {
                background: #1e1e24;
                color: #a1a1aa;
                border: 1px solid #2e2e38;
                border-bottom: none;
                padding: 6px 14px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 11px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: #272730;
                color: #60a5fa;
                border-color: #3b82f6;
                border-bottom: 2px solid #3b82f6;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected {
                background: #25252d;
                color: #e4e4e7;
            }
            QTabBar::close-button {
                image: none;
                subcontrol-position: right;
            }
        """)

        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        self.tab_bar.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(self._on_context_menu)

        layout.addWidget(self.tab_bar)

        self.btn_add_map = QToolButton(self)
        self.btn_add_map.setIcon(IconFactory.get_icon("plus", 14))
        self.btn_add_map.setToolTip("Utwórz nową mapę w projekcie")
        self.btn_add_map.setStyleSheet("""
            QToolButton {
                background: #1e1e24;
                color: #a1a1aa;
                border: 1px solid #2e2e38;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QToolButton:hover {
                background: #2b2b36;
                color: #ffffff;
                border-color: #3b82f6;
            }
        """)
        self.btn_add_map.clicked.connect(self._on_add_map_clicked)
        layout.addWidget(self.btn_add_map)

        layout.addStretch()

    def set_project(self, project: Project) -> None:
        self.project = project
        self.refresh_tabs()

    def refresh_tabs(self) -> None:
        self.tab_bar.blockSignals(True)
        while self.tab_bar.count() > 0:
            self.tab_bar.removeTab(0)

        active_idx = 0
        for i, m in enumerate(self.project.maps.values()):
            idx = self.tab_bar.addTab(IconFactory.get_icon("map", 16), m.name)
            self.tab_bar.setTabData(idx, m.id)
            if m.id == self.project.active_map_id:
                active_idx = idx

        if self.tab_bar.count() > 0:
            self.tab_bar.setCurrentIndex(active_idx)

        self.tab_bar.blockSignals(False)

    def _on_tab_changed(self, index: int) -> None:
        if index < 0 or index >= self.tab_bar.count():
            return
        map_id = self.tab_bar.tabData(index)
        if map_id:
            self.project.set_active_map(map_id)
            self.map_selected.emit(map_id)

    def _on_tab_close_requested(self, index: int) -> None:
        if self.tab_bar.count() <= 1:
            QMessageBox.warning(self, "Nie można zamknąć", "Projekt musi zawierać co najmniej jedną mapę.")
            return

        map_id = self.tab_bar.tabData(index)
        m = self.project.maps.get(map_id)
        name = m.name if m else "tę mapę"

        res = QMessageBox.question(
            self,
            "Usunięcie mapy",
            f"Czy na pewno chcesz usunąć mapę '{name}' z projektu?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            self.project.remove_map(map_id)
            self.refresh_tabs()
            self.map_closed.emit(map_id)

    def _on_add_map_clicked(self) -> None:
        self.new_map_requested.emit()

    def _on_context_menu(self, pos) -> None:
        tab_idx = self.tab_bar.tabAt(pos)
        if tab_idx < 0:
            return

        map_id = self.tab_bar.tabData(tab_idx)
        m = self.project.maps.get(map_id)
        if not m:
            return

        menu = QMenu(self)
        act_rename = menu.addAction(IconFactory.get_icon("pencil", 16), "Zmień nazwę mapy...")
        act_dup = menu.addAction(IconFactory.get_icon("copy", 16), "Duplikuj mapę")
        menu.addSeparator()
        act_close = menu.addAction(IconFactory.get_icon("trash", 16), "Usuń mapę")
        if self.tab_bar.count() <= 1:
            act_close.setEnabled(False)

        action = menu.exec(self.tab_bar.mapToGlobal(pos))
        if action == act_rename:
            new_name, ok = QInputDialog.getText(self, "Zmiana nazwy mapy", "Podaj nową nazwę:", text=m.name)
            if ok and new_name.strip():
                self.project.rename_map(map_id, new_name.strip())
                self.refresh_tabs()
                self.map_renamed.emit(map_id, new_name.strip())
        elif action == act_dup:
            clone = self.project.duplicate_map(map_id)
            if clone:
                self.refresh_tabs()
                self.map_duplicated.emit(clone.id)
        elif action == act_close:
            self._on_tab_close_requested(tab_idx)
