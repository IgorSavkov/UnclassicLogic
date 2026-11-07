"""Общее состояние приложения: текущее множество, выбранная величина, журнал."""
from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from fuzzy_student import FuzzySet, Journal, StudentFuzzy


class AppState(QObject):
    set_changed = pyqtSignal()           # множество заменено или изменено
    selection_changed = pyqtSignal(int)  # выбрана другая величина (индекс; -1 — не выбрана)

    def __init__(self, journal: Journal):
        super().__init__()
        self.journal = journal
        self.fset = FuzzySet()
        self.full_set: FuzzySet | None = None  # исходное множество, если сейчас открыто подмножество
        self.selected = -1

    @property
    def selected_value(self) -> StudentFuzzy | None:
        return self.fset[self.selected] if 0 <= self.selected < len(self.fset) else None

    @property
    def is_subset(self) -> bool:
        return self.full_set is not None

    def log(self, message: str):
        self.journal.info(message)

    def set_fuzzy_set(self, fset: FuzzySet, message: str = "", *, is_subset: bool = False,
                      selected: int = 0):
        if is_subset:
            if self.full_set is None:
                self.full_set = self.fset
        else:
            self.full_set = None
        self.fset = fset
        # selected = -1 — величина не выбрана
        self.selected = selected if -1 <= selected < len(fset) else (0 if len(fset) else -1)
        if message:
            self.log(message)
        self.set_changed.emit()
        self.selection_changed.emit(self.selected)

    def restore_full_set(self):
        if self.full_set is None:
            return
        full = self.full_set
        self.set_fuzzy_set(full, f"Возврат к исходному множеству ({len(full)} величин)")

    def add_value(self, value: StudentFuzzy, message: str = ""):
        self.fset.add(value)
        self.selected = len(self.fset) - 1
        self.log(message or f"Добавлена величина {value}")
        self.set_changed.emit()
        self.selection_changed.emit(self.selected)

    def remove_values(self, indices):
        indices = sorted(set(indices), reverse=True)
        removed = [self.fset.remove(i) for i in indices]
        if not removed:
            return
        self.selected = min(self.selected, len(self.fset) - 1)
        self.log("Удалены величины: " + ", ".join(v.name for v in reversed(removed)))
        self.set_changed.emit()
        self.selection_changed.emit(self.selected)

    def select(self, index: int):
        """Выбрать величину по индексу; -1 — снять выбор."""
        if index != self.selected and -1 <= index < len(self.fset):
            self.selected = index
            self.selection_changed.emit(index)
