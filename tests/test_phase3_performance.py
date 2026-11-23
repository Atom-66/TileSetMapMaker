import gc
import time
import unittest

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.history import HistoryManager, TileBatchCommand
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.models.asset import Asset, AssetType
from tileset_map_maker.models.layer import MapItem
from tileset_map_maker.models.project import Project

APP = QApplication.instance() or QApplication([])


class TestPhase3Performance(unittest.TestCase):
    def setUp(self):
        self.assets = AssetManager()
        self.engine = RenderEngine(self.assets)

    def _render_viewport(self, size: int) -> float:
        project = Project(map_width=size, map_height=size, tile_size=32)
        layer = project.get_active_layer()
        for row in range(20):
            for col in range(32):
                layer.tiles[(col, row)] = MapItem("missing", col, row)
        image = QImage(1024, 640, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        options = RenderOptions(show_grid=True, render_checkerboard=False)
        started = time.perf_counter()
        self.engine.render(
            painter,
            project,
            options,
            clip_rect=QRectF(0, 0, 1024, 640),
        )
        painter.end()
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.assertLess(
            self.engine.metrics.visible_items[-1],
            800,
            "Viewport rendering must not traverse and draw the whole map",
        )
        return elapsed_ms

    def test_large_map_viewport_benchmarks(self):
        timings = {
            size: self._render_viewport(size) for size in (100, 500, 1000)
        }
        self.assertLess(max(timings.values()), 1000)
        self.assertGreaterEqual(len(self.engine.metrics.render_ms), 3)

    def test_render_metrics_report_memory_and_samples(self):
        self._render_viewport(100)
        summary = self.engine.metrics.summary()
        self.assertGreater(summary["last_render_ms"], 0)
        self.assertGreaterEqual(summary["memory_mb"], 0)
        self.assertEqual(summary["samples"], 1)

    def test_history_remains_bounded_after_repeated_edits(self):
        project = Project(map_width=10, map_height=10)
        layer = project.get_active_layer()
        history = HistoryManager(max_history=100)
        for index in range(250):
            after = MapItem("asset", 1, 1)
            history.push(
                TileBatchCommand(
                    project,
                    layer.id,
                    {(1, 1): (layer.get_tile(1, 1), after)},
                )
            )
            layer.set_tile(1, 1, after)
        self.assertEqual(len(history.undo_stack), 100)
        for _ in range(100):
            self.assertTrue(history.undo())
        self.assertFalse(history.undo())
        del after
        gc.collect()
        self.assertEqual(len(history.redo_stack), 100)

    def test_asset_search_index_handles_large_library(self):
        for index in range(1500):
            asset = Asset.__new__(Asset)
            asset.id = f"asset-{index}"
            asset.name = f"Terrain {index:04d}"
            asset.category_path = "World/Terrain"
            asset.asset_type = AssetType.TILESET
            asset.is_favorite = index % 10 == 0
            self.assets.assets[asset.id] = asset
        self.assets.invalidate_search_index()
        started = time.perf_counter()
        first = self.assets.search_assets("Terrain 1499")
        repeated = self.assets.search_assets("Terrain 1499")
        elapsed = (time.perf_counter() - started) * 1000
        self.assertEqual([asset.id for asset in first], ["asset-1499"])
        self.assertEqual(first, repeated)
        self.assertLess(elapsed, 1000)

    def test_tile_texture_cache_is_reused_and_bounded(self):
        self.assets._pixmap_cache["asset"] = QPixmap(32, 32)
        project = Project(map_width=4, map_height=4)
        layer = project.get_active_layer()
        for col in range(4):
            for row in range(4):
                item = MapItem("asset", col, row, rotation=90)
                layer.set_tile(col, row, item)
        image = QImage(128, 128, QImage.Format.Format_ARGB32)
        for _ in range(4):
            painter = QPainter(image)
            self.engine.render(
                painter,
                project,
                RenderOptions(show_grid=False, render_checkerboard=False),
            )
            painter.end()
        self.assertEqual(len(self.engine._tile_pixmap_cache), 1)
        self.assertLessEqual(
            len(self.engine._tile_pixmap_cache),
            self.engine._tile_cache_limit,
        )

    def test_source_texture_cache_evicts_old_entries(self):
        self.assets._texture_cache_limit_bytes = 16
        self.assets._pixmap_cache["first"] = QPixmap(4, 4)
        self.assets._pixmap_cache["second"] = QPixmap(4, 4)
        self.assets._evict_texture_cache(
            self.assets._pixmap_cache,
            lambda cached: cached.width() * cached.height() * 4,
        )
        self.assertEqual(len(self.assets._pixmap_cache), 1)
        self.assertIn("second", self.assets._pixmap_cache)

    def test_rapid_viewport_pan_and_zoom_stays_responsive(self):
        project = Project(map_width=1000, map_height=1000)
        layer = project.get_active_layer()
        for index in range(2000):
            layer.tiles[(index % 1000, index // 1000)] = MapItem(
                "missing", index % 1000, index // 1000
            )
        image = QImage(800, 600, QImage.Format.Format_ARGB32)
        started = time.perf_counter()
        for step in range(30):
            x = (step * 32_000) % 31_000
            y = (step * 6400) % 31_000
            painter = QPainter(image)
            self.engine.render(
                painter,
                project,
                RenderOptions(show_grid=True, render_checkerboard=False),
                clip_rect=QRectF(x, y, 800 + step * 8, 600 + step * 6),
            )
            painter.end()
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 3.0)
        self.assertEqual(len(self.engine.metrics.render_ms), 30)


if __name__ == "__main__":
    unittest.main()
