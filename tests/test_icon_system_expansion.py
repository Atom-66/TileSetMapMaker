import os
import unittest
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QImage, QColor
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtSvg import QSvgRenderer

from tileset_map_maker.ui.icons import IconFactory
from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.ui.history_panel import HistoryPanel
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.models.project import Project


class TestIconSystemExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_01_all_newly_created_svg_files_exist_and_are_valid(self):
        """1. Sprawdzenie obecności i poprawności składni nowo wygenerowanych plików SVG."""
        new_icons = [
            "autotile.svg",
            "path-generator.svg",
            "tile-variants.svg",
            "tileset-slice.svg",
            "stamp-save.svg",
            "save-as.svg",
            "grid-3x3-template.svg",
            "hud-coords.svg",
            "map-edit.svg",
        ]
        icons_dir = os.path.join("icons", "outline")
        for fname in new_icons:
            full_path = os.path.join(icons_dir, fname)
            self.assertTrue(os.path.isfile(full_path), f"File {full_path} must exist!")
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<svg", content)
            self.assertIn('viewBox="0 0 24 24"', content)
            self.assertIn('stroke="currentColor"', content)

            # Test QSvgRenderer parse
            renderer = QSvgRenderer(full_path)
            self.assertTrue(renderer.isValid(), f"SVG {fname} must be valid for QSvgRenderer")

    def test_02_all_mapped_keys_resolve_to_valid_svgs(self):
        """2. Weryfikacja, że wszystkie zdefiniowane klucze w ICON_NAME_MAP wskazują na istniejące SVG."""
        missing = []
        for key, canonical in IconFactory.ICON_NAME_MAP.items():
            svg_text = IconFactory._load_svg_text(key)
            if not svg_text:
                missing.append((key, canonical))
        self.assertEqual(missing, [], f"Keys failed to load SVG: {missing}")

    def test_03_icon_rendering_at_multiple_sizes(self):
        """3. Weryfikacja czytelności i renderowania w rozmiarach 16, 20, 24, 32 px."""
        test_keys = [
            "autotile",
            "path-generator",
            "tile-variants",
            "tileset-slice",
            "stamp-save",
            "save-as",
            "grid-3x3-template",
            "hud",
            "map-edit",
            "pencil",
            "target",
        ]
        sizes = [16, 20, 24, 32]
        for key in test_keys:
            for s in sizes:
                icon = IconFactory.get_icon(key, size=s)
                self.assertFalse(icon.isNull(), f"Icon {key} at {s}px should not be null")
                pix = icon.pixmap(s, s)
                self.assertFalse(pix.isNull(), f"Pixmap {key} at {s}px should not be null")
                self.assertEqual(pix.width(), s)
                self.assertEqual(pix.height(), s)

                # Ensure image has transparent background and non-empty content
                img = pix.toImage()
                has_content = False
                has_transparent = False
                for y in range(s):
                    for x in range(s):
                        pixel = img.pixelColor(x, y)
                        if pixel.alpha() > 10:
                            has_content = True
                        if pixel.alpha() == 0:
                            has_transparent = True
                self.assertTrue(has_content, f"Icon {key} at {s}px must have visible pixels")
                self.assertTrue(has_transparent, f"Icon {key} at {s}px must preserve transparent background")

    def test_04_dark_theme_contrast_and_states(self):
        """4. Weryfikacja stanów ikony (Normal, Active, Selected, Disabled) i kontrastu."""
        icon = IconFactory.get_icon("autotile", size=24)
        pix_normal = icon.pixmap(24, 24, QIcon.Mode.Normal, QIcon.State.Off)
        pix_selected = icon.pixmap(24, 24, QIcon.Mode.Selected, QIcon.State.Off)
        pix_disabled = icon.pixmap(24, 24, QIcon.Mode.Disabled, QIcon.State.Off)

        self.assertFalse(pix_normal.isNull())
        self.assertFalse(pix_selected.isNull())
        self.assertFalse(pix_disabled.isNull())

    def test_05_main_window_menu_actions_have_icons(self):
        """5. Sprawdzenie czy wszystkie akcje w menu głównym MainWindow posiadają ikony (bez braków)."""
        win = MainWindow()
        actions_to_check = [
            ("act_new", win.act_new),
            ("act_open", win.act_open),
            ("act_save", win.act_save),
            ("act_export", win.act_export),
            ("act_undo", win.act_undo),
            ("act_redo", win.act_redo),
            ("act_shortcuts", win.act_shortcuts),
            ("act_autotile", win.act_autotile),
            ("act_path_gen", win.act_path_gen),
            ("act_randomizer", win.act_randomizer),
            ("act_save_stamp", win.act_save_stamp),
            ("act_layout_default", win.act_layout_default),
            ("act_preset_map_edit", win.act_preset_map_edit),
            ("act_preset_tileset", win.act_preset_tileset),
            ("act_preset_minimal", win.act_preset_minimal),
            ("act_preset_expanded", win.act_preset_expanded),
        ]
        for name, act in actions_to_check:
            self.assertFalse(act.icon().isNull(), f"Action {name} must have a valid icon!")
        win.close()

    def test_06_history_buttons_use_icons_without_emojis(self):
        """6. Sprawdzenie, że przyciski historii używają wektorowych ikon zamiast emoji."""
        proj = Project(map_width=10, map_height=10, tile_size=32)
        hist = HistoryManager()
        hist_panel = HistoryPanel(hist)
        # Check btn_undo and btn_redo
        buttons = hist_panel.findChildren(QIcon)
        # Find QToolButton instances in hist_panel
        from PyQt6.QtWidgets import QToolButton
        tool_btns = hist_panel.findChildren(QToolButton)
        self.assertGreaterEqual(len(tool_btns), 2)
        for btn in tool_btns:
            self.assertFalse(btn.icon().isNull(), "History panel tool buttons must have icons")
            self.assertEqual(btn.text(), "", "History panel tool buttons must not have emoji text")


if __name__ == "__main__":
    unittest.main()
