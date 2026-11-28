import os
import sys
import tempfile
import shutil
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QImage, QColor, QPainter, QPixmap

from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig
from tileset_map_maker.models.project import Project
from tileset_map_maker.models.layer import ItemType
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.core.rpg_autotile import (
    RPGAutotile,
    AutotileFormat,
    SelectedAutotile,
    synthesize_from_single_tile,
    synthesize_from_tileset_context,
    create_rpg_autotile_from_tile,
)
from tileset_map_maker.ui.dialogs.path_generator_dialog import (
    PathGeneratorDialog,
    TilesetSheetCanvas,
)
from tileset_map_maker.ui.main_window import MainWindow


class TestOneTilePathsSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.asset_mgr = AssetManager()
        self.autotile_engine = AutoTileEngine()
        self.history_mgr = HistoryManager()
        self.project = Project(20, 20, 32)
        self.layer = self.project.get_active_layer()

        # Create two sample tileset sheets
        # Sheet 1: 128x128 (4x4 tiles of 32x32)
        self.sheet1_path = os.path.join(self.test_dir, "sheet1.png")
        img1 = QImage(128, 128, QImage.Format.Format_ARGB32)
        img1.fill(QColor(60, 140, 60))  # grass base
        p = QPainter(img1)
        # Dirt tile at col 1, row 1
        p.fillRect(32, 32, 32, 32, QColor(160, 110, 60))
        # Stone tile at col 2, row 3
        p.fillRect(64, 96, 32, 32, QColor(120, 120, 130))
        p.end()
        img1.save(self.sheet1_path)

        self.asset1, _, _ = self.asset_mgr.import_single_file(
            self.sheet1_path, target_category_path="Terrains", force_asset_type=AssetType.TILESET
        )
        self.asset1.name = "Sheet 1 (Grass & Dirt)"
        self.asset1.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

        # Sheet 2: 96x96 (3x3 tiles of 32x32)
        self.sheet2_path = os.path.join(self.test_dir, "sheet2.png")
        img2 = QImage(96, 96, QImage.Format.Format_ARGB32)
        img2.fill(QColor(40, 100, 200))  # water base
        img2.save(self.sheet2_path)
        self.asset2, _, _ = self.asset_mgr.import_single_file(
            self.sheet2_path, target_category_path="Water", force_asset_type=AssetType.TILESET
        )
        self.asset2.name = "Sheet 2 (Water)"
        self.asset2.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Otwarcie Paths
    def test_01_open_paths_dialog(self):
        dlg = PathGeneratorDialog(self.autotile_engine, self.asset_mgr)
        self.assertIsNotNone(dlg)
        self.assertGreaterEqual(dlg.width(), 800)
        self.assertGreaterEqual(dlg.height(), 600)
        dlg.close()

    # 2. Wyświetlenie istniejącej biblioteki tilesetów
    def test_02_display_existing_tileset_library(self):
        dlg = PathGeneratorDialog(self.autotile_engine, self.asset_mgr)
        self.assertEqual(dlg.cmb_tileset.count(), 2)
        items_data = [dlg.cmb_tileset.itemData(i) for i in range(dlg.cmb_tileset.count())]
        self.assertIn(self.asset1.id, items_data)
        self.assertIn(self.asset2.id, items_data)
        dlg.close()

    # 3. Wybranie różnych tilesetów
    def test_03_switch_different_tilesets(self):
        dlg = PathGeneratorDialog(self.autotile_engine, self.asset_mgr)
        # Select first tileset
        idx1 = dlg.cmb_tileset.findData(self.asset1.id)
        dlg.cmb_tileset.setCurrentIndex(idx1)
        self.assertEqual(dlg.selected_asset.id, self.asset1.id)
        self.assertEqual(dlg.sheet_canvas.pixmap.width(), 128)
        self.assertEqual(dlg.sheet_canvas.pixmap.height(), 128)

        # Switch to second tileset
        idx2 = dlg.cmb_tileset.findData(self.asset2.id)
        dlg.cmb_tileset.setCurrentIndex(idx2)
        self.assertEqual(dlg.selected_asset.id, self.asset2.id)
        self.assertEqual(dlg.sheet_canvas.pixmap.width(), 96)
        self.assertEqual(dlg.sheet_canvas.pixmap.height(), 96)
        dlg.close()

    # 4. Zaznaczenie dowolnego kafelka
    def test_04_select_arbitrary_tile(self):
        dlg = PathGeneratorDialog(self.autotile_engine, self.asset_mgr)
        idx1 = dlg.cmb_tileset.findData(self.asset1.id)
        dlg.cmb_tileset.setCurrentIndex(idx1)

        # Select tile at col 1, row 1
        dlg.sheet_canvas.set_selected_tile(1, 1)
        dlg._on_tile_clicked(1, 1)
        self.assertEqual(dlg.selected_col, 1)
        self.assertEqual(dlg.selected_row, 1)
        coords_1 = dlg.lbl_tile_coords.text()
        self.assertTrue(
            "column: 1, row: 1" in coords_1 or "kolumna: 1, wiersz: 1" in coords_1,
            f"Unexpected coordinates label: {coords_1!r}",
        )

        # Select tile at col 2, row 3
        dlg.sheet_canvas.set_selected_tile(2, 3)
        dlg._on_tile_clicked(2, 3)
        self.assertEqual(dlg.selected_col, 2)
        self.assertEqual(dlg.selected_row, 3)
        coords_2 = dlg.lbl_tile_coords.text()
        self.assertTrue(
            "column: 2, row: 3" in coords_2 or "kolumna: 2, wiersz: 3" in coords_2,
            f"Unexpected coordinates label: {coords_2!r}",
        )
        dlg.close()

    # 5. Wygenerowanie Autotile z wybranego kafelka
    def test_05_generate_autotile_from_tile(self):
        dlg = PathGeneratorDialog(self.autotile_engine, self.asset_mgr)
        idx1 = dlg.cmb_tileset.findData(self.asset1.id)
        dlg.cmb_tileset.setCurrentIndex(idx1)
        dlg._on_tile_clicked(1, 1)  # dirt tile

        autotile = dlg.current_autotile
        self.assertIsNotNone(autotile)
        self.assertEqual(autotile.source_asset_id, self.asset1.id)
        self.assertEqual(autotile.source_col, 1)
        self.assertEqual(autotile.source_row, 1)
        # Check atlas was synthesized with 47 combinations
        self.assertFalse(autotile.atlas_pixmap.isNull())
        self.assertEqual(autotile.atlas_pixmap.width(), 8 * 32)
        self.assertEqual(autotile.atlas_pixmap.height(), 6 * 32)
        dlg.close()

    # 6. Podgląd wygenerowanej ścieżki (Sandbox)
    def test_06_live_path_preview_sandbox(self):
        dlg = PathGeneratorDialog(self.autotile_engine, self.asset_mgr)
        idx1 = dlg.cmb_tileset.findData(self.asset1.id)
        dlg.cmb_tileset.setCurrentIndex(idx1)
        dlg._on_tile_clicked(1, 1)

        self.assertIsNotNone(dlg.sandbox.active_rpg_autotile)
        self.assertGreater(len(dlg.sandbox.active_cells), 0)

        # Test presets
        dlg._load_sample_cross()
        self.assertGreater(len(dlg.sandbox.active_cells), 5)
        dlg._load_sample_loop()
        self.assertGreater(len(dlg.sandbox.active_cells), 8)
        dlg._clear_sandbox()
        self.assertEqual(len(dlg.sandbox.active_cells), 0)
        dlg.close()

    # 7. Malowanie ścieżek o różnych kształtach
    def test_07_paint_paths_various_shapes(self):
        # Create an autotile from dirt tile (col 1, row 1)
        sheet_img = self.asset_mgr.get_pixmap(self.asset1.id).toImage()
        at = create_rpg_autotile_from_tile(
            name="Dirt Path",
            source_asset_id=self.asset1.id,
            sheet=sheet_img,
            col=1,
            row=1,
            tile_size=32,
            mode="single_tile",
            edge_style="organic",
        )
        self.autotile_engine.register_rpg_autotile(at)

        # Paint horizontal line
        tool = BrushTool()
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=BrushSettings(),
            autotile_engine=self.autotile_engine,
        )
        self.asset_mgr.selected_item = SelectedAutotile(at)

        # Stroke from (3, 5) to (7, 5)
        tool.on_press(3, 5, ctx)
        for c in range(4, 8):
            tool.on_drag(c, 5, ctx)
        tool.on_release(7, 5, ctx)

        # Check all cells exist on layer
        for c in range(3, 8):
            item = self.layer.get_tile(c, 5)
            self.assertIsNotNone(item, f"Cell ({c}, 5) should have a path item")
            self.assertEqual(item.asset_id, at.id)
            self.assertTrue(item.is_auto_tiled)

    # 8. Automatyczne aktualizowanie krawędzi i narożników
    def test_08_auto_update_edges_and_corners(self):
        sheet_img = self.asset_mgr.get_pixmap(self.asset1.id).toImage()
        at = create_rpg_autotile_from_tile(
            name="Dirt Path",
            source_asset_id=self.asset1.id,
            sheet=sheet_img,
            col=1,
            row=1,
            tile_size=32,
            mode="single_tile",
        )
        self.autotile_engine.register_rpg_autotile(at)

        tool = BrushTool()
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=BrushSettings(),
            autotile_engine=self.autotile_engine,
        )
        self.asset_mgr.selected_item = SelectedAutotile(at)

        # Paint a corner at (5, 5) heading North to (5, 4) and East to (6, 5)
        # 1. Paint (5, 5)
        tool.on_press(5, 5, ctx)
        tool.on_release(5, 5, ctx)
        # 2. Paint (5, 4)
        tool.on_press(5, 4, ctx)
        tool.on_release(5, 4, ctx)
        # 3. Paint (6, 5)
        tool.on_press(6, 5, ctx)
        tool.on_release(6, 5, ctx)

        corner_item = self.layer.get_tile(5, 5)
        self.assertIsNotNone(corner_item)
        self.assertEqual(corner_item.asset_id, at.id)
        # Verify corner slice coordinates differ from isolated 1x1 island
        isolated_slice = at.get_tile_slice_for_mask(0)
        self.assertIsNotNone(corner_item.source_x)

    # 9. Usuwanie fragmentów i ponowne łączenie ścieżek
    def test_09_erase_and_reconnect_paths(self):
        sheet_img = self.asset_mgr.get_pixmap(self.asset1.id).toImage()
        at = create_rpg_autotile_from_tile(
            name="Dirt Path",
            source_asset_id=self.asset1.id,
            sheet=sheet_img,
            col=1,
            row=1,
            tile_size=32,
        )
        self.autotile_engine.register_rpg_autotile(at)

        tool = BrushTool()
        eraser = EraserTool()
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=BrushSettings(),
            autotile_engine=self.autotile_engine,
        )
        self.asset_mgr.selected_item = SelectedAutotile(at)

        # Paint 3 tiles: (4, 4), (5, 4), (6, 4)
        for c in (4, 5, 6):
            tool.on_press(c, 4, ctx)
            tool.on_release(c, 4, ctx)

        # Erase middle tile (5, 4)
        eraser.on_press(5, 4, ctx)
        eraser.on_release(5, 4, ctx)

        self.assertIsNone(self.layer.get_tile(5, 4))
        # (4, 4) should still be on layer
        item_w = self.layer.get_tile(4, 4)
        self.assertIsNotNone(item_w)
        self.assertEqual(item_w.asset_id, at.id)

    # 10. Zapisywanie i odtwarzanie wygenerowanych zestawów
    def test_10_save_and_restore_generated_sets(self):
        sheet_img = self.asset_mgr.get_pixmap(self.asset1.id).toImage()
        at = create_rpg_autotile_from_tile(
            name="Custom Sand Path",
            source_asset_id=self.asset1.id,
            sheet=sheet_img,
            col=2,
            row=3,
            tile_size=32,
            mode="single_tile",
            edge_style="dark_outline",
            terrain_type="sand",
            seed=123,
        )
        d = at.to_dict()
        self.assertEqual(d["name"], "Custom Sand Path")
        self.assertEqual(d["source_asset_id"], self.asset1.id)
        self.assertEqual(d["source_col"], 2)
        self.assertEqual(d["source_row"], 3)
        self.assertEqual(d["generation_mode"], "single_tile")
        self.assertEqual(d["edge_style"], "dark_outline")

        # Restore from dict
        restored = RPGAutotile.from_dict(d)
        self.assertEqual(restored.name, "Custom Sand Path")
        self.assertEqual(restored.source_asset_id, self.asset1.id)
        self.assertEqual(restored.source_col, 2)
        self.assertEqual(restored.source_row, 3)

        # Rebuild atlas via asset manager
        restored.load_source_image(self.asset_mgr)
        self.assertFalse(restored.atlas_pixmap.isNull())

    # 11. Zapis i ponowne otwarcie map
    def test_11_save_and_reopen_map_with_paths(self):
        sheet_img = self.asset_mgr.get_pixmap(self.asset1.id).toImage()
        at = create_rpg_autotile_from_tile(
            name="Dirt Path",
            source_asset_id=self.asset1.id,
            sheet=sheet_img,
            col=1,
            row=1,
            tile_size=32,
        )
        self.autotile_engine.register_rpg_autotile(at)

        tool = BrushTool()
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=BrushSettings(),
            autotile_engine=self.autotile_engine,
        )
        self.asset_mgr.selected_item = SelectedAutotile(at)
        tool.on_press(2, 2, ctx)
        tool.on_release(2, 2, ctx)

        # Save to .tmmap
        save_path = os.path.join(self.test_dir, "map_test.tmmap")
        success = ProjectIO.save_project(self.project, self.asset_mgr, save_path, self.autotile_engine)
        self.assertTrue(success, "Project save failed")

        # Load back
        loaded_proj = ProjectIO.load_project(save_path, self.asset_mgr, self.autotile_engine)
        self.assertIsNotNone(loaded_proj)
        loaded_layer = loaded_proj.get_active_layer()
        loaded_item = loaded_layer.get_tile(2, 2)
        self.assertIsNotNone(loaded_item)
        self.assertEqual(loaded_item.asset_id, at.id)

    # 12. Obsługa błędnych lub niekompletnych danych
    def test_12_handling_invalid_or_incomplete_data(self):
        # Empty asset manager
        empty_mgr = AssetManager()
        dlg = PathGeneratorDialog(self.autotile_engine, empty_mgr)
        self.assertFalse(dlg.btn_accept.isEnabled())
        info_txt = dlg.lbl_tileset_info.text()
        self.assertTrue(
            "No imported tilesets" in info_txt or "Brak zaimportowanych tilesetów" in info_txt,
            f"Unexpected empty tilesets label: {info_txt!r}",
        )
        dlg.close()

        # Out-of-bounds coordinate synthesis
        sheet_img = self.asset_mgr.get_pixmap(self.asset1.id).toImage()
        src_img, fmt, desc = synthesize_from_tileset_context(
            sheet_img, 999, 999, 32, mode="auto"
        )
        self.assertIsNotNone(src_img)
        self.assertFalse(src_img.isNull())
        self.assertIn("poza zakresem", desc)

    # 13. Brak crashy podczas całego procesu (End-to-End)
    def test_13_no_crashes_end_to_end(self):
        dlg = PathGeneratorDialog(self.autotile_engine, self.asset_mgr)
        # Select tileset, pick tile, accept
        idx = dlg.cmb_tileset.findData(self.asset1.id)
        dlg.cmb_tileset.setCurrentIndex(idx)
        dlg._on_tile_clicked(2, 3)
        dlg._accept_and_paint()

        # Verify active autotile registered in engine
        active_at = self.autotile_engine.get_active_rpg_autotile()
        self.assertIsNotNone(active_at)
        self.assertEqual(active_at.source_col, 2)
        self.assertEqual(active_at.source_row, 3)

    # 14. Weryfikacja deselect w TilesetCanvas i aktywacji z TilesetPaletteWidget
    def test_14_tileset_palette_deselect_and_selection(self):
        from tileset_map_maker.ui.tileset_palette_widget import TilesetPaletteWidget, TilesetCanvas
        palette = TilesetPaletteWidget(self.asset_mgr)
        palette.autotile_engine = self.autotile_engine
        palette.set_active_asset(self.asset1)
        self.assertTrue(hasattr(palette.canvas, "deselect"))
        self.assertTrue(palette.canvas.has_selection)

        # Create and select autotile
        sheet = self.asset_mgr.get_pixmap(self.asset1.id).toImage()
        at = create_rpg_autotile_from_tile(
            "test_p", self.asset1.id, sheet, 1, 1, 32, mode="auto", terrain_type="path"
        )
        self.autotile_engine.register_rpg_autotile(at)
        palette.refresh_autotiles()
        palette._select_autotile(at)

        # Selection on canvas should be cleared
        self.assertFalse(palette.canvas.has_selection)
        self.assertEqual(palette.selected_autotile_id, at.id)

        # Calling deselect directly should not fail
        palette.canvas.deselect()
        self.assertFalse(palette.canvas.has_selection)
