import os
import sys
import tempfile
import unittest

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QImage, QPainter, QTransform
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

from tileset_map_maker.models.brush_preset import (
    BrushSettings,
    transform_composition_cell,
)


def _apply_composition(grid_rows, *, flip_x=False, flip_y=False, rotation=0):
    """Applies transform_composition_cell to a 2D matrix of labels and returns the transformed 2D matrix."""
    h = len(grid_rows)
    w = len(grid_rows[0])
    rot = int(round(rotation)) % 360
    out_w, out_h = (h, w) if rot in (90, 270) else (w, h)
    out = [[None for _ in range(out_w)] for _ in range(out_h)]
    for dr in range(h):
        for dc in range(w):
            ndc, ndr = transform_composition_cell(
                dc, dr, w, h, flip_x=flip_x, flip_y=flip_y, rotation=rot
            )
            out[ndr][ndc] = grid_rows[dr][dc]
    return out


class TestMirrorCompositionMath(unittest.TestCase):
    """Pure-Python deterministic tests for composition cell mapping and BrushSettings state."""

    def test_3x2_composition_horizontal_vertical_and_both(self):
        orig = [
            ["A", "B", "C"],
            ["D", "E", "F"],
        ]
        self.assertEqual(
            _apply_composition(orig, flip_x=True, flip_y=False),
            [["C", "B", "A"], ["F", "E", "D"]],
        )
        self.assertEqual(
            _apply_composition(orig, flip_x=False, flip_y=True),
            [["D", "E", "F"], ["A", "B", "C"]],
        )
        self.assertEqual(
            _apply_composition(orig, flip_x=True, flip_y=True),
            [["F", "E", "D"], ["C", "B", "A"]],
        )

    def test_2x2_and_2x3_and_4x4_compositions(self):
        g2x2 = [["TL", "TR"], ["BL", "BR"]]
        self.assertEqual(_apply_composition(g2x2, flip_x=True), [["TR", "TL"], ["BR", "BL"]])
        self.assertEqual(_apply_composition(g2x2, flip_y=True), [["BL", "BR"], ["TL", "TR"]])
        self.assertEqual(_apply_composition(g2x2, flip_x=True, flip_y=True), [["BR", "BL"], ["TR", "TL"]])

        g2x3 = [["A", "B"], ["C", "D"], ["E", "F"]]
        self.assertEqual(_apply_composition(g2x3, flip_x=True), [["B", "A"], ["D", "C"], ["F", "E"]])
        self.assertEqual(_apply_composition(g2x3, flip_y=True), [["E", "F"], ["C", "D"], ["A", "B"]])

        g4x4 = [[f"R{r}C{c}" for c in range(4)] for r in range(4)]
        flipped_h = _apply_composition(g4x4, flip_x=True)
        self.assertEqual(flipped_h, [[f"R{r}C{3 - c}" for c in range(4)] for r in range(4)])

    def test_composition_with_rotation_and_mirror(self):
        orig = [["A", "B", "C"], ["D", "E", "F"]]
        # 90 deg CW
        self.assertEqual(_apply_composition(orig, rotation=90), [["D", "A"], ["E", "B"], ["F", "C"]])
        # Flip H then 90 deg CW: C B A / F E D -> F C / E B / D A
        self.assertEqual(
            _apply_composition(orig, flip_x=True, rotation=90),
            [["F", "C"], ["E", "B"], ["D", "A"]],
        )
        # 180 deg CW == Flip H + Flip V
        self.assertEqual(
            _apply_composition(orig, rotation=180),
            _apply_composition(orig, flip_x=True, flip_y=True),
        )

    def test_brush_settings_mirror_is_100_percent_deterministic(self):
        bs = BrushSettings()
        self.assertFalse(bs.flip_horizontal)
        self.assertFalse(bs.flip_vertical)

        # Toggle horizontal on -> 100 calls identical
        bs.toggle_flip_horizontal()
        self.assertTrue(bs.flip_horizontal)
        self.assertFalse(bs.flip_vertical)
        for _ in range(100):
            rot, fx, fy, ox, oy = bs.get_brush_transform()
            self.assertEqual((rot, fx, fy, ox, oy), (0.0, True, False, 0, 0))

        # Double toggle returns to original
        bs.toggle_flip_horizontal()
        self.assertFalse(bs.flip_horizontal)
        self.assertEqual(bs.get_brush_transform(), (0.0, False, False, 0, 0))

        # Both H and V active simultaneously, even with random_variant=True
        bs.random_variant = True
        bs.set_flip_horizontal(True)
        bs.set_flip_vertical(True)
        for _ in range(100):
            _, fx, fy, _, _ = bs.get_brush_transform()
            self.assertEqual((fx, fy), (True, True))

        # Serialization round-trip
        bs.set_rotation(90)
        data = bs.to_dict()
        bs2 = BrushSettings()
        bs2.load_from_dict(data)
        self.assertEqual((bs2.flip_horizontal, bs2.flip_vertical, bs2.rotation), (True, True, 90))


