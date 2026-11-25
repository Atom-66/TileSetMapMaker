import os
import sys
import tempfile
import unittest

from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

APP = QApplication.instance() or QApplication(sys.argv)

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.paths import ConnectionRuleEngine, PathSolver, TileAnalyzer
from tileset_map_maker.core.paths.models import EdgeSignature, PathVariant
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.rpg_autotile import (
    AutotileFormat,
    RPGAutotile,
    SelectedAutotile,
    create_rpg_autotile_from_tile,
    synthesize_vx_ace_from_3x3,
)
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.models.asset import AssetType, TilesetConfig
from tileset_map_maker.models.autotile import MASK_E, MASK_N, MASK_S, MASK_W
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.models.layer import ItemType, MapItem
from tileset_map_maker.models.project import Project

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TERRAIN_SUMMER_PATH = os.path.join(REPO_ROOT, "sample_assets", "terrain_summer.png")


def _is_green_surface(px: int) -> bool:
    a = (px >> 24) & 0xFF
    r = (px >> 16) & 0xFF
    g = (px >> 8) & 0xFF
    b = px & 0xFF
    return a > 200 and g > r + 15 and g > b + 15


def _is_blue_water(px: int) -> bool:
    a = (px >> 24) & 0xFF
    r = (px >> 16) & 0xFF
    b = px & 0xFF
    return a > 200 and b > r + 30 and b > 100


def _render_project(project: Project, am: AssetManager, engine: AutoTileEngine) -> QImage:
    ts = project.tile_size
    img = QImage(project.map_width * ts, project.map_height * ts, QImage.Format.Format_ARGB32)
    img.fill(QColor(20, 20, 24, 255))
    painter = QPainter(img)
    RenderEngine(am, autotile_engine=engine).render(
        painter,
        project,
        RenderOptions(
            show_grid=False,
            show_selection=False,
            transparent_bg=False,
            render_checkerboard=False,
        ),
    )
    painter.end()
    return img


