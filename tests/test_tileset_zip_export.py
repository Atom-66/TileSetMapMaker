import hashlib
import io
import os
import sys
import tempfile
import unittest
import zipfile

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

from tileset_map_maker.models.asset import AssetType, TilesetConfig
from tileset_map_maker.core.tileset_exporter import (
    TilesetExportError,
    default_zip_filename,
    export_tileset_to_zip,
    sanitize_export_name,
)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _make_patterned_tileset(
    path: str,
    cols: int,
    rows: int,
    tile_w: int,
    tile_h: int,
    *,
    margin_x: int = 0,
    margin_y: int = 0,
    spacing_x: int = 0,
    spacing_y: int = 0,
    start_x: int = 0,
    start_y: int = 0,
    extra_right: int = 0,
    extra_bottom: int = 0,
    empty_indices=(),
    dirty_transparent_indices=(),
):
    """
    Creates an RGBA PNG tileset where every non-empty tile has a unique,
    deterministic pixel signature (including semi-transparent pixels) so
    extracted tiles can be verified pixel-for-pixel.
    """
    img_w = start_x + margin_x * 2 + cols * tile_w + max(0, cols - 1) * spacing_x + extra_right
    img_h = start_y + margin_y * 2 + rows * tile_h + max(0, rows - 1) * spacing_y + extra_bottom

    # Fill margins/spacing with a distinctive sentinel color that MUST NOT leak into tiles
    img = Image.new("RGBA", (img_w, img_h), (255, 0, 255, 255))
    cfg = TilesetConfig(
        tile_width=tile_w,
        tile_height=tile_h,
        margin_x=margin_x,
        margin_y=margin_y,
        spacing_x=spacing_x,
        spacing_y=spacing_y,
        start_x=start_x,
        start_y=start_y,
    )

    empty_set = set(empty_indices)
    dirty_empty_set = set(dirty_transparent_indices)
    expected_tiles = {}

    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c + 1
            sx, sy, tw, th = cfg.get_tile_rect(c, r)
            if idx in dirty_empty_set:
                # Completely transparent, but with non-zero RGB payload
                tile = Image.new("RGBA", (tw, th), (200, 100, 50, 0))
            elif idx in empty_set:
                tile = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
            else:
                tile = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
                px = tile.load()
                base_r = (idx * 37) % 251
                base_g = (idx * 73) % 251
                base_b = (idx * 113) % 251
                # Corner & interior pixels with both opaque and semi-transparent alpha
                px[0, 0] = (base_r, base_g, base_b, 255)
                px[tw - 1, 0] = ((base_r + 10) % 256, base_g, base_b, 180)
                px[0, th - 1] = (base_r, (base_g + 20) % 256, base_b, 90)
                px[tw - 1, th - 1] = (base_r, base_g, (base_b + 30) % 256, 255)
                px[tw // 2, th // 2] = (255 - base_r, 255 - base_g, 255 - base_b, 1)
            img.paste(tile, (sx, sy))
            expected_tiles[idx] = tile

    img.save(path, format="PNG")
    return cfg, expected_tiles


class TestTilesetExportHelpers(unittest.TestCase):
    def test_sanitize_and_default_zip_filename(self):
        self.assertEqual(default_zip_filename("Forest"), "Forest.zip")
        self.assertEqual(default_zip_filename("Forest", selected_only=True), "Forest_selected.zip")
        self.assertEqual(default_zip_filename("  Forest / Biome: 01  "), "Forest _ Biome_ 01.zip")
        self.assertEqual(
            default_zip_filename("  Forest / Biome: 01  ", selected_only=True),
            "Forest _ Biome_ 01_selected.zip",
        )
        self.assertEqual(sanitize_export_name("..."), "tileset")
        self.assertEqual(sanitize_export_name(""), "tileset")


@unittest.skipIf(Image is None, "Pillow is required for image export tests")
class TestTilesetZipExporterCore(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _assert_zip_matches(self, zip_path, prefix, expected_indices, expected_tiles, tile_w, tile_h):
        self.assertTrue(os.path.isfile(zip_path))
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            # Only PNG files, no JSON/map/project files
            self.assertTrue(all(n.endswith(".png") and "/" not in n for n in names))
            pad = max(4, len(str(max(expected_tiles.keys()))))
            expected_names = [f"{prefix}_{i:0{pad}d}.png" for i in expected_indices]
            self.assertEqual(names, expected_names)

            for idx, name in zip(expected_indices, names):
                with Image.open(io.BytesIO(zf.read(name))) as actual:
                    self.assertEqual(actual.format, "PNG")
                    self.assertEqual(actual.size, (tile_w, tile_h))
                    actual_rgba = actual.convert("RGBA")
                    self.assertEqual(
                        actual_rgba.tobytes(),
                        expected_tiles[idx].tobytes(),
                        f"Pixel mismatch at tile #{idx} ({name})",
                    )

    def test_512x832_with_32x32_produces_416_tiles(self):
        """Matches specification example: 512x832 px at 32x32 px = 16x26 = 416 tiles."""
        src = os.path.join(self.tmp_dir.name, "Forest.png")
        out = os.path.join(self.tmp_dir.name, "Forest.zip")
        cfg, expected = _make_patterned_tileset(src, cols=16, rows=26, tile_w=32, tile_h=32)
        src_hash_before = _sha256_file(src)

        res = export_tileset_to_zip(src, "Forest", cfg, out, include_empty=False)

        self.assertFalse(res.cancelled)
        self.assertEqual((res.cols, res.rows, res.total_cells), (16, 26, 416))
        self.assertEqual(res.exported_count, 416)
        self.assertEqual(res.skipped_empty_count, 0)
        self.assertEqual(_sha256_file(src), src_hash_before)
        self._assert_zip_matches(out, "Forest", list(range(1, 417)), expected, 32, 32)

    def test_tile_sizes_32x48_48x48_and_custom_dimensions(self):
        cases = [
            ("Chars32x48", 4, 3, 32, 48, 0, 0),
            ("Icons48x48", 3, 2, 48, 48, 0, 0),
            ("Large64x64", 3, 2, 64, 64, 0, 0),
            ("Custom23x37", 5, 4, 23, 37, 7, 11),  # With incomplete remainder edges
        ]
        for name, cols, rows, tw, th, rem_x, rem_y in cases:
            with self.subTest(name=name):
                src = os.path.join(self.tmp_dir.name, f"{name}.png")
                out = os.path.join(self.tmp_dir.name, f"{name}.zip")
                cfg, expected = _make_patterned_tileset(
                    src,
                    cols=cols,
                    rows=rows,
                    tile_w=tw,
                    tile_h=th,
                    extra_right=rem_x,
                    extra_bottom=rem_y,
                )
                res = export_tileset_to_zip(src, name, cfg, out)
                self.assertEqual(res.total_cells, cols * rows)
                self.assertEqual(res.exported_count, cols * rows)
                self._assert_zip_matches(
                    out, name, list(range(1, cols * rows + 1)), expected, tw, th
                )

    def test_margins_spacing_and_start_offset_exact_pixels(self):
        src = os.path.join(self.tmp_dir.name, "Spaced.png")
        out = os.path.join(self.tmp_dir.name, "Spaced.zip")
        cfg, expected = _make_patterned_tileset(
            src,
            cols=4,
            rows=3,
            tile_w=32,
            tile_h=48,
            margin_x=5,
            margin_y=7,
            spacing_x=3,
            spacing_y=4,
            start_x=6,
            start_y=9,
            extra_right=10,
            extra_bottom=12,
        )
        res = export_tileset_to_zip(src, "Spaced", cfg, out)
        self.assertEqual(res.exported_count, 12)
        self._assert_zip_matches(out, "Spaced", list(range(1, 13)), expected, 32, 48)

    def test_skip_empty_preserves_original_indices_and_include_empty_option(self):
        src = os.path.join(self.tmp_dir.name, "Forest.png")
        out_skip = os.path.join(self.tmp_dir.name, "Forest_skip.zip")
        out_all = os.path.join(self.tmp_dir.name, "Forest_all.zip")
        # Tile 2 is clean transparent; tile 5 is dirty transparent (RGB!=0, A=0)
        cfg, expected = _make_patterned_tileset(
            src,
            cols=3,
            rows=2,
            tile_w=32,
            tile_h=32,
            empty_indices=(2,),
            dirty_transparent_indices=(5,),
        )

        res_skip = export_tileset_to_zip(src, "Forest", cfg, out_skip, include_empty=False)
        self.assertEqual(res_skip.total_cells, 6)
        self.assertEqual(res_skip.exported_count, 4)
        self.assertEqual(res_skip.skipped_empty_count, 2)
        self._assert_zip_matches(out_skip, "Forest", [1, 3, 4, 6], expected, 32, 32)

        res_all = export_tileset_to_zip(src, "Forest", cfg, out_all, include_empty=True)
        self.assertEqual(res_all.total_cells, 6)
        self.assertEqual(res_all.exported_count, 6)
        self.assertEqual(res_all.skipped_empty_count, 0)
        self._assert_zip_matches(out_all, "Forest", [1, 2, 3, 4, 5, 6], expected, 32, 32)

    def test_cancellation_cleans_up_temp_file_and_does_not_write_output(self):
        src = os.path.join(self.tmp_dir.name, "Cancel.png")
        out = os.path.join(self.tmp_dir.name, "Cancel.zip")
        cfg, _ = _make_patterned_tileset(src, cols=4, rows=4, tile_w=32, tile_h=32)

        calls = {"n": 0}

        def cancel_after_three():
            calls["n"] += 1
            return calls["n"] > 3

        res = export_tileset_to_zip(src, "Cancel", cfg, out, cancel_check=cancel_after_three)
        self.assertTrue(res.cancelled)
        self.assertFalse(os.path.exists(out))
        leftovers = [f for f in os.listdir(self.tmp_dir.name) if f.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_missing_source_raises_export_error(self):
        with self.assertRaises(TilesetExportError):
            export_tileset_to_zip(
                os.path.join(self.tmp_dir.name, "does_not_exist.png"),
                "Missing",
                TilesetConfig(32, 32),
                os.path.join(self.tmp_dir.name, "out.zip"),
            )

    def test_selected_single_2x2_3x3_and_20_tiles_are_separate_pngs_with_original_indices(self):
        """
        Verifies single (1x1), 2x2 (4 PNGs), 3x3 (9 PNGs), 5x4 (20 PNGs), and
        irregular selections preserve exact 1-based sheet indices (e.g. 0012, 0013, 0028, 0029)
        and never merge selected tiles into a larger image.
        """
        src = os.path.join(self.tmp_dir.name, "Forest.png")
        cfg, expected = _make_patterned_tileset(src, cols=16, rows=5, tile_w=32, tile_h=32)

        # 1x1 single tile at (col=3, row=2) -> index = 2*16 + 3 + 1 = 36
        out_1x1 = os.path.join(self.tmp_dir.name, "Forest_1x1.zip")
        res = export_tileset_to_zip(src, "Forest", cfg, out_1x1, selected_cells=[(3, 2)])
        self.assertEqual(res.exported_count, 1)
        self._assert_zip_matches(out_1x1, "Forest", [36], expected, 32, 32)

        # 2x2 block at cols 11..12, rows 0..1 -> indices 12, 13, 28, 29
        out_2x2 = os.path.join(self.tmp_dir.name, "Forest_selected.zip")
        cells_2x2 = [(11, 0), (12, 0), (11, 1), (12, 1)]
        res = export_tileset_to_zip(src, "Forest", cfg, out_2x2, selected_cells=cells_2x2)
        self.assertEqual(res.exported_count, 4)
        self._assert_zip_matches(out_2x2, "Forest", [12, 13, 28, 29], expected, 32, 32)

        # 3x3 block at cols 1..3, rows 1..3 -> 9 separate 32x32 PNGs
        out_3x3 = os.path.join(self.tmp_dir.name, "Forest_3x3.zip")
        cells_3x3 = [(c, r) for r in range(1, 4) for c in range(1, 4)]
        expected_3x3 = [r * 16 + c + 1 for c, r in cells_3x3]
        res = export_tileset_to_zip(src, "Forest", cfg, out_3x3, selected_cells=cells_3x3)
        self.assertEqual(res.exported_count, 9)
        self._assert_zip_matches(out_3x3, "Forest", expected_3x3, expected, 32, 32)

        # 20 tiles (5x4) -> 20 separate 32x32 PNGs
        out_20 = os.path.join(self.tmp_dir.name, "Forest_20.zip")
        cells_20 = [(c, r) for r in range(0, 4) for c in range(2, 7)]
        expected_20 = [r * 16 + c + 1 for c, r in cells_20]
        res = export_tileset_to_zip(src, "Forest", cfg, out_20, selected_cells=cells_20)
        self.assertEqual(res.exported_count, 20)
        self._assert_zip_matches(out_20, "Forest", expected_20, expected, 32, 32)

        # Irregular non-rectangular selection (unsorted & with duplicate) -> sorted by (row, col)
        out_irr = os.path.join(self.tmp_dir.name, "Forest_irr.zip")
        res = export_tileset_to_zip(
            src,
            "Forest",
            cfg,
            out_irr,
            selected_cells=[(15, 4), (0, 0), (5, 2), (0, 0)],
        )
        self.assertEqual(res.exported_count, 3)
        self._assert_zip_matches(out_irr, "Forest", [1, 38, 80], expected, 32, 32)

    def test_selected_empty_list_raises_error(self):
        src = os.path.join(self.tmp_dir.name, "Forest.png")
        out = os.path.join(self.tmp_dir.name, "Forest_selected.zip")
        cfg, _ = _make_patterned_tileset(src, cols=3, rows=3, tile_w=32, tile_h=32)
        with self.assertRaises(TilesetExportError):
            export_tileset_to_zip(src, "Forest", cfg, out, selected_cells=[])
        self.assertFalse(os.path.exists(out))


@unittest.skipIf(QApplication is None or Image is None, "PyQt6 and Pillow are required for UI tests")
class TestTilesetPreviewExportButtonUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_button_state_localization_and_canvas_stability(self):
        from tileset_map_maker.core.asset_manager import AssetManager
        from tileset_map_maker.core.localization import get_localization
        from tileset_map_maker.ui.tileset_palette_widget import TilesetPaletteWidget

        loc = get_localization()
        prev_lang = loc.get_language()
        try:
            asset_mgr = AssetManager()
            palette = TilesetPaletteWidget(asset_mgr)

            # Disabled when no tileset is selected
            self.assertFalse(palette.btn_export_zip.isEnabled())
            self.assertFalse(palette.act_export_all_tiles.isEnabled())
            self.assertFalse(palette.act_export_selected_tiles.isEnabled())
            self.assertFalse(palette.btn_export_zip.icon().isNull())
            self.assertFalse(palette.act_export_include_empty.isChecked())

            # Localization EN / PL
            loc.set_language("en", persist=False)
            self.assertEqual(palette.btn_export_zip.toolTip(), "Export tiles as ZIP")
            self.assertEqual(palette.act_export_all_tiles.text(), "Export All Tiles")
            self.assertEqual(palette.act_export_selected_tiles.text(), "Export Selected Tiles")
            loc.set_language("pl", persist=False)
            self.assertEqual(palette.btn_export_zip.toolTip(), "Eksportuj kafelki do ZIP")
            self.assertEqual(palette.act_export_all_tiles.text(), "Eksportuj wszystkie kafelki")
            self.assertEqual(palette.act_export_selected_tiles.text(), "Eksportuj zaznaczone kafelki")

            # Load two tilesets -> enabled, switching active tileset works cleanly
            src = os.path.join(self.tmp_dir.name, "Forest.png")
            cfg, _ = _make_patterned_tileset(src, cols=4, rows=3, tile_w=32, tile_h=32)
            asset, _, _ = asset_mgr.import_single_file(src, force_asset_type=AssetType.TILESET)
            asset.tileset_config = cfg

            src2 = os.path.join(self.tmp_dir.name, "Dungeon.png")
            cfg2, _ = _make_patterned_tileset(src2, cols=3, rows=2, tile_w=48, tile_h=48)
            asset2, _, _ = asset_mgr.import_single_file(src2, force_asset_type=AssetType.TILESET)
            asset2.tileset_config = cfg2

            palette.refresh_tilesets()
            palette.set_active_asset(asset)

            self.assertTrue(palette.btn_export_zip.isEnabled())
            self.assertTrue(palette.act_export_all_tiles.isEnabled())
            self.assertTrue(palette.act_export_selected_tiles.isEnabled())

            # Select 2x2 block (4 tiles) -> menu reflects count
            palette.canvas.sel_start_col = 1
            palette.canvas.sel_start_row = 0
            palette.canvas.sel_end_col = 2
            palette.canvas.sel_end_row = 1
            palette.canvas._emit_selection()

            loc.set_language("en", persist=False)
            self.assertEqual(palette.act_export_selected_tiles.text(), "Export Selected Tiles (4)")
            loc.set_language("pl", persist=False)
            self.assertEqual(
                palette.act_export_selected_tiles.text(),
                "Eksportuj zaznaczone kafelki (4)",
            )

            # Deselect -> Export Selected Tiles becomes disabled while Export All stays enabled
            palette.canvas.deselect()
            palette._update_export_zip_menu_state()
            self.assertTrue(palette.act_export_all_tiles.isEnabled())
            self.assertFalse(palette.act_export_selected_tiles.isEnabled())

            # Re-select 2x2 and test export across multiple zoom levels without mutating view state
            palette.canvas.has_selection = True
            palette.canvas.sel_start_col = 1
            palette.canvas.sel_start_row = 0
            palette.canvas.sel_end_col = 2
            palette.canvas.sel_end_row = 1
            palette.canvas._emit_selection()

            for zoom_val in (0.5, 1.0, 4.0):
                palette.canvas.set_zoom(zoom_val)
                palette.canvas.pan_offset.setX(42.5)
                palette.canvas.pan_offset.setY(-17.0)
                out_sel = os.path.join(self.tmp_dir.name, f"Forest_sel_{zoom_val}.zip")
                res = export_tileset_to_zip(
                    asset.file_path,
                    asset.name,
                    asset.tileset_config,
                    out_sel,
                    selected_cells=palette.canvas.get_selected_cells(),
                )
                self.assertEqual(res.exported_count, 4)
                self.assertAlmostEqual(palette.canvas.zoom, zoom_val)
                self.assertAlmostEqual(palette.canvas.pan_offset.x(), 42.5)
                self.assertAlmostEqual(palette.canvas.pan_offset.y(), -17.0)
                self.assertEqual(
                    (
                        palette.canvas.sel_start_col,
                        palette.canvas.sel_start_row,
                        palette.canvas.sel_end_col,
                        palette.canvas.sel_end_row,
                    ),
                    (1, 0, 2, 1),
                )

            # Switch active tileset -> exports the new active tileset
            palette.set_active_asset(asset2)
            self.assertEqual(palette.active_asset_id, asset2.id)
            out_dungeon = os.path.join(self.tmp_dir.name, "Dungeon.zip")
            res2 = export_tileset_to_zip(asset2.file_path, asset2.name, asset2.tileset_config, out_dungeon)
            self.assertEqual((res2.exported_count, res2.tile_width, res2.tile_height), (6, 48, 48))

            # Clearing active asset disables button and actions again
            palette.set_active_asset(None)
            self.assertFalse(palette.btn_export_zip.isEnabled())
            self.assertFalse(palette.act_export_all_tiles.isEnabled())
            self.assertFalse(palette.act_export_selected_tiles.isEnabled())
        finally:
            loc.set_language(prev_lang, persist=False)


if __name__ == "__main__":
    unittest.main()
