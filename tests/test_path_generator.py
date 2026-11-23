import unittest
import sys
import os
import tempfile
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QImage, QColor

from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.models.project import Project
from tileset_map_maker.models.layer import ItemType, MapItem
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.models.path_ruleset import (
    PathRuleSet,
    ROLE_STRAIGHT_H,
    ROLE_STRAIGHT_V,
    ROLE_CORNER_TL,
    ROLE_CORNER_TR,
    ROLE_CORNER_BL,
    ROLE_CORNER_BR,
    ROLE_CORNER_GENERIC,
    ROLE_T_JUNCTION,
    ROLE_CROSS,
    ROLE_END,
    ROLE_CENTER,
    TEMPLATE_4_TILE,
    TEMPLATE_6_TILE,
    TEMPLATE_CUSTOM,
)
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.ui.dialogs.path_generator_dialog import PathPreviewWidget, PathGeneratorDialog


class TestPathGenerator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.project = Project(name="PathGenTest", map_width=20, map_height=20, tile_size=32)
        self.layer = self.project.add_layer("Ground")
        self.asset_mgr = AssetManager()
        self.history_mgr = HistoryManager()
        self.autotile_engine = AutoTileEngine()

        # Create two real test image files on disk so QPixmap can load them
        self.temp_dir = tempfile.mkdtemp()
        self.png1_path = os.path.join(self.temp_dir, "tileset1.png")
        self.png2_path = os.path.join(self.temp_dir, "tileset2.png")

        img1 = QImage(128, 128, QImage.Format.Format_ARGB32)
        img1.fill(QColor(100, 150, 200))
        img1.save(self.png1_path)

        img2 = QImage(128, 128, QImage.Format.Format_ARGB32)
        img2.fill(QColor(200, 150, 100))
        img2.save(self.png2_path)

        # Asset 1
        self.asset1 = Asset(name="RoadTileset", file_path=self.png1_path, asset_type=AssetType.TILESET)
        self.asset1.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.asset_mgr.assets[self.asset1.id] = self.asset1

        # Asset 2
        self.asset2 = Asset(name="StoneTileset", file_path=self.png2_path, asset_type=AssetType.TILESET)
        self.asset2.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.asset_mgr.assets[self.asset2.id] = self.asset2

    def tearDown(self):
        for p in [self.png1_path, self.png2_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        if os.path.exists(self.temp_dir):
            try:
                os.rmdir(self.temp_dir)
            except Exception:
                pass

    def _make_subtile(self, asset: Asset, col: int, row: int, name: str = "tile") -> SelectedSubTile:
        return SelectedSubTile(
            asset_id=asset.id,
            col=col,
            row=row,
            cols_count=1,
            rows_count=1,
            sub_x=col * 32,
            sub_y=row * 32,
            sub_w=32,
            sub_h=32,
            tile_width=32,
            tile_height=32,
            asset_name=name,
        )

    # 1. Tworzenie zestawu 4-elementowego
    def test_01_create_4_tile_set(self):
        ps = PathRuleSet(name="Dirt Path 4", template_type=TEMPLATE_4_TILE)
        self.assertEqual(ps.template_type, TEMPLATE_4_TILE)
        self.assertEqual(len(ps.roles), 0)

        # Assign the 4 core roles
        h_tile = self._make_subtile(self.asset1, 0, 0, "H")
        v_tile = self._make_subtile(self.asset1, 1, 0, "V")
        c_tile = self._make_subtile(self.asset1, 2, 0, "Corner")
        x_tile = self._make_subtile(self.asset1, 3, 0, "Cross")

        ps.set_role_tile(ROLE_STRAIGHT_H, h_tile)
        ps.set_role_tile(ROLE_STRAIGHT_V, v_tile)
        ps.set_role_tile(ROLE_CORNER_GENERIC, c_tile)
        ps.set_role_tile(ROLE_CROSS, x_tile)

        self.assertEqual(ps.get_role_tile(ROLE_STRAIGHT_H)[0], self.asset1.id)
        self.assertEqual(ps.get_role_tile(ROLE_STRAIGHT_V)[0], self.asset1.id)
        self.assertEqual(ps.get_role_tile(ROLE_CORNER_GENERIC)[0], self.asset1.id)
        self.assertEqual(ps.get_role_tile(ROLE_CROSS)[0], self.asset1.id)

        # In 4-tile set, TL corner falls back to generic corner
        # Mask 20 = E + S (TL corner)
        tile_found = ps.get_tile_for_mask(20)
        self.assertEqual(tile_found, ps.roles[ROLE_CORNER_GENERIC])

    # 2. Tworzenie zestawu 6-elementowego
    def test_02_create_6_tile_set(self):
        ps = PathRuleSet(name="Stone Path 6", template_type=TEMPLATE_6_TILE)
        self.assertEqual(ps.template_type, TEMPLATE_6_TILE)

        h_tile = self._make_subtile(self.asset1, 0, 0, "H")
        v_tile = self._make_subtile(self.asset1, 1, 0, "V")
        c_tile = self._make_subtile(self.asset1, 2, 0, "Corner")
        t_tile = self._make_subtile(self.asset1, 3, 0, "T")
        x_tile = self._make_subtile(self.asset1, 0, 1, "Cross")
        e_tile = self._make_subtile(self.asset1, 1, 1, "End")

        ps.set_role_tile(ROLE_STRAIGHT_H, h_tile)
        ps.set_role_tile(ROLE_STRAIGHT_V, v_tile)
        ps.set_role_tile(ROLE_CORNER_GENERIC, c_tile)
        ps.set_role_tile(ROLE_T_JUNCTION, t_tile)
        ps.set_role_tile(ROLE_CROSS, x_tile)
        ps.set_role_tile(ROLE_END, e_tile)

        # Endpoint mask = 16 (North only) -> should resolve to e_tile
        self.assertEqual(ps.get_tile_for_mask(16), ps.roles[ROLE_END])
        # T-junction mask = 69 (W + E + S) -> should resolve to t_tile
        self.assertEqual(ps.get_tile_for_mask(69), ps.roles[ROLE_T_JUNCTION])

    # 3. Ręczne przypisywanie kafelków z nieprzylegających pozycji
    def test_03_non_adjacent_tiles_assignment(self):
        ps = PathRuleSet(name="Scattered Path")
        # Assign completely non-adjacent tiles (e.g. (0,0), (3,2), (1,3))
        tile_a = self._make_subtile(self.asset1, 0, 0, "Tile_0_0")
        tile_b = self._make_subtile(self.asset1, 3, 2, "Tile_3_2")
        tile_c = self._make_subtile(self.asset1, 1, 3, "Tile_1_3")

        ps.set_role_tile(ROLE_STRAIGHT_H, tile_a)
        ps.set_role_tile(ROLE_STRAIGHT_V, tile_b)
        ps.set_role_tile(ROLE_CORNER_TL, tile_c)

        self.assertEqual(ps.roles[ROLE_STRAIGHT_H][1], 0)  # sub_x
        self.assertEqual(ps.roles[ROLE_STRAIGHT_H][2], 0)  # sub_y
        self.assertEqual(ps.roles[ROLE_STRAIGHT_V][1], 3 * 32)
        self.assertEqual(ps.roles[ROLE_STRAIGHT_V][2], 2 * 32)
        self.assertEqual(ps.roles[ROLE_CORNER_TL][1], 1 * 32)
        self.assertEqual(ps.roles[ROLE_CORNER_TL][2], 3 * 32)

    # 4. Przypisywanie kafelków z różnych tilesetów
    def test_04_tiles_from_different_tilesets(self):
        ps = PathRuleSet(name="Hybrid Path")
        tile_road = self._make_subtile(self.asset1, 0, 0, "RoadH")
        tile_stone = self._make_subtile(self.asset2, 1, 1, "StoneV")

        ps.set_role_tile(ROLE_STRAIGHT_H, tile_road)
        ps.set_role_tile(ROLE_STRAIGHT_V, tile_stone)

        self.assertEqual(ps.roles[ROLE_STRAIGHT_H][0], self.asset1.id)
        self.assertEqual(ps.roles[ROLE_STRAIGHT_V][0], self.asset2.id)

        # Check resolving returns appropriate asset subtiles
        self.assertEqual(ps.get_tile_for_mask(68)[0], self.asset1.id)
        self.assertEqual(ps.get_tile_for_mask(17)[0], self.asset2.id)

    # 5. Podmiana i usuwanie przypisań kafelków
    def test_05_reassign_and_clear_roles(self):
        ps = PathRuleSet(name="ModPath")
        tile1 = self._make_subtile(self.asset1, 0, 0)
        tile2 = self._make_subtile(self.asset1, 1, 1)

        ps.set_role_tile(ROLE_STRAIGHT_H, tile1)
        self.assertEqual(ps.get_role_tile(ROLE_STRAIGHT_H)[0], self.asset1.id)

        # Overwrite
        ps.set_role_tile(ROLE_STRAIGHT_H, tile2)
        self.assertEqual(ps.get_role_tile(ROLE_STRAIGHT_H)[1], 32)

        # Remove
        ps.remove_role(ROLE_STRAIGHT_H)
        self.assertIsNone(ps.get_role_tile(ROLE_STRAIGHT_H))

    # 6. Generowanie miniaturek kafelków w dialogu
    def test_06_role_thumbnails_in_dialog(self):
        dlg = PathGeneratorDialog(self.autotile_engine, self.asset_mgr)
        ps = PathRuleSet(name="ThumbPath")
        tile = self._make_subtile(self.asset1, 0, 0)
        ps.set_role_tile(ROLE_STRAIGHT_H, tile)
        dlg.current_ruleset = ps

        pix = dlg._create_subtile_thumbnail(tile, 32)
        self.assertFalse(pix.isNull())
        self.assertEqual(pix.width(), 32)
        self.assertEqual(pix.height(), 32)
        dlg.close()

    # 7. Renderowanie podglądu na żywo (PathPreviewWidget)
    def test_07_live_path_preview_widget(self):
        pw = PathPreviewWidget(ruleset=None, asset_manager=self.asset_mgr)
        ps = PathRuleSet(name="PreviewPath")
        h_tile = self._make_subtile(self.asset1, 0, 0)
        ps.set_role_tile(ROLE_STRAIGHT_H, h_tile)
        pw.set_ruleset(ps)

        # Ensure render works without throwing exceptions
        pm = QPixmap(300, 240)
        pm.fill(QColor(30, 30, 30))
        from PyQt6.QtGui import QPainter
        painter = QPainter(pm)
        pw.render(painter)
        painter.end()
        self.assertFalse(pm.isNull())

    # 8. Malowanie poziomej prostej ścieżki
    def test_08_draw_horizontal_path(self):
        ps = PathRuleSet(id="road_1", name="Road", terrain_type="road")
        h_tile = self._make_subtile(self.asset1, 0, 0, "RoadH")
        v_tile = self._make_subtile(self.asset1, 1, 0, "RoadV")
        end_tile = self._make_subtile(self.asset1, 2, 0, "RoadEnd")
        ps.set_role_tile(ROLE_STRAIGHT_H, h_tile)
        ps.set_role_tile(ROLE_STRAIGHT_V, v_tile)
        ps.set_role_tile(ROLE_END, end_tile)

        self.autotile_engine.add_ruleset(ps)
        self.autotile_engine.active_ruleset_id = ps.id

        brush = BrushTool()
        bs = BrushSettings()
        bs.auto_tile_enabled = True

        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
            autotile_engine=self.autotile_engine,
        )

        brush.on_press(5, 5, ctx)
        brush.on_drag(6, 5, ctx)
        brush.on_drag(7, 5, ctx)
        brush.on_release(7, 5, ctx)

        item_mid = self.layer.get_tile(6, 5)
        self.assertIsNotNone(item_mid)
        # Middle cell (6,5) has neighbors West (5,5) and East (7,5) -> mask = 68 -> ROLE_STRAIGHT_H
        self.assertEqual(item_mid.source_x, h_tile.sub_x)
        self.assertEqual(item_mid.source_y, h_tile.sub_y)

    # 9. Malowanie pionowej prostej ścieżki
    def test_09_draw_vertical_path(self):
        ps = PathRuleSet(id="road_v", name="RoadV", terrain_type="road")
        v_tile = self._make_subtile(self.asset1, 0, 1, "RoadV")
        ps.set_role_tile(ROLE_STRAIGHT_V, v_tile)
        self.autotile_engine.add_ruleset(ps)
        self.autotile_engine.active_ruleset_id = ps.id

        brush = BrushTool()
        bs = BrushSettings()
        bs.auto_tile_enabled = True
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
            autotile_engine=self.autotile_engine,
        )

        brush.on_press(5, 3, ctx)
        brush.on_drag(5, 4, ctx)
        brush.on_drag(5, 5, ctx)
        brush.on_release(5, 5, ctx)

        item_mid = self.layer.get_tile(5, 4)
        self.assertIsNotNone(item_mid)
        # Neighbors North and South -> mask = 17 -> ROLE_STRAIGHT_V
        self.assertEqual(item_mid.source_x, v_tile.sub_x)
        self.assertEqual(item_mid.source_y, v_tile.sub_y)

    # 10. Malowanie zakrętów / narożników (TL, TR, BL, BR)
    def test_10_draw_corners(self):
        ps = PathRuleSet(id="road_c", name="RoadCorners", terrain_type="road")
        tl_tile = self._make_subtile(self.asset1, 0, 2, "TL")
        tr_tile = self._make_subtile(self.asset1, 1, 2, "TR")
        bl_tile = self._make_subtile(self.asset1, 2, 2, "BL")
        br_tile = self._make_subtile(self.asset1, 3, 2, "BR")

        ps.set_role_tile(ROLE_CORNER_TL, tl_tile)
        ps.set_role_tile(ROLE_CORNER_TR, tr_tile)
        ps.set_role_tile(ROLE_CORNER_BL, bl_tile)
        ps.set_role_tile(ROLE_CORNER_BR, br_tile)
        self.autotile_engine.add_ruleset(ps)
        self.autotile_engine.active_ruleset_id = ps.id

        brush = BrushTool()
        bs = BrushSettings()
        bs.auto_tile_enabled = True
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
            autotile_engine=self.autotile_engine,
        )

        # Draw a turn at (5,5) connecting East (6,5) and South (5,6) -> Corner TL (mask = 20)
        brush.on_press(6, 5, ctx)
        brush.on_drag(5, 5, ctx)
        brush.on_drag(5, 6, ctx)
        brush.on_release(5, 6, ctx)

        item_corner = self.layer.get_tile(5, 5)
        self.assertIsNotNone(item_corner)
        self.assertEqual(item_corner.source_x, tl_tile.sub_x)
        self.assertEqual(item_corner.source_y, tl_tile.sub_y)

    # 11. Malowanie skrzyżowań T i 4-kierunkowych
    def test_11_draw_t_junction_and_cross(self):
        ps = PathRuleSet(id="road_x", name="RoadCross", terrain_type="road")
        t_tile = self._make_subtile(self.asset1, 0, 3, "T")
        x_tile = self._make_subtile(self.asset1, 1, 3, "Cross")
        ps.set_role_tile(ROLE_T_JUNCTION, t_tile)
        ps.set_role_tile(ROLE_CROSS, x_tile)
        self.autotile_engine.add_ruleset(ps)
        self.autotile_engine.active_ruleset_id = ps.id

        brush = BrushTool()
        bs = BrushSettings()
        bs.auto_tile_enabled = True
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
            autotile_engine=self.autotile_engine,
        )

        # Draw cross around center (10, 10): (9,10), (11,10), (10,9), (10,11), (10,10)
        brush.on_press(9, 10, ctx)
        brush.on_drag(11, 10, ctx)
        brush.on_drag(10, 9, ctx)
        brush.on_drag(10, 11, ctx)
        brush.on_drag(10, 10, ctx)
        brush.on_release(10, 10, ctx)

        item_cross = self.layer.get_tile(10, 10)
        self.assertIsNotNone(item_cross)
        self.assertEqual(item_cross.source_x, x_tile.sub_x)
        self.assertEqual(item_cross.source_y, x_tile.sub_y)

    # 12. Aktualizacja falowa (ripple update) przy przedłużaniu ścieżki
    def test_12_ripple_update_on_extension(self):
        ps = PathRuleSet(id="road_ripple", name="RoadRipple", terrain_type="road")
        h_tile = self._make_subtile(self.asset1, 0, 0, "H")
        end_tile = self._make_subtile(self.asset1, 2, 0, "End")
        ps.set_role_tile(ROLE_STRAIGHT_H, h_tile)
        ps.set_role_tile(ROLE_END, end_tile)
        self.autotile_engine.add_ruleset(ps)
        self.autotile_engine.active_ruleset_id = ps.id

        brush = BrushTool()
        bs = BrushSettings()
        bs.auto_tile_enabled = True
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
            autotile_engine=self.autotile_engine,
        )

        # First stroke: (5,5) and (6,5). (6,5) is an endpoint
        brush.on_press(5, 5, ctx)
        brush.on_drag(6, 5, ctx)
        brush.on_release(6, 5, ctx)
        self.assertEqual(self.layer.get_tile(6, 5).source_x, end_tile.sub_x)

        # Second stroke: extend to (7,5). (6,5) must automatically ripple-update to straight H!
        brush.on_press(7, 5, ctx)
        brush.on_release(7, 5, ctx)
        self.assertEqual(self.layer.get_tile(6, 5).source_x, h_tile.sub_x)
        self.assertEqual(self.layer.get_tile(7, 5).source_x, end_tile.sub_x)

    # 13. Izolacja wielu warstw (ścieżka na warstwie 1 nie łączy się z warstwą 2)
    def test_13_multi_layer_isolation(self):
        layer2 = self.project.add_layer("Overhead")
        ps = PathRuleSet(id="road_iso", name="RoadIso", terrain_type="road")
        h_tile = self._make_subtile(self.asset1, 0, 0, "H")
        v_tile = self._make_subtile(self.asset1, 1, 0, "V")
        ps.set_role_tile(ROLE_STRAIGHT_H, h_tile)
        ps.set_role_tile(ROLE_STRAIGHT_V, v_tile)
        self.autotile_engine.add_ruleset(ps)
        self.autotile_engine.active_ruleset_id = ps.id

        brush = BrushTool()
        bs = BrushSettings()
        bs.auto_tile_enabled = True
        ctx1 = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
            autotile_engine=self.autotile_engine,
        )

        # Draw horizontal path on Ground layer
        brush.on_press(5, 5, ctx1)
        brush.on_drag(6, 5, ctx1)
        brush.on_drag(7, 5, ctx1)
        brush.on_release(7, 5, ctx1)

        # Draw adjacent cell on Overhead layer at (6, 6)
        ctx2 = ToolContext(
            project=self.project,
            active_layer=layer2,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
            autotile_engine=self.autotile_engine,
        )
        brush.on_press(6, 6, ctx2)
        brush.on_release(6, 6, ctx2)

        # Ground layer's (6,5) should NOT have connected to Overhead's (6,6) as a T-junction;
        # it must remain straight horizontal
        self.assertEqual(self.layer.get_tile(6, 5).source_x, h_tile.sub_x)

    # 14. Cofanie (Undo) i Ponawianie (Redo) malowania ścieżek
    def test_14_undo_redo_path_stroke(self):
        ps = PathRuleSet(id="road_ur", name="RoadUR", terrain_type="road")
        h_tile = self._make_subtile(self.asset1, 0, 0, "H")
        ps.set_role_tile(ROLE_STRAIGHT_H, h_tile)
        self.autotile_engine.add_ruleset(ps)
        self.autotile_engine.active_ruleset_id = ps.id

        brush = BrushTool()
        bs = BrushSettings()
        bs.auto_tile_enabled = True
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
            autotile_engine=self.autotile_engine,
        )

        brush.on_press(3, 3, ctx)
        brush.on_drag(4, 3, ctx)
        brush.on_drag(5, 3, ctx)
        brush.on_release(5, 3, ctx)

        self.assertIsNotNone(self.layer.get_tile(4, 3))

        # Undo
        self.assertTrue(self.history_mgr.can_undo())
        self.history_mgr.undo()
        self.assertIsNone(self.layer.get_tile(4, 3))

        # Redo
        self.assertTrue(self.history_mgr.can_redo())
        self.history_mgr.redo()
        self.assertIsNotNone(self.layer.get_tile(4, 3))

    # 15. Zapis i odczyt projektu (.tmmap) z zachowaniem kafelków ścieżki
    def test_15_project_save_load_preserves_path(self):
        ps = PathRuleSet(id="road_save", name="RoadSave", terrain_type="road")
        h_tile = self._make_subtile(self.asset1, 0, 0, "H")
        ps.set_role_tile(ROLE_STRAIGHT_H, h_tile)
        self.autotile_engine.add_ruleset(ps)
        self.autotile_engine.active_ruleset_id = ps.id

        brush = BrushTool()
        bs = BrushSettings()
        bs.auto_tile_enabled = True
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
            autotile_engine=self.autotile_engine,
        )

        brush.on_press(2, 2, ctx)
        brush.on_drag(3, 2, ctx)
        brush.on_drag(4, 2, ctx)
        brush.on_release(4, 2, ctx)

        save_path = os.path.join(self.temp_dir, "test_proj.tmmap")
        try:
            ProjectIO.save_project(self.project, self.asset_mgr, save_path)
            loaded_proj = ProjectIO.load_project(save_path, self.asset_mgr)
            loaded_layer = loaded_proj.get_active_layer()
            item = loaded_layer.get_tile(3, 2)
            self.assertIsNotNone(item)
            self.assertEqual(item.source_x, h_tile.sub_x)
            self.assertEqual(item.source_y, h_tile.sub_y)
        finally:
            if os.path.exists(save_path):
                os.remove(save_path)

    # 16. Trwałość konfiguracji w app_config.json
    def test_16_app_config_persistence(self):
        config_file = os.path.join(self.temp_dir, "test_config.json")
        cfg_mgr = ConfigManager(custom_config_path=config_file)

        ps = PathRuleSet(id="road_cfg", name="Persistent Road", terrain_type="road", template_type=TEMPLATE_6_TILE)
        h_tile = self._make_subtile(self.asset1, 0, 0, "H")
        ps.set_role_tile(ROLE_STRAIGHT_H, h_tile)
        self.autotile_engine.add_ruleset(ps)

        # Save to config
        cfg_mgr.save_autotile_rules(self.autotile_engine)

        # Create new engine and restore
        new_engine = AutoTileEngine()
        cfg_mgr.restore_autotile_rules(new_engine)

        self.assertIn("road_cfg", new_engine.rulesets)
        restored_ps = new_engine.rulesets["road_cfg"]
        self.assertTrue(getattr(restored_ps, "is_path_ruleset", False))
        self.assertEqual(restored_ps.name, "Persistent Road")
        self.assertEqual(restored_ps.template_type, TEMPLATE_6_TILE)
        self.assertIn(ROLE_STRAIGHT_H, restored_ps.roles)
        self.assertEqual(restored_ps.roles[ROLE_STRAIGHT_H][1], 0)
        self.assertEqual(restored_ps.roles[ROLE_STRAIGHT_H][2], 0)


if __name__ == "__main__":
    unittest.main()
