import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from .ui.main_window import MainWindow
from .ui.styles import DARK_THEME_QSS
from sample_assets.generate_samples import create_sample_assets


def main():
    # Enable High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("TileSet Map Maker")
    app.setOrganizationName("TileSetMapMaker")

    # Apply modern dark theme
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()

    # Pre-populate with sample assets if none exist, for immediate out-of-the-box delight!
    samples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_assets")
    if not os.path.exists(os.path.join(samples_dir, "Terrain", "Grass", "grass_01.png")):
        create_sample_assets(samples_dir)

    # Import default sample assets into library
    window.asset_manager.import_folder(samples_dir)
    window.asset_library.refresh_categories()
    window.asset_library.refresh_assets_list()

    # Select initial grass tile for immediate painting
    grass_assets = window.asset_manager.search_assets("grass")
    if grass_assets:
        window.asset_manager.select_asset(grass_assets[0])

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
