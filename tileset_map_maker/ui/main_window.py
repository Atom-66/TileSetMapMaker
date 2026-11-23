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
    QTabWidget,
    QStatusBar,
    QLabel,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QApplication,
)
from PyQt6.QtGui import QAction, QKeySequence, QIcon, QKeyEvent

from ..models.project import Project
from ..models.asset import Asset, AssetType, SelectedSubTile
from ..core.asset_manager import AssetManager
from ..core.config_manager import ConfigManager
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
from .toolbar_manager import ToolbarManager, CustomizableToolBar, ToolbarEditModeBanner
from .minimap_widget import MinimapWidget
from .object_list_panel import ObjectListPanel
from .dialogs import MapSettingsDialog, ExportDialog, ShortcutsDialog, PreferencesDialog
from .dialogs.autotile_dialog import AutoTileDialog
from .dialogs.path_generator_dialog import PathGeneratorDialog
from .dialogs.tileset_import_dialog import TilesetImportDialog


LAYOUT_VERSION = 2


class MainWindow(QMainWindow):
    """Main window for TileSet Map Maker desktop application (Etap 2 Advanced)."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        super().__init__()
        self.setWindowTitle("TileSet Map Maker")
        self.resize(1400, 880)

        # Core systems
        self.config_manager = config_manager or ConfigManager()
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
        self.central_layout = central_layout

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

        self.brush_options = BrushOptionsBar(
            self.canvas.tool_context.brush_settings,
            autotile_engine=self.autotile_engine,
            asset_manager=self.asset_manager,
            project=self.project,
            history_manager=self.history_manager,
        )
        self.brush_options.options_changed.connect(self.canvas.update)

        # Multi-Map Tab Bar (Aseprite & Tiled style)
        self.map_tab_bar = MapTabBar(self.project, central_container)
        central_layout.addWidget(self.map_tab_bar)

        # Middle row: Map Canvas (central area expands to fill all space)
        mid_widget = QWidget()
        mid_layout = QHBoxLayout(mid_widget)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(0)

        self.tool_panel = ToolPanel()
        mid_layout.addWidget(self.canvas, 1)

        central_layout.addWidget(mid_widget, 1)
        self.setCentralWidget(central_container)

        # Initial tool setup
        self.canvas.set_tool(self.tool_panel.get_tool("brush"))

        # Configure Photoshop / Aseprite / Tiled style docking options
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.GroupedDragging
            | QMainWindow.DockOption.AllowNestedDocks
        )

        # Tabs on top of tabbed dock groups (Photoshop / Tiled style)
        self.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)
        self.setTabShape(QTabWidget.TabShape.Rounded)

        # Full-height vertical left and right dock areas
        self.setCorner(Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)

        dock_features = (
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        # 1. Tool Dock (draggable toolbox, dockable to left, right, top, bottom, or floating)
        self.tool_dock = QDockWidget("Narzędzia", self)
        self.tool_dock.setObjectName("ToolDock")
        self.tool_dock.setFeatures(dock_features)
        self.tool_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.tool_dock.setWidget(self.tool_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tool_dock)

        # 2. Tileset Palette coordinator (supports separate preview & library docks)
        self.tileset_palette = TilesetPaletteWidget(
            self.asset_manager, config_manager=self.config_manager, parent=self, standalone=False
        )

        # 3. Tileset Preview Dock (top section: interactive canvas & tile selector)
        self.tileset_preview_dock = QDockWidget("Podgląd tilesetu", self)
        self.tileset_preview_dock.setObjectName("TilesetPreviewDock")
        self.tileset_preview_dock.setFeatures(dock_features)
        self.tileset_preview_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.tileset_preview_dock.setWidget(self.tileset_palette.top_widget)
        self.tileset_dock = self.tileset_preview_dock  # Backward compatibility alias
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tileset_preview_dock)

        # 4. Tileset Library Dock (bottom section: folders, tree, import buttons)
        self.tileset_library_dock = QDockWidget("Biblioteka tilesetów", self)
        self.tileset_library_dock.setObjectName("TilesetLibraryDock")
        self.tileset_library_dock.setFeatures(dock_features)
        self.tileset_library_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.tileset_library_dock.setWidget(self.tileset_palette.bottom_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tileset_library_dock)

        # Split preview and library vertically on left by default
        self.splitDockWidget(self.tileset_preview_dock, self.tileset_library_dock, Qt.Orientation.Vertical)

        # 5. Right Docks: Layers, Objects, Properties, History, Minimap
        self.layer_dock = QDockWidget("Warstwy i grupy mapy", self)
        self.layer_dock.setObjectName("RightDockLayers")
        self.layer_dock.setFeatures(dock_features)
        self.layer_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.layer_panel = LayerPanel(self.project, self.history_manager, self.layer_dock)
        self.layer_dock.setWidget(self.layer_panel)
        self.right_dock = self.layer_dock  # Backward compatibility alias
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_dock)

        # 6. Objects Dock (tabified with Layers: 'Warstwy | Obiekty')
        self.objects_dock = QDockWidget("Obiekty na mapie", self)
        self.objects_dock.setObjectName("ObjectsDock")
        self.objects_dock.setFeatures(dock_features)
        self.objects_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.objects_panel = ObjectListPanel(self.project, self.history_manager, self.objects_dock)
        self.objects_dock.setWidget(self.objects_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.objects_dock)
        self.tabifyDockWidget(self.layer_dock, self.objects_dock)

        # 7. Properties Dock
        self.properties_dock = QDockWidget("Właściwości", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setFeatures(dock_features)
        self.properties_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.properties_panel = PropertiesPanel(self.project, self.asset_manager, self.properties_dock)
        self.properties_dock.setWidget(self.properties_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.tabifyDockWidget(self.layer_dock, self.properties_dock)

        # 8. History Dock
        self.history_dock = QDockWidget("Historia operacji", self)
        self.history_dock.setObjectName("HistoryDock")
        self.history_dock.setFeatures(dock_features)
        self.history_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.history_panel = HistoryPanel(self.history_manager, self.history_dock)
        self.history_dock.setWidget(self.history_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.history_dock)
        self.tabifyDockWidget(self.layer_dock, self.history_dock)

        # 9. Minimap Dock (TASK-505)
        self.minimap_dock = QDockWidget("Minimapa", self)
        self.minimap_dock.setObjectName("MinimapDock")
        self.minimap_dock.setFeatures(dock_features)
        self.minimap_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.minimap_widget = MinimapWidget(self.project, self.render_engine, self.canvas, self.minimap_dock)
        self.minimap_dock.setWidget(self.minimap_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.minimap_dock)
        self.tabifyDockWidget(self.layer_dock, self.minimap_dock)

        self.layer_dock.raise_()

        # Connect Objects Panel with History & Layer changes
        self.history_manager.history_changed.connect(lambda: self.objects_panel.refresh())
        self.layer_panel.layer_changed.connect(self.objects_panel.refresh)
        self.objects_panel.focus_requested.connect(lambda cx, cy: self.canvas.center_on_world_pos(cx, cy))

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
        self.toolbar = CustomizableToolBar("Główny pasek narzędzi", toolbar_id="main", parent=self)
        self.toolbar.setObjectName("MainToolBar")
        self.toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)
        self.brush_options.setParent(self.toolbar)

        self.secondary_toolbar = CustomizableToolBar("Dodatkowy pasek narzędzi", toolbar_id="secondary", parent=self)
        self.secondary_toolbar.setObjectName("SecondaryToolBar")
        self.secondary_toolbar.setIconSize(QSize(20, 20))
        self.insertToolBarBreak(self.secondary_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.secondary_toolbar)

        # 1. Project actions
        self.act_new = QAction(IconFactory.get_icon("new", 20), "Nowy", self)
        self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_new.setToolTip("Nowy projekt (Ctrl+N)")
        self.act_new.triggered.connect(self.new_project)
        self.addAction(self.act_new)

        self.act_open = QAction(IconFactory.get_icon("open", 20), "Otwórz", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.setToolTip("Otwórz projekt (Ctrl+O)")
        self.act_open.triggered.connect(self.open_project)
        self.addAction(self.act_open)

        self.act_save = QAction(IconFactory.get_icon("save", 20), "Zapisz", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.setToolTip("Zapisz projekt (Ctrl+S)")
        self.act_save.triggered.connect(self.save_project)
        self.addAction(self.act_save)

        self.act_export = QAction(IconFactory.get_icon("export", 20), "Eksport PNG", self)
        self.act_export.setShortcut("Ctrl+E")
        self.act_export.setToolTip("Eksportuj gotową mapę do pliku PNG (Ctrl+E)")
        self.act_export.triggered.connect(self.export_png_dialog)
        self.addAction(self.act_export)

        # 2. History actions
        self.act_undo = QAction(IconFactory.get_icon("undo", 20), "Cofnij", self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.setToolTip("Cofnij operację (Ctrl+Z)")
        self.act_undo.setEnabled(False)
        self.act_undo.triggered.connect(lambda: self.history_manager.undo())
        self.addAction(self.act_undo)

        self.act_redo = QAction(IconFactory.get_icon("redo", 20), "Ponów", self)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.act_redo.setToolTip("Ponów operację (Ctrl+Y)")
        self.act_redo.setEnabled(False)
        self.act_redo.triggered.connect(lambda: self.history_manager.redo())
        self.addAction(self.act_redo)

        # 3. View actions
        self.act_grid = QAction(IconFactory.get_icon("grid", 20), "Siatka", self)
        self.act_grid.setCheckable(True)
        self.act_grid.setChecked(True)
        self.act_grid.setShortcut("Ctrl+G")
        self.act_grid.setToolTip("Przełącz widoczność siatki (Ctrl+G)")
        self.act_grid.triggered.connect(lambda: self.canvas.toggle_grid(self.act_grid.isChecked()))
        self.addAction(self.act_grid)

        self.act_fit = QAction(IconFactory.get_icon("fit", 20), "Dopasuj", self)
        self.act_fit.setShortcut("Ctrl+F")
        self.act_fit.setToolTip("Dopasuj mapę do okna (Ctrl+F)")
        self.act_fit.triggered.connect(self.canvas.fit_to_view)
        self.addAction(self.act_fit)

        self.act_palette = self.tileset_dock.toggleViewAction()
        self.act_palette.setIcon(IconFactory.get_icon("grid", 20))
        self.act_palette.setText("Paleta")
        self.act_palette.setToolTip("Pokaż lub ukryj interaktywną paletę kafelków (Tiled-style)")
        self.addAction(self.act_palette)

        # 4. Brush & Stamp
        self.act_save_stamp = QAction(IconFactory.get_icon("save_stamp", 20), "Zapisz stempel", self)
        self.act_save_stamp.setToolTip("Zapisz zaznaczony fragment mapy jako trwały stempel w bibliotece")
        self.act_save_stamp.triggered.connect(self.save_selection_as_stamp)
        self.addAction(self.act_save_stamp)

        # Menu bar references
        self.act_autotile = QAction(IconFactory.get_icon("autotile", 20), "Auto-Tile", self)
        self.act_autotile.setToolTip("Konfigurator reguł Auto-Tiling i połączeń terenu")
        self.act_autotile.triggered.connect(self.open_autotile_dialog)

        self.act_path_gen = QAction(IconFactory.get_icon("path", 20), "Ścieżki", self)
        self.act_path_gen.setToolTip("Generator Ścieżek (konfigurator kafelków ścieżki i podgląd na żywo)")
        self.act_path_gen.triggered.connect(self.open_path_generator_dialog)

        self.act_randomizer = QAction(IconFactory.get_icon("randomizer", 20), "Randomizer", self)
        self.act_randomizer.setToolTip("Konfigurator Randomizera kafelków i wag (Tile Randomizer)")
        self.act_randomizer.triggered.connect(self.brush_options.open_randomizer_dialog)

        # 5. System actions
        self.act_settings = QAction(IconFactory.get_icon("settings", 20), "Ustawienia", self)
        self.act_settings.setToolTip("Zmień rozmiar mapy, kafelków lub tło")
        self.act_settings.triggered.connect(self.open_map_settings)
        self.addAction(self.act_settings)

        self.act_shortcuts = QAction(IconFactory.get_icon("shortcuts", 20), "Skróty", self)
        self.act_shortcuts.setToolTip("Lista skrótów klawiszowych")
        self.act_shortcuts.triggered.connect(self.open_shortcuts_dialog)
        self.addAction(self.act_shortcuts)

        self.act_reset_ui = QAction(IconFactory.get_icon("reset_ui", 20), "Reset", self)
        self.act_reset_ui.setToolTip("Przywróć domyślny układ paneli")
        self.act_reset_ui.triggered.connect(self._reset_dock_layout)
        self.addAction(self.act_reset_ui)

        # Modular Toolbar Manager: unified buttons, categories and personalization across main & secondary toolbars
        self.toolbar_manager = ToolbarManager(
            toolbar=self.toolbar,
            config_manager=self.config_manager,
            secondary_toolbar=self.secondary_toolbar,
            parent=self,
        )

        # Register Project items
        self.toolbar_manager.register_item("new", "Nowy", "project", action=self.act_new, icon_name="new")
        self.toolbar_manager.register_item("open", "Otwórz", "project", action=self.act_open, icon_name="open")
        self.toolbar_manager.register_item("save", "Zapisz", "project", action=self.act_save, icon_name="save")
        self.toolbar_manager.register_item("export", "Eksport PNG", "project", action=self.act_export, icon_name="export")

        # Register History items
        self.toolbar_manager.register_item("undo", "Cofnij", "history", action=self.act_undo, icon_name="undo")
        self.toolbar_manager.register_item("redo", "Ponów", "history", action=self.act_redo, icon_name="redo")

        # Register View items
        self.toolbar_manager.register_item("grid", "Siatka", "view", action=self.act_grid, icon_name="grid")
        self.toolbar_manager.register_item("fit", "Dopasuj widok", "view", action=self.act_fit, icon_name="fit")
        self.toolbar_manager.register_item("palette", "Paleta", "view", action=self.act_palette, icon_name="palette")

        # Register Brush items
        self.toolbar_manager.register_item("save_stamp", "Zapisz stempel", "brush", action=self.act_save_stamp, icon_name="save_stamp")

        # Register Brush Options Bar modular items (brush size, autotile, paths, randomizer, transforms)
        for item_id, item_data in self.brush_options.get_toolbar_items().items():
            self.toolbar_manager.register_item(
                item_id=item_id,
                label=item_data["label"],
                category_id=item_data["category"],
                widget=item_data["widget"],
                icon_name=item_data.get("icon", "grid"),
                tooltip=item_data.get("tooltip", ""),
            )

        # Register System items
        self.toolbar_manager.register_item("settings", "Ustawienia", "system", action=self.act_settings, icon_name="settings")
        self.toolbar_manager.register_item("shortcuts", "Skróty", "system", action=self.act_shortcuts, icon_name="shortcuts")
        self.toolbar_manager.register_item("reset_ui", "Reset układu", "system", action=self.act_reset_ui, icon_name="reset_ui")

        # Load layout configuration (or safe default)
        self.toolbar_manager.load_layout()

        # Banner for interactive Drag & Drop customization mode
        self.toolbar_edit_banner = ToolbarEditModeBanner(self.toolbar_manager, parent=self)
        if hasattr(self, "central_layout"):
            self.central_layout.insertWidget(1, self.toolbar_edit_banner)
        self.toolbar_manager.set_edit_banner(self.toolbar_edit_banner)

    def _init_menubar(self) -> None:
        mb = self.menuBar()

        # 1. Plik
        menu_file = mb.addMenu("&Plik")
        menu_file.addAction(self.act_new)
        menu_file.addAction(self.act_open)
        menu_file.addAction(self.act_save)
        act_save_as = QAction(IconFactory.get_icon("save-as", 16), "Zapisz jako...", self)
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self._save_project_as)
        menu_file.addAction(act_save_as)
        menu_file.addSeparator()
        menu_file.addAction(self.act_export)
        menu_file.addSeparator()
        act_exit = QAction(IconFactory.get_icon("exit", 16), "Zamknij program", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # 2. Edycja
        menu_edit = mb.addMenu("&Edycja")
        menu_edit.addAction(self.act_undo)
        menu_edit.addAction(self.act_redo)
        menu_edit.addSeparator()
        act_copy = QAction(IconFactory.get_icon("copy", 16), "Kopiuj zaznaczenie", self)
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.triggered.connect(self._copy_selection)
        menu_edit.addAction(act_copy)
        act_paste = QAction(IconFactory.get_icon("paste", 16), "Wklej zaznaczenie (stempel)", self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(self._paste_stamp)
        menu_edit.addAction(act_paste)
        act_del = QAction(IconFactory.get_icon("trash", 16), "Usuń zaznaczenie", self)
        act_del.setShortcut(QKeySequence.StandardKey.Delete)
        act_del.triggered.connect(self._delete_selection)
        menu_edit.addAction(act_del)
        menu_edit.addSeparator()
        act_prefs = QAction(IconFactory.get_icon("settings", 16), "Preferencje...", self)
        act_prefs.setShortcut("Ctrl+,")
        act_prefs.triggered.connect(self.open_preferences_dialog)
        menu_edit.addAction(act_prefs)

        # 3. Widok (View Menu)
        menu_view = mb.addMenu("&Widok")

        # Submenu: Układ interfejsu (Layout Management)
        self.menu_layout = menu_view.addMenu(IconFactory.get_icon("layout", 16), "&Układ interfejsu")

        self.act_layout_default = QAction(IconFactory.get_icon("fit", 16), "Domyślny układ (Photoshop / Tiled)", self)
        self.act_layout_default.setShortcut("Ctrl+Shift+D")
        self.act_layout_default.triggered.connect(self._reset_dock_layout)
        self.menu_layout.addAction(self.act_layout_default)

        self.menu_layout.addSeparator()

        self.act_layout_save = QAction(IconFactory.get_icon("save", 16), "Zapisz bieżący układ jako...", self)
        self.act_layout_save.triggered.connect(self.save_custom_layout_action)
        self.menu_layout.addAction(self.act_layout_save)

        self.menu_load_layout = self.menu_layout.addMenu(IconFactory.get_icon("open", 16), "Wczytaj zapisany układ")
        self.menu_rename_layout = self.menu_layout.addMenu(IconFactory.get_icon("pencil", 16), "Zmień nazwę zapisanego układu")
        self.menu_delete_layout = self.menu_layout.addMenu(IconFactory.get_icon("trash", 16), "Usuń zapisany układ")

        self.menu_layout.addSeparator()

        # Built-in Presets
        self.act_preset_map_edit = QAction(IconFactory.get_icon("map-edit", 16), "Edycja mapy (Maksymalne płótno i warstwy)", self)
        self.act_preset_map_edit.triggered.connect(lambda: self.apply_layout_preset("map_editing"))
        self.menu_layout.addAction(self.act_preset_map_edit)

        self.act_preset_tileset = QAction(IconFactory.get_icon("palette", 16), "Studio tilesetów (Powiększona paleta)", self)
        self.act_preset_tileset.triggered.connect(lambda: self.apply_layout_preset("tileset_studio"))
        self.menu_layout.addAction(self.act_preset_tileset)

        self.act_preset_minimal = QAction(IconFactory.get_icon("arrows-maximize", 16), "Minimalistyczny (Tylko narzędzia)", self)
        self.act_preset_minimal.triggered.connect(lambda: self.apply_layout_preset("minimalist"))
        self.menu_layout.addAction(self.act_preset_minimal)

        self.act_preset_expanded = QAction(IconFactory.get_icon("layout", 16), "Wszystkie panele (Rozszerzony)", self)
        self.act_preset_expanded.triggered.connect(lambda: self.apply_layout_preset("expanded"))
        self.menu_layout.addAction(self.act_preset_expanded)

        self._rebuild_layout_menu()

        # Submenu: Panele dokowalne
        menu_docks = menu_view.addMenu(IconFactory.get_icon("layout", 16), "&Panele dokowalne")
        menu_docks.addAction(self.tileset_preview_dock.toggleViewAction())
        menu_docks.addAction(self.tileset_library_dock.toggleViewAction())
        menu_docks.addAction(self.layer_dock.toggleViewAction())
        menu_docks.addAction(self.objects_dock.toggleViewAction())
        menu_docks.addAction(self.properties_dock.toggleViewAction())
        menu_docks.addAction(self.history_dock.toggleViewAction())
        menu_docks.addAction(self.minimap_dock.toggleViewAction())
        menu_docks.addAction(self.tool_dock.toggleViewAction())

        # Direct shortcuts for toggling individual docks in main View menu
        menu_view.addAction(self.tileset_preview_dock.toggleViewAction())
        menu_view.addAction(self.tileset_library_dock.toggleViewAction())
        menu_view.addAction(self.layer_dock.toggleViewAction())
        menu_view.addAction(self.objects_dock.toggleViewAction())
        menu_view.addAction(self.properties_dock.toggleViewAction())
        menu_view.addAction(self.history_dock.toggleViewAction())
        menu_view.addAction(self.minimap_dock.toggleViewAction())
        menu_view.addAction(self.tool_dock.toggleViewAction())

        menu_view.addSeparator()
        menu_view.addAction(self._make_widget_toggle_action("Pasek zakładek map", self.map_tab_bar))
        menu_view.addAction(self.toolbar.toggleViewAction())
        menu_view.addAction(self.secondary_toolbar.toggleViewAction())
        self.act_toolbar_edit = QAction(IconFactory.get_icon("edit", 16), "Personalizuj paski narzędzi (Drag & Drop)...", self)
        self.act_toolbar_edit.setShortcut("Ctrl+Alt+T")
        self.act_toolbar_edit.setCheckable(True)
        self.act_toolbar_edit.triggered.connect(self.toolbar_manager.toggle_edit_mode)
        menu_view.addAction(self.act_toolbar_edit)
        self.toolbar_manager.edit_mode_changed.connect(self.act_toolbar_edit.setChecked)

        self.act_customize_toolbar = QAction(IconFactory.get_icon("settings", 16), "Dostosuj paski narzędzi (Dialog)...", self)
        self.act_customize_toolbar.setToolTip("Dostosuj kolejność i widoczność przycisków oraz kategorii na paskach narzędzi w oknie dialogowym")
        self.act_customize_toolbar.triggered.connect(lambda: self.toolbar_manager.open_customizer_dialog())
        menu_view.addAction(self.act_customize_toolbar)
        menu_view.addAction(self.act_grid)
        act_hud = QAction(IconFactory.get_icon("hud", 16), "Wskaźnik współrzędnych (HUD)", self)
        act_hud.setCheckable(True)
        act_hud.setChecked(self.canvas.show_hud)
        act_hud.triggered.connect(lambda ch: setattr(self.canvas, "show_hud", ch) or self.canvas.update())
        menu_view.addAction(act_hud)
        menu_view.addAction(self.act_fit)
        menu_view.addSeparator()
        menu_view.addAction(self.act_reset_ui)
        act_full = QAction(IconFactory.get_icon("fullscreen", 16), "Pełny obszar roboczy (F11)", self)
        act_full.setShortcut("F11")
        act_full.triggered.connect(self._toggle_fullscreen_workspace)
        menu_view.addAction(act_full)

        # 4. Narzędzia
        menu_tools = mb.addMenu("&Narzędzia")
        for tool_name in ["brush", "eraser", "fill", "line", "rect", "select", "wand", "object", "eyedropper", "stamp"]:
            tool_obj = self.tool_panel.get_tool(tool_name)
            if tool_obj:
                act = QAction(IconFactory.get_icon(tool_name, 16), f"{tool_obj.name} ({tool_obj.shortcut})", self)
                act.triggered.connect(lambda ch, n=tool_name: self.tool_panel.select_tool_by_key(n))
                menu_tools.addAction(act)
        menu_tools.addSeparator()
        menu_tools.addAction(self.act_autotile)
        menu_tools.addAction(self.act_path_gen)
        menu_tools.addAction(self.act_randomizer)
        menu_tools.addAction(self.act_save_stamp)

        # 5. Pomoc
        menu_help = mb.addMenu("&Pomoc")
        menu_help.addAction(self.act_shortcuts)
        act_about = QAction(IconFactory.get_icon("about", 16), "O programie", self)
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
            self.tool_dock,
            self.tileset_preview_dock,
            self.tileset_library_dock,
            self.layer_dock,
            self.objects_dock,
            self.properties_dock,
            self.history_dock,
            self.minimap_dock,
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
        self.tool_panel.tool_changed.connect(self._on_tool_changed)
        if hasattr(self, "tool_dock") and hasattr(self.tool_panel, "on_dock_location_changed"):
            self.tool_dock.dockLocationChanged.connect(self.tool_panel.on_dock_location_changed)
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

        if hasattr(self, "secondary_toolbar") and self.secondary_toolbar:
            self.secondary_toolbar.visibilityChanged.connect(self._on_secondary_toolbar_visibility_changed)

    def _on_secondary_toolbar_visibility_changed(self, visible: bool) -> None:
        if hasattr(self, "toolbar_manager") and not getattr(self.toolbar_manager, "_is_loading", False):
            self.toolbar_manager.secondary_toolbar_visible = visible

    def _on_tool_changed(self, tool: BaseTool) -> None:
        self.canvas.set_tool(tool)
        tool_key = "brush"
        for k, t in self.tool_panel.tools.items():
            if t == tool:
                tool_key = k
                break
        if hasattr(self, "brush_options"):
            self.brush_options.set_active_tool(tool_key)

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
        if hasattr(self, "objects_panel") and self.objects_panel:
            self.objects_panel.set_history_manager(history_mgr)
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
        if hasattr(self, "objects_panel") and self.objects_panel:
            self.objects_panel.set_project(self.project)
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
                if self.tileset_palette.active_asset_id != item.id:
                    self.tileset_palette.set_active_asset(item)
            elif isinstance(item, SelectedSubTile):
                parent_asset = self.asset_manager.get_asset(item.asset_id)
                if parent_asset:
                    if self.tileset_palette.active_asset_id != parent_asset.id:
                        self.tileset_palette.set_active_asset(parent_asset, item)
                    else:
                        self.tileset_palette.set_selected_sub_tile(item)
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
        if dlg.exec():
            if hasattr(self, "brush_options") and hasattr(self.brush_options, "refresh_rulesets"):
                self.brush_options.refresh_rulesets()

    def open_path_generator_dialog(self) -> None:
        dlg = PathGeneratorDialog(self.autotile_engine, self.asset_manager, self)
        if dlg.exec():
            if hasattr(self, "brush_options") and hasattr(self.brush_options, "refresh_rulesets"):
                self.brush_options.refresh_rulesets()
                self.brush_options.settings.auto_tile_enabled = True
                self.brush_options.chk_autotile.setChecked(True)
            if hasattr(self, "config_manager"):
                self.config_manager.save_autotile_rules(self.autotile_engine)

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
        if hasattr(self, "objects_panel") and self.objects_panel:
            self.objects_panel.set_project(self.project)
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
            proj = ProjectIO.load_project(path, self.asset_manager, autotile_engine=self.autotile_engine)
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

        ok = ProjectIO.save_project(
            self.project,
            self.asset_manager,
            self.project.file_path,
            autotile_engine=self.autotile_engine,
        )
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
        """Restores the standard professional Photoshop/Tiled layout."""
        # Ensure all docks are unfloated and visible
        all_docks = [
            self.tool_dock,
            self.tileset_preview_dock,
            self.tileset_library_dock,
            self.layer_dock,
            self.objects_dock,
            self.properties_dock,
            self.history_dock,
            self.minimap_dock,
        ]
        for dock in all_docks:
            dock.setFloating(False)
            dock.show()

        # Left side: Tools, Tileset Preview & Library
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tool_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tileset_preview_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tileset_library_dock)
        self.splitDockWidget(self.tileset_preview_dock, self.tileset_library_dock, Qt.Orientation.Vertical)

        # Right side: Layers, Objects, Properties, History, Minimap
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.objects_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.history_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.minimap_dock)

        # Tab groups on the right side
        self.tabifyDockWidget(self.layer_dock, self.objects_dock)
        self.tabifyDockWidget(self.layer_dock, self.properties_dock)
        self.tabifyDockWidget(self.layer_dock, self.history_dock)
        self.tabifyDockWidget(self.layer_dock, self.minimap_dock)
        self.layer_dock.raise_()

        # Proportions
        self.resizeDocks([self.tileset_preview_dock], [300], Qt.Orientation.Horizontal)
        self.resizeDocks([self.layer_dock], [280], Qt.Orientation.Horizontal)
        self.resizeDocks([self.tool_dock], [52], Qt.Orientation.Horizontal)

        if hasattr(self, "tileset_palette"):
            self.tileset_palette.reset_splitter_sizes()
        self.canvas.fit_to_view()

    def apply_layout_preset(self, preset_name: str) -> None:
        """Applies a built-in layout preset."""
        if preset_name == "default":
            self._reset_dock_layout()
        elif preset_name == "map_editing":
            self._reset_dock_layout()
            # Maximized map canvas: keep primary tools and layers visible
            self.tileset_library_dock.hide()
            self.objects_dock.hide()
            self.properties_dock.hide()
            self.tabifyDockWidget(self.layer_dock, self.history_dock)
            self.tabifyDockWidget(self.layer_dock, self.minimap_dock)
            self.layer_dock.raise_()
            self.resizeDocks([self.tileset_preview_dock], [220], Qt.Orientation.Horizontal)
            self.resizeDocks([self.layer_dock], [240], Qt.Orientation.Horizontal)
        elif preset_name == "tileset_studio":
            self._reset_dock_layout()
            self.history_dock.hide()
            self.minimap_dock.hide()
            self.objects_dock.hide()
            self.splitDockWidget(self.tileset_preview_dock, self.tileset_library_dock, Qt.Orientation.Horizontal)
            self.resizeDocks([self.tileset_preview_dock, self.tileset_library_dock], [260, 260], Qt.Orientation.Horizontal)
        elif preset_name == "minimalist":
            for dock in [
                self.tileset_library_dock,
                self.layer_dock,
                self.objects_dock,
                self.properties_dock,
                self.history_dock,
                self.minimap_dock,
            ]:
                dock.hide()
            self.tool_dock.show()
            self.tileset_preview_dock.show()
            self.resizeDocks([self.tileset_preview_dock], [240], Qt.Orientation.Horizontal)
        elif preset_name == "expanded":
            for dock in [
                self.tool_dock,
                self.tileset_preview_dock,
                self.tileset_library_dock,
                self.layer_dock,
                self.objects_dock,
                self.properties_dock,
                self.history_dock,
                self.minimap_dock,
            ]:
                dock.setFloating(False)
                dock.show()
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tool_dock)
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tileset_preview_dock)
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tileset_library_dock)
            self.splitDockWidget(self.tileset_preview_dock, self.tileset_library_dock, Qt.Orientation.Vertical)

            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_dock)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.objects_dock)
            self.splitDockWidget(self.layer_dock, self.objects_dock, Qt.Orientation.Vertical)

            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.history_dock)
            self.tabifyDockWidget(self.properties_dock, self.history_dock)
            self.tabifyDockWidget(self.properties_dock, self.minimap_dock)

        self.canvas.fit_to_view()

    def save_custom_layout_action(self) -> None:
        """Prompts for a name and saves current layout."""
        name, ok = QInputDialog.getText(self, "Zapisz układ", "Podaj unikalną nazwę dla bieżącego układu paneli:")
        if ok and name.strip():
            self.save_custom_layout(name.strip())

    def save_custom_layout(self, name: str) -> None:
        """Saves current dock & window state under a custom name."""
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        custom_layouts = settings.value("custom_layouts", {})
        if not isinstance(custom_layouts, dict):
            custom_layouts = {}
        state_b64 = self.saveState(LAYOUT_VERSION).toBase64().data().decode("ascii")
        geom_b64 = self.saveGeometry().toBase64().data().decode("ascii")
        custom_layouts[name] = {"state": state_b64, "geometry": geom_b64, "version": LAYOUT_VERSION}
        settings.setValue("custom_layouts", custom_layouts)
        self._rebuild_layout_menu()
        if hasattr(self, "status_bar"):
            self.status_bar.showMessage(f"Zapisano układ: '{name}'", 3000)

    def load_custom_layout(self, name: str) -> bool:
        """Loads and applies a previously saved custom layout with safe fallback."""
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        custom_layouts = settings.value("custom_layouts", {})
        if isinstance(custom_layouts, dict) and name in custom_layouts:
            data = custom_layouts[name]
            from PyQt6.QtCore import QByteArray
            success = True
            version = data.get("version", LAYOUT_VERSION)
            if "geometry" in data:
                geom_bytes = QByteArray.fromBase64(data["geometry"].encode("ascii"))
                self.restoreGeometry(geom_bytes)
            if "state" in data:
                state_bytes = QByteArray.fromBase64(data["state"].encode("ascii"))
                success = self.restoreState(state_bytes, version)

            if not success:
                self._reset_dock_layout()
                if hasattr(self, "status_bar"):
                    self.status_bar.showMessage(f"Układ '{name}' jest nieprawidłowy – przywrócono domyślny", 4000)
                return False

            if hasattr(self, "status_bar"):
                self.status_bar.showMessage(f"Wczytano układ: '{name}'", 3000)
            return True
        return False

    def rename_custom_layout(self, old_name: str, new_name: str) -> bool:
        """Renames an existing saved layout preset."""
        if not old_name or not new_name or old_name == new_name:
            return False
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        custom_layouts = settings.value("custom_layouts", {})
        if not isinstance(custom_layouts, dict) or old_name not in custom_layouts:
            return False
        if new_name in custom_layouts:
            return False
        custom_layouts[new_name] = custom_layouts.pop(old_name)
        settings.setValue("custom_layouts", custom_layouts)
        self._rebuild_layout_menu()
        if hasattr(self, "status_bar"):
            self.status_bar.showMessage(f"Zmieniono nazwę układu: '{old_name}' -> '{new_name}'", 3000)
        return True

    def rename_custom_layout_action(self, old_name: Optional[str] = None) -> None:
        """Prompts for a new name for an existing layout preset."""
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        custom_layouts = settings.value("custom_layouts", {})
        if not isinstance(custom_layouts, dict) or not custom_layouts:
            QMessageBox.information(self, "Zmień nazwę układu", "Brak zapisanych układów do zmiany nazwy.")
            return

        if not old_name:
            items = sorted(custom_layouts.keys())
            item, ok = QInputDialog.getItem(self, "Zmień nazwę układu", "Wybierz układ do zmiany nazwy:", items, 0, False)
            if not ok or not item:
                return
            old_name = item

        new_name, ok = QInputDialog.getText(
            self, "Zmień nazwę układu", f"Podaj nową nazwę dla układu '{old_name}':", text=old_name
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            if not self.rename_custom_layout(old_name, new_name.strip()):
                QMessageBox.warning(self, "Błąd", f"Nie można zmienić nazwy na '{new_name.strip()}'. Być może układ o tej nazwie już istnieje.")

    def delete_custom_layout(self, name: str) -> None:
        """Deletes a saved layout preset."""
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        custom_layouts = settings.value("custom_layouts", {})
        if isinstance(custom_layouts, dict) and name in custom_layouts:
            del custom_layouts[name]
            settings.setValue("custom_layouts", custom_layouts)
            self._rebuild_layout_menu()
            if hasattr(self, "status_bar"):
                self.status_bar.showMessage(f"Usunięto układ: '{name}'", 3000)

    def _rebuild_layout_menu(self) -> None:
        """Rebuilds the dynamically populated Load/Rename/Delete submenus."""
        if not hasattr(self, "menu_load_layout") or not hasattr(self, "menu_delete_layout"):
            return

        self.menu_load_layout.clear()
        if hasattr(self, "menu_rename_layout"):
            self.menu_rename_layout.clear()
        self.menu_delete_layout.clear()

        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        custom_layouts = settings.value("custom_layouts", {})
        if not isinstance(custom_layouts, dict) or not custom_layouts:
            act_empty1 = QAction("(Brak zapisanych układów)", self)
            act_empty1.setEnabled(False)
            self.menu_load_layout.addAction(act_empty1)

            if hasattr(self, "menu_rename_layout"):
                act_empty_ren = QAction("(Brak zapisanych układów)", self)
                act_empty_ren.setEnabled(False)
                self.menu_rename_layout.addAction(act_empty_ren)

            act_empty2 = QAction("(Brak zapisanych układów)", self)
            act_empty2.setEnabled(False)
            self.menu_delete_layout.addAction(act_empty2)
            return

        for layout_name in sorted(custom_layouts.keys()):
            act_load = QAction(IconFactory.get_icon("layout", 16), layout_name, self)
            act_load.triggered.connect(lambda ch, ln=layout_name: self.load_custom_layout(ln))
            self.menu_load_layout.addAction(act_load)

            if hasattr(self, "menu_rename_layout"):
                act_ren = QAction(IconFactory.get_icon("pencil", 16), f"Zmień: {layout_name}", self)
                act_ren.triggered.connect(lambda ch, ln=layout_name: self.rename_custom_layout_action(ln))
                self.menu_rename_layout.addAction(act_ren)

            act_del = QAction(IconFactory.get_icon("trash", 16), f"Usuń: {layout_name}", self)
            act_del.triggered.connect(lambda ch, ln=layout_name: self.delete_custom_layout(ln))
            self.menu_delete_layout.addAction(act_del)

    def _restore_settings(self) -> None:
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        geom = settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        state = settings.value("windowState")
        if state:
            success = self.restoreState(state, LAYOUT_VERSION)
            if not success:
                self._reset_dock_layout()
        else:
            self._reset_dock_layout()

        # Synchronize secondary toolbar visibility with toolbar_manager layout configuration
        if hasattr(self, "toolbar_manager") and hasattr(self, "secondary_toolbar") and self.secondary_toolbar:
            self.secondary_toolbar.setVisible(self.toolbar_manager.secondary_toolbar_visible)

        # Restore persistent tileset library from ConfigManager
        active_id, expanded = self.config_manager.restore_tileset_library(self.asset_manager)
        if hasattr(self, "tileset_palette"):
            self.tileset_palette.expanded_folders = list(expanded)
            self.tileset_palette.refresh_tilesets()
            if active_id:
                active_asset = self.asset_manager.get_asset(active_id)
                if active_asset:
                    self.tileset_palette.set_active_asset(active_asset)

        # Restore persistent autotile rules
        self.config_manager.restore_autotile_rules(self.autotile_engine)
        if hasattr(self, "brush_options") and hasattr(self.brush_options, "refresh_rulesets"):
            self.brush_options.refresh_rulesets()

        # Restore persistent brush randomizer settings
        self.config_manager.restore_brush_settings(self.canvas.tool_context.brush_settings)
        if hasattr(self, "brush_options") and hasattr(self.brush_options, "update_variants_summary"):
            self.brush_options.update_variants_summary()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if hasattr(self, "toolbar_manager") and self.toolbar_manager.is_edit_mode:
                self.toolbar_manager.set_edit_mode(False)
                event.accept()
                return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        geom = self.saveGeometry()
        state = self.saveState(LAYOUT_VERSION)
        settings.setValue("geometry", geom)
        settings.setValue("windowState", state)
        if hasattr(self, "tileset_palette"):
            self.tileset_palette.save_splitter_state()
            self.tileset_palette._auto_save_library()

        # Save autotile rules to ConfigManager
        self.config_manager.save_autotile_rules(self.autotile_engine)

        # Save brush settings to ConfigManager
        self.config_manager.save_brush_settings(self.canvas.tool_context.brush_settings)

        # Save toolbar layout
        if hasattr(self, "toolbar_manager"):
            self.toolbar_manager.save_layout()

        # Save to ConfigManager
        geom_b64 = geom.toBase64().data().decode("ascii") if geom else ""
        state_b64 = state.toBase64().data().decode("ascii") if state else ""
        splitter_b64 = ""
        if hasattr(self, "tileset_palette") and hasattr(self.tileset_palette, "splitter"):
            splitter_b64 = self.tileset_palette.splitter.saveState().toBase64().data().decode("ascii")
        self.config_manager.save_window_state(geom_b64, state_b64, splitter_b64)

        super().closeEvent(event)
