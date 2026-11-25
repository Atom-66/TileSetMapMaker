import os
import tempfile
import unittest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QColor

from tileset_map_maker.core.rpg_autotile import (
    RPGAutotile,
    AutotileFormat,
    SelectedAutotile,
    resolve_quadrant_states,
    mask_to_quadrant_states,
    detect_autotile_format,
    QUAD_OUTER_CORNER,
    QUAD_EDGE_H,
    QUAD_EDGE_V,
    QUAD_INNER_CORNER,
    QUAD_CENTER,
)
from tileset_map_maker.models.autotile import (
    MASK_N, MASK_NE, MASK_E, MASK_SE, MASK_S, MASK_SW, MASK_W, MASK_NW,
    canonicalize_blob_mask,
)
from tileset_map_maker.models.layer import Layer, MapItem, ItemType
from tileset_map_maker.models.project import Project
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.core.project_io import ProjectIO


class TestRPGMakerAutotileSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

        # Create temporary directory for sample test autotile sheets
        cls.test_dir = tempfile.mkdtemp()

        # 1. Standard RPG Maker VX Ace ground autotile (2x3 full tiles = 64x96 px at 32x32)
        cls.vx_ace_path = os.path.join(cls.test_dir, "autotile_vx_ace.png")
        img_vx = QImage(64, 96, QImage.Format.Format_ARGB32)
        img_vx.fill(QColor(40, 160, 40))  # Green grass
        # Draw distinctive colors for sub-tiles to test slicing
        for y in range(0, 96, 16):
            for x in range(0, 64, 16):
                c = QColor((x * 3) % 255, (y * 2 + 50) % 255, 100)
                for py in range(y, y + 16):
                    for px in range(x, x + 16):
                        img_vx.setPixelColor(px, py, c)
        img_vx.save(cls.vx_ace_path)

        # 2. RPG Maker XP autotile (3x4 full tiles = 96x128 px at 32x32)
        cls.xp_path = os.path.join(cls.test_dir, "autotile_xp.png")
        img_xp = QImage(96, 128, QImage.Format.Format_ARGB32)
        img_xp.fill(QColor(60, 120, 220))  # Blue water
        img_xp.save(cls.xp_path)

        # 3. Simple 3x3 autotile (96x96 px at 32x32)
        cls.simple_path = os.path.join(cls.test_dir, "autotile_simple.png")
        img_s = QImage(96, 96, QImage.Format.Format_ARGB32)
        img_s.fill(QColor(200, 160, 80))  # Sand/dirt
        img_s.save(cls.simple_path)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        self.engine = AutoTileEngine()
        self.asset_mgr = AssetManager()
        self.history = HistoryManager()

        self.project = Project(name="Autotile Test Project", tile_size=32, map_width=30, map_height=30)
        self.layer = self.project.get_active_layer()

        self.autotile = RPGAutotile(
            name="Meadow Grass",
            terrain_type="Grass",
            autotile_format=AutotileFormat.VX_ACE_2X3,
            tile_size=32,
            source_image_path=self.vx_ace_path,
        )
        self.autotile.rebuild_atlas()
        self.engine.register_rpg_autotile(self.autotile)
        self.asset_mgr.register_rpg_autotile(self.autotile)

    # --------------------------------------------------------------------------
    # 1. Malowanie pojedynczego pola (Single isolated cell - 4 outer corners)
    # --------------------------------------------------------------------------
    def test_01_single_cell_isolated_four_outer_corners(self):
        """Single cell has 0 neighbors and resolves to 4 outer corners."""
        tl, tr, bl, br = mask_to_quadrant_states(0)
        self.assertEqual(tl, QUAD_OUTER_CORNER)
        self.assertEqual(tr, QUAD_OUTER_CORNER)
        self.assertEqual(bl, QUAD_OUTER_CORNER)
        self.assertEqual(br, QUAD_OUTER_CORNER)

        # Place single cell via engine
        changes = self.engine.apply_rpg_autotile_stroke(self.layer, [(5, 5)], self.autotile, self.project)
        self.assertIn((5, 5), changes)
        tile = self.layer.get_tile(5, 5)
        self.assertIsNotNone(tile)
        self.assertTrue(tile.is_auto_tiled)
        self.assertEqual(tile.terrain_type, "Grass")
        self.assertEqual(tile.source_x, 0)
        self.assertEqual(tile.source_y, 0)

    # --------------------------------------------------------------------------
    # 2. Rysowanie długiej linii (Edges and endpoints)
    # --------------------------------------------------------------------------
    def test_02_long_line_drawing_edges_and_caps(self):
        """A 1-tile wide horizontal line forms left cap, horizontal edges, and right cap."""
        line_coords = [(x, 10) for x in range(5, 11)]
        self.engine.apply_rpg_autotile_stroke(self.layer, line_coords, self.autotile, self.project)

        # Left endpoint (5, 10): only East neighbor
        m_start = self.engine.compute_rpg_mask(self.layer, 5, 10, self.autotile, self.project)
        self.assertEqual(m_start, MASK_E)
        tl, tr, bl, br = mask_to_quadrant_states(m_start)
        self.assertEqual((tl, bl), (QUAD_OUTER_CORNER, QUAD_OUTER_CORNER))
        self.assertEqual((tr, br), (QUAD_EDGE_H, QUAD_EDGE_H))

        # Middle tile (7, 10): West and East neighbors
        m_mid = self.engine.compute_rpg_mask(self.layer, 7, 10, self.autotile, self.project)
        self.assertEqual(m_mid, MASK_W | MASK_E)
        tl, tr, bl, br = mask_to_quadrant_states(m_mid)
        self.assertEqual((tl, tr, bl, br), (QUAD_EDGE_H, QUAD_EDGE_H, QUAD_EDGE_H, QUAD_EDGE_H))

        # Right endpoint (10, 10): only West neighbor
        m_end = self.engine.compute_rpg_mask(self.layer, 10, 10, self.autotile, self.project)
        self.assertEqual(m_end, MASK_W)
        tl, tr, bl, br = mask_to_quadrant_states(m_end)
        self.assertEqual((tl, bl), (QUAD_EDGE_H, QUAD_EDGE_H))
        self.assertEqual((tr, br), (QUAD_OUTER_CORNER, QUAD_OUTER_CORNER))

    # --------------------------------------------------------------------------
    # 3. Rysowanie szerokiej powierzchni (Solid area - center + outer borders)
    # --------------------------------------------------------------------------
    def test_03_wide_surface_filling_center_and_borders(self):
        """A 3x3 filled square forms 4 outer corners, 4 edges, and 1 solid center."""
        coords = [(c, r) for r in range(5, 8) for c in range(5, 8)]
        self.engine.apply_rpg_autotile_stroke(self.layer, coords, self.autotile, self.project)

        # Center tile (6, 6) has all 8 neighbors present -> mask 255 -> all quadrants are QUAD_CENTER
        m_center = self.engine.compute_rpg_mask(self.layer, 6, 6, self.autotile, self.project)
        self.assertEqual(m_center, 255)
        tl, tr, bl, br = mask_to_quadrant_states(m_center)
        self.assertEqual((tl, tr, bl, br), (QUAD_CENTER, QUAD_CENTER, QUAD_CENTER, QUAD_CENTER))

        # Top-left outer corner (5, 5) -> S, E, SE present
        m_tl = self.engine.compute_rpg_mask(self.layer, 5, 5, self.autotile, self.project)
        self.assertEqual(m_tl, MASK_S | MASK_E | MASK_SE)
        tl, tr, bl, br = mask_to_quadrant_states(m_tl)
        self.assertEqual(tl, QUAD_OUTER_CORNER)
        self.assertEqual(tr, QUAD_EDGE_H)
        self.assertEqual(bl, QUAD_EDGE_V)
        self.assertEqual(br, QUAD_CENTER)

    # --------------------------------------------------------------------------
    # 4. Wszystkie rodzaje zakrętów (NE, NW, SE, SW)
    # --------------------------------------------------------------------------
    def test_04_all_corner_turns(self):
        """All 4 turn types (South-East, South-West, North-East, North-West) form proper quadrants."""
        # 1. Turn SE (comes from South, goes East) -> has S and E
        tl, tr, bl, br = resolve_quadrant_states(
            has_n=False, has_s=True, has_w=False, has_e=True,
            has_nw=False, has_ne=False, has_sw=False, has_se=False,
        )
        self.assertEqual(tl, QUAD_OUTER_CORNER)
        self.assertEqual(tr, QUAD_EDGE_H)
        self.assertEqual(bl, QUAD_EDGE_V)
        self.assertEqual(br, QUAD_INNER_CORNER)

        # 2. Turn SW (comes from South, goes West) -> has S and W
        tl, tr, bl, br = resolve_quadrant_states(
            has_n=False, has_s=True, has_w=True, has_e=False,
            has_nw=False, has_ne=False, has_sw=False, has_se=False,
        )
        self.assertEqual(tl, QUAD_EDGE_H)
        self.assertEqual(tr, QUAD_OUTER_CORNER)
        self.assertEqual(bl, QUAD_INNER_CORNER)
        self.assertEqual(br, QUAD_EDGE_V)

        # 3. Turn NE (comes from North, goes East) -> has N and E
        tl, tr, bl, br = resolve_quadrant_states(
            has_n=True, has_s=False, has_w=False, has_e=True,
            has_nw=False, has_ne=False, has_sw=False, has_se=False,
        )
        self.assertEqual(tl, QUAD_EDGE_V)
        self.assertEqual(tr, QUAD_INNER_CORNER)
        self.assertEqual(bl, QUAD_OUTER_CORNER)
        self.assertEqual(br, QUAD_EDGE_H)

        # 4. Turn NW (comes from North, goes West) -> has N and W
        tl, tr, bl, br = resolve_quadrant_states(
            has_n=True, has_s=False, has_w=True, has_e=False,
            has_nw=False, has_ne=False, has_sw=False, has_se=False,
        )
        self.assertEqual(tl, QUAD_INNER_CORNER)
        self.assertEqual(tr, QUAD_EDGE_V)
        self.assertEqual(bl, QUAD_EDGE_H)
        self.assertEqual(br, QUAD_OUTER_CORNER)

    # --------------------------------------------------------------------------
    # 5. Rozgałęzienia i skrzyżowania (T-junctions and 4-way cross)
    # --------------------------------------------------------------------------
    def test_05_junctions_and_four_way_cross(self):
        """Crossroads (N+S+E+W with no diagonals) properly resolve 4 inner corners."""
        tl, tr, bl, br = resolve_quadrant_states(
            has_n=True, has_s=True, has_w=True, has_e=True,
            has_nw=False, has_ne=False, has_sw=False, has_se=False,
        )
        self.assertEqual((tl, tr, bl, br), (
            QUAD_INNER_CORNER, QUAD_INNER_CORNER, QUAD_INNER_CORNER, QUAD_INNER_CORNER
        ))

    # --------------------------------------------------------------------------
    # 6. Zamknięte obszary (Inner corners & donuts/loops)
    # --------------------------------------------------------------------------
    def test_06_donut_loop_with_inner_pond(self):
        """A 6x6 square with a 2x2 hole in the middle correctly renders inner corners."""
        coords = []
        for r in range(4, 10):
            for c in range(4, 10):
                if not (r in (6, 7) and c in (6, 7)):
                    coords.append((c, r))
        self.engine.apply_rpg_autotile_stroke(self.layer, coords, self.autotile, self.project)

        # Cell (5, 6) is on the left border of the hole, facing East into empty space
        m = self.engine.compute_rpg_mask(self.layer, 5, 6, self.autotile, self.project)
        self.assertTrue(m & MASK_N)
        self.assertTrue(m & MASK_S)
        self.assertTrue(m & MASK_W)
        self.assertFalse(m & MASK_E)  # Hole to the East

        # Top-left of the hole is (6, 6). The cell directly above-left of the hole is (5, 5).
        # (5, 5) has N, S, W, E and NW, NE, SW present, but NOT SE (since (6, 6) is the hole)!
        # So at (5, 5), quadrant BR is an INNER CORNER!
        m_inner = self.engine.compute_rpg_mask(self.layer, 5, 5, self.autotile, self.project)
        tl, tr, bl, br = mask_to_quadrant_states(m_inner)
        self.assertEqual(br, QUAD_INNER_CORNER)

    # --------------------------------------------------------------------------
    # 7. Usuwanie fragmentów ze środka (Adapts surrounding borders)
    # --------------------------------------------------------------------------
    def test_07_erasing_middle_adapts_neighbors(self):
        """Erasing the center of a 3x3 filled area adapts the 8 neighbors to form an inner border."""
        coords = [(c, r) for r in range(5, 8) for c in range(5, 8)]
        self.engine.apply_rpg_autotile_stroke(self.layer, coords, self.autotile, self.project)

        # Before erase: (6, 5) had South neighbor (6, 6)
        m_before = self.engine.compute_rpg_mask(self.layer, 6, 5, self.autotile, self.project)
        self.assertTrue(m_before & MASK_S)

        # Erase center cell (6, 6)
        self.layer.remove_tile(6, 6)
        changes = self.engine.update_rpg_neighbors_after_erase(self.layer, [(6, 6)], self.project)
        self.assertIn((6, 5), changes)

        # After erase: (6, 5) no longer has South neighbor
        m_after = self.engine.compute_rpg_mask(self.layer, 6, 5, self.autotile, self.project)
        self.assertFalse(m_after & MASK_S)

    # --------------------------------------------------------------------------
    # 8. Łączenie i rozdzielanie powierzchni (Merging and splitting)
    # --------------------------------------------------------------------------
    def test_08_merge_and_split_patches(self):
        """Two separated paths merge into one connected path when bridge tile is placed."""
        left_path = [(3, 5), (4, 5)]
        right_path = [(6, 5), (7, 5)]
        self.engine.apply_rpg_autotile_stroke(self.layer, left_path + right_path, self.autotile, self.project)

        # (4, 5) initially has no East neighbor
        m_left_end = self.engine.compute_rpg_mask(self.layer, 4, 5, self.autotile, self.project)
        self.assertFalse(m_left_end & MASK_E)

        # Place bridge tile at (5, 5)
        self.engine.apply_rpg_autotile_stroke(self.layer, [(5, 5)], self.autotile, self.project)

        # Now (4, 5) has East neighbor
        m_left_connected = self.engine.compute_rpg_mask(self.layer, 4, 5, self.autotile, self.project)
        self.assertTrue(m_left_connected & MASK_E)

    # --------------------------------------------------------------------------
    # 9. Sąsiadowanie różnych Autotile (Independence)
    # --------------------------------------------------------------------------
    def test_09_multiple_independent_autotiles(self):
        """Different Autotiles (Grass and Water) side-by-side maintain independent boundaries."""
        water_autotile = RPGAutotile(
            name="Deep Water",
            terrain_type="Water",
            autotile_format=AutotileFormat.XP_3X4,
            tile_size=32,
            source_image_path=self.xp_path,
        )
        water_autotile.rebuild_atlas()
        self.engine.register_rpg_autotile(water_autotile)

        # Place grass at (5, 5) and water at (6, 5)
        self.engine.apply_rpg_autotile_stroke(self.layer, [(5, 5)], self.autotile, self.project)
        self.engine.apply_rpg_autotile_stroke(self.layer, [(6, 5)], water_autotile, self.project)

        # Grass at (5, 5) should NOT treat Water at (6, 5) as same terrain
        m_grass = self.engine.compute_rpg_mask(self.layer, 5, 5, self.autotile, self.project)
        self.assertEqual(m_grass, 0)  # Isolated outer corners

        m_water = self.engine.compute_rpg_mask(self.layer, 6, 5, water_autotile, self.project)
        self.assertEqual(m_water, 0)  # Isolated outer corners

    # --------------------------------------------------------------------------
    # 10. Współpracę z wieloma warstwami (Layer isolation)
    # --------------------------------------------------------------------------
    def test_10_layer_isolation(self):
        """Autotile calculations are strictly scoped to the active layer."""
        layer2 = self.project.add_layer("Foreground Layer")
        self.engine.apply_rpg_autotile_stroke(self.layer, [(5, 5)], self.autotile, self.project)
        self.engine.apply_rpg_autotile_stroke(layer2, [(6, 5)], self.autotile, self.project)

        # (5, 5) on layer 1 does not connect to (6, 5) on layer 2
        m_l1 = self.engine.compute_rpg_mask(self.layer, 5, 5, self.autotile, self.project)
        self.assertEqual(m_l1, 0)

    # --------------------------------------------------------------------------
    # 11. Undo / Redo (Single command restoring exact state)
    # --------------------------------------------------------------------------
    def test_11_brush_undo_redo_with_rpg_autotile(self):
        """Brush stroke with SelectedAutotile produces a single atomic undo/redo command."""
        tool = BrushTool()
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history,
            autotile_engine=self.engine,
            selected_asset=SelectedAutotile(self.autotile),
        )

        tool.on_press(5, 5, ctx)
        tool.on_drag(6, 5, ctx)
        tool.on_release(6, 5, ctx)

        self.assertEqual(len(self.history.undo_stack), 1)
        self.assertIsNotNone(self.layer.get_tile(5, 5))
        self.assertIsNotNone(self.layer.get_tile(6, 5))

        # Undo
        self.history.undo()
        self.assertIsNone(self.layer.get_tile(5, 5))
        self.assertIsNone(self.layer.get_tile(6, 5))

        # Redo
        self.history.redo()
        self.assertIsNotNone(self.layer.get_tile(5, 5))
        self.assertIsNotNone(self.layer.get_tile(6, 5))

    # --------------------------------------------------------------------------
    # 12. Zapis i ponowne otwarcie mapy (.tmmap serialization)
    # --------------------------------------------------------------------------
    def test_12_save_and_reload_tmmap_with_rpg_autotiles(self):
        """Project with RPG Maker autotiles saves to JSON and restores perfectly."""
        self.engine.apply_rpg_autotile_stroke(self.layer, [(3, 3), (3, 4)], self.autotile, self.project)

        save_path = os.path.join(self.test_dir, "test_autotile_project.tmmap")
        success = ProjectIO.save_project(self.project, self.asset_mgr, save_path, autotile_engine=self.engine)
        self.assertTrue(success)

        # Reload into new engine & project
        reloaded_engine = AutoTileEngine()
        reloaded_asset_mgr = AssetManager()
        loaded_project = ProjectIO.load_project(save_path, reloaded_asset_mgr, autotile_engine=reloaded_engine)

        self.assertIsNotNone(loaded_project)
        self.assertIn(self.autotile.id, reloaded_engine.rpg_autotiles)
        restored_at = reloaded_engine.rpg_autotiles[self.autotile.id]
        self.assertEqual(restored_at.name, "Meadow Grass")
        self.assertEqual(restored_at.format, AutotileFormat.VX_ACE_2X3)

    # --------------------------------------------------------------------------
    # 13. Duże mapy i wydajność (100x100 fast local radius-1 update)
    # --------------------------------------------------------------------------
    def test_13_large_map_performance(self):
        """Drawing on a 100x100 map computes in under 5 milliseconds (local radius-1)."""
        import time
        big_project = Project(tile_size=32, map_width=100, map_height=100)
        big_layer = big_project.get_active_layer()

        t0 = time.perf_counter()
        # Draw a 20-tile stroke
        coords = [(i, 50) for i in range(10, 30)]
        changes = self.engine.apply_rpg_autotile_stroke(big_layer, coords, self.autotile, big_project)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 0.05)  # Well under 50ms (usually < 2ms)
        self.assertEqual(len(changes), 20)

    # --------------------------------------------------------------------------
    # 14. Różne formaty źródłowych arkuszy (VX Ace, XP, Simple 3x3)
    # --------------------------------------------------------------------------
    def test_14_different_source_formats_slicing_and_detection(self):
        """Auto-detection and composite atlas generation works across VX Ace, XP, and 3x3."""
        # 1. Format detection
        self.assertEqual(detect_autotile_format(64, 96, 32), AutotileFormat.VX_ACE_2X3)
        self.assertEqual(detect_autotile_format(96, 128, 32), AutotileFormat.XP_3X4)
        self.assertEqual(detect_autotile_format(96, 96, 32), AutotileFormat.SIMPLE_3X3)

        # 2. XP 3x4 synthesis
        xp_at = RPGAutotile(
            name="XP Water",
            terrain_type="Water",
            autotile_format=AutotileFormat.XP_3X4,
            tile_size=32,
            source_image_path=self.xp_path,
        )
        self.assertTrue(xp_at.rebuild_atlas())
        self.assertEqual(xp_at.atlas_pixmap.width(), 8 * 32)
        self.assertEqual(xp_at.atlas_pixmap.height(), 6 * 32)

        # 3. Simple 3x3 synthesis
        s_at = RPGAutotile(
            name="Simple Sand",
            terrain_type="Sand",
            autotile_format=AutotileFormat.SIMPLE_3X3,
            tile_size=32,
            source_image_path=self.simple_path,
        )
        self.assertTrue(s_at.rebuild_atlas())
        self.assertEqual(s_at.atlas_pixmap.width(), 8 * 32)
        self.assertEqual(s_at.atlas_pixmap.height(), 6 * 32)


if __name__ == "__main__":
    unittest.main()
