import os
import tempfile
import time
from typing import Optional
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ..models.project import Project
from .asset_manager import AssetManager
from .project_io import ProjectIO


class AutosaveManager(QObject):
    """
    Background timer-based autosave system (TASK-1204).
    Automatically saves .tmmap.autosave copies when changes are detected,
    and provides crash recovery detection.
    """
    autosaved = pyqtSignal(str)

    def __init__(
        self,
        project: Project,
        asset_manager: AssetManager,
        interval_ms: int = 180000,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.project = project
        self.asset_manager = asset_manager
        self.interval_ms = interval_ms
        self.enabled = True
        self._last_autosave_at = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.perform_autosave)
        if self.interval_ms > 0:
            self.timer.start(self.interval_ms)

    def set_project(self, project: Project) -> None:
        self.project = project
        self._last_autosave_at = 0.0

    def set_interval(self, minutes: int) -> None:
        if minutes <= 0:
            self.enabled = False
            self.timer.stop()
        else:
            self.enabled = True
            self.interval_ms = minutes * 60 * 1000
            self.timer.start(self.interval_ms)

    def get_autosave_path(self, target_path: Optional[str] = None) -> str:
        path = target_path or self.project.file_path
        if path:
            return f"{path}.autosave"
        return os.path.join(tempfile.gettempdir(), "tileset_map_maker_backup.tmmap.autosave")

    def perform_autosave(self) -> Optional[str]:
        if not self.enabled or not self.project.is_modified:
            return None
        now = time.monotonic()
        if self.interval_ms > 0 and (
            now - self._last_autosave_at < self.interval_ms / 1000
        ):
            return None

        save_path = self.get_autosave_path()
        # Preserve existing modified flag so user still knows project has unsaved edits
        was_modified = self.project.is_modified
        orig_file_path = self.project.file_path

        success = ProjectIO.save_project(self.project, self.asset_manager, save_path)
        # Restore project flags
        self.project.file_path = orig_file_path
        self.project.is_modified = was_modified

        if success:
            self._last_autosave_at = now
            self.autosaved.emit(save_path)
            return save_path
        return None

    def check_recovery_available(self, target_path: Optional[str] = None) -> Optional[str]:
        """Returns autosave file path if an autosave newer than original exists."""
        auto_path = self.get_autosave_path(target_path)
        if not os.path.exists(auto_path):
            return None

        orig_path = target_path or self.project.file_path
        if orig_path and os.path.exists(orig_path):
            if os.path.getmtime(auto_path) > os.path.getmtime(orig_path):
                return auto_path
            return None
        return auto_path

    def cleanup_autosave(self, target_path: Optional[str] = None) -> None:
        """Removes the autosave file upon normal save or discard."""
        auto_path = self.get_autosave_path(target_path)
        if os.path.exists(auto_path):
            try:
                os.remove(auto_path)
            except OSError:
                pass
