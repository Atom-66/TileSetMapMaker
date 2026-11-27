from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QToolButton,
    QHBoxLayout,
    QWidget,
)

from ..core.localization import get_localization, tr


class NotificationBanner(QWidget):
    """Non-modal notification with explicit diagnostics affordance."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setVisible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)
        self.label = QLabel()
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        self.details = QToolButton()
        self.details.setText(tr("notify.details"))
        self.details.setVisible(False)
        layout.addWidget(self.details)
        close = QToolButton()
        close.setText("×")
        close.clicked.connect(self.hide)
        layout.addWidget(close)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._details_callback = None
        get_localization().languageChanged.connect(self._apply_language)

    def _apply_language(self, _language: str = "") -> None:
        self.details.setText(tr("notify.details"))

    def show_message(
        self, message: str, severity: str = "info", details=None
    ) -> None:
        palette = {
            "info": ("#172554", "#93c5fd"),
            "success": ("#052e16", "#86efac"),
            "warning": ("#422006", "#fde68a"),
            "error": ("#450a0a", "#fca5a5"),
        }
        background, foreground = palette.get(severity, palette["info"])
        self.setStyleSheet(
            f"background:{background}; color:{foreground}; "
            "border:1px solid rgba(255,255,255,0.12); border-radius:5px;"
        )
        self.label.setText(message)
        self.details.setVisible(details is not None)
        if self._details_callback is not None:
            try:
                self.details.clicked.disconnect(self._details_callback)
            except TypeError:
                pass
        self._details_callback = details
        if details is not None:
            self.details.clicked.connect(details)
        self.show()
