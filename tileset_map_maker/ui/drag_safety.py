import logging
from typing import Callable, Dict, Optional

from PyQt6.QtCore import QObject, QEvent
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QWidget


logger = logging.getLogger("DragSafety")


class DragSafetyManager(QObject):
    """Cancels active Qt drags when the application loses focus or Escape is pressed."""

    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app
        self._operations: Dict[str, Callable[[], None]] = {}
        app.installEventFilter(self)
        app.focusChanged.connect(self._on_focus_changed)

    def begin(self, operation_id: str, cancel_callback: Callable[[], None]) -> bool:
        if operation_id in self._operations:
            logger.debug("Ignoring duplicate drag operation %s", operation_id)
            return False
        self._operations[operation_id] = cancel_callback
        logger.debug("Drag operation started: %s", operation_id)
        return True

    def finish(self, operation_id: str) -> None:
        if operation_id in self._operations:
            del self._operations[operation_id]
            logger.debug("Drag operation finished: %s", operation_id)

    def cancel(self, operation_id: str) -> None:
        callback = self._operations.pop(operation_id, None)
        if callback is None:
            return
        try:
            callback()
        except Exception:
            logger.exception("Error while cancelling drag operation %s", operation_id)
        finally:
            self._release_mouse()

    def cancel_all(self, reason: str = "cancelled") -> None:
        operation_ids = list(self._operations.keys())
        if not operation_ids:
            return
        for operation_id in operation_ids:
            self.cancel(operation_id)
        logger.debug("Drag operations cancelled (%s): %s", reason, operation_ids)

    def is_active(self, operation_id: str) -> bool:
        return operation_id in self._operations

    def _release_mouse(self) -> None:
        widget = QWidget.mouseGrabber()
        if isinstance(widget, QWidget):
            widget.releaseMouse()

    def _on_focus_changed(self, old: object, new: object) -> None:
        if new is None and self.app.activeWindow() is None:
            self.cancel_all("focus lost")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        event_type = event.type()
        if event_type in (
            QEvent.Type.ApplicationDeactivate,
        ):
            self.cancel_all("application inactive")
        elif event_type == QEvent.Type.KeyPress:
            key_event: Optional[QKeyEvent] = event if isinstance(event, QKeyEvent) else None
            if key_event is not None and key_event.key() == Qt.Key.Key_Escape:
                self.cancel_all("escape")
        elif event_type in (QEvent.Type.WindowDeactivate,):
            self.cancel_all("window inactive")
        return False
