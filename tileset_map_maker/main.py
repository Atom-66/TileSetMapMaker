import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from .ui.main_window import MainWindow
from .ui.styles import DARK_THEME_QSS


def main():
    # Enable High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("TileSet Map Maker")
    app.setOrganizationName("TileSetMapMaker")

    # Apply modern dark theme
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
