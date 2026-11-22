import os
import shutil
import unittest
from PyQt6.QtWidgets import QApplication
import sys

# Ensure QApplication exists for QPixmap operations
app = QApplication.instance() or QApplication(sys.argv)

from tileset_map_maker.models.category import CategoryTree
from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.models.layer import Layer, MapItem, ItemType
from tileset_map_maker.models.project import Project
from tileset_map_maker.core.asset_manager import AssetManager
from sample_assets.generate_samples import create_sample_assets


class TestModelsAndAssetManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = "test_sample_assets"
        create_sample_assets(cls.test_dir)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)

    def test_category_tree(self):
        tree = CategoryTree()
        node = tree.add_category_path("World/Biome/Forest")
        self.assertEqual(node.path, "World/Biome/Forest")
        self.assertIsNotNone(tree.get_node("World/Biome"))
        
        # Rename category
        renamed = tree.rename_category("World/Biome/Forest", "DeepJungle")
        self.assertEqual(renamed, "World/Biome/DeepJungle")
        self.assertIsNotNone(tree.get_node("World/Biome/DeepJungle"))
        self.assertIsNone(tree.get_node("World/Biome/Forest"))

        # Move category
        moved = tree.move_category("World/Biome/DeepJungle", "Custom")
        self.assertEqual(moved, "Custom/DeepJungle")
        self.assertIsNotNone(tree.get_node("Custom/DeepJungle"))

        # Delete category
        deleted = tree.delete_category("Custom/DeepJungle")
        self.assertTrue(deleted)
        self.assertIsNone(tree.get_node("Custom/DeepJungle"))

    def test_folder_import_and_duplicates(self):
        manager = AssetManager()
        res = manager.import_folder(self.test_dir)
        self.assertGreaterEqual(res["imported_count"], 4)
        self.assertEqual(res["duplicates_count"], 0)

        # Re-import same folder - all should be detected as duplicates
        res2 = manager.import_folder(self.test_dir, skip_duplicates=True)
        self.assertEqual(res2["imported_count"], 0)
        self.assertGreaterEqual(res2["duplicates_count"], 4)

        # Check preserved category paths
        terrain_node = manager.category_tree.get_node(f"{self.test_dir}/Terrain/Grass")
        self.assertIsNotNone(terrain_node)
        self.assertGreater(len(terrain_node.asset_ids), 0)

        # Search
        grass_assets = manager.search_assets("grass")
        self.assertGreaterEqual(len(grass_assets), 2)

    def test_tileset_slicing(self):
        manager = AssetManager()
        ts_path = f"{self.test_dir}/Terrain/terrain_tileset.png"
        asset, is_dup, err = manager.import_single_file(ts_path, force_asset_type=AssetType.TILESET)
        self.assertIsNotNone(asset)
        self.assertEqual(asset.width, 64)
        self.assertEqual(asset.height, 64)
        
        cfg = asset.tileset_config
        self.assertIsNotNone(cfg)
        cfg.tile_width = 32
        cfg.tile_height = 32
        cols, rows = asset.get_tileset_dimensions()
        self.assertEqual(cols, 2)
        self.assertEqual(rows, 2)
        
        # Test rects for tile (1, 1)
        x, y, w, h = asset.get_tile_rect(1, 1)
        self.assertEqual((x, y, w, h), (32, 32, 32, 32))

    def test_layer_operations(self):
        project = Project(map_width=20, map_height=15, tile_size=32)
        self.assertEqual(len(project.layers), 5)
        
        active = project.get_active_layer()
        self.assertIsNotNone(active)
        
        # Place a tile
        item = MapItem(asset_id="test_asset", col=5, row=5)
        active.set_tile(5, 5, item)
        self.assertEqual(active.get_tile(5, 5), item)
        
        # Clone layer
        cloned = active.clone("Ground Copy")
        self.assertEqual(cloned.name, "Ground Copy")
        self.assertIn((5, 5), cloned.tiles)
        self.assertEqual(cloned.tiles[(5, 5)].asset_id, "test_asset")

        # Duplicate in project
        dup = project.duplicate_layer(active.id)
        self.assertIsNotNone(dup)
        self.assertEqual(len(project.layers), 6)

        # Remove layer
        removed = project.remove_layer(dup.id)
        self.assertTrue(removed)
        self.assertEqual(len(project.layers), 5)


if __name__ == "__main__":
    unittest.main()
