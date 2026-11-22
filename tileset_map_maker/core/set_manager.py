import os
import json
from typing import Dict, List, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal
from ..models.asset_set import AssetSet


class SetManager(QObject):
    """Manages logical asset sets and persistence across application sessions."""
    sets_changed = pyqtSignal()

    def __init__(self, storage_path: Optional[str] = None):
        super().__init__()
        self.sets: Dict[str, AssetSet] = {}
        self.active_set_id: Optional[str] = None
        self.storage_path = storage_path or os.path.expanduser("~/.tileset_map_maker_sets.json")
        self.load_from_disk()

    def create_set(self, name: str, asset_ids: Optional[List[str]] = None) -> AssetSet:
        s = AssetSet(name=name, asset_ids=asset_ids)
        self.sets[s.id] = s
        self.active_set_id = s.id
        self.save_to_disk()
        self.sets_changed.emit()
        return s

    def remove_set(self, set_id: str) -> bool:
        if set_id in self.sets:
            del self.sets[set_id]
            if self.active_set_id == set_id:
                self.active_set_id = next(iter(self.sets.keys())) if self.sets else None
            self.save_to_disk()
            self.sets_changed.emit()
            return True
        return False

    def get_set(self, set_id: Optional[str]) -> Optional[AssetSet]:
        if not set_id:
            return None
        return self.sets.get(set_id)

    def get_active_set(self) -> Optional[AssetSet]:
        return self.get_set(self.active_set_id)

    def set_active_set(self, set_id: Optional[str]) -> None:
        self.active_set_id = set_id
        self.sets_changed.emit()

    def save_to_disk(self) -> None:
        try:
            data = [s.to_dict() for s in self.sets.values()]
            os.makedirs(os.path.dirname(os.path.abspath(self.storage_path)), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Błąd zapisu zestawów: {e}")

    def load_from_disk(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.sets.clear()
            for s_data in data:
                s = AssetSet.from_dict(s_data)
                self.sets[s.id] = s
            if self.sets and not self.active_set_id:
                self.active_set_id = next(iter(self.sets.keys()))
            self.sets_changed.emit()
        except Exception as e:
            print(f"Błąd odczytu zestawów: {e}")
