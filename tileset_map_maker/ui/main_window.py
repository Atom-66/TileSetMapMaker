import os
from typing import Optional, List
from PyQt6.QtCore import Qt, QSize, QSettings
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QToolBar,
    QDockWidget,
    QStatusBar,
    QLabel,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QApplication,
)
from PyQt6.QtGui import QAction, QKeySequence, QIcon

from ..models.project import Project
from ..core.asset_manager import AssetManager
from ..core.render_engine import RenderEngine
from ..core.history import HistoryManager
from ..core.project_io import ProjectIO
from ..core.autotile_engine import AutoTileEngine
from ..core.set_manager import SetManager
from ..core.stamp_manager import StampManager
from ..core.tools.select_tool import SelectTool
from ..core.tools.object_tool import ObjectTool
from .map_canvas import MapCanvas
from .asset_library_widget import AssetLibraryWidget
from .layer_panel import LayerPanel
from .tool_panel import ToolPanel
from .brush_options_bar import BrushOptionsBar
from .dialogs import MapSettingsDialog, ExportDialog, ShortcutsDialog
from .dialogs.autotile_dialog import AutoTileDialog


class MainWindow(QMainWindow):
    """Main window for TileSet Map Maker desktop application (Etap 2 Advanced)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TileSet Map Maker")
        self.resize(1400, 880)

        # Core systems
        self.asset_manager = AssetManager()
        self.history_manager = HistoryManager()
        self.set_manager = SetManager()
        self.stamp_manager = StampManager()
        self.autotile_engine = AutoTileEngine()

        self.project = Project(map_width=30, map_height=20, tile_size=32)
        self.render_engine = RenderEngine(self.asset_manager)

        self._init_ui()
        self._init_shortcuts()
        self._connect_events()
        self._restore_settings()
        self._update_title()
        self._update_status_bar()

    def _init_ui(self) -> None:
        central_container = QWidget()
        central_layout = QVBoxLayout(central_container)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # Contextual Brush Options Ribbon (Top of Canvas)
        self.canvas = MapCanvas(
            project=self.project,
            render_engine=self.render_engine,
            asset_manager=self.asset_manager,
            history_manager=self.history_manager,
        )
        self.canvas.tool_context.autotile_engine = self.autotile_engine
        self.canvas.tool_context.stamp_manager = self.stamp_manager
        self.canvas.tool_context.set_manager = self.set_manager

        self.brush_options = BrushOptionsBar(self.canvas.tool_context.brush_settings)
        self.brush_options.options_changed.connect(self.canvas.update)
        central_layout.addWidget(self.brush_options)

        # Middle row: Tool Panel + Map Canvas
        mid_widget = QWidget()
        mid_layout = QHBoxLayout(mid_widget)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(0)

        self.tool_panel = ToolPanel()
        mid_layout.addWidget(self.tool_panel)
        mid_layout.addWidget(self.canvas, 1)

        central_layout.addWidget(mid_widget, 1)
        self.setCentralWidget(central_container)

        # Initial tool setup
        self.canvas.set_tool(self.tool_panel.get_tool("brush"))

        # Dock Widgets: Left (Library / Sets / Stamps) & Right (Layers & Groups)
        self.left_dock = QDockWidget("Biblioteka kafelków i zestawów", self)
        self.left_dock.setObjectName("LeftDockLibrary")
        self.left_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.asset_library = AssetLibraryWidget(
            self.asset_manager,
            set_manager=self.set_manager,
            stamp_manager=self.stamp_manager,
            parent=self.left_dock,
        )
        self.left_dock.setWidget(self.asset_library)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)

        self.right_dock = QDockWidget("Warstwy i grupy mapy", self)
        self.right_dock.setObjectName("RightDockLayers")
        self.right_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.layer_panel = LayerPanel(self.project, self.history_manager, self.right_dock)
        self.right_dock.setWidget(self.layer_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.right_dock)

        # Top Toolbar
        self._init_toolbar()

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.lbl_status_pos = QLabel("Kursor: (0, 0)")
        self.lbl_status_size = QLabel(f"Wymiary: {self.project.map_width}x{self.project.map_height} ({self.project.tile_size}px)")
        self.lbl_status_zoom = QLabel("Zoom: 200%")
        self.lbl_status_layer = QLabel("Warstwa: Ground")
        self.lbl_status_asset = QLabel("Zasób: Brak")

        self.status_bar.addWidget(self.lbl_status_pos)
        self.status_bar.addWidget(self.lbl_status_size)
        self.status_bar.addWidget(self.lbl_status_zoom)
        self.status_bar.addWidget(self.lbl_status_layer)
        self.status_bar.addWidget(self.lbl_status_asset)

    def _init_toolbar(self) -> None:
        self.toolbar = QToolBar("Główny pasek narzędzi")
        self.toolbar.setObjectName("MainToolBar")
        self.toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        self.act_new = QAction("📄 Nowy", self)
        self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_new.setToolTip("Nowy projekt (Ctrl+N)")
        self.act_new.triggered.connect(self.new_project)
        self.toolbar.addAction(self.act_new)

        self.act_open = QAction("📂 Otwórz", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.setToolTip("Otwórz projekt (Ctrl+O)")
        self.act_open.triggered.connect(self.open_project)
        self.toolbar.addAction(self.act_open)

        self.act_save = QAction("💾 Zapisz", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.setToolTip("Zapisz projekt (Ctrl+S)")
        self.act_save.triggered.connect(self.save_project)
        self.toolbar.addAction(self.act_save)

        self.toolbar.addSeparator()

        self.act_undo = QAction("↩️ Cofnij", self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.setToolTip("Cofnij operację (Ctrl+Z)")
        self.act_undo.setEnabled(False)
        self.act_undo.triggered.connect(self.history_manager.undo)
        self.toolbar.addAction(self.act_undo)

        self.act_redo = QAction("↪️ Ponów", self)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.act_redo.setToolTip("Ponów operację (Ctrl+Y)")
        self.act_redo.setEnabled(False)
        self.act_redo.triggered.connect(self.history_manager.redo)
        self.toolbar.addAction(self.act_redo)

        self.toolbar.addSeparator()

        self.act_grid = QAction("▦ Siatka", self)
        self.act_grid.setCheckable(True)
        self.act_grid.setChecked(True)
        self.act_grid.setShortcut("Ctrl+G")
        self.act_grid.setToolTip("Przełącz widoczność siatki (Ctrl+G)")
        self.act_grid.triggered.connect(lambda: self.canvas.toggle_grid(self.act_grid.isChecked()))
        self.toolbar.addAction(self.act_grid)

        self.act_fit = QAction("🎯 Dopasuj", self)
        self.act_fit.setShortcut("Ctrl+F")
        self.act_fit.setToolTip("Dopasuj mapę do okna (Ctrl+F)")
        self.act_fit.triggered.connect(self.canvas.fit_to_view)
        self.toolbar.addAction(self.act_fit)

        self.toolbar.addSeparator()

        # Auto-Tiling configuration dialog
        self.act_autotile = QAction("⚡ Auto-Tile", self)
        self.act_autotile.setToolTip("Konfigurator reguł Auto-Tiling i połączeń terenu")
        self.act_autotile.triggered.connect(self.open_autotile_dialog)
        self.toolbar.addAction(self.act_autotile)

        # Save stamp from selection
        self.act_save_stamp = QAction("📑 Zapisz stempel", self)
        self.act_save_stamp.setToolTip("Zapisz zaznaczony fragment mapy jako trwały stempel w bibliotece")
        self.act_save_stamp.triggered.connect(self.save_selection_as_stamp)
        self.toolbar.addAction(self.act_save_stamp)

        self.toolbar.addSeparator()

        self.act_settings = QAction("⚙️ Ustawienia mapy", self)
        self.act_settings.setToolTip("Zmień rozmiar mapy, kafelków lub tło")
        self.act_settings.triggered.connect(self.open_map_settings)
        self.toolbar.addAction(self.act_settings)

        self.act_export = QAction("🖼️ Eksport PNG", self)
        self.act_export.setShortcut("Ctrl+E")
        self.act_export.setToolTip("Eksportuj gotową mapę do pliku PNG (Ctrl+E)")
        self.act_export.triggered.connect(self.export_png_dialog)
        self.toolbar.addAction(self.act_export)

        self.toolbar.addSeparator()

        self.act_shortcuts = QAction("⌨️ Skróty", self)
        self.act_shortcuts.setToolTip("Lista skrótów klawiszowych")
        self.act_shortcuts.triggered.connect(self.open_shortcuts_dialog)
        self.toolbar.addAction(self.act_shortcuts)

        self.act_reset_ui = QAction("🔄 Reset paneli", self)
        self.act_reset_ui.setToolTip("Przywróć domyślny układ paneli")
        self.act_reset_ui.triggered.connect(self._reset_dock_layout)
        self.toolbar.addAction(self.act_reset_ui)

    def _init_shortcuts(self) -> None:
        tool_keys = {
            Qt.Key.Key_B: "brush",
            Qt.Key.Key_E: "eraser",
            Qt.Key.Key_G: "fill",
            Qt.Key.Key_L: "line",
            Qt.Key.Key_U: "rect",
            Qt.Key.Key_S: "select",
            Qt.Key.Key_V: "object",
            Qt.Key.Key_I: "eyedropper",
            Qt.Key.Key_T: "stamp",
        }
        for key, name in tool_keys.items():
            act = QAction(self)
            act.setShortcut(QKeySequence(key))
            act.triggered.connect(lambda checked, n=name: self.tool_panel.select_tool_by_key(n))
            self.addAction(act)

        act_copy = QAction(self)
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.triggered.connect(self._copy_selection)
        self.addAction(act_copy)

        act_paste = QAction(self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(self._paste_stamp)
        self.addAction(act_paste)

        act_delete = QAction(self)
        act_delete.setShortcut(QKeySequence.StandardKey.Delete)
        act_delete.triggered.connect(self._delete_selection)
        self.addAction(act_delete)

    def _connect_events(self) -> None:
        self.tool_panel.tool_changed.connect(self.canvas.set_tool)
        self.layer_panel.layer_changed.connect(self._on_layers_modified)
        self.canvas.cursor_moved.connect(self._on_cursor_moved)
        self.canvas.zoom_changed.connect(self._on_zoom_changed)
        self.canvas.files_dropped.connect(self._on_files_dropped)

        self.asset_manager.asset_selected.connect(self._on_asset_selected)
        self.history_manager.history_changed.connect(self._on_history_changed)
        self.asset_library.variant_added.connect(self._on_variant_added)

    def _on_variant_added(self, item) -> None:
        bs = self.canvas.tool_context.brush_settings
        if item not in bs.variants:
            bs.variants.append(item)
            bs.random_variant = True
            self.brush_options.chk_variants.setChecked(True)
            self.statusBar().showMessage(f"Dodano wariant do pędzla (łącznie wariantów: {len(bs.variants)})", 3000)

    def _update_title(self) -> None:
        mod = "*" if self.project.is_modified else ""
        name = self.project.name
        self.setWindowTitle(f"{mod}{name} – TileSet Map Maker")

    def _update_status_bar(self) -> None:
        self.lbl_status_size.setText(
            f"Wymiary: {self.project.map_width}x{self.project.map_height} ({self.project.tile_size}px)"
        )
        layer = self.project.get_active_layer()
        self.lbl_status_layer.setText(f"Warstwa: {layer.name if layer else 'Brak'}")

    def _on_cursor_moved(self, col: int, row: int) -> None:
        self.lbl_status_pos.setText(f"Kursor: ({col}, {row})")

    def _on_zoom_changed(self, zoom: float) -> None:
        self.lbl_status_zoom.setText(f"Zoom: {int(zoom * 100)}%")

    def _on_asset_selected(self, item) -> None:
        if item:
            name = getattr(item, "name", "SubTile")
            self.lbl_status_asset.setText(f"Zasób: {name}")
        else:
            self.lbl_status_asset.setText("Zasób: Brak")

    def _on_history_changed(self, can_undo: bool, can_redo: bool, undo_desc: str, redo_desc: str) -> None:
        self.act_undo.setEnabled(can_undo)
        self.act_undo.setToolTip(f"Cofnij: {undo_desc}" if undo_desc else "Cofnij (Ctrl+Z)")
        self.act_redo.setEnabled(can_redo)
        self.act_redo.setToolTip(f"Ponów: {redo_desc}" if redo_desc else "Ponów (Ctrl+Y)")
        self._update_title()
        self.canvas.update()

    def _on_layers_modified(self) -> None:
        self._update_title()
        self._update_status_bar()
        self.canvas.set_active_layer(self.project.get_active_layer())
        self.canvas.update()

    def _on_files_dropped(self, paths: List[str]) -> None:
        for p in paths:
            if os.path.isdir(p):
                self.asset_manager.import_folder(p)
            elif os.path.isfile(p):
                self.asset_manager.import_single_file(p)
        self.asset_library.refresh_categories()
        self.asset_library.refresh_assets_list()

    def _copy_selection(self) -> None:
        tool = self.tool_panel.get_tool("select")
        if isinstance(tool, SelectTool):
            tool.copy_selection(self.canvas.tool_context)
            self.statusBar().showMessage("Skopiowano zaznaczenie do schowka.", 2500)

    def _paste_stamp(self) -> None:
        if self.canvas.tool_context.clipboard_tiles:
            self.tool_panel.select_tool_by_key("stamp")

    def _delete_selection(self) -> None:
        tool = self.tool_panel.get_tool("select")
        if isinstance(tool, SelectTool):
            tool.delete_selection(self.canvas.tool_context)
            self.canvas.update()
        obj_tool = self.tool_panel.get_tool("object")
        if isinstance(obj_tool, ObjectTool) and obj_tool.selected_ids and self.project.get_active_layer():
            for oid in list(obj_tool.selected_ids):
                self.project.get_active_layer().remove_object(oid)
            obj_tool.selected_ids.clear()
            self.canvas.tool_context.selected_object_ids.clear()
            self.canvas.update()

    def save_selection_as_stamp(self) -> None:
        tool = self.tool_panel.get_tool("select")
        if isinstance(tool, SelectTool) and tool.selection_rect:
            name, ok = QInputDialog.getText(self, "Zapisz stempel", "Nazwa nowego stempla:", text="Mój stempel")
            if ok and name.strip():
                preset = tool.save_as_stamp_preset(name.strip(), self.canvas.tool_context)
                if preset:
                    self.asset_library.refresh_stamps_list()
                    QMessageBox.information(self, "Zapisano", f"Stempel '{preset.name}' został zapisany w bibliotece!")
        else:
            QMessageBox.warning(self, "Brak zaznaczenia", "Zaznacz najpierw obszar mapy narzędziem Zaznaczanie (S).")

    def open_autotile_dialog(self) -> None:
        dlg = AutoTileDialog(self.autotile_engine, self.asset_manager, self)
        dlg.exec()

    def new_project(self) -> None:
        self.project = Project(name="Nowy Projekt", map_width=30, map_height=20, tile_size=32)
        self.history_manager.clear()
        self.canvas.set_project(self.project)
        self.layer_panel.set_project(self.project)
        self._update_title()
        self._update_status_bar()

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Otwórz projekt mapy",
            "",
            "Projekty mapy (*.tmmap);;Wszystkie pliki (*.*)",
        )
        if path:
            proj = ProjectIO.load_project(path, self.asset_manager)
            if proj:
                self.project = proj
                self.history_manager.clear()
                self.canvas.set_project(self.project)
                self.layer_panel.set_project(self.project)
                self.asset_library.refresh_categories()
                self.asset_library.refresh_sets_list()
                self.asset_library.refresh_assets_list()
                self._update_title()
                self._update_status_bar()
            else:
                QMessageBox.critical(self, "Błąd", "Nie udało się otworzyć pliku projektu.")

    def save_project(self) -> None:
        if not self.project.file_path:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Zapisz projekt mapy",
                f"{self.project.name.replace(' ', '_')}.tmmap",
                "Projekty mapy (*.tmmap)",
            )
            if not path:
                return
            self.project.file_path = path

        ok = ProjectIO.save_project(self.project, self.asset_manager, self.project.file_path)
        if ok:
            self._update_title()
            self.statusBar().showMessage("Projekt zapisany pomyślnie.", 3000)
        else:
            QMessageBox.critical(self, "Błąd", "Nie udało się zapisać projektu.")

    def open_map_settings(self) -> None:
        dlg = MapSettingsDialog(self.project, self)
        if dlg.exec():
            self._update_status_bar()
            self.canvas.fit_to_view()
            self.canvas.update()

    def export_png_dialog(self) -> None:
        dlg = ExportDialog(self.project, self.render_engine, self)
        dlg.exec()

    def open_shortcuts_dialog(self) -> None:
        dlg = ShortcutsDialog(self)
        dlg.exec()

    def _reset_dock_layout(self) -> None:
        self.left_dock.show()
        self.right_dock.show()
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.right_dock)
        self.canvas.fit_to_view()

    def _restore_settings(self) -> None:
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        geom = settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        state = settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event) -> None:
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        super().closeEvent(event)
