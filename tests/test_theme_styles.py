import unittest

from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from tileset_map_maker.core.localization import tr
from tileset_map_maker.ui.icons import IconFactory
from tileset_map_maker.ui.widgets.switch_toggle import ToolbarToggleButton
from tileset_map_maker.ui.styles import (
    DARK_THEME_QSS,
    FOREST_ADVENTURE_THEME_QSS,
    HIGH_CONTRAST_THEME_QSS,
    LIGHT_THEME_QSS,
    apply_application_theme,
    get_canvas_theme_colors,
    get_icon_palette,
    get_theme_stylesheet,
    _recolor_inline_stylesheet,
)
from tileset_map_maker.ui.dialogs.preferences_dialog import PreferencesDialog


class TestThemeStyles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_existing_default_remains_dark(self):
        self.assertEqual(get_theme_stylesheet(0), DARK_THEME_QSS)

    def test_forest_adventure_uses_game_inspired_palette(self):
        self.assertEqual(get_theme_stylesheet(3), FOREST_ADVENTURE_THEME_QSS)
        self.assertIn("#172b22", FOREST_ADVENTURE_THEME_QSS)
        self.assertIn("#60452d", FOREST_ADVENTURE_THEME_QSS)
        self.assertIn("#b69a57", FOREST_ADVENTURE_THEME_QSS)

    def test_studio_light_has_light_surfaces_and_dark_text(self):
        stylesheet = get_theme_stylesheet(1)
        self.assertEqual(stylesheet, LIGHT_THEME_QSS)
        self.assertIn("background-color: #f8fafc;", stylesheet)
        self.assertIn("color: #1e293b;", stylesheet)
        self.assertIn("border: 1px solid #64748b;", stylesheet)
        self.assertIn("QToolButton:checked", stylesheet)
        self.assertNotEqual(stylesheet, DARK_THEME_QSS)

    def test_studio_light_dock_controls_have_visible_hover_states(self):
        stylesheet = get_theme_stylesheet(1)
        self.assertIn("QDockWidget::close-button, QDockWidget::float-button", stylesheet)
        self.assertIn("QDockWidget::close-button:hover, QDockWidget::float-button:hover", stylesheet)
        self.assertIn("background-color: #cbd5e1;", stylesheet)
        self.assertIn("QDockWidget::close-button {\n    right: 4px;", stylesheet)
        self.assertIn("QDockWidget::float-button {\n    right: 22px;", stylesheet)

    def test_studio_light_toolbar_toggles_keep_text_readable_in_each_state(self):
        app = QApplication.instance()
        old_theme = app.property("theme_index")
        old_stylesheet = app.styleSheet()
        apply_application_theme(app, 0)
        toggle = ToolbarToggleButton("Randomizer")
        toggle.resize(140, 26)
        toggle.show()
        app.processEvents()
        apply_application_theme(app, 1)
        app.processEvents()

        self.assertIn("background-color: #e2e8f0;", toggle.styleSheet())
        self.assertIn("color: #1e293b;", toggle.styleSheet())
        rendered_background = toggle.grab().toImage().pixelColor(130, 13).name()
        self.assertIn(rendered_background, {"#e2e8f0", "#cbd5e1"})

        toggle.setChecked(True)
        app.processEvents()
        self.assertIn("background-color: #1d4ed8;", toggle.styleSheet())
        self.assertIn("color: #ffffff;", toggle.styleSheet())

        toggle.setEnabled(False)
        app.processEvents()
        self.assertIn("background-color: #ffffff;", toggle.styleSheet())
        self.assertIn("color: #64748b;", toggle.styleSheet())

        toggle.close()
        toggle.deleteLater()
        if old_theme is None:
            app.setProperty("theme_index", 0)
            app.setStyleSheet(old_stylesheet)
        else:
            apply_application_theme(app, int(old_theme))

    def test_high_contrast_uses_black_surfaces_and_bright_accents(self):
        stylesheet = get_theme_stylesheet(2)
        self.assertEqual(stylesheet, HIGH_CONTRAST_THEME_QSS)
        self.assertIn("background-color: #000000;", stylesheet)
        self.assertIn("color: #ffffff;", stylesheet)
        self.assertIn("#00e5ff", stylesheet)
        self.assertNotEqual(stylesheet, DARK_THEME_QSS)

    def test_unknown_theme_index_falls_back_to_dark(self):
        self.assertEqual(get_theme_stylesheet(99), DARK_THEME_QSS)

    def test_map_canvas_uses_theme_specific_backgrounds(self):
        backgrounds = {
            index: get_canvas_theme_colors(index)["background"]
            for index in range(4)
        }
        self.assertEqual(len(set(backgrounds.values())), 4)
        self.assertEqual(backgrounds[1], "#dce1e8")
        self.assertEqual(backgrounds[2], "#000000")
        self.assertEqual(backgrounds[3], "#203326")

    def test_studio_light_icon_states_use_high_contrast_colors(self):
        app = QApplication.instance()
        old_theme = app.property("theme_index")
        app.setProperty("theme_index", 1)
        icon = IconFactory.get_icon("brush", size=24)

        normal = icon.pixmap(QSize(24, 24), QIcon.Mode.Normal, QIcon.State.Off).toImage()
        selected = icon.pixmap(QSize(24, 24), QIcon.Mode.Selected, QIcon.State.Off).toImage()
        disabled = icon.pixmap(QSize(24, 24), QIcon.Mode.Disabled, QIcon.State.Off).toImage()

        def has_opaque_color(image, color):
            return any(
                image.pixelColor(x, y).alpha() >= 240
                and image.pixelColor(x, y).name() == color
                for y in range(image.height())
                for x in range(image.width())
            )

        self.assertTrue(has_opaque_color(normal, "#1e293b"))
        self.assertTrue(has_opaque_color(selected, "#ffffff"))
        self.assertTrue(has_opaque_color(disabled, "#64748b"))
        if old_theme is None:
            app.setProperty("theme_index", 0)
        else:
            app.setProperty("theme_index", old_theme)

    def test_icon_palette_changes_with_theme_and_state(self):
        self.assertEqual(
            get_icon_palette(1, QIcon.Mode.Normal, QIcon.State.Off),
            ("#1e293b", "#475569"),
        )
        self.assertEqual(
            get_icon_palette(1, QIcon.Mode.Selected, QIcon.State.Off),
            ("#ffffff", "#1d4ed8"),
        )

    def test_existing_icons_update_when_switching_to_studio_light(self):
        app = QApplication.instance()
        old_theme = app.property("theme_index")
        old_stylesheet = app.styleSheet()
        app.setProperty("theme_index", 0)
        widget = QWidget()
        button = QPushButton(widget)
        button.setIcon(IconFactory.get_icon("brush", 24))

        apply_application_theme(app, 1)
        image = button.icon().pixmap(
            QSize(24, 24), QIcon.Mode.Normal, QIcon.State.Off
        ).toImage()
        icon_colors = {
            image.pixelColor(x, y).name()
            for y in range(image.height())
            for x in range(image.width())
            if image.pixelColor(x, y).alpha() >= 240
        }
        self.assertIn("#1e293b", icon_colors)

        widget.deleteLater()
        if old_theme is None:
            app.setProperty("theme_index", 0)
            app.setStyleSheet(old_stylesheet)
        else:
            apply_application_theme(app, int(old_theme))

    def test_studio_light_recolors_toolbar_category_background_and_labels(self):
        dark_toolbar_style = """
            ToolbarCategoryWidget { background: #1d1e24; border: 1px solid #34363e; }
            QLabel { color: #b8bac2; }
            QLabel:hover { background-color: #30323a; border: 1px solid #4b4d58; }
        """
        light_style = _recolor_inline_stylesheet(dark_toolbar_style, 1)
        self.assertIn("background: #e2e8f0;", light_style)
        self.assertIn("border: 1px solid #64748b;", light_style)
        self.assertIn("color: #334155;", light_style)
        self.assertIn("background-color: #cbd5e1;", light_style)

    def test_theme_recolors_custom_button_styles_and_restores_them(self):
        app = QApplication.instance()
        widget = QWidget()
        button = QPushButton(widget)
        original = """
            QToolButton { background-color: #27272a; color: #e4e4e7;
                          border: 1px solid #3f3f46; }
        """
        button.setStyleSheet(original)
        old_stylesheet = app.styleSheet()
        old_theme = app.property("theme_index")
        apply_application_theme(app, 1)
        self.assertIn("#e2e8f0", button.styleSheet())
        self.assertIn("#1e293b", button.styleSheet())
        self.assertIn("#64748b", button.styleSheet())
        apply_application_theme(app, 3)
        self.assertIn("#294936", button.styleSheet())
        self.assertIn("#eee2c2", button.styleSheet())
        apply_application_theme(app, 0)
        self.assertEqual(button.styleSheet(), original)
        if old_theme is not None:
            apply_application_theme(app, int(old_theme))
        else:
            app.setStyleSheet(old_stylesheet)
        widget.deleteLater()

    def test_preferences_offer_the_forest_theme(self):
        dialog = PreferencesDialog()
        self.assertEqual(dialog.combo_theme.count(), 4)
        self.assertEqual(dialog.combo_theme.itemText(3), tr("theme.forest"))
        dialog.close()


if __name__ == "__main__":
    unittest.main()
