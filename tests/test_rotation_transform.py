from __future__ import annotations

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QImage, QKeyEvent, QPainter, QTransform
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

from tileset_map_maker.models.brush_preset import (
    BrushSettings,
    can_rotate_selection_90,
    transform_composition_cell,
)


def _apply_comp(grid, *, flip_x=False, flip_y=False, rotation=0):
    h, w = len(grid), len(grid[0])
    rot = int(round(rotation)) % 360
    ow, oh = (h, w) if rot in (90, 270) else (w, h)
    out = [[None for _ in range(ow)] for _ in range(oh)]
    for dr in range(h):
        for dc in range(w):
            ndc, ndr = transform_composition_cell(
                dc, dr, w, h, flip_x=flip_x, flip_y=flip_y, rotation=rot
            )
            out[ndr][ndc] = grid[dr][dc]
    return out


class TestRotationMathAndD4Algebra(unittest.TestCase):
    """Pure-Python verification of 90° CW/CCW cycles, multi-tile compositions, D4 order, and non-square guard."""

    def test_cw_and_ccw_cycles(self):
        bs = BrushSettings()
        self.assertEqual(bs.rotation, 0)
        self.assertEqual(bs.rotate_cw(), 90)
        self.assertEqual(bs.rotate_cw(), 180)
        self.assertEqual(bs.rotate_cw(), 270)
        self.assertEqual(bs.rotate_cw(), 0)

        # Shift+R counter-clockwise
        self.assertEqual(bs.rotate_ccw(), 270)
        self.assertEqual(bs.rotate_ccw(), 180)
        self.assertEqual(bs.rotate_ccw(), 90)
        self.assertEqual(bs.rotate_ccw(), 0)

    def test_3x2_composition_full_360_cycle(self):
        orig = [["A", "B", "C"], ["D", "E", "F"]]
        r90 = _apply_comp(orig, rotation=90)
        r180 = _apply_comp(orig, rotation=180)
        r270 = _apply_comp(orig, rotation=270)
        r360 = _apply_comp(orig, rotation=360)

        self.assertEqual(r90, [["D", "A"], ["E", "B"], ["F", "C"]])
        self.assertEqual(r180, [["F", "E", "D"], ["C", "B", "A"]])
        self.assertEqual(r270, [["C", "F"], ["B", "E"], ["A", "D"]])
        self.assertEqual(r360, orig)

    def test_d4_order_matters_rotate_then_flip_then_rotate(self):
        orig = [["A", "B"], ["C", "D"]]
        # Sequence: Rotate CW -> Flip H (in screen space) -> Rotate CW
        bs = BrushSettings()
        bs.rotate_cw()               # 90° CW:  C A / D B
        bs.toggle_flip_horizontal()  # Screen Flip H: A C / B D
        bs.rotate_cw()               # 90° CW:  B A / D C
        rot, fx, fy, _, _ = bs.get_brush_transform()
        result = _apply_comp(orig, flip_x=fx, flip_y=fy, rotation=rot)
        self.assertEqual(result, [["B", "A"], ["D", "C"]])

        # Verify step-by-step on actual 2D matrices matches BrushSettings D4 state
        step1 = _apply_comp(orig, rotation=90)
        step2 = _apply_comp(step1, flip_x=True)
        step3 = _apply_comp(step2, rotation=90)
        self.assertEqual(result, step3)

    def test_50_strokes_keep_identical_rotation_even_with_random_variants(self):
        bs = BrushSettings(random_variant=True)
        bs.rotate_cw()  # 90°
        for _ in range(50):
            rot, fx, fy, _, _ = bs.get_brush_transform()
            self.assertEqual((rot, fx, fy), (90.0, False, False))
        bs.rotate_cw()  # 180°
        for _ in range(50):
            rot, fx, fy, _, _ = bs.get_brush_transform()
            self.assertEqual((rot, fx, fy), (180.0, False, False))

    def test_all_8_unique_d4_orientations_and_inverses(self):
        """Verifies all 8 dihedral group D4 orientations are distinct and invertible."""
        orig = [["1", "2"], ["3", "4"]]
        seen = set()
        for rot in (0, 90, 180, 270):
            for fx in (False, True):
                mat = _apply_comp(orig, flip_x=fx, flip_y=False, rotation=rot)
                seen.add(tuple(tuple(r) for r in mat))
        self.assertEqual(len(seen), 8)

        # Double horizontal flip, double vertical flip, and 4x rotate all return identity
        bs = BrushSettings()
        bs.toggle_flip_horizontal()
        bs.toggle_flip_horizontal()
        self.assertEqual(bs.get_brush_transform()[:3], (0.0, False, False))

        bs.toggle_flip_vertical()
        bs.toggle_flip_vertical()
        self.assertEqual(bs.get_brush_transform()[:3], (0.0, False, False))

        for _ in range(4):
            bs.rotate_cw()
        self.assertEqual(bs.get_brush_transform()[:3], (0.0, False, False))

    def test_nonsquare_tile_rotation_is_blocked(self):
        ok_sq, _, _ = can_rotate_selection_90(SimpleNamespace(tile_width=32, tile_height=32))
        ok_rect, tw, th = can_rotate_selection_90(SimpleNamespace(tile_width=32, tile_height=48))
        self.assertTrue(ok_sq)
        self.assertFalse(ok_rect)
        self.assertEqual((tw, th), (32, 48))


