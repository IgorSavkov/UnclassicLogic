"""Журнал (лог) работы с нечёткими величинами: текстовый файл + подписчики (GUI)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


class Journal:
    def __init__(self, path="fuzzy_log.txt"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._listeners = []

    def subscribe(self, callback):
        """callback(line: str) вызывается на каждую новую запись."""
        self._listeners.append(callback)

    def write(self, message: str, level: str = "INFO") -> str:
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} [{level}] {message}"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        for callback in self._listeners:
            callback(line)
        return line

    def info(self, message: str) -> str:
        return self.write(message, "INFO")

    def warning(self, message: str) -> str:
        return self.write(message, "WARN")

    def error(self, message: str) -> str:
        return self.write(message, "ERROR")

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8") if self.path.exists() else ""
