import json
import logging
import os
import platform
import sys
import traceback
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QStandardPaths


class DiagnosticService:
    """Rotating local diagnostics and an exportable environment report."""

    def __init__(self):
        self.log_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_path = os.path.join(self.log_dir, "tileset-map-maker.log")
        self.logger = logging.getLogger("TileSetMapMaker")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            handler = RotatingFileHandler(
                self.log_path,
                maxBytes=2 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s %(name)s: %(message)s"
                )
            )
            self.logger.addHandler(handler)

    def exception(self, context: str, exc: BaseException) -> None:
        self.logger.error(
            "%s: %s\n%s",
            context,
            exc,
            "".join(traceback.format_exception(exc)),
        )

    def build_report(self) -> Dict[str, Any]:
        return {
            "application": "TileSet Map Maker",
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "executable": sys.executable,
            "log_path": self.log_path,
        }

    def export_report(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(
                self.build_report(),
                handle,
                indent=2,
                ensure_ascii=False,
            )


class InterfaceProfileService:
    def __init__(self, settings):
        self.settings = settings

    def names(self) -> List[str]:
        profiles = self.settings.value("interface_profiles", {}, type=dict)
        return sorted(profiles) if isinstance(profiles, dict) else []

    def save(self, name: str, geometry, state, toolbar_layout: Optional[dict]) -> bool:
        name = name.strip()
        if not name:
            return False
        profiles = self.settings.value("interface_profiles", {}, type=dict)
        if not isinstance(profiles, dict):
            profiles = {}
        profiles[name] = {
            "geometry": geometry.toBase64().data().decode("ascii"),
            "state": state.toBase64().data().decode("ascii"),
            "toolbar_layout": toolbar_layout,
        }
        self.settings.setValue("interface_profiles", profiles)
        self.settings.setValue("active_interface_profile", name)
        return True

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        profiles = self.settings.value("interface_profiles", {}, type=dict)
        return profiles.get(name) if isinstance(profiles, dict) else None

    def active(self) -> str:
        return self.settings.value("active_interface_profile", "", type=str)