@unittest.skipIf(QApplication is None, "PyQt6 is required for UI, key, and rendering Rotation tests")
class TestRotationEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    @staticmethod
    def _make_asym_sheet(path: str, cols: int, rows: int, tw: int = 32, th: int = 32) -> QImage:
        img = QImage(cols * tw, rows * th, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        for y in range(rows * th):
            for x in range(cols * tw):
                r = (x * 7 + 13) % 256
                g = (y * 11 + 29) % 256
                b = ((x // tw) * 61 + (y // th) * 89 + 41) % 256
                img.setPixelColor(x, y, QColor(r, g, b, 255))
        img.save(path, "PNG")
        return img

    def test_r_key_shift_r_autorepeat_and_text_input_guard(self):
        from tileset_map_maker.core.config_manager import ConfigManager
        from tileset_map_maker.ui.main_window import MainWindow

        cfg = ConfigManager(os.path.join(self.tmp_dir.name, "cfg.json"))
        win = MainWindow(config_manager=cfg)
        try:
            win.show()
            bs = win.canvas.tool_context.brush_settings
            self.assertEqual(bs.rotation, 0)

            # Single R press -> 90°
            ev_r = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.NoModifier)
            win.keyPressEvent(ev_r)
            self.assertEqual(bs.rotation, 90)
            self.assertIn("90°", win.brush_options.btn_rot.text())

            # Auto-repeat R press -> ignored (stays 90°)
            ev_rep = QKeyEvent(
                QKeyEvent.Type.KeyPress,
                Qt.Key.Key_R,
                Qt.KeyboardModifier.NoModifier,
                "",
                True,
            )
            win.keyPressEvent(ev_rep)
            self.assertEqual(bs.rotation, 90)

            # Shift+R -> back to 0°
            ev_sr = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.ShiftModifier)
            win.keyPressEvent(ev_sr)
            self.assertEqual(bs.rotation, 0)

            # Focus inside a QLineEdit -> R must type 'r' and NOT rotate brush!
            search_edit = win.tileset_palette.txt_library_search
            search_edit.setFocus()
            self.app.processEvents()
            ev_type_r = QKeyEvent(
                QKeyEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.NoModifier, "r"
            )
            QApplication.sendEvent(search_edit, ev_type_r)
            win.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.NoModifier))
            self.assertEqual(search_edit.text(), "r")
            self.assertEqual(bs.rotation, 0)
        finally:
            win.close()

    def test_rotate_50_strokes_fill_undo_redo_save_png_tmx_and_nonsquare_block(self):
        from tileset_map_maker.core.asset_manager import AssetManager
        from tileset_map_maker.core.history import HistoryManager
        from tileset_map_maker.core.project_io import ProjectIO
        from tileset_map_maker.core.render_engine import RenderEngine
        from tileset_map_maker.core.tools.base import ToolContext
        from tileset_map_maker.core.tools.brush import BrushTool
        from tileset_map_maker.core.tools.fill import FillTool
        from tileset_map_maker.models.asset import AssetType, SelectedSubTile, TilesetConfig
        from tileset_map_maker.models.project import Project
        from tileset_map_maker.ui.brush_options_bar import BrushOptionsBar

        ts = 32
        src_path = os.path.join(self.tmp_dir.name, "rot_tiles.png")
        self._make_asym_sheet(src_path, cols=3, rows=2, tw=ts, th=ts)

        mgr = AssetManager()
        asset, _, _ = mgr.import_single_file(src_path, force_asset_type=AssetType.TILESET)
        asset.tileset_config = TilesetConfig(tile_width=ts, tile_height=ts)

        proj = Project(name="Rot50", map_width=10, map_height=10, tile_size=ts)
        hist = HistoryManager()
        bs = BrushSettings()
        bs.rotate_cw()  # 90°

        sub = SelectedSubTile(
            asset_id=asset.id, col=0, row=0, cols_count=1, rows_count=1,
            sub_x=0, sub_y=0, sub_w=ts, sub_h=ts, tile_width=ts, tile_height=ts,
        )
        ctx = ToolContext(
            project=proj, asset_manager=mgr, history_manager=hist,
            active_layer=proj.get_active_layer(), selected_asset=sub, brush_settings=bs,
        )
        brush = BrushTool()

        # Paint 50 tiles at 90°
        for r in range(5):
            for c in range(10):
                brush.on_press(c, r, ctx)
                brush.on_release(c, r, ctx)

        layer = proj.get_active_layer()
        for r in range(5):
            for c in range(10):
                self.assertEqual(layer.get_tile(c, r).rotation, 90.0)

        # Rotate to 180° -> previously painted tiles stay 90°, FillTool fills empty bottom half at 180°
        bs.rotate_cw()
        fill = FillTool()
        fill.on_press(0, 5, ctx)
        self.assertEqual(layer.get_tile(0, 0).rotation, 90.0)
        self.assertEqual(layer.get_tile(0, 5).rotation, 180.0)

        # Undo/Redo
        self.assertTrue(hist.undo())
        self.assertIsNone(layer.get_tile(0, 5))
        self.assertTrue(hist.redo())
        self.assertEqual(layer.get_tile(0, 5).rotation, 180.0)

        # Save & Reload + PNG + TMX
        p_path = os.path.join(self.tmp_dir.name, "rot.tmmap")
        self.assertTrue(ProjectIO.save_project(proj, mgr, p_path))
        loaded = ProjectIO.load_project(p_path, AssetManager())
        self.assertEqual(loaded.get_active_layer().get_tile(0, 0).rotation, 90.0)
        self.assertEqual(loaded.get_active_layer().get_tile(0, 5).rotation, 180.0)

        png_path = os.path.join(self.tmp_dir.name, "rot.png")
        self.assertTrue(ProjectIO.export_png(proj, RenderEngine(mgr), png_path))
        self.assertTrue(os.path.isfile(png_path))

        tmx_path = os.path.join(self.tmp_dir.name, "rot.tmx")
        self.assertTrue(ProjectIO.export_tmx(proj, mgr, tmx_path))
        tmx_loaded = ProjectIO.import_tmx(tmx_path, AssetManager())
        self.assertEqual(tmx_loaded.get_active_layer().get_tile(0, 0).rotation, 90.0)
        self.assertEqual(tmx_loaded.get_active_layer().get_tile(0, 5).rotation, 180.0)

        # Non-square tile (32x48) blocked in BrushOptionsBar
        rect_sub = SelectedSubTile(
            asset_id=asset.id, col=0, row=0, cols_count=1, rows_count=1,
            sub_x=0, sub_y=0, sub_w=32, sub_h=48, tile_width=32, tile_height=48,
        )
        mgr.selected_item = rect_sub
        bar = BrushOptionsBar(BrushSettings(), asset_manager=mgr)
        self.assertFalse(bar.rotate_brush(clockwise=True))
        self.assertEqual(bar.settings.rotation, 0)


if __name__ == "__main__":
    unittest.main()
