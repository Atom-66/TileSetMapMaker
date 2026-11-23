from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal

from ..models.layer import Layer, MapItem
from ..models.project import Project


class Command(ABC):
    """Abstract base class for undoable commands."""

    def __init__(self, description: str = ""):
        self.description = description

    @abstractmethod
    def execute(self) -> None:
        pass

    @abstractmethod
    def undo(self) -> None:
        pass

    def redo(self) -> None:
        self.execute()


class TileBatchCommand(Command):
    """Command that handles changing tiles on a layer."""

    def __init__(
        self,
        project: Project,
        layer_id: str,
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]],
        description: str = "Edycja kafelków",
    ):
        """
        changes maps (col, row) -> (before_item, after_item).
        """
        super().__init__(description)
        self.project = project
        self.layer_id = layer_id
        self.changes = changes

    def execute(self) -> None:
        layer = self.project.get_layer(self.layer_id)
        if not layer or layer.locked:
            return
        for (col, row), (_, after_item) in self.changes.items():
            if after_item is None:
                layer.remove_tile(col, row)
            else:
                layer.set_tile(col, row, after_item.clone())
        self.project.is_modified = True

    def undo(self) -> None:
        layer = self.project.get_layer(self.layer_id)
        if not layer:
            return
        for (col, row), (before_item, _) in self.changes.items():
            if before_item is None:
                layer.remove_tile(col, row)
            else:
                layer.set_tile(col, row, before_item.clone())
        self.project.is_modified = True


class MapTileBatchesCommand(Command):
    """Reapply an already computed group of layer changes on one map."""

    def __init__(
        self,
        project: Project,
        map_id: str,
        changes: Dict[str, Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]]],
    ):
        super().__init__("Przeliczenie Auto-Tiling")
        self.project = project
        self.map_id = map_id
        self.changes = changes

    def _apply(self, index: int) -> None:
        map_model = self.project.maps.get(self.map_id)
        if not map_model:
            return
        for layer_id, changes in self.changes.items():
            layer = map_model.get_layer(layer_id)
            if not layer:
                continue
            for (col, row), pair in changes.items():
                item = pair[index]
                if item is None:
                    layer.remove_tile(col, row)
                else:
                    layer.set_tile(col, row, item.clone())
        self.project.is_modified = True

    def execute(self) -> None:
        self._apply(1)

    def undo(self) -> None:
        self._apply(0)


class ObjectAddCommand(Command):
    """Command to add a freeform object/prop to a layer."""

    def __init__(self, project: Project, layer_id: str, obj: MapItem, description: str = "Dodaj obiekt"):
        super().__init__(description)
        self.project = project
        self.layer_id = layer_id
        self.obj = obj

    def execute(self) -> None:
        layer = self.project.get_layer(self.layer_id)
        if layer and not layer.locked:
            layer.add_object(self.obj.clone())
            self.project.is_modified = True

    def undo(self) -> None:
        layer = self.project.get_layer(self.layer_id)
        if layer:
            layer.remove_object(self.obj.id)
            self.project.is_modified = True


class ObjectRemoveCommand(Command):
    """Command to remove a freeform object/prop from a layer."""

    def __init__(self, project: Project, layer_id: str, obj: MapItem, description: str = "Usuń obiekt"):
        super().__init__(description)
        self.project = project
        self.layer_id = layer_id
        self.obj = obj

    def execute(self) -> None:
        layer = self.project.get_layer(self.layer_id)
        if layer and not layer.locked:
            layer.remove_object(self.obj.id)
            self.project.is_modified = True

    def undo(self) -> None:
        layer = self.project.get_layer(self.layer_id)
        if layer:
            layer.add_object(self.obj.clone())
            self.project.is_modified = True