def _make_edge(width_px: int, ts: int = 32, edge_type: str = "open_path") -> EdgeSignature:
    pad = max(0, (ts - width_px) // 2)
    span = (pad, pad + width_px)
    strip = tuple(
        (70, 140, 55, 255) if pad <= (i * ts) // 8 < pad + width_px else (150, 105, 65, 255)
        for i in range(8)
    )
    return EdgeSignature(
        has_surface=width_px > 0,
        surface_span=span,
        surface_width_px=width_px,
        surface_ratio=width_px / float(ts),
        edge_type=edge_type,
        mean_rgb=(70, 140, 55),
        texture_activity=0.05,
        sample_strip=strip,
    )


class TestPathsRightArmPinchRegression(unittest.TestCase):
    """
    Covers all 10 mandatory regression scenarios verifying elimination of the
    right-arm crossroad narrowing bug, real navigable surface-width validation,
    whole-intersection coherence, symmetry preservation, and editor compatibility.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.am = AssetManager()
        self.engine = AutoTileEngine(asset_manager=self.am)
        self.summer_asset, _, err = self.am.import_single_file(
            TERRAIN_SUMMER_PATH, force_asset_type=AssetType.TILESET
        )
        self.assertIsNotNone(self.summer_asset, f"Failed to load terrain_summer.png: {err}")
        self.summer_asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.summer_sheet = self.am.get_pixmap(self.summer_asset.id).toImage()

    def tearDown(self):
        self.tmp.cleanup()

    def _make_at(
        self, col: int, row: int, name: str, mode: str = "auto",
        w_tiles: int = 1, h_tiles: int = 1, rim_balance: float = 0.40,
        path_width: int = 1,
    ) -> RPGAutotile:
        at = create_rpg_autotile_from_tile(
            name=name,
            source_asset_id=self.summer_asset.id,
            sheet=self.summer_sheet,
            col=col,
            row=row,
            tile_size=32,
            mode=mode,
            w_tiles=w_tiles,
            h_tiles=h_tiles,
            rim_balance=rim_balance,
            path_width=path_width,
            terrain_type=name.lower(),
        )
        self.engine.register_rpg_autotile(at, self.am)
        return at

    # 1. Skrzyżowanie z załączonego screena (grass-on-dirt 7,1) — zero right-arm pinch!
    def test_01_screenshot_crossroad_no_right_arm_pinch_and_full_symmetry(self):
        at_comp = self._make_at(7, 1, "ScreenshotGrassDirt")
        patch = self.summer_sheet.copy(6 * 32, 0, 96, 96)
        vx_proc = synthesize_vx_ace_from_3x3(patch, 32, companion_2x2=None, rim_balance=0.40)
        at_proc = RPGAutotile(
            name="ScreenshotGrassDirtProc",
            terrain_type="proc",
            autotile_format=AutotileFormat.VX_ACE_2X3,
            tile_size=32,
        )
        at_proc.set_source_qimage(vx_proc)
        self.engine.register_rpg_autotile(at_proc, self.am)

        for label, at in (("with_companion_2x2", at_comp), ("procedural_3x3", at_proc)):
            with self.subTest(mode=label):
                proj = Project(map_width=7, map_height=7, tile_size=32)
                layer = proj.get_active_layer()
                cells = [
                    (1, 3), (2, 3), (3, 3), (4, 3), (5, 3),
                    (3, 1), (3, 2), (3, 4), (3, 5),
                ]
                self.engine.apply_rpg_autotile_stroke(layer, cells, at, proj, self.am)
                img = _render_project(proj, self.am, self.engine)

                cx, cy = 3 * 32, 3 * 32
                # Right arm entry at seam (R:0, R:1) and center right border (C:30, C:31)
                r_seam = [sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx + 32 + dx, y))) for dx in range(3)]
                c_right = [sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx + 31 - dx, y))) for dx in range(3)]
                # Left arm entry at seam (L:31, L:30) and center left border (C:0, C:1)
                l_seam = [sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx - 1 - dx, y))) for dx in range(3)]
                c_left = [sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx + dx, y))) for dx in range(3)]
                # Top & Bottom seams (make sure fixing right arm never pinches T or B!)
                t_seam = [sum(1 for x in range(cx, cx + 32) if _is_green_surface(img.pixel(x, cy - 1 - dy))) for dy in range(3)]
                c_top = [sum(1 for x in range(cx, cx + 32) if _is_green_surface(img.pixel(x, cy + dy))) for dy in range(3)]
                b_seam = [sum(1 for x in range(cx, cx + 32) if _is_green_surface(img.pixel(x, cy + 32 + dy))) for dy in range(3)]
                c_bot = [sum(1 for x in range(cx, cx + 32) if _is_green_surface(img.pixel(x, cy + 31 - dy))) for dy in range(3)]

                # Previously R:0..1 plunged to 18px, 16px! Now MUST remain >= 19px everywhere at junction!
                self.assertGreaterEqual(min(r_seam[:2]), 19, f"[{label}] Right arm pinched at seam: {r_seam}")
                self.assertGreaterEqual(min(c_right[:2]), 19, f"[{label}] Center right edge pinched: {c_right}")
                self.assertGreaterEqual(min(l_seam[:2]), 19, f"[{label}] Left arm pinched: {l_seam}")
                self.assertGreaterEqual(min(t_seam[:2]), 19, f"[{label}] Top arm pinched: {t_seam}")
                self.assertGreaterEqual(min(b_seam[:2]), 19, f"[{label}] Bottom arm pinched: {b_seam}")

                # Left vs Right symmetry at the junction
                self.assertLessEqual(
                    abs(sum(l_seam) / 3.0 - sum(r_seam) / 3.0),
                    2.5,
                    f"[{label}] L vs R arm entry asymmetry: L={l_seam} vs R={r_seam}",
                )
                self.assertLessEqual(
                    abs(c_left[0] - c_right[0]),
                    2,
                    f"[{label}] Center L vs R seam asymmetry: C_L={c_left} vs C_R={c_right}",
                )
                self.assertLessEqual(
                    abs(sum(t_seam) / 3.0 - sum(b_seam) / 3.0),
                    3.0,
                    f"[{label}] T vs B arm entry asymmetry: T={t_seam} vs B={b_seam}",
                )

    # 2. Identical L/R variants + PathSolver whole-intersection rejection of pinched right side
    def test_02_identical_lr_variants_and_solver_rejects_pinched_right_center(self):
        at = self._make_at(7, 1, "SymVariants")
        proj = Project(map_width=7, map_height=5, tile_size=32)
        layer = proj.get_active_layer()
        cells = [(1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (3, 0), (3, 1), (3, 3), (3, 4)]
        self.engine.apply_rpg_autotile_stroke(layer, cells, at, proj, self.am)

        # Left inner arm (2,2) and Right inner arm (4,2) have identical horizontal neighbors (W|E)
        item_l = layer.tiles.get((2, 2))
        item_r = layer.tiles.get((4, 2))
        self.assertIsNotNone(item_l)
        self.assertIsNotNone(item_r)
        self.assertEqual(
            (item_l.source_x, item_l.source_y, item_l.source_w, item_l.source_h),
            (item_r.source_x, item_r.source_y, item_r.source_w, item_r.source_h),
        )

        # Custom variant coherence validation: center with pinched right edge (10px vs 22px) MUST be rejected!
        arm_h = PathVariant(
            variant_id="arm_h", mask=MASK_W | MASK_E,
            source_asset_id=self.summer_asset.id, source_col=1, source_row=0, role="straight_h",
            edges={"N": _make_edge(0, edge_type="closed_outer"), "S": _make_edge(0, edge_type="closed_outer"),
                   "W": _make_edge(22), "E": _make_edge(22)},
            surface_width_px=22,
        )
        arm_v = PathVariant(
            variant_id="arm_v", mask=MASK_N | MASK_S,
            source_asset_id=self.summer_asset.id, source_col=0, source_row=1, role="straight_v",
            edges={"N": _make_edge(22), "S": _make_edge(22),
                   "W": _make_edge(0, edge_type="closed_outer"), "E": _make_edge(0, edge_type="closed_outer")},
            surface_width_px=22,
        )
        bad_center = PathVariant(
            variant_id="bad_center_right_pinch",
            mask=MASK_N | MASK_E | MASK_S | MASK_W,
            source_asset_id=self.summer_asset.id, source_col=2, source_row=2,
            role="cross",
            priority=10,
            edges={"N": _make_edge(22), "S": _make_edge(22), "W": _make_edge(22), "E": _make_edge(10)},
            surface_width_px=19,
        )
        good_center = PathVariant(
            variant_id="good_center_sym",
            mask=MASK_N | MASK_E | MASK_S | MASK_W,
            source_asset_id=self.summer_asset.id, source_col=1, source_row=1,
            role="cross",
            priority=5,
            edges={"N": _make_edge(22), "S": _make_edge(22), "W": _make_edge(22), "E": _make_edge(22)},
            surface_width_px=22,
        )

        # Whole-intersection check rejects bad_center even though 3 of 4 arms (N, S, W) are perfect!
        res_bad = ConnectionRuleEngine.validate_intersection_composition(
            bad_center, {"N": arm_v, "S": arm_v, "W": arm_h, "E": arm_h}
        )
        self.assertFalse(res_bad.compatible, "3 good arms + 1 pinched right arm must be rejected!")
        res_good = ConnectionRuleEngine.validate_intersection_composition(
            good_center, {"N": arm_v, "S": arm_v, "W": arm_h, "E": arm_h}
        )
        self.assertTrue(res_good.compatible, f"Symmetric cross must be accepted: {res_good.reasons}")

        # PathSolver must reject higher-priority bad_center (via E/S lookahead!) and choose good_center!
        at.custom_variants = [arm_h, arm_v, bad_center, good_center]
        cell_set = set(cells)
        placements = PathSolver.solve_region(
            cell_set,
            lambda c, r: (c, r) in cell_set,
            at,
            lambda aid, c, r, ts: (c * ts, r * ts, ts, ts),
            bounds=(7, 5),
        )
        center_p = next(p for p in placements if (3, 2) in p.cell_slices)
        self.assertEqual(center_p.variant_id, "good_center_sym")

    # 3. Varied graphic styles + intentionally asymmetric tileset fidelity
    def test_03_varied_graphics_and_intentional_asymmetry_preserved(self):
        # 3a. Solid grass on transparent (1,1) & Blue water with brown cliff (1,11)
        at_sg = self._make_at(1, 1, "SolidGrass")
        at_bw = self._make_at(1, 11, "BlueWater")

        for label, at, pred in (
            ("solid_grass", at_sg, _is_green_surface),
            ("blue_water", at_bw, _is_blue_water),
        ):
            with self.subTest(style=label):
                proj = Project(map_width=7, map_height=7, tile_size=32)
                layer = proj.get_active_layer()
                cells = [(1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (3, 1), (3, 2), (3, 4), (3, 5)]
                self.engine.apply_rpg_autotile_stroke(layer, cells, at, proj, self.am)
                img = _render_project(proj, self.am, self.engine)
                cx, cy = 3 * 32, 3 * 32
                l_w = sum(1 for y in range(cy, cy + 32) if pred(img.pixel(cx - 1, y)))
                cl_w = sum(1 for y in range(cy, cy + 32) if pred(img.pixel(cx, y)))
                cr_w = sum(1 for y in range(cy, cy + 32) if pred(img.pixel(cx + 31, y)))
                r_w = sum(1 for y in range(cy, cy + 32) if pred(img.pixel(cx + 32, y)))
                self.assertGreaterEqual(min(l_w, cl_w, cr_w, r_w), 18, f"[{label}] pinched: {(l_w, cl_w, cr_w, r_w)}")
                self.assertLessEqual(abs(cl_w - cr_w), 2, f"[{label}] center L/R mismatch: {cl_w} vs {cr_w}")

        # 3b. Intentionally asymmetric custom arms (W=24px wide road meeting E=12px narrow alley):
        # Validator must NOT reject a matching asymmetric center!
        wide_w = PathVariant(variant_id="w24", mask=MASK_W | MASK_E, source_asset_id="s", source_col=0, source_row=0, edges={"W": _make_edge(24), "E": _make_edge(24)})
        narrow_e = PathVariant(variant_id="e12", mask=MASK_W | MASK_E, source_asset_id="s", source_col=1, source_row=0, edges={"W": _make_edge(12), "E": _make_edge(12)})
        asym_center = PathVariant(
            variant_id="asym_c", mask=MASK_N | MASK_E | MASK_S | MASK_W,
            source_asset_id="s", source_col=2, source_row=0,
            edges={"N": _make_edge(20), "S": _make_edge(20), "W": _make_edge(24), "E": _make_edge(12)},
        )
        arm_v = PathVariant(variant_id="v20", mask=MASK_N | MASK_S, source_asset_id="s", source_col=3, source_row=0, edges={"N": _make_edge(20), "S": _make_edge(20)})
        res_asym = ConnectionRuleEngine.validate_intersection_composition(
            asym_center, {"N": arm_v, "S": arm_v, "W": wide_w, "E": narrow_e}
        )
        self.assertTrue(
            res_asym.compatible,
            f"Intentionally asymmetric matching tileset should NOT have fake symmetry forced: {res_asym.reasons}",
        )

    # 4. Larger compositions (2x2 dirt-in-grass & composition_wxh)
    def test_04_larger_compositions_crossroad(self):
        at_2x2 = self._make_at(6, 3, "Dirt2x2", mode="block_2x2", w_tiles=2, h_tiles=2)
        proj = Project(map_width=7, map_height=7, tile_size=32)
        layer = proj.get_active_layer()
        cells = [(1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (3, 1), (3, 2), (3, 4), (3, 5)]
        self.engine.apply_rpg_autotile_stroke(layer, cells, at_2x2, proj, self.am)
        img = _render_project(proj, self.am, self.engine)

        def _is_dirt(px: int) -> bool:
            r, g, b = (px >> 16) & 0xFF, (px >> 8) & 0xFF, px & 0xFF
            return r > g + 15 and g > b + 10

        cx, cy = 3 * 32, 3 * 32
        c_l = sum(1 for y in range(cy, cy + 32) if _is_dirt(img.pixel(cx, y)))
        c_r = sum(1 for y in range(cy, cy + 32) if _is_dirt(img.pixel(cx + 31, y)))
        r_0 = sum(1 for y in range(cy, cy + 32) if _is_dirt(img.pixel(cx + 32, y)))
        self.assertGreaterEqual(min(c_l, c_r, r_0), 16, f"2x2 dirt cross pinched: {(c_l, c_r, r_0)}")
        self.assertLessEqual(abs(c_l - c_r), 2, f"2x2 dirt cross L/R mismatch: {c_l} vs {c_r}")

    # 5. Varied navigable surface widths (rim_balance=0.25, 0.40, 0.55 and path_width=2)
    def test_05_varied_surface_widths_no_pinch(self):
        for bal in (0.25, 0.40, 0.55):
            with self.subTest(rim_balance=bal):
                at = self._make_at(7, 1, f"WidthBal_{bal}", rim_balance=bal)
                proj = Project(map_width=7, map_height=7, tile_size=32)
                layer = proj.get_active_layer()
                cells = [(1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (3, 1), (3, 2), (3, 4), (3, 5)]
                self.engine.apply_rpg_autotile_stroke(layer, cells, at, proj, self.am)
                img = _render_project(proj, self.am, self.engine)
                cx, cy = 3 * 32, 3 * 32
                l_w = sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx - 1, y)))
                cl_w = sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx, y)))
                cr_w = sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx + 31, y)))
                r_w = sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx + 32, y)))
                self.assertLessEqual(abs(cl_w - cr_w), 2, f"bal={bal}: C_L={cl_w} vs C_R={cr_w}")
                self.assertLessEqual(abs(l_w - r_w), 4, f"bal={bal}: L={l_w} vs R={r_w}")

    # 6. T-junctions in all 4 orientations
    def test_06_all_four_t_junctions_unpinched(self):
        at = self._make_at(7, 1, "TJunctionGrass")
        configs = {
            "T_N": [(1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (3, 1), (3, 2)],
            "T_S": [(1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (3, 4), (3, 5)],
            "T_E": [(3, 1), (3, 2), (3, 3), (3, 4), (3, 5), (4, 3), (5, 3)],
            "T_W": [(3, 1), (3, 2), (3, 3), (3, 4), (3, 5), (1, 3), (2, 3)],
        }
        for name, cells in configs.items():
            with self.subTest(junction=name):
                proj = Project(map_width=7, map_height=7, tile_size=32)
                layer = proj.get_active_layer()
                self.engine.apply_rpg_autotile_stroke(layer, cells, at, proj, self.am)
                img = _render_project(proj, self.am, self.engine)
                cx, cy = 3 * 32, 3 * 32
                if (4, 3) in cells:
                    cr_w = sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx + 31, y)))
                    r0_w = sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx + 32, y)))
                    self.assertGreaterEqual(min(cr_w, r0_w), 19, f"{name} right arm pinched: {(cr_w, r0_w)}")
                if (2, 3) in cells:
                    cl_w = sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx, y)))
                    l0_w = sum(1 for y in range(cy, cy + 32) if _is_green_surface(img.pixel(cx - 1, y)))
                    self.assertGreaterEqual(min(cl_w, l0_w), 19, f"{name} left arm pinched: {(cl_w, l0_w)}")

    # 7. Corners and straight segments
    def test_07_corners_and_straight_segments_consistent_width(self):
        at = self._make_at(7, 1, "CornersStraights")
        proj = Project(map_width=8, map_height=6, tile_size=32)
        layer = proj.get_active_layer()
        # Horizontal straight + corner down + vertical straight
        cells = [(1, 1), (2, 1), (3, 1), (4, 1), (4, 2), (4, 3), (4, 4)]
        self.engine.apply_rpg_autotile_stroke(layer, cells, at, proj, self.am)
        img = _render_project(proj, self.am, self.engine)
        # Straight horizontal seam between (2,1) and (3,1): x=95 and x=96
        w_left = sum(1 for y in range(32, 64) if _is_green_surface(img.pixel(95, y)))
        w_right = sum(1 for y in range(32, 64) if _is_green_surface(img.pixel(96, y)))
        self.assertGreaterEqual(min(w_left, w_right), 19, f"Straight seam pinched: {(w_left, w_right)}")
        self.assertLessEqual(abs(w_left - w_right), 3)

    # 8. Neighbor mutations around crossroad preserve independent tiles & layers
    def test_08_neighbor_mutation_around_crossroad(self):
        at = self._make_at(7, 1, "MutateCross")
        proj = Project(map_width=7, map_height=7, tile_size=32)
        layer = proj.get_active_layer()
        # Place an unrelated manual tile adjacent to the cross (2,2) — must never be touched!
        manual = MapItem(
            item_type=ItemType.TILE,
            asset_id=self.summer_asset.id,
            source_x=0, source_y=0, source_w=32, source_h=32,
            dest_w=32, dest_h=32,
            col=2, row=2,
            is_auto_tiled=False,
        )
        layer.set_tile(2, 2, manual)

        # Build horizontal -> cross -> remove right arm via EraserTool -> re-add right arm
        self.engine.apply_rpg_autotile_stroke(layer, [(1, 3), (2, 3), (3, 3), (4, 3), (5, 3)], at, proj, self.am)
        self.engine.apply_rpg_autotile_stroke(layer, [(3, 1), (3, 2), (3, 4), (3, 5)], at, proj, self.am)
        img_full = _render_project(proj, self.am, self.engine)
        eraser = EraserTool()
        ectx = ToolContext(
            project=proj,
            active_layer=layer,
            asset_manager=self.am,
            history_manager=HistoryManager(),
            autotile_engine=self.engine,
            brush_settings=BrushSettings(),
        )
        for c, r in ((4, 3), (5, 3)):
            eraser.on_press(c, r, ectx)
            eraser.on_release(c, r, ectx)
        self.engine.apply_rpg_autotile_stroke(layer, [(4, 3), (5, 3)], at, proj, self.am)
        img_rebuilt = _render_project(proj, self.am, self.engine)

        self.assertEqual(img_full, img_rebuilt, "Re-adding right arm must restore pixel-exact crossroad!")
        self.assertIs(layer.tiles.get((2, 2)), manual, "Independent neighbor tile was modified!")

    # 9. Undo/Redo atomicity & exact pixel restoration
    def test_09_undo_redo_crossroad_brush_stroke(self):
        at = self._make_at(7, 1, "UndoCross")
        proj = Project(map_width=7, map_height=7, tile_size=32)
        layer = proj.get_active_layer()
        history = HistoryManager()
        brush = BrushTool()
        sel = SelectedAutotile(at)
        bs = BrushSettings()
        bs.selected_autotile = sel
        ctx = ToolContext(
            project=proj,
            active_layer=layer,
            asset_manager=self.am,
            history_manager=history,
            autotile_engine=self.engine,
            selected_asset=sel,
            brush_settings=bs,
        )
        # Paint horizontal stroke, then vertical stroke (creating crossroad)
        brush.on_press(1, 3, ctx)
        for c in (2, 3, 4, 5):
            brush.on_drag(c, 3, ctx)
        brush.on_release(5, 3, ctx)
        img_horiz = _render_project(proj, self.am, self.engine)

        brush.on_press(3, 1, ctx)
        for r in (2, 3, 4, 5):
            brush.on_drag(3, r, ctx)
        brush.on_release(3, 5, ctx)
        img_cross = _render_project(proj, self.am, self.engine)

        self.assertTrue(history.undo())
        self.assertEqual(_render_project(proj, self.am, self.engine), img_horiz)
        self.assertTrue(history.redo())
        self.assertEqual(_render_project(proj, self.am, self.engine), img_cross)

    # 10. Save and reload .tmmap preserves pixel-exact crossroad and right-arm width
    def test_10_save_and_reload_preserves_crossroad_pixels(self):
        at = self._make_at(7, 1, "SaveCross")
        proj = Project(map_width=7, map_height=7, tile_size=32)
        layer = proj.get_active_layer()
        cells = [(1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (3, 1), (3, 2), (3, 4), (3, 5)]
        self.engine.apply_rpg_autotile_stroke(layer, cells, at, proj, self.am)
        img_before = _render_project(proj, self.am, self.engine)

        save_path = os.path.join(self.tmp.name, "crossroad_test.tmmap")
        self.assertTrue(ProjectIO.save_project(proj, self.am, save_path, self.engine))

        am2 = AssetManager()
        engine2 = AutoTileEngine(asset_manager=am2)
        proj2 = ProjectIO.load_project(save_path, am2, autotile_engine=engine2)
        self.assertIsNotNone(proj2, "Reloaded project is None")
        img_after = _render_project(proj2, am2, engine2)
        self.assertEqual(img_before, img_after, "Reloaded .tmmap crossroad pixels must match exactly!")


if __name__ == "__main__":
    unittest.main()
