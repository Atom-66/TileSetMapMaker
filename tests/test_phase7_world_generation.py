import gc
import time
import unittest

from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.terrain_generator import TerrainApplyCommand
from tileset_map_maker.core.rpg_autotile import RPGAutotile
from tileset_map_maker.models.project import Project
from tileset_map_maker.models.terrain import (
    TerrainConfig,
    TerrainGenerator,
    TerrainMask,
    TerrainType,
)


APP = QApplication.instance() or QApplication([])


class TestPhase7WorldGeneration(unittest.TestCase):
    def setUp(self):
        self.generator = TerrainGenerator()
        self.config = TerrainConfig(
            seed=4242,
            scale=10,
            river_count=2,
            road_count=2,
        )

    def test_generation_is_deterministic(self):
        first = self.generator.generate(80, 60, self.config)
        second = self.generator.generate(80, 60, self.config)
        self.assertEqual(first.cells, second.cells)
        self.assertEqual(first.seed, 4242)

    def test_contains_all_configured_biomes_and_paths(self):
        config = TerrainConfig(
            seed=7,
            scale=8,
            water_level=0.40,
            mountain_level=0.60,
            forest_threshold=0.52,
            river_count=1,
            road_count=2,
        )
        result = self.generator.generate(100, 80, config)
        used = set(result.cells)
        self.assertIn(TerrainType.WATER.value, used)
        self.assertIn(TerrainType.ROAD.value, used)
        self.assertIn(TerrainType.LAKE.value, used)
        self.assertTrue(
            TerrainType.FOREST.value in used
            or TerrainType.MOUNTAIN.value in used
        )

    def test_masks_force_terrain_and_manual_correction(self):
        mask = TerrainMask(30, 20)
        mask.set_rect(3, 4, 5, 6)
        result = self.generator.generate(
            30, 20, self.config, {"mountain": mask}
        )
        self.assertEqual(result.get(4, 5), TerrainType.MOUNTAIN)
        result.set(4, 5, TerrainType.GRASS)
        self.assertEqual(result.get(4, 5), TerrainType.GRASS)

    def test_previous_result_can_be_restored(self):
        first = self.generator.generate(30, 20, self.config)
        second_config = TerrainConfig(seed=999, scale=20)
        self.generator.generate(30, 20, second_config)
        restored = self.generator.restore_previous()
        self.assertEqual(restored.cells, first.cells)

    def test_presets_and_masks_roundtrip(self):
        self.generator.add_preset("Custom Isles", self.config)
        mask = TerrainMask(12, 10)
        mask.set_cell(5, 4)
        self.generator.masks["forest"] = mask
        restored = TerrainGenerator()
        restored.load_from_dict(self.generator.to_dict())
        self.assertIn("custom_isles", restored.presets)
        self.assertTrue(restored.masks["forest"][(5, 4)])
        self.assertEqual(
            restored.presets["custom_isles"].config.seed,
            self.config.seed,
        )

    def test_apply_uses_existing_rules_and_is_undoable(self):
        project = Project(map_width=12, map_height=12)
        engine = AutoTileEngine()
        grass = RPGAutotile(id="grass_id", name="Grass", tileset_id="grass_asset", tile_size=32)
        engine.register_rpg_autotile(grass)
        result = self.generator.generate(12, 12, self.config)
        config = TerrainConfig(
            autotile_ids={"grass": grass.id}
        )
        command = TerrainApplyCommand(
            project,
            project.active_layer_id,
            result,
            config,
            engine,
        )
        command.execute()
        history = HistoryManager()
        history.push(command)
        grass_cells = [
            (col, row)
            for row in range(12)
            for col in range(12)
            if result.get(col, row) == TerrainType.GRASS
        ]
        self.assertTrue(grass_cells)
        self.assertEqual(
            project.get_active_layer().get_tile(*grass_cells[0]).asset_id,
            "grass_id",
        )
        history.undo()
        self.assertIsNone(
            project.get_active_layer().get_tile(*grass_cells[0])
        )
        history.redo()
        self.assertIsNotNone(
            project.get_active_layer().get_tile(*grass_cells[0])
        )

    def test_large_generation_is_bounded_and_linear(self):
        started = time.perf_counter()
        result = self.generator.generate(
            1000, 1000, TerrainConfig(seed=55, river_count=2)
        )
        elapsed = time.perf_counter() - started
        gc.collect()
        self.assertEqual(len(result.cells), 1_000_000)
        self.assertLess(elapsed, 20.0)
        self.assertLessEqual(len(result.cells), 2_000_000)


if __name__ == "__main__":
    unittest.main()
