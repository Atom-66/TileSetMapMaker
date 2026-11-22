import os
import shutil
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtCore import QRect
import sys

app = QApplication.instance() or QApplication(sys.argv)

from tileset_map_maker.models.project import Project
from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.tools import (
    ToolContext,
    BrushTool,
    EraserTool,
    FillTool,
    LineTool,
    RectTool,
    SelectTool,
    StampTool,
    EyedropperTool,
)
from tileset_map_maker.core.project_io import ProjectIO
from sample_assets.generate_samples import create_sample_assets


class TestToolsRenderAndExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = "test_assets_render"
        cls.export_dir = "test_exports"
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
        self.project = Project(map_width=10, map_height=10, tile_size=32)
        self.render_engine = RenderEngine(self.asset_mgr)

    def test_brush_tool_and_undo_redo(self):
        # Pick grass asset
        grass = self.asset_mgr.search_assets("grass_01")[0]
        self.asset_mgr.select_asset(grass)

        ctx = ToolContext(
            self.project,
            self.asset_mgr,
            self.history_mgr,
            self.project.get_active_layer(),
            self.asset_mgr.selected_item,
        )

        brush = BrushTool()
        brush.on_press(2, 3, ctx)
        brush.on_drag(2, 4, ctx)
        brush.on_release(2, 4, ctx)

        layer = self.project.get_active_layer()
        self.assertIsNotNone(layer.get_tile(2, 3))
        self.assertIsNotNone(layer.get_tile(2, 4))
        self.assertEqual(layer.get_tile(2, 3).asset_id, grass.id)

        # Test Undo
        self.assertTrue(self.history_mgr.can_undo())
        self.history_mgr.undo()
        self.assertIsNone(layer.get_tile(2, 3))
        self.assertIsNone(layer.get_tile(2, 4))

        # Test Redo
        self.assertTrue(self.history_mgr.can_redo())
        self.history_mgr.redo()
        self.assertIsNotNone(layer.get_tile(2, 3))
        self.assertIsNotNone(layer.get_tile(2, 4))

    def test_eraser_tool(self):
        grass = self.asset_mgr.search_assets("grass_01")[0]
        self.asset_mgr.select_asset(grass)
        ctx = ToolContext(
            self.project,
            self.asset_mgr,
            self.history_mgr,
            self.project.get_active_layer(),
            self.asset_mgr.selected_item,
        )

        brush = BrushTool()
        brush.on_press(1, 1, ctx)
        brush.on_release(1, 1, ctx)
        self.assertIsNotNone(ctx.active_layer.get_tile(1, 1))

        eraser = EraserTool()
        eraser.on_press(1, 1, ctx)
        eraser.on_release(1, 1, ctx)
        self.assertIsNone(ctx.active_layer.get_tile(1, 1))

        # Undo eraser
        self.history_mgr.undo()
        self.assertIsNotNone(ctx.active_layer.get_tile(1, 1))

    def test_fill_tool(self):
        water = self.asset_mgr.search_assets("water")[0]
        self.asset_mgr.select_asset(water)
        ctx = ToolContext(
            self.project,
            self.asset_mgr,
            self.history_mgr,
            self.project.get_active_layer(),
            self.asset_mgr.selected_item,
        )

        fill = FillTool()
        fill.on_press(0, 0, ctx)

        # Whole 10x10 layer should be filled with water
        layer = self.project.get_active_layer()
        self.assertEqual(len(layer.tiles), 100)
        self.assertEqual(layer.get_tile(5, 5).asset_id, water.id)

    def test_line_and_rect_tools(self):
        grass = self.asset_mgr.search_assets("grass_01")[0]
        self.asset_mgr.select_asset(grass)
        ctx = ToolContext(
            self.project,
            self.asset_mgr,
            self.history_mgr,
            self.project.get_active_layer(),
            self.asset_mgr.selected_item,
        )

        line = LineTool()
        line.on_press(0, 0, ctx)
        line.on_drag(5, 0, ctx)
        line.on_release(5, 0, ctx)

        layer = self.project.get_active_layer()
        for c in range(6):
            self.assertIsNotNone(layer.get_tile(c, 0))

        rect = RectTool(filled=True)
        rect.on_press(2, 2, ctx)
        rect.on_drag(4, 4, ctx)
        rect.on_release(4, 4, ctx)

        for r in range(2, 5):
            for c in range(2, 5):
                self.assertIsNotNone(layer.get_tile(c, r))

    def test_eyedropper_and_selection_copy_paste(self):
        grass = self.asset_mgr.search_assets("grass_01")[0]
        self.asset_mgr.select_asset(grass)
        ctx = ToolContext(
            self.project,
            self.asset_mgr,
            self.history_mgr,
            self.project.get_active_layer(),
            self.asset_mgr.selected_item,
        )
        BrushTool().on_press(3, 3, ctx)
        BrushTool().on_release(3, 3, ctx)

        # Clear selection, use Eyedropper at (3, 3)
        self.asset_mgr.select_asset(None)
        self.assertIsNone(self.asset_mgr.selected_item)

        eyedropper = EyedropperTool()
        eyedropper.on_press(3, 3, ctx)
        self.assertIsNotNone(self.asset_mgr.selected_item)
        self.assertEqual(self.asset_mgr.selected_item.id, grass.id)

        # Select & copy
        select_tool = SelectTool()
        select_tool.on_press(3, 3, ctx)
        select_tool.on_release(3, 3, ctx)
        select_tool.copy_selection(ctx)
        self.assertIn((0, 0), ctx.clipboard_tiles)

        # Stamp pasted tile at (7, 7)
        stamp_tool = StampTool()
        stamp_tool.on_press(7, 7, ctx)
        self.assertIsNotNone(ctx.active_layer.get_tile(7, 7))

    def test_save_and_load_project(self):
        grass = self.asset_mgr.search_assets("grass_01")[0]
        self.asset_mgr.select_asset(grass)
        ctx = ToolContext(
            self.project,
            self.asset_mgr,
            self.history_mgr,
            self.project.get_active_layer(),
            self.asset_mgr.selected_item,
        )
        BrushTool().on_press(1, 1, ctx)
        BrushTool().on_release(1, 1, ctx)

        file_path = os.path.join(self.export_dir, "test_proj.tmmap")
        saved = ProjectIO.save_project(self.project, self.asset_mgr, file_path)
        self.assertTrue(saved)
        self.assertTrue(os.path.exists(file_path))

        # Fresh manager and project
        fresh_mgr = AssetManager()
        loaded_project = ProjectIO.load_project(file_path, fresh_mgr)
        self.assertIsNotNone(loaded_project)
        self.assertEqual(loaded_project.map_width, 10)
        self.assertEqual(loaded_project.map_height, 10)
        loaded_layer = loaded_project.get_layer(self.project.get_active_layer().id)
        self.assertIsNotNone(loaded_layer)
        self.assertIsNotNone(loaded_layer.get_tile(1, 1))

    def test_export_png_options(self):
        grass = self.asset_mgr.search_assets("grass_01")[0]
        self.asset_mgr.select_asset(grass)
        ctx = ToolContext(
            self.project,
            self.asset_mgr,
            self.history_mgr,
            self.project.get_active_layer(),
            self.asset_mgr.selected_item,
        )
        BrushTool().on_press(0, 0, ctx)
        BrushTool().on_release(0, 0, ctx)

        out_full = os.path.join(self.export_dir, "export_full.png")
        exported = ProjectIO.export_png(
            self.project,
            self.render_engine,
            out_full,
            transparent_bg=True,
        )
        self.assertTrue(exported)
        self.assertTrue(os.path.exists(out_full))
        
        # Verify image size (10 * 32 = 320x320)
        img = QImage(out_full)
        self.assertEqual(img.width(), 320)
        self.assertEqual(img.height(), 320)

        # Test crop to content
        out_crop = os.path.join(self.export_dir, "export_crop.png")
        exported_crop = ProjectIO.export_png(
            self.project,
            self.render_engine,
            out_crop,
            transparent_bg=True,
            crop_to_content=True,
        )
        self.assertTrue(exported_crop)
        img_crop = QImage(out_crop)
        self.assertEqual(img_crop.width(), 32)
        self.assertEqual(img_crop.height(), 32)


if __name__ == "__main__":
    unittest.main()
