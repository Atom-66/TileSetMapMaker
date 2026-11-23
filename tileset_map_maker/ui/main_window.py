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
from ..models.asset import Asset, AssetType, SelectedSubTile
from ..core.asset_manager import AssetManager
from ..core.render_engine import RenderEngine
from ..core.history import HistoryManager
from ..core.project_io import ProjectIO
from ..core.autosave_manager import AutosaveManager
from ..core.autotile_engine import AutoTileEngine
from ..core.set_manager import SetManager
from ..core.stamp_manager import StampManager
from ..core.tools.select_tool import SelectTool
from ..core.tools.wand import WandTool
from ..core.tools.object_tool import ObjectTool
from .icons import IconFactory
from .map_canvas import MapCanvas
from .tileset_palette_widget import TilesetPaletteWidget
from .map_tab_bar import MapTabBar
from .properties_panel import PropertiesPanel
from .history_panel import HistoryPanel
from .layer_panel import LayerPanel
from .tool_panel import ToolPanel
from .brush_options_bar import BrushOptionsBar
from .minimap_widget import MinimapWidget
from .dialogs import MapSettingsDialog, ExportDialog, ShortcutsDialog, PreferencesDialog
from .dialogs.autotile_dialog import AutoTileDialog
from .dialogs.tileset_import_dialog import TilesetImportDialog


