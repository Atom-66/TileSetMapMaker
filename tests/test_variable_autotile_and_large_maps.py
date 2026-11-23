import os
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication, QMessageBox

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.history import HistoryManager, MapTileBatchesCommand, TileBatchCommand
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.models.asset import AssetType, SelectedSubTile, TilesetConfig
from tileset_map_maker.models.autotile import AutoTileRuleSet, MASK_CENTER
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.models.layer import MapItem
from tileset_map_maker.models.project import Project
from tileset_map_maker.ui.dialogs.autotile_dialog import AutoTileDialog
from tileset_map_maker.ui.dialogs.map_settings_dialog import MapSettingsDialog
from tileset_map_maker.ui.map_canvas import MapCanvas


APP = QApplication.instance() or QApplication([])


def pattern(width, height):
    rule = AutoTileRuleSet(terrain_type="Grass")
    rule.resize_pattern(width, height)
    for y in range(height):
        for x in range(width):
            rule.set_pattern_tile(x, y, ("sheet", x, y, 1, 1))
    return rule


class VariableAutoTileTests(unittest.TestCase):
    def test_sizes_and_edges(self):
        for width, height in ((1, 1), (2, 2), (2, 5), (3, 3), (4, 4),
                              (5, 5), (8, 8), (10, 10), (7, 3)):
            with self.subTest(width=width, height=height):
                rule = pattern(width, height)
                project = Project(map_width=20, map_height=20)
                layer = project.get_active_layer()
                engine = AutoTileEngine()
                coords = [(x, y) for y in range(12) for x in range(12)]
                for x, y in coords:
                    layer.set_tile(x, y, MapItem("old", x, y, terrain_type="Grass", is_auto_tiled=True))
                engine.apply_autotile_stroke(layer, coords, rule, project)
                self.assertEqual((layer.get_tile(0, 0).source_x, layer.get_tile(0, 0).source_y), (0, 0))
                self.assertEqual((layer.get_tile(11, 11).source_x, layer.get_tile(11, 11).source_y),
                                 (width - 1, height - 1))
                used = {(layer.get_tile(x, y).source_x, layer.get_tile(x, y).source_y)
                        for x, y in coords}
                self.assertEqual(len(used), width * height)

    def test_resize_serialization_and_legacy_rules(self):
        rule = pattern(5, 5)
        rule.resize_pattern(2, 5)
        self.assertEqual(len(rule.pattern_tiles), 10)
        self.assertEqual(rule.pattern_tiles[(1, 4)], ("sheet", 1, 4, 1, 1))
        rule.resize_pattern(7, 6)
        self.assertEqual(len(rule.pattern_tiles), 10)
        restored = AutoTileRuleSet.from_dict(rule.to_dict())
        self.assertEqual(restored.pattern_tiles, rule.pattern_tiles)
        legacy = AutoTileRuleSet()
        legacy.setup_standard_3x3_box("sheet", 0, 0, 16, 16)
        data = legacy.to_dict()
        for key in ("pattern_width", "pattern_height", "pattern_enabled", "pattern_tiles"):
            del data[key]
        loaded = AutoTileRuleSet.from_dict(data)
        self.assertFalse(loaded.pattern_enabled)
        self.assertEqual(loaded.get_tile_for_mask(MASK_CENTER), ("sheet", 16, 16, 16, 16))

    def test_pattern_keeps_weighted_mask_variants(self):
        rule = pattern(5, 5)
        rule.seed = 123
        variant = ("variant", 0, 0, 1, 1)
        rule.add_mapping_variant(MASK_CENTER, variant, 1000)
        self.assertEqual(rule.get_pattern_tile(MASK_CENTER, 4, 4), variant)
        restored = AutoTileRuleSet.from_dict(rule.to_dict())
        self.assertEqual(restored.get_pattern_tile(MASK_CENTER, 4, 4), variant)

    def test_undo_redo_and_independent_layers(self):
        project = Project(map_width=600, map_height=700)
        layer = project.get_active_layer()
        other = project.add_layer("other")
        engine = AutoTileEngine()
        rule = pattern(4, 4)
        layer.set_tile(599, 699, MapItem("old", 599, 699, terrain_type="Grass", is_auto_tiled=True))
        other.set_tile(599, 699, MapItem("other", 599, 699, terrain_type="Grass", is_auto_tiled=True))
        changes = engine.apply_autotile_stroke(layer, [(599, 699)], rule, project)
        history = HistoryManager()
        history.push(TileBatchCommand(project, layer.id, changes, "autotile"))
        self.assertEqual(other.get_tile(599, 699).asset_id, "other")
        self.assertTrue(history.undo())
        self.assertEqual(layer.get_tile(599, 699).asset_id, "old")
        self.assertTrue(history.redo())
        self.assertEqual(layer.get_tile(599, 699).asset_id, "sheet")

    def test_recalculate_map_batches_undo_across_layers(self):
        project = Project(map_width=20, map_height=20)
        first = project.get_active_layer()
        second = project.add_layer("other")
        for layer in (first, second):
            layer.set_tile(1, 1, MapItem("old", 1, 1, terrain_type="Grass", is_auto_tiled=True))
        engine = AutoTileEngine()
        engine.register_ruleset(pattern(5, 5))
        changes = engine.recalculate_project(project)
        grouped = {key.split(":", 1)[1]: value for key, value in changes.items()}
        history = HistoryManager()
        history.push(MapTileBatchesCommand(project, project.active_map_id, grouped))
        self.assertTrue(history.undo())
        self.assertEqual(first.get_tile(1, 1).asset_id, "old")
        self.assertEqual(second.get_tile(1, 1).asset_id, "old")
        self.assertTrue(history.redo())
        self.assertEqual(first.get_tile(1, 1).asset_id, "sheet")
        self.assertEqual(second.get_tile(1, 1).asset_id, "sheet")

    def test_palette_selection_and_individual_assignment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "sheet.png")
            image = QImage(160, 160, QImage.Format.Format_ARGB32)
            image.fill(0xffffffff)
            self.assertTrue(image.save(path))
            assets = AssetManager()
            asset, _, _ = assets.import_single_file(path, force_asset_type=AssetType.TILESET)
            asset.tileset_config = TilesetConfig(tile_width=16, tile_height=16)
            assets.selected_item = SelectedSubTile(asset.id, col=1, row=2, cols_count=2, rows_count=5,
                                                   sub_x=16, sub_y=32, tile_width=16, tile_height=16)
            engine = AutoTileEngine()
            dialog = AutoTileDialog(engine, assets)
            self.assertGreater(dialog.spin_col.maximum(), 500)
            self.assertGreater(dialog.spin_row.maximum(), 500)
            dialog._use_palette_selection()
            self.assertEqual((dialog.spin_pattern_width.value(), dialog.spin_pattern_height.value()), (2, 5))
            with patch.object(QMessageBox, "information"), patch(
                "tileset_map_maker.ui.dialogs.autotile_dialog.ConfigManager.save_autotile_rules"
            ):
                dialog._apply_template()
            rule = engine.get_active_ruleset()
            self.assertEqual(rule.pattern_tiles[(1, 4)], (asset.id, 32, 96, 16, 16))
            dialog._assign_pattern_tile(dialog.pattern_model.index(0, 1))
            self.assertEqual(rule.pattern_tiles[(1, 0)], (asset.id, 16, 32, 16, 16))

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
                rule = pattern(2, 5)
                rule.pattern_tiles = {
                    position: (asset.id, *tile[1:])
                    for position, tile in rule.pattern_tiles.items()
                }
                rule.default_tile = rule.pattern_tiles[(0, 0)]
                engine.register_ruleset(rule)
                layer = project.get_active_layer()
                layer.set_tile(width - 1, height - 1, MapItem(asset.id, width - 1, height - 1,
                                                             terrain_type="Grass", is_auto_tiled=True))
                engine.apply_autotile_stroke(layer, [(width - 1, height - 1)], rule, project)
                path = os.path.join(directory, "map.tmmap")
                self.assertTrue(ProjectIO.save_project(project, assets, path, engine))
                restored_engine = AutoTileEngine()
                restored = ProjectIO.load_project(path, AssetManager(), restored_engine)
                self.assertEqual((restored.map_width, restored.map_height), (width, height))
                self.assertEqual(restored_engine.get_active_ruleset().pattern_tiles, rule.pattern_tiles)
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
        rule = pattern(8, 8)
        engine.register_ruleset(rule)
        layer.autotile_ruleset_id = rule.id
        history = HistoryManager()
        settings = BrushSettings()
        settings.auto_tile_enabled = True
        context = ToolContext(project=project, active_layer=layer,
                              asset_manager=AssetManager(), history_manager=history,
                              brush_settings=settings, autotile_engine=engine)
        brush = BrushTool()
        brush.on_press(1198, 899, context)
        brush.on_drag(1199, 899, context)
        brush.on_release(1199, 899, context)
        self.assertEqual(layer.get_tile(1198, 899).source_x, 0)
        self.assertEqual(layer.get_tile(1199, 899).source_x, 7)
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
