import os
import sys
import tempfile
import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

APP = QApplication.instance() or QApplication(sys.argv)

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.rpg_autotile import (
    AutotileFormat,
    CustomPathVariant,
    QUAD_CENTER,
    QUAD_EDGE_H,
    QUAD_EDGE_V,
    QUAD_INNER_CORNER,
    RPGAutotile,
    SelectedAutotile,
    create_rpg_autotile_from_tile,
    extract_packed_tileset_image,
    mask_to_quadrant_states,
    synthesize_from_single_tile,
    synthesize_from_tileset_context,
    synthesize_vx_ace_from_3x3,
)
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.models.asset import AssetType, TilesetConfig
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.models.layer import ItemType, MapItem
from tileset_map_maker.models.project import Project
from tileset_map_maker.ui.dialogs.autotile_sandbox_widget import AutoTileSandboxWidget
from tileset_map_maker.ui.dialogs.path_generator_dialog import PathGeneratorDialog


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TERRAIN_SUMMER_PATH = os.path.join(REPO_ROOT, "sample_assets", "terrain_summer.png")
TERRAIN_TILESET_PATH = os.path.join(REPO_ROOT, "sample_assets", "Terrain", "terrain_tileset.png")
GRASS_SINGLE_PATH = os.path.join(REPO_ROOT, "sample_assets", "Terrain", "Grass", "grass_01.png")


def _is_green_interior(color: QColor) -> bool:
    return color.alpha() > 200 and color.green() > color.red() + 10


def _is_brown_outer(color: QColor) -> bool:
    return color.alpha() > 200 and color.red() > color.green() + 15


