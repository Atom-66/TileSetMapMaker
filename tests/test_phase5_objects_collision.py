import json
import os
import tempfile
import unittest

from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.object_tool import ObjectTool
from tileset_map_maker.models.layer import (
    CollisionObject,
    CollisionShape,
    ItemType,
    MapItem,
)
from tileset_map_maker.models.project import Project


APP = QApplication.instance() or QApplication([])


class TestPhase5ObjectsCollision(unittest.TestCase):
    def setUp(self):
        self.project = Project(map_width=20, map_height=20, tile_size=32)

    def test_object_properties_and_type_roundtrip(self):
        obj = MapItem(
            "asset",
            2,
            3,
            item_type=ItemType.OBJECT,
            free_x=64,
            free_y=96,
            object_type="npc",
            properties={"hp": 42, "hostile": False},
            property_types={"hp": "integer", "hostile": "boolean"},
            interaction_label="Porozmawiaj",
            interaction_radius=48,
        )
        self.project.get_active_layer().add_object(obj)
        restored = Project.from_dict(self.project.to_dict())
        loaded = restored.get_active_layer().objects[0]
        self.assertEqual(loaded.object_type, "npc")
        self.assertEqual(loaded.properties["hp"], 42)
        self.assertFalse(loaded.properties["hostile"])
        self.assertEqual(loaded.interaction_label, "Porozmawiaj")

    def test_collision_shapes_and_walkability(self):
        layer = self.project.add_layer("Kolizje", layer_type="collision")
        rectangle = CollisionObject(0, 0, 32, 32)
        ellipse = CollisionObject(
            64, 64, 32, 32, shape=CollisionShape.ELLIPSE
        )
        layer.add_collision(rectangle)
        layer.add_collision(ellipse)
        self.assertFalse(self.project.is_walkable(16, 16))
        self.assertFalse(self.project.is_walkable(80, 80))
        self.assertTrue(self.project.is_walkable(64, 64))
        self.assertTrue(self.project.is_walkable(200, 200))

    def test_interaction_radius_selects_nearest_objects(self):
        layer = self.project.add_layer("Obiekty", layer_type="object")
        low = MapItem(
            "a", 0, 0, item_type=ItemType.OBJECT,
            free_x=0, free_y=0, dest_w=16, dest_h=16,
            interaction_label="Niski", interaction_radius=40, z_index=1,
        )
        high = low.clone()
        high.object_type = "portal"
        high.interaction_label = "Wysoki"
        high.z_index = 10
        layer.add_object(low)
        layer.add_object(high)
        found = self.project.get_interactions_at(20, 20)
        self.assertEqual([item.interaction_label for item in found], ["Wysoki", "Niski"])

    def test_collision_and_objects_survive_project_save(self):
        layer = self.project.add_layer("Gameplay", layer_type="collision")
        layer.add_collision(CollisionObject(5, 6, 32, 64, trigger=True))
        layer.add_object(MapItem("tree", 2, 2, item_type=ItemType.OBJECT))
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "world.tmmap")
            self.assertTrue(
                ProjectIO.save_project(
                    self.project, AssetManager(), path
                )
            )
            restored = ProjectIO.load_project(path, AssetManager())
        self.assertIsNotNone(restored)
        restored_layer = next(
            item for item in restored.layers
            if item.name == "Gameplay"
        )
        self.assertEqual(len(restored_layer.collisions), 1)
        self.assertTrue(restored_layer.collisions[0].trigger)
        self.assertEqual(len(restored_layer.objects), 1)

    def test_collision_json_export_contains_properties_and_triggers(self):
        object_layer = self.project.add_layer("Obiekty", layer_type="object")
        object_layer.add_object(
            MapItem(
                "npc",
                1,
                1,
                item_type=ItemType.OBJECT,
                free_x=32,
                free_y=32,
                object_type="npc",
                interaction_label="Rozmowa",
                interaction_radius=24,
                properties={"quest": "main"},
                property_types={"quest": "string"},
            )
        )
        collision_layer = self.project.add_layer(
            "Kolizje", layer_type="collision"
        )
        collision_layer.add_collision(
            CollisionObject(
                64, 64, 32, 32, trigger=True, blocking=False,
                interaction_label="Wejście",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "gameplay.json")
            self.assertTrue(
                ProjectIO.export_collision_json(self.project, path)
            )
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        exported = data["maps"][0]
        collisions = next(
            layer for layer in exported["layers"]
            if layer["type"] == "collision"
        )["collisions"]
        self.assertTrue(collisions[0]["trigger"])
        objects = next(
            layer for layer in exported["layers"]
            if layer["type"] == "object"
        )["objects"]
        self.assertEqual(objects[0]["properties"], {"quest": "main"})

    def test_object_transform_remains_undoable(self):
        layer = self.project.add_layer("Obiekty", layer_type="object")
        obj = MapItem(
            "asset", 0, 0, item_type=ItemType.OBJECT,
            free_x=10, free_y=20, dest_w=32, dest_h=32,
        )
        layer.add_object(obj)
        other = MapItem(
            "asset", 0, 0, item_type=ItemType.OBJECT,
            free_x=40, free_y=20, dest_w=32, dest_h=32,
        )
        layer.add_object(other)
        context = ToolContext(
            self.project, AssetManager(), HistoryManager(), layer
        )
        tool = ObjectTool()
        tool.selected_ids = [obj.id, other.id]
        tool.align_selected("left", context)
        self.assertTrue(context.history_manager.can_undo())
        context.history_manager.undo()
        self.assertEqual(obj.free_x, 10)
        self.assertEqual(other.free_x, 40)


if __name__ == "__main__":
    unittest.main()
