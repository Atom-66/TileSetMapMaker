import os
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.history import HistoryManager, LayerClearCommand
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.select_tool import SelectTool
from tileset_map_maker.core.tools.wand import WandTool
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.models.asset import SelectedSubTile
from tileset_map_maker.models.layer import CollisionObject, MapItem
from tileset_map_maker.models.path_ruleset import (
    PathRuleSet,
    ROLE_EDGE_TOP,
    ROLE_END,
    ROLE_START,
    TEMPLATE_3X3,
)
from tileset_map_maker.models.project import Project
from tileset_map_maker.ui.tool_panel import ToolPanel
from tileset_map_maker.ui.tileset_palette_widget import TilesetPaletteWidget


APP = QApplication.instance() or QApplication([])


class TestReportedEditorRegressions(unittest.TestCase):
    def test_horizontal_tools_remain_one_row(self):
        panel = ToolPanel()
        panel.resize(500, 52)
        panel._apply_orientation(Qt.Orientation.Horizontal)
        layout = panel.layout()
        self.assertIsNotNone(layout)
        self.assertEqual(layout.count(), 10)
        self.assertTrue(
            all(layout.itemAt(index).widget() for index in range(10))
        )
        self.assertTrue(
            all(layout.getItemPosition(index)[0] == 0 for index in range(10))
        )
        self.assertEqual(panel.minimumWidth(), 404)
        panel._apply_orientation(Qt.Orientation.Vertical)
        self.assertEqual(panel.minimumWidth(), 44)

    def test_top_dock_height_is_resizable(self):
        from tileset_map_maker.ui.main_window import MainWindow

        window = MainWindow()
        window.show()
        window.addDockWidget(
            Qt.DockWidgetArea.TopDockWidgetArea, window.tool_dock
        )
        window._update_tool_dock_width()
        APP.processEvents()
        self.assertGreater(
            window.tool_dock.maximumHeight(), window.tool_dock.minimumHeight()
        )
        self.assertGreater(window.tool_dock.maximumHeight(), 200)
        window.tool_dock.resize(window.tool_dock.width(), 120)
        APP.processEvents()
        self.assertEqual(
            window.tool_panel.current_orientation,
            Qt.Orientation.Horizontal,
        )
        self.assertGreaterEqual(window.tool_panel.height(), 44)
        window.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, window.tool_dock
        )
        window.project.is_modified = False
        window.close()

    def test_select_starts_move_inside_previous_rect(self):
        project = Project(map_width=5, map_height=5)
        context = ToolContext(
            project, AssetManager(), HistoryManager(),
            project.get_active_layer(),
        )
        tool = SelectTool()
        tool.on_press(1, 1, context)
        tool.on_drag(3, 3, context)
        tool.on_release(3, 3, context)
        tool.on_press(2, 2, context)
        self.assertTrue(tool.moving_selection)
        self.assertEqual(tool.selection_rect.width(), 3)
        self.assertEqual(tool.selection_rect.height(), 3)
        self.assertIn((2, 2), context.selected_cells)

    def test_wand_records_exact_irregular_selection(self):
        project = Project(map_width=5, map_height=5)
        layer = project.get_active_layer()
        layer.set_tile(1, 1, MapItem("a", 1, 1))
        layer.set_tile(2, 1, MapItem("a", 2, 1))
        layer.set_tile(2, 2, MapItem("a", 2, 2))
        layer.set_tile(3, 3, MapItem("b", 3, 3))
        context = ToolContext(project, AssetManager(), HistoryManager(), layer)
        tool = WandTool()
        tool.on_press(1, 1, context)
        self.assertEqual(
            tool.selected_cells,
            {(1, 1), (2, 1), (2, 2)},
        )
        self.assertNotIn((3, 3), context.selected_cells)

    def test_selection_renderer_draws_wand_cells_only(self):
        project = Project(map_width=4, map_height=4)
        engine = RenderEngine(AssetManager())
        image = QImage(128, 128, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        engine.render(
            painter,
            project,
            RenderOptions(
                show_grid=False,
                selection_cells=[(1, 1), (3, 3)],
            ),
        )
        painter.end()
        self.assertEqual(engine.metrics.visible_items[-1], 0)

    def test_layer_clear_is_undoable_for_all_content_types(self):
        project = Project()
        layer = project.get_active_layer()
        layer.set_tile(1, 1, MapItem("a", 1, 1))
        layer.add_object(MapItem("b", 0, 0))
        layer.add_collision(CollisionObject(4, 4, 8, 8))
        command = LayerClearCommand(project, layer.id)
        command.execute()
        self.assertFalse(layer.tiles)
        self.assertFalse(layer.objects)
        self.assertFalse(layer.collisions)
        command.undo()
        self.assertTrue(layer.tiles)
        self.assertTrue(layer.objects)
        self.assertTrue(layer.collisions)

    def test_randomizer_gap_range_is_repeatable_and_serialized(self):
        settings = BrushSettings(
            random_variant=True, gap_min=1, gap_max=1, seed=7
        )
        settings.add_variant(
            SelectedSubTile("a", 0, 0, sub_w=32, sub_h=32)
        )
        sequence = [settings.consume_gap() for _ in range(5)]
        self.assertEqual(sequence, [False, True, False, True, False])
        restored = BrushSettings()
        restored.load_from_dict(settings.to_dict())
        self.assertEqual((restored.gap_min, restored.gap_max), (1, 1))

    def test_paths_3x3_contains_edges_start_and_end(self):
        ruleset = PathRuleSet(template_type="3x3")
        roles = ruleset.get_template_roles()
        self.assertEqual(set(roles), set(TEMPLATE_3X3))
        self.assertIn(ROLE_EDGE_TOP, roles)
        self.assertIn(ROLE_START, roles)
        self.assertIn(ROLE_END, roles)

    def test_brush_gap_reduces_painted_cells(self):
        project = Project(map_width=10, map_height=2)
        settings = BrushSettings(
            random_variant=True, gap_min=2, gap_max=2, seed=11
        )
        variant = SelectedSubTile(
            "a", 0, 0, sub_w=32, sub_h=32,
            tile_width=32, tile_height=32,
        )
        settings.add_variant(variant)
        context = ToolContext(
            project,
            AssetManager(),
            HistoryManager(),
            project.get_active_layer(),
            selected_asset=variant,
            brush_settings=settings,
        )
        tool = BrushTool()
        tool.on_press(0, 0, context)
        for col in range(1, 7):
            tool.on_drag(col, 0, context)
        tool.on_release(6, 0, context)
        self.assertLess(len(project.get_active_layer().tiles), 7)

    def test_new_library_folder_is_created_at_root_by_default(self):
        palette = TilesetPaletteWidget(AssetManager())
        palette.asset_manager.category_tree.add_category_path("Wybrany")
        palette.refresh_tilesets()
        palette.tree.setCurrentItem(palette._find_folder_item("Wybrany"))
        with patch(
            "tileset_map_maker.ui.tileset_palette_widget.QInputDialog.getText",
            return_value=("Nowy", True),
        ):
            palette._create_folder_action()
        self.assertIsNotNone(
            palette.asset_manager.category_tree.get_node("Nowy")
        )
        self.assertIsNone(
            palette.asset_manager.category_tree.get_node("Wybrany/Nowy")
        )

    def test_batch_folder_import_does_not_rebuild_during_each_drop(self):
        palette = TilesetPaletteWidget(AssetManager())
        with tempfile.TemporaryDirectory() as root:
            for name in ("Pierwszy", "Drugi"):
                folder = os.path.join(root, name)
                os.mkdir(folder)
                APP.processEvents()
                with patch.object(palette, "refresh_tilesets") as refresh:
                    palette.import_folder_from_path(
                        folder, show_message=False, refresh=False
                    )
                    refresh.assert_not_called()
        self.assertIsNotNone(
            palette.asset_manager.category_tree.get_node("Pierwszy")
        )
        self.assertIsNotNone(
            palette.asset_manager.category_tree.get_node("Drugi")
        )


if __name__ == "__main__":
    unittest.main()