@unittest.skipIf(QApplication is None, "PyQt6 is required for rendering and UI Mirror tests")
class TestMirrorEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    @staticmethod
    def _create_asymmetric_tileset(path: str, cols: int, rows: int, ts: int = 32) -> QImage:
        """Creates an RGBA tileset where every pixel has a unique asymmetric color signature."""
        img = QImage(cols * ts, rows * ts, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        for y in range(rows * ts):
            for x in range(cols * ts):
                # Asymmetric gradient + unique tile index tint + transparent corner border
                lx, ly = x % ts, y % ts
                if lx == 0 and ly == 0:
                    img.setPixelColor(x, y, QColor(0, 0, 0, 0))
                else:
                    r = (x * 3 + 17) % 256
                    g = (y * 5 + 43) % 256
                    b = ((x // ts) * 53 + (y // ts) * 97 + 29) % 256
                    img.setPixelColor(x, y, QColor(r, g, b, 255))
        img.save(path, "PNG")
        return img

    @staticmethod
    def _render_project_to_image(project, asset_manager) -> QImage:
        from tileset_map_maker.core.render_engine import RenderEngine

        engine = RenderEngine(asset_manager)
        w = project.map_width * project.tile_size
        h = project.map_height * project.tile_size
        out = QImage(w, h, QImage.Format.Format_ARGB32)
        out.fill(QColor(0, 0, 0, 0))
        p = QPainter(out)
        engine.render_layer(p, project.get_active_layer(), project, 1.0)
        p.end()
        return out

    def _assert_images_equal(self, img_a: QImage, img_b: QImage, msg: str = ""):
        self.assertEqual((img_a.width(), img_a.height()), (img_b.width(), img_b.height()), msg)
        a = img_a.convertToFormat(QImage.Format.Format_ARGB32)
        b = img_b.convertToFormat(QImage.Format.Format_ARGB32)
        self.assertEqual(
            bytes(a.constBits().asarray(a.sizeInBytes())),
            bytes(b.constBits().asarray(b.sizeInBytes())),
            msg,
        )

    def test_single_and_multi_tile_mirror_pixels_match_true_image_mirror(self):
        """Verifies 1x1, 2x2, 3x2, 2x3, and 4x4 compositions match exact whole-image mirror pixels."""
        from tileset_map_maker.core.asset_manager import AssetManager
        from tileset_map_maker.core.tools.base import ToolContext
        from tileset_map_maker.core.tools.brush import BrushTool
        from tileset_map_maker.models.asset import AssetType, SelectedSubTile, TilesetConfig
        from tileset_map_maker.models.project import Project

        ts = 32
        src_path = os.path.join(self.tmp_dir.name, "asym.png")
        src_img = self._create_asymmetric_tileset(src_path, cols=4, rows=4, ts=ts)

        mgr = AssetManager()
        asset, _, _ = mgr.import_single_file(src_path, force_asset_type=AssetType.TILESET)
        asset.tileset_config = TilesetConfig(tile_width=ts, tile_height=ts)

        for cw, ch in ((1, 1), (2, 2), (3, 2), (2, 3), (4, 4)):
            for fx, fy, rot in (
                (True, False, 0),
                (False, True, 0),
                (True, True, 0),
                (False, False, 0),
                (True, False, 90),
            ):
                with self.subTest(size=f"{cw}x{ch}", fx=fx, fy=fy, rot=rot):
                    proj = Project(name="MirrorTest", map_width=6, map_height=6, tile_size=ts)
                    bs = BrushSettings(flip_horizontal=fx, flip_vertical=fy, rotation=rot)
                    sub = SelectedSubTile(
                        asset_id=asset.id,
                        col=0,
                        row=0,
                        cols_count=cw,
                        rows_count=ch,
                        sub_x=0,
                        sub_y=0,
                        sub_w=cw * ts,
                        sub_h=ch * ts,
                        tile_width=ts,
                        tile_height=ts,
                    )
                    ctx = ToolContext(
                        project=proj,
                        asset_manager=mgr,
                        active_layer=proj.get_active_layer(),
                        selected_asset=sub,
                        brush_settings=bs,
                    )
                    brush = BrushTool()
                    # Verify cursor preview matches painted tiles 100%
                    ctx.cursor_col, ctx.cursor_row = 1, 1
                    previews = brush.get_preview_items(ctx)
                    brush.on_press(1, 1, ctx)
                    brush.on_release(1, 1, ctx)

                    layer = proj.get_active_layer()
                    self.assertEqual(len(previews), cw * ch)
                    for prev_item in previews:
                        painted = layer.get_tile(prev_item.col, prev_item.row)
                        self.assertIsNotNone(painted)
                        self.assertEqual(
                            (painted.source_x, painted.source_y, painted.flip_x, painted.flip_y, painted.rotation),
                            (prev_item.source_x, prev_item.source_y, prev_item.flip_x, prev_item.flip_y, prev_item.rotation),
                        )

                    # Render full map and compare painted region against Qt whole-image transform
                    rendered = self._render_project_to_image(proj, mgr)
                    out_w = (ch if rot in (90, 270) else cw) * ts
                    out_h = (cw if rot in (90, 270) else ch) * ts
                    actual_region = rendered.copy(ts, ts, out_w, out_h)

                    expected_region = src_img.copy(0, 0, cw * ts, ch * ts)
                    t = QTransform()
                    if rot:
                        t.rotate(rot)
                    t.scale(-1 if fx else 1, -1 if fy else 1)
                    expected_region = expected_region.transformed(t, Qt.TransformationMode.FastTransformation)
                    self._assert_images_equal(actual_region, expected_region)

    def test_100_strokes_undo_redo_save_reload_png_and_tmx_roundtrip(self):
        from tileset_map_maker.core.asset_manager import AssetManager
        from tileset_map_maker.core.history import HistoryManager
        from tileset_map_maker.core.project_io import ProjectIO
        from tileset_map_maker.core.render_engine import RenderEngine
        from tileset_map_maker.core.tools.base import ToolContext
        from tileset_map_maker.core.tools.brush import BrushTool
        from tileset_map_maker.models.asset import AssetType, SelectedSubTile, TilesetConfig
        from tileset_map_maker.models.project import Project

        ts = 32
        src_path = os.path.join(self.tmp_dir.name, "tiles.png")
        self._create_asymmetric_tileset(src_path, cols=2, rows=2, ts=ts)

        mgr = AssetManager()
        asset, _, _ = mgr.import_single_file(src_path, force_asset_type=AssetType.TILESET)
        asset.tileset_config = TilesetConfig(tile_width=ts, tile_height=ts)

        proj = Project(name="Mirror100", map_width=10, map_height=10, tile_size=ts)
        hist = HistoryManager()
        bs = BrushSettings(flip_horizontal=True, flip_vertical=False)
        sub = SelectedSubTile(
            asset_id=asset.id, col=0, row=0, cols_count=1, rows_count=1,
            sub_x=0, sub_y=0, sub_w=ts, sub_h=ts, tile_width=ts, tile_height=ts,
        )
        ctx = ToolContext(
            project=proj, asset_manager=mgr, history_manager=hist,
            active_layer=proj.get_active_layer(), selected_asset=sub, brush_settings=bs,
        )
        brush = BrushTool()

        # Paint 100 tiles with Flip H active -> ALL 100 must have identical (True, False)
        for r in range(10):
            for c in range(10):
                brush.on_press(c, r, ctx)
                brush.on_release(c, r, ctx)

        layer = proj.get_active_layer()
        for r in range(10):
            for c in range(10):
                tile = layer.get_tile(c, r)
                self.assertIsNotNone(tile)
                self.assertTrue(tile.flip_x)
                self.assertFalse(tile.flip_y)

        # Undo & Redo preserve mirrored tile
        self.assertTrue(hist.undo())
        self.assertIsNone(layer.get_tile(9, 9))
        self.assertTrue(hist.redo())
        restored = layer.get_tile(9, 9)
        self.assertTrue(restored.flip_x and not restored.flip_y)

        # Save & Reload project preserves mirror flags
        proj_path = os.path.join(self.tmp_dir.name, "mirror.tmmap")
        self.assertTrue(ProjectIO.save_project(proj, mgr, proj_path))
        loaded = ProjectIO.load_project(proj_path, AssetManager())
        self.assertIsNotNone(loaded)
        loaded_tile = loaded.get_active_layer().get_tile(0, 0)
        self.assertTrue(loaded_tile.flip_x and not loaded_tile.flip_y)

        # Export PNG succeeds
        png_path = os.path.join(self.tmp_dir.name, "mirror.png")
        self.assertTrue(ProjectIO.export_png(proj, RenderEngine(mgr), png_path))
        self.assertTrue(os.path.isfile(png_path))

        # Export & Re-import TMX preserves flip flags
        tmx_path = os.path.join(self.tmp_dir.name, "mirror.tmx")
        self.assertTrue(ProjectIO.export_tmx(proj, mgr, tmx_path))
        tmx_proj = ProjectIO.import_tmx(tmx_path, AssetManager())
        self.assertIsNotNone(tmx_proj)
        tmx_tile = tmx_proj.get_active_layer().get_tile(0, 0)
        self.assertTrue(tmx_tile.flip_x and not tmx_tile.flip_y)


if __name__ == "__main__":
    unittest.main()
