import unittest
import sys
import os
import tempfile
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.models.project import Project
from tileset_map_maker.models.layer import ItemType, MapItem
from tileset_map_maker.models.brush_preset import BrushSettings, TileVariant
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.fill import FillTool
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.rpg_autotile import RPGAutotile, SelectedAutotile


class TestTileRandomizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.project = Project(name="RandomizerTest", map_width=20, map_height=20, tile_size=32)
        self.layer = self.project.add_layer("Ground")
        self.asset_mgr = AssetManager()
        self.history_mgr = HistoryManager()
        self.autotile_engine = AutoTileEngine()

        # Create a mock tileset asset
        self.asset = Asset(name="GrassTileset", file_path="dummy.png", asset_type=AssetType.TILESET)
        self.asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.asset_mgr.assets[self.asset.id] = self.asset

    def _create_subtiles(self, count: int) -> list:
        """Helper to create N distinct subtiles (A, B, C, ...)."""
        subs = []
        for i in range(count):
            sub = SelectedSubTile(
                asset_id=self.asset.id,
                col=i % 4,
                row=i // 4,
                cols_count=1,
                rows_count=1,
                sub_x=(i % 4) * 32,
                sub_y=(i // 4) * 32,
                sub_w=32,
                sub_h=32,
                tile_width=32,
                tile_height=32,
                asset_name=f"Grass_{chr(65 + i)}",
            )
            subs.append(sub)
        return subs

    def test_01_group_of_2_tiles(self):
        """1. Grupa z 2 kafelków."""
        bs = BrushSettings()
        bs.random_variant = True
        subs = self._create_subtiles(2)

        v1 = bs.add_variant(subs[0], weight=10.0, name="Grass A")
        v2 = bs.add_variant(subs[1], weight=10.0, name="Grass B")
        self.assertEqual(len(bs.variants), 2)

        picked = {bs.pick_variant(subs[0]).col for _ in range(50)}
        self.assertEqual(picked, {0, 1}, "Both variants must be picked over 50 iterations")

    def test_02_group_of_6_tiles_user_example(self):
        """2. Grupa z 6 kafelków (scenariusz użytkownika z 6 wariantami trawy A..F)."""
        bs = BrushSettings()
        bs.random_variant = True
        subs = self._create_subtiles(6)
        for s in subs:
            bs.add_variant(s, weight=10.0)

        self.assertEqual(len(bs.variants), 6)

        results = [bs.pick_variant(subs[0]) for _ in range(100)]
        cols = {r.col for r in results}
        rows = {r.row for r in results}
        # In 100 picks with equal weights, all 6 variants should be observed
        coords = {(r.col, r.row) for r in results}
        self.assertEqual(len(coords), 6, "All 6 grass variants must be drawn")

    def test_03_group_of_many_tiles(self):
        """3. Grupa z kilkunastu kafelków (np. 16 kafelków 4x4)."""
        bs = BrushSettings()
        bs.random_variant = True
        subs = self._create_subtiles(16)
        for s in subs:
            bs.add_variant(s, weight=5.0)

        self.assertEqual(len(bs.variants), 16)
        results = [bs.pick_variant(subs[0]) for _ in range(300)]
        coords = {(r.col, r.row) for r in results}
        self.assertEqual(len(coords), 16, "All 16 variants must be picked over 300 trials")

    def test_04_equal_weights_distribution(self):
        """4. Losowanie z jednakowymi wagami."""
        bs = BrushSettings(seed=42)
        bs.random_variant = True
        subs = self._create_subtiles(3)
        for s in subs:
            bs.add_variant(s, weight=10.0)

        counts = {0: 0, 1: 0, 2: 0}
        trials = 3000
        for _ in range(trials):
            res = bs.pick_variant(subs[0])
            counts[res.col] += 1

        # Each should be roughly 1/3 (1000 +- 150)
        for c in counts:
            self.assertGreater(counts[c], 850)
            self.assertLess(counts[c], 1150)

    def test_05_different_weights_distribution(self):
        """5. Losowanie z różnymi wagami (np. 90 vs 10)."""
        bs = BrushSettings(seed=999)
        bs.random_variant = True
        subs = self._create_subtiles(2)
        bs.add_variant(subs[0], weight=90.0)  # 90%
        bs.add_variant(subs[1], weight=10.0)  # 10%

        counts = {0: 0, 1: 0}
        trials = 1000
        for _ in range(trials):
            res = bs.pick_variant(subs[0])
            counts[res.col] += 1

        self.assertGreater(counts[0], 800, "High weight variant should be picked ~90% of times")
        self.assertLess(counts[1], 200, "Low weight variant should be picked ~10% of times")

    def test_06_single_click_painting(self):
        """6. Malowanie pojedynczym kliknięciem."""
        bs = BrushSettings()
        bs.random_variant = True
        subs = self._create_subtiles(6)
        for s in subs:
            bs.add_variant(s)

        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
        )

        brush = BrushTool()
        brush.on_press(5, 5, ctx)
        brush.on_release(5, 5, ctx)

        tile = self.layer.get_tile(5, 5)
        self.assertIsNotNone(tile)
        self.assertEqual(tile.asset_id, self.asset.id)
        # Source coords must match one of the 6 variants
        valid_sources = {(s.sub_x, s.sub_y) for s in subs}
        self.assertIn((tile.source_x, tile.source_y), valid_sources)

    def test_07_dragging_stroke_independent_randomization(self):
        """7. Malowanie przez przeciąganie – każda komórka otrzymuje własny niezależny wariant."""
        bs = BrushSettings()
        bs.random_variant = True
        subs = self._create_subtiles(6)
        for s in subs:
            bs.add_variant(s)

        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
        )

        brush = BrushTool()
        brush.on_press(0, 0, ctx)
        for c in range(1, 10):
            brush.on_drag(c, 0, ctx)
        brush.on_release(9, 0, ctx)

        # 10 tiles painted in a row (0..9, 0)
        placed_sources = []
        for c in range(10):
            t = self.layer.get_tile(c, 0)
            self.assertIsNotNone(t)
            placed_sources.append((t.source_x, t.source_y))

        unique_variants = set(placed_sources)
        self.assertGreater(len(unique_variants), 1, "Stroke must NOT repeat a single variant across all cells")

    def test_08_bucket_fill_with_randomizer(self):
        """8. Wypełnianie obszaru (FillTool) z włączonym randomizerem."""
        bs = BrushSettings()
        bs.random_variant = True
        subs = self._create_subtiles(6)
        for s in subs:
            bs.add_variant(s)

        # Place initial boundary or leave empty (empty flood fill)
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
        )

        fill = FillTool()
        fill.on_press(0, 0, ctx)

        # Entire 20x20 map should now be filled with diverse variants
        placed_sources = set()
        for r in range(5):
            for c in range(5):
                t = self.layer.get_tile(c, r)
                self.assertIsNotNone(t)
                placed_sources.add((t.source_x, t.source_y))

        self.assertGreater(len(placed_sources), 1, "Bucket fill must use multiple randomized variants")

    def test_09_undo_redo_preserves_exact_variants(self):
        """9. Undo/redo przywraca dokładnie te same warianty, które zostały umieszczone."""
        bs = BrushSettings()
        bs.random_variant = True
        subs = self._create_subtiles(6)
        for s in subs:
            bs.add_variant(s)

        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
        )

        brush = BrushTool()
        brush.on_press(2, 2, ctx)
        brush.on_drag(3, 2, ctx)
        brush.on_release(3, 2, ctx)

        t1_orig = self.layer.get_tile(2, 2).clone()
        t2_orig = self.layer.get_tile(3, 2).clone()

        # Undo
        self.history_mgr.undo()
        self.assertIsNone(self.layer.get_tile(2, 2))
        self.assertIsNone(self.layer.get_tile(3, 2))

        # Redo
        self.history_mgr.redo()
        t1_redo = self.layer.get_tile(2, 2)
        t2_redo = self.layer.get_tile(3, 2)
        self.assertIsNotNone(t1_redo)
        self.assertIsNotNone(t2_redo)
        self.assertEqual((t1_redo.source_x, t1_redo.source_y), (t1_orig.source_x, t1_orig.source_y))
        self.assertEqual((t2_redo.source_x, t2_redo.source_y), (t2_orig.source_x, t2_orig.source_y))

    def test_10_save_and_reload_map_preserves_exact_variants(self):
        """10. Zapis i ponowne otwarcie mapy – brak ponownego losowania przy wczytaniu."""
        bs = BrushSettings()
        bs.random_variant = True
        subs = self._create_subtiles(6)
        for s in subs:
            bs.add_variant(s)

        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
        )

        brush = BrushTool()
        brush.on_press(4, 4, ctx)
        brush.on_release(4, 4, ctx)

        tile_before = self.layer.get_tile(4, 4)

        with tempfile.NamedTemporaryFile(suffix=".tmmap", delete=False) as tf:
            temp_path = tf.name

        try:
            ProjectIO.save_project(self.project, self.asset_mgr, temp_path)
            loaded_proj = ProjectIO.load_project(temp_path, self.asset_mgr)

            loaded_layer = loaded_proj.get_layer(self.layer.id)
            tile_after = loaded_layer.get_tile(4, 4)

            self.assertIsNotNone(tile_after)
            self.assertEqual(tile_after.asset_id, tile_before.asset_id)
            self.assertEqual(tile_after.source_x, tile_before.source_x)
            self.assertEqual(tile_after.source_y, tile_before.source_y)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_11_interaction_and_precedence_with_autotiling(self):
        """11. Współpraca z Auto Tiling – Auto Tiling ma jasny priorytet kształtowania terenu."""
        from PyQt6.QtGui import QImage, QColor
        autotile = RPGAutotile(id="grass_auto", name="GrassAuto", terrain_type="GrassAuto", tileset_id=self.asset.id, tile_size=32)
        src_img = QImage(64, 96, QImage.Format.Format_ARGB32)
        src_img.fill(QColor(50, 180, 70, 255))
        autotile.set_source_qimage(src_img)
        self.autotile_engine.register_rpg_autotile(autotile, self.asset_mgr)

        bs = BrushSettings()
        bs.selected_autotile = SelectedAutotile(autotile)
        bs.random_variant = True
        subs = self._create_subtiles(6)
        for s in subs:
            bs.add_variant(s)

        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            autotile_engine=self.autotile_engine,
            brush_settings=bs,
        )

        brush = BrushTool()
        brush.on_press(3, 3, ctx)
        brush.on_release(3, 3, ctx)

        tile = self.layer.get_tile(3, 3)
        self.assertIsNotNone(tile)
        self.assertTrue(tile.is_auto_tiled)
        self.assertEqual(tile.terrain_type, "GrassAuto")

    def test_12_disable_randomization_returns_to_standard_painting(self):
        """12. Wyłączenie randomizacji i powrót do zwykłego malowania."""
        bs = BrushSettings()
        bs.random_variant = False
        subs = self._create_subtiles(6)
        for s in subs:
            bs.add_variant(s)

        default_sub = subs[2]  # Grass C
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            selected_asset=default_sub,
            brush_settings=bs,
        )

        brush = BrushTool()
        brush.on_press(1, 1, ctx)
        brush.on_drag(2, 1, ctx)
        brush.on_release(2, 1, ctx)

        # Both tiles must be exactly default_sub (Grass C)
        t1 = self.layer.get_tile(1, 1)
        t2 = self.layer.get_tile(2, 1)
        self.assertEqual((t1.source_x, t1.source_y), (default_sub.sub_x, default_sub.sub_y))
        self.assertEqual((t2.source_x, t2.source_y), (default_sub.sub_x, default_sub.sub_y))

    def test_13_avoid_adjacent_duplicates(self):
        """13. Tryb ograniczający powtarzanie identycznych kafelków obok siebie."""
        bs = BrushSettings()
        bs.random_variant = True
        bs.avoid_adjacent = True
        subs = self._create_subtiles(3)
        for s in subs:
            bs.add_variant(s)

        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.asset_mgr,
            history_manager=self.history_mgr,
            brush_settings=bs,
        )

        brush = BrushTool()
        brush.on_press(0, 0, ctx)
        for c in range(1, 15):
            brush.on_drag(c, 0, ctx)
        brush.on_release(14, 0, ctx)

        # Verify no two adjacent cells in the line have identical source coords
        for c in range(14):
            t_curr = self.layer.get_tile(c, 0)
            t_next = self.layer.get_tile(c + 1, 0)
            self.assertNotEqual(
                (t_curr.source_x, t_curr.source_y),
                (t_next.source_x, t_next.source_y),
                f"Adjacent tiles at col {c} and {c+1} must not be identical when avoid_adjacent is active",
            )


if __name__ == "__main__":
    unittest.main()
