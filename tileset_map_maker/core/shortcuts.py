from typing import Dict, Iterable, Optional

from PyQt6.QtGui import QAction, QKeySequence


DEFAULT_SHORTCUTS: Dict[str, str] = {
    "new_project": "Ctrl+N",
    "open_project": "Ctrl+O",
    "save_project": "Ctrl+S",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Y",
    "brush": "B",
    "eraser": "E",
    "fill": "G",
    "line": "L",
    "rectangle": "U",
    "selection": "S",
    "wand": "W",
    "free_object": "V",
    "eyedropper": "I",
    "stamp": "T",
    "radial": "Q",
    "copy": "Ctrl+C",
    "paste_stamp": "Ctrl+V",
    "delete": "Delete",
    "fullscreen": "F11",
    "grid": "Ctrl+G",
    "fit": "Ctrl+F",
    "export": "Ctrl+E",
}


class ShortcutManager:
    def __init__(self, settings):
        self.settings = settings
        saved = settings.value("keyboard_shortcuts", {}, type=dict)
        self.shortcuts = dict(DEFAULT_SHORTCUTS)
        if isinstance(saved, dict):
            self.shortcuts.update(
                {
                    key: str(value)
                    for key, value in saved.items()
                    if key in self.shortcuts
                }
            )
        self.actions: Dict[str, QAction] = {}

    def register(self, key: str, action: QAction) -> None:
        self.actions[key] = action
        if key in self.shortcuts:
            action.setShortcut(QKeySequence(self.shortcuts[key]))

    def register_many(self, actions: Dict[str, QAction]) -> None:
        for key, action in actions.items():
            self.register(key, action)

    def set_shortcuts(self, shortcuts: Dict[str, str]) -> None:
        conflicts = self.conflicts(shortcuts.values())
        if conflicts:
            raise ValueError("Konflikt skrótów: " + ", ".join(conflicts))
        self.shortcuts.update(shortcuts)
        self.settings.setValue("keyboard_shortcuts", self.shortcuts)
        for key, action in self.actions.items():
            action.setShortcut(QKeySequence(self.shortcuts.get(key, "")))

    @staticmethod
    def conflicts(shortcuts: Iterable[str]) -> list[str]:
        seen = set()
        conflicts = set()
        for shortcut in shortcuts:
            normalized = QKeySequence(shortcut).toString(
                QKeySequence.SequenceFormat.PortableText
            ).casefold()
            if not normalized:
                continue
            if normalized in seen:
                conflicts.add(normalized)
            seen.add(normalized)
        return sorted(conflicts)

    def for_dialog(self) -> Dict[str, str]:
        return dict(self.shortcuts)
