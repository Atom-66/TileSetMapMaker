import unittest
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QDockWidget
from PyQt6.QtCore import Qt, QSettings, QByteArray

from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig
from tileset_map_maker.models.layer import MapItem, ItemType


class TestDockingAndLayouts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        settings.clear()
        self.win = MainWindow()
        self.win.show()

    def tearDown(self):
        self.win.close()
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        settings.clear()

    def test_drag_safety_cancel_is_idempotent(self):
        """Escape/focus loss can cancel all drag state repeatedly without exceptions."""
        self.win.drag_safety.cancel_all("test escape")
        self.win.drag_safety.cancel_all("test focus loss")
        self.assertFalse(self.win.drag_safety.is_active("missing-operation"))

    def test_01_drag_panel_left_to_right(self):
        """1. Przeciągnięcie panelu z lewej strony na prawą (zmiana obszaru dokowania)."""
        # Initially tileset_preview_dock is on the left
        left_docks = self.win.findChildren(QDockWidget)
        self.assertEqual(self.win.dockWidgetArea(self.win.tileset_preview_dock), Qt.DockWidgetArea.LeftDockWidgetArea)

        # Move tileset preview dock to the right
        self.win.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.win.tileset_preview_dock)
        self.assertEqual(self.win.dockWidgetArea(self.win.tileset_preview_dock), Qt.DockWidgetArea.RightDockWidgetArea)
        self.assertTrue(self.win.tileset_preview_dock.isVisible())

    def test_02_combine_panels_into_tab_group(self):
        """2. Połączenie dwóch paneli w grupę zakładek (tabifyDockWidget)."""
        # Combine preview dock and library dock into a tabbed group
        self.win.tabifyDockWidget(self.win.tileset_preview_dock, self.win.tileset_library_dock)
        tabbed_docks = self.win.tabifiedDockWidgets(self.win.tileset_preview_dock)
        self.assertIn(self.win.tileset_library_dock, tabbed_docks)

    def test_03_separate_tab_into_individual_panel(self):
        """3. Rozdzielenie zakładki na osobny panel."""
        # First ensure they are tabbed
        self.win.tabifyDockWidget(self.win.tileset_preview_dock, self.win.tileset_library_dock)
        self.assertIn(self.win.tileset_library_dock, self.win.tabifiedDockWidgets(self.win.tileset_preview_dock))

        # Separate by splitting vertically
        self.win.splitDockWidget(self.win.tileset_preview_dock, self.win.tileset_library_dock, Qt.Orientation.Vertical)
        tabbed_after = self.win.tabifiedDockWidgets(self.win.tileset_preview_dock)
        self.assertNotIn(self.win.tileset_library_dock, tabbed_after)

    def test_04_reorder_and_raise_tab_groups(self):
        """4. Zmiana kolejności zakładek i uaktywnianie wybranej zakładki."""
        # On right side: layer_dock, properties_dock, history_dock
        self.win.layer_dock.raise_()
        self.assertTrue(self.win.layer_dock.isVisible())

        # Switch to history dock
        self.win.history_dock.raise_()
        self.assertTrue(self.win.history_dock.isVisible())

    def test_05_detach_panel_into_floating_window(self):
        """5. Odłączenie panelu do osobnego, niezależnego okna (setFloating)."""
        dock = self.win.tool_dock
        self.assertFalse(dock.isFloating())

        dock.setFloating(True)
        self.assertTrue(dock.isFloating())
        self.assertTrue(dock.isVisible())

    def test_06_redock_floating_window(self):
        """6. Ponowne zadokowanie okna pływającego do głównego układu."""
        dock = self.win.tileset_library_dock
        dock.setFloating(True)
        self.assertTrue(dock.isFloating())

        dock.setFloating(False)
        self.win.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self.assertFalse(dock.isFloating())
        self.assertEqual(self.win.dockWidgetArea(dock), Qt.DockWidgetArea.BottomDockWidgetArea)

    def test_07_resize_docks_adjusts_proportions(self):
        """7. Zmiana rozmiarów kilku paneli (resizeDocks)."""
        # Resize left docks
        self.win.resizeDocks([self.win.tileset_preview_dock], [350], Qt.Orientation.Horizontal)
        self.win.resizeDocks([self.win.layer_dock], [320], Qt.Orientation.Horizontal)
        self.assertTrue(self.win.canvas.isVisible())
        self.assertGreaterEqual(self.win.tileset_preview_dock.width(), 180)

    def test_12_tool_dock_uses_single_column_content_width(self):
        """The left ToolDock must not reserve extra columns or right-side padding."""
        app = QApplication.instance()
        self.win.show()
        app.processEvents()

        self.win._update_tool_dock_width()
        app.processEvents()

        self.assertEqual(self.win.tool_dock.width(), 44)
        self.assertEqual(self.win.tool_panel.width(), 44)
        self.assertEqual(self.win.tool_panel.layout().contentsMargins().left(), 4)
        self.assertEqual(self.win.tool_panel.layout().contentsMargins().right(), 4)

        for button in self.win.tool_panel.buttons.values():
            rect = button.geometry()
            self.assertGreaterEqual(rect.left(), 0)
            self.assertLessEqual(rect.right(), self.win.tool_panel.width())

    def test_08_save_custom_layout_and_reload(self):
        """8. Zapisanie układu, zmiana stanu i ponowne wczytanie zapisanego układu."""
        # Float history dock and hide minimap
        self.win.history_dock.setFloating(True)
        self.win.minimap_dock.hide()

        # Save custom layout
        layout_name = "TestCustomLayout"
        self.win.save_custom_layout(layout_name)

        # Change state completely: reset layout
        self.win._reset_dock_layout()
        self.assertFalse(self.win.history_dock.isFloating())
        self.assertTrue(self.win.minimap_dock.isVisible())

        # Reload custom layout
        loaded = self.win.load_custom_layout(layout_name)
        self.assertTrue(loaded)
        self.assertTrue(self.win.history_dock.isFloating())
        self.assertFalse(self.win.minimap_dock.isVisible())

        # Cleanup
        self.win.delete_custom_layout(layout_name)

    def test_09_reset_to_default_layout(self):
        """9. Przywrócenie domyślnego układu po przestawieniu wszystkich paneli."""
        # Mess up layout: float some, hide others
        self.win.tool_dock.setFloating(True)
        self.win.tileset_preview_dock.hide()
        self.win.layer_dock.hide()

        # Reset
        self.win._reset_dock_layout()

        # Verify all docks are unfloated and visible
        for dock in [
            self.win.tool_dock,
            self.win.tileset_preview_dock,
            self.win.tileset_library_dock,
            self.win.layer_dock,
            self.win.properties_dock,
            self.win.history_dock,
            self.win.minimap_dock,
        ]:
            self.assertFalse(dock.isFloating())
            self.assertTrue(dock.isVisible())

        self.assertEqual(self.win.dockWidgetArea(self.win.tileset_preview_dock), Qt.DockWidgetArea.LeftDockWidgetArea)
        self.assertEqual(self.win.dockWidgetArea(self.win.layer_dock), Qt.DockWidgetArea.RightDockWidgetArea)

    def test_10_tileset_preview_and_library_independent_docks_interaction(self):
        """10. Podgląd tilesetu i biblioteka tilesetów jako dwa niezależne panele, ale zsynchronizowane."""
        # Both docks exist as distinct QDockWidgets
        self.assertIsNot(self.win.tileset_preview_dock, self.win.tileset_library_dock)
        self.assertIs(self.win.tileset_dock, self.win.tileset_preview_dock)

        # Import an asset and check synchronization
        asset = Asset(name="GrassSheet", file_path="dummy.png", asset_type=AssetType.TILESET)
        asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.win.asset_manager.assets[asset.id] = asset

        # Selecting in library sets active in palette and preview canvas
        self.win.tileset_palette.set_active_asset(asset)
        self.assertEqual(self.win.tileset_palette.active_asset_id, asset.id)
        self.assertEqual(self.win.tileset_palette.canvas.current_asset.id, asset.id)

    def test_12_corrupted_layout_safe_fallback(self):
        """12. Bezpieczny fallback przy uszkodzonym zapisanym układzie."""
        corrupted_state = QByteArray(b"INVALID_CORRUPTED_GARBAGE_STATE")
        success = self.win.restoreState(corrupted_state)
        if not success:
            self.win._reset_dock_layout()

        # After fallback, default docks should be visible
        self.assertTrue(self.win.tileset_preview_dock.isVisible())
        self.assertTrue(self.win.layer_dock.isVisible())

    def test_13_dock_tabs_placed_at_north(self):
        """13. Sprawdzenie, czy karty zakładek są umieszczone na górze (North) wzorem Photoshopa."""
        from PyQt6.QtWidgets import QTabWidget
        self.assertEqual(
            self.win.tabPosition(Qt.DockWidgetArea.RightDockWidgetArea),
            QTabWidget.TabPosition.North,
        )
        self.assertEqual(
            self.win.tabPosition(Qt.DockWidgetArea.LeftDockWidgetArea),
            QTabWidget.TabPosition.North,
        )

    def test_14_layout_presets_application(self):
        """14. Aplikowanie wbudowanych presetów: Domyślny, Edycja mapy, Studio tilesetów, Minimalistyczny, Rozszerzony."""
        # 1. Map editing preset
        self.win.apply_layout_preset("map_editing")
        self.assertTrue(self.win.layer_dock.isVisible())
        self.assertTrue(self.win.tileset_preview_dock.isVisible())
        self.assertFalse(self.win.tileset_library_dock.isVisible())
        self.assertFalse(self.win.properties_dock.isVisible())

        # 2. Tileset studio preset
        self.win.apply_layout_preset("tileset_studio")
        self.assertTrue(self.win.tileset_preview_dock.isVisible())
        self.assertTrue(self.win.tileset_library_dock.isVisible())
        self.assertFalse(self.win.history_dock.isVisible())
        self.assertFalse(self.win.minimap_dock.isVisible())

        # 3. Minimalist preset
        self.win.apply_layout_preset("minimalist")
        self.assertTrue(self.win.tool_dock.isVisible())
        self.assertTrue(self.win.tileset_preview_dock.isVisible())
        self.assertFalse(self.win.layer_dock.isVisible())
        self.assertFalse(self.win.tileset_library_dock.isVisible())

        # 4. Expanded preset
        self.win.apply_layout_preset("expanded")
        self.assertTrue(self.win.tool_dock.isVisible())
        self.assertTrue(self.win.tileset_preview_dock.isVisible())
        self.assertTrue(self.win.tileset_library_dock.isVisible())
        self.assertTrue(self.win.layer_dock.isVisible())
        self.assertTrue(self.win.properties_dock.isVisible())
        self.assertTrue(self.win.history_dock.isVisible())
        self.assertTrue(self.win.minimap_dock.isVisible())

        # 5. Default preset
        self.win.apply_layout_preset("default")
        self.assertTrue(self.win.layer_dock.isVisible())
        self.assertTrue(self.win.tileset_preview_dock.isVisible())
        self.assertTrue(self.win.tileset_library_dock.isVisible())

    def test_15_rename_custom_layout(self):
        """15. Zmiana nazwy zapisanego profilu układu."""
        self.win.save_custom_layout("OriginalLayout")
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        custom_layouts = settings.value("custom_layouts", {})
        self.assertIn("OriginalLayout", custom_layouts)

        # Rename to RenamedLayout
        renamed = self.win.rename_custom_layout("OriginalLayout", "RenamedLayout")
        self.assertTrue(renamed)

        custom_layouts = settings.value("custom_layouts", {})
        self.assertNotIn("OriginalLayout", custom_layouts)
        self.assertIn("RenamedLayout", custom_layouts)

        # Cannot rename to existing name
        self.win.save_custom_layout("AnotherLayout")
        conflict = self.win.rename_custom_layout("RenamedLayout", "AnotherLayout")
        self.assertFalse(conflict)

        # Load renamed layout works
        loaded = self.win.load_custom_layout("RenamedLayout")
        self.assertTrue(loaded)

    def test_16_corrupted_custom_layout_restore_fallback(self):
        """16. Bezpieczny fallback przy próbie wczytania uszkodzonego zapisanego profilu."""
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        custom_layouts = {
            "BrokenLayout": {
                "state": "VGhpcyBpcyBub3QgYSB2YWxpZCBxdCBzdGF0ZQ==",
                "geometry": "",
                "version": 999,
            }
        }
        settings.setValue("custom_layouts", custom_layouts)

        # Load broken layout: should safely fail and fallback to default layout
        success = self.win.load_custom_layout("BrokenLayout")
        self.assertFalse(success)
        # Fallback ensures default docks are visible
        self.assertTrue(self.win.tileset_preview_dock.isVisible())
        self.assertTrue(self.win.layer_dock.isVisible())


if __name__ == "__main__":
    unittest.main()
