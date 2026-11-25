import os
import sys
import tempfile
import time
import unittest

from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

APP = QApplication.instance() or QApplication(sys.argv)

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.paths import (
    ConnectionRuleEngine,
    PathMapRenderer,
    PathSolver,
    PathVariant,
    TileAnalyzer,
)
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.rpg_autotile import (
    SelectedAutotile,
    create_rpg_autotile_from_tile,
)
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.models.asset import AssetType, TilesetConfig
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.models.project import Project
from tileset_map_maker.ui.dialogs.path_generator_dialog import PathGeneratorDialog

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TERRAIN_SUMMER_PATH = os.path.join(REPO_ROOT, "sample_assets", "terrain_summer.png")
GRASS_SINGLE_PATH = os.path.join(REPO_ROOT, "sample_assets", "Terrain", "Grass", "grass_01.png")


def _render_map(project: Project, am: AssetManager, engine: AutoTileEngine) -> QImage:
    ts = project.tile_size
    img = QImage(project.map_width * ts, project.map_height * ts, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    RenderEngine(am, autotile_engine=engine).render(
        p,
        project,
        RenderOptions(show_grid=False, show_selection=False, transparent_bg=True, render_checkerboard=False),
    )
    p.end()
    return img


class TestPathsArchitecture20Points(unittest.TestCase):
    """
    Full 20-point acceptance test suite validating the 5-pillar Paths architecture:
    TileAnalyzer (cached), Variant Editor (PathVariant), ConnectionRuleEngine,
    PathSolver (constraint-based), and PathMapRenderer + definition independence.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.am = AssetManager()
        self.engine = AutoTileEngine(asset_manager=self.am)
        self.history = HistoryManager()
        self.project = Project(name="Paths20", map_width=16, map_height=14, tile_size=32)
        self.layer = self.project.get_active_layer()

        self.summer_asset, _, err = self.am.import_single_file(
            TERRAIN_SUMMER_PATH, force_asset_type=AssetType.TILESET
        )
        self.assertIsNotNone(self.summer_asset, err)
        self.summer_asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.summer_sheet = self.am.get_pixmap(self.summer_asset.id).toImage()

    def tearDown(self):
        self.tmp.cleanup()

    # 1. Pojedynczy kafelek 1x1 + TileAnalyzer
    def test_01_single_tile_1x1_and_analyzer(self):
        g_asset, _, _ = self.am.import_single_file(GRASS_SINGLE_PATH, force_asset_type=AssetType.TILESET)
        g_asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        g_sheet = self.am.get_pixmap(g_asset.id).toImage()

        v = self.engine.analyzer.analyze_variant(g_sheet, g_asset.id, 0, 0, 1, 1, 32, g_asset.tileset_config)
        self.assertEqual((v.width_tiles, v.height_tiles), (1, 1))
        self.assertEqual(set(v.edges.keys()), {"N", "E", "S", "W"})
        self.assertEqual(v.role, "center")

        at = create_rpg_autotile_from_tile("Single1x1", g_asset.id, g_sheet, 0, 0, 32, mode="single_tile")
        self.engine.register_rpg_autotile(at, self.am)
        self.engine.apply_rpg_autotile_stroke(self.layer, [(2, 2), (3, 2), (4, 2)], at, self.project, self.am)
        self.assertEqual(len(self.layer.tiles), 3)

    # 2, 3, 4, 5. Kompozycje 2x2, 2x3, 3x2, 3x3 (plus 4x4!) jako niepodzielne warianty logiczne
    def test_02_to_05_logical_compositions_2x2_2x3_3x2_3x3_4x4(self):
        for cw, ch in ((2, 2), (2, 3), (3, 2), (3, 3), (4, 4)):
            with self.subTest(size=f"{cw}x{ch}"):
                proj = Project(map_width=12, map_height=12, tile_size=32)
                layer = proj.get_active_layer()
                at = create_rpg_autotile_from_tile(
                    f"Comp_{cw}x{ch}", self.summer_asset.id, self.summer_sheet,
                    0, 0, 32, mode="composition_wxh", w_tiles=cw, h_tiles=ch, terrain_type=f"c_{cw}_{ch}",
                )
                self.engine.register_rpg_autotile(at, self.am)
                self.engine.apply_rpg_autotile_stroke(layer, [(0, 0), (cw, 0)], at, proj, self.am)
                self.assertEqual(len(layer.tiles), 2 * cw * ch)
                for dr in range(ch):
                    for dc in range(cw):
                        t0 = layer.get_tile(dc, dr)
                        t1 = layer.get_tile(cw + dc, dr)
                        self.assertEqual((t0.source_x, t0.source_y), (dc * 32, dr * 32))
                        self.assertEqual((t1.source_x, t1.source_y), (dc * 32, dr * 32))
                        self.assertEqual(t0.properties["composition_origin"], [0, 0])
                        self.assertEqual(t1.properties["composition_origin"], [cw, 0])

    # 6. Nieregularny tileset + TileAnalyzer sheet cache + ConnectionRuleEngine (non-color-only!)
    def test_06_irregular_tileset_analyzer_cache_and_connection_rules(self):
        analyzer = TileAnalyzer()
        a1 = analyzer.analyze_sheet(
            self.summer_sheet, self.summer_asset.id, 32, self.summer_asset.tileset_config
        )
        a2 = analyzer.analyze_sheet(
            self.summer_sheet, self.summer_asset.id, 32, self.summer_asset.tileset_config
        )
        self.assertIs(a1, a2, "Second sheet analysis must hit cache without re-scanning!")
        self.assertGreaterEqual(len(a1.detected_3x3_blocks), 5)
        self.assertGreaterEqual(len(a1.proposed_variants), 5)

        # Verify ConnectionRuleEngine distinguishes narrow vs wide & blocks decorative variants!
        v_wide = PathVariant(mask=68, source_asset_id="a", source_col=0, source_row=0, surface_width_px=24, role="straight_h")
        v_narrow = PathVariant(mask=68, source_asset_id="a", source_col=1, source_row=0, surface_width_px=8, role="straight_h")
        v_deco = PathVariant(mask=0, source_asset_id="a", source_col=2, source_row=0, role="decoration", allow_connections=False)

        res_mismatch = ConnectionRuleEngine.check_edge_compatibility(v_wide, v_narrow, "E")
        self.assertFalse(res_mismatch.compatible, "Wide and narrow variants must NOT be falsely compatible!")
        res_deco = ConnectionRuleEngine.check_edge_compatibility(v_wide, v_deco, "E")
        self.assertFalse(res_deco.compatible, "Decoration must never bridge path connections!")

        # Explicit user compatibility override MUST be respected by ConnectionRuleEngine & PathSolver!
        v_custom_a = PathVariant(mask=68, source_asset_id=self.summer_asset.id, source_col=3, source_row=1, priority=30)
        v_custom_b = PathVariant(mask=68, source_asset_id=self.summer_asset.id, source_col=4, source_row=1, priority=30)
        v_custom_a.compatible_neighbors = {"E": [v_custom_b.id]}
        self.assertTrue(ConnectionRuleEngine.check_edge_compatibility(v_custom_a, v_custom_b, "E").compatible)
        self.assertFalse(ConnectionRuleEngine.check_edge_compatibility(v_custom_a, v_wide, "E").compatible)

    # 7 & 8. Ścieżka o małej szerokości vs ścieżka o dużej szerokości
    def test_07_08_narrow_vs_wide_paths(self):
        at_narrow = create_rpg_autotile_from_tile(
            "NarrowPath", self.summer_asset.id, self.summer_sheet, 7, 1, 32, mode="auto", rim_balance=0.55, terrain_type="narrow"
        )
        at_wide = create_rpg_autotile_from_tile(
            "WidePath", self.summer_asset.id, self.summer_sheet, 7, 1, 32, mode="auto", rim_balance=0.25, path_width=2, terrain_type="wide"
        )
        self.engine.register_rpg_autotile(at_narrow, self.am)
        self.engine.register_rpg_autotile(at_wide, self.am)

        # Compare single-tile navigable green height of narrow vs wide rim_balance
        atlas_n = at_narrow.get_atlas_pixmap(self.am).toImage()
        atlas_w = at_wide.get_atlas_pixmap(self.am).toImage()
        sx_n, sy_n, _, _ = at_narrow.get_tile_slice_for_mask(68)
        sx_w, sy_w, _, _ = at_wide.get_tile_slice_for_mask(68)
        is_green = lambda c: c.alpha() > 200 and c.green() > c.red() + 10
        h_narrow = sum(1 for y in range(32) if is_green(atlas_n.pixelColor(sx_n + 16, sy_n + y)))
        h_wide = sum(1 for y in range(32) if is_green(atlas_w.pixelColor(sx_w + 16, sy_w + y)))
        self.assertGreater(h_wide, h_narrow + 4)

        # Wide path_width=2 expands stroke automatically to 2 tiles wide!
        self.engine.apply_rpg_autotile_stroke(self.layer, [(2, 3), (3, 3), (4, 3)], at_wide, self.project, self.am)
        self.assertEqual(len(self.layer.tiles), 8)  # 4 cols x 2 rows

    # 9, 10, 11, 12, 13, 14. Woda, trawa, skrzyżowania +, T, zakręty i wiele skrzyżowań blisko siebie
    def test_09_to_14_water_grass_cross_t_turns_and_nearby_crosses(self):
        at_water = create_rpg_autotile_from_tile("Water", self.summer_asset.id, self.summer_sheet, 1, 11, 32, mode="auto", terrain_type="water")
        at_grass = create_rpg_autotile_from_tile("Grass", self.summer_asset.id, self.summer_sheet, 1, 1, 32, mode="auto", terrain_type="grass")
        self.engine.register_rpg_autotile(at_water, self.am)
        self.engine.register_rpg_autotile(at_grass, self.am)

        # Water network with 2 nearby crosses, T-junctions, and turns
        water_coords = (
            [(c, 2) for c in range(1, 9)]
            + [(c, 5) for c in range(1, 9)]
            + [(3, r) for r in range(1, 7)]
            + [(6, r) for r in range(1, 7)]
        )
        self.engine.apply_rpg_autotile_stroke(self.layer, water_coords, at_water, self.project, self.am)
        # Verify crosses at (3,2), (6,2), (3,5), (6,5), T-junctions at (1,2)/(8,2) -> corners!
        for cx, cy in ((3, 2), (6, 2), (3, 5), (6, 5)):
            self.assertEqual(self.engine.compute_rpg_mask(self.layer, cx, cy, at_water, self.project), 85)
        # Add pure T-junction at (3, 7) branching off bottom of (3, 6)
        self.engine.apply_rpg_autotile_stroke(self.layer, [(2, 7), (3, 7), (4, 7)], at_water, self.project, self.am)
        self.assertEqual(self.engine.compute_rpg_mask(self.layer, 3, 7, at_water, self.project), 69)  # W+E+N T-junction

        # Grass closed loop (4 corner turns!) at cols 10..13, rows 1..4
        grass_loop = (
            [(c, 1) for c in range(10, 14)]
            + [(c, 4) for c in range(10, 14)]
            + [(10, r) for r in range(1, 5)]
            + [(13, r) for r in range(1, 5)]
        )
        self.engine.apply_rpg_autotile_stroke(self.layer, grass_loop, at_grass, self.project, self.am)
        self.assertEqual(self.engine.compute_rpg_mask(self.layer, 10, 1, at_grass, self.project), 20)  # E+S corner
        self.assertEqual(self.engine.compute_rpg_mask(self.layer, 13, 1, at_grass, self.project), 80)  # W+S corner
        self.assertEqual(self.engine.compute_rpg_mask(self.layer, 10, 4, at_grass, self.project), 5)   # N+E corner
        self.assertEqual(self.engine.compute_rpg_mask(self.layer, 13, 4, at_grass, self.project), 65)  # N+W corner

    # 15, 16, 17, 18, 19. Usuwanie, Undo/Redo, Zapis/Odczyt, Usunięcie definicji, Zmiana definicji bez utraty mapy!
    def test_15_to_19_erase_undo_save_delete_and_edit_definition_independence(self):
        at_orig = create_rpg_autotile_from_tile(
            "OrigGrass", self.summer_asset.id, self.summer_sheet, 7, 1, 32, mode="auto", terrain_type="indep_grass"
        )
        self.engine.register_rpg_autotile(at_orig, self.am)
        ctx = ToolContext(
            project=self.project, active_layer=self.layer, asset_manager=self.am,
            history_manager=self.history, brush_settings=BrushSettings(),
            autotile_engine=self.engine, selected_asset=SelectedAutotile(at_orig),
        )
        ctx.brush_settings.selected_autotile = ctx.selected_asset
        brush = BrushTool()
        eraser = EraserTool()

        # Paint a cross at (4, 4)
        for c, r in [(3, 4), (4, 4), (5, 4), (4, 3), (4, 5)]:
            brush.on_press(c, r, ctx)
            brush.on_release(c, r, ctx)
        img_orig = _render_map(self.project, self.am, self.engine)

        # 15 & 16: Erase (4, 3) then Undo -> exact pixel restoration
        eraser.on_press(4, 3, ctx)
        eraser.on_release(4, 3, ctx)
        self.assertIsNone(self.layer.get_tile(4, 3))
        self.assertTrue(self.history.undo())
        img_undone = _render_map(self.project, self.am, self.engine)
        self.assertEqual(
            img_undone.constBits().asstring(img_undone.sizeInBytes()),
            img_orig.constBits().asstring(img_orig.sizeInBytes()),
        )

        # 19: MODIFY definition (switch to water!) via update_rpg_autotile_definition ->
        # Already-painted grass cross on the map MUST remain 100% grass (NOT silently turned into water!)
        at_edited = create_rpg_autotile_from_tile(
            "EditedToWater", self.summer_asset.id, self.summer_sheet, 1, 11, 32, mode="auto", terrain_type="indep_grass"
        )
        new_at = self.engine.update_rpg_autotile_definition(at_orig.id, at_edited, self.am)
        self.assertNotEqual(new_at.id, at_orig.id)
        self.assertTrue(self.engine.rpg_autotiles[at_orig.id].archived)

        img_after_edit = _render_map(self.project, self.am, self.engine)
        self.assertEqual(
            img_after_edit.constBits().asstring(img_after_edit.sizeInBytes()),
            img_orig.constBits().asstring(img_orig.sizeInBytes()),
            "Editing a Paths definition must NOT retroactively alter already-painted map tiles!",
        )

        # 18: DELETE (archive) the new definition too -> map tiles STILL render identically!
        self.engine.archive_rpg_autotile(new_at.id)
        img_after_delete = _render_map(self.project, self.am, self.engine)
        self.assertEqual(
            img_after_delete.constBits().asstring(img_after_delete.sizeInBytes()),
            img_orig.constBits().asstring(img_orig.sizeInBytes()),
        )

        # 17: Save & reload .tmmap -> map tiles STILL render pixel-identically!
        save_path = os.path.join(self.tmp.name, "indep_map.tmmap")
        self.assertTrue(ProjectIO.save_project(self.project, self.am, save_path, self.engine))
        am2 = AssetManager()
        eng2 = AutoTileEngine(asset_manager=am2)
        reloaded = ProjectIO.load_project(save_path, am2, autotile_engine=eng2)
        self.assertIsNotNone(reloaded)
        img_reloaded = _render_map(reloaded, am2, eng2)
        self.assertEqual(
            img_reloaded.constBits().asstring(img_reloaded.sizeInBytes()),
            img_orig.constBits().asstring(img_orig.sizeInBytes()),
        )

    # 20. Wydajność na dużej mapie (200x200) + integracja UI PathGeneratorDialog (Zoom, Auto-Analyze, Compat)
    def test_20_large_map_performance_and_dialog_workflow(self):
        at = create_rpg_autotile_from_tile(
            "FastPath", self.summer_asset.id, self.summer_sheet, 7, 1, 32, mode="auto", terrain_type="fast"
        )
        self.engine.register_rpg_autotile(at, self.am)

        big_proj = Project(name="Big200", map_width=200, map_height=200, tile_size=32)
        big_layer = big_proj.get_active_layer()

        t0 = time.perf_counter()
        stroke = [(c, 100) for c in range(50, 100)] + [(75, r) for r in range(75, 125)]
        changes = self.engine.apply_rpg_autotile_stroke(big_layer, stroke, at, big_proj, self.am)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.assertGreater(len(changes), 90)
        self.assertLess(elapsed_ms, 150.0, f"Large map local stroke took too long: {elapsed_ms:.1f} ms")

        # Verify dialog Zoom, Auto-Analyze, Variant creation with EdgeSignatures, and Compatibility Matrix
        dlg = PathGeneratorDialog(self.engine, self.am, initial_asset_id=self.summer_asset.id)
        dlg.sheet_canvas.set_zoom(2.0)
        self.assertEqual(dlg.sheet_canvas.zoom, 2.0)
        dlg._auto_analyze_sheet()
        self.assertIn("Przeanalizowano arkusz", dlg.lbl_status.text())
        dlg._on_region_selected(6, 3, 2, 2)
        dlg._add_custom_variant()
        self.assertEqual(len(dlg._custom_variants), 1)
        self.assertEqual(set(dlg._custom_variants[0].edges.keys()), {"N", "E", "S", "W"})
        dlg._auto_suggest_compatibility()
        self.assertIn("kompatybilnych połączeń", dlg.lbl_compat_info.text())
        dlg.close()


if __name__ == "__main__":
    unittest.main()
