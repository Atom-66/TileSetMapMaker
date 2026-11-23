import unittest
import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QSettings
from PyQt6.QtGui import QImage, QColor

from tileset_map_maker.models.asset import AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.models.project import Project
from tileset_map_maker.models.layer import ItemType
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.ui.tileset_palette_widget import TilesetPaletteWidget


class TestTilesetPanelLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        os.makedirs("test_panel_assets", exist_ok=True)
        # Create 2 sample tilesets (64x64 each = 2x2 of 32x32 tiles)
        img1 = QImage(64, 64, QImage.Format.Format_ARGB32)
        img1.fill(QColor(40, 140, 40))
        img1.save("test_panel_assets/tileset_grass.png")

        img2 = QImage(64, 64, QImage.Format.Format_ARGB32)
        img2.fill(QColor(40, 60, 180))
        img2.save("test_panel_assets/tileset_water.png")

    @classmethod
    def tearDownClass(cls):
        for f in ["test_panel_assets/tileset_grass.png", "test_panel_assets/tileset_water.png"]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists("test_panel_assets"):
            os.rmdir("test_panel_assets")

    def setUp(self):
        self.asset_mgr = AssetManager()
        self.asset_grass, _, _ = self.asset_mgr.import_single_file(
            "test_panel_assets/tileset_grass.png",
            target_category_path="Terrain",
            force_asset_type=AssetType.TILESET
        )
        self.asset_grass.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

        self.asset_water, _, _ = self.asset_mgr.import_single_file(
            "test_panel_assets/tileset_water.png",
            target_category_path="Terrain",
            force_asset_type=AssetType.TILESET
        )
        self.asset_water.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

    def test_01_preview_above_list_in_vertical_splitter(self):
        """1. Preview (top_widget) is above list (bottom_widget) in vertical splitter."""
        palette = TilesetPaletteWidget(self.asset_mgr)
        self.assertIsNotNone(palette.splitter)
        self.assertEqual(palette.splitter.orientation(), Qt.Orientation.Vertical)

        # Check splitter child ordering
        self.assertIs(palette.splitter.widget(0), palette.top_widget)
        self.assertIs(palette.splitter.widget(1), palette.bottom_widget)

        # Check that top_widget contains the interactive canvas
        self.assertTrue(palette.canvas.isWidgetType())
        self.assertIs(palette.canvas.parent(), palette.top_widget)

        # Check that bottom_widget contains the tileset list
        self.assertTrue(palette.tileset_list.isWidgetType())
        self.assertIs(palette.tileset_list.parent(), palette.bottom_widget)

        # Minimum heights are enforced so neither collapses
        self.assertGreaterEqual(palette.top_widget.minimumHeight(), 120)
        self.assertGreaterEqual(palette.bottom_widget.minimumHeight(), 80)
        self.assertFalse(palette.splitter.childrenCollapsible())

    def test_02_splitter_resizing_and_proportion_adjustment(self):
        """2. Splitter allows smooth manual height adjustments between preview and list."""
        palette = TilesetPaletteWidget(self.asset_mgr)
        palette.resize(300, 600)
        palette.show()

        # Set sizes: larger preview (450), smaller list (150)
        palette.splitter.setSizes([450, 150])
        sizes_1 = palette.splitter.sizes()
        self.assertGreater(sizes_1[0], sizes_1[1])

        # Set sizes: smaller preview (200), larger list (400)
        palette.splitter.setSizes([200, 400])
        sizes_2 = palette.splitter.sizes()
        self.assertLess(sizes_2[0], sizes_2[1])

    def test_03_selecting_tileset_in_list_updates_preview(self):
        """3. Selecting a tileset in the bottom list immediately updates the top preview."""
        palette = TilesetPaletteWidget(self.asset_mgr)
        palette.refresh_tilesets()

        # Both tilesets should be present in the bottom list
        self.assertEqual(palette.tileset_list.count(), 2)
        item0 = palette.tileset_list.item(0)
        item1 = palette.tileset_list.item(1)

        # Verify items have names and thumbnail icons
        self.assertIn(self.asset_grass.name, item0.text())
        self.assertIn(self.asset_water.name, item1.text())
        self.assertFalse(item0.icon().isNull())
        self.assertFalse(item1.icon().isNull())

        # Select second item (water)
        palette.tileset_list.setCurrentRow(1)
        self.assertEqual(palette.active_asset_id, self.asset_water.id)
        self.assertEqual(palette.canvas.current_asset.id, self.asset_water.id)

        # Select first item (grass)
        palette.tileset_list.setCurrentRow(0)
        self.assertEqual(palette.active_asset_id, self.asset_grass.id)
        self.assertEqual(palette.canvas.current_asset.id, self.asset_grass.id)

    def test_04_selecting_tiles_and_multi_tile_block_in_preview(self):
        """4. Single and multi-tile rectangular selection in top canvas works cleanly."""
        palette = TilesetPaletteWidget(self.asset_mgr)
        palette.set_active_asset(self.asset_grass)

        # Select single cell (0, 0)
        palette.canvas.sel_start_col = 0
        palette.canvas.sel_start_row = 0
        palette.canvas.sel_end_col = 0
        palette.canvas.sel_end_row = 0
        palette.canvas._emit_selection()

        sel = self.asset_mgr.selected_item
        self.assertIsInstance(sel, SelectedSubTile)
        self.assertEqual((sel.col, sel.row), (0, 0))
        self.assertEqual((sel.cols_count, sel.rows_count), (1, 1))

        # Select 2x2 rectangular block (cells 0,0 to 1,1)
        palette.canvas.sel_start_col = 0
        palette.canvas.sel_start_row = 0
        palette.canvas.sel_end_col = 1
        palette.canvas.sel_end_row = 1
        palette.canvas._emit_selection()

        sel_multi = self.asset_mgr.selected_item
        self.assertIsInstance(sel_multi, SelectedSubTile)
        self.assertEqual((sel_multi.cols_count, sel_multi.rows_count), (2, 2))
        self.assertEqual(sel_multi.sub_w, 64)
        self.assertEqual(sel_multi.sub_h, 64)

    def test_05_painting_on_map_with_selected_tiles(self):
        """5. Armed brush tool paints selected tiles accurately on map layers."""
        win = MainWindow()
        win.asset_manager = self.asset_mgr
        win.tileset_palette.refresh_tilesets()

        # Select grass tileset
        win.tileset_palette.set_active_asset(self.asset_grass)
        # Select single cell (1, 0)
        win.tileset_palette.canvas.sel_start_col = 1
        win.tileset_palette.canvas.sel_start_row = 0
        win.tileset_palette.canvas.sel_end_col = 1
        win.tileset_palette.canvas.sel_end_row = 0
        win.tileset_palette.canvas._emit_selection()

        # Paint using brush tool on active layer at grid (3, 5)
        ctx = win.canvas.tool_context
        brush = BrushTool()
        brush.on_press(3, 5, ctx)
        brush.on_release(3, 5, ctx)

        layer = win.project.get_active_layer()
        self.assertIsNotNone(layer)

        tile = layer.get_tile(3, 5)
        self.assertIsNotNone(tile)
        self.assertEqual(tile.item_type, ItemType.TILE)
        self.assertEqual(tile.asset_id, self.asset_grass.id)

    def test_06_splitter_state_persisted_across_sessions(self):
        """6. Splitter heights are saved and restored cleanly using QSettings."""
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        # Save specific sizes
        palette1 = TilesetPaletteWidget(self.asset_mgr)
        palette1.resize(300, 600)
        palette1.show()
        palette1.splitter.setSizes([380, 220])
        palette1.save_splitter_state()

        # Verify QSettings has the key
        saved_bytes = settings.value("tileset_panel/splitter_state")
        self.assertIsNotNone(saved_bytes)

        # Instantiate a second palette widget (simulating app restart)
        palette2 = TilesetPaletteWidget(self.asset_mgr)
        palette2.resize(300, 600)
        palette2.show()
        palette2.restore_splitter_state()

        restored_sizes = palette2.splitter.sizes()
        self.assertEqual(restored_sizes, palette1.splitter.sizes())


if __name__ == "__main__":
    unittest.main()
