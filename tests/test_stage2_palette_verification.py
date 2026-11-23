import unittest
import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QImage, QColor, QWheelEvent

from tileset_map_maker.models.asset import AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.ui.tileset_palette_widget import TilesetPaletteWidget, TilesetCanvas
from tileset_map_maker.ui.dialogs.tileset_import_dialog import TilesetImportDialog


class TestStage2PaletteVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        os.makedirs("test_stage2_tmp", exist_ok=True)

        # Create a sample test tileset (128x128 px)
        img = QImage(128, 128, QImage.Format.Format_ARGB32)
        img.fill(QColor(60, 160, 60))
        img.save("test_stage2_tmp/tileset_sample.png")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists("test_stage2_tmp/tileset_sample.png"):
            os.remove("test_stage2_tmp/tileset_sample.png")
        if os.path.exists("test_stage2_tmp"):
            os.rmdir("test_stage2_tmp")

    def setUp(self):
        self.asset_mgr = AssetManager()
        self.asset, _, _ = self.asset_mgr.import_single_file(
            "test_stage2_tmp/tileset_sample.png",
            target_category_path="Terrain",
            force_asset_type=AssetType.TILESET
        )
        self.asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

    def test_01_import_dialog_dimensions_and_presets(self):
        """1. TilesetImportDialog allows choosing preset or custom tile sizes."""
        dlg = TilesetImportDialog("test_stage2_tmp/tileset_sample.png", default_tile_size=32)
        # Verify inspection metadata
        self.assertEqual(dlg.img_w, 128)
        self.assertEqual(dlg.img_h, 128)
        self.assertEqual(dlg.get_tile_dimensions(), (32, 32))

        # Check grid calculation for 32x32: 4 cols x 4 rows = 16 cells
        self.assertEqual(dlg.spin_w.value(), 32)
        self.assertEqual(dlg.spin_h.value(), 32)

        # Apply preset 16x16: 8 cols x 8 rows = 64 cells
        dlg._apply_preset(16, 16)
        self.assertEqual(dlg.get_tile_dimensions(), (16, 16))

        # Apply preset 64x64: 2 cols x 2 rows = 4 cells
        dlg._apply_preset(64, 64)
        self.assertEqual(dlg.get_tile_dimensions(), (64, 64))

    def test_02_canvas_rendering_and_grid_structure(self):
        """2. Loaded image renders in the palette with a regular grid matching configuration."""
        palette = TilesetPaletteWidget(self.asset_mgr)
        palette.set_active_asset(self.asset)

        canvas = palette.canvas
        self.assertIsNotNone(canvas.current_asset)
        self.assertEqual(canvas.current_asset.id, self.asset.id)

        cfg = canvas.current_asset.tileset_config
        grid = cfg.compute_grid(self.asset.width, self.asset.height)
        self.assertEqual(grid["cols"], 4)
        self.assertEqual(grid["rows"], 4)
        self.assertEqual(grid["total_cells"], 16)
        self.assertEqual(grid["remainder_x"], 0)
        self.assertEqual(grid["remainder_y"], 0)

    def test_03_zoom_slider_buttons_and_wheel(self):
        """3. Zoom works smoothly via slider, zoom buttons, set_zoom, and updates slider."""
        palette = TilesetPaletteWidget(self.asset_mgr)
        palette.set_active_asset(self.asset)
        palette.resize(300, 600)
        palette.show()

        canvas = palette.canvas
        # Test direct set_zoom
        canvas.set_zoom(2.0)
        self.assertEqual(canvas.zoom, 2.0)
        self.assertEqual(palette.slider_zoom.value(), 200)

        # Test zoom in button
        palette.btn_zoom_in.click()
        self.assertGreater(canvas.zoom, 2.0)

        # Test zoom 100% (1:1) button
        palette.btn_zoom_100.click()
        self.assertEqual(canvas.zoom, 1.0)
        self.assertEqual(palette.slider_zoom.value(), 100)

        # Test fit to view
        canvas.fit_to_view()
        self.assertGreater(canvas.zoom, 0.0)

    def test_04_pan_and_scroll_in_palette(self):
        """4. Pan and scroll via mouse and keys adjusts pan_offset properly."""
        palette = TilesetPaletteWidget(self.asset_mgr)
        palette.set_active_asset(self.asset)
        canvas = palette.canvas

        initial_pan = QPointF(canvas.pan_offset)

        # Simulate wheel vertical scroll
        wheel_event = QWheelEvent(
            QPointF(50, 50),
            QPointF(50, 50),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        canvas.wheelEvent(wheel_event)
        self.assertEqual(canvas.pan_offset.y(), initial_pan.y() + 120)

        # Simulate shift + wheel horizontal scroll
        shift_wheel_event = QWheelEvent(
            QPointF(50, 50),
            QPointF(50, 50),
            QPoint(0, 0),
            QPoint(0, 80),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ShiftModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        canvas.wheelEvent(shift_wheel_event)
        self.assertEqual(canvas.pan_offset.x(), initial_pan.x() + 80)

    def test_05_single_tile_selection_updates_properties_panel(self):
        """5. Clicking LPM selects a single tile and updates PropertiesPanel."""
        win = MainWindow()
        asset, _, _ = win.asset_manager.import_single_file(
            "test_stage2_tmp/tileset_sample.png",
            target_category_path="Terrain",
            force_asset_type=AssetType.TILESET
        )
        asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        win.tileset_palette.set_active_asset(asset)

        # Select cell (2, 1)
        canvas = win.tileset_palette.canvas
        canvas.sel_start_col = 2
        canvas.sel_start_row = 1
        canvas.sel_end_col = 2
        canvas.sel_end_row = 1
        canvas._emit_selection()

        selected = win.asset_manager.selected_item
        self.assertIsInstance(selected, SelectedSubTile)
        self.assertEqual(selected.col, 2)
        self.assertEqual(selected.row, 1)
        self.assertEqual(selected.cols_count, 1)
        self.assertEqual(selected.rows_count, 1)
        self.assertEqual(selected.sub_x, 64)
        self.assertEqual(selected.sub_y, 32)
        self.assertEqual(selected.sub_w, 32)
        self.assertEqual(selected.sub_h, 32)

        # Check PropertiesPanel reflects this selection
        props = win.properties_panel
        self.assertEqual(props.lbl_sel_type.text(), "Pojedynczy kafelek tilesetu")
        self.assertIn("Komórka (2, 1)", props.lbl_sel_name.text())
        self.assertEqual(props.lbl_sel_pos.text(), "X: 64 px, Y: 32 px")
        self.assertEqual(props.lbl_sel_size.text(), "32 × 32 px")

    def test_06_multi_tile_brush_selection_updates_properties_panel(self):
        """6. Mouse drag multi-tile selection (e.g. 3x2) arms multi-tile brush and updates Properties."""
        win = MainWindow()
        asset, _, _ = win.asset_manager.import_single_file(
            "test_stage2_tmp/tileset_sample.png",
            target_category_path="Terrain",
            force_asset_type=AssetType.TILESET
        )
        asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        win.tileset_palette.set_active_asset(asset)

        # Select block (col 0..2, row 1..2) -> 3 cols x 2 rows
        canvas = win.tileset_palette.canvas
        canvas.sel_start_col = 0
        canvas.sel_start_row = 1
        canvas.sel_end_col = 2
        canvas.sel_end_row = 2
        canvas._emit_selection()

        selected = win.asset_manager.selected_item
        self.assertIsInstance(selected, SelectedSubTile)
        self.assertTrue(selected.is_multi_tile())
        self.assertEqual(selected.cols_count, 3)
        self.assertEqual(selected.rows_count, 2)
        self.assertEqual(selected.sub_w, 96)
        self.assertEqual(selected.sub_h, 64)

        # Check PropertiesPanel reflects multi-tile block
        props = win.properties_panel
        self.assertEqual(props.lbl_sel_type.text(), "Blok kafelków tilesetu")
        self.assertIn("3 × 2 kafelków", props.lbl_sel_name.text())
        self.assertEqual(props.lbl_sel_pos.text(), "X: 0 px, Y: 32 px")
        self.assertEqual(props.lbl_sel_size.text(), "96 × 64 px")


if __name__ == "__main__":
    unittest.main()
