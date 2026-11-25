import unittest
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QPainter, QPixmap

from tileset_map_maker.ui.widgets.switch_toggle import SwitchToggle
from tileset_map_maker.models.brush_preset import BrushSettings
from tileset_map_maker.models.project import Project
from tileset_map_maker.ui.brush_options_bar import BrushOptionsBar
from tileset_map_maker.ui.dialogs.preferences_dialog import PreferencesDialog
from tileset_map_maker.ui.dialogs.tile_randomizer_dialog import TileRandomizerDialog
from tileset_map_maker.ui.dialogs.export_dialog import ExportDialog
from tileset_map_maker.ui.dialogs.map_settings_dialog import MapSettingsDialog
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autotile_engine import AutoTileEngine


class TestSwitchToggle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.toggle = SwitchToggle("Test Toggle", checked=False)

    def test_01_initial_state_and_properties(self):
        self.assertFalse(self.toggle.isChecked())
        self.assertEqual(self.toggle.text(), "Test Toggle")
        self.assertEqual(self.toggle.thumb_position, 0.0)

        t_on = SwitchToggle("Active", checked=True)
        self.assertTrue(t_on.isChecked())
        self.assertEqual(t_on.thumb_position, 1.0)

    def test_02_set_checked_and_signals(self):
        received = []
        self.toggle.toggled.connect(lambda val: received.append(val))

        self.toggle.setChecked(True)
        self.assertTrue(self.toggle.isChecked())
        self.assertEqual(received, [True])

        # Setting same value should not emit duplicate signal
        self.toggle.setChecked(True)
        self.assertEqual(received, [True])

        self.toggle.setChecked(False)
        self.assertFalse(self.toggle.isChecked())
        self.assertEqual(received, [True, False])

    def test_03_toggle_method(self):
        self.assertFalse(self.toggle.isChecked())
        self.toggle.toggle()
        self.assertTrue(self.toggle.isChecked())
        self.toggle.toggle()
        self.assertFalse(self.toggle.isChecked())

    def test_04_keyboard_accessibility(self):
        received = []
        self.toggle.toggled.connect(lambda val: received.append(val))

        # Space key toggles
        event_space = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
        self.toggle.keyPressEvent(event_space)
        self.assertTrue(self.toggle.isChecked())
        self.assertEqual(received, [True])

        # Enter key toggles
        event_enter = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        self.toggle.keyPressEvent(event_enter)
        self.assertFalse(self.toggle.isChecked())
        self.assertEqual(received, [True, False])

    def test_05_disabled_state_behavior(self):
        self.toggle.setEnabled(False)
        self.assertFalse(self.toggle.isEnabled())

        # Clicking or pressing space while disabled should NOT change state
        event_space = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
        self.toggle.keyPressEvent(event_space)
        self.assertFalse(self.toggle.isChecked())

    def test_06_rendering_paint_event(self):
        # Verify paintEvent executes cleanly for OFF, ON, hovered, and disabled
        pm = QPixmap(100, 40)
        painter = QPainter(pm)
        
        # OFF
        self.toggle._pill_widget.render(painter)
        
        # ON
        self.toggle.setChecked(True)
        self.toggle._pill_widget.render(painter)

        # Hovered
        self.toggle._hovered = True
        self.toggle._pill_widget.render(painter)

        # Disabled
        self.toggle.setEnabled(False)
        self.toggle._pill_widget.render(painter)
        
        painter.end()
        self.assertFalse(pm.isNull())

    def test_07_brush_options_bar_integration(self):
        bs = BrushSettings()
        engine = AutoTileEngine()
        mgr = AssetManager()
        bar = BrushOptionsBar(brush_settings=bs, autotile_engine=engine, asset_manager=mgr)

        # 1. Variants toggle
        self.assertIsInstance(bar.chk_variants, SwitchToggle)
        self.assertFalse(bar.chk_variants.isChecked())
        self.assertFalse(bs.random_variant)
        bar.chk_variants.setChecked(True)
        self.assertTrue(bs.random_variant)

        # 3. Avoid adjacent toggle
        self.assertIsInstance(bar.chk_avoid, SwitchToggle)
        self.assertFalse(bar.chk_avoid.isChecked())
        self.assertFalse(bs.avoid_adjacent)
        bar.chk_avoid.setChecked(True)
        self.assertTrue(bs.avoid_adjacent)

        # 4. Rotation & Flip toggles
        self.assertIsInstance(bar.chk_rot, SwitchToggle)
        self.assertIsInstance(bar.chk_flip, SwitchToggle)
        bar.chk_rot.setChecked(True)
        self.assertTrue(bs.random_rotation)
        bar.chk_flip.setChecked(True)
        self.assertTrue(bs.random_flip_x)

    def test_08_dialogs_switch_toggle_integration(self):
        proj = Project(name="TestProj", map_width=10, map_height=10)
        mgr = AssetManager()
        bs = BrushSettings()

        # MapSettingsDialog
        dlg_map = MapSettingsDialog(proj)
        self.assertIsInstance(dlg_map.chk_transparent, SwitchToggle)
        dlg_map.chk_transparent.setChecked(True)
        self.assertTrue(dlg_map.chk_transparent.isChecked())
        dlg_map.close()

        from tileset_map_maker.core.render_engine import RenderEngine
        # ExportDialog
        dlg_exp = ExportDialog(proj, RenderEngine(mgr))
        self.assertIsInstance(dlg_exp.chk_transparent, SwitchToggle)
        self.assertTrue(dlg_exp.chk_transparent.isChecked())
        dlg_exp.close()

        # PreferencesDialog
        dlg_pref = PreferencesDialog()
        self.assertIsInstance(dlg_pref.chk_show_grid, SwitchToggle)
        self.assertIsInstance(dlg_pref.chk_show_hud, SwitchToggle)
        self.assertIsInstance(dlg_pref.chk_checkerboard, SwitchToggle)
        self.assertIsInstance(dlg_pref.chk_snap_default, SwitchToggle)
        self.assertIsInstance(dlg_pref.chk_imp_skip_single, SwitchToggle)
        dlg_pref.close()

        # TileRandomizerDialog
        dlg_rand = TileRandomizerDialog(brush_settings=bs, asset_manager=mgr, project=proj)
        self.assertIsInstance(dlg_rand.chk_enable, SwitchToggle)
        self.assertIsInstance(dlg_rand.chk_avoid, SwitchToggle)
        self.assertIsInstance(dlg_rand.chk_seed, SwitchToggle)
        dlg_rand.close()


if __name__ == "__main__":
    unittest.main()
