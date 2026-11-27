import os
import sys
import tempfile
import unittest

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None


@unittest.skipIf(QApplication is None, "PyQt6 is required for toolbar scaling tests")
class TestToolbarEditModeWindowScaling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_edit_mode_preserves_exact_window_geometry_across_resolutions(self):
        from tileset_map_maker.core.config_manager import ConfigManager
        from tileset_map_maker.core.localization import get_localization
        from tileset_map_maker.ui.main_window import MainWindow

        cfg = ConfigManager(os.path.join(self.tmp_dir.name, "cfg.json"))
        win = MainWindow(config_manager=cfg)
        loc = get_localization()
        prev_lang = loc.get_language()
        try:
            # Ensure clean non-maximized window regardless of saved QSettings state
            win.showNormal()
            self.app.processEvents()
            for w, h in ((1280, 720), (1366, 768), (1920, 1080)):
                win.showNormal()
                win.resize(w, h)
                win.show()
                for _ in range(3):
                    self.app.processEvents()

                before_size = win.size()
                before_min = win.minimumSizeHint()

                # Toggle edit mode ON -> geometry & minimum width MUST NOT expand
                win.toolbar_manager.set_edit_mode(True)
                for _ in range(3):
                    self.app.processEvents()
                self.assertEqual(win.size(), before_size, f"Window resized on edit mode ON at {w}x{h}")
                self.assertLessEqual(
                    win.minimumSizeHint().width(),
                    max(before_min.width(), before_size.width()),
                    f"Minimum width grew beyond window at {w}x{h}",
                )

                # Switch language while in edit mode -> still must not expand window
                loc.set_language("pl", persist=False)
                self.app.processEvents()
                self.assertEqual(win.size(), before_size)
                loc.set_language("en", persist=False)
                self.app.processEvents()
                self.assertEqual(win.size(), before_size)

                # Manual resize during edit mode must be preserved when exiting edit mode
                resized_w, resized_h = max(1100, before_size.width() - 60), max(640, before_size.height() - 40)
                win.resize(resized_w, resized_h)
                for _ in range(3):
                    self.app.processEvents()
                manual_size = win.size()

                win.toolbar_manager.set_edit_mode(False)
                for _ in range(3):
                    self.app.processEvents()
                self.assertEqual(win.size(), manual_size)

            # Banner minimumSizeHint must always stay 0 width
            self.assertEqual(win.toolbar_edit_banner.minimumSizeHint().width(), 0)
            # Toolbar height must stay capped even with all items visible
            win.toolbar_manager.show_all_items()
            self.app.processEvents()
            self.assertLessEqual(win.toolbar.height(), win.toolbar.MAX_FLOW_HEIGHT + 24)
        finally:
            loc.set_language(prev_lang, persist=False)
            win.close()


if __name__ == "__main__":
    unittest.main()
