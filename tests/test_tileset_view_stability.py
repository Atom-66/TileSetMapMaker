import os
import shutil
import tempfile
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF, QPoint
from PyQt6.QtGui import QMouseEvent, QWheelEvent
from PIL import Image

from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.models.project import Project
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.ui.tileset_palette_widget import TilesetPaletteWidget, TilesetCanvas
from tileset_map_maker.ui.main_window import MainWindow

app = QApplication.instance()
if not app:
    app = QApplication([])


class TestTilesetViewStability(unittest.TestCase):
    """
    Comprehensive verification tests ensuring tileset preview zoom and pan positions
    are never reset when selecting single or multiple tiles, switching tools, or resizing.
    """

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="tileset_view_test_")
        cls.sample1_path = os.path.join(cls.test_dir, "sheet_a.png")
        cls.sample2_path = os.path.join(cls.test_dir, "sheet_b.png")

        # Create two test images (128x128 px: 4x4 tiles of 32x32)
        im1 = Image.new("RGBA", (128, 128), (60, 120, 60, 255))
        im1.save(cls.sample1_path)

        im2 = Image.new("RGBA", (128, 128), (120, 60, 60, 255))
        im2.save(cls.sample2_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        self.asset_mgr = AssetManager()
        self.asset_a, _, _ = self.asset_mgr.import_single_file(self.sample1_path, force_asset_type=AssetType.TILESET)
        self.asset_b, _, _ = self.asset_mgr.import_single_file(self.sample2_path, force_asset_type=AssetType.TILESET)
        self.asset_a.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.asset_b.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

        self.palette = TilesetPaletteWidget(self.asset_mgr)
        self.palette.resize(400, 300)
        self.palette.canvas.resize(400, 250)
        self.palette.set_active_asset(self.asset_a)

    def tearDown(self):
        self.palette.close()
        self.palette.deleteLater()

    def test_01_single_tile_selection_preserves_zoom_and_pan(self):
        """1. Zooming to 150% and clicking single tiles maintains exact zoom and pan."""
        canvas = self.palette.canvas
        canvas.set_zoom(1.5)
        canvas.pan_offset = QPointF(50.0, 75.0)
        canvas.save_current_view_state()

        self.assertEqual(canvas.zoom, 1.5)
        self.assertEqual(canvas.pan_offset, QPointF(50.0, 75.0))

        # Click tile at (1, 1): world coordinates for cell (1, 1) in 32x32 is (32..64, 32..64)
        # Screen position = pan_offset + world * zoom
        screen_x = canvas.pan_offset.x() + (32 + 16) * canvas.zoom
        screen_y = canvas.pan_offset.y() + (32 + 16) * canvas.zoom
        click_pos = QPointF(screen_x, screen_y)

        # Simulate left click
        press_ev = QMouseEvent(QMouseEvent.Type.MouseButtonPress, click_pos, click_pos, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        canvas.mousePressEvent(press_ev)

        release_ev = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, click_pos, click_pos, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        canvas.mouseReleaseEvent(release_ev)

        self.assertEqual(canvas.sel_start_col, 1)
        self.assertEqual(canvas.sel_start_row, 1)
        self.assertEqual(canvas.zoom, 1.5, "Zoom must remain 1.5 after tile selection!")
        self.assertEqual(canvas.pan_offset, QPointF(50.0, 75.0), "Pan offset must remain intact!")

        # Click another tile at (2, 3)
        screen_x2 = canvas.pan_offset.x() + (64 + 16) * canvas.zoom
        screen_y2 = canvas.pan_offset.y() + (96 + 16) * canvas.zoom
        click_pos2 = QPointF(screen_x2, screen_y2)

        press_ev2 = QMouseEvent(QMouseEvent.Type.MouseButtonPress, click_pos2, click_pos2, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        canvas.mousePressEvent(press_ev2)
        release_ev2 = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, click_pos2, click_pos2, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        canvas.mouseReleaseEvent(release_ev2)

        self.assertEqual(canvas.sel_start_col, 2)
        self.assertEqual(canvas.sel_start_row, 3)
        self.assertEqual(canvas.zoom, 1.5, "Zoom must stay 1.5 on second selection!")
        self.assertEqual(canvas.pan_offset, QPointF(50.0, 75.0), "Pan offset must stay intact!")

    def test_02_multi_tile_selection_preserves_zoom_and_pan(self):
        """2. Zooming to 200% and selecting multi-tile rectangular blocks preserves zoom and pan."""
        canvas = self.palette.canvas
        canvas.set_zoom(2.0)
        canvas.pan_offset = QPointF(100.0, -20.0)
        canvas.save_current_view_state()

        # Drag selection from (0, 0) to (1, 2)
        start_x = canvas.pan_offset.x() + 16 * canvas.zoom
        start_y = canvas.pan_offset.y() + 16 * canvas.zoom
        end_x = canvas.pan_offset.x() + (32 + 16) * canvas.zoom
        end_y = canvas.pan_offset.y() + (64 + 16) * canvas.zoom

        press_ev = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(start_x, start_y), QPointF(start_x, start_y), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        canvas.mousePressEvent(press_ev)

        move_ev = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(end_x, end_y), QPointF(end_x, end_y), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        canvas.mouseMoveEvent(move_ev)

        release_ev = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(end_x, end_y), QPointF(end_x, end_y), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        canvas.mouseReleaseEvent(release_ev)

        self.assertEqual((canvas.sel_start_col, canvas.sel_start_row), (0, 0))
        self.assertEqual((canvas.sel_end_col, canvas.sel_end_row), (1, 2))
        self.assertEqual(canvas.zoom, 2.0, "Zoom must remain 2.0 after multi-tile selection!")
        self.assertEqual(canvas.pan_offset, QPointF(100.0, -20.0), "Pan offset must remain intact!")

    def test_03_repeated_selection_and_panning(self):
        """3. Pan sheet with middle-drag, then select multiple tiles repeatedly."""
        canvas = self.palette.canvas
        canvas.set_zoom(1.8)
        canvas.pan_offset = QPointF(30.0, 40.0)

        # Pan by (20, 30) via mouse panning
        canvas.is_panning = True
        canvas.last_mouse_pos = QPointF(100, 100)
        move_ev = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(120, 130), QPointF(120, 130), Qt.MouseButton.NoButton, Qt.MouseButton.MiddleButton, Qt.KeyboardModifier.NoModifier)
        canvas.mouseMoveEvent(move_ev)
        release_ev = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(120, 130), QPointF(120, 130), Qt.MouseButton.MiddleButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        canvas.mouseReleaseEvent(release_ev)

        panned_pos = QPointF(canvas.pan_offset)
        self.assertEqual(panned_pos, QPointF(50.0, 70.0))

        # Repeatedly select various cells
        for c, r in [(0, 0), (1, 1), (2, 2), (3, 3), (1, 0)]:
            canvas.sel_start_col = c
            canvas.sel_start_row = r
            canvas.sel_end_col = c
            canvas.sel_end_row = r
            canvas._emit_selection()

            self.assertEqual(canvas.zoom, 1.8, f"Zoom changed during cell ({c},{r}) selection!")
            self.assertEqual(canvas.pan_offset, panned_pos, f"Pan reset during cell ({c},{r}) selection!")

    def test_04_per_tileset_view_state_persistence_and_restoration(self):
        """4. Switching between tilesets preserves independent zoom and pan for each tileset."""
        canvas = self.palette.canvas

        # Configure Tileset A
        self.palette.set_active_asset(self.asset_a)
        canvas.set_zoom(2.5)
        canvas.pan_offset = QPointF(80.0, 90.0)
        canvas.sel_start_col, canvas.sel_start_row = 1, 2
        canvas.save_current_view_state()

        # Switch to Tileset B
        self.palette.set_active_asset(self.asset_b)
        self.assertEqual(self.palette.active_asset_id, self.asset_b.id)
        canvas.set_zoom(3.2)
        canvas.pan_offset = QPointF(-40.0, 60.0)
        canvas.sel_start_col, canvas.sel_start_row = 3, 1
        canvas.save_current_view_state()

        # Switch back to Tileset A -> must restore zoom 2.5 and pan (80, 90)
        self.palette.set_active_asset(self.asset_a)
        self.assertEqual(self.palette.active_asset_id, self.asset_a.id)
        self.assertEqual(canvas.zoom, 2.5, "Tileset A zoom must be restored to 2.5!")
        self.assertEqual(canvas.pan_offset, QPointF(80.0, 90.0), "Tileset A pan must be restored!")
        self.assertEqual((canvas.sel_start_col, canvas.sel_start_row), (1, 2))

        # Switch back to Tileset B -> must restore zoom 3.2 and pan (-40, 60)
        self.palette.set_active_asset(self.asset_b)
        self.assertEqual(self.palette.active_asset_id, self.asset_b.id)
        self.assertEqual(canvas.zoom, 3.2, "Tileset B zoom must be restored to 3.2!")
        self.assertEqual(canvas.pan_offset, QPointF(-40.0, 60.0), "Tileset B pan must be restored!")
        self.assertEqual((canvas.sel_start_col, canvas.sel_start_row), (3, 1))

    def test_05_manual_fit_to_view_button_is_the_only_auto_fit(self):
        """5. Manual fit button calculates fit, and subsequent selections do NOT re-fit."""
        canvas = self.palette.canvas
        canvas.set_zoom(3.5)
        canvas.pan_offset = QPointF(200.0, 200.0)

        # Click the fit button
        self.palette.btn_fit.click()

        fitted_zoom = canvas.zoom
        fitted_pan = QPointF(canvas.pan_offset)
        self.assertNotEqual(fitted_zoom, 3.5, "Fit button should have adapted the zoom!")

        # Now select a tile
        canvas.sel_start_col, canvas.sel_start_row = 0, 1
        canvas._emit_selection()

        self.assertEqual(canvas.zoom, fitted_zoom, "Tile selection must NOT alter fitted zoom!")
        self.assertEqual(canvas.pan_offset, fitted_pan, "Tile selection must NOT alter fitted pan!")

    def test_06_resizing_panel_does_not_reset_zoom_or_pan(self):
        """6. Resizing the preview dock or canvas does not reset zoom or pan."""
        canvas = self.palette.canvas
        canvas.set_zoom(2.2)
        canvas.pan_offset = QPointF(65.0, 45.0)
        canvas.save_current_view_state()

        # Resize widget
        self.palette.resize(600, 500)
        canvas.resize(600, 450)

        self.assertEqual(canvas.zoom, 2.2, "Zoom must remain 2.2 after window resize!")
        self.assertEqual(canvas.pan_offset, QPointF(65.0, 45.0), "Pan must remain intact after resize!")

        # Select tile
        canvas.sel_start_col, canvas.sel_start_row = 2, 2
        canvas._emit_selection()

        self.assertEqual(canvas.zoom, 2.2)
        self.assertEqual(canvas.pan_offset, QPointF(65.0, 45.0))

    def test_07_main_window_selection_event_does_not_reset_view(self):
        """7. Full integration with MainWindow: asset_selected signal does not reset palette zoom/pan."""
        win = MainWindow()
        win.resize(1000, 700)
        # Import test asset into window's asset manager
        asset, _, _ = win.asset_manager.import_single_file(self.sample1_path, force_asset_type=AssetType.TILESET)
        asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

        win.tileset_palette.set_active_asset(asset)
        canvas = win.tileset_palette.canvas
        canvas.set_zoom(2.4)
        canvas.pan_offset = QPointF(77.0, 88.0)
        canvas.save_current_view_state()

        # Emit sub_tile selection as happens when clicking in canvas or map eyedropper
        sub = SelectedSubTile(
            asset_id=asset.id,
            col=2,
            row=1,
            cols_count=1,
            rows_count=1,
            sub_x=64,
            sub_y=32,
            sub_w=32,
            sub_h=32,
            tile_width=32,
            tile_height=32,
            spacing_x=0,
            spacing_y=0,
            asset_name=asset.name,
        )
        win.asset_manager.select_asset(asset, sub)

        self.assertEqual(canvas.zoom, 2.4, "MainWindow selection event must NOT reset zoom!")
        self.assertEqual(canvas.pan_offset, QPointF(77.0, 88.0), "MainWindow selection event must NOT reset pan!")
        self.assertEqual((canvas.sel_start_col, canvas.sel_start_row), (2, 1))

        # Switch tools in main window toolbox
        win.tool_panel.select_tool_by_key("eraser")
        win.tool_panel.select_tool_by_key("bucket")
        win.tool_panel.select_tool_by_key("brush")

        self.assertEqual(canvas.zoom, 2.4, "Tool switching must NOT alter tileset zoom!")
        self.assertEqual(canvas.pan_offset, QPointF(77.0, 88.0), "Tool switching must NOT alter tileset pan!")

        win.close()
        win.deleteLater()


if __name__ == "__main__":
    unittest.main()
