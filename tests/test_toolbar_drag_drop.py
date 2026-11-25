import os
import tempfile
import unittest
from PyQt6.QtCore import Qt, QPoint, QPointF, QEvent
from PyQt6.QtGui import QAction, QMouseEvent
from PyQt6.QtWidgets import QApplication, QWidget

from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.ui.toolbar_manager import (
    ToolbarManager,
    CustomizableToolBar,
    ToolbarItemDef,
    ToolbarCategoryDef,
    ToolbarEditModeBanner,
    ToolbarItemDragFilter,
    CategoryGripWidget,
)
from tileset_map_maker.ui.main_window import MainWindow

app = QApplication.instance()
if app is None:
    app = QApplication([])


class TestToolbarDragDrop(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.cfg_path = os.path.join(self.tmp_dir.name, "test_drag_drop_config.json")
        self.config_manager = ConfigManager(custom_config_path=self.cfg_path)

        self.main_toolbar = CustomizableToolBar("Main", toolbar_id="main")
        self.sec_toolbar = CustomizableToolBar("Secondary", toolbar_id="secondary")
        self.manager = ToolbarManager(self.main_toolbar, self.config_manager, secondary_toolbar=self.sec_toolbar)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_move_item_last_to_first(self):
        """1. Przeniesienie ostatniego przycisku na pierwszą pozycję."""
        # W kategorii project domyślnie są: ["new", "open", "save", "export"]
        project_cat = self.manager.categories["project"]
        self.assertEqual(project_cat.item_ids, ["new", "open", "save", "export"])

        # Przenosimy 'export' (ostatni) na pozycję 0 (początek)
        self.manager.move_item("export", "project", 0)

        self.assertEqual(project_cat.item_ids, ["export", "new", "open", "save"])
        self.assertEqual(self.manager.items["export"].category_id, "project")

    def test_02_move_item_insert_between_two_existing(self):
        """2. Wstawienie przycisku pomiędzy dwa istniejące przyciski (np. A, B, C, D -> przenieś D między A i B -> A, D, B, C)."""
        project_cat = self.manager.categories["project"]
        self.assertEqual(project_cat.item_ids, ["new", "open", "save", "export"])

        # Chwytamy przycisk 'export' (D) i wstawiamy go pomiędzy 'new' (A) i 'open' (B), czyli pod indeks 1
        self.manager.move_item("export", "project", 1)

        self.assertEqual(project_cat.item_ids, ["new", "export", "open", "save"])

    def test_03_move_item_first_to_last(self):
        """3. Przeniesienie pierwszego przycisku na koniec."""
        project_cat = self.manager.categories["project"]
        self.assertEqual(project_cat.item_ids, ["new", "open", "save", "export"])

        # Przenosimy 'new' (pierwszy) na koniec (indeks 4)
        self.manager.move_item("new", "project", 4)

        self.assertEqual(project_cat.item_ids, ["open", "save", "export", "new"])

    def test_04_move_items_multiple_in_sequence(self):
        """4. Przenoszenie kilku różnych przycisków pod rząd."""
        project_cat = self.manager.categories["project"]
        self.assertEqual(project_cat.item_ids, ["new", "open", "save", "export"])

        # Krok 1: Przenieś 'save' na początek -> save, new, open, export
        self.manager.move_item("save", "project", 0)
        self.assertEqual(project_cat.item_ids, ["save", "new", "open", "export"])

        # Krok 2: Przenieś 'open' między 'save' i 'new' -> save, open, new, export
        self.manager.move_item("open", "project", 1)
        self.assertEqual(project_cat.item_ids, ["save", "open", "new", "export"])

        # Krok 3: Przenieś 'save' na koniec -> open, new, export, save
        self.manager.move_item("save", "project", 4)
        self.assertEqual(project_cat.item_ids, ["open", "new", "export", "save"])

    def test_05_move_item_between_categories_and_toolbars(self):
        """5. Przenoszenie przycisku pomiędzy kategoriami i pomiędzy paskami."""
        proj_cat = self.manager.categories["project"]
        hist_cat = self.manager.categories["history"]
        paths_cat = self.manager.categories["paths"]

        self.assertIn("undo", hist_cat.item_ids)
        self.assertEqual(hist_cat.toolbar_id, "main")
        self.assertEqual(paths_cat.toolbar_id, "secondary")

        # 5a. Przenieś 'undo' z kategorii 'history' do kategorii 'project' pod indeks 1
        self.manager.move_item("undo", "project", 1)
        self.assertNotIn("undo", hist_cat.item_ids)
        self.assertEqual(proj_cat.item_ids, ["new", "undo", "open", "save", "export"])
        self.assertEqual(self.manager.items["undo"].category_id, "project")

        # 5b. Przenieś 'undo' z 'project' (pasek główny) do 'paths' (pasek dodatkowy)
        self.manager.move_item("undo", "paths", 0)
        self.assertNotIn("undo", proj_cat.item_ids)
        self.assertIn("undo", paths_cat.item_ids)
        self.assertEqual(paths_cat.item_ids[0], "undo")
        self.assertEqual(self.manager.items["undo"].category_id, "paths")

    def test_06_move_category_order_and_toolbar(self):
        """6. Zmiana kolejności kategorii oraz przenoszenie kategorii na inny pasek."""
        # Początkowa kolejność kategorii: project, history, view, brush, autotile, ...
        self.assertEqual(self.manager.category_order[:3], ["project", "history", "view"])
        self.assertEqual(self.manager.categories["history"].toolbar_id, "main")

        # 6a. Przenieś kategorię 'history' przed 'project' (indeks 0)
        self.manager.move_category("history", 0)
        self.assertEqual(self.manager.category_order[:3], ["history", "project", "view"])

        # 6b. Przenieś kategorię 'history' na pasek dodatkowy (secondary) pod indeks 5
        self.manager.move_category("history", 5, target_toolbar_id="secondary")
        self.assertEqual(self.manager.categories["history"].toolbar_id, "secondary")

    def test_07_drag_cancel_no_side_effects(self):
        """7. Anulowanie przeciągania nie powoduje zmian w kolejności ani uszkodzeń."""
        proj_cat = self.manager.categories["project"]
        initial_order = list(proj_cat.item_ids)

        w = QWidget()
        self.manager.on_item_drag_started("new", w)
        self.assertEqual(self.manager.dragged_item_id, "new")

        # Użytkownik anuluje przeciąganie (np. Esc lub upuszczenie poza dozwolonym obszarem)
        self.manager.on_drag_finished()
        self.assertIsNone(self.manager.dragged_item_id)
        self.assertEqual(proj_cat.item_ids, initial_order)

        # Idempotent repeated cleanup must be safe.
        self.manager.on_drag_finished()
        self.manager.on_drag_finished()

    def test_08_save_and_restore_after_restart(self):
        """8. Zapisanie układu po zmianach i odtworzenie go po ponownym uruchomieniu."""
        # Dokonaj zmian
        self.manager.move_item("export", "project", 0)
        self.manager.move_item("save", "history", 1)
        self.manager.move_category("system", 0, target_toolbar_id="secondary")

        # Symuluj restart aplikacji: utwórz nowy manager z tym samym plikiem konfiguracyjnym
        new_main_tb = CustomizableToolBar("Main2", toolbar_id="main")
        new_sec_tb = CustomizableToolBar("Secondary2", toolbar_id="secondary")
        new_manager = ToolbarManager(new_main_tb, self.config_manager, secondary_toolbar=new_sec_tb)
        new_manager.load_layout()

        # Sprawdź odtworzenie stanu
        self.assertEqual(new_manager.categories["project"].item_ids[0], "export")
        self.assertIn("save", new_manager.categories["history"].item_ids)
        self.assertEqual(new_manager.categories["system"].toolbar_id, "secondary")
        self.assertEqual(new_manager.category_order[0], "system")

    def test_09_normal_clicking_vs_edit_mode_safety(self):
        """9. Normalne klikanie przycisków poza trybem personalizacji vs ochrona w trybie edycji."""
        act_test = QAction("Test Action", self.main_toolbar)
        clicks = []
        act_test.triggered.connect(lambda: clicks.append(True))
        self.manager.register_item("test_action", "Test", "project", action=act_test)
        self.manager.build_toolbar()

        btn = self.manager.items["test_action"].button
        self.assertIsNotNone(btn)

        # 9a. Poza trybem personalizacji: kliknięcie normalnie wywołuje akcję
        self.assertFalse(self.manager.is_edit_mode)
        btn.click()
        self.assertEqual(clicks, [True])

        # 9b. W trybie personalizacji: akcja jest chroniona, kliknięcie nie wywołuje akcji
        self.manager.set_edit_mode(True)
        self.assertTrue(self.manager.is_edit_mode)

        filter_obj = self.manager._item_drag_filters["test_action"]
        press_event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(5.0, 5.0),
            QPointF(5.0, 5.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        release_event = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(5.0, 5.0),
            QPointF(5.0, 5.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

        # Press remains available for Qt's mouse tracking; release is consumed to suppress activation.
        self.assertFalse(filter_obj.eventFilter(btn, press_event))
        self.assertTrue(filter_obj.eventFilter(btn, release_event))
        self.assertEqual(clicks, [True], "W trybie edycji liczba wywołań akcji nie powinna wzrosnąć")

        # 9c. Wyłączenie trybu edycji
        self.manager.set_edit_mode(False)
        self.assertFalse(self.manager.is_edit_mode)
        btn.click()
        self.assertEqual(clicks, [True, True], "Po wyjściu z trybu edycji akcja znów działa natychmiast")

    def test_10_drop_slot_calculation_and_visual_indicator(self):
        """10. Weryfikacja obliczania pozycji slotu (calculate_item_drop_slot) i wskaźnika wstawienia."""
        self.main_toolbar.set_manager(self.manager)
        self.manager.set_edit_mode(True)
        self.manager.build_toolbar()

        # Symuluj przeciąganie nad paskiem głównym
        drop_pos = QPoint(15, 12)
        slot_x, cat_id, item_idx = self.main_toolbar.calculate_item_drop_slot(drop_pos, "export")
        self.assertIsInstance(slot_x, int)
        self.assertIn(cat_id, self.manager.categories)
        self.assertGreaterEqual(item_idx, 0)

        # Ustaw wskaźnik upuszczenia i sprawdź czy Toolbar go rejestruje
        self.main_toolbar.drop_indicator_x = slot_x
        self.assertEqual(self.main_toolbar.drop_indicator_x, slot_x)

    def test_11_mainwindow_edit_mode_and_escape_key(self):
        """11. Weryfikacja aktywacji trybu edycji i klawisza Esc w MainWindow."""
        win = MainWindow()
        win.show()
        tm = win.toolbar_manager

        # Początkowo tryb edycji wyłączony, baner ukryty
        self.assertFalse(tm.is_edit_mode)
        self.assertTrue(win.toolbar_edit_banner.isHidden())

        # Włącz tryb edycji
        tm.set_edit_mode(True)
        self.assertTrue(tm.is_edit_mode)
        self.assertFalse(win.toolbar_edit_banner.isHidden())
        self.assertTrue(win.act_toolbar_edit.isChecked())

        # Wciśnięcie Esc wyłącza tryb edycji
        from PyQt6.QtGui import QKeyEvent
        esc_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        win.keyPressEvent(esc_event)

        self.assertFalse(tm.is_edit_mode)
        self.assertTrue(win.toolbar_edit_banner.isHidden())
        self.assertFalse(win.act_toolbar_edit.isChecked())

        win.close()
