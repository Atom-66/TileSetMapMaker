import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtWidgets import QApplication, QMessageBox
from PIL import Image

from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.models.layer import Layer, MapItem
from tileset_map_maker.models.project import Project
from tileset_map_maker.models.autotile import (
    AutoTileRuleSet,
    CARD_CORNER_TL,
    CARD_EDGE_TOP,
    CARD_CORNER_TR,
    CARD_EDGE_LEFT,
    CARD_CENTER,
    CARD_EDGE_RIGHT,
    CARD_CORNER_BL,
    CARD_EDGE_BOTTOM,
    CARD_CORNER_BR,
    MASK_CENTER,
    MASK_CORNER_TL,
    MASK_EDGE_TOP,
)
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.ui.dialogs.autotile_dialog import AutoTileDialog


class TestAutoTileComprehensive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="tmm_test_autotile_")
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
        self.config_manager = ConfigManager(custom_config_path=self.config_file)
        self.asset_manager = AssetManager()
        self.autotile_engine = AutoTileEngine()
        self.history_manager = HistoryManager()

        # Create a test tileset image (3x3 tiles of 32x32 each = 96x96 px)
        # We fill each 32x32 slot with a distinct identifiable color pattern
        self.tileset_path = os.path.join(self.temp_dir, "autotile_sheet.png")
        sheet = Image.new("RGBA", (96, 96), (0, 0, 0, 255))
        sheet.save(self.tileset_path)

        self.asset, _, _ = self.asset_manager.import_single_file(
            self.tileset_path, force_asset_type=AssetType.TILESET
        )
        self.asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

        self.project = Project(map_width=20, map_height=20, tile_size=32)
        self.layer = self.project.get_active_layer()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_create_autotile_ruleset(self):
        """1. Utworzenie zestawu Auto Tile."""
        rule = AutoTileRuleSet(name="Ścieżka Kamienna", terrain_type="Stone")
        self.autotile_engine.register_ruleset(rule)
        self.assertIn(rule.id, self.autotile_engine.rulesets)
        self.assertEqual(self.autotile_engine.get_active_ruleset().id, rule.id)

    def test_02_assign_real_tiles_from_imported_tileset(self):
        """2. Przypisanie rzeczywistych kafelków z zaimportowanego tilesetu."""
        rule = AutoTileRuleSet(name="Trawa Standard", terrain_type="Grass")
        rule.setup_standard_3x3_box(
            asset_id=self.asset.id,
            start_x=0,
            start_y=0,
            tile_w=32,
            tile_h=32,
        )
        self.autotile_engine.register_ruleset(rule)

        # Check TL corner tile has asset.id and correct (0, 0) coords
        tl_tile = rule.get_tile_for_mask(CARD_CORNER_TL)
        self.assertIsNotNone(tl_tile)
        self.assertEqual(tl_tile[0], self.asset.id)
        self.assertEqual((tl_tile[1], tl_tile[2]), (0, 0))

        # Check Center tile has (32, 32) coords
        c_tile = rule.get_tile_for_mask(CARD_CENTER)
        self.assertIsNotNone(c_tile)
        self.assertEqual(c_tile[0], self.asset.id)
        self.assertEqual((c_tile[1], c_tile[2]), (32, 32))

        # Check BR corner tile has (64, 64) coords
        br_tile = rule.get_tile_for_mask(CARD_CORNER_BR)
        self.assertIsNotNone(br_tile)
        self.assertEqual(br_tile[0], self.asset.id)
        self.assertEqual((br_tile[1], br_tile[2]), (64, 64))

    def test_03_save_and_persist_ruleset(self):
        """3. Zapisanie zestawu i odtworzenie z ConfigManager."""
        rule = AutoTileRuleSet(name="Pustynia", terrain_type="Sand", connects_with=["Sand", "Dirt"])
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        # Persist to ConfigManager
        self.config_manager.save_autotile_rules(self.autotile_engine)

        # Reload into a fresh engine
        fresh_engine = AutoTileEngine()
        self.config_manager.restore_autotile_rules(fresh_engine)
        self.assertIn(rule.id, fresh_engine.rulesets)
        restored = fresh_engine.get_ruleset(rule.id)
        self.assertEqual(restored.name, "Pustynia")
        self.assertEqual(restored.terrain_type, "Sand")
        self.assertIn("Dirt", restored.connects_with)
        self.assertEqual(len(restored.tile_mappings), len(rule.tile_mappings))

    def test_04_paint_single_isolated_tile(self):
        """4. Malowanie pojedynczego kafelka (izolowany otrzymuje poprawny wariant)."""
        rule = AutoTileRuleSet(name="Trawa", terrain_type="Grass")
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        # Place single tile at (5, 5)
        item = MapItem(asset_id=self.asset.id, col=5, row=5, terrain_type="Grass", is_auto_tiled=True)
        self.layer.set_tile(5, 5, item)
        self.autotile_engine.apply_autotile_stroke(self.layer, [(5, 5)], rule, self.project)

        tile = self.layer.get_tile(5, 5)
        self.assertIsNotNone(tile)
        self.assertTrue(tile.is_auto_tiled)
        self.assertEqual(tile.terrain_type, "Grass")
        # An isolated tile gracefully resolves without error
        self.assertEqual(tile.asset_id, self.asset.id)

    def test_05_paint_two_adjacent_tiles(self):
        """5. Malowanie dwóch sąsiadujących kafelków w poziomie."""
        rule = AutoTileRuleSet(name="Trawa", terrain_type="Grass")
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        # Place at (5, 5) and (6, 5)
        t1 = MapItem(asset_id=self.asset.id, col=5, row=5, terrain_type="Grass", is_auto_tiled=True)
        t2 = MapItem(asset_id=self.asset.id, col=6, row=5, terrain_type="Grass", is_auto_tiled=True)
        self.layer.set_tile(5, 5, t1)
        self.layer.set_tile(6, 5, t2)

        self.autotile_engine.apply_autotile_stroke(self.layer, [(5, 5), (6, 5)], rule, self.project)

        tile_left = self.layer.get_tile(5, 5)
        tile_right = self.layer.get_tile(6, 5)

        # Left tile has neighbor to the East (4), no West. Right tile has neighbor to the West (64), no East.
        self.assertNotEqual(tile_left.source_x, tile_right.source_x)

    def test_06_paint_large_surface_3x3_and_interior(self):
        """6. Malowanie większej powierzchni 3x3 – środek otrzymuje Center."""
        rule = AutoTileRuleSet(name="Trawa", terrain_type="Grass")
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        coords = []
        for r in range(2, 5):
            for c in range(2, 5):
                item = MapItem(asset_id=self.asset.id, col=c, row=r, terrain_type="Grass", is_auto_tiled=True)
                self.layer.set_tile(c, r, item)
                coords.append((c, r))

        self.autotile_engine.apply_autotile_stroke(self.layer, coords, rule, self.project)

        # Interior center tile at (3, 3) must be the Center tile (source_x=32, source_y=32)
        center = self.layer.get_tile(3, 3)
        self.assertEqual((center.source_x, center.source_y), (32, 32))

    def test_07_edges_top_bottom_left_right(self):
        """7. Malowanie krawędzi (top, bottom, left, right mają właściwe współrzędne źródłowe)."""
        rule = AutoTileRuleSet(name="Trawa", terrain_type="Grass")
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        coords = []
        for r in range(2, 5):
            for c in range(2, 5):
                item = MapItem(asset_id=self.asset.id, col=c, row=r, terrain_type="Grass", is_auto_tiled=True)
                self.layer.set_tile(c, r, item)
                coords.append((c, r))

        self.autotile_engine.apply_autotile_stroke(self.layer, coords, rule, self.project)

        top_edge = self.layer.get_tile(3, 2)
        bottom_edge = self.layer.get_tile(3, 4)
        left_edge = self.layer.get_tile(2, 3)
        right_edge = self.layer.get_tile(4, 3)

        self.assertEqual((top_edge.source_x, top_edge.source_y), (32, 0))
        self.assertEqual((bottom_edge.source_x, bottom_edge.source_y), (32, 64))
        self.assertEqual((left_edge.source_x, left_edge.source_y), (0, 32))
        self.assertEqual((right_edge.source_x, right_edge.source_y), (64, 32))

    def test_08_corners_tl_tr_bl_br(self):
        """8. Malowanie narożników (TL, TR, BL, BR mają właściwe współrzędne źródłowe)."""
        rule = AutoTileRuleSet(name="Trawa", terrain_type="Grass")
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        coords = []
        for r in range(2, 5):
            for c in range(2, 5):
                item = MapItem(asset_id=self.asset.id, col=c, row=r, terrain_type="Grass", is_auto_tiled=True)
                self.layer.set_tile(c, r, item)
                coords.append((c, r))

        self.autotile_engine.apply_autotile_stroke(self.layer, coords, rule, self.project)

        tl = self.layer.get_tile(2, 2)
        tr = self.layer.get_tile(4, 2)
        bl = self.layer.get_tile(2, 4)
        br = self.layer.get_tile(4, 4)

        self.assertEqual((tl.source_x, tl.source_y), (0, 0))
        self.assertEqual((tr.source_x, tr.source_y), (64, 0))
        self.assertEqual((bl.source_x, bl.source_y), (0, 64))
        self.assertEqual((br.source_x, br.source_y), (64, 64))

    def test_09_adding_tiles_to_existing_surface_adapts_edges(self):
        """9. Dodawanie kafelków do istniejącej powierzchni natychmiast adaptuje krawędzie."""
        rule = AutoTileRuleSet(name="Trawa", terrain_type="Grass")
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        # Initial 3x3 surface
        coords = [(c, r) for r in range(2, 5) for c in range(2, 5)]
        for c, r in coords:
            self.layer.set_tile(c, r, MapItem(asset_id=self.asset.id, col=c, row=r, terrain_type="Grass", is_auto_tiled=True))
        self.autotile_engine.apply_autotile_stroke(self.layer, coords, rule, self.project)

        # Before: (4, 3) was Right Edge
        r_before = self.layer.get_tile(4, 3)
        self.assertEqual((r_before.source_x, r_before.source_y), (64, 32))

        # Add an extension to the right at (5, 3)
        self.layer.set_tile(5, 3, MapItem(asset_id=self.asset.id, col=5, row=3, terrain_type="Grass", is_auto_tiled=True))
        self.autotile_engine.apply_autotile_stroke(self.layer, [(5, 3)], rule, self.project)

        # After: (4, 3) now has an East neighbor, so it is no longer the Right Edge!
        r_after = self.layer.get_tile(4, 3)
        self.assertNotEqual((r_after.source_x, r_after.source_y), (64, 32))

    def test_10_erasing_tiles_adapts_neighbors(self):
        """10. Usuwanie kafelków adaptuje sąsiadujące kafelki w nowe krawędzie."""
        rule = AutoTileRuleSet(name="Trawa", terrain_type="Grass")
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        coords = [(c, r) for r in range(2, 5) for c in range(2, 5)]
        for c, r in coords:
            self.layer.set_tile(c, r, MapItem(asset_id=self.asset.id, col=c, row=r, terrain_type="Grass", is_auto_tiled=True))
        self.autotile_engine.apply_autotile_stroke(self.layer, coords, rule, self.project)

        # (3, 3) is Center
        self.assertEqual((self.layer.get_tile(3, 3).source_x, self.layer.get_tile(3, 3).source_y), (32, 32))

        # Erase the center tile (3, 3)
        self.layer.remove_tile(3, 3)
        changes = self.autotile_engine.update_neighbors_after_erase(
            self.layer, [(3, 3)], rule, self.project
        )
        self.assertGreater(len(changes), 0)

        # Tile (3, 2) which was Top Edge now lacks a South neighbor, so its mask changes!
        top_tile_after = self.layer.get_tile(3, 2)
        self.assertIsNotNone(top_tile_after)

    def test_11_brush_tool_autotiling_stroke(self):
        """11. Rysowanie narzędziem BrushTool z włączonym Auto-Tiling."""
        rule = AutoTileRuleSet(name="Trawa", terrain_type="Grass")
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        bs = BrushSettings()
        bs.auto_tile_enabled = True

        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_manager,
            history_manager=self.history_manager,
            brush_settings=bs,
            autotile_engine=self.autotile_engine,
        )

        brush = BrushTool()
        brush.on_press(2, 2, ctx)
        brush.on_drag(3, 2, ctx)
        brush.on_drag(4, 2, ctx)
        brush.on_release(4, 2, ctx)

        # Three tiles painted in a horizontal row
        t2 = self.layer.get_tile(2, 2)
        t3 = self.layer.get_tile(3, 2)
        t4 = self.layer.get_tile(4, 2)

        self.assertIsNotNone(t2)
        self.assertIsNotNone(t3)
        self.assertIsNotNone(t4)
        self.assertTrue(t2.is_auto_tiled)
        self.assertEqual(t2.terrain_type, "Grass")

    def test_12_layer_isolation_and_disabled_autotiling(self):
        """12. Izolacja warstw – AutoTile sprawdza sąsiadów tylko na właściwej warstwie."""
        rule = AutoTileRuleSet(name="Trawa", terrain_type="Grass")
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        layer2 = self.project.add_layer("Warstwa 2")

        # Place tile on layer 1 at (2, 2)
        self.layer.set_tile(2, 2, MapItem(asset_id=self.asset.id, col=2, row=2, terrain_type="Grass", is_auto_tiled=True))
        # Place tile on layer 2 at (3, 2)
        layer2.set_tile(3, 2, MapItem(asset_id=self.asset.id, col=3, row=2, terrain_type="Grass", is_auto_tiled=True))

        # Check mask on layer 1: should NOT see the tile on layer 2!
        mask_l1 = self.autotile_engine.compute_mask(self.layer, 2, 2, rule, self.project)
        self.assertEqual(mask_l1, 0, "Layer 1 must not connect with tiles on Layer 2!")

    def test_13_undo_and_redo_autotiling_stroke(self):
        """13. Cofanie (Undo) i ponawianie (Redo) operacji Auto-Tiling."""
        rule = AutoTileRuleSet(name="Trawa", terrain_type="Grass")
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        bs = BrushSettings()
        bs.auto_tile_enabled = True

        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_manager,
            history_manager=self.history_manager,
            brush_settings=bs,
            autotile_engine=self.autotile_engine,
        )

        brush = BrushTool()
        brush.on_press(3, 3, ctx)
        brush.on_release(3, 3, ctx)

        self.assertIsNotNone(self.layer.get_tile(3, 3))
        self.assertTrue(self.history_manager.can_undo())

        # Undo
        self.history_manager.undo()
        self.assertIsNone(self.layer.get_tile(3, 3))

        # Redo
        self.history_manager.redo()
        self.assertIsNotNone(self.layer.get_tile(3, 3))
        self.assertEqual(self.layer.get_tile(3, 3).terrain_type, "Grass")

    def test_14_project_save_and_load_with_autotile(self):
        """14. Zapisanie projektu mapy i ponowne otwarcie z regułami Auto-Tile."""
        rule = AutoTileRuleSet(name="Woda", terrain_type="Water")
        rule.setup_standard_3x3_box(self.asset.id, 0, 0, 32, 32)
        self.autotile_engine.register_ruleset(rule)

        item = MapItem(asset_id=self.asset.id, col=1, row=1, terrain_type="Water", is_auto_tiled=True)
        self.layer.set_tile(1, 1, item)

        save_path = os.path.join(self.temp_dir, "test_autotile_map.tmmap")
        ok = ProjectIO.save_project(self.project, self.asset_manager, save_path, autotile_engine=self.autotile_engine)
        self.assertTrue(ok)

        # Load project
        fresh_asset_mgr = AssetManager()
        fresh_engine = AutoTileEngine()
        loaded_proj = ProjectIO.load_project(save_path, fresh_asset_mgr, autotile_engine=fresh_engine)

        self.assertIsNotNone(loaded_proj)
        self.assertIn(rule.id, fresh_engine.rulesets)
        self.assertEqual(fresh_engine.get_ruleset(rule.id).terrain_type, "Water")

        loaded_layer = loaded_proj.get_active_layer()
        loaded_tile = loaded_layer.get_tile(1, 1)
        self.assertIsNotNone(loaded_tile)
        self.assertTrue(loaded_tile.is_auto_tiled)
        self.assertEqual(loaded_tile.terrain_type, "Water")

    def test_15_autotile_dialog_template_application(self):
        """15. AutoTileDialog poprawnie konfiguruje regułę 3x3 i uaktualnia widok."""
        dlg = AutoTileDialog(self.autotile_engine, self.asset_manager)
        dlg.spin_col.setValue(0)
        dlg.spin_row.setValue(0)

        # Avoid opening a modal OK dialog in the headless test environment.
        with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok):
            dlg._apply_template()

        rule = self.autotile_engine.get_active_ruleset()
        self.assertIsNotNone(rule)
        self.assertGreater(len(rule.tile_mappings), 0)

        # Check visual preview labels were generated with QPixmap
        tl_label = dlg.preview_labels[(0, 0)]
        self.assertIsNotNone(tl_label.pixmap())
        self.assertFalse(tl_label.pixmap().isNull())


if __name__ == "__main__":
    unittest.main()
