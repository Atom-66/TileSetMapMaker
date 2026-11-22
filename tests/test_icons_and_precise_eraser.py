import os
import shutil
import unittest
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QImage, QMouseEvent
from PyQt6.QtCore import Qt, QPointF, QEvent

app = QApplication.instance() or QApplication(sys.argv)

from tileset_map_maker.models.project import Project
from tileset_map_maker.models.layer import Layer, MapItem, ItemType
from tileset_map_maker.models.asset import Asset
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.render_engine import RenderEngine
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.ui.icons import IconFactory
from tileset_map_maker.ui.map_canvas import MapCanvas
from sample_assets.generate_samples import create_sample_assets


class TestIconsAndPreciseEraser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = "test_icons_eraser_assets"
        cls.export_dir = "test_icons_eraser_exports"
        os.makedirs(cls.export_dir, exist_ok=True)
        create_sample_assets(cls.test_dir)

    @classmethod
    def tearDownClass(cls):
        for d in [cls.test_dir, cls.export_dir]:
            if os.path.exists(d):
                shutil.rmtree(d)

    def setUp(self):
        self.asset_mgr = AssetManager()
        self.asset_mgr.import_folder(self.test_dir)
        self.history_mgr = HistoryManager()
        self.project = Project(map_width=20, map_height=20, tile_size=32)
        self.render_engine = RenderEngine(self.asset_mgr)

    # 1. TEST ICON RENDERING AND FALLBACKS
    def test_all_tool_icons_render_properly(self):
        tool_names = [
            "brush", "eraser", "fill", "line", "rect", "select",
            "object", "eyedropper", "stamp", "new", "open", "save",
            "undo", "redo", "grid", "fit", "autotile", "save_stamp",
            "settings", "export", "shortcuts", "reset_ui", "non_existent_fallback"
        ]
        for name in tool_names:
            icon = IconFactory.get_icon(name, size=24)
            self.assertFalse(icon.isNull(), f"Icon '{name}' should not be null")
            pix = icon.pixmap(24, 24)
            self.assertFalse(pix.isNull(), f"Pixmap for icon '{name}' should not be null")
            self.assertEqual(pix.width(), 24)
            self.assertEqual(pix.height(), 24)

    # 2. TEST PRECISE GRID TILE ERASING (NO NEIGHBOR REMOVAL)
    def test_precise_grid_tile_erasing(self):
        layer = self.project.get_active_layer()
        grass = self.asset_mgr.search_assets("grass")[0]

        # Place a cross of 5 tiles centered at (5, 5)
        coords = [(5, 5), (5, 4), (5, 6), (4, 5), (6, 5)]
        for c, r in coords:
            layer.set_tile(c, r, MapItem(asset_id=grass.id, col=c, row=r))

        ctx = ToolContext(self.project, self.asset_mgr, self.history_mgr, layer, None)
        ctx.cursor_col = 5
        ctx.cursor_row = 5
        ctx.cursor_pixel_x = 5 * 32 + 16
        ctx.cursor_pixel_y = 5 * 32 + 16

        eraser = EraserTool()
        eraser.on_press(5, 5, ctx)
        eraser.on_release(5, 5, ctx)

        # Center tile (5, 5) must be removed
        self.assertIsNone(layer.get_tile(5, 5))

        # Surrounding 4 neighbor tiles MUST NOT be removed
        self.assertIsNotNone(layer.get_tile(5, 4), "North neighbor must remain")
        self.assertIsNotNone(layer.get_tile(5, 6), "South neighbor must remain")
        self.assertIsNotNone(layer.get_tile(4, 5), "West neighbor must remain")
        self.assertIsNotNone(layer.get_tile(6, 5), "East neighbor must remain")

    # 3. TEST ALPHA HIT-TESTING ON OBJECTS (LARGE PNG GRAPHICS)
    def test_alpha_hit_testing_on_single_png_objects(self):
        layer = self.project.get_active_layer()
        tree = self.asset_mgr.search_assets("tree")[0]

        # In generate_samples.py: tree is 64x96 px
        # Trunk is at x: [24, 39], y: [60, 95]
        # Top-left corner [0, 0] to [10, 10] is 100% transparent alpha 0!
        obj = MapItem(
            asset_id=tree.id,
            col=2,
            row=2,
            item_type=ItemType.OBJECT,
            free_x=64.0,
            free_y=64.0,
            dest_w=64,
            dest_h=96,
        )
        layer.add_object(obj)

        ctx = ToolContext(self.project, self.asset_mgr, self.history_mgr, layer, None)
        eraser = EraserTool()

        # Click 1: Transparent top-left corner of the tree at (66.0, 66.0) (local 2, 2)
        ctx.cursor_pixel_x = 66.0
        ctx.cursor_pixel_y = 66.0
        ctx.cursor_col = int(66.0 // 32)
        ctx.cursor_row = int(66.0 // 32)

        eraser.on_press(ctx.cursor_col, ctx.cursor_row, ctx)
        eraser.on_release(ctx.cursor_col, ctx.cursor_row, ctx)

        # Object should NOT be erased because pixel is completely transparent!
        self.assertIn(obj, layer.objects, "Transparent pixel click must NOT delete object")

        # Click 2: Center of foliage at (96.0, 96.0) (local 32, 32) which is solid green
        ctx.cursor_pixel_x = 96.0
        ctx.cursor_pixel_y = 96.0
        ctx.cursor_col = int(96.0 // 32)
        ctx.cursor_row = int(96.0 // 32)

        eraser.on_press(ctx.cursor_col, ctx.cursor_row, ctx)
        eraser.on_release(ctx.cursor_col, ctx.cursor_row, ctx)

        # Object must now be erased!
        self.assertNotIn(obj, layer.objects, "Opaque pixel click must delete object")

    # 4. TEST OVERLAPPING OBJECTS: DELETES ONLY TOPMOST OBJECT
    def test_overlapping_objects_erases_only_topmost(self):
        layer = self.project.get_active_layer()
        tree = self.asset_mgr.search_assets("tree")[0]

        # Bottom tree
        obj_bottom = MapItem(
            asset_id=tree.id,
            col=0,
            row=0,
            item_type=ItemType.OBJECT,
            free_x=0.0,
            free_y=0.0,
            dest_w=64,
            dest_h=96,
        )
        # Top tree right above it
        obj_top = MapItem(
            asset_id=tree.id,
            col=0,
            row=0,
            item_type=ItemType.OBJECT,
            free_x=0.0,
            free_y=0.0,
            dest_w=64,
            dest_h=96,
        )
        layer.add_object(obj_bottom)
        layer.add_object(obj_top)

        ctx = ToolContext(self.project, self.asset_mgr, self.history_mgr, layer, None)
        ctx.cursor_pixel_x = 32.0
        ctx.cursor_pixel_y = 32.0
        ctx.cursor_col = 1
        ctx.cursor_row = 1

        eraser = EraserTool()
        eraser.on_press(1, 1, ctx)
        eraser.on_release(1, 1, ctx)

        # Top tree removed, bottom tree MUST still be present!
        self.assertNotIn(obj_top, layer.objects)
        self.assertIn(obj_bottom, layer.objects, "Bottom object must remain when top object is erased")

    # 5. TEST LAYER ISOLATION
    def test_eraser_respects_active_layer(self):
        # Two layers: Background and Foreground
        bg_layer = self.project.layers[0]
        fg_layer = self.project.add_layer("FG Layer")

        grass = self.asset_mgr.search_assets("grass")[0]
        bg_layer.set_tile(3, 3, MapItem(asset_id=grass.id, col=3, row=3))

        # Active layer is Foreground (which has no tile at 3,3)
        self.project.set_active_layer(fg_layer.id)
        ctx = ToolContext(self.project, self.asset_mgr, self.history_mgr, fg_layer, None)
        ctx.cursor_col = 3
        ctx.cursor_row = 3
        ctx.cursor_pixel_x = 3 * 32 + 16
        ctx.cursor_pixel_y = 3 * 32 + 16

        eraser = EraserTool()
        eraser.on_press(3, 3, ctx)
        eraser.on_release(3, 3, ctx)

        # Tile on Background layer MUST NOT be erased
        self.assertIsNotNone(bg_layer.get_tile(3, 3), "Inactive layer must not be modified by eraser")

    # 6. TEST RIGHT-CLICK TEMPORARY ERASER ON MAP CANVAS
    def test_canvas_right_click_temporary_eraser(self):
        canvas = MapCanvas(
            project=self.project,
            render_engine=self.render_engine,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
        )
        brush = BrushTool()
        canvas.set_tool(brush)
        self.assertEqual(canvas.active_tool, brush)

        # Place a tile at (2, 2)
        layer = self.project.get_active_layer()
        grass = self.asset_mgr.search_assets("grass")[0]
        layer.set_tile(2, 2, MapItem(asset_id=grass.id, col=2, row=2))
        self.assertIsNotNone(layer.get_tile(2, 2))

        # Calculate screen coordinates for tile (2, 2)
        world_pt = QPointF(2 * 32 + 16, 2 * 32 + 16)
        screen_pt = world_pt * canvas.zoom + canvas.pan_offset

        # Simulate Right Mouse Press at tile (2, 2)
        press_event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            screen_pt,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        canvas.mousePressEvent(press_event)

        # Eraser is active right now
        self.assertTrue(canvas.is_right_erasing)

        # Tile at (2, 2) is deleted
        self.assertIsNone(layer.get_tile(2, 2))

        # Simulate Right Mouse Release
        release_event = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            screen_pt,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        canvas.mouseReleaseEvent(release_event)

        # Right erasing is finished, and active tool is STILL BRUSH!
        self.assertFalse(canvas.is_right_erasing)
        self.assertEqual(canvas.active_tool, brush, "Active tool must be restored to Brush after right click release")


if __name__ == "__main__":
    unittest.main()