class MainWindow(QMainWindow):
    """Main window for TileSet Map Maker desktop application (Etap 2 Advanced)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TileSet Map Maker")
        self.resize(1400, 880)

        # Core systems
        self.asset_manager = AssetManager()
        self.project = Project(map_width=30, map_height=20, tile_size=32)
        self.map_histories: Dict[str, HistoryManager] = {}
        self.history_manager = self.get_map_history(self.project.active_map_id)
        self.set_manager = SetManager()
        self.stamp_manager = StampManager()
        self.autotile_engine = AutoTileEngine()
        self.autosave_manager = AutosaveManager(self.project, self.asset_manager, parent=self)
        self.autosave_manager.autosaved.connect(self._on_autosaved)

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

        # Multi-Map Tab Bar (Aseprite & Tiled style)
        self.map_tab_bar = MapTabBar(self.project, central_container)
        central_layout.addWidget(self.map_tab_bar)

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

        # Configure Photoshop / Tiled style docking options
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.GroupedDragging
            | QMainWindow.DockOption.AllowNestedDocks
        )

        dock_features = (
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        # Left Dock: Tileset Palette (Tiled-Style)
        self.tileset_dock = QDockWidget("Paleta kafelków (Tileset)", self)
        self.tileset_dock.setObjectName("TilesetPaletteDock")
        self.tileset_dock.setFeatures(dock_features)
        self.tileset_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea)
        self.tileset_palette = TilesetPaletteWidget(self.asset_manager, self.tileset_dock)
        self.tileset_dock.setWidget(self.tileset_palette)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tileset_dock)

        # Right Docks: Layers, Properties, History
        self.right_dock = QDockWidget("Warstwy i grupy mapy", self)
        self.right_dock.setObjectName("RightDockLayers")
        self.right_dock.setFeatures(dock_features)
        self.right_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.layer_panel = LayerPanel(self.project, self.history_manager, self.right_dock)
        self.right_dock.setWidget(self.layer_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.right_dock)

        self.properties_dock = QDockWidget("Właściwości", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setFeatures(dock_features)
        self.properties_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.properties_panel = PropertiesPanel(self.project, self.asset_manager, self.properties_dock)
        self.properties_dock.setWidget(self.properties_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.tabifyDockWidget(self.right_dock, self.properties_dock)

        self.history_dock = QDockWidget("Historia operacji", self)
        self.history_dock.setObjectName("HistoryDock")
        self.history_dock.setFeatures(dock_features)
        self.history_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.history_panel = HistoryPanel(self.history_manager, self.history_dock)
        self.history_dock.setWidget(self.history_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.history_dock)
        self.tabifyDockWidget(self.right_dock, self.history_dock)

        # Minimap Dock (TASK-505)
        self.minimap_dock = QDockWidget("Minimapa", self)
        self.minimap_dock.setObjectName("MinimapDock")
        self.minimap_dock.setFeatures(dock_features)
        self.minimap_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.minimap_widget = MinimapWidget(self.project, self.render_engine, self.canvas, self.minimap_dock)
        self.minimap_dock.setWidget(self.minimap_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.minimap_dock)
        self.tabifyDockWidget(self.right_dock, self.minimap_dock)

        self.right_dock.raise_()

        # Top Toolbar and Menu Bar
        self._init_toolbar()
        self._init_menubar()

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

        self.act_new = QAction(IconFactory.get_icon("new", 20), "Nowy", self)
        self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_new.setToolTip("Nowy projekt (Ctrl+N)")
        self.act_new.triggered.connect(self.new_project)
        self.toolbar.addAction(self.act_new)

        self.act_open = QAction(IconFactory.get_icon("open", 20), "Otwórz", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.setToolTip("Otwórz projekt (Ctrl+O)")
        self.act_open.triggered.connect(self.open_project)
        self.toolbar.addAction(self.act_open)

        self.act_save = QAction(IconFactory.get_icon("save", 20), "Zapisz", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.setToolTip("Zapisz projekt (Ctrl+S)")
        self.act_save.triggered.connect(self.save_project)
        self.toolbar.addAction(self.act_save)

        self.toolbar.addSeparator()

        self.act_undo = QAction(IconFactory.get_icon("undo", 20), "Cofnij", self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.setToolTip("Cofnij operację (Ctrl+Z)")
        self.act_undo.setEnabled(False)
        self.act_undo.triggered.connect(lambda: self.history_manager.undo())
        self.toolbar.addAction(self.act_undo)

        self.act_redo = QAction(IconFactory.get_icon("redo", 20), "Ponów", self)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.act_redo.setToolTip("Ponów operację (Ctrl+Y)")
        self.act_redo.setEnabled(False)
        self.act_redo.triggered.connect(lambda: self.history_manager.redo())
        self.toolbar.addAction(self.act_redo)

        self.toolbar.addSeparator()

        self.act_grid = QAction(IconFactory.get_icon("grid", 20), "Siatka", self)
        self.act_grid.setCheckable(True)
        self.act_grid.setChecked(True)
        self.act_grid.setShortcut("Ctrl+G")
        self.act_grid.setToolTip("Przełącz widoczność siatki (Ctrl+G)")
        self.act_grid.triggered.connect(lambda: self.canvas.toggle_grid(self.act_grid.isChecked()))
        self.toolbar.addAction(self.act_grid)

        self.act_fit = QAction(IconFactory.get_icon("fit", 20), "Dopasuj", self)
        self.act_fit.setShortcut("Ctrl+F")
        self.act_fit.setToolTip("Dopasuj mapę do okna (Ctrl+F)")
        self.act_fit.triggered.connect(self.canvas.fit_to_view)
        self.toolbar.addAction(self.act_fit)

        self.toolbar.addSeparator()

        # Auto-Tiling configuration dialog
        self.act_autotile = QAction(IconFactory.get_icon("autotile", 20), "Auto-Tile", self)
        self.act_autotile.setToolTip("Konfigurator reguł Auto-Tiling i połączeń terenu")
        self.act_autotile.triggered.connect(self.open_autotile_dialog)
        self.toolbar.addAction(self.act_autotile)

        # Save stamp from selection
        self.act_save_stamp = QAction(IconFactory.get_icon("save_stamp", 20), "Zapisz stempel", self)
        self.act_save_stamp.setToolTip("Zapisz zaznaczony fragment mapy jako trwały stempel w bibliotece")
        self.act_save_stamp.triggered.connect(self.save_selection_as_stamp)
        self.toolbar.addAction(self.act_save_stamp)

        self.toolbar.addSeparator()

        self.act_settings = QAction(IconFactory.get_icon("settings", 20), "Ustawienia", self)
        self.act_settings.setToolTip("Zmień rozmiar mapy, kafelków lub tło")
        self.act_settings.triggered.connect(self.open_map_settings)
        self.toolbar.addAction(self.act_settings)

        self.act_export = QAction(IconFactory.get_icon("export", 20), "Eksport PNG", self)
        self.act_export.setShortcut("Ctrl+E")
        self.act_export.setToolTip("Eksportuj gotową mapę do pliku PNG (Ctrl+E)")
        self.act_export.triggered.connect(self.export_png_dialog)
        self.toolbar.addAction(self.act_export)

        self.act_palette = self.tileset_dock.toggleViewAction()
        self.act_palette.setIcon(IconFactory.get_icon("grid", 20))
        self.act_palette.setText("Paleta")
        self.act_palette.setToolTip("Pokaż lub ukryj interaktywną paletę kafelków (Tiled-style)")
        self.toolbar.addAction(self.act_palette)

        self.toolbar.addSeparator()

        self.act_shortcuts = QAction(IconFactory.get_icon("shortcuts", 20), "Skróty", self)
        self.act_shortcuts.setToolTip("Lista skrótów klawiszowych")
        self.act_shortcuts.triggered.connect(self.open_shortcuts_dialog)
        self.toolbar.addAction(self.act_shortcuts)

        self.act_reset_ui = QAction(IconFactory.get_icon("reset_ui", 20), "Reset", self)
        self.act_reset_ui.setToolTip("Przywróć domyślny układ paneli")
        self.act_reset_ui.triggered.connect(self._reset_dock_layout)
        self.toolbar.addAction(self.act_reset_ui)

    def _init_menubar(self) -> None:
        mb = self.menuBar()

        # 1. Plik
        menu_file = mb.addMenu("&Plik")
        menu_file.addAction(self.act_new)
        menu_file.addAction(self.act_open)
        menu_file.addAction(self.act_save)
        act_save_as = QAction("Zapisz jako...", self)
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self._save_project_as)
        menu_file.addAction(act_save_as)
        menu_file.addSeparator()
        menu_file.addAction(self.act_export)
        menu_file.addSeparator()
        act_exit = QAction("Zamknij program", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # 2. Edycja
        menu_edit = mb.addMenu("&Edycja")
        menu_edit.addAction(self.act_undo)
        menu_edit.addAction(self.act_redo)
        menu_edit.addSeparator()
        act_copy = QAction("Kopiuj zaznaczenie", self)
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.triggered.connect(self._copy_selection)
        menu_edit.addAction(act_copy)
        act_paste = QAction("Wklej zaznaczenie (stempel)", self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(self._paste_stamp)
        menu_edit.addAction(act_paste)
        act_del = QAction("Usuń zaznaczenie", self)
        act_del.setShortcut(QKeySequence.StandardKey.Delete)
        act_del.triggered.connect(self._delete_selection)
        menu_edit.addAction(act_del)
        menu_edit.addSeparator()
        act_prefs = QAction("Preferencje...", self)
        act_prefs.setShortcut("Ctrl+,")
        act_prefs.triggered.connect(self.open_preferences_dialog)
        menu_edit.addAction(act_prefs)

        # 3. Widok (View Menu)
        menu_view = mb.addMenu("&Widok")
        menu_view.addAction(self._make_widget_toggle_action("Panel narzędzi", self.tool_panel))
        menu_view.addAction(self.tileset_dock.toggleViewAction())
        menu_view.addAction(self.right_dock.toggleViewAction())
        menu_view.addAction(self.properties_dock.toggleViewAction())
        menu_view.addAction(self.history_dock.toggleViewAction())
        menu_view.addAction(self.minimap_dock.toggleViewAction())
        menu_view.addSeparator()
        menu_view.addAction(self._make_widget_toggle_action("Pasek opcji pędzla", self.brush_options))
        menu_view.addAction(self._make_widget_toggle_action("Pasek zakładek map", self.map_tab_bar))
        menu_view.addAction(self.toolbar.toggleViewAction())
        menu_view.addAction(self.act_grid)
        act_hud = QAction("Wskaźnik współrzędnych (HUD)", self)
        act_hud.setCheckable(True)
        act_hud.setChecked(self.canvas.show_hud)
        act_hud.triggered.connect(lambda ch: setattr(self.canvas, "show_hud", ch) or self.canvas.update())
        menu_view.addAction(act_hud)
        menu_view.addAction(self.act_fit)
        menu_view.addSeparator()
        menu_view.addAction(self.act_reset_ui)
        act_full = QAction("Pełny obszar roboczy", self)
        act_full.setShortcut("F11")
        act_full.triggered.connect(self._toggle_fullscreen_workspace)
        menu_view.addAction(act_full)

        # 4. Narzędzia
        menu_tools = mb.addMenu("&Narzędzia")
        for tool_name in ["brush", "eraser", "fill", "line", "rect", "select", "wand", "object", "eyedropper", "stamp"]:
            tool_obj = self.tool_panel.get_tool(tool_name)
            if tool_obj:
                act = QAction(f"{tool_obj.name} ({tool_obj.shortcut})", self)
                act.triggered.connect(lambda ch, n=tool_name: self.tool_panel.select_tool_by_key(n))
                menu_tools.addAction(act)
        menu_tools.addSeparator()
        menu_tools.addAction(self.act_autotile)
        menu_tools.addAction(self.act_save_stamp)

        # 5. Pomoc
        menu_help = mb.addMenu("&Pomoc")
        menu_help.addAction(self.act_shortcuts)
        act_about = QAction("O programie", self)
        act_about.triggered.connect(self._show_about_dialog)
        menu_help.addAction(act_about)

    def _make_widget_toggle_action(self, text: str, widget: QWidget) -> QAction:
        act = QAction(text, self)
        act.setCheckable(True)
        act.setChecked(widget.isVisible())
        act.triggered.connect(lambda checked: widget.setVisible(checked))
        return act

    def _toggle_fullscreen_workspace(self) -> None:
        docks = [
            self.tileset_dock,
            self.right_dock,
            self.properties_dock,
            self.history_dock,
        ]
        any_visible = any(d.isVisible() for d in docks)
        for d in docks:
            d.setVisible(not any_visible)
        self.canvas.fit_to_view()

    def _save_project_as(self) -> None:
        old_path = self.project.file_path
        self.project.file_path = None
        self.save_project()
        if not self.project.file_path:
            self.project.file_path = old_path

    def _show_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            "O programie TileSet Map Maker",
            "<h3>TileSet Map Maker 2D</h3>"
            "<p>Profesjonalny kreator i edytor map 2D z obsługą tilesetów oraz obiektów PNG.</p>"
            "<p>Inspiracje: <b>Tiled</b>, <b>Aseprite</b>, <b>Margonem</b>.</p>",
        )

    def _init_shortcuts(self) -> None:
        tool_keys = {
            Qt.Key.Key_B: "brush",
            Qt.Key.Key_E: "eraser",
            Qt.Key.Key_G: "fill",
            Qt.Key.Key_L: "line",
            Qt.Key.Key_U: "rect",
            Qt.Key.Key_S: "select",
            Qt.Key.Key_W: "wand",
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
        self.canvas.quick_tool_requested.connect(self.tool_panel.select_tool_by_key)
        self.layer_panel.layer_changed.connect(self._on_layers_modified)
        self.canvas.cursor_moved.connect(self._on_cursor_moved)
        self.canvas.zoom_changed.connect(self._on_zoom_changed)
        self.canvas.files_dropped.connect(self._on_files_dropped)

        self.asset_manager.asset_selected.connect(self._on_asset_selected)
        self.history_manager.history_changed.connect(self._on_history_changed)

        self.map_tab_bar.map_selected.connect(self._on_map_switched)
        self.map_tab_bar.new_map_requested.connect(self._on_new_map_requested)
        self.map_tab_bar.map_closed.connect(self._on_map_closed)
        self.map_tab_bar.map_renamed.connect(lambda mid, name: self._on_map_renamed())
        self.map_tab_bar.map_duplicated.connect(self._on_map_duplicated)

    def get_map_history(self, map_id: str) -> HistoryManager:
        if map_id not in self.map_histories:
            self.map_histories[map_id] = HistoryManager()
        return self.map_histories[map_id]

    def _set_active_history_manager(self, history_mgr: HistoryManager) -> None:
        if hasattr(self, "history_manager") and self.history_manager:
            try:
                self.history_manager.history_changed.disconnect(self._on_history_changed)
            except Exception:
                pass
        self.history_manager = history_mgr
        self.history_manager.history_changed.connect(self._on_history_changed)
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.tool_context.history_manager = history_mgr
            self.canvas.history_manager = history_mgr
        if hasattr(self, "layer_panel") and self.layer_panel:
            self.layer_panel.history_manager = history_mgr
        if hasattr(self, "history_panel") and self.history_panel:
            self.history_panel.set_history_manager(history_mgr)
        self._on_history_changed(
            history_mgr.can_undo(),
            history_mgr.can_redo(),
            history_mgr.undo_description(),
            history_mgr.redo_description(),
        )

    def _update_title(self) -> None:
        mod = "*" if self.project.is_modified else ""
        name = self.project.name
        map_name = self.project.get_active_map().name
        self.setWindowTitle(f"{mod}{name} – [{map_name}] – TileSet Map Maker")

    def _on_map_switched(self, map_id: str) -> None:
        self.project.set_active_map(map_id)
        hist = self.get_map_history(map_id)
        self._set_active_history_manager(hist)
        self.canvas.set_active_layer(self.project.get_active_layer())
        self.layer_panel.set_project(self.project)
        self.properties_panel.set_project(self.project)
        if hasattr(self, "minimap_widget") and self.minimap_widget:
            self.minimap_widget.set_project(self.project)
        self.map_tab_bar.refresh_tabs()
        self._update_title()
        self._update_status_bar()
        self.canvas.fit_to_view()
        self.canvas.update()

    def _on_new_map_requested(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            "Nowa mapa",
            "Nazwa nowej mapy w projekcie:",
            text=f"Mapa_{len(self.project.maps) + 1}",
        )
        if ok and name.strip():
            new_m = self.project.add_map(
                name=name.strip(),
                width=30,
                height=20,
                tile_size=self.project.tile_size,
            )
            self._on_map_switched(new_m.id)

    def _on_map_closed(self, map_id: str) -> None:
        self.map_histories.pop(map_id, None)
        self._on_map_switched(self.project.active_map_id)

    def _on_map_renamed(self) -> None:
        self._update_title()

    def _on_map_duplicated(self, map_id: str) -> None:
        self._on_map_switched(map_id)

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
            if isinstance(item, Asset) and item.asset_type == AssetType.TILESET:
                self.tileset_palette.set_active_asset(item)
            elif isinstance(item, SelectedSubTile):
                parent_asset = self.asset_manager.get_asset(item.asset_id)
                if parent_asset:
                    self.tileset_palette.set_active_asset(parent_asset, item)
        else:
            self.lbl_status_asset.setText("Zasób: Brak")
        self.properties_panel.set_selected_item(item)

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
        if hasattr(self, "minimap_widget") and self.minimap_widget:
            self.minimap_widget.update()
        self.canvas.update()

    def _on_files_dropped(self, paths: List[str]) -> None:
        for p in paths:
            if not os.path.exists(p):
                continue
            if os.path.isdir(p):
                self.asset_manager.import_folder(p)
            elif os.path.isfile(p):
                ext = os.path.splitext(p)[1].lower()
                if ext == ".tmmap":
                    proj = ProjectIO.load_project(p, self.asset_manager)
                    if proj:
                        self.project = proj
                        self.map_histories.clear()
                        self._set_active_history_manager(self.get_map_history(self.project.active_map_id))
                        self.canvas.set_project(self.project)
                        self.layer_panel.set_project(self.project)
                        self.map_tab_bar.set_project(self.project)
                        self.properties_panel.set_project(self.project)
                        self.tileset_palette.refresh_tilesets()
                        self._update_title()
                        self._update_status_bar()
                elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
                    dlg = TilesetImportDialog(p, default_tile_size=self.project.tile_size, parent=self)
                    if dlg.exec():
                        tile_w, tile_h = dlg.get_tile_dimensions()
                        asset, is_dup, err = self.asset_manager.import_single_file(
                            p,
                            target_category_path="Terrain",
                            force_asset_type=AssetType.TILESET,
                        )
                        if asset:
                            from ..models.asset import TilesetConfig
                            asset.tileset_config = TilesetConfig(tile_width=tile_w, tile_height=tile_h)
                            if asset.id not in self.tileset_palette.open_tileset_ids:
                                self.tileset_palette.open_tileset_ids.append(asset.id)
                            self.tileset_palette.refresh_tilesets()
                            self.tileset_palette.set_active_asset(asset)
                            self.tool_panel.select_tool_by_key("brush")
                            self.statusBar().showMessage(f"Zaimportowano tileset: {asset.name}", 3000)
                else:
                    self.asset_manager.import_single_file(p, force_asset_type=AssetType.TILESET)
        self.tileset_palette.refresh_tilesets()

    def _copy_selection(self) -> None:
        tool = self.tool_panel.get_tool("select")
        if isinstance(tool, SelectTool) and tool.selection_rect:
            tool.copy_selection(self.canvas.tool_context)
            self.statusBar().showMessage("Skopiowano zaznaczenie do schowka.", 2500)
            return
        wand_tool = self.tool_panel.get_tool("wand")
        if isinstance(wand_tool, WandTool) and wand_tool.selected_cells:
            wand_tool.copy_selection(self.canvas.tool_context)
            self.statusBar().showMessage("Skopiowano zaznaczenie różdżki do schowka.", 2500)
            return

    def _paste_stamp(self) -> None:
        if self.canvas.tool_context.clipboard_tiles:
            self.tool_panel.select_tool_by_key("stamp")

    def _delete_selection(self) -> None:
        tool = self.tool_panel.get_tool("select")
        if isinstance(tool, SelectTool) and tool.selection_rect:
            tool.delete_selection(self.canvas.tool_context)
            self.canvas.update()
        wand_tool = self.tool_panel.get_tool("wand")
        if isinstance(wand_tool, WandTool) and wand_tool.selected_cells:
            wand_tool.delete_selection(self.canvas.tool_context)
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
                    QMessageBox.information(self, "Zapisano", f"Stempel '{preset.name}' został zapisany!")
        else:
            QMessageBox.warning(self, "Brak zaznaczenia", "Zaznacz najpierw obszar mapy narzędziem Zaznaczanie (S).")

    def open_autotile_dialog(self) -> None:
        dlg = AutoTileDialog(self.autotile_engine, self.asset_manager, self)
        dlg.exec()

    def _on_autosaved(self, path: str) -> None:
        self.statusBar().showMessage(f"Autozapis wykonany ({os.path.basename(path)})", 2500)

    def new_project(self) -> None:
        self.project = Project(name="Nowy Projekt", map_width=30, map_height=20, tile_size=32)
        self.map_histories.clear()
        self._set_active_history_manager(self.get_map_history(self.project.active_map_id))
        self.autosave_manager.set_project(self.project)
        self.canvas.set_project(self.project)
        self.layer_panel.set_project(self.project)
        self.map_tab_bar.set_project(self.project)
        self.properties_panel.set_project(self.project)
        if hasattr(self, "minimap_widget") and self.minimap_widget:
            self.minimap_widget.set_project(self.project)
        self.tileset_palette.refresh_tilesets()
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
                self.map_histories.clear()
                self._set_active_history_manager(self.get_map_history(self.project.active_map_id))
                self.autosave_manager.set_project(self.project)
                self.canvas.set_project(self.project)
                self.layer_panel.set_project(self.project)
                self.map_tab_bar.set_project(self.project)
                self.properties_panel.set_project(self.project)
                if hasattr(self, "minimap_widget") and self.minimap_widget:
                    self.minimap_widget.set_project(self.project)
                self.tileset_palette.refresh_tilesets()
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
            self.autosave_manager.cleanup_autosave(self.project.file_path)
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

    def open_preferences_dialog(self) -> None:
        dlg = PreferencesDialog(self)
        if dlg.exec():
            settings = dlg.settings
            show_hud = settings.value("show_hud", True, type=bool)
            show_grid = settings.value("show_grid", True, type=bool)
            op = settings.value("grid_opacity", 35, type=int)
            self.canvas.show_hud = show_hud
            self.canvas.show_grid = show_grid
            self.canvas.grid_color = QColor(255, 255, 255, int(op * 255 / 100))
            as_idx = settings.value("autosave_interval_idx", 1, type=int)
            intervals = [1, 3, 5, 10, 0]
            if as_idx < len(intervals):
                self.autosave_manager.set_interval(intervals[as_idx])
            self.canvas.update()

    def _reset_dock_layout(self) -> None:
        self.tileset_dock.show()
        self.right_dock.show()
        self.properties_dock.show()
        self.history_dock.show()
        self.minimap_dock.show()
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tileset_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.right_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.history_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.minimap_dock)
        self.tabifyDockWidget(self.right_dock, self.properties_dock)
        self.tabifyDockWidget(self.right_dock, self.history_dock)
        self.tabifyDockWidget(self.right_dock, self.minimap_dock)
        self.right_dock.raise_()
        if hasattr(self, "tileset_palette"):
            self.tileset_palette.reset_splitter_sizes()
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
        if hasattr(self, "tileset_palette"):
            self.tileset_palette.save_splitter_state()
        super().closeEvent(event)
