import os
import tempfile
import unittest

from PyQt6.QtCore import QRect

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.render_engine import RenderEngine
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.select_tool import SelectTool
from tileset_map_maker.models.layer import Layer, MapItem
from tileset_map_maker.models.project import Project


class TestPhase2EditorVerification(unittest.TestCase):
    def setUp(self):
        self.project = Project(map_width=4, map_height=3)
        self.assets = AssetManager()

    def test_resize_preserves_shifted_content(self):
        item = MapItem("asset", 1, 1)
        self.project.get_active_layer().set_tile(1, 1, item)
        self.project.resize_map(6, 5, "center")
        self.assertIsNone(self.project.get_active_layer().get_tile(1, 1))
        self.assertIsNotNone(self.project.get_active_layer().get_tile(2, 2))

    def test_map_template_and_clone_keep_independent_layers(self):
        source = self.project.get_active_map()
        template = self.project.save_map_template(source.id)
        clone = self.project.add_map_from_template(template, "Kopia szablonu")
        self.assertNotEqual(clone.id, source.id)
        self.assertNotEqual(
            clone.get_active_layer().id, source.get_active_layer().id
        )
        clone.get_active_layer().set_tile(0, 0, MapItem("asset", 0, 0))
        self.assertIsNone(source.get_active_layer().get_tile(0, 0))

    def test_copy_move_and_merge_layers_between_maps(self):
        source = self.project.get_active_map()
        target = self.project.add_map("Druga")
        self.project.set_active_map(source.id)
        first = source.add_layer("Pierwsza")
        second = source.add_layer("Druga warstwa")
        first.set_tile(0, 0, MapItem("a", 0, 0))
        second.set_tile(0, 0, MapItem("b", 0, 0))

        copied = self.project.copy_layer_between_maps(
            source.id, first.id, target.id
        )
        self.assertIsNotNone(copied)
        self.assertNotEqual(copied.id, first.id)
        self.assertTrue(
            self.project.move_layer_between_maps(source.id, second.id, target.id)
        )
        merged = self.project.merge_layers(
            target.id, [copied.id, second.id], "Połączone"
        )
        self.assertIsNotNone(merged)
        self.assertEqual(merged.get_tile(0, 0).asset_id, "b")
        self.assertIsNone(source.get_layer(second.id))

    def test_selection_transformations_are_undoable(self):
        layer = self.project.get_active_layer()
        layer.set_tile(1, 1, MapItem("a", 1, 1))
        history = HistoryManager()
        context = ToolContext(self.project, self.assets, history, layer)
        tool = SelectTool()
        tool.selection_rect = QRect(1, 1, 2, 1)

        self.assertTrue(tool.rotate_selection_clockwise(context))
        self.assertIsNotNone(layer.get_tile(1, 1))
        self.assertEqual(layer.get_tile(1, 1).rotation, 90.0)
        self.assertTrue(history.undo())
        self.assertEqual(layer.get_tile(1, 1).rotation, 0.0)
        self.assertTrue(tool.flip_selection_horizontal(context))
        self.assertTrue(layer.get_tile(1, 1).flip_x)

    def test_polygon_selection_and_move_preview(self):
        layer = self.project.get_active_layer()
        layer.set_tile(1, 1, MapItem("a", 1, 1))
        layer.set_tile(2, 1, MapItem("b", 2, 1))
        context = ToolContext(
            self.project, self.assets, HistoryManager(), layer
        )
        tool = SelectTool()
        self.assertTrue(
            tool.set_polygon_selection([(0, 0), (3, 0), (3, 2), (0, 2)])
        )
        tool.on_press(1, 1, context)
        tool.on_drag(1, 2, context)
        previews = tool.get_preview_items(context)
        self.assertIn((1, 2), {(item.col, item.row) for item in previews})
        tool.on_release(1, 2, context)
        self.assertIsNone(layer.get_tile(1, 1))
        self.assertIsNotNone(layer.get_tile(1, 2))

    def test_layer_type_isolation_and_serialization(self):
        collision = self.project.add_layer("Kolizje")
        collision.layer_type = "collision"
        self.assertTrue(self.project.isolate_layer(collision.id))
        restored = Project.from_dict(self.project.to_dict())
        self.assertEqual(restored.isolated_layer_id, collision.id)
        self.assertEqual(restored.get_layer(collision.id).layer_type, "collision")

    def test_export_all_maps_and_validate_missing_assets(self):
        self.project.add_map("Mapa świata")
        self.project.layers
        self.project.get_active_layer().set_tile(
            0, 0, MapItem("brakujący", 0, 0)
        )
        self.assertEqual(
            ProjectIO.validate_project_assets(self.project, self.assets),
            ["brakujący"],
        )
        with tempfile.TemporaryDirectory() as output:
            self.assertTrue(
                ProjectIO.export_maps_png(
                    self.project,
                    RenderEngine(self.assets),
                    output,
                    transparent_bg=True,
                )
            )
            self.assertEqual(
                sorted(os.listdir(output)),
                ["Główna_Mapa.png", "Mapa_świata.png"],
            )


if __name__ == "__main__":
    unittest.main()
