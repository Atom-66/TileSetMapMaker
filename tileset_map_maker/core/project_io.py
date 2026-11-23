import json
import os
from typing import Optional, List, Dict, Any
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtCore import Qt

from ..models.project import Project
from .asset_manager import AssetManager
from .render_engine import RenderEngine, RenderOptions


class ProjectIO:
    """Handles project file serialization/deserialization and PNG exports."""

    @staticmethod
    def save_project(
        project: Project,
        asset_manager: AssetManager,
        file_path: str,
        autotile_engine: Optional[Any] = None,
    ) -> bool:
        """Saves project, asset library metadata, and autotile rules to a JSON .tmmap file."""
        try:
            base_dir = os.path.dirname(os.path.abspath(file_path))
            os.makedirs(base_dir, exist_ok=True)

            data = {
                "version": "1.0",
                "project": project.to_dict(),
                "assets": asset_manager.to_dict(),
            }
            if autotile_engine:
                data["autotile"] = autotile_engine.to_dict()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            project.file_path = file_path
            project.is_modified = False
            return True
        except Exception as e:
            print(f"Błąd zapisu projektu: {e}")
            return False

    @staticmethod
    def load_project(
        file_path: str,
        asset_manager: AssetManager,
        autotile_engine: Optional[Any] = None,
    ) -> Optional[Project]:
        """Loads project from .tmmap file and restores asset library, layers, and autotile rules."""
        try:
            if not os.path.exists(file_path):
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "assets" in data:
                asset_manager.load_from_dict(data["assets"])

            if autotile_engine and "autotile" in data:
                autotile_engine.load_from_dict(data["autotile"])

            project_data = data.get("project", {})
            project = Project.from_dict(project_data)
            project.file_path = file_path
            project.is_modified = False
            return project
        except Exception as e:
            print(f"Błąd odczytu projektu: {e}")
            return None

    @staticmethod
    def export_png(
        project: Project,
        render_engine: RenderEngine,
        file_path: str,
        transparent_bg: bool = False,
        custom_bg_color: Optional[str] = None,
        only_layer_ids: Optional[List[str]] = None,
        crop_to_content: bool = False,
        scale: float = 1.0,
    ) -> bool:
        """
        Exports the map to a clean, high-resolution PNG file.
        Respects layer visibility and custom background settings.
        """
        try:
            bg_col = QColor(custom_bg_color) if custom_bg_color else None

            options = RenderOptions(
                show_grid=False,
                show_selection=False,
                preview_items=[],
                render_checkerboard=False,
                ignore_hidden_layers=True,
                transparent_bg=transparent_bg,
                custom_bg_color=bg_col,
                only_layer_ids=only_layer_ids,
                scale=scale,
            )

            qimg = render_engine.export_to_image(
                project=project,
                options=options,
                crop_to_content=crop_to_content,
            )

            if scale != 1.0 and scale > 0.1:
                target_w = int(qimg.width() * scale)
                target_h = int(qimg.height() * scale)
                qimg = qimg.scaled(
                    target_w,
                    target_h,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )

            dir_path = os.path.dirname(os.path.abspath(file_path))
            os.makedirs(dir_path, exist_ok=True)

            return qimg.save(file_path, "PNG")
        except Exception as e:
            print(f"Błąd eksportu PNG: {e}")
            return False
