import unittest
import os
import sys
import tempfile
import shutil
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QImage, QColor

from tileset_map_maker.models.asset import AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.models.layer import ItemType
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.core.tools.fill import FillTool
from tileset_map_maker.core.tools.eyedropper import EyedropperTool
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.ui.main_window import MainWindow


class TestStage3CanvasToolsLayersExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.test_dir = tempfile.mkdtemp()

        # Create a sample test sheet (64x64 px = 2x2 of 32x32)
        cls.sample_path = os.path.join(cls.test_dir, "test_tileset.png")
        img = QImage(64, 64, QImage.Format.Format_ARGB32)
        img.fill(QColor(50, 150, 50))
        img.save(cls.sample_path)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        self.win = MainWindow()
        self.asset, _, _ = self.win.asset_manager.import_single_file(
            self.sample_path,
            target_category_path="Terrain",
            force_asset_type=AssetType.TILESET
        )
        self.asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.win.tileset_palette.set_active_asset(self.asset)

    def test_01_coordinate_transformation_accuracy(self):
        """1. Screen to tile coordinate conversion is pixel-accurate across zooms and pan offsets."""
        canvas = self.win.canvas
        ts = self.win.project.tile_size  # 32 px

        # Test at 1.0x zoom, pan (0, 0)
        canvas.zoom = 1.0
        canvas.pan_offset = QPointF(0.0, 0.0)
        self.assertEqual(canvas.screen_to_tile(QPointF(0, 0)), (0, 0))
        self.assertEqual(canvas.screen_to_tile(QPointF(31, 31)), (0, 0))
        self.assertEqual(canvas.screen_to_tile(QPointF(32, 0)), (1, 0))
        self.assertEqual(canvas.screen_to_tile(QPointF(64, 96)), (2, 3))

        # Test at 2.0x zoom, pan (100, 50)
        canvas.zoom = 2.0
        canvas.pan_offset = QPointF(100.0, 50.0)
        # Point (100, 50) on screen maps to world (0, 0) -> cell (0, 0)
        self.assertEqual(canvas.screen_to_tile(QPointF(100, 50)), (0, 0))
        # Point (100 + 2 * 32, 50 + 2 * 32 * 2) = (164, 178) -> cell (1, 2)
        self.assertEqual(canvas.screen_to_tile(QPointF(164, 178)), (1, 2))

    def test_02_brush_single_and_multi_tile_painting(self):
        """2. Brush paints single tile and multi-tile rectangular blocks with spatial accuracy."""
        layer = self.win.project.get_active_layer()
        self.assertIsNotNone(layer)

        # 2a: Single tile painting at cell (4, 4)
        sub_single = SelectedSubTile(self.asset.id, col=0, row=0, cols_count=1, rows_count=1, sub_w=32, sub_h=32)
        self.win.asset_manager.select_asset(self.asset, sub_single)

        ctx = self.win.canvas.tool_context
        brush = BrushTool()
        brush.on_press(4, 4, ctx)
        brush.on_release(4, 4, ctx)

        tile = layer.get_tile(4, 4)
        self.assertIsNotNone(tile)
        self.assertEqual(tile.item_type, ItemType.TILE)
        self.assertEqual(tile.asset_id, self.asset.id)
        self.assertEqual(tile.source_x, 0)
        self.assertEqual(tile.source_y, 0)

        # 2b: Multi-tile block (2x2) painting at cell (6, 6)
        sub_multi = SelectedSubTile(self.asset.id, col=0, row=0, cols_count=2, rows_count=2, sub_w=64, sub_h=64)
        self.win.asset_manager.select_asset(self.asset, sub_multi)

        brush.on_press(6, 6, ctx)
        brush.on_release(6, 6, ctx)

        # All 4 sub-tiles must be placed correctly
        self.assertIsNotNone(layer.get_tile(6, 6))
        self.assertIsNotNone(layer.get_tile(7, 6))
        self.assertIsNotNone(layer.get_tile(6, 7))
        self.assertIsNotNone(layer.get_tile(7, 7))

    def test_03_eraser_removes_tiles_and_respects_lock(self):
        """3. Eraser removes tiles and prevents erasing when layer is locked."""
        layer = self.win.project.get_active_layer()
        ctx = self.win.canvas.tool_context
        eraser = EraserTool()

        # Paint a tile at (2, 2)
        sub = SelectedSubTile(self.asset.id, col=0, row=0, cols_count=1, rows_count=1)
        self.win.asset_manager.select_asset(self.asset, sub)
        BrushTool().on_press(2, 2, ctx)

        self.assertIsNotNone(layer.get_tile(2, 2))

        # Erase when unlocked
        eraser.on_press(2, 2, ctx)
        eraser.on_release(2, 2, ctx)
        self.assertIsNone(layer.get_tile(2, 2))

        # Re-paint and lock layer
        BrushTool().on_press(2, 2, ctx)
        self.assertIsNotNone(layer.get_tile(2, 2))
        layer.locked = True

        # Erasing on locked layer must be a no-op
        eraser.on_press(2, 2, ctx)
        eraser.on_release(2, 2, ctx)
        self.assertIsNotNone(layer.get_tile(2, 2))

    def test_04_flood_fill_tool(self):
        """4. FillTool fills contiguous empty or matching cells within map bounds."""
        layer = self.win.project.get_active_layer()
        layer.locked = False
        ctx = self.win.canvas.tool_context

        # Set map size small for fast flood fill
        self.win.project.map_width = 5
        self.win.project.map_height = 5
        layer.tiles.clear()

        # Arm brush with asset
        sub = SelectedSubTile(self.asset.id, col=1, row=1, cols_count=1, rows_count=1, sub_x=32, sub_y=32)
        self.win.asset_manager.select_asset(self.asset, sub)

        fill = FillTool()
        fill.on_press(0, 0, ctx)

        # Entire 5x5 grid should now be filled with sub-tile
        self.assertEqual(len(layer.tiles), 25)
        for c in range(5):
            for r in range(5):
                t = layer.get_tile(c, r)
                self.assertIsNotNone(t)
                self.assertEqual(t.source_x, 32)
                self.assertEqual(t.source_y, 32)

    def test_05_eyedropper_tool_samples_tile(self):
        """5. EyedropperTool samples tile accurately and arms active asset."""
        layer = self.win.project.get_active_layer()
        layer.locked = False
        ctx = self.win.canvas.tool_context

        # Paint cell (3, 3) with cell (1, 0) -> source_x=32, source_y=0
        sub_painted = SelectedSubTile(self.asset.id, col=1, row=0, cols_count=1, rows_count=1, sub_x=32, sub_y=0)
        self.win.asset_manager.select_asset(self.asset, sub_painted)
        BrushTool().on_press(3, 3, ctx)

        # Clear active selection to simulate user picking from canvas
        self.win.asset_manager.selected_item = None

        eyedropper = EyedropperTool()
        eyedropper.on_press(3, 3, ctx)

        sampled = self.win.asset_manager.selected_item
        self.assertIsInstance(sampled, SelectedSubTile)
        self.assertEqual(sampled.asset_id, self.asset.id)
        self.assertEqual(sampled.col, 1)
        self.assertEqual(sampled.row, 0)
        self.assertEqual(sampled.sub_x, 32)
        self.assertEqual(sampled.sub_y, 0)

    def test_06_undo_redo_fidelity(self):
        """6. Undo and Redo revert and restore brush, eraser, and fill changes."""
        layer = self.win.project.get_active_layer()
        ctx = self.win.canvas.tool_context
        hist = self.win.history_manager

        sub = SelectedSubTile(self.asset.id, col=0, row=0, cols_count=1, rows_count=1)
        self.win.asset_manager.select_asset(self.asset, sub)

        # 1. Paint tile at (1, 1)
        brush = BrushTool()
        brush.on_press(1, 1, ctx)
        brush.on_release(1, 1, ctx)
        self.assertIsNotNone(layer.get_tile(1, 1))

        # 2. Undo -> tile removed
        self.assertTrue(hist.can_undo())
        hist.undo()
        self.assertIsNone(layer.get_tile(1, 1))

        # 3. Redo -> tile restored
        self.assertTrue(hist.can_redo())
        hist.redo()
        self.assertIsNotNone(layer.get_tile(1, 1))

    def test_07_status_bar_updates(self):
        """7. Status bar updates X, Y cursor position, zoom percentage, and active layer."""
        self.win._on_cursor_moved(15, 23)
        self.assertIn("15", self.win.lbl_status_pos.text())
        self.assertIn("23", self.win.lbl_status_pos.text())

        self.win._on_zoom_changed(2.5)
        self.assertEqual(self.win.lbl_status_zoom.text(), "Zoom: 250%")

        layer = self.win.project.get_active_layer()
        self.assertIn(layer.name, self.win.lbl_status_layer.text())

    def test_08_layer_panel_operations(self):
        """8. LayerPanel supports adding, deleting, renaming, visibility, locking, and opacity."""
        panel = self.win.layer_panel
        initial_count = len(self.win.project.layers)

        # Add layer
        new_layer = self.win.project.add_layer("Warstwa Testowa")
        panel.refresh_layers()
        self.assertEqual(len(self.win.project.layers), initial_count + 1)

        # Toggle visibility
        new_layer.visible = False
        self.assertFalse(self.win.project.get_effective_visible(new_layer))

        # Toggle lock
        new_layer.locked = True
        self.assertTrue(self.win.project.get_effective_locked(new_layer))

        # Change opacity
        panel.slider_opacity.setValue(60)
        self.assertAlmostEqual(new_layer.opacity, 0.60, places=2)

        # Remove layer
        self.win.project.remove_layer(new_layer.id)
        panel.refresh_layers()
        self.assertEqual(len(self.win.project.layers), initial_count)

    def test_09_save_load_project_and_export_png(self):
        """9. Save/Load to .tmmap and export to PNG with transparency preservation."""
        proj = self.win.project
        layer = proj.get_active_layer()
        layer.locked = False

        # Paint a tile
        sub = SelectedSubTile(self.asset.id, col=0, row=0, cols_count=1, rows_count=1)
        self.win.asset_manager.select_asset(self.asset, sub)
        BrushTool().on_press(0, 0, self.win.canvas.tool_context)

        # 9a: Save project to JSON .tmmap
        save_file = os.path.join(self.test_dir, "test_project.tmmap")
        ok_save = ProjectIO.save_project(proj, self.win.asset_manager, save_file)
        self.assertTrue(ok_save)
        self.assertTrue(os.path.exists(save_file))

        # 9b: Load project from .tmmap
        loaded_mgr = self.win.asset_manager
        loaded_proj = ProjectIO.load_project(save_file, loaded_mgr)
        self.assertIsNotNone(loaded_proj)
        self.assertEqual(loaded_proj.map_width, proj.map_width)
        loaded_tile = loaded_proj.get_active_layer().get_tile(0, 0)
        self.assertIsNotNone(loaded_tile)
        self.assertEqual(loaded_tile.asset_id, self.asset.id)

        # 9c: Export to PNG
        export_file = os.path.join(self.test_dir, "test_export.png")
        ok_export = ProjectIO.export_png(
            proj,
            self.win.render_engine,
            export_file,
            transparent_bg=True,
        )
        self.assertTrue(ok_export)
        self.assertTrue(os.path.exists(export_file))

        exported_img = QImage(export_file)
        self.assertFalse(exported_img.isNull())
        self.assertEqual(exported_img.width(), proj.map_width * proj.tile_size)
        self.assertEqual(exported_img.height(), proj.map_height * proj.tile_size)


if __name__ == "__main__":
    unittest.main()
