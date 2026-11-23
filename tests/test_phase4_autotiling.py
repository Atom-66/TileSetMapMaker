import unittest

from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.history import HistoryManager, TileBatchCommand
from tileset_map_maker.models.autotile import (
    AutoTileRuleSet,
    CARD_CENTER,
)
from tileset_map_maker.models.layer import MapItem
from tileset_map_maker.models.project import Project


APP = QApplication.instance() or QApplication([])


class TestPhase4Autotiling(unittest.TestCase):
    def setUp(self):
        self.engine = AutoTileEngine()
        self.project = Project(map_width=5, map_height=5)
        self.rule = AutoTileRuleSet(
            name="Grass", terrain_type="Grass", seed=1234
        )
        self.rule.setup_standard_3x3_box("asset", 0, 0, 32, 32)
        self.engine.register_ruleset(self.rule)

    def test_weighted_mapping_is_deterministic_with_seed(self):
        variant = ("other", 64, 64, 32, 32)
        self.rule.add_mapping_variant(CARD_CENTER, variant, 10.0)
        first = [
            self.rule.get_weighted_tile_for_mask(CARD_CENTER, col, 2)
            for col in range(10)
        ]
        second = [
            self.rule.get_weighted_tile_for_mask(CARD_CENTER, col, 2)
            for col in range(10)
        ]
        self.assertEqual(first, second)
        self.assertIn(variant, first)

    def test_multiple_rulesets_resolve_by_terrain(self):
        water = AutoTileRuleSet(name="Water", terrain_type="Water")
        water.setup_standard_3x3_box("water", 0, 0, 32, 32)
        self.engine.register_ruleset(water)
        self.assertIs(self.engine.get_ruleset_for_terrain("Water"), water)
        layer = self.project.get_active_layer()
        layer.autotile_ruleset_id = water.id
        self.assertIs(self.engine.resolve_layer_ruleset(layer), water)

    def test_recalculate_area_updates_all_autotiled_cells(self):
        layer = self.project.get_active_layer()
        for row in range(1, 4):
            for col in range(1, 4):
                layer.set_tile(
                    col,
                    row,
                    MapItem(
                        "old",
                        col,
                        row,
                        terrain_type="Grass",
                        is_auto_tiled=True,
                    ),
                )
        changes = self.engine.recalculate_layer(self.project, layer)
        self.assertEqual(len(changes), 9)
        self.assertTrue(all(v[1].asset_id == "asset" for v in changes.values()))
        center = layer.get_tile(2, 2)
        self.assertEqual((center.source_x, center.source_y), (32, 32))

    def test_recalculate_preserves_history(self):
        layer = self.project.get_active_layer()
        layer.set_tile(
            2,
            2,
            MapItem(
                "old", 2, 2, terrain_type="Grass", is_auto_tiled=True
            ),
        )
        history = HistoryManager()
        changes = self.engine.recalculate_layer(self.project, layer)
        history.push(
            TileBatchCommand(
                self.project, layer.id, changes, "Przeliczenie Auto-Tiling"
            )
        )
        self.assertTrue(history.undo())
        self.assertEqual(layer.get_tile(2, 2).asset_id, "old")
        self.assertTrue(history.redo())
        self.assertEqual(layer.get_tile(2, 2).asset_id, "asset")

    def test_ruleset_presets_roundtrip(self):
        preset_id = self.engine.save_ruleset_preset("Grass preset", self.rule)
        fresh = AutoTileEngine()
        fresh.load_from_dict(self.engine.to_dict())
        clone = fresh.create_ruleset_from_preset(preset_id, "Grass 2")
        self.assertIsNotNone(clone)
        self.assertEqual(clone.name, "Grass 2")
        self.assertEqual(clone.terrain_type, "Grass")
        self.assertEqual(len(clone.tile_mappings), len(self.rule.tile_mappings))

    def test_layer_ruleset_assignment_serializes(self):
        layer = self.project.get_active_layer()
        layer.autotile_ruleset_id = self.rule.id
        restored = type(self.project).from_dict(self.project.to_dict())
        self.assertEqual(
            restored.get_active_layer().autotile_ruleset_id, self.rule.id
        )


if __name__ == "__main__":
    unittest.main()
