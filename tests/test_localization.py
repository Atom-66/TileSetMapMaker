import os
import tempfile
import unittest
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.core.localization import LocalizationManager, tr


class TestLocalization(unittest.TestCase):
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
        get_localization().set_language("en")
        dlg = PreferencesDialog()
        appearance_index = 1
        self.assertEqual(dlg.tab_widget.tabText(appearance_index), "Appearance")
        self.assertTrue(dlg.combo_language is not None)
        self.assertEqual(dlg.combo_language.count(), 2)

    def test_main_menus_and_minimap_retranslate_in_both_directions(self):
        app = QApplication.instance() or QApplication([])
        from tileset_map_maker.ui.main_window import MainWindow

        window = MainWindow(config_manager=self.config)
        try:
            localization = window.localization
            palette = window.tileset_palette
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
                {"Cofnij", "Ponów", "Kopiuj zaznaczenie", "Wklej zaznaczenie (stempel)",
                 "Usuń zaznaczenie", "Preferencje..."} <= set(edit_items)
            )
            view_items = [action.text() for action in menus[2].menu().actions()]
            self.assertTrue(
                {"&Układ", "&Panele dokowalne", "Minimapa", "Pasek zakładek map",
                 "Personalizuj paski narzędzi (Drag & Drop)...",
                 "Dostosuj paski narzędzi (Dialog)..."} <= set(view_items)
            )
            tool_items = [action.text() for action in menus[3].menu().actions()]
            self.assertTrue(
                {"Pędzel (B)", "Gumka (E)", "Wypełnianie (G)", "Automatyczne kafelkowanie",
                 "Generator ścieżek", "Losowe warianty", "Zapisz stempel"} <= set(tool_items)
            )
            self.assertEqual(
                [action.text() for action in menus[4].menu().actions()],
                ["Skróty", "O programie"],
            )
            self.assertEqual(window.minimap_dock.windowTitle(), "Minimapa")

            localization.set_language("en")
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
                {"Undo", "Redo", "Copy Selection", "Paste Selection (Stamp)",
                 "Delete Selection", "Preferences..."}
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
                {"Brush (B)", "Eraser (E)", "Fill (G)", "Auto-Tiling",
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
