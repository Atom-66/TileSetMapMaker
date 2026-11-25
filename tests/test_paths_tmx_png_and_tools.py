import base64
import gzip
import hashlib
import math
import os
import struct
import sys
import tempfile
import unittest
import zlib
import xml.etree.ElementTree as ET

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QImage, QPainter, QMouseEvent
from PyQt6.QtWidgets import QApplication

APP = QApplication.instance() or QApplication(sys.argv)

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.core.external_formats import TiledTMX
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.rpg_autotile import (
    CustomPathVariant,
    RPGAutotile,
    SelectedAutotile,
    analyze_tileset_region,
    create_rpg_autotile_from_tile,
    synthesize_from_single_tile,
    synthesize_from_tileset_context,
    synthesize_vx_ace_from_2x2,
    synthesize_vx_ace_from_3x3,
)
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.models.asset import AssetType, TilesetConfig
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.models.layer import MapItem
from tileset_map_maker.models.project import Project
from tileset_map_maker.ui.dialogs.import_png_map_dialog import ImportPngMapDialog
from tileset_map_maker.ui.dialogs.path_generator_dialog import PathGeneratorDialog
from tileset_map_maker.ui.map_canvas import MapCanvas
from tileset_map_maker.ui.main_window import MainWindow


class TestPathsExpanded(unittest.TestCase):
    """Tests for Part I: 3x3 transparent-center fix, 2x2 blocks, multi-tile WxH custom variants."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sheet_path = os.path.join(self.tmp.name, "lpc_sheet.png")
        # 256x256 sheet (8x8 tiles of 32x32):
        # - Cols 0..2, Rows 0..2: LPC-style 3x3 ring with TRANSPARENT center at (1,1)!
        # - Cols 4..5, Rows 0..1: 2x2 grass/sand transition block
        # - Cols 0..1, Rows 4..5: 2x2 custom crossing graphic (distinct purple/gold pixels)
        # - Cols 3..4, Row 4: 2x1 horizontal bridge graphic
        img = QImage(256, 256, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        p = QPainter(img)
        # 3x3 ring (outer 8 tiles opaque green/brown, center (1,1) transparent!)
        for r in range(3):
            for c in range(3):
                if (c, r) == (1, 1):
                    continue
                p.fillRect(c * 32, r * 32, 32, 32, QColor(80, 150, 60, 255))
        # 2x2 block at (4..5, 0..1)
        p.fillRect(4 * 32, 0, 64, 64, QColor(210, 175, 95, 255))
        # 2x2 custom crossing at (0..1, 4..5)
        p.fillRect(0, 4 * 32, 64, 64, QColor(180, 90, 220, 255))
        # 2x1 horizontal bridge at (3..4, 4)
        p.fillRect(3 * 32, 4 * 32, 64, 32, QColor(150, 100, 50, 255))
        p.end()
        self.assertTrue(img.save(self.sheet_path))

        self.am = AssetManager()
        self.asset, _, _ = self.am.import_single_file(self.sheet_path, force_asset_type=AssetType.TILESET)
        self.asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.engine = AutoTileEngine(asset_manager=self.am)

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_lpc_3x3_with_transparent_center_auto_fills_opaque_interior(self):
        sheet = self.am.get_pixmap(self.asset.id).toImage()
        analysis = analyze_tileset_region(sheet, 1, 1, 1, 1, 32)
        self.assertTrue(analysis["center_is_transparent"])
        self.assertEqual(analysis["suggested_mode"], "block_3x3_center")

        at = create_rpg_autotile_from_tile(
            "LPC Ring", self.asset.id, sheet, 1, 1, tile_size=32, mode="block_3x3_center"
        )
        atlas = at.get_atlas_pixmap(self.am).toImage()
        # Center mask 255 must be OPAQUE (not a black/transparent hole!)
        sx, sy, sw, sh = at.get_tile_slice_for_mask(255, 0, 0)
        center_px = atlas.pixelColor(sx + 16, sy + 16)
        self.assertGreater(center_px.alpha(), 200)
        self.assertGreater(center_px.green(), 100)

    def test_01b_two_by_two_hole_fill_does_not_mosaic_ring_colors(self):
        tile_size = 32
        ring = QImage(64, 64, QImage.Format.Format_ARGB32)
        ring.fill(QColor(220, 40, 40))
        painter = QPainter(ring)
        painter.fillRect(48, 0, 16, 64, QColor(40, 200, 40))
        painter.fillRect(0, 48, 64, 16, QColor(40, 40, 220))
        painter.fillRect(0, 0, 16, 64, QColor(220, 200, 40))
        painter.end()
        for y in range(16, 48):
            for x in range(16, 48):
                ring.setPixel(x, y, 0)

        source = synthesize_vx_ace_from_2x2(ring, tile_size)
        autotile = RPGAutotile(tile_size=tile_size)
        autotile.set_source_qimage(source)
        atlas = autotile.get_atlas_pixmap().toImage()
        sx, sy, _, _ = autotile.get_tile_slice_for_mask(255)
        row_colors = [
            atlas.pixelColor(sx + x, sy + tile_size // 2).rgba()
            for x in range(tile_size)
        ]
        color_runs = sum(
            row_colors[index] != row_colors[index - 1]
            for index in range(1, len(row_colors))
        )
        self.assertLessEqual(color_runs, 2)
        self.assertTrue(
            all(
                atlas.pixelColor(sx + x, sy + y).alpha() > 200
                for y in range(tile_size)
                for x in range(tile_size)
            )
        )

    def test_01c_three_by_three_inner_corners_use_local_ground_not_outer_corners(self):
        patch = QImage(96, 96, QImage.Format.Format_ARGB32)
        patch.fill(QColor(80, 170, 55))
        for x, y in ((0, 0), (64, 0), (0, 64), (64, 64)):
            painter = QPainter(patch)
            painter.fillRect(x, y, 32, 32, QColor(230, 20, 180))
            painter.end()
        for y in range(32, 64):
            for x in range(32, 64):
                patch.setPixel(x, y, 0)

        source = synthesize_vx_ace_from_3x3(patch, 32)
        for x, y in ((32, 0), (48, 0), (32, 16), (48, 16)):
            with self.subTest(inner_corner=(x, y)):
                for py in range(y, y + 16):
                    for px in range(x, x + 16):
                        color = source.pixelColor(px, py)
                        if color.alpha() > 0:
                            self.assertNotEqual(
                                (color.red(), color.green(), color.blue()),
                                (230, 20, 180),
                            )

    def test_02_block_2x2_synthesis_and_region_analysis(self):
        sheet = self.am.get_pixmap(self.asset.id).toImage()
        analysis = analyze_tileset_region(sheet, 4, 0, 2, 2, 32)
        self.assertEqual(analysis["suggested_mode"], "block_2x2")
        self.assertGreater(analysis["confidence"], 0.8)

        at = create_rpg_autotile_from_tile(
            "Sand 2x2", self.asset.id, sheet, 4, 0, tile_size=32, mode="block_2x2", w_tiles=2, h_tiles=2
        )
        self.assertTrue(at.has_valid_atlas(self.am))
        atlas = at.get_atlas_pixmap(self.am).toImage()
        sx, sy, sw, sh = at.get_tile_slice_for_mask(255, 0, 0)
        px = atlas.pixelColor(sx + 16, sy + 16)
        self.assertGreater(px.red(), 180)

    def test_02a_auto_mode_does_not_merge_disconnected_sprites_as_a_2x2_block(self):
        sheet = QImage(64, 64, QImage.Format.Format_ARGB32)
        sheet.fill(QColor(0, 0, 0, 0))
        painter = QPainter(sheet)
        painter.setBrush(QColor(220, 40, 40))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.drawEllipse(9, 9, 14, 14)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.fillRect(38, 6, 20, 20, QColor(40, 200, 40))
        painter.fillRect(6, 38, 20, 20, QColor(40, 40, 220))
        painter.fillRect(38, 38, 20, 20, QColor(220, 200, 40))
        painter.end()

        analysis = analyze_tileset_region(sheet, 0, 0, 2, 2, 32)
        self.assertEqual(analysis["suggested_mode"], "single_tile")
        generated, _, description = synthesize_from_tileset_context(
            sheet, 0, 0, 32, mode="auto", w_tiles=2, h_tiles=2
        )
        self.assertIn("Pojedynczy kafelek", description)
        self.assertFalse(generated.isNull())
        self.assertGreater(generated.pixelColor(16, 16).alpha(), 200)
        self.assertEqual(generated.pixelColor(0, 0).alpha(), 0)

    def test_02aa_auto_fallback_uses_the_most_opaque_tile_in_a_disconnected_selection(self):
        sheet = QImage(64, 64, QImage.Format.Format_ARGB32)
        sheet.fill(QColor(0, 0, 0, 0))
        painter = QPainter(sheet)
        painter.fillRect(32, 0, 32, 32, QColor(35, 155, 225))
        painter.fillRect(3, 35, 4, 4, QColor(220, 40, 40))
        painter.end()

        generated, _, description = synthesize_from_tileset_context(
            sheet, 0, 0, 32, mode="auto", w_tiles=2, h_tiles=2
        )

        self.assertIn("źródło (1, 0)", description)
        self.assertEqual(generated.pixelColor(16, 16).blue(), 225)

    def test_02b_arbitrary_region_preserves_all_selected_corners_without_stretching(self):
        tile_size = 32
        sheet = QImage(6 * tile_size, 6 * tile_size, QImage.Format.Format_ARGB32)
        painter = QPainter(sheet)
        for row in range(6):
            for col in range(6):
                painter.fillRect(
                    col * tile_size,
                    row * tile_size,
                    tile_size,
                    tile_size,
                    QColor(20 + col * 30, 20 + row * 30, 50 + (col + row) * 10),
                )
        painter.end()

        for col, row, width, height in ((1, 1, 2, 1), (2, 1, 1, 3), (1, 2, 4, 2)):
            with self.subTest(selection=(col, row, width, height)):
                generated, _, description = synthesize_from_tileset_context(
                    sheet, col, row, tile_size, mode="auto",
                    w_tiles=width, h_tiles=height,
                )
                self.assertFalse(generated.isNull())
                self.assertIn(f"{width}×{height}", description)
                generated_colors = {
                    generated.pixelColor(x, y).rgba()
                    for y in range(generated.height())
                    for x in range(generated.width())
                }
                for src_col, src_row in (
                    (col, row),
                    (col + width - 1, row),
                    (col, row + height - 1),
                    (col + width - 1, row + height - 1),
                ):
                    expected = QColor(
                        20 + src_col * 30,
                        20 + src_row * 30,
                        50 + (src_col + src_row) * 10,
                    )
                    self.assertIn(expected.rgba(), generated_colors)

    def test_02c_out_of_bounds_multi_tile_selection_is_rejected_as_a_whole(self):
        sheet = QImage(64, 64, QImage.Format.Format_ARGB32)
        sheet.fill(QColor(210, 80, 40))
        generated, _, description = synthesize_from_tileset_context(
            sheet, 1, 1, 32, mode="auto", w_tiles=2, h_tiles=2
        )
        self.assertFalse(generated.isNull())
        self.assertIn("poza zakresem", description.lower())
        self.assertEqual((generated.width(), generated.height()), (64, 96))

    def test_02d_organic_edges_stay_continuous_and_round_only_the_outer_corner(self):
        tile = QImage(32, 32, QImage.Format.Format_ARGB32)
        tile.fill(QColor(80, 150, 60))
        generated = synthesize_from_single_tile(tile, 32, "organic")
        straight_edge_y = 36
        self.assertTrue(
            all(
                generated.pixelColor(x, straight_edge_y).alpha() > 0
                for x in range(16, 32)
            )
        )
        self.assertEqual(generated.pixelColor(0, 32).alpha(), 0)
        self.assertGreater(generated.pixelColor(8, straight_edge_y).alpha(), 0)
        self.assertTrue(
            all(generated.pixelColor(x, 32).alpha() == 0 for x in range(32))
        )
        self.assertTrue(
            all(generated.pixelColor(x, 34).alpha() > 0 for x in range(3, 29))
        )

    def test_02e_four_way_cross_has_no_seams_on_joined_edges(self):
        tile = QImage(32, 32, QImage.Format.Format_ARGB32)
        for y in range(32):
            for x in range(32):
                tile.setPixelColor(
                    x,
                    y,
                    QColor(
                        int(140 + 25 * math.sin(2 * math.pi * x / 32)),
                        int(150 + 25 * math.sin(2 * math.pi * y / 32)),
                        int(100 + 15 * math.sin(2 * math.pi * (x + y) / 32)),
                    ),
                )
        generated = synthesize_from_single_tile(tile, 32, "organic")
        autotile = RPGAutotile(tile_size=32)
        autotile.set_source_qimage(generated)
        project = Project(map_width=5, map_height=5, tile_size=32)
        layer = project.get_active_layer()
        engine = AutoTileEngine()
        coords = (
            [(col, 2) for col in range(5)]
            + [(2, row) for row in range(5)]
        )
        engine.apply_rpg_autotile_stroke(layer, coords, autotile, project)

        atlas = autotile.get_atlas_pixmap().toImage()
        cross = QImage(160, 160, QImage.Format.Format_ARGB32)
        cross.fill(QColor(0, 0, 0, 0))
        painter = QPainter(cross)
        for (col, row), item in layer.tiles.items():
            sx, sy, sw, sh = autotile.get_tile_slice_for_mask(
                engine.compute_rpg_mask(layer, col, row, autotile, project),
                col,
                row,
            )
            painter.drawImage(col * 32, row * 32, atlas, sx, sy, sw, sh)
        painter.end()

        self.assertTrue(
            all(
                cross.pixelColor(x, 80).alpha() > 0
                for x in range(3, 157)
            )
        )
        self.assertTrue(
            all(
                cross.pixelColor(80, y).alpha() > 0
                for y in range(3, 157)
            )
        )
        for pixels in (
            [cross.pixelColor(x, 80) for x in range(3, 157)],
            [cross.pixelColor(80, y) for y in range(3, 157)],
        ):
            largest_color_step = max(
                sum(
                    abs(first_value - second_value)
                    for first_value, second_value in zip(
                        (
                            first.red(),
                            first.green(),
                            first.blue(),
                        ),
                        (
                            second.red(),
                            second.green(),
                            second.blue(),
                        ),
                    )
                )
                for first, second in zip(pixels, pixels[1:])
            )
            self.assertLess(largest_color_step, 40)

    def test_03_custom_2x2_and_2x1_multi_tile_variants_no_overlap_and_roundtrip(self):
        sheet = self.am.get_pixmap(self.asset.id).toImage()
        at = create_rpg_autotile_from_tile(
            "MultiPath", self.asset.id, sheet, 4, 0, tile_size=32, mode="block_2x2", w_tiles=2, h_tiles=2
        )
        # Bind a 2x2 custom crossing variant to full-center mask (255) with high priority
        v_2x2 = CustomPathVariant(
            mask=255,
            source_asset_id=self.asset.id,
            source_col=0,
            source_row=4,
            width_tiles=2,
            height_tiles=2,
            priority=50,
            weight=1.0,
            name="2x2 Plaza",
        )
        at.add_custom_variant(v_2x2)
        self.engine.register_rpg_autotile(at, self.am)

        project = Project(map_width=10, map_height=10, tile_size=32)
        layer = project.get_active_layer()
        # Paint a 4x4 block (cols 2..5, rows 2..5) so (3,3) has mask 255 and footprint (3..4, 3..4) fits 2x2!
        coords = [(c, r) for r in range(2, 6) for c in range(2, 6)]
        self.engine.apply_rpg_autotile_stroke(layer, coords, at, project, asset_manager=self.am)

        # Verify the 2x2 variant stamped all 4 exact sub-tiles without overlap
        for dr in range(2):
            for dc in range(2):
                t = layer.get_tile(3 + dc, 3 + dr)
                self.assertEqual(t.asset_id, self.asset.id)
                self.assertEqual((t.source_x, t.source_y), (dc * 32, (4 + dr) * 32))

        # Verify serialization round-trip preserves custom_variants & WxH source dims
        restored = RPGAutotile.from_dict(at.to_dict())
        self.assertEqual((restored.source_w_tiles, restored.source_h_tiles), (2, 2))
        self.assertEqual(len(restored.custom_variants), 1)
        self.assertEqual((restored.custom_variants[0].width_tiles, restored.custom_variants[0].height_tiles), (2, 2))

    def test_04_dialog_region_selection_and_custom_variant_ui(self):
        dlg = PathGeneratorDialog(self.engine, self.am, initial_asset_id=self.asset.id)
        dlg._on_region_selected(4, 0, 2, 2)
        self.assertEqual((dlg.selected_w_tiles, dlg.selected_h_tiles), (2, 2))
        self.assertIn("2×2", dlg.lbl_tile_coords.text())
        dlg._add_custom_variant()
        self.assertEqual(len(dlg.current_autotile.custom_variants), 1)
        dlg.close()

    def test_05_inner_corner_matches_brown_side_pattern_no_black_hole(self):
        """
        Reproduces the user's screenshot: 3x3 block with brown dirt outer border
        and green grass interior (with a transparent center gap).
        Verifies:
        1) Center is filled seamlessly with green grass from the inward-facing strips.
        2) Inner corners (Inner TL/TR/BL/BR) contain opaque BROWN dirt (NOT black/transparent holes!)
           matching the side border width and transitioning cleanly into green grass.
        """
        ts = 32
        patch = QImage(3 * ts, 3 * ts, QImage.Format.Format_ARGB32)
        patch.fill(QColor(0, 0, 0, 0))
        p = QPainter(patch)
        brown = QColor(168, 126, 78, 255)
        green = QColor(92, 160, 44, 255)
        # Fill outer 3x3 with brown dirt, inner 64x64 (offset 16..80) with green grass,
        # and leave center 32x32 (32..64) transparent!
        p.fillRect(0, 0, 3 * ts, 3 * ts, brown)
        p.fillRect(14, 14, 3 * ts - 28, 3 * ts - 28, green)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(ts, ts, ts, ts, QColor(0, 0, 0, 0))
        p.end()

        vx = synthesize_vx_ace_from_3x3(patch, ts)
        # 1. Center (half-tile (1,3) -> pixel (16..31, 48..63)) must be opaque green grass!
        c_px = vx.pixelColor(24, 56)
        self.assertEqual(c_px.alpha(), 255)
        self.assertGreater(c_px.green(), 140)

        # 2. Inner TL corner (at (32, 0), size 16x16):
        #    Top-left pixel (32+2, 2) MUST be opaque BROWN dirt (no transparent/black hole!)
        #    Bottom-right pixel (32+15, 15) MUST be opaque GREEN grass!
        inner_tl_corner = vx.pixelColor(34, 2)
        inner_tl_grass = vx.pixelColor(47, 15)
        self.assertEqual(inner_tl_corner.alpha(), 255, "Inner corner must NOT be transparent/black!")
        self.assertGreater(inner_tl_corner.red(), 140, f"Expected brown dirt, got {inner_tl_corner.getRgb()}")
        self.assertGreater(inner_tl_grass.green(), 140, f"Expected green grass, got {inner_tl_grass.getRgb()}")

        # 3. 1x1 isolated block (at (0, 0), size 32x32) must have a wide green grass center (>= 12px wide)
        green_center_pixels = sum(
            1
            for y in range(10, 22)
            for x in range(10, 22)
            if vx.pixelColor(x, y).green() > 140
        )
        self.assertGreater(green_center_pixels, 100, "1x1 isolated tile has too little green interior!")

    def test_05_archiving_saved_path_preserves_map_tiles_across_reload(self):
        autotile = create_rpg_autotile_from_tile(
            "Persistent path",
            self.asset.id,
            self.am.get_pixmap(self.asset.id).toImage(),
            0,
            0,
            tile_size=32,
        )
        self.engine.register_rpg_autotile(autotile, self.am)
        project = Project(name="Archived path", map_width=4, map_height=4, tile_size=32)
        project.layers[0].set_tile(
            1,
            1,
            MapItem(
                autotile.id,
                1,
                1,
                source_w=32,
                source_h=32,
                dest_w=32,
                dest_h=32,
            ),
        )

        dialog = PathGeneratorDialog(
            self.engine, self.am, initial_asset_id=self.asset.id
        )
        saved_index = dialog.cmb_saved.findData(autotile.id)
        self.assertGreaterEqual(saved_index, 0)
        dialog.cmb_saved.setCurrentIndex(saved_index)
        dialog._delete_saved_autotile()
        self.assertEqual(dialog.cmb_saved.findData(autotile.id), -1)
        dialog.close()

        self.assertTrue(autotile.archived)
        self.assertNotEqual(self.engine.active_rpg_autotile_id, autotile.id)
        self.assertIsNotNone(self.am.get_pixmap(autotile.id))

        project_path = os.path.join(self.tmp.name, "archived_path.tmmap")
        self.assertTrue(
            ProjectIO.save_project(project, self.am, project_path, self.engine)
        )
        reloaded_am = AssetManager()
        reloaded_engine = AutoTileEngine(asset_manager=reloaded_am)
        reloaded_project = ProjectIO.load_project(
            project_path, reloaded_am, reloaded_engine
        )

        self.assertIsNotNone(reloaded_project)
        self.assertTrue(reloaded_engine.rpg_autotiles[autotile.id].archived)
        self.assertIsNotNone(reloaded_am.get_pixmap(autotile.id))
        self.assertEqual(
            reloaded_project.layers[0].get_tile(1, 1).asset_id, autotile.id
        )


class TestPngMapImport(unittest.TestCase):
    """Tests for Part II (Section 6): PNG import as raster map or reference underlay."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.am = AssetManager()

    def tearDown(self):
        self.tmp.cleanup()

    def _make_png(self, name: str, w: int, h: int, color: QColor) -> str:
        path = os.path.join(self.tmp.name, name)
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        p = QPainter(img)
        p.fillRect(0, 0, w // 2, h, color)  # Left half colored, right half transparent!
        p.end()
        self.assertTrue(img.save(path))
        return path

    def test_01_import_small_large_transparent_and_nonsquare_png(self):
        cases = [
            ("small.png", 64, 64, "raster", 1.0),
            ("large.png", 1024, 768, "reference", 0.55),
            ("wide.png", 400, 120, "reference", 0.40),
        ]
        for fname, w, h, mode, opacity in cases:
            with self.subTest(fname=fname):
                path = self._make_png(fname, w, h, QColor(40, 130, 220, 255))
                with open(path, "rb") as f:
                    before_hash = hashlib.sha256(f.read()).hexdigest()

                proj = ProjectIO.import_png_as_map(path, self.am, mode=mode, tile_size=32, opacity=opacity)
                self.assertIsNotNone(proj)
                # Original file MUST NOT be modified
                with open(path, "rb") as f:
                    after_hash = hashlib.sha256(f.read()).hexdigest()
                self.assertEqual(before_hash, after_hash)

                # Bottom layer is object/raster layer with exact 1:1 dimensions (no stretching!)
                img_layer = proj.layers[0]
                self.assertEqual(img_layer.layer_type, "object")
                self.assertAlmostEqual(img_layer.opacity, opacity, places=2)
                self.assertEqual(len(img_layer.objects), 1)
                obj = img_layer.objects[0]
                self.assertEqual((obj.source_w, obj.source_h, obj.dest_w, obj.dest_h), (w, h, w, h))

                # Top layer is editable tile layer
                self.assertEqual(proj.layers[1].layer_type, "tile")
                self.assertEqual(proj.active_layer_id, proj.layers[1].id)

    def test_02_png_map_save_reload_and_alpha_preservation(self):
        path = self._make_png("alpha_map.png", 128, 96, QColor(200, 60, 80, 255))
        proj = ProjectIO.import_png_as_map(path, self.am, mode="raster", tile_size=32)
        project_dir = os.path.join(self.tmp.name, "project")
        os.makedirs(project_dir)
        save_path = os.path.join(project_dir, "png_project.tmmap")
        self.assertTrue(ProjectIO.save_project(proj, self.am, save_path))
        copied_assets = os.listdir(os.path.join(project_dir, "assets"))
        self.assertEqual(len(copied_assets), 1)
        self.assertTrue(
            os.path.isfile(os.path.join(project_dir, "assets", copied_assets[0]))
        )

        moved_project_dir = os.path.join(self.tmp.name, "moved_project")
        os.rename(project_dir, moved_project_dir)

        fresh_am = AssetManager()
        moved_save_path = os.path.join(moved_project_dir, "png_project.tmmap")
        reloaded = ProjectIO.load_project(moved_save_path, fresh_am)
        self.assertIsNotNone(reloaded)

        # Render to transparent QImage and verify left half colored, right half transparent
        out = QImage(128, 96, QImage.Format.Format_ARGB32)
        out.fill(QColor(0, 0, 0, 0))
        p = QPainter(out)
        RenderEngine(fresh_am).render(
            p, reloaded, RenderOptions(show_grid=False, show_selection=False, transparent_bg=True, render_checkerboard=False)
        )
        p.end()
        self.assertEqual(out.pixelColor(16, 16).red(), 200)
        self.assertEqual(out.pixelColor(100, 16).alpha(), 0)

    def test_03_import_png_dialog_options(self):
        path = self._make_png("dlg_test.png", 320, 160, QColor(100, 200, 100, 255))
        dlg = ImportPngMapDialog(path, default_tile_size=32)
        opts = dlg.get_options()
        self.assertEqual(opts["mode"], "reference")
        self.assertEqual(opts["tile_size"], 32)
        self.assertIn("10 × 5", dlg.lbl_grid_dims.text())
        dlg.close()


class TestTmxFullImportExport(unittest.TestCase):
    """Tests for Part II (Sections 7 & 8): CSV, XML, Base64 (raw/zlib/gzip), TSX, flips/rotations, missing assets, round-trip."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ts1_path = os.path.join(self.tmp.name, "ts1.png")
        self.ts2_path = os.path.join(self.tmp.name, "ts2.png")
        for path, color in ((self.ts1_path, QColor(50, 180, 60)), (self.ts2_path, QColor(60, 100, 220))):
            img = QImage(64, 64, QImage.Format.Format_ARGB32)
            img.fill(color)
            self.assertTrue(img.save(path))

        # External TSX file for ts2
        self.tsx_path = os.path.join(self.tmp.name, "ts2.tsx")
        with open(self.tsx_path, "w", encoding="utf-8") as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<tileset version="1.10" name="TS2" tilewidth="32" tileheight="32" tilecount="4" columns="2">\n'
                '  <image source="ts2.png" width="64" height="64"/>\n'
                '</tileset>\n'
            )

    def tearDown(self):
        self.tmp.cleanup()

    def _write_tmx(self, filename: str, layers_xml: str, extra_tilesets: str = "") -> str:
        path = os.path.join(self.tmp.name, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<map version="1.10" orientation="orthogonal" width="2" height="2" tilewidth="32" tileheight="32">\n'
                '  <properties><property name="author" type="string" value="tester"/></properties>\n'
                '  <tileset firstgid="1" name="TS1" tilewidth="32" tileheight="32" tilecount="4" columns="2">\n'
                '    <image source="ts1.png" width="64" height="64"/>\n'
                '  </tileset>\n'
                '  <tileset firstgid="5" source="ts2.tsx"/>\n'
                f'{extra_tilesets}\n'
                f'{layers_xml}\n'
                '</map>\n'
            )
        return path

    def test_01_all_encodings_csv_xml_base64_zlib_gzip_and_transforms(self):
        # 4 cells:
        # (0,0): gid=1 + 90 deg rotation (FLIP_H | FLIP_D)
        # (1,0): gid=5 (from external TSX!) + FLIP_H
        # (0,1): gid=2 + 270 deg rotation (FLIP_V | FLIP_D)
        # (1,1): gid=6 + 180 deg rotation (FLIP_H | FLIP_V)
        gids = [
            1 | TiledTMX.FLIP_H | TiledTMX.FLIP_D,
            5 | TiledTMX.FLIP_H,
            2 | TiledTMX.FLIP_V | TiledTMX.FLIP_D,
            6 | TiledTMX.FLIP_H | TiledTMX.FLIP_V,
        ]
        packed = struct.pack("<4I", *gids)
        b64_raw = base64.b64encode(packed).decode("ascii")
        b64_zlib = base64.b64encode(zlib.compress(packed)).decode("ascii")
        b64_gzip = base64.b64encode(gzip.compress(packed)).decode("ascii")
        xml_tiles = "".join(f'<tile gid="{g}"/>' for g in gids)
        csv_text = ",".join(str(g) for g in gids)

        layers_xml = (
            f'<layer name="CSV" width="2" height="2" opacity="0.8"><data encoding="csv">{csv_text}</data></layer>\n'
            f'<layer name="XML" width="2" height="2"><data>{xml_tiles}</data></layer>\n'
            f'<layer name="B64Raw" width="2" height="2"><data encoding="base64">{b64_raw}</data></layer>\n'
            f'<layer name="B64Zlib" width="2" height="2"><data encoding="base64" compression="zlib">{b64_zlib}</data></layer>\n'
            f'<layer name="B64Gzip" width="2" height="2" visible="0"><data encoding="base64" compression="gzip">{b64_gzip}</data></layer>\n'
        )
        tmx_path = self._write_tmx("all_enc.tmx", layers_xml)
        am = AssetManager()
        proj = ProjectIO.import_tmx(tmx_path, am)
        self.assertIsNotNone(proj, ProjectIO.get_last_error())
        self.assertEqual(len(proj.layers), 5)
        self.assertAlmostEqual(proj.layers[0].opacity, 0.8, places=2)
        self.assertFalse(proj.layers[4].visible)

        for layer in proj.layers:
            t00 = layer.get_tile(0, 0)
            t10 = layer.get_tile(1, 0)
            t01 = layer.get_tile(0, 1)
            t11 = layer.get_tile(1, 1)
            self.assertEqual((t00.rotation, t00.flip_x, t00.flip_y), (90.0, False, False))
            self.assertEqual((t10.rotation, t10.flip_x, t10.flip_y), (0.0, True, False))
            self.assertEqual((t01.rotation, t01.flip_x, t01.flip_y), (270.0, False, False))
            self.assertEqual((t11.rotation, t11.flip_x, t11.flip_y), (180.0, False, False))

    def test_02_missing_tsx_and_image_warns_without_crashing(self):
        tmx_path = self._write_tmx(
            "missing_res.tmx",
            '<layer name="L1" width="2" height="2"><data encoding="csv">1,0,0,5</data></layer>',
            extra_tilesets='<tileset firstgid="20" source="does_not_exist.tsx"/>',
        )
        am = AssetManager()
        proj = ProjectIO.import_tmx(tmx_path, am)
        self.assertIsNotNone(proj)
        warnings = ProjectIO.get_last_warnings()
        self.assertTrue(any("does_not_exist.tsx" in w for w in warnings))

    def test_03_image_layers_are_imported_in_document_order(self):
        tmx_path = self._write_tmx(
            "image_layer.tmx",
            '<layer name="Foreground" width="2" height="2"><data encoding="csv">1,0,0,0</data></layer>',
        )
        xml = ET.parse(tmx_path)
        root = xml.getroot()
        foreground = root.find("layer")
        root.remove(foreground)
        image_layer = ET.Element(
            "imagelayer", name="Background image", opacity="0.75", visible="1"
        )
        ET.SubElement(
            image_layer,
            "image",
            source="ts1.png",
            width="64",
            height="64",
        )
        root.append(image_layer)
        root.append(foreground)
        xml.write(tmx_path, encoding="utf-8", xml_declaration=True)

        manager = AssetManager()
        project = ProjectIO.import_tmx(tmx_path, manager)
        self.assertIsNotNone(project, ProjectIO.get_last_error())
        self.assertEqual(
            [layer.name for layer in project.layers],
            ["Background image", "Foreground"],
        )
        image_model = project.layers[0]
        self.assertEqual(image_model.layer_type, "object")
        self.assertAlmostEqual(image_model.opacity, 0.75)
        self.assertEqual(len(image_model.objects), 1)
        self.assertEqual(
            image_model.objects[0].object_type, "tiled_image_layer"
        )

    def test_03_offsets_and_tile_properties_are_supported_without_warnings(self):
        tmx_path = os.path.join(self.tmp.name, "unsupported_features.tmx")
        with open(tmx_path, "w", encoding="utf-8") as handle:
            handle.write(
                '<map orientation="orthogonal" width="2" height="2" tilewidth="32" tileheight="32">'
                '<tileset firstgid="1" name="TS1" tilewidth="32" tileheight="32" tilecount="4" columns="2">'
                '<tileoffset x="4" y="-2"/>'
                '<tile id="0"><properties><property name="terrain" value="sand"/></properties></tile>'
                '<image source="ts1.png" width="64" height="64"/>'
                '</tileset>'
                '<layer name="Offset" width="2" height="2" offsetx="4" offsety="0">'
                '<data encoding="csv">1,0,0,0</data></layer>'
                '</map>'
            )

        imported = ProjectIO.import_tmx(tmx_path, AssetManager())
        self.assertIsNotNone(imported, ProjectIO.get_last_error())
        warnings = ProjectIO.get_last_warnings()
        self.assertFalse(any("tileoffset" in warning for warning in warnings))
        self.assertFalse(any("Właściwości kafelka 0" in warning for warning in warnings))
        self.assertFalse(any("Warstwa 'Offset' ma offsety" in warning for warning in warnings))

    def test_03_tmx_full_round_trip(self):
        """Import TMX -> Save .tmmap -> Export TMX -> Re-import TMX preserves exact layout & transforms."""
        gids = [
            1 | TiledTMX.FLIP_H | TiledTMX.FLIP_D,
            5 | TiledTMX.FLIP_H,
            2 | TiledTMX.FLIP_V,
            6 | TiledTMX.FLIP_V | TiledTMX.FLIP_D,
        ]
        tmx_in = self._write_tmx(
            "roundtrip_in.tmx",
            f'<layer name="Ground" width="2" height="2"><data encoding="csv">{",".join(str(g) for g in gids)}</data></layer>',
        )
        am1 = AssetManager()
        p1 = ProjectIO.import_tmx(tmx_in, am1)
        self.assertIsNotNone(p1)

        tmmap_path = os.path.join(self.tmp.name, "mid.tmmap")
        self.assertTrue(ProjectIO.save_project(p1, am1, tmmap_path))

        am2 = AssetManager()
        p2 = ProjectIO.load_project(tmmap_path, am2)
        self.assertIsNotNone(p2)

        tmx_out = os.path.join(self.tmp.name, "roundtrip_out.tmx")
        self.assertTrue(ProjectIO.export_tmx(p2, am2, tmx_out))

        am3 = AssetManager()
        p3 = ProjectIO.import_tmx(tmx_out, am3)
        self.assertIsNotNone(p3)
        exported_tilesets = ET.parse(tmx_out).getroot().findall("tileset")
        self.assertEqual(
            [tileset.get("firstgid") for tileset in exported_tilesets], ["1", "5"]
        )
        l1 = p1.layers[0]
        l3 = p3.layers[0]
        for r in range(2):
            for c in range(2):
                a, b = l1.get_tile(c, r), l3.get_tile(c, r)
                self.assertEqual((a.rotation, a.flip_x, a.flip_y), (b.rotation, b.flip_x, b.flip_y))

    def test_05_margin_spacing_and_non_one_firstgid_are_preserved(self):
        image_path = os.path.join(self.tmp.name, "margined.png")
        image = QImage(70, 70, QImage.Format.Format_ARGB32)
        image.fill(QColor(210, 80, 40))
        self.assertTrue(image.save(image_path))
        input_path = os.path.join(self.tmp.name, "margined.tmx")
        with open(input_path, "w", encoding="utf-8") as handle:
            handle.write(
                '<map orientation="orthogonal" width="1" height="1" tilewidth="32" tileheight="32">'
                '<tileset firstgid="10" name="Margined" tilewidth="32" tileheight="32" '
                'tilecount="3" columns="2" margin="2" spacing="2">'
                '<image source="margined.png" width="70" height="70"/>'
                '</tileset>'
                '<layer name="Ground" width="1" height="1">'
                '<data encoding="csv">12</data></layer>'
                '</map>'
            )

        manager = AssetManager()
        project = ProjectIO.import_tmx(input_path, manager)
        self.assertIsNotNone(project, ProjectIO.get_last_error())
        tile = project.layers[0].get_tile(0, 0)
        self.assertEqual((tile.source_x, tile.source_y), (2, 36))
        output_path = os.path.join(self.tmp.name, "margined_out.tmx")
        self.assertTrue(ProjectIO.export_tmx(project, manager, output_path))
        root = ET.parse(output_path).getroot()
        exported_tileset = root.find("tileset")
        self.assertEqual(exported_tileset.get("firstgid"), "10")
        self.assertEqual(exported_tileset.get("tilecount"), "3")
        self.assertEqual(exported_tileset.get("columns"), "2")
        self.assertEqual(exported_tileset.get("margin"), "2")
        self.assertEqual(exported_tileset.get("spacing"), "2")
        self.assertEqual(root.find("./layer/data").text, "12")

        reloaded = ProjectIO.import_tmx(output_path, AssetManager())
        self.assertIsNotNone(reloaded, ProjectIO.get_last_error())
        self.assertEqual(
            (reloaded.layers[0].get_tile(0, 0).source_x,
             reloaded.layers[0].get_tile(0, 0).source_y),
            (2, 36),
        )

    def test_04_layer_and_tileset_offsets_and_tile_properties_round_trip(self):
        tmx_path = os.path.join(self.tmp.name, "offsets.tmx")
        with open(tmx_path, "w", encoding="utf-8") as handle:
            handle.write(
                '<map orientation="orthogonal" width="2" height="2" tilewidth="32" tileheight="32">'
                '<properties><property name="author" value="map-author"/></properties>'
                '<tileset firstgid="1" name="TS1" tilewidth="32" tileheight="32" tilecount="4" columns="2">'
                '<tileoffset x="2" y="3"/>'
                '<tile id="0"><properties><property name="ground" value="sand"/></properties></tile>'
                '<image source="ts1.png" width="64" height="64"/>'
                '</tileset>'
                '<layer name="Offset" width="1" height="1" offsetx="3" offsety="4">'
                '<properties><property name="custom-layer" type="bool" value="true"/></properties>'
                '<data encoding="csv">1</data></layer>'
                '</map>'
            )

        manager = AssetManager()
        project = ProjectIO.import_tmx(tmx_path, manager)
        self.assertIsNotNone(project, ProjectIO.get_last_error())
        layer = project.layers[0]
        item = layer.get_tile(0, 0)
        self.assertEqual(project.get_active_map().properties["author"], "map-author")
        self.assertTrue(layer.properties["custom-layer"])
        self.assertEqual((layer.offset_x, layer.offset_y), (3.0, 4.0))
        self.assertEqual((item.offset_x, item.offset_y), (2, 3))
        self.assertEqual(
            item.properties["tiled_tile_properties"], {"ground": "sand"}
        )
        canvas = MapCanvas(
            project,
            RenderEngine(manager),
            manager,
            HistoryManager(),
        )
        canvas.pan_offset = QPointF(0, 0)
        canvas.zoom = 1.0
        self.assertEqual(
            canvas._screen_to_layer_tile(QPointF(36, 38), layer), (1, 1)
        )
        canvas.close()

        rendered = QImage(64, 64, QImage.Format.Format_ARGB32)
        rendered.fill(QColor(0, 0, 0, 0))
        painter = QPainter(rendered)
        RenderEngine(manager).render(
            painter,
            project,
            RenderOptions(
                show_grid=False,
                show_selection=False,
                transparent_bg=True,
                render_checkerboard=False,
            ),
        )
        painter.end()
        self.assertEqual(rendered.pixelColor(5, 7).green(), 180)
        self.assertEqual(rendered.pixelColor(1, 1).alpha(), 0)

        project_dir = os.path.join(self.tmp.name, "tmmap")
        os.makedirs(project_dir)
        project_file = os.path.join(project_dir, "offsets.tmmap")
        self.assertTrue(ProjectIO.save_project(project, manager, project_file))
        manager = AssetManager()
        project = ProjectIO.load_project(project_file, manager)
        self.assertIsNotNone(project)
        layer = project.layers[0]
        self.assertEqual((layer.offset_x, layer.offset_y), (3.0, 4.0))
        self.assertEqual(layer.properties["custom-layer"], True)
        self.assertEqual(project.get_active_map().properties["author"], "map-author")

        exported = os.path.join(self.tmp.name, "offsets_out.tmx")
        self.assertTrue(ProjectIO.export_tmx(project, manager, exported))
        root = ET.parse(exported).getroot()
        exported_tileset = root.find("tileset")
        self.assertEqual(exported_tileset.find("tileoffset").get("x"), "2")
        self.assertEqual(exported_tileset.find("tileoffset").get("y"), "3")
        self.assertEqual(
            exported_tileset.find("./tile/properties/property").get("name"),
            "ground",
        )
        exported_layer = root.find("layer")
        self.assertEqual(exported_layer.get("offsetx"), "3.0")
        self.assertEqual(exported_layer.get("offsety"), "4.0")
        self.assertEqual(
            root.find("./properties/property").get("value"), "map-author"
        )
        self.assertTrue(
            root.find("./layer/properties/property[@name='custom-layer']") is not None
        )

        reloaded = ProjectIO.import_tmx(exported, AssetManager())
        self.assertIsNotNone(reloaded, ProjectIO.get_last_error())
        restored_item = reloaded.layers[0].get_tile(0, 0)
        self.assertEqual(
            restored_item.properties["tiled_tile_properties"], {"ground": "sand"}
        )
        self.assertEqual(
            (reloaded.layers[0].offset_x, reloaded.layers[0].offset_y),
            (3.0, 4.0),
        )
        self.assertEqual(
            reloaded.layers[0].properties["custom-layer"], True
        )
        self.assertEqual(reloaded.get_active_map().properties["author"], "map-author")


class TestToolsPanelNoAutoExpand(unittest.TestCase):
    """Tests for Part III (Section 12): Tools panel never auto-expands on startup or restart."""

    def test_startup_restart_and_manual_resize(self):
        from PyQt6.QtCore import QSettings
        settings = QSettings("TileSetMapMaker", "TileSetMapMaker")
        prev_state = settings.value("windowState")
        settings.remove("windowState")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg = ConfigManager(os.path.join(tmp, "cfg.json"))
                win1 = MainWindow(config_manager=cfg)
                win1.show()
                APP.processEvents()
                w1 = win1.tool_dock.width()
                self.assertLess(w1, 100, f"Tool dock auto-expanded on first startup to {w1}px!")
                self.assertEqual(win1.tool_panel.current_orientation, Qt.Orientation.Vertical)

                # Manual resize works
                win1.resizeDocks([win1.tool_dock], [110], Qt.Orientation.Horizontal)
                APP.processEvents()
                self.assertGreaterEqual(win1.tool_dock.width(), 100)
                win1.close()

                # Fresh restart restores user's custom width (110px) and does NOT auto-expand to 404px
                win2 = MainWindow(config_manager=cfg)
                win2.show()
                APP.processEvents()
                self.assertLess(win2.tool_dock.width(), 150)
                win2.close()
        finally:
            if prev_state is not None:
                settings.setValue("windowState", prev_state)
            else:
                settings.remove("windowState")


if __name__ == "__main__":
    unittest.main()
