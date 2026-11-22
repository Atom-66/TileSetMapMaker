import os
import json
from typing import Dict, List, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal
from ..models.stamp import StampPreset


class StampManager(QObject):
    """Manages the stamp preset library and session persistence."""
    stamps_changed = pyqtSignal()

    def __init__(self, storage_path: Optional[str] = None):
        super().__init__()
        self.stamps: Dict[str, StampPreset] = {}
        self.active_stamp_id: Optional[str] = None
        self.storage_path = storage_path or os.path.expanduser("~/.tileset_map_maker_stamps.json")
        self.load_from_disk()

    def add_stamp(self, preset: StampPreset) -> None:
        self.stamps[preset.id] = preset
        self.active_stamp_id = preset.id
        self.save_to_disk()
        self.stamps_changed.emit()

    def remove_stamp(self, stamp_id: str) -> bool:
        if stamp_id in self.stamps:
            del self.stamps[stamp_id]
            if self.active_stamp_id == stamp_id:
                self.active_stamp_id = next(iter(self.stamps.keys())) if self.stamps else None
            self.save_to_disk()
            self.stamps_changed.emit()
            return True
        return False

    def get_stamp(self, stamp_id: Optional[str]) -> Optional[StampPreset]:
        if not stamp_id:
            return None
        return self.stamps.get(stamp_id)

    def get_active_stamp(self) -> Optional[StampPreset]:
        return self.get_stamp(self.active_stamp_id)

    def set_active_stamp(self, stamp_id: Optional[str]) -> None:
        self.active_stamp_id = stamp_id
        self.stamps_changed.emit()

    def save_to_disk(self) -> None:
        try:
            data = [s.to_dict() for s in self.stamps.values()]
            os.makedirs(os.path.dirname(os.path.abspath(self.storage_path)), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Błąd zapisu stempli: {e}")

    def load_from_disk(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.stamps.clear()
            for s_data in data:
                s = StampPreset.from_dict(s_data)
                self.stamps[s.id] = s
            if self.stamps and not self.active_stamp_id:
                self.active_stamp_id = next(iter(self.stamps.keys()))
            self.stamps_changed.emit()
        except Exception as e:
            print(f"Błąd odczytu stempli: {e}")
