import os
import shutil
import unittest
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)

from tileset_map_maker.models.project import Project
from tileset_map_maker.models.layer import Layer, MapItem, ItemType
from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.core.rpg_autotile import (
    RPGAutotile,
)
from tileset_map_maker.models.stamp import StampPreset
from tileset_map_maker.models.asset_set import AssetSet
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.set_manager import SetManager
from tileset_map_maker.core.stamp_manager import StampManager
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.tools import (
    ToolContext,
    BrushTool,
    SelectTool,
    StampTool,
    ObjectTool,
)
from tileset_map_maker.core.project_io import ProjectIO
from sample_assets.generate_samples import create_sample_assets


class TestStage2AdvancedFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = "test_stage2_assets"
        cls.export_dir = "test_stage2_exports"
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
        self.autotile_engine = AutoTileEngine()
        self.set_mgr = SetManager(os.path.join(self.export_dir, "test_sets.json"))
        self.stamp_mgr = StampManager(os.path.join(self.export_dir, "test_stamps.json"))
        self.project = Project(map_width=15, map_height=15, tile_size=32)
        self.render_engine = RenderEngine(self.asset_mgr)

    # 1. AUTO-TILING
    def test_autotiling_system(self):
        autotile = RPGAutotile(id="test_grass", name="Test Grass", terrain_type="Test Grass", tileset_id="grass_center", tile_size=32)
        self.autotile_engine.register_rpg_autotile(autotile)

        layer = self.project.get_active_layer()

        # Place 3x3 block of grass
        coords = []
        for r in range(1, 4):
            for c in range(1, 4):
                coords.append((c, r))

        # Apply autotile stroke
        self.autotile_engine.apply_rpg_autotile_stroke(layer, coords, autotile, self.project)

        # Center tile (2, 2) should receive center mapping
        center_tile = layer.get_tile(2, 2)
        self.assertIsNotNone(center_tile)
        self.assertEqual(center_tile.asset_id, "test_grass")
        self.assertEqual(center_tile.terrain_type, "Test Grass")

        # Top-left tile (1, 1) has no North or West, should match outer corner
        corner_tile = layer.get_tile(1, 1)
        self.assertIsNotNone(corner_tile)

        # Disable autotiling on layer -> changes should not be applied
        layer.auto_tiling_enabled = False
        empty_changes = self.autotile_engine.apply_rpg_autotile_stroke(layer, coords, autotile, self.project)
        self.assertEqual(len(empty_changes), 0)

    # 2. ADVANCED BRUSHES AND SAVED STAMPS
    def test_stamps_and_rotations(self):
        stamp = StampPreset(name="Domek i drzewo", width=2, height=2)
        item1 = MapItem(asset_id="asset1", col=0, row=0)
        item2 = MapItem(asset_id="asset2", col=1, row=0)
        stamp.items[(0, 0)] = item1
        stamp.items[(1, 0)] = item2

        # Rotate 90 degrees
        stamp.rotate_90()
        self.assertEqual(stamp.width, 2)
        self.assertEqual(stamp.height, 2)
        # item1 at (0,0) -> nc = 2 - 1 - 0 = 1, nr = 0 -> (1, 0)
        self.assertIn((1, 0), stamp.items)
        self.assertEqual(stamp.items[(1, 0)].rotation, 90.0)

        # Flip horizontal
        stamp.flip_horizontal()
        self.assertIn((0, 0), stamp.items)
        self.assertTrue(stamp.items[(0, 0)].flip_x)

        # Persistence in StampManager
        self.stamp_mgr.add_stamp(stamp)
        self.assertIsNotNone(self.stamp_mgr.get_stamp(stamp.id))

        # Fresh StampManager loads from disk
        fresh_stamp_mgr = StampManager(self.stamp_mgr.storage_path)
        self.assertIn(stamp.id, fresh_stamp_mgr.stamps)

    # 3. LOGICAL ASSET SETS
    def test_asset_sets(self):
        grass = self.asset_mgr.search_assets("grass")[0]
        tree = self.asset_mgr.search_assets("tree")[0]

        # Assets come from different categories!
        self.assertNotEqual(grass.category_path, tree.category_path)

        # Create combined set
        forest_set = self.set_mgr.create_set("Leśna lokacja", [grass.id, tree.id])
        self.assertEqual(len(forest_set.asset_ids), 2)
        self.assertIn(grass.id, forest_set.asset_ids)
        self.assertIn(tree.id, forest_set.asset_ids)

        # Reorder items
        self.assertTrue(forest_set.move_asset(0, 1))
        self.assertEqual(forest_set.asset_ids[0], tree.id)

        # Persistence check
        fresh_set_mgr = SetManager(self.set_mgr.storage_path)
        loaded_set = fresh_set_mgr.get_set(forest_set.id)
        self.assertIsNotNone(loaded_set)
        self.assertEqual(loaded_set.name, "Leśna lokacja")

    # 4. LAYER GROUPS AND HIERARCHY
    def test_layer_groups_and_hierarchy(self):
        # Create group "Nature"
        group = self.project.add_group("Nature")
        self.assertTrue(group.is_group)

        # Add child layers "Ground" and "Trees" to "Nature" group
        child1 = self.project.add_layer("Ground Tiles", group_id=group.id)
        child2 = self.project.add_layer("Tree Objects", group_id=group.id)
        self.assertEqual(child1.group_id, group.id)
        self.assertEqual(child2.group_id, group.id)

        # Effective visibility test
        self.assertTrue(self.project.get_effective_visible(child1))
        group.visible = False
        self.assertFalse(self.project.get_effective_visible(child1))
        self.assertFalse(self.project.get_effective_visible(child2))

        # Effective opacity test (group 0.5 * child 0.5 = 0.25)
        group.visible = True
        group.opacity = 0.5
        child1.opacity = 0.5
        self.assertAlmostEqual(self.project.get_effective_opacity(child1), 0.25)

        # Effective locked test
        self.assertFalse(self.project.get_effective_locked(child1))
        group.locked = True
        self.assertTrue(self.project.get_effective_locked(child1))

    # 5. FREEFORM OBJECT TRANSFORMS
    def test_freeform_object_transforms(self):
        tree = self.asset_mgr.search_assets("tree")[0]
        layer = self.project.get_active_layer()

        # Add freeform object
        obj = MapItem(
            asset_id=tree.id,
            col=5,
            row=5,
            item_type=ItemType.OBJECT,
            free_x=160.0,
            free_y=160.0,
            dest_w=64,
            dest_h=96,
        )
        layer.add_object(obj)

        ctx = ToolContext(self.project, self.asset_mgr, self.history_mgr, layer, None)
        ctx.cursor_pixel_x = 180.0
        ctx.cursor_pixel_y = 180.0

        tool = ObjectTool()
        # Click to select object
        tool.on_press(5, 5, ctx)
        self.assertIn(obj.id, tool.selected_ids)

        # Rotate object
        tool.rotate_selected(90.0, ctx)
        self.assertEqual(obj.rotation, 90.0)

        # Scale object
        tool.scale_selected(1.5, ctx)
        self.assertAlmostEqual(obj.scale_x, 1.5)

        # Flip object
        tool.flip_selected(horizontal=True, context=ctx)
        self.assertTrue(obj.flip_x)

        # Undo transformations
        self.assertTrue(self.history_mgr.can_undo())
        self.history_mgr.undo()  # Undo flip
        self.assertFalse(obj.flip_x)
        self.history_mgr.undo()  # Undo scale
        self.assertAlmostEqual(obj.scale_x, 1.0)
        self.history_mgr.undo()  # Undo rotate
        self.assertEqual(obj.rotation, 0.0)

    # 6. RANDOM VARIANTS AND SEED DETERMINISM
    def test_random_brush_variants_and_seed(self):
        grass1 = self.asset_mgr.search_assets("grass_01")[0]
        grass2 = self.asset_mgr.search_assets("grass_02")[0]

        bs = BrushSettings(random_variant=True, seed=42)
        bs.variants = [grass1, grass2]

        # Sequence with seed 42
        seq1 = [bs.pick_variant(grass1).id for _ in range(10)]

        # Reset RNG with same seed 42
        bs.reset_rng()
        seq2 = [bs.pick_variant(grass1).id for _ in range(10)]

        self.assertEqual(seq1, seq2)

    # 7. BACKWARDS COMPATIBILITY
    def test_backward_compatibility(self):
        # Create an old-style legacy project dict
        legacy_data = {
            "version": "1.0",
            "project": {
                "name": "Stary Projekt v1",
                "map_width": 12,
                "map_height": 8,
                "tile_size": 32,
                "background_color": "#202020",
                "layers": [
                    {
                        "name": "Ground",
                        "visible": True,
                        "locked": False,
                        "opacity": 1.0,
                        "tiles": [],
                        "objects": [],
                    }
                ],
            },
            "assets": {"assets": [], "category_tree": {}},
        }
        legacy_file = os.path.join(self.export_dir, "legacy_v1.tmmap")
        import json
        with open(legacy_file, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        loaded = ProjectIO.load_project(legacy_file, self.asset_mgr)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "Stary Projekt v1")
        self.assertEqual(len(loaded.layers), 1)
        # Should have new fields default-initialized gracefully
        self.assertFalse(loaded.layers[0].is_group)
        self.assertIsNone(loaded.layers[0].group_id)
        self.assertTrue(loaded.layers[0].auto_tiling_enabled)


if __name__ == "__main__":
    unittest.main()
