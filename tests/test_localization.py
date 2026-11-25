import os
import tempfile
import unittest
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication, QGroupBox
from PyQt6.QtGui import QColor, QImage

from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.core.localization import LocalizationManager, tr


class TestLocalization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)
        self.config = ConfigManager(path)

    def test_default_language_is_english(self):
        loc = LocalizationManager(self.config)
        self.assertEqual(loc.get_language(), "en")
        self.assertEqual(loc.t("action.save"), "Save")

    def test_switch_and_persist_language(self):
        loc = LocalizationManager(self.config)
        loc.set_language("pl")
        self.assertEqual(loc.t("action.save"), "Zapisz")
        reloaded = ConfigManager(self.config.config_path)
        reloaded_loc = LocalizationManager(reloaded)
        self.assertEqual(reloaded_loc.get_language(), "pl")

    def test_missing_translation_falls_back_to_english(self):
        loc = LocalizationManager(self.config)
        loc.set_language("pl")
        self.assertEqual(loc.t("not.a.real.key"), "Missing translation")

    def test_translate_tracks_parameters(self):
        loc = LocalizationManager(self.config)
        self.assertEqual(loc.t("status.cursor"), "Cursor")

    def test_appearance_preference_contains_language(self):
        app = QApplication.instance() or QApplication([])
        from tileset_map_maker.ui.dialogs.preferences_dialog import PreferencesDialog
        from tileset_map_maker.core.localization import get_localization
        localization = get_localization()
        original_language = localization.get_language()
        localization.set_language("en", persist=False)
        dlg = PreferencesDialog()
        try:
            appearance_index = 1
            self.assertEqual(dlg.tab_widget.tabText(appearance_index), "Appearance")
            self.assertTrue(dlg.combo_language is not None)
            self.assertEqual(dlg.combo_language.count(), 2)
            shortcut = dlg.table_shortcuts.item(0, 1).text()
            localization.set_language("pl", persist=False)
            self.assertEqual(dlg.table_shortcuts.item(0, 0).text(), "Pędzel")
            self.assertEqual(dlg.table_shortcuts.item(0, 1).text(), shortcut)
        finally:
            dlg.close()
            localization.set_language(original_language, persist=False)

    def test_popup_dialogs_use_both_locales(self):
        app = QApplication.instance() or QApplication([])
        from tileset_map_maker.core.asset_manager import AssetManager
        from tileset_map_maker.core.autotile_engine import AutoTileEngine
        from tileset_map_maker.core.localization import get_localization
        from tileset_map_maker.core.render_engine import RenderEngine
        from tileset_map_maker.models.asset import AssetType
        from tileset_map_maker.models.brush_preset import BrushSettings
        from tileset_map_maker.models.project import Project
        from tileset_map_maker.ui.dialogs.export_dialog import ExportDialog
        from tileset_map_maker.ui.dialogs.path_generator_dialog import PathGeneratorDialog
        from tileset_map_maker.ui.dialogs.shortcuts_dialog import ShortcutsDialog
        from tileset_map_maker.ui.dialogs.tile_randomizer_dialog import TileRandomizerDialog
        from tileset_map_maker.ui.dialogs.tileset_import_dialog import TilesetImportDialog
        from tileset_map_maker.ui.tileset_palette_widget import GlobalImportSettingsDialog
        from tileset_map_maker.ui.tileset_slicer_dialog import TilesetSlicerDialog

        localization = get_localization()
        original_language = localization.get_language()
        asset_manager = AssetManager()
        project = Project(name="Localization Test")
        dialogs = []
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = os.path.join(temp_dir, "tileset.png")
            image = QImage(64, 64, QImage.Format.Format_ARGB32)
            image.fill(QColor(80, 120, 80))
            self.assertTrue(image.save(image_path))
            tileset, _, error = asset_manager.import_single_file(
                image_path, force_asset_type=AssetType.TILESET
            )
            self.assertFalse(error)
            self.assertIsNotNone(tileset)
            config = ConfigManager(os.path.join(temp_dir, "config.json"))
            slicer_dialog = TilesetSlicerDialog(tileset, asset_manager)
            import_settings_dialog = GlobalImportSettingsDialog(config)
        expected = {
            "en": {
                "path": ("Path Generator - Manual Tile Configuration", "Path role"),
                "randomizer": "General Randomization Options",
                "shortcuts": "Keyboard Shortcuts",
                "export": "Export to PNG",
                "tileset_import": "Grid Split Result",
                "slicer": "Tileset Settings – tileset",
                "slicer_presets": "Quick Grid Size Presets",
                "import_settings": "Default Tileset Import Settings",
            },
            "pl": {
                "path": ("Generator ścieżek – ręczna konfiguracja kafelków", "Rola ścieżki"),
                "randomizer": "Opcje ogólne losowania",
                "shortcuts": "Skróty klawiszowe",
                "export": "Eksport do PNG",
                "tileset_import": "Wynik podziału siatki",
                "slicer": "Ustawienia tilesetu – tileset",
                "slicer_presets": "Szybki wybór rozmiaru siatki",
                "import_settings": "Domyślne ustawienia importu tilesetów",
            },
        }
        try:
            for language in ("en", "pl"):
                localization.set_language(language, persist=False)
                path_dialog = PathGeneratorDialog(AutoTileEngine(), asset_manager)
                randomizer_dialog = TileRandomizerDialog(BrushSettings(), asset_manager)
                shortcuts_dialog = ShortcutsDialog()
                export_dialog = ExportDialog(project, RenderEngine(asset_manager))
                import_dialog = TilesetImportDialog("missing-tileset.png")
                dialogs.extend(
                    [
                        path_dialog,
                        randomizer_dialog,
                        shortcuts_dialog,
                        export_dialog,
                        import_dialog,
                        slicer_dialog,
                        import_settings_dialog,
                    ]
                )

                labels = expected[language]
                self.assertEqual(path_dialog.windowTitle(), labels["path"][0])
                self.assertEqual(
                    path_dialog.table.horizontalHeaderItem(1).text(), labels["path"][1]
                )
                self.assertEqual(randomizer_dialog.windowTitle(), (
                    "Tile Variant Randomizer"
                    if language == "en"
                    else "Konfigurator losowych wariantów kafelków"
                ))
                self.assertEqual(shortcuts_dialog.windowTitle(), labels["shortcuts"])
                self.assertEqual(export_dialog.windowTitle(), labels["export"])
                self.assertEqual(import_dialog.grp_calc.title(), labels["tileset_import"])
                self.assertEqual(slicer_dialog.windowTitle(), labels["slicer"])
                self.assertEqual(
                    slicer_dialog.findChildren(QGroupBox)[0].title(),
                    labels["slicer_presets"],
                )
                self.assertEqual(import_settings_dialog.windowTitle(), labels["import_settings"])

                alternate = "pl" if language == "en" else "en"
                localization.set_language(alternate, persist=False)
                self.assertEqual(
                    path_dialog.table.horizontalHeaderItem(1).text(),
                    "Rola ścieżki" if alternate == "pl" else "Path role",
                )
                self.assertEqual(
                    randomizer_dialog.findChildren(QGroupBox)[0].title(),
                    "Opcje ogólne losowania"
                    if alternate == "pl"
                    else "General Randomization Options",
                )
                self.assertEqual(
                    shortcuts_dialog.windowTitle(),
                    "Skróty klawiszowe" if alternate == "pl" else "Keyboard Shortcuts",
                )
                self.assertEqual(
                    export_dialog.combo_area.itemText(0),
                    "Cała mapa (pełne wymiary)"
                    if alternate == "pl"
                    else "Entire map (full dimensions)",
                )
                self.assertEqual(
                    import_dialog.grp_calc.title(),
                    "Wynik podziału siatki"
                    if alternate == "pl"
                    else "Grid Split Result",
                )
                self.assertEqual(
                    slicer_dialog.windowTitle(),
                    "Ustawienia tilesetu – tileset"
                    if alternate == "pl"
                    else "Tileset Settings – tileset",
                )
                self.assertEqual(
                    import_settings_dialog.windowTitle(),
                    "Domyślne ustawienia importu tilesetów"
                    if alternate == "pl"
                    else "Default Tileset Import Settings",
                )
                localization.set_language(language, persist=False)
        finally:
            for dialog in dialogs:
                dialog.close()
            localization.set_language(original_language, persist=False)

    def test_about_dialog_uses_current_locale(self):
        from unittest.mock import patch
        from tileset_map_maker.core.localization import get_localization
        from tileset_map_maker.ui.main_window import MainWindow

        localization = get_localization()
        original_language = localization.get_language()
        window = MainWindow(config_manager=self.config)
        try:
            for language, title, description in (
                ("en", "About TileSet Map Maker", "Professional 2D map creator"),
                ("pl", "O programie TileSet Map Maker", "Profesjonalny kreator"),
            ):
                localization.set_language(language, persist=False)
                with patch("tileset_map_maker.ui.main_window.QMessageBox.about") as about:
                    window._show_about_dialog()
                self.assertEqual(about.call_args.args[1], title)
                self.assertIn(description, about.call_args.args[2])
        finally:
            window.close()
            localization.set_language(original_language, persist=False)

    def test_main_menus_and_minimap_retranslate_in_both_directions(self):
        app = QApplication.instance() or QApplication([])
        from tileset_map_maker.ui.main_window import MainWindow

        window = MainWindow(config_manager=self.config)
        try:
            localization = window.localization
            palette = window.tileset_palette
            window.toolbar_manager.secondary_toolbar_visible = True
            window.toolbar_manager.build_toolbar()
            window.history_manager.undo_stack.append(
                SimpleNamespace(description="Rysowanie pędzlem")
            )
            window.history_manager.undo_stack.append(
                SimpleNamespace(description="Dodaj warstwę 'Warstwa 1'")
            )
            window.history_manager.redo_stack.append(
                SimpleNamespace(description="Użycie gumki")
            )
            localization.set_language("pl")
            self.assertEqual(
                {
                    **{
                        category_id: grip.lbl_title.text()
                        for category_id, grip in window.toolbar.category_grips.items()
                    },
                    **{
                        category_id: grip.lbl_title.text()
                        for category_id, grip in window.secondary_toolbar.category_grips.items()
                    },
                },
                {
                    "project": "Projekt",
                    "history": "Historia",
                    "view": "Widok",
                    "brush": "Pędzel",
                    "paths": "Ścieżki",
                    "randomizer": "Losowe warianty",
                    "transforms": "Transformacje",
                    "system": "System",
                },
            )
            self.assertEqual(
                tr("palette.canvas_empty"),
                "Brak załadowanego tilesetu.\nWybierz tileset z biblioteki poniżej lub zaimportuj plik (+)",
            )
            self.assertEqual(palette.lbl_list_title.text(), "Tilesety (0)")
            self.assertEqual(
                palette.lbl_active_title.text(),
                "Podgląd tilesetu: (Brak wyboru)",
            )
            self.assertIn("Kliknij [+ Plik(i)]", palette.lbl_info.text())
            self.assertEqual(window.tileset_preview_dock.windowTitle(), "Podgląd tilesetu")
            self.assertEqual(window.tileset_library_dock.windowTitle(), "Biblioteka tilesetów")
            history = window.history_panel
            history_items = [
                history.list_history.item(index).text()
                for index in range(history.list_history.count())
            ]
            self.assertEqual(history.lbl_title.text(), "HISTORIA OPERACJI")
            self.assertEqual(
                history_items,
                [
                    "Stan początkowy",
                    "Rysowanie pędzlem",
                    "Dodaj warstwę 'Warstwa 1'",
                    "Użycie gumki (cofnięto)",
                ],
            )
            self.assertEqual(window.properties_panel.grp_map.title(), "Aktywna mapa")
            self.assertEqual(window.properties_panel.grp_layer.title(), "Aktywna warstwa")
            self.assertEqual(
                window.properties_panel.grp_sel.title(),
                "Wybrany element / pędzel",
            )
            self.assertEqual(
                window.properties_panel.form_map.labelForField(
                    window.properties_panel.lbl_map_dim
                ).text(),
                "Wymiary mapy:",
            )
            self.assertIn("komórek", window.properties_panel.lbl_map_dim.text())
            self.assertIn("warstw", window.properties_panel.lbl_layers_cnt.text())
            self.assertEqual(window.properties_panel.lbl_layer_status.text(), "Widoczna, Edytowalna")
            self.assertEqual(window.properties_panel.lbl_sel_type.text(), "Brak wyboru")

            menus = window.menuBar().actions()
            self.assertEqual(
                [action.text() for action in menus],
                ["&Plik", "&Edycja", "&Widok", "&Narzędzia", "&Pomoc"],
            )
            file_items = [action.text() for action in menus[0].menu().actions()]
            self.assertTrue({"Zapisz jako...", "Eksport PNG", "Zamknij program"} <= set(file_items))
            edit_items = [action.text() for action in menus[1].menu().actions()]
            self.assertTrue(
                {"Cofnij", "Ponów", "Kopiuj", "Wklej", "Preferencje..."} <= set(edit_items)
            )
            view_items = [action.text() for action in menus[2].menu().actions()]
            self.assertTrue(
                {"&Układ", "&Panele dokowalne", "Minimapa", "Pasek zakładek map",
                 "Personalizuj paski narzędzi (Drag & Drop)...",
                 "Dostosuj paski narzędzi (Dialog)..."} <= set(view_items)
            )
            tool_items = [action.text() for action in menus[3].menu().actions()]
            self.assertTrue(
                {"Pędzel (B)", "Gumka (E)", "Wypełnianie (G)", 
                 "Generator ścieżek", "Losowe warianty", "Zapisz stempel"} <= set(tool_items)
            )
            self.assertEqual(
                [action.text() for action in menus[4].menu().actions()],
                ["Skróty", "O programie"],
            )
            self.assertEqual(window.minimap_dock.windowTitle(), "Minimapa")

            localization.set_language("en")
            self.assertEqual(
                {
                    **{
                        category_id: grip.lbl_title.text()
                        for category_id, grip in window.toolbar.category_grips.items()
                    },
                    **{
                        category_id: grip.lbl_title.text()
                        for category_id, grip in window.secondary_toolbar.category_grips.items()
                    },
                },
                {
                    "project": "Project",
                    "history": "History",
                    "view": "View",
                    "brush": "Brush",
                    "paths": "Paths",
                    "randomizer": "Randomizer",
                    "transforms": "Transforms",
                    "system": "System",
                },
            )
            self.assertEqual(
                tr("palette.canvas_empty"),
                "No tileset loaded.\nSelect a tileset from the library below or import a file (+)",
            )
            self.assertEqual(palette.lbl_list_title.text(), "Tilesets (0)")
            self.assertEqual(
                palette.lbl_active_title.text(),
                "Tileset preview: (No selection)",
            )
            self.assertIn("Click [+ File(s)]", palette.lbl_info.text())
            self.assertEqual(window.tileset_preview_dock.windowTitle(), "Tileset Preview")
            self.assertEqual(window.tileset_library_dock.windowTitle(), "Tileset Library")
            history_items = [
                history.list_history.item(index).text()
                for index in range(history.list_history.count())
            ]
            self.assertEqual(history.lbl_title.text(), "OPERATION HISTORY")
            self.assertEqual(
                history_items,
                [
                    "Initial state",
                    "Paint with brush",
                    "Add layer 'Warstwa 1'",
                    "Erase with eraser (undone)",
                ],
            )
            self.assertEqual(window.properties_panel.grp_map.title(), "Active Map")
            self.assertEqual(window.properties_panel.grp_layer.title(), "Active Layer")
            self.assertEqual(window.properties_panel.grp_sel.title(), "Selected Item / Brush")
            self.assertEqual(
                window.properties_panel.form_map.labelForField(
                    window.properties_panel.lbl_map_dim
                ).text(),
                "Map dimensions:",
            )
            self.assertIn("cells", window.properties_panel.lbl_map_dim.text())
            self.assertIn("layers", window.properties_panel.lbl_layers_cnt.text())
            self.assertEqual(
                window.properties_panel.lbl_layer_status.text(),
                "Visible, Editable",
            )
            self.assertEqual(window.properties_panel.lbl_sel_type.text(), "No selection")

            menus = window.menuBar().actions()
            self.assertEqual(
                [action.text() for action in menus],
                ["&File", "&Edit", "&View", "&Tools", "&Help"],
            )
            self.assertTrue(
                {"Save As...", "Export PNG", "Exit"}
                <= {action.text() for action in menus[0].menu().actions()}
            )
            self.assertTrue(
                {"Undo", "Redo", "Copy", "Paste", "Preferences..."}
                <= {action.text() for action in menus[1].menu().actions()}
            )
            en_view_items = {action.text() for action in menus[2].menu().actions()}
            self.assertTrue(
                {"&Layout", "&Dockable Panels", "Minimap", "Map Tabs",
                 "Customize Toolbars (Drag & Drop)...",
                 "Customize Toolbars (Dialog)..."} <= en_view_items
            )
            en_tool_items = {action.text() for action in menus[3].menu().actions()}
            self.assertTrue(
                {"Brush (B)", "Eraser (E)", "Fill (G)", 
                 "Path Generator", "Random Variants", "Save Stamp"} <= en_tool_items
            )
            self.assertEqual(
                [action.text() for action in menus[4].menu().actions()],
                ["Shortcuts", "About"],
            )
            self.assertEqual(window.minimap_dock.windowTitle(), "Minimap")
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