def _render_project_image(project: Project, asset_manager: AssetManager, engine: AutoTileEngine) -> QImage:
    ts = project.tile_size
    img = QImage(project.map_width * ts, project.map_height * ts, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    painter = QPainter(img)
    RenderEngine(asset_manager, autotile_engine=engine).render(
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
    return img


class TestPathsIntersectionsComprehensive(unittest.TestCase):
    """
    Covers all 10 mandatory intersection verification scenarios across real project
    tilesets (terrain_summer.png, terrain_tileset.png, grass_01.png) and custom
    irregular/margin-spaced tilesets.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.am = AssetManager()
        self.engine = AutoTileEngine(asset_manager=self.am)
        self.history = HistoryManager()
        self.project = Project(name="Intersection Tests", map_width=14, map_height=12, tile_size=32)
        self.layer = self.project.get_active_layer()

        self.summer_asset, _, err = self.am.import_single_file(
            TERRAIN_SUMMER_PATH, force_asset_type=AssetType.TILESET
        )
        self.assertIsNotNone(self.summer_asset, f"Failed to load terrain_summer.png: {err}")
        self.summer_asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.summer_sheet = self.am.get_pixmap(self.summer_asset.id).toImage()

    def tearDown(self):
        self.tmp.cleanup()

    def _make_summer_autotile(self, col: int = 7, row: int = 1, name: str = "GrassDirt") -> RPGAutotile:
        at = create_rpg_autotile_from_tile(
            name=name,
            source_asset_id=self.summer_asset.id,
            sheet=self.summer_sheet,
            col=col,
            row=row,
            tile_size=32,
            mode="auto",
            terrain_type=name.lower(),
        )
        self.engine.register_rpg_autotile(at, self.am)
        return at

    # ------------------------------------------------------------------
    # 1. Skrzyżowanie czterokierunkowe (width parity + center texture continuity)
    # ------------------------------------------------------------------
    def test_01_four_way_cross_no_narrowing_and_textured_center_both_modes(self):
        # Test BOTH: (A) full sheet with companion 2x2 detection, and (B) isolated pure 3x3 without companion 2x2
        at_sheet = self._make_summer_autotile(7, 1, "GrassDirtSheet")

        isolated_patch = self.summer_sheet.copy(6 * 32, 0, 96, 96)
        vx_pure = synthesize_vx_ace_from_3x3(isolated_patch, 32, companion_2x2=None)
        at_pure = RPGAutotile(
            name="GrassDirtPure3x3",
            terrain_type="pure3x3",
            autotile_format=AutotileFormat.VX_ACE_2X3,
            tile_size=32,
        )
        at_pure.set_source_qimage(vx_pure)
        self.engine.register_rpg_autotile(at_pure, self.am)

        for label, at in (("with_companion_2x2", at_sheet), ("pure_procedural_3x3", at_pure)):
            with self.subTest(mode=label):
                proj = Project(map_width=7, map_height=5, tile_size=32)
                layer = proj.get_active_layer()
                cross_coords = [
                    (1, 2), (2, 2), (3, 2), (4, 2), (5, 2),
                    (3, 0), (3, 1), (3, 3), (3, 4),
                ]
                self.engine.apply_rpg_autotile_stroke(layer, cross_coords, at, proj, self.am)
                img = _render_project_image(proj, self.am, self.engine)

                # Measure horizontal arm green height across full 32px tile (col=2)
                h_col_widths = [
                    sum(1 for y in range(2 * 32, 3 * 32) if _is_green_interior(img.pixelColor(x, y)))
                    for x in range(2 * 32, 3 * 32)
                ]
                h_arm_green = sum(h_col_widths) / 32.0
                # Measure vertical arm green width across full 32px tile (row=1)
                v_row_widths = [
                    sum(1 for x in range(3 * 32, 4 * 32) if _is_green_interior(img.pixelColor(x, y)))
                    for y in range(1 * 32, 2 * 32)
                ]
                v_arm_green = sum(v_row_widths) / 32.0

                # Measure intersection entry bands (4px deep on each side of center cell (3, 2))
                cx0, cy0 = 3 * 32, 2 * 32
                neck_left_band = [
                    sum(1 for y in range(cy0, cy0 + 32) if _is_green_interior(img.pixelColor(cx0 + dx, y)))
                    for dx in range(4)
                ]
                neck_right_band = [
                    sum(1 for y in range(cy0, cy0 + 32) if _is_green_interior(img.pixelColor(cx0 + 31 - dx, y)))
                    for dx in range(4)
                ]
                neck_top_band = [
                    sum(1 for x in range(cx0, cx0 + 32) if _is_green_interior(img.pixelColor(x, cy0 + dy)))
                    for dy in range(4)
                ]
                neck_bot_band = [
                    sum(1 for x in range(cx0, cx0 + 32) if _is_green_interior(img.pixelColor(x, cy0 + 31 - dy)))
                    for dy in range(4)
                ]

                # Horizontal and vertical arms must both be wide (>= 18px) and balanced
                self.assertGreaterEqual(h_arm_green, 18.0)
                self.assertGreaterEqual(v_arm_green, 18.0)
                self.assertLessEqual(abs(h_arm_green - v_arm_green), 3.0)

                # Intersection entry bands MUST NOT pinch below incoming arm width
                self.assertGreaterEqual(sum(neck_left_band) / 4.0, h_arm_green - 3.0)
                self.assertGreaterEqual(sum(neck_right_band) / 4.0, h_arm_green - 3.0)
                self.assertGreaterEqual(sum(neck_top_band) / 4.0, v_arm_green - 3.0)
                self.assertGreaterEqual(sum(neck_bot_band) / 4.0, v_arm_green - 3.0)
                # Even the exact 1px tile seam must never dip below the arm's own minimum tuft width
                self.assertGreaterEqual(neck_left_band[0], min(h_col_widths))
                self.assertGreaterEqual(neck_right_band[0], min(h_col_widths))
                self.assertGreaterEqual(neck_top_band[0], min(v_row_widths))
                self.assertGreaterEqual(neck_bot_band[0], min(v_row_widths))

                # Center 16x16 interior of the cross must be 100% opaque green AND textured (not a flat solid void!)
                center_rgbs = set()
                for y in range(cy0 + 8, cy0 + 24):
                    for x in range(cx0 + 8, cx0 + 24):
                        c = img.pixelColor(x, y)
                        self.assertTrue(_is_green_interior(c), f"Non-green pixel at cross center ({x},{y}): {c.getRgb()}")
                        center_rgbs.add((c.red(), c.green(), c.blue()))
                self.assertGreaterEqual(len(center_rgbs), 2, "Cross center must preserve textured grass detail, not a flat single-color void")

    # ------------------------------------------------------------------
    # 2. Skrzyżowanie z różnymi szerokościami ramion (2x1, 1x2, 2x2)
    # ------------------------------------------------------------------
    def test_02_mixed_width_intersections_2x1_and_2x2(self):
        at = self._make_summer_autotile(7, 1, "MixedWidthGrass")

        # 2-wide horizontal (rows 3..4, cols 1..7) intersecting 1-wide vertical (col 4, rows 1..6)
        coords = []
        for c in range(1, 8):
            coords.extend([(c, 3), (c, 4)])
        for r in range(1, 7):
            coords.append((4, r))
        self.engine.apply_rpg_autotile_stroke(self.layer, coords, at, self.project, self.am)

        # (4, 3): top-half of 2-wide road with N arm -> TL/TR inner corners, BL/BR center
        m_top = self.engine.compute_rpg_mask(self.layer, 4, 3, at, self.project)
        self.assertEqual(
            mask_to_quadrant_states(m_top),
            (QUAD_INNER_CORNER, QUAD_INNER_CORNER, QUAD_CENTER, QUAD_CENTER),
        )
        # (4, 4): bottom-half of 2-wide road with S arm -> TL/TR center, BL/BR inner corners
        m_bot = self.engine.compute_rpg_mask(self.layer, 4, 4, at, self.project)
        self.assertEqual(
            mask_to_quadrant_states(m_bot),
            (QUAD_CENTER, QUAD_CENTER, QUAD_INNER_CORNER, QUAD_INNER_CORNER),
        )

        img = _render_project_image(self.project, self.am, self.engine)
        # Verify continuous green across the entire 2-tile vertical height at the confluence (x = 4*32 + 16)
        for y in range(3 * 32, 5 * 32):
            self.assertTrue(_is_green_interior(img.pixelColor(4 * 32 + 16, y)))

        # Now widen vertical arm to 2 tiles (add col 5, rows 1..6) -> 2x2 intersection!
        self.engine.apply_rpg_autotile_stroke(
            self.layer, [(5, r) for r in range(1, 7)], at, self.project, self.am
        )
        # 4 center tiles (4,3), (5,3), (4,4), (5,4) each have 1 outer-facing inner corner and 3 center quadrants
        self.assertEqual(
            mask_to_quadrant_states(self.engine.compute_rpg_mask(self.layer, 4, 3, at, self.project)),
            (QUAD_INNER_CORNER, QUAD_CENTER, QUAD_CENTER, QUAD_CENTER),
        )
        self.assertEqual(
            mask_to_quadrant_states(self.engine.compute_rpg_mask(self.layer, 5, 4, at, self.project)),
            (QUAD_CENTER, QUAD_CENTER, QUAD_CENTER, QUAD_INNER_CORNER),
        )

    # ------------------------------------------------------------------
    # 3. Skrzyżowania z większymi wariantami 2x2 i 3x3 (+ Sandbox live preview + clean erase)
    # ------------------------------------------------------------------
    def test_03_custom_2x2_and_3x3_variants_map_sandbox_and_clean_erase(self):
        # Create custom sheet with distinct 2x2 and 3x3 intersection graphics
        sheet_path = os.path.join(self.tmp.name, "variants_sheet.png")
        img = QImage(256, 256, QImage.Format.Format_ARGB32)
        img.fill(QColor(80, 150, 70, 255))
        p = QPainter(img)
        p.fillRect(0, 128, 64, 64, QColor(200, 90, 220, 255))    # 2x2 custom variant at (0..1, 4..5)
        p.fillRect(96, 128, 96, 96, QColor(240, 170, 40, 255))   # 3x3 custom variant at (3..5, 4..6)
        p.end()
        img.save(sheet_path)

        asset, _, _ = self.am.import_single_file(sheet_path, force_asset_type=AssetType.TILESET)
        asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

        at = create_rpg_autotile_from_tile(
            "CustomCross", asset.id, img, 0, 0, tile_size=32, mode="single_tile", terrain_type="custom_cross"
        )
        v_3x3 = CustomPathVariant(
            mask=255,
            source_asset_id=asset.id,
            source_col=3,
            source_row=4,
            width_tiles=3,
            height_tiles=3,
            priority=50,
            name="3x3 Plaza Intersection",
        )
        at.add_custom_variant(v_3x3)
        self.engine.register_rpg_autotile(at, self.am)

        # Paint a 3x3 filled intersection center (cols 3..5, rows 3..5) plus 4 arms
        coords = [(c, r) for r in range(3, 6) for c in range(3, 6)]
        coords += [(4, 2), (4, 6), (2, 4), (6, 4)]
        self.engine.apply_rpg_autotile_stroke(self.layer, coords, at, self.project, self.am)

        # Center (4,4) has mask 255 -> 3x3 centered placement stamps (3..5, 3..5)!
        for dr in range(3):
            for dc in range(3):
                tile = self.layer.get_tile(3 + dc, 3 + dr)
                self.assertEqual(tile.asset_id, asset.id)
                self.assertEqual((tile.source_x, tile.source_y), ((3 + dc) * 32, (4 + dr) * 32))
                self.assertEqual(tile.properties.get("variant_origin"), [3, 3])
                self.assertEqual(tile.properties.get("variant_size"), [3, 3])

        # Verify Sandbox ALSO evaluates the 3x3 custom variant live!
        sb = AutoTileSandboxWidget(asset_manager=self.am, cols=10, rows=8, tile_size=32)
        sb.set_active_rpg_autotile(at)
        sb.active_cells = set(coords)
        evaluated = sb.engine.evaluate_rpg_sandbox_grid(sb.active_cells, at, 10, 8, asset_manager=self.am)
        self.assertEqual(evaluated[(4, 4)][0], asset.id)
        self.assertEqual((evaluated[(4, 4)][1], evaluated[(4, 4)][2]), (4 * 32, 5 * 32))
        sb.close()

        # Erase 1 corner cell (3, 3) of the 3x3 variant -> ALL remaining 8 cells MUST cleanly revert to Wang-47 (no orphaned 3x3 pieces!)
        self.layer.remove_tile(3, 3)
        self.engine.update_rpg_neighbors_after_erase(self.layer, {(3, 3)}, self.project)
        for r in range(3, 6):
            for c in range(3, 6):
                if (c, r) == (3, 3):
                    continue
                tile = self.layer.get_tile(c, r)
                self.assertEqual(tile.asset_id, at.id, f"Orphaned 3x3 variant fragment left at ({c},{r})!")
                self.assertNotIn("variant_origin", tile.properties)

    # ------------------------------------------------------------------
    # 4. Skrzyżowania z nieregularnych tilesetów (asymmetric rim, margin/spacing, multiple real assets)
    # ------------------------------------------------------------------
    def test_04_irregular_asymmetric_margin_spacing_and_other_project_tilesets(self):
        # A) Synthetic irregular 3x3 with ASYMMETRIC rims (4px top/bottom, 10px left/right) + margin=4, spacing=2
        tw, margin, spacing = 32, 4, 2
        sheet_w = margin * 2 + 3 * tw + 2 * spacing
        sheet_h = margin * 2 + 3 * tw + 2 * spacing
        raw = QImage(sheet_w, sheet_h, QImage.Format.Format_ARGB32)
        raw.fill(QColor(255, 0, 255, 255))  # Magenta gutter to catch any margin/spacing mis-slice!
        p = QPainter(raw)
        cfg = TilesetConfig(tile_width=tw, tile_height=tw, margin=margin, spacing=spacing)
        # Draw 3x3 stone-on-sand block with asymmetric rim (4px top/bottom, 10px left/right) into spaced cells
        sand = QColor(225, 195, 130, 255)
        stone = QColor(115, 120, 132, 255)
        stone_hi = QColor(150, 155, 165, 255)
        # Build clean 96x96 artwork first then blit per-cell into spaced sheet
        art = QImage(96, 96, QImage.Format.Format_ARGB32)
        art.fill(sand)
        pa = QPainter(art)
        pa.fillRect(10, 4, 96 - 20, 96 - 8, stone)
        # Add pixel-art stone cobble highlights inside
        for yy in range(6, 90, 4):
            for xx in range(12, 84, 5):
                art.setPixelColor(xx, yy, stone_hi)
        pa.end()
        for r in range(3):
            for c in range(3):
                rx, ry, rw, rh = cfg.get_tile_rect(c, r)
                p.drawImage(rx, ry, art, c * tw, r * tw, tw, tw)
        p.end()

        spaced_path = os.path.join(self.tmp.name, "spaced_irregular.png")
        raw.save(spaced_path)
        sp_asset, _, _ = self.am.import_single_file(spaced_path, force_asset_type=AssetType.TILESET)
        sp_asset.tileset_config = cfg

        packed, ptw, pth = extract_packed_tileset_image(raw, cfg)
        self.assertEqual((ptw, pth), (32, 32))
        self.assertEqual((packed.width(), packed.height()), (96, 96))

        at_irreg = create_rpg_autotile_from_tile(
            "AsymStone", sp_asset.id, packed, 1, 1, tile_size=32, mode="block_3x3_center", terrain_type="asym_stone"
        )
        self.engine.register_rpg_autotile(at_irreg, self.am)

        # Verify ZERO magenta gutter pixels leaked into the synthesized atlas!
        atlas = at_irreg.get_atlas_pixmap(self.am).toImage()
        for y in range(atlas.height()):
            for x in range(atlas.width()):
                c = atlas.pixelColor(x, y)
                if c.alpha() > 0:
                    self.assertFalse(c.red() > 240 and c.green() < 20 and c.blue() > 240, "Magenta margin/spacing pixel leaked!")

        # Verify cross preserves BOTH the wider horizontal passage AND vertical passage
        proj = Project(map_width=5, map_height=5, tile_size=32)
        layer = proj.get_active_layer()
        self.engine.apply_rpg_autotile_stroke(
            layer, [(0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (2, 0), (2, 1), (2, 3), (2, 4)], at_irreg, proj, self.am
        )
        out = _render_project_image(proj, self.am, self.engine)
        is_stone = lambda col: col.alpha() > 200 and abs(col.red() - col.blue()) < 30
        h_w = sum(1 for y in range(64, 96) if is_stone(out.pixelColor(32 + 16, y)))
        v_w = sum(1 for x in range(64, 96) if is_stone(out.pixelColor(x, 32 + 16)))
        cross_l = sum(1 for y in range(64, 96) if is_stone(out.pixelColor(64, y)))
        cross_t = sum(1 for x in range(64, 96) if is_stone(out.pixelColor(x, 64)))
        self.assertGreaterEqual(cross_l, h_w - 1)
        self.assertGreaterEqual(cross_t, v_w - 1)

        # B) Other real project assets: water_grass & grass_sand in terrain_summer + 2x2 terrain_tileset + 1x1 grass_01
        for label, col, row in (("grass_sand", 7, 6), ("water_grass", 4, 11), ("water_dirt", 7, 11)):
            at_s = self._make_summer_autotile(col, row, label)
            self.assertTrue(at_s.has_valid_atlas(self.am))

        ts2_asset, _, _ = self.am.import_single_file(TERRAIN_TILESET_PATH, force_asset_type=AssetType.TILESET)
        ts2_asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        ts2_img = self.am.get_pixmap(ts2_asset.id).toImage()
        at_2x2 = create_rpg_autotile_from_tile("Sample2x2", ts2_asset.id, ts2_img, 0, 0, 32, mode="block_2x2", w_tiles=2, h_tiles=2)
        self.assertTrue(at_2x2.has_valid_atlas(self.am))

        g1_img = QImage(GRASS_SINGLE_PATH)
        for style in ("organic", "alpha_fade", "dark_outline"):
            vx_1 = synthesize_from_single_tile(g1_img, 32, edge_style=style)
            at_1 = RPGAutotile(tile_size=32)
            at_1.set_source_qimage(vx_1)
            # Single-tile cross inner corners must align with straight edge width (no extra pinch!)
            atlas_1 = at_1.get_atlas_pixmap().toImage()
            sx_h, sy_h, _, _ = at_1.get_tile_slice_for_mask(68)   # W+E
            sx_c, sy_c, _, _ = at_1.get_tile_slice_for_mask(85)   # N+E+S+W cross
            h_opaque = sum(1 for y in range(32) if atlas_1.pixelColor(sx_h + 16, sy_h + y).alpha() > 0)
            c_opaque = sum(1 for y in range(32) if atlas_1.pixelColor(sx_c, sy_c + y).alpha() > 0)
            self.assertGreaterEqual(c_opaque, h_opaque, f"Single-tile style '{style}' pinched at intersection!")

    # ------------------------------------------------------------------
    # 5. Kilka skrzyżowań połączonych ze sobą
    # ------------------------------------------------------------------
    def test_05_multiple_connected_intersections(self):
        at = self._make_summer_autotile(7, 1, "ConnectedCrosses")
        # Two horizontal roads (rows 3 and 7) crossing two vertical roads (cols 3 and 7) -> 4 connected crosses!
        coords = []
        for c in range(1, 10):
            coords.extend([(c, 3), (c, 7)])
        for r in range(1, 10):
            coords.extend([(3, r), (7, r)])
        self.engine.apply_rpg_autotile_stroke(self.layer, coords, at, self.project, self.am)

        for cx, cy in ((3, 3), (7, 3), (3, 7), (7, 7)):
            m = self.engine.compute_rpg_mask(self.layer, cx, cy, at, self.project)
            self.assertEqual(m, 85, f"Expected 4-way cross mask 85 at ({cx},{cy}), got {m}")

        img = _render_project_image(self.project, self.am, self.engine)
        for cx, cy in ((3, 3), (7, 3), (3, 7), (7, 7)):
            self.assertTrue(_is_green_interior(img.pixelColor(cx * 32 + 16, cy * 32 + 16)))

    # ------------------------------------------------------------------
    # 6 & 7. Usunięcie jednego ramienia (Cross -> T) i zmiana kierunku ścieżki (Cross -> Turn)
    # ------------------------------------------------------------------
    def test_06_07_erase_arm_and_change_direction_updates_intersection_cleanly(self):
        at = self._make_summer_autotile(7, 1, "DynamicCross")
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.am,
            history_manager=self.history,
            brush_settings=BrushSettings(),
            autotile_engine=self.engine,
            selected_asset=SelectedAutotile(at),
        )
        ctx.brush_settings.selected_autotile = ctx.selected_asset

        brush = BrushTool()
        eraser = EraserTool()

        # Draw 4-way cross centered at (5, 5)
        for c, r in [(3, 5), (4, 5), (5, 5), (6, 5), (7, 5), (5, 3), (5, 4), (5, 6), (5, 7)]:
            brush.on_press(c, r, ctx)
            brush.on_release(c, r, ctx)
        self.assertEqual(self.engine.compute_rpg_mask(self.layer, 5, 5, at, self.project), 85)

        # 6. Erase North arm (5, 4) -> center (5, 5) becomes T-junction (W+E+S = 84)
        eraser.on_press(5, 4, ctx)
        eraser.on_release(5, 4, ctx)
        m_t = self.engine.compute_rpg_mask(self.layer, 5, 5, at, self.project)
        self.assertEqual(m_t, 84)
        self.assertEqual(
            mask_to_quadrant_states(m_t),
            (QUAD_EDGE_H, QUAD_EDGE_H, QUAD_INNER_CORNER, QUAD_INNER_CORNER),
        )

        # 7. Erase West arm (4, 5) -> center (5, 5) becomes SE corner turn (E+S = 20)
        eraser.on_press(4, 5, ctx)
        eraser.on_release(4, 5, ctx)
        m_turn = self.engine.compute_rpg_mask(self.layer, 5, 5, at, self.project)
        self.assertEqual(m_turn, 20)

        # Verify visual top edge of (5,5) is now brown outer dirt (closed off where N arm was removed!)
        img = _render_project_image(self.project, self.am, self.engine)
        self.assertTrue(_is_brown_outer(img.pixelColor(5 * 32 + 16, 5 * 32 + 1)))

    # ------------------------------------------------------------------
    # 8. Zapis i ponowne otwarcie mapy (.tmmap round-trip preserves exact cross pixels)
    # ------------------------------------------------------------------
    def test_08_save_and_reload_map_preserves_exact_intersection_pixels(self):
        at = self._make_summer_autotile(7, 1, "PersistCross")
        coords = [(2, 4), (3, 4), (4, 4), (5, 4), (6, 4), (4, 2), (4, 3), (4, 5), (4, 6)]
        self.engine.apply_rpg_autotile_stroke(self.layer, coords, at, self.project, self.am)

        before_img = _render_project_image(self.project, self.am, self.engine)

        save_path = os.path.join(self.tmp.name, "intersection_map.tmmap")
        self.assertTrue(ProjectIO.save_project(self.project, self.am, save_path, self.engine))

        fresh_am = AssetManager()
        fresh_engine = AutoTileEngine(asset_manager=fresh_am)
        reloaded = ProjectIO.load_project(save_path, fresh_am, autotile_engine=fresh_engine)
        self.assertIsNotNone(reloaded)

        after_img = _render_project_image(reloaded, fresh_am, fresh_engine)
        # Pixel-for-pixel identical across the entire intersection center!
        for y in range(4 * 32, 5 * 32):
            for x in range(4 * 32, 5 * 32):
                self.assertEqual(
                    before_img.pixel(x, y),
                    after_img.pixel(x, y),
                    f"Mismatch at ({x},{y}) after save/reload!",
                )

    # ------------------------------------------------------------------
    # 9. Zmiana sąsiedztwa wokół skrzyżowania (+ preservation of independent tiles & other layers)
    # ------------------------------------------------------------------
    def test_09_neighbor_mutation_around_cross_preserves_independent_tiles_and_layers(self):
        at = self._make_summer_autotile(7, 1, "NeighborMut")
        # Place an independent non-autotile next to the cross AND a tile on layer 2
        indep = MapItem(
            asset_id=self.summer_asset.id,
            col=1,
            row=1,
            item_type=ItemType.TILE,
            source_x=96,
            source_y=0,
            source_w=32,
            source_h=32,
            dest_w=32,
            dest_h=32,
            is_auto_tiled=False,
        )
        self.layer.set_tile(1, 1, indep)
        layer2 = self.project.add_layer("Upper Layer")
        layer2.set_tile(4, 4, indep.clone())

        # Build cross at (4, 4)
        coords = [(3, 4), (4, 4), (5, 4), (4, 3), (4, 5)]
        self.engine.apply_rpg_autotile_stroke(self.layer, coords, at, self.project, self.am)
        self.assertEqual(
            mask_to_quadrant_states(self.engine.compute_rpg_mask(self.layer, 4, 4, at, self.project)),
            (QUAD_INNER_CORNER, QUAD_INNER_CORNER, QUAD_INNER_CORNER, QUAD_INNER_CORNER),
        )

        # Fill diagonal NW cell (3, 3) -> TL quadrant of (4,4) transitions from INNER_CORNER to CENTER!
        self.engine.apply_rpg_autotile_stroke(self.layer, [(3, 3)], at, self.project, self.am)
        self.assertEqual(
            mask_to_quadrant_states(self.engine.compute_rpg_mask(self.layer, 4, 4, at, self.project)),
            (QUAD_CENTER, QUAD_INNER_CORNER, QUAD_INNER_CORNER, QUAD_INNER_CORNER),
        )

        # Independent tile and layer 2 tile must remain completely untouched
        self.assertEqual(self.layer.get_tile(1, 1).asset_id, self.summer_asset.id)
        self.assertFalse(self.layer.get_tile(1, 1).is_auto_tiled)
        self.assertEqual(layer2.get_tile(4, 4).asset_id, self.summer_asset.id)

    # ------------------------------------------------------------------
    # 10. Undo/Redo po zmianie skrzyżowania (standard + multi-tile variant)
    # ------------------------------------------------------------------
    def test_10_undo_redo_intersection_edits_and_variant_erasure(self):
        at = self._make_summer_autotile(7, 1, "UndoCross")
        ctx = ToolContext(
            project=self.project,
            active_layer=self.layer,
            asset_manager=self.am,
            history_manager=self.history,
            brush_settings=BrushSettings(),
            autotile_engine=self.engine,
            selected_asset=SelectedAutotile(at),
        )
        ctx.brush_settings.selected_autotile = ctx.selected_asset
        brush = BrushTool()
        eraser = EraserTool()

        # Stroke 1: Horizontal line (3..7, 5)
        brush.on_press(3, 5, ctx)
        for c in (4, 5, 6, 7):
            brush.on_drag(c, 5, ctx)
        brush.on_release(7, 5, ctx)
        img_line = _render_project_image(self.project, self.am, self.engine)

        # Stroke 2: Vertical line crossing at (5, 5) -> forms 4-way cross!
        brush.on_press(5, 3, ctx)
        for r in (4, 5, 6, 7):
            brush.on_drag(5, r, ctx)
        brush.on_release(5, 7, ctx)
        self.assertEqual(self.engine.compute_rpg_mask(self.layer, 5, 5, at, self.project), 85)
        img_cross = _render_project_image(self.project, self.am, self.engine)

        # Stroke 3: Erase South arm (5, 6) -> cross becomes T-junction
        eraser.on_press(5, 6, ctx)
        eraser.on_release(5, 6, ctx)
        self.assertEqual(self.engine.compute_rpg_mask(self.layer, 5, 5, at, self.project), 69)
        img_t = _render_project_image(self.project, self.am, self.engine)

        # Undo Stroke 3 -> exact pixel restoration of 4-way cross!
        self.assertTrue(self.history.undo())
        self.assertEqual(self.engine.compute_rpg_mask(self.layer, 5, 5, at, self.project), 85)
        img_undo_cross = _render_project_image(self.project, self.am, self.engine)
        self.assertEqual(img_undo_cross.constBits().asstring(img_undo_cross.sizeInBytes()), img_cross.constBits().asstring(img_cross.sizeInBytes()))

        # Undo Stroke 2 -> exact pixel restoration of horizontal line!
        self.assertTrue(self.history.undo())
        self.assertEqual(self.engine.compute_rpg_mask(self.layer, 5, 5, at, self.project), 68)
        img_undo_line = _render_project_image(self.project, self.am, self.engine)
        self.assertEqual(img_undo_line.constBits().asstring(img_undo_line.sizeInBytes()), img_line.constBits().asstring(img_line.sizeInBytes()))

        # Redo Stroke 2 + Stroke 3 -> exact pixel restoration of T-junction!
        self.assertTrue(self.history.redo())
        self.assertTrue(self.history.redo())
        self.assertEqual(self.engine.compute_rpg_mask(self.layer, 5, 5, at, self.project), 69)
        img_redo_t = _render_project_image(self.project, self.am, self.engine)
        self.assertEqual(img_redo_t.constBits().asstring(img_redo_t.sizeInBytes()), img_t.constBits().asstring(img_t.sizeInBytes()))

    # ------------------------------------------------------------------
    # 11. Przykład 2 ze screena: zielona ścieżka z płaskim środkiem -> spójna tekstura centrum
    # ------------------------------------------------------------------
    def test_11_screenshot_ex2_solid_green_grass_center_is_textured_not_flat(self):
        at = self._make_summer_autotile(1, 1, "SolidGreenGrass")
        coords = [(2, 1), (1, 2), (2, 2), (3, 2), (2, 3)]
        self.engine.apply_rpg_autotile_stroke(self.layer, coords, at, self.project, self.am)
        img = _render_project_image(self.project, self.am, self.engine)

        # Center tile (2,2) must have textured green blades (NOT a 1-color flat solid green blob!)
        cx0, cy0 = 2 * 32, 2 * 32
        rgbs = set()
        for y in range(cy0 + 8, cy0 + 24):
            for x in range(cx0 + 8, cx0 + 24):
                c = img.pixelColor(x, y)
                self.assertTrue(_is_green_interior(c))
                rgbs.add((c.red(), c.green(), c.blue()))
        self.assertGreaterEqual(len(rgbs), 2, "Solid-center grass cross must be textured, not a flat single-color blob!")

    # ------------------------------------------------------------------
    # 12. Przykład 3 ze screena: woda z brązowym klifem i trawą -> gładkie kontury i brak schodków
    # ------------------------------------------------------------------
    def test_12_screenshot_ex3_water_multilayer_cliff_bank_and_rippled_center(self):
        at = self._make_summer_autotile(1, 11, "WaterCliff")
        coords = [(2, 1), (1, 2), (2, 2), (3, 2), (2, 3)]
        self.engine.apply_rpg_autotile_stroke(self.layer, coords, at, self.project, self.am)
        img = _render_project_image(self.project, self.am, self.engine)

        is_water = lambda c: c.alpha() > 200 and c.blue() > c.red() + 40
        is_cliff_or_grass = lambda c: c.alpha() > 200 and not is_water(c)

        cx0, cy0 = 2 * 32, 2 * 32
        # 1. Center 12x12 of water cross must be 100% blue water AND rippled (>= 2 shades, not flat teal!)
        water_rgbs = set()
        for y in range(cy0 + 10, cy0 + 22):
            for x in range(cx0 + 10, cx0 + 22):
                c = img.pixelColor(x, y)
                self.assertTrue(is_water(c), f"Expected blue water at ({x},{y}), got {c.getRgb()}")
                water_rgbs.add((c.red(), c.green(), c.blue()))
        self.assertGreaterEqual(len(water_rgbs), 2, "Water cross center must preserve rippled caustic texture!")

        # 2. All 4 inner corners of the water cross MUST preserve bank pixels (grass/cliff) matching incoming arms!
        tl_bank = sum(1 for y in range(cy0, cy0 + 8) for x in range(cx0, cx0 + 8) if is_cliff_or_grass(img.pixelColor(x, y)))
        tr_bank = sum(1 for y in range(cy0, cy0 + 8) for x in range(cx0 + 24, cx0 + 32) if is_cliff_or_grass(img.pixelColor(x, y)))
        bl_bank = sum(1 for y in range(cy0 + 24, cy0 + 32) for x in range(cx0, cx0 + 8) if is_cliff_or_grass(img.pixelColor(x, y)))
        br_bank = sum(1 for y in range(cy0 + 24, cy0 + 32) for x in range(cx0 + 24, cx0 + 32) if is_cliff_or_grass(img.pixelColor(x, y)))
        for corner_name, count in (("TL", tl_bank), ("TR", tr_bank), ("BL", bl_bank), ("BR", br_bank)):
            self.assertGreaterEqual(count, 10, f"Water inner corner {corner_name} lost its shoreline bank ({count} px)!")

        # 3. Left seam of center tile must align water depth with right seam of left arm (within 2px — no crooked step!)
        left_arm_water = sum(1 for y in range(cy0, cy0 + 32) if is_water(img.pixelColor(cx0 - 1, y)))
        center_left_water = sum(1 for y in range(cy0, cy0 + 32) if is_water(img.pixelColor(cx0, y)))
        self.assertLessEqual(abs(left_arm_water - center_left_water), 2)

    # ------------------------------------------------------------------
    # 13. Przykład 4 ze screena: kompozycja 2x2 (ciągła ścieżka ORAZ niepodzielna kompozycja WxH)
    # ------------------------------------------------------------------
    def test_13_screenshot_ex4_2x2_connected_path_and_logical_wxh_compositions(self):
        # Part A: 2x2 closed dirt-in-grass patch (6,3) as connected path -> NO 4 separated circles!
        at_path = create_rpg_autotile_from_tile(
            "DirtInGrass2x2", self.summer_asset.id, self.summer_sheet, 6, 3,
            tile_size=32, mode="auto", w_tiles=2, h_tiles=2, terrain_type="dirt2x2",
        )
        self.engine.register_rpg_autotile(at_path, self.am)

        # Horizontal 4x1 line at (1..4, 2)
        self.engine.apply_rpg_autotile_stroke(self.layer, [(1, 2), (2, 2), (3, 2), (4, 2)], at_path, self.project, self.am)
        img = _render_project_image(self.project, self.am, self.engine)
        # Centerline y = 2*32 + 16 MUST be continuous brown dirt across ALL internal tile seams (zero green walls!)
        for x in range(1 * 32 + 12, 4 * 32 + 20):
            c = img.pixelColor(x, 2 * 32 + 16)
            self.assertTrue(_is_brown_outer(c), f"Green divider wall broke 2x2 horizontal path at x={x}: {c.getRgb()}")

        # 4-way cross at (7, 5): center 10x10 must be 100% pure brown dirt (zero stray green specks!)
        self.engine.apply_rpg_autotile_stroke(
            self.layer, [(7, 4), (6, 5), (7, 5), (8, 5), (7, 6)], at_path, self.project, self.am
        )
        img2 = _render_project_image(self.project, self.am, self.engine)
        for y in range(5 * 32 + 11, 5 * 32 + 21):
            for x in range(7 * 32 + 11, 7 * 32 + 21):
                self.assertTrue(_is_brown_outer(img2.pixelColor(x, y)), f"Stray non-dirt speck at ({x},{y})")

        # Part B: True logical multi-cell compositions (2x2, 2x3, 3x2, 3x3) with BrushTool, EraserTool, Undo/Redo & Save/Reload!
        for cw, ch in ((2, 2), (2, 3), (3, 2), (3, 3)):
            with self.subTest(composition=(cw, ch)):
                proj = Project(map_width=12, map_height=12, tile_size=32)
                layer = proj.get_active_layer()
                hist = HistoryManager()
                at_comp = create_rpg_autotile_from_tile(
                    f"Comp_{cw}x{ch}", self.summer_asset.id, self.summer_sheet, 6, 3,
                    tile_size=32, mode="composition_wxh", w_tiles=cw, h_tiles=ch, terrain_type=f"comp_{cw}_{ch}",
                )
                self.engine.register_rpg_autotile(at_comp, self.am)
                self.assertTrue(at_comp.is_multi_cell_composition)
                self.assertEqual((at_comp.composition_width, at_comp.composition_height), (cw, ch))

                ctx = ToolContext(
                    project=proj, active_layer=layer, asset_manager=self.am,
                    history_manager=hist, brush_settings=BrushSettings(),
                    autotile_engine=self.engine, selected_asset=SelectedAutotile(at_comp),
                )
                ctx.brush_settings.selected_autotile = ctx.selected_asset
                brush = BrushTool()
                eraser = EraserTool()

                # Single click at (0, 0) places ALL cw*ch tiles in exact relative positions!
                brush.on_press(0, 0, ctx)
                brush.on_release(0, 0, ctx)
                self.assertEqual(len(layer.tiles), cw * ch)
                for dr in range(ch):
                    for dc in range(cw):
                        t = layer.get_tile(dc, dr)
                        self.assertIsNotNone(t)
                        self.assertEqual(t.asset_id, self.summer_asset.id)
                        self.assertEqual((t.source_x, t.source_y), ((6 + dc) * 32, (3 + dr) * 32))
                        self.assertEqual(t.properties.get("composition_origin"), [0, 0])
                        self.assertEqual(t.properties.get("composition_size"), [cw, ch])

                # Clicking next macro-cell (cw, 0) places a second non-overlapping WxH composition!
                brush.on_press(cw, 0, ctx)
                brush.on_release(cw, 0, ctx)
                self.assertEqual(len(layer.tiles), 2 * cw * ch)

                # Sandbox preview also renders full WxH composition footprint!
                sb_eval = self.engine.evaluate_rpg_sandbox_grid({(0, 0)}, at_comp, 10, 10, asset_manager=self.am)
                self.assertEqual(len(sb_eval), cw * ch)

                # Erasing 1 cell (0, 0) removes the ENTIRE first WxH composition atomically (zero orphans!)
                eraser.on_press(0, 0, ctx)
                eraser.on_release(0, 0, ctx)
                self.assertEqual(len(layer.tiles), cw * ch)
                self.assertIsNone(layer.get_tile(cw - 1, ch - 1))

                # Undo restores ALL cw*ch tiles of the erased composition!
                self.assertTrue(hist.undo())
                self.assertEqual(len(layer.tiles), 2 * cw * ch)
                self.assertIsNotNone(layer.get_tile(cw - 1, ch - 1))

                # Save & reload preserves composition metadata and tiles!
                save_p = os.path.join(self.tmp.name, f"comp_{cw}x{ch}.tmmap")
                self.assertTrue(ProjectIO.save_project(proj, self.am, save_p, self.engine))
                am2 = AssetManager()
                eng2 = AutoTileEngine(asset_manager=am2)
                reloaded = ProjectIO.load_project(save_p, am2, autotile_engine=eng2)
                self.assertIsNotNone(reloaded)
                self.assertEqual(len(reloaded.get_active_layer().tiles), 2 * cw * ch)
                r_at = eng2.get_rpg_autotile(at_comp.id)
                self.assertTrue(r_at.is_multi_cell_composition)
                self.assertEqual((r_at.composition_width, r_at.composition_height), (cw, ch))

    # ------------------------------------------------------------------
    # 14. Różne rozmiary kafelków (16x16, 24x24, 48x48), path_width=2 i kontrolki dialogu
    # ------------------------------------------------------------------
    def test_14_different_tile_sizes_path_width_and_dialog_controls(self):
        # Test 16x16, 24x24, and 48x48 tile sizes
        for ts in (16, 24, 48):
            with self.subTest(tile_size=ts):
                patch = QImage(3 * ts, 3 * ts, QImage.Format.Format_ARGB32)
                patch.fill(QColor(170, 125, 75, 255))
                p = QPainter(patch)
                rim = max(4, ts // 3)
                p.fillRect(rim, rim, 3 * ts - 2 * rim, 3 * ts - 2 * rim, QColor(70, 145, 55, 255))
                p.end()
                vx = synthesize_vx_ace_from_3x3(patch, ts)
                self.assertEqual((vx.width(), vx.height()), (2 * ts, 3 * ts))
                at = RPGAutotile(tile_size=ts)
                at.set_source_qimage(vx)
                self.assertTrue(at.has_valid_atlas())

        # Test path_width = 2 paints 2-tile-wide connected path + cross cleanly
        at_w2 = create_rpg_autotile_from_tile(
            "Wide2Road", self.summer_asset.id, self.summer_sheet, 7, 1,
            tile_size=32, mode="auto", path_width=2, rim_balance=0.28, terrain_type="wide2",
        )
        self.engine.register_rpg_autotile(at_w2, self.am)
        self.engine.apply_rpg_autotile_stroke(self.layer, [(2, 4), (3, 4), (4, 4)], at_w2, self.project, self.am)
        # Should occupy 2 rows (row 4 and row 5) across cols 2..5!
        for r in (4, 5):
            for c in (2, 3, 4, 5):
                self.assertIsNotNone(self.layer.get_tile(c, r))

        # Verify PathGeneratorDialog exposes composition_wxh, path_width, and rim_balance controls
        dlg = PathGeneratorDialog(self.engine, self.am, initial_asset_id=self.summer_asset.id)
        idx_comp = dlg.cmb_mode.findData("composition_wxh")
        self.assertGreaterEqual(idx_comp, 0)
        dlg._on_region_selected(6, 3, 2, 2)
        dlg.cmb_mode.setCurrentIndex(idx_comp)
        self.assertTrue(dlg.current_autotile.is_multi_cell_composition)
        self.assertEqual((dlg.current_autotile.composition_width, dlg.current_autotile.composition_height), (2, 2))
        dlg.spin_path_width.setValue(2)
        self.assertEqual(dlg.current_autotile.path_width, 2)
        dlg.close()


if __name__ == "__main__":
    unittest.main()
