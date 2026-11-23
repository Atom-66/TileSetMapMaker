import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSettings

from .ui.main_window import MainWindow
from .ui.styles import apply_application_theme


def main():
    # Enable High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("TileSet Map Maker")
    app.setOrganizationName("TileSetMapMaker")

    theme_index = QSettings("TileSetMapMaker", "TileSetMapMaker").value(
        "theme_idx", 0, type=int
    )
    apply_application_theme(app, theme_index)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
