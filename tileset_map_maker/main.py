import sys
import os
from typing import Sequence, Optional
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSettings

from .ui.main_window import MainWindow
from .ui.styles import apply_application_theme


def main(argv: Optional[Sequence[str]] = None) -> int:
    # Enable High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    args = list(argv if argv is not None else sys.argv[1:])
    smoke_test = "--smoke-test" in args
    qt_args = [sys.argv[0]] + [arg for arg in args if arg != "--smoke-test"]
    app = QApplication(qt_args)
    app.setApplicationName("TileSet Map Maker")
    app.setOrganizationName("TileSetMapMaker")

    theme_index = QSettings("TileSetMapMaker", "TileSetMapMaker").value(
        "theme_idx", 0, type=int
    )
    apply_application_theme(app, theme_index)

    window = MainWindow()
    window.show()
    if smoke_test:
        app.processEvents()
        if window.width() <= 0 or window.height() <= 0:
            window.close()
            return 1
        window.close()
        app.processEvents()
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