class LayerAddCommand(Command):
    """Command to add a layer."""

    def __init__(self, project: Project, layer: Layer, index: Optional[int] = None):
        super().__init__(f"Dodaj warstwę '{layer.name}'")
        self.project = project
        self.layer = layer
        self.index = index if index is not None else len(project.layers)

    def execute(self) -> None:
        if self.index <= len(self.project.layers):
            self.project.layers.insert(self.index, self.layer)
        else:
            self.project.layers.append(self.layer)
        self.project.active_layer_id = self.layer.id
        self.project.is_modified = True

    def undo(self) -> None:
        self.project.remove_layer(self.layer.id)
        self.project.is_modified = True


class LayerRemoveCommand(Command):
    """Command to remove a layer."""

    def __init__(self, project: Project, layer_id: str):
        layer = project.get_layer(layer_id)
        super().__init__(f"Usuń warstwę '{layer.name if layer else ''}'")
        self.project = project
        self.layer_id = layer_id
        if layer:
            self.layer = layer.clone(new_name=layer.name)
            self.layer.id = layer.id
        else:
            self.layer = None
        self.index = project.get_layer_index(layer_id)

    def execute(self) -> None:
        if self.layer_id:
            self.project.remove_layer(self.layer_id)
            self.project.is_modified = True

    def undo(self) -> None:
        if self.layer and self.index is not None:
            restored = self.layer.clone(new_name=self.layer.name)
            restored.id = self.layer_id
            self.project.layers.insert(self.index, restored)
            self.project.active_layer_id = self.layer_id
            self.project.is_modified = True


class LayerMoveCommand(Command):
    """Command to move layer position."""

    def __init__(self, project: Project, from_index: int, to_index: int):
        super().__init__("Zmień kolejność warstw")
        self.project = project
        self.from_index = from_index
        self.to_index = to_index

    def execute(self) -> None:
        self.project.move_layer(self.from_index, self.to_index)

    def undo(self) -> None:
        self.project.move_layer(self.to_index, self.from_index)


class LayerClearCommand(Command):
    """Snapshot and clear every item type on a layer."""

    def __init__(self, project: Project, layer_id: str):
        layer = project.get_layer(layer_id)
        super().__init__(f"Wyczyść warstwę '{layer.name if layer else ''}'")
        self.project = project
        self.layer_id = layer_id
        self.tiles = {
            coord: item.clone()
            for coord, item in layer.tiles.items()
        } if layer else {}
        self.objects = [item.clone() for item in layer.objects] if layer else []
        self.collisions = [
            collision.clone() for collision in layer.collisions
        ] if layer else []

    def execute(self) -> None:
        layer = self.project.get_layer(self.layer_id)
        if not layer or layer.locked:
            return
        layer.clear()
        self.project.is_modified = True

    def undo(self) -> None:
        layer = self.project.get_layer(self.layer_id)
        if not layer:
            return
        layer.tiles = {
            coord: item.clone() for coord, item in self.tiles.items()
        }
        layer.objects = [item.clone() for item in self.objects]
        layer.collisions = [
            collision.clone() for collision in self.collisions
        ]
        self.project.is_modified = True


class HistoryManager(QObject):
    """Manages undo/redo history stacks."""
    history_changed = pyqtSignal(bool, bool, str, str)  # can_undo, can_redo, undo_desc, redo_desc

    def __init__(self, max_history: int = 100):
        super().__init__()
        self.max_history = max_history
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []

    def push(self, command: Command) -> None:
        """Pushes and executes a command (or if already executed, registers it)."""
        self.undo_stack.append(command)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self._notify()

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        cmd = self.undo_stack.pop()
        cmd.undo()
        self.redo_stack.append(cmd)
        self._notify()
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        cmd = self.redo_stack.pop()
        cmd.redo()
        self.undo_stack.append(cmd)
        self._notify()
        return True

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def undo_description(self) -> str:
        return self.undo_stack[-1].description if self.undo_stack else ""

    def redo_description(self) -> str:
        return self.redo_stack[-1].description if self.redo_stack else ""

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._notify()

    def _notify(self) -> None:
        undo_desc = self.undo_stack[-1].description if self.undo_stack else ""
        redo_desc = self.redo_stack[-1].description if self.redo_stack else ""
        self.history_changed.emit(self.can_undo(), self.can_redo(), undo_desc, redo_desc)
