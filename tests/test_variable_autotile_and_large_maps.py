import os
import tempfile
import unittest

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.models.asset import AssetType, SelectedSubTile, TilesetConfig
from tileset_map_maker.core.rpg_autotile import RPGAutotile, SelectedAutotile
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.models.layer import MapItem
from tileset_map_maker.models.project import Project
from tileset_map_maker.ui.dialogs.map_settings_dialog import MapSettingsDialog
from tileset_map_maker.ui.map_canvas import MapCanvas

APP = QApplication.instance() or QApplication([])


class LargeMapsTests(unittest.TestCase):
    def test_large_maps_io_dimensions_and_canvas(self):
        for width, height in ((501, 20), (20, 501), (601, 701), (2101, 503)):
            with self.subTest(width=width, height=height), tempfile.TemporaryDirectory() as directory:
                project = Project(map_width=width, map_height=height)
                assets = AssetManager()
                sheet = QImage(16, 16, QImage.Format.Format_ARGB32)
                sheet.fill(0xffff0000)
                sheet_path = os.path.join(directory, "sheet.png")
                self.assertTrue(sheet.save(sheet_path))
                asset, _, _ = assets.import_single_file(sheet_path, force_asset_type=AssetType.TILESET)
                engine = AutoTileEngine()
                autotile = RPGAutotile(id="test_at", name="Test AT", tileset_id=asset.id, tile_size=16)
                engine.register_rpg_autotile(autotile)
                layer = project.get_active_layer()
                layer.set_tile(width - 1, height - 1, MapItem(asset.id, width - 1, height - 1,
                                                             source_x=0, source_y=0, source_w=16, source_h=16,
                                                             terrain_type="Test AT", is_auto_tiled=True))
                path = os.path.join(directory, "map.tmmap")
                self.assertTrue(ProjectIO.save_project(project, assets, path, engine))
                restored_engine = AutoTileEngine()
                restored = ProjectIO.load_project(path, AssetManager(), restored_engine)
                self.assertEqual((restored.map_width, restored.map_height), (width, height))
                self.assertIsNotNone(restored.get_active_layer().get_tile(width - 1, height - 1))
                settings = MapSettingsDialog(project)
                self.assertEqual((settings.spin_width.value(), settings.spin_height.value()), (width, height))
                self.assertGreater(settings.spin_width.maximum(), 2000)
                self.assertGreater(settings.spin_height.maximum(), 2000)
                canvas = MapCanvas(project, RenderEngine(assets), assets, HistoryManager())
                canvas.resize(400, 300)
                canvas.show_grid = False
                canvas.show_hud = False
                canvas.pan_to_tile(width - 1, height - 1)
                self.assertEqual(canvas.screen_to_tile(QPointF(canvas.rect().center())),
                                 (width - 1, height - 1))
                image = QImage(400, 300, QImage.Format.Format_ARGB32)
                painter = QPainter(image)
                canvas.render(painter)
                painter.end()
                self.assertEqual(image.pixelColor(200, 150).red(), 255)

    def test_brush_and_eraser_on_large_map(self):
        project = Project(map_width=1200, map_height=900)
        layer = project.get_active_layer()
        engine = AutoTileEngine()
        autotile = RPGAutotile(id="test_at", name="Test AT", tileset_id="sheet", tile_size=16)
        engine.register_rpg_autotile(autotile)
        history = HistoryManager()
        settings = BrushSettings()
        settings.selected_autotile = SelectedAutotile(autotile)
        context = ToolContext(project=project, active_layer=layer,
                              asset_manager=AssetManager(), history_manager=history,
                              brush_settings=settings, autotile_engine=engine)
        brush = BrushTool()
        brush.on_press(1198, 899, context)
        brush.on_drag(1199, 899, context)
        brush.on_release(1199, 899, context)
        self.assertIsNotNone(layer.get_tile(1198, 899))
        self.assertIsNotNone(layer.get_tile(1199, 899))
        self.assertTrue(history.undo())
        self.assertIsNone(layer.get_tile(1198, 899))
        self.assertTrue(history.redo())
        eraser = EraserTool()
        eraser.on_press(1199, 899, context)
        eraser.on_release(1199, 899, context)
        self.assertIsNone(layer.get_tile(1199, 899))
        self.assertTrue(history.undo())
        self.assertIsNotNone(layer.get_tile(1199, 899))

    def test_extremely_large_viewport_uses_clipped_background(self):
        project = Project(map_width=100_000_000, map_height=100_000_000)
        project.is_bg_transparent = True
        image = QImage(100, 100, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        painter.translate(-3_000_000_000, -3_000_000_000)
        RenderEngine(AssetManager()).render(
            painter, project, RenderOptions(),
            QRectF(3_000_000_000, 3_000_000_000, 100, 100),
        )
        painter.end()
        self.assertEqual(image.pixelColor(50, 50).alpha(), 255)


if __name__ == "__main__":
    unittest.main()
