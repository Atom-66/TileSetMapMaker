from typing import Any, Dict, List


PROJECT_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://tileset-map-maker.invalid/schema/project-1.0.json",
    "title": "TileSet Map Maker project package 1.0",
    "type": "object",
    "required": ["format", "version", "project", "assets"],
    "properties": {
        "format": {"const": "tileset-map-maker"},
        "version": {"const": "1.0"},
        "project": {
            "type": "object",
            "required": ["id", "name", "active_map_id", "maps"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "active_map_id": {"type": "string"},
                "maps": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["id", "name", "map_width", "map_height", "layers"],
                    },
                },
            },
        },
        "assets": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "file_path", "asset_type"],
            },
        },
        "autotile": {"type": "object"},
        "terrain": {"type": "object"},
    },
}


def schema_errors(data: Any) -> List[str]:
    """Validate the documented 1.0 envelope without an optional dependency."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["Dokument musi być obiektem JSON."]
    if data.get("format") != "tileset-map-maker":
        errors.append("Pole 'format' musi mieć wartość 'tileset-map-maker'.")
    if data.get("version") != "1.0":
        errors.append("Pole 'version' musi mieć wartość '1.0'.")
    project = data.get("project")
    if not isinstance(project, dict):
        errors.append("Brak obiektu 'project'.")
    else:
        for key in ("id", "name", "active_map_id", "maps"):
            if key not in project:
                errors.append(f"Brak pola project.{key}.")
        if not isinstance(project.get("maps"), list) or not project.get("maps"):
            errors.append("project.maps musi zawierać co najmniej jedną mapę.")
    assets = data.get("assets")
    if not isinstance(assets, list):
        errors.append("Pole 'assets' musi być tablicą.")
    else:
        for index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                errors.append(f"assets[{index}] musi być obiektem.")
                continue
            for key in ("id", "name", "file_path", "asset_type"):
                if key not in asset:
                    errors.append(f"Brak pola assets[{index}].{key}.")
    return errors
