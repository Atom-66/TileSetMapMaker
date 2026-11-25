import os
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QPoint, QPointF, Qt, QMimeData, QEvent
from PyQt6.QtGui import QAction, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.ui.drag_safety import DragSafetyManager
from tileset_map_maker.ui.toolbar_manager import (
    CustomizableToolBar,
    ToolbarCategoryListWidget,
    ToolbarCustomizerDialog,
    ToolbarManager,
    ToolbarDragPhase,
    DragContext,
    DragElementType,
    ToolbarDragOperation,
    ToolbarDragRequest,
)


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
app = QApplication.instance() or QApplication([])


class FakeDropEvent:
    def __init__(self, mime_data, position=QPointF(0, 0)):
        self._mime_data = mime_data
        self._position = position
        self.accepted = False
        self.ignored = False
        self.drop_action = None

    def mimeData(self):
        return self._mime_data

    def position(self):
        return self._position

    def acceptProposedAction(self):
        self.accepted = True

    def setDropAction(self, action):
        self.drop_action = action

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


class TestToolbarDragDropSeparation(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        config_path = os.path.join(self.tmp_dir.name, "toolbar.json")
        self.config = ConfigManager(custom_config_path=config_path)
        self.main_toolbar = CustomizableToolBar("Main", toolbar_id="main")
        self.secondary_toolbar = CustomizableToolBar("Secondary", toolbar_id="secondary")
        self.manager = ToolbarManager(
            self.main_toolbar,
            self.config,
            secondary_toolbar=self.secondary_toolbar,
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def category_mime(self, category_id, context=DragContext.TOOLBAR):
        request = self.manager.create_category_drag_request(category_id, context)
        mime_type = (
            "application/x-toolbar-category"
            if context is DragContext.TOOLBAR
            else "application/x-toolbar-config-category"
        )
        mime_data = QMimeData()
        mime_data.setData(mime_type, request.to_bytes())
        return mime_data

    def item_mime(self, dialog, item_id):
        item = dialog.working_items[item_id]
        category = dialog.working_categories[item.category_id]
        request = ToolbarDragRequest(
            element_type=DragElementType.BUTTON,
            element_id=item_id,
            context=DragContext.CUSTOMIZER,
            allowed_operations=(
                ToolbarDragOperation.BUTTON_REORDER,
                ToolbarDragOperation.BUTTON_REASSIGN,
            ),
            source_category_id=category.id,
            source_toolbar_id=category.toolbar_id,
        )
        mime_data = QMimeData()
        mime_data.setData("application/x-toolbar-config-item", request.to_bytes())
        return mime_data

    def test_top_toolbar_rejects_configurator_item_payload(self):
        before_categories = {
            cat_id: list(category.item_ids)
            for cat_id, category in self.manager.categories.items()
        }
        before_assignments = {
            item_id: item.category_id for item_id, item in self.manager.items.items()
        }
        mime_data = QMimeData()
        mime_data.setData("application/x-toolbar-config-item", b"undo")

        enter_event = FakeDropEvent(mime_data)
        self.main_toolbar.dragEnterEvent(enter_event)
        self.assertTrue(enter_event.ignored)
        self.assertFalse(enter_event.accepted)

        drop_event = FakeDropEvent(mime_data)
        self.main_toolbar.dropEvent(drop_event)
        self.assertTrue(drop_event.ignored)
        self.assertEqual(
            {cat_id: cat.item_ids for cat_id, cat in self.manager.categories.items()},
            before_categories,
        )
        self.assertEqual(
            {item_id: item.category_id for item_id, item in self.manager.items.items()},
            before_assignments,
        )

    def test_edit_mode_button_drag_reorders_only_within_its_category(self):
        action = QAction("Undo", self.main_toolbar)
        redo_action = QAction("Redo", self.main_toolbar)
        triggered = []
        action.triggered.connect(lambda: triggered.append(True))
        self.manager.register_item("undo", "Undo", "history", action=action)
        self.manager.register_item("redo", "Redo", "history", action=redo_action)
        self.manager.build_toolbar()
        self.main_toolbar.resize(900, 80)
        self.main_toolbar.show()
        self.manager.set_edit_mode(True)
        app.processEvents()

        drag_filter = self.manager._item_drag_filters["undo"]
        button = self.main_toolbar.item_widgets_map["undo"]
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(1, 1),
            QPointF(1, 1),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        below_threshold = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(2, 1),
            QPointF(2, 1),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        beyond_threshold = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(40, 1),
            QPointF(40, 1),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        self.assertFalse(drag_filter.eventFilter(button, press))
        self.assertEqual(drag_filter.phase, ToolbarDragPhase.PRESSED)
        self.assertFalse(drag_filter.eventFilter(button, below_threshold))
        self.assertEqual(drag_filter.phase, ToolbarDragPhase.PRESSED)
        captured = {}

        class FakeDrag:
            def __init__(self, source):
                captured["source"] = source

            def setMimeData(self, mime_data):
                captured["mime_data"] = mime_data

            def setPixmap(self, pixmap):
                captured["pixmap"] = pixmap

            def setHotSpot(self, point):
                captured["hotspot"] = point

            def exec(self, action):
                captured["action"] = action
                return Qt.DropAction.IgnoreAction

        with patch("tileset_map_maker.ui.toolbar_manager.QDrag", FakeDrag):
            self.assertTrue(drag_filter.eventFilter(button, beyond_threshold))
        self.assertEqual(drag_filter.phase, ToolbarDragPhase.IDLE)
        request = ToolbarDragRequest.from_bytes(
            bytes(captured["mime_data"].data("application/x-toolbar-button"))
        )
        self.assertIsNotNone(request)
        self.assertEqual(request.element_type, DragElementType.BUTTON)
        self.assertEqual(request.element_id, "undo")
        self.assertEqual(request.source_category_id, "history")
        self.assertEqual(request.context, DragContext.TOOLBAR)

        category_widget = self.main_toolbar.category_widgets["history"]
        redo_widget = category_widget.item_widgets["redo"]
        redo_pos = redo_widget.mapTo(self.main_toolbar.container, QPoint(0, 0))
        drop_pos_container = QPoint(
            redo_pos.x() + redo_widget.width() // 2 - 1,
            redo_pos.y() + redo_widget.height() // 2,
        )
        drop_pos_toolbar = self.main_toolbar.mapFrom(
            self.main_toolbar.container, drop_pos_container
        )
        move_event = FakeDropEvent(
            captured["mime_data"],
            QPointF(drop_pos_toolbar.x(), drop_pos_toolbar.y()),
        )
        self.main_toolbar.dragMoveEvent(move_event)
        self.assertTrue(move_event.accepted)
        self.assertEqual(self.main_toolbar.target_cat_id, "history")
        self.assertIsNotNone(self.main_toolbar.drop_indicator_x)

        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(40, 1),
            QPointF(40, 1),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.assertTrue(drag_filter.eventFilter(button, release))

        drop_event = FakeDropEvent(
            captured["mime_data"],
            QPointF(drop_pos_toolbar.x(), drop_pos_toolbar.y()),
        )
        self.main_toolbar.dropEvent(drop_event)
        self.assertTrue(drop_event.accepted)

        self.assertEqual(drag_filter.phase, ToolbarDragPhase.IDLE)
        self.assertEqual(self.manager.categories["history"].item_ids, ["redo", "undo"])
        self.assertIsNone(self.manager.dragged_item_id)
        self.assertEqual(triggered, [])
        restored = ToolbarManager(
            CustomizableToolBar("Restored Main", toolbar_id="main"),
            self.config,
            secondary_toolbar=CustomizableToolBar(
                "Restored Secondary", toolbar_id="secondary"
            ),
        )
        restored.load_layout()
        self.assertEqual(restored.categories["history"].item_ids, ["redo", "undo"])

    def test_toolbar_button_drop_to_other_category_or_toolbar_is_rejected(self):
        self.manager.register_item(
            "undo", "Undo", "history", action=QAction("Undo", self.main_toolbar)
        )
        self.manager.build_toolbar()
        self.main_toolbar.resize(900, 100)
        self.secondary_toolbar.resize(900, 100)
        self.main_toolbar.show()
        self.secondary_toolbar.show()
        self.manager.set_edit_mode(True)
        app.processEvents()
        request = self.manager.create_button_drag_request(
            "undo", DragContext.TOOLBAR
        )
        mime_data = QMimeData()
        mime_data.setData("application/x-toolbar-button", request.to_bytes())
        before_layout = self.manager.get_layout_dict()

        project_widget = self.main_toolbar.category_widgets["project"]
        project_pos = project_widget.geometry().center()
        project_pos_toolbar = self.main_toolbar.mapFrom(
            self.main_toolbar.container, project_pos
        )
        other_category_move = FakeDropEvent(
            mime_data,
            QPointF(project_pos_toolbar.x(), project_pos_toolbar.y()),
        )
        self.main_toolbar.dragMoveEvent(other_category_move)
        self.assertTrue(other_category_move.ignored)
        self.assertIsNone(self.main_toolbar.drop_indicator_x)
        other_category_drop = FakeDropEvent(mime_data)
        self.main_toolbar.dropEvent(other_category_drop)
        self.assertTrue(other_category_drop.ignored)

        other_toolbar_move = FakeDropEvent(mime_data, QPointF(20, 20))
        self.secondary_toolbar.dragMoveEvent(other_toolbar_move)
        self.assertTrue(other_toolbar_move.ignored)
        self.assertIsNone(self.secondary_toolbar.drop_indicator_x)

        self.assertEqual(self.manager.get_layout_dict(), before_layout)
        self.assertEqual(self.manager.items["undo"].category_id, "history")

    def test_top_toolbars_reject_button_payload_without_preview_or_mutation(self):
        undo_action = QAction("Undo", self.main_toolbar)
        path_action = QAction("Paths", self.secondary_toolbar)
        self.manager.register_item("undo", "Undo", "history", action=undo_action)
        self.manager.register_item(
            "path_gen_dialog", "Paths", "paths", action=path_action
        )
        self.manager.build_toolbar()
        self.manager.set_edit_mode(True)
        before_layout = self.manager.get_layout_dict()
        save_calls = []
        self.manager.save_layout = lambda: save_calls.append(True) or True

        for toolbar in (self.main_toolbar, self.secondary_toolbar):
            with self.subTest(toolbar=toolbar.toolbar_id):
                direct_button_request = ToolbarDragRequest(
                    element_type=DragElementType.BUTTON,
                    element_id="undo",
                    context=DragContext.TOOLBAR,
                    allowed_operations=(ToolbarDragOperation.BUTTON_REASSIGN,),
                    source_category_id="history",
                    source_toolbar_id="main",
                )
                for mime_type, payload in (
                    ("application/x-toolbar-item", b"undo"),
                    ("application/x-toolbar-config-item", b"undo"),
                    (
                        "application/x-toolbar-category",
                        direct_button_request.to_bytes(),
                    ),
                ):
                    mime_data = QMimeData()
                    mime_data.setData(mime_type, payload)

                    enter = FakeDropEvent(mime_data)
                    toolbar.dragEnterEvent(enter)
                    self.assertTrue(enter.ignored)
                    self.assertFalse(enter.accepted)

                    move = FakeDropEvent(mime_data, QPointF(20, 20))
                    toolbar.dragMoveEvent(move)
                    self.assertTrue(move.ignored)
                    self.assertFalse(move.accepted)
                    self.assertIsNone(toolbar.drop_indicator_x)

                    drop = FakeDropEvent(mime_data)
                    toolbar.dropEvent(drop)
                    self.assertTrue(drop.ignored)

        self.assertEqual(self.manager.get_layout_dict(), before_layout)
        self.assertEqual(save_calls, [])
        self.assertIsNone(self.manager.dragged_item_id)
        self.assertIsNone(self.manager.dragged_category_id)

    def test_pressed_item_cancels_on_focus_loss_without_dragging(self):
        action = QAction("Undo", self.main_toolbar)
        self.manager.register_item("undo", "Undo", "history", action=action)
        self.manager.build_toolbar()
        self.manager.set_edit_mode(True)
        drag_filter = self.manager._item_drag_filters["undo"]
        button = self.main_toolbar.item_widgets_map["undo"]
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(1, 1),
            QPointF(1, 1),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        drag_filter.eventFilter(button, press)
        drag_filter.eventFilter(button, QEvent(QEvent.Type.FocusOut))

        self.assertEqual(drag_filter.phase, ToolbarDragPhase.IDLE)
        self.assertTrue(drag_filter._suppress_release)

    def test_category_drag_still_works_after_rejected_button_drop(self):
        undo_action = QAction("Undo", self.main_toolbar)
        path_action = QAction("Paths", self.secondary_toolbar)
        self.manager.register_item("undo", "Undo", "history", action=undo_action)
        self.manager.register_item(
            "path_gen_dialog", "Paths", "paths", action=path_action
        )
        self.manager.build_toolbar()
        self.main_toolbar.resize(900, 100)
        self.secondary_toolbar.resize(900, 100)
        self.main_toolbar.show()
        self.secondary_toolbar.show()
        self.manager.set_edit_mode(True)
        app.processEvents()

        item_mime = QMimeData()
        item_mime.setData("application/x-toolbar-item", b"undo")
        rejected_move = FakeDropEvent(item_mime, QPointF(20, 20))
        self.secondary_toolbar.dragMoveEvent(rejected_move)
        self.assertTrue(rejected_move.ignored)
        self.assertIsNone(self.secondary_toolbar.drop_indicator_x)

        before_items = list(self.manager.categories["project"].item_ids)
        category_mime = self.category_mime("project")
        category_move = FakeDropEvent(category_mime)
        self.secondary_toolbar.dragMoveEvent(category_move)
        self.assertTrue(category_move.accepted)
        category_drop = FakeDropEvent(category_mime)
        self.secondary_toolbar.dropEvent(category_drop)

        self.assertTrue(category_drop.accepted)
        self.assertEqual(self.manager.categories["project"].toolbar_id, "secondary")
        self.assertEqual(self.manager.categories["project"].item_ids, before_items)

        self.assertEqual(self.manager.items["undo"].category_id, "history")
        self.assertIn("undo", self.main_toolbar.category_widgets["history"].item_widgets)

    def test_category_move_preserves_all_category_contents_and_widgets(self):
        action = QAction("New", self.main_toolbar)
        self.manager.register_item("new", "New", "project", action=action)
        self.manager.build_toolbar()
        self.manager.set_edit_mode(True)
        category_widget = self.main_toolbar.category_widgets["project"]
        item_widget = category_widget.item_widgets["new"]
        category_items = list(self.manager.categories["project"].item_ids)
        item_assignments = {
            item_id: item.category_id for item_id, item in self.manager.items.items()
        }

        mime_data = self.category_mime("project")
        drag_move_event = FakeDropEvent(mime_data)
        self.secondary_toolbar.dragMoveEvent(drag_move_event)
        self.assertTrue(drag_move_event.accepted)
        self.assertTrue(self.secondary_toolbar.is_category_drag)
        self.assertIsNotNone(self.secondary_toolbar.drop_indicator_x)

        drop_event = FakeDropEvent(mime_data)
        self.secondary_toolbar.dropEvent(drop_event)

        self.assertTrue(drop_event.accepted)
        self.assertEqual(self.manager.categories["project"].toolbar_id, "secondary")
        self.assertEqual(self.manager.categories["project"].item_ids, category_items)
        self.assertEqual(
            {item_id: item.category_id for item_id, item in self.manager.items.items()},
            item_assignments,
        )
        self.assertIs(
            self.secondary_toolbar.category_widgets["project"], category_widget
        )
        self.assertIs(category_widget.item_widgets["new"], item_widget)

    def test_category_drop_reorders_categories_without_rebuilding(self):
        self.manager.build_toolbar()
        self.manager.set_edit_mode(True)
        category_widget = self.main_toolbar.category_widgets["view"]
        original_items = list(self.manager.categories["view"].item_ids)
        self.main_toolbar.target_cat_index = 0
        self.main_toolbar.is_category_drag = True
        mime_data = self.category_mime("view")

        move_event = FakeDropEvent(mime_data)
        self.main_toolbar.dragMoveEvent(move_event)
        self.main_toolbar.dropEvent(FakeDropEvent(mime_data))

        ordered_main = [
            category.id for category in self.manager.get_ordered_categories()
            if category.toolbar_id == "main"
        ]
        self.assertEqual(ordered_main[0], "view")
        self.assertIs(self.main_toolbar.category_widgets["view"], category_widget)
        self.assertEqual(self.manager.categories["view"].item_ids, original_items)

    def test_customizer_item_drop_changes_assignment_and_persists(self):
        dialog = ToolbarCustomizerDialog(self.manager)
        dialog.show()
        app.processEvents()
        history_row = next(
            row
            for row in range(dialog.list_main_cats.count())
            if dialog.list_main_cats.item(row).data(Qt.ItemDataRole.UserRole) == "history"
        )
        dialog.list_main_cats.setCurrentRow(history_row)
        app.processEvents()
        project_index = dialog.combo_target_cat.findData("project")
        self.assertGreaterEqual(project_index, 0)
        dialog.combo_target_cat.setCurrentIndex(project_index)
        dialog.list_items.setCurrentRow(0)
        dialog._move_item_to_target_category()

        self.assertNotIn("undo", dialog.working_categories["history"].item_ids)
        self.assertIn("undo", dialog.working_categories["project"].item_ids)
        self.assertEqual(dialog.working_items["undo"].category_id, "project")
        dialog._accept_and_save()

        restored = ToolbarManager(
            CustomizableToolBar("Restored Main", toolbar_id="main"),
            self.config,
            secondary_toolbar=CustomizableToolBar(
                "Restored Secondary", toolbar_id="secondary"
            ),
        )
        restored.load_layout()
        self.assertNotIn("undo", restored.categories["history"].item_ids)
        self.assertIn("undo", restored.categories["project"].item_ids)
        self.assertEqual(restored.items["undo"].category_id, "project")

    def test_customizer_rejects_button_drop_outside_selected_category(self):
        dialog = ToolbarCustomizerDialog(self.manager)
        dialog.show()
        app.processEvents()
        self.assertEqual(
            dialog.list_items.item(0).data(Qt.ItemDataRole.UserRole), "new"
        )

        mime_data = self.item_mime(dialog, "new")
        tab_bar = dialog.tab_toolbars.tabBar()
        tab_position = tab_bar.tabRect(1).center()
        dialog._item_drag_active = True
        tab_drag_event = FakeDropEvent(
            mime_data, QPointF(tab_position.x(), tab_position.y())
        )
        tab_bar.dragMoveEvent(tab_drag_event)

        self.assertEqual(dialog.tab_toolbars.currentIndex(), 1)
        self.assertEqual(
            dialog.list_items.item(0).data(Qt.ItemDataRole.UserRole), "new"
        )
        target_category_item = dialog.list_sec_cats.item(0)
        target_rect = dialog.list_sec_cats.visualItemRect(target_category_item)
        drop_event = FakeDropEvent(
            mime_data,
            QPointF(target_rect.center().x(), target_rect.center().y()),
        )
        dialog.list_sec_cats.dropEvent(drop_event)

        self.assertTrue(drop_event.ignored)
        self.assertFalse(drop_event.accepted)
        self.assertEqual(dialog.working_items["new"].category_id, "project")
        self.assertIn("new", dialog.working_categories["project"].item_ids)
        self.assertNotIn("new", dialog.working_categories["paths"].item_ids)
        dialog._item_drag_active = False
        dialog._populate_all(select_cat_id="project")
        dialog._accept_and_save()

        restored = ToolbarManager(
            CustomizableToolBar("Restored Main", toolbar_id="main"),
            self.config,
            secondary_toolbar=CustomizableToolBar(
                "Restored Secondary", toolbar_id="secondary"
            ),
        )
        restored.load_layout()
        self.assertEqual(restored.items["new"].category_id, "project")

    def test_customizer_drag_reorders_items_in_selected_category(self):
        dialog = ToolbarCustomizerDialog(self.manager)
        dialog.show()
        history_row = next(
            row
            for row in range(dialog.list_main_cats.count())
            if dialog.list_main_cats.item(row).data(Qt.ItemDataRole.UserRole) == "history"
        )
        dialog.list_main_cats.setCurrentRow(history_row)
        app.processEvents()

        self.assertTrue(dialog.list_items.dragEnabled())
        self.assertTrue(dialog.list_items.acceptDrops())
        self.assertEqual(
            [
                dialog.list_items.item(row).data(Qt.ItemDataRole.UserRole)
                for row in range(dialog.list_items.count())
            ],
            ["undo", "redo"],
        )
        mime_data = dialog.list_items.mimeData([dialog.list_items.item(0)])
        request = dialog.drag_request_from_mime(mime_data)
        self.assertIsNotNone(request)
        self.assertEqual(request.element_id, "undo")
        self.assertEqual(request.source_category_id, "history")

        target_rect = dialog.list_items.visualItemRect(dialog.list_items.item(1))
        drop_event = FakeDropEvent(
            mime_data,
            QPointF(target_rect.center().x(), target_rect.center().y()),
        )
        dialog.list_items.dropEvent(drop_event)

        self.assertTrue(drop_event.accepted)
        self.assertEqual(
            dialog.working_categories["history"].item_ids, ["redo", "undo"]
        )
        self.assertEqual(dialog.working_items["undo"].category_id, "history")
        self.assertEqual(dialog._get_current_category_id(), "history")
        dialog._accept_and_save()

        restored = ToolbarManager(
            CustomizableToolBar("Restored Main", toolbar_id="main"),
            self.config,
            secondary_toolbar=CustomizableToolBar(
                "Restored Secondary", toolbar_id="secondary"
            ),
        )
        restored.load_layout()
        self.assertEqual(restored.categories["history"].item_ids, ["redo", "undo"])

    def test_configurator_keeps_same_category_item_drag_distinct_from_toolbar_drag(self):
        dialog = ToolbarCustomizerDialog(self.manager)
        dialog._populate_items("history")
        list_item = dialog.list_items.item(0)
        mime_data = dialog.list_items.mimeData([list_item])

        self.assertTrue(mime_data.hasFormat("application/x-toolbar-config-item"))
        self.assertFalse(mime_data.hasFormat("application/x-toolbar-category"))
        self.assertFalse(mime_data.hasFormat("application/x-toolbar-item"))
        request = dialog.drag_request_from_mime(mime_data)
        self.assertIsNotNone(request)
        self.assertEqual(request.source_category_id, "history")
        self.assertIsInstance(dialog.list_main_cats, ToolbarCategoryListWidget)

    def test_drag_operation_validation_matrix(self):
        self.manager.set_edit_mode(True)
        project = self.manager.create_category_drag_request(
            "project", DragContext.TOOLBAR
        )
        history = self.manager.create_category_drag_request(
            "history", DragContext.TOOLBAR
        )
        project_customizer = self.manager.create_category_drag_request(
            "project", DragContext.CUSTOMIZER
        )
        button_toolbar = ToolbarDragRequest(
            element_type=DragElementType.BUTTON,
            element_id="undo",
            context=DragContext.TOOLBAR,
            allowed_operations=(
                ToolbarDragOperation.BUTTON_REORDER,
                ToolbarDragOperation.BUTTON_REASSIGN,
            ),
            source_category_id="history",
            source_toolbar_id="main",
        )
        button_customizer = ToolbarDragRequest(
            element_type=DragElementType.BUTTON,
            element_id="undo",
            context=DragContext.CUSTOMIZER,
            allowed_operations=(
                ToolbarDragOperation.BUTTON_REORDER,
                ToolbarDragOperation.BUTTON_REASSIGN,
            ),
            source_category_id="history",
            source_toolbar_id="main",
        )
        cases = (
            (project, ToolbarDragOperation.CATEGORY_REORDER, "view", "main", True),
            (project, ToolbarDragOperation.CATEGORY_MOVE, "paths", "secondary", True),
            (button_toolbar, ToolbarDragOperation.BUTTON_REASSIGN, "project", "main", False),
            (button_toolbar, ToolbarDragOperation.BUTTON_REASSIGN, "paths", "secondary", False),
            (project_customizer, ToolbarDragOperation.CATEGORY_REORDER, "view", "main", True),
            (project_customizer, ToolbarDragOperation.CATEGORY_MOVE, "paths", "secondary", True),
            (button_customizer, ToolbarDragOperation.BUTTON_REORDER, "history", "main", True),
            (button_customizer, ToolbarDragOperation.BUTTON_REASSIGN, "project", "main", True),
            (button_customizer, ToolbarDragOperation.BUTTON_REASSIGN, "paths", "secondary", True),
        )

        for request, operation, target_id, target_toolbar_id, expected in cases:
            with self.subTest(
                context=request.context,
                element=request.element_type,
                operation=operation,
                target=target_id,
            ):
                self.assertEqual(
                    self.manager.validate_drag_operation(
                        request,
                        operation,
                        target_id=target_id,
                        target_toolbar_id=target_toolbar_id,
                    ),
                    expected,
                )

        self.assertIsNotNone(history)

    def test_customizer_reorders_and_moves_categories_and_buttons(self):
        dialog = ToolbarCustomizerDialog(self.manager)
        dialog.show()
        app.processEvents()

        history_items = list(dialog.working_categories["history"].item_ids)
        self.assertTrue(
            dialog.move_working_item_to_category("undo", "history", target_index=2)
        )
        self.assertEqual(
            dialog.working_categories["history"].item_ids,
            ["redo", "undo"],
        )
        self.assertTrue(dialog.move_working_category("view", "main", 0))
        main_category_order = [
            category_id
            for category_id in dialog.working_category_order
            if dialog.working_categories[category_id].toolbar_id == "main"
        ]
        self.assertEqual(main_category_order[0], "view")
        self.assertTrue(
            dialog.move_working_item_to_category("undo", "project", target_index=1)
        )
        self.assertNotIn("undo", dialog.working_categories["history"].item_ids)
        self.assertEqual(dialog.working_categories["project"].item_ids[1], "undo")
        self.assertEqual(dialog.working_items["undo"].category_id, "project")

        self.assertTrue(dialog.move_working_category("history", "secondary", 0))
        self.assertEqual(dialog.working_categories["history"].toolbar_id, "secondary")
        self.assertEqual(dialog.working_categories["history"].item_ids, ["redo"])
        self.assertEqual(
            dialog.working_categories["project"].item_ids[1], "undo"
        )
        self.assertNotEqual(dialog.working_categories["history"].item_ids, history_items)

        dialog._accept_and_save()
        restored = ToolbarManager(
            CustomizableToolBar("Restored Main", toolbar_id="main"),
            self.config,
            secondary_toolbar=CustomizableToolBar(
                "Restored Secondary", toolbar_id="secondary"
            ),
        )
        restored.load_layout()
        self.assertEqual(restored.items["undo"].category_id, "project")
        self.assertEqual(restored.categories["history"].toolbar_id, "secondary")
        self.assertEqual(restored.categories["history"].item_ids, ["redo"])
        restored_main_order = [
            category.id
            for category in restored.get_ordered_categories()
            if category.toolbar_id == "main"
        ]
        self.assertEqual(restored_main_order[0], "view")

    def test_customizer_category_drop_between_toolbar_lists(self):
        dialog = ToolbarCustomizerDialog(self.manager)
        dialog.show()
        app.processEvents()
        mime_data = self.category_mime("history", DragContext.CUSTOMIZER)
        target = dialog.list_sec_cats.item(0)
        rect = dialog.list_sec_cats.visualItemRect(target)
        event = FakeDropEvent(
            mime_data, QPointF(rect.center().x(), rect.center().y())
        )

        dialog.list_sec_cats.dropEvent(event)

        self.assertTrue(event.accepted)
        self.assertEqual(event.drop_action, Qt.DropAction.CopyAction)
        self.assertEqual(dialog.working_categories["history"].toolbar_id, "secondary")
        self.assertEqual(dialog.working_categories["history"].item_ids, ["undo", "redo"])

    def test_drag_lifecycles_do_not_clear_each_others_state(self):
        self.manager.dragged_category_id = "history"
        self.manager.dragged_item_id = "undo"

        self.manager.on_item_drag_finished()

        self.assertIsNone(self.manager.dragged_item_id)
        self.assertEqual(self.manager.dragged_category_id, "history")

        self.manager.dragged_item_id = "undo"
        self.manager.on_category_drag_finished()

        self.assertEqual(self.manager.dragged_item_id, "undo")
        self.assertIsNone(self.manager.dragged_category_id)

    def test_drag_safety_does_not_cancel_before_drop_on_mouse_release(self):
        safety = DragSafetyManager(app)
        cancelled = []
        safety.begin("category:test", lambda: cancelled.append(True))
        release_event = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(0, 0),
            QPointF(0, 0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

        safety.eventFilter(app, release_event)

        self.assertTrue(safety.is_active("category:test"))
        self.assertEqual(cancelled, [])
        safety.finish("category:test")
        safety.deleteLater()

    def test_drag_safety_cancels_on_escape(self):
        safety = DragSafetyManager(app)
        cancelled = []
        safety.begin("item:test", lambda: cancelled.append(True))
        escape_event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )

        safety.eventFilter(app, escape_event)

        self.assertFalse(safety.is_active("item:test"))
        self.assertEqual(cancelled, [True])
        safety.deleteLater()


if __name__ == "__main__":
    unittest.main()
