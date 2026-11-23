import os
import sys
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF

from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.models.project import Project
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.tools.base import ToolContext, create_items_from_selection
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eyedropper import EyedropperTool
from tileset_map_maker.ui.tileset_palette_widget import TilesetCanvas, TilesetPaletteWidget

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


class TestTiledTilesetImport(unittest.TestCase):
    """
    Test suite for Tiled-style uniform regular grid tileset import,
    file analysis, remainder fragment handling, and multi-tile painting.
    """

    @classmethod
    def setUpClass(cls):
        cls.sample_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "sample_assets", "terrain_summer.png")
        )
        assert os.path.exists(cls.sample_path), f"File {cls.sample_path} must exist!"

    def setUp(self):
        self.asset_manager = AssetManager()
        self.asset, _, _ = self.asset_manager.import_single_file(self.sample_path)
        self.assertIsNotNone(self.asset)
        # Ensure it is treated as a tileset
        self.asset.asset_type = AssetType.TILESET

    def test_01_file_analysis_and_metadata(self):
        """Analyze file: 512x832 px, RGBA, format PNG, alpha channel detected."""
        meta = self.asset.analyze_file()
        self.assertEqual(meta["width"], 512)
        self.assertEqual(meta["height"], 832)
        self.assertEqual(meta["format"], "PNG")
        self.assertIn("A", meta["mode"])
        self.assertTrue(meta["has_alpha"])

        # Also verify classmethod
        meta_static = Asset.analyze_file_path(self.sample_path)
        self.assertEqual(meta_static["width"], 512)
        self.assertEqual(meta_static["height"], 832)
        self.assertTrue(meta_static["has_alpha"])

    def test_02_grid_32x32_exact_fit(self):
        """32x32 px grid: 16 cols x 26 rows = 416 cells, 0 remainder."""
        cfg = TilesetConfig(tile_width=32, tile_height=32)
        grid = cfg.compute_grid(self.asset.width, self.asset.height)

        self.assertEqual(grid["cols"], 16)
        self.assertEqual(grid["rows"], 26)
        self.assertEqual(grid["total_cells"], 416)
        self.assertEqual(grid["remainder_x"], 0)
        self.assertEqual(grid["remainder_y"], 0)
        self.assertFalse(grid["has_incomplete_edges"])

        # Check first and last cell rects
        x0, y0, w0, h0 = cfg.get_tile_rect(0, 0)
        self.assertEqual((x0, y0, w0, h0), (0, 0, 32, 32))
        x_last, y_last, wl, hl = cfg.get_tile_rect(15, 25)
        self.assertEqual((x_last, y_last, wl, hl), (480, 800, 32, 32))

    def test_03_grid_32x48_with_bottom_remainder(self):
        """32x48 px grid: 16 cols x 17 rows = 272 cells, remainder_y = 16 px."""
        cfg = TilesetConfig(tile_width=32, tile_height=48)
        grid = cfg.compute_grid(512, 832)

        self.assertEqual(grid["cols"], 16)
        self.assertEqual(grid["rows"], 17)
        self.assertEqual(grid["total_cells"], 272)
        self.assertEqual(grid["remainder_x"], 0)
        self.assertEqual(grid["remainder_y"], 16)  # 832 - (17 * 48) = 832 - 816 = 16
        self.assertTrue(grid["has_incomplete_edges"])

    def test_04_grid_48x48_with_both_remainders(self):
        """48x48 px grid: 10 cols x 17 rows = 170 cells, remainder_x=32px, remainder_y=16px."""
        cfg = TilesetConfig(tile_width=48, tile_height=48)
        grid = cfg.compute_grid(512, 832)

        self.assertEqual(grid["cols"], 10)  # 512 // 48 = 10
        self.assertEqual(grid["rows"], 17)  # 832 // 48 = 17
        self.assertEqual(grid["total_cells"], 170)
        self.assertEqual(grid["remainder_x"], 32)  # 512 - 480 = 32
        self.assertEqual(grid["remainder_y"], 16)  # 832 - 816 = 16
        self.assertTrue(grid["has_incomplete_edges"])

    def test_05_grid_64x64_exact_fit(self):
        """64x64 px grid: 8 cols x 13 rows = 104 cells, 0 remainder."""
        cfg = TilesetConfig(tile_width=64, tile_height=64)
        grid = cfg.compute_grid(512, 832)

        self.assertEqual(grid["cols"], 8)
        self.assertEqual(grid["rows"], 13)
        self.assertEqual(grid["total_cells"], 104)
        self.assertEqual(grid["remainder_x"], 0)
        self.assertEqual(grid["remainder_y"], 0)
        self.assertFalse(grid["has_incomplete_edges"])

    def test_06_margins_and_spacings(self):
        """Margin and spacing calculation."""
        cfg = TilesetConfig(
            tile_width=32,
            tile_height=32,
            margin_x=4,
            margin_y=4,
            spacing_x=2,
            spacing_y=2,
        )
        grid = cfg.compute_grid(100, 100)
        # width available: 100 - 8 = 92. step = 34. 92 // 34 = 2 cols. (2 * 32 + 1 * 2 = 66, fits)
        self.assertEqual(grid["cols"], 2)
        self.assertEqual(grid["rows"], 2)
        # Rect of (1, 1): x = 4 + 1 * 34 = 38, y = 38
        x, y, w, h = cfg.get_tile_rect(1, 1)
        self.assertEqual((x, y, w, h), (38, 38, 32, 32))

    def test_07_single_and_multi_tile_subtile(self):
        """SelectedSubTile single cell vs multi-tile rectangular block."""
        cfg = TilesetConfig(tile_width=32, tile_height=32)
        self.asset.tileset_config = cfg

        # Single tile (col=2, row=3)
        single = SelectedSubTile(
            asset_id=self.asset.id,
            col=2,
            row=3,
            cols_count=1,
            rows_count=1,
            sub_x=64,
            sub_y=96,
            sub_w=32,
            sub_h=32,
        )
        self.assertFalse(single.is_multi_tile())
        slice_00 = single.get_tile_slice(0, 0)
        self.assertEqual(slice_00, (64, 96, 32, 32))

        # Multi-tile block: 2 columns x 3 rows (building/tree)
        multi = SelectedSubTile(
            asset_id=self.asset.id,
            col=1,
            row=2,
            cols_count=2,
            rows_count=3,
            sub_x=32,
            sub_y=64,
            sub_w=64,
            sub_h=96,
            tile_width=32,
            tile_height=32,
        )
        self.assertTrue(multi.is_multi_tile())
        # Slice for relative (0, 0) -> cell (1, 2)
        self.assertEqual(multi.get_tile_slice(0, 0), (32, 64, 32, 32))
        # Slice for relative (1, 2) -> cell (2, 4)
        self.assertEqual(multi.get_tile_slice(1, 2), (64, 128, 32, 32))

    def test_08_multi_tile_brush_painting(self):
        """Painting with a 2x3 multi-tile block places 6 correctly aligned MapItems."""
        project = Project(map_width=20, map_height=20, tile_size=32)
        layer = project.get_active_layer()
        self.assertIsNotNone(layer)

        multi = SelectedSubTile(
            asset_id=self.asset.id,
            col=0,
            row=0,
            cols_count=2,
            rows_count=3,
            sub_x=0,
            sub_y=0,
            sub_w=64,
            sub_h=96,
            tile_width=32,
            tile_height=32,
        )
        self.asset_manager.select_asset(self.asset, multi)

        context = ToolContext(
            project=project,
            active_layer=layer,
            asset_manager=self.asset_manager,
            selected_asset=multi,
        )

        brush = BrushTool()
        brush.on_press(4, 5, context)
        brush.on_release(4, 5, context)

        # There should be 6 placed tiles: cols 4..5, rows 5..7
        for dc in range(2):
            for dr in range(3):
                tile = layer.get_tile(4 + dc, 5 + dr)
                self.assertIsNotNone(tile, f"Tile at ({4 + dc}, {5 + dr}) should exist")
                self.assertEqual(tile.asset_id, self.asset.id)
                self.assertEqual(tile.source_x, dc * 32)
                self.assertEqual(tile.source_y, dr * 32)
                self.assertEqual(tile.source_w, 32)
                self.assertEqual(tile.source_h, 32)

    def test_09_eyedropper_picks_subtile_and_coords(self):
        """Eyedropper tool accurately computes subtile col and row in sheet."""
        project = Project(map_width=20, map_height=20, tile_size=32)
        layer = project.get_active_layer()

        cfg = TilesetConfig(tile_width=32, tile_height=32)
        self.asset.tileset_config = cfg

        # Place a tile from sheet col 5, row 7 (x=160, y=224)
        from tileset_map_maker.models.layer import MapItem
        item = MapItem(
            asset_id=self.asset.id,
            col=2,
            row=3,
            source_x=160,
            source_y=224,
            source_w=32,
            source_h=32,
        )
        layer.set_tile(2, 3, item)

        context = ToolContext(
            project=project,
            active_layer=layer,
            asset_manager=self.asset_manager,
        )

        eyedropper = EyedropperTool()
        eyedropper.on_press(2, 3, context)

        # Selected asset in asset manager should be a SelectedSubTile with col=5, row=7
        selected = self.asset_manager.selected_item
        self.assertIsInstance(selected, SelectedSubTile)
        self.assertEqual(selected.asset_id, self.asset.id)
        self.assertEqual(selected.col, 5)
        self.assertEqual(selected.row, 7)
        self.assertEqual(selected.sub_x, 160)
        self.assertEqual(selected.sub_y, 224)

    def test_10_tileset_palette_widget(self):
        """TilesetPaletteWidget and TilesetCanvas interactive operations."""
        palette = TilesetPaletteWidget(self.asset_manager)
        palette.set_active_asset(self.asset)

        canvas = palette.canvas
        self.assertEqual(canvas.current_asset.id, self.asset.id)

        # World to cell coordinates
        cell_00 = canvas.world_to_cell(QPointF(10.0, 10.0))
        self.assertEqual(cell_00, (0, 0))

        cell_34 = canvas.world_to_cell(QPointF(32 * 3 + 5, 32 * 4 + 5))
        self.assertEqual(cell_34, (3, 4))

        # Test selecting a rectangular block in canvas
        canvas.sel_start_col = 1
        canvas.sel_start_row = 1
        canvas.sel_end_col = 3
        canvas.sel_end_row = 2
        canvas._emit_selection()

        sel = self.asset_manager.selected_item
        self.assertIsInstance(sel, SelectedSubTile)
        self.assertEqual(sel.cols_count, 3)
        self.assertEqual(sel.rows_count, 2)
        self.assertEqual(sel.sub_w, 96)
        self.assertEqual(sel.sub_h, 64)


if __name__ == "__main__":
    unittest.main()
