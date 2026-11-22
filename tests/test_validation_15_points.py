import os
import shutil
import unittest
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtCore import Qt, QPointF

app = QApplication.instance() or QApplication(sys.argv)

from tileset_map_maker.models.project import Project
from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.models.layer import Layer, MapItem, ItemType
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
from tileset_map_maker.ui.main_window import MainWindow
from sample_assets.generate_samples import create_sample_assets


class TestValidation15Points(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = "test_validation_assets"
        cls.export_dir = "test_validation_exports"
        os.makedirs(cls.export_dir, exist_ok=True)
        create_sample_assets(cls.test_dir)

    @classmethod
    def tearDownClass(cls):
        for d in [cls.test_dir, cls.export_dir]:
            if os.path.exists(d):
                shutil.rmtree(d)

    def setUp(self):
        self.asset_mgr = AssetManager()
        self.history_mgr = HistoryManager()
        self.render_engine = RenderEngine(self.asset_mgr)

    # 1. Czy można utworzyć nowy projekt.
    def test_01_create_new_project(self):
        project = Project(name="Testowy Projekt", map_width=40, map_height=25, tile_size=32)
        self.assertEqual(project.name, "Testowy Projekt")
        self.assertEqual(project.map_width, 40)
        self.assertEqual(project.map_height, 25)
        self.assertEqual(project.tile_size, 32)
        self.assertGreaterEqual(len(project.layers), 1)
        self.assertIsNotNone(project.get_active_layer())

    # 2. Czy można importować pojedyncze PNG.
    def test_02_import_single_png(self):
        png_path = f"{self.test_dir}/Terrain/Water/water.png"
        asset, is_dup, err = self.asset_mgr.import_single_file(png_path, target_category_path="Terrain/Water")
        self.assertIsNotNone(asset)
        self.assertFalse(is_dup)
        self.assertEqual(asset.width, 32)
        self.assertEqual(asset.height, 32)
        self.assertEqual(asset.category_path, "Terrain/Water")

    # 3. Czy można importować całe foldery z podfolderami.
    def test_03_import_folder_with_subfolders(self):
        res = self.asset_mgr.import_folder(self.test_dir, skip_duplicates=True)
        self.assertGreaterEqual(res["imported_count"], 4)
        self.assertEqual(len(res["errors"]), 0)

    # 4. Czy struktura folderów jest prawidłowo odwzorowywana w bibliotece.
    def test_04_folder_structure_preserved_in_categories(self):
        self.asset_mgr.import_folder(self.test_dir, skip_duplicates=True)
        grass_node = self.asset_mgr.category_tree.get_node(f"{self.test_dir}/Terrain/Grass")
        self.assertIsNotNone(grass_node)
        self.assertGreaterEqual(len(grass_node.asset_ids), 2)
        
        trees_node = self.asset_mgr.category_tree.get_node(f"{self.test_dir}/Objects/Trees")
        self.assertIsNotNone(trees_node)
        self.assertGreaterEqual(len(trees_node.asset_ids), 1)

    # 5. Czy klasyczne tilesety można prawidłowo dzielić na kafelki.
    def test_05_classic_tileset_slicing(self):
        ts_path = f"{self.test_dir}/Terrain/terrain_tileset.png"
        asset, _, _ = self.asset_mgr.import_single_file(ts_path, force_asset_type=AssetType.TILESET)
        self.assertIsNotNone(asset)
        asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32, margin=0, spacing=0)
        cols, rows = asset.get_tileset_dimensions()
        self.assertEqual(cols, 2)
        self.assertEqual(rows, 2)
        x, y, w, h = asset.get_tile_rect(1, 0)
        self.assertEqual((x, y, w, h), (32, 0, 32, 32))

    # 6. Czy pojedyncze grafiki zachowują oryginalne wymiary.
    def test_06_single_graphics_preserve_dimensions(self):
        tree_path = f"{self.test_dir}/Objects/Trees/large_tree.png"
        asset, _, _ = self.asset_mgr.import_single_file(tree_path)
        self.assertIsNotNone(asset)
        self.assertEqual(asset.width, 64)
        self.assertEqual(asset.height, 96)

        cottage_path = f"{self.test_dir}/Buildings/Houses/cottage.png"
        house, _, _ = self.asset_mgr.import_single_file(cottage_path)
        self.assertIsNotNone(house)
        self.assertEqual(house.width, 96)
        self.assertEqual(house.height, 96)

    # 7. Czy można swobodnie malować po mapie.
    def test_07_painting_on_map(self):
        self.asset_mgr.import_folder(self.test_dir)
        grass = self.asset_mgr.search_assets("grass_01")[0]
        self.asset_mgr.select_asset(grass)

        project = Project(map_width=20, map_height=20, tile_size=32)
        ctx = ToolContext(project, self.asset_mgr, self.history_mgr, project.get_active_layer(), grass)

        brush = BrushTool()
        brush.on_press(3, 4, ctx)
        brush.on_drag(3, 5, ctx)
        brush.on_drag(3, 6, ctx)
        brush.on_release(3, 6, ctx)

        layer = project.get_active_layer()
        self.assertIsNotNone(layer.get_tile(3, 4))
        self.assertIsNotNone(layer.get_tile(3, 5))
        self.assertIsNotNone(layer.get_tile(3, 6))

    # 8. Czy system warstw działa poprawnie.
    def test_08_layer_system(self):
        project = Project(map_width=20, map_height=20, tile_size=32)
        initial_layers_count = len(project.layers)

        # Add layer
        new_layer = project.add_layer("Decorations 2")
        self.assertEqual(len(project.layers), initial_layers_count + 1)
        self.assertEqual(project.active_layer_id, new_layer.id)

        # Lock layer
        new_layer.locked = True
        self.assertTrue(new_layer.locked)

        # Opacity
        new_layer.opacity = 0.5
        self.assertEqual(new_layer.opacity, 0.5)

        # Duplicate
        dup = project.duplicate_layer(new_layer.id)
        self.assertIsNotNone(dup)
        self.assertEqual(len(project.layers), initial_layers_count + 2)

        # Remove
        removed = project.remove_layer(dup.id)
        self.assertTrue(removed)

    # 9. Czy zmiana kolejności warstw wpływa na renderowanie.
    def test_09_layer_reordering_affects_render_order(self):
        project = Project(map_width=2, map_height=2, tile_size=32)
        # Clear layers and setup 2 layers: Bottom and Top
        project.layers.clear()
        l_bottom = Layer(name="Bottom")
        l_top = Layer(name="Top")
        project.layers = [l_bottom, l_top]

        # Bottom layer has grass, Top layer has water at (0, 0)
        self.asset_mgr.import_folder(self.test_dir)
        grass = self.asset_mgr.search_assets("grass_01")[0]
        water = self.asset_mgr.search_assets("water")[0]

        l_bottom.set_tile(0, 0, MapItem(asset_id=grass.id, col=0, row=0))
        l_top.set_tile(0, 0, MapItem(asset_id=water.id, col=0, row=0))

        # In current order, Top (water) is on top
        img1 = self.render_engine.export_to_image(project)
        pixel_color1 = QColor(img1.pixel(16, 16))

        # Reorder layers so Bottom is now Top
        project.move_layer(0, 1)  # l_bottom becomes index 1 (top)
        img2 = self.render_engine.export_to_image(project)
        pixel_color2 = QColor(img2.pixel(16, 16))

        # Colors must differ because top tile changed!
        self.assertNotEqual((pixel_color1.red(), pixel_color1.green(), pixel_color1.blue()),
                            (pixel_color2.red(), pixel_color2.green(), pixel_color2.blue()))

    # 10. Czy cofanie i ponawianie działa poprawnie.
    def test_10_undo_redo_fidelity(self):
        project = Project(map_width=10, map_height=10, tile_size=32)
        self.asset_mgr.import_folder(self.test_dir)
        grass = self.asset_mgr.search_assets("grass_01")[0]
        ctx = ToolContext(project, self.asset_mgr, self.history_mgr, project.get_active_layer(), grass)

        brush = BrushTool()
        brush.on_press(5, 5, ctx)
        brush.on_release(5, 5, ctx)
        self.assertIsNotNone(project.get_active_layer().get_tile(5, 5))

        self.history_mgr.undo()
        self.assertIsNone(project.get_active_layer().get_tile(5, 5))

        self.history_mgr.redo()
        self.assertIsNotNone(project.get_active_layer().get_tile(5, 5))

    # 11. Czy zapis i ponowne otwarcie projektu zachowuje wszystkie dane.
    def test_11_save_and_reopen_project(self):
        project = Project(name="Przetestowany Zapis", map_width=15, map_height=12, tile_size=48)
        self.asset_mgr.import_folder(self.test_dir)
        grass = self.asset_mgr.search_assets("grass_01")[0]
        layer = project.get_active_layer()
        layer.set_tile(2, 2, MapItem(asset_id=grass.id, col=2, row=2, dest_w=48, dest_h=48))

        save_path = os.path.join(self.export_dir, "roundtrip.tmmap")
        self.assertTrue(ProjectIO.save_project(project, self.asset_mgr, save_path))

        fresh_mgr = AssetManager()
        loaded = ProjectIO.load_project(save_path, fresh_mgr)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "Przetestowany Zapis")
        self.assertEqual(loaded.map_width, 15)
        self.assertEqual(loaded.map_height, 12)
        self.assertEqual(loaded.tile_size, 48)
        self.assertIsNotNone(loaded.get_active_layer().get_tile(2, 2))

    # 12. Czy eksport PNG generuje poprawny obraz.
    def test_12_png_export_validity(self):
        project = Project(map_width=8, map_height=6, tile_size=32)
        out_png = os.path.join(self.export_dir, "test_map.png")
        ok = ProjectIO.export_png(project, self.render_engine, out_png)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(out_png))

        qimg = QImage(out_png)
        self.assertFalse(qimg.isNull())
        self.assertEqual(qimg.width(), 8 * 32)
        self.assertEqual(qimg.height(), 6 * 32)

    # 13. Czy przezroczystość PNG jest zachowana.
    def test_13_png_transparency_preserved(self):
        project = Project(map_width=4, map_height=4, tile_size=32, is_bg_transparent=True)
        # Empty map with transparent background
        out_trans = os.path.join(self.export_dir, "transparent.png")
        ok = ProjectIO.export_png(project, self.render_engine, out_trans, transparent_bg=True)
        self.assertTrue(ok)

        qimg = QImage(out_trans)
        alpha = qimg.pixelColor(10, 10).alpha()
        self.assertEqual(alpha, 0)  # Pure transparent

    # 14. Czy ukryte warstwy nie pojawiają się w eksporcie.
    def test_14_hidden_layers_excluded_from_export(self):
        project = Project(map_width=4, map_height=4, tile_size=32, is_bg_transparent=True)
        self.asset_mgr.import_folder(self.test_dir)
        grass = self.asset_mgr.search_assets("grass_01")[0]

        # Place tile on active layer, then hide the layer
        active = project.get_active_layer()
        active.set_tile(0, 0, MapItem(asset_id=grass.id, col=0, row=0))
        active.visible = False

        out_hidden = os.path.join(self.export_dir, "hidden_layer_test.png")
        ProjectIO.export_png(project, self.render_engine, out_hidden, transparent_bg=True)

        qimg = QImage(out_hidden)
        # Tile was hidden, so pixel at (16, 16) should remain transparent (alpha 0)
        self.assertEqual(qimg.pixelColor(16, 16).alpha(), 0)

    # 15. Czy aplikacja działa poprawnie przy dużej liczbie zasobów.
    def test_15_performance_with_many_assets(self):
        # Generate and import 150 simulated assets
        bulk_dir = os.path.join(self.test_dir, "BulkTest")
        os.makedirs(bulk_dir, exist_ok=True)
        from PIL import Image
        for i in range(150):
            p = os.path.join(bulk_dir, f"bulk_tile_{i:03d}.png")
            if not os.path.exists(p):
                img = Image.new("RGBA", (32, 32), (i % 255, (i * 2) % 255, (i * 3) % 255, 255))
                img.save(p)

        res = self.asset_mgr.import_folder(bulk_dir)
        self.assertGreaterEqual(len(self.asset_mgr.assets), 150)

        # Search should be near instantaneous
        search_results = self.asset_mgr.search_assets("bulk_tile_05")
        self.assertGreaterEqual(len(search_results), 1)

        # MainWindow instantiates and operates cleanly
        window = MainWindow()
        window.asset_manager.import_folder(bulk_dir)
        window.asset_library.refresh_categories()
        window.asset_library.refresh_assets_list()
        self.assertGreaterEqual(window.asset_library.asset_list.count(), 150)
        window.close()


if __name__ == "__main__":
    unittest.main()
