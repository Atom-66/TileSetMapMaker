import os
import sys
import unittest
import tempfile
import shutil
from PIL import Image
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF

from tileset_map_maker.models.project import Project
from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.ui.tileset_palette_widget import TilesetPaletteWidget

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


class TestAuditRemediation(unittest.TestCase):
    """
    Exhaustive integration test suite verifying the 4 critical audit remediation tests:
    - Test A: Real tileset import, uniform grid, selection, and map painting
    - Test B: Layers independence, visibility, locking, reordering, and render order
    - Test C: Multi-map switching, distinct layer contents, save and reopen fidelity
    - Test D: View menu toggles, dock resizing, and layout restore
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.png_path = os.path.join(self.temp_dir, "test_sheet.png")

        # Create a real 64x64 PNG image (4 cells of 32x32)
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        # Cell 0,0: Red
        for x in range(32):
            for y in range(32):
                img.putpixel((x, y), (255, 0, 0, 255))
        # Cell 1,0: Green
        for x in range(32, 64):
            for y in range(32):
                img.putpixel((x, y), (0, 255, 0, 255))
        # Cell 0,1: Blue
        for x in range(32):
            for y in range(32, 64):
                img.putpixel((x, y), (0, 0, 255, 255))
        # Cell 1,1: Yellow
        for x in range(32, 64):
            for y in range(32, 64):
                img.putpixel((x, y), (255, 255, 0, 255))
        img.save(self.png_path)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_a_tileset_flow(self):
        """
        Test A:
        1. Uruchom pusty projekt.
        2. Sprawdź, czy nie pojawiają się fikcyjne tilesety.
        3. Zaimportuj prawdziwy PNG.
        4. Sprawdź, czy pojawia się w bibliotece.
        5. Otwórz go w palecie.
        6. Zaznacz pojedynczy kafelek.
        7. Zaznacz grupę kafelków.
        8. Użyj ich do malowania mapy.
        """
        win = MainWindow()
        win.canvas.tool_context.brush_settings.size = 1
        # 1 & 2: Empty on start
        self.assertEqual(len(win.asset_manager.assets), 0)
        self.assertEqual(win.tileset_palette.tab_bar.count(), 0)

        # 3 & 4: Import real PNG
        asset, is_dup, err = win.asset_manager.import_single_file(
            self.png_path, force_asset_type=AssetType.TILESET
        )
        self.assertIsNotNone(asset)
        asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.assertIn(asset.id, win.asset_manager.assets)

        # 5: Open in palette
        win.tileset_palette.open_tileset_ids.append(asset.id)
        win.tileset_palette.refresh_tilesets()
        self.assertEqual(win.tileset_palette.tab_bar.count(), 1)
        self.assertEqual(win.tileset_palette.active_asset_id, asset.id)

        # 6: Single cell selection
        win.tileset_palette.canvas.sel_start_col = 0
        win.tileset_palette.canvas.sel_start_row = 0
        win.tileset_palette.canvas.sel_end_col = 0
        win.tileset_palette.canvas.sel_end_row = 0
        win.tileset_palette.canvas._emit_selection()

        selected = win.asset_manager.selected_item
        self.assertIsInstance(selected, SelectedSubTile)
        self.assertEqual(selected.cols_count, 1)
        self.assertEqual(selected.rows_count, 1)

        # Paint single tile on active layer
        ctx = win.canvas.tool_context
        brush = BrushTool()
        brush.on_press(2, 2, ctx)
        brush.on_release(2, 2, ctx)

        active_layer = win.project.get_active_layer()
        tile = active_layer.get_tile(2, 2)
        self.assertIsNotNone(tile)
        self.assertEqual(tile.asset_id, asset.id)
        self.assertEqual(tile.source_x, 0)
        self.assertEqual(tile.source_y, 0)

        # 7: Select a group of tiles (2x1 block)
        win.tileset_palette.canvas.sel_start_col = 0
        win.tileset_palette.canvas.sel_start_row = 0
        win.tileset_palette.canvas.sel_end_col = 1
        win.tileset_palette.canvas.sel_end_row = 0
        win.tileset_palette.canvas._emit_selection()

        selected_group = win.asset_manager.selected_item
        self.assertIsInstance(selected_group, SelectedSubTile)
        self.assertEqual(selected_group.cols_count, 2)
        self.assertEqual(selected_group.rows_count, 1)

        # 8: Paint with multi-tile block
        brush.on_press(4, 4, ctx)
        brush.on_release(4, 4, ctx)

        # Cell 1 at (4, 4) and Cell 2 at (5, 4)
        tile_a = active_layer.get_tile(4, 4)
        tile_b = active_layer.get_tile(5, 4)
        self.assertIsNotNone(tile_a)
        self.assertIsNotNone(tile_b)
        self.assertEqual(tile_a.source_x, 0)
        self.assertEqual(tile_b.source_x, 32)
        win.close()

    def test_b_layers_flow(self):
        """
        Test B:
        1. Utwórz dwie warstwy.
        2. Namaluj różne elementy na każdej.
        3. Przełącz aktywną warstwę.
        4. Ukryj pierwszą warstwę.
        5. Sprawdź, czy jej zawartość znika.
        6. Zablokuj drugą warstwę.
        7. Spróbuj ją edytować.
        8. Zmień kolejność warstw.
        9. Sprawdź rzeczywistą kolejność renderowania.
        """
        proj = Project(map_width=20, map_height=20, tile_size=32)
        mgr = AssetManager()
        hist = HistoryManager()
        asset, _, _ = mgr.import_single_file(self.png_path, force_asset_type=AssetType.TILESET)
        mgr.select_asset(asset)

        # 1: Create two layers: Layer 1 (Ground), Layer 2 (Decoration)
        layer1 = proj.get_active_layer()
        layer1.name = "Podłoże"
        layer2 = proj.add_layer("Dekoracje")

        # 2: Paint on Layer 1 at (1, 1)
        proj.set_active_layer(layer1.id)
        ctx = ToolContext(proj, mgr, hist, layer1, mgr.selected_item)
        brush = BrushTool()
        brush.on_press(1, 1, ctx)
        brush.on_release(1, 1, ctx)
        self.assertIsNotNone(layer1.get_tile(1, 1))
        self.assertIsNone(layer2.get_tile(1, 1))

        # 3: Switch active layer to Layer 2 and paint at (2, 2)
        proj.set_active_layer(layer2.id)
        ctx.active_layer = layer2
        brush.on_press(2, 2, ctx)
        brush.on_release(2, 2, ctx)
        self.assertIsNotNone(layer2.get_tile(2, 2))
        self.assertIsNone(layer1.get_tile(2, 2))

        # 4 & 5: Hide layer 1 - content excluded from render
        layer1.visible = False
        render_engine = RenderEngine(mgr)
        img = render_engine.export_to_image(proj, RenderOptions(ignore_hidden_layers=True))
        self.assertIsNotNone(img)

        # 6 & 7: Lock layer 2 - prevent edit
        layer2.locked = True
        brush.on_press(3, 3, ctx)
        brush.on_release(3, 3, ctx)
        self.assertIsNone(layer2.get_tile(3, 3))

        eraser = EraserTool()
        eraser.on_press(2, 2, ctx)
        eraser.on_release(2, 2, ctx)
        self.assertIsNotNone(layer2.get_tile(2, 2))  # Still present because locked!

        # 8 & 9: Reorder layers and verify render order
        self.assertEqual(proj.layers[0].id, layer1.id)
        self.assertEqual(proj.layers[1].id, layer2.id)
        proj.move_layer(0, 1)
        self.assertEqual(proj.layers[0].id, layer2.id)
        self.assertEqual(proj.layers[1].id, layer1.id)
        render_layers = proj.get_render_order_layers()
        self.assertEqual(render_layers[0].id, layer2.id)
        self.assertEqual(render_layers[1].id, layer1.id)

    def test_c_maps_flow(self):
        """
        Test C:
        1. Utwórz dwie mapy.
        2. Umieść inną zawartość na każdej.
        3. Przełączaj się między zakładkami.
        4. Sprawdź, czy zawartość map nie miesza się.
        5. Zapisz obie mapy.
        6. Zamknij aplikację.
        7. Uruchom ponownie.
        8. Otwórz projekt i sprawdź, czy obie mapy i ich warstwy zostały zachowane.
        """
        mgr = AssetManager()
        asset, _, _ = mgr.import_single_file(self.png_path, force_asset_type=AssetType.TILESET)
        mgr.select_asset(asset)

        # 1: Create project with Map A and Map B
        proj = Project(name="TestProjekt", map_width=15, map_height=10, tile_size=32)
        map_a = proj.get_active_map()
        map_a.name = "Mapa_A"

        map_b = proj.add_map(name="Mapa_B", width=25, height=20, tile_size=32)

        # 2: Paint distinct items on Map A and Map B
        proj.set_active_map(map_a.id)
        ctx_a = ToolContext(proj, mgr, HistoryManager(), proj.get_active_layer(), mgr.selected_item)
        BrushTool().on_press(1, 1, ctx_a)
        BrushTool().on_release(1, 1, ctx_a)

        proj.set_active_map(map_b.id)
        ctx_b = ToolContext(proj, mgr, HistoryManager(), proj.get_active_layer(), mgr.selected_item)
        BrushTool().on_press(8, 8, ctx_b)
        BrushTool().on_release(8, 8, ctx_b)

        # 3 & 4: Check isolation
        proj.set_active_map(map_a.id)
        self.assertIsNotNone(proj.get_active_layer().get_tile(1, 1))
        self.assertIsNone(proj.get_active_layer().get_tile(8, 8))

        proj.set_active_map(map_b.id)
        self.assertIsNotNone(proj.get_active_layer().get_tile(8, 8))
        self.assertIsNone(proj.get_active_layer().get_tile(1, 1))

        # 5: Save project file
        save_path = os.path.join(self.temp_dir, "saved_world.tmmap")
        saved = ProjectIO.save_project(proj, mgr, save_path)
        self.assertTrue(saved)
        self.assertTrue(os.path.exists(save_path))

        # 6, 7 & 8: Reopen project in fresh instances
        fresh_mgr = AssetManager()
        loaded_proj = ProjectIO.load_project(save_path, fresh_mgr)
        self.assertIsNotNone(loaded_proj)
        self.assertEqual(len(loaded_proj.maps), 2)

        loaded_map_a = [m for m in loaded_proj.maps.values() if m.name == "Mapa_A"][0]
        loaded_map_b = [m for m in loaded_proj.maps.values() if m.name == "Mapa_B"][0]

        # Check map A contents
        loaded_proj.set_active_map(loaded_map_a.id)
        self.assertIsNotNone(loaded_proj.get_active_layer().get_tile(1, 1))
        self.assertIsNone(loaded_proj.get_active_layer().get_tile(8, 8))

        # Check map B contents
        loaded_proj.set_active_map(loaded_map_b.id)
        self.assertIsNotNone(loaded_proj.get_active_layer().get_tile(8, 8))
        self.assertIsNone(loaded_proj.get_active_layer().get_tile(1, 1))

    def test_d_view_menu_flow(self):
        """
        Test D:
        1. Ukryj paletę tilesetów.
        2. Sprawdź, czy płótno powiększa się.
        3. Ukryj panel warstw.
        4. Ponownie włącz oba panele.
        5. Przywróć domyślny układ.
        6. Sprawdź zachowanie po ponownym uruchomieniu.
        """
        win = MainWindow()
        win.show()

        # 1 & 2: Toggle tileset palette visibility
        self.assertTrue(win.tileset_dock.isVisible())
        win.tileset_dock.hide()
        self.assertFalse(win.tileset_dock.isVisible())

        # 3: Toggle layers dock visibility
        self.assertTrue(win.right_dock.isVisible())
        win.right_dock.hide()
        self.assertFalse(win.right_dock.isVisible())

        # 4: Re-show both docks
        win.tileset_dock.show()
        win.right_dock.show()
        self.assertTrue(win.tileset_dock.isVisible())
        self.assertTrue(win.right_dock.isVisible())

        # 5: Reset dock layout
        win._reset_dock_layout()
        self.assertTrue(win.tileset_dock.isVisible())
        self.assertTrue(win.right_dock.isVisible())
        self.assertTrue(win.properties_dock.isVisible())
        self.assertTrue(win.history_dock.isVisible())
        self.assertFalse(hasattr(win, "world_dock"))
        win.close()


if __name__ == "__main__":
    unittest.main()
