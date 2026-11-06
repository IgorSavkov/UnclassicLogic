"""Множество нечётких величин Стьюдента."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .compare import intersection_heights
from .student import SUPPORT_ALPHA, StudentFuzzy


class FuzzySet:
    """Упорядоченный набор величин StudentFuzzy с уникальными именами."""

    def __init__(self, items=None, name: str = ""):
        self.name = name
        self._items: list[StudentFuzzy] = []
        for v in items or []:
            self.add(v)

    # ------------------------------------------------------------ контейнер
    def add(self, value: StudentFuzzy) -> StudentFuzzy:
        if not isinstance(value, StudentFuzzy):
            raise TypeError("в множество можно добавлять только StudentFuzzy")
        if not value.name or value.name in self.names():
            value.name = self._free_name()
        self._items.append(value)
        return value

    def extend(self, values):
        for v in values:
            self.add(v)

    def remove(self, index: int) -> StudentFuzzy:
        return self._items.pop(index)

    def clear(self):
        self._items.clear()

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return FuzzySet(self._items[index])
        return self._items[index]

    def names(self) -> list[str]:
        return [v.name for v in self._items]

    def index_of(self, name: str) -> int:
        return self.names().index(name)

    def _free_name(self) -> str:
        used = set(self.names())
        i = len(self._items) + 1
        while f"T{i:03d}" in used:
            i += 1
        return f"T{i:03d}"

    # ---------------------------------------------------------------- данные
    def params(self) -> np.ndarray:
        """Матрица параметров (n × 3): x0, s, ν."""
        if not self._items:
            return np.empty((0, 3))
        return np.array([[v.x0, v.s, v.nu] for v in self._items], dtype=float)

    def bounds(self, alpha: float = SUPPORT_ALPHA) -> tuple[float, float]:
        """Общий диапазон α-срезов всех величин (для осей графиков)."""
        if not self._items:
            return -1.0, 1.0
        cuts = [v.alpha_cut(alpha) for v in self._items]
        return min(c[0] for c in cuts), max(c[1] for c in cuts)

    def subset(self, indices) -> "FuzzySet":
        """Подмножество из выбранных величин (сами объекты не копируются)."""
        result = FuzzySet(name=self.name)
        result._items = [self._items[i] for i in indices]
        return result

    # --------------------------------------------------------- отбор по α
    def heights_with(self, reference: StudentFuzzy) -> np.ndarray:
        """Poss(reference = B) для каждой величины B множества."""
        if not self._items:
            return np.empty(0)
        p = self.params()
        return intersection_heights(reference, p[:, 0], p[:, 1], p[:, 2])

    def memberships_at(self, x: float) -> np.ndarray:
        """μ_B(x) для каждой величины B множества."""
        if not self._items:
            return np.empty(0)
        p = self.params()
        t = (x - p[:, 0]) / p[:, 1]
        return (1.0 + t * t / p[:, 2]) ** (-(p[:, 2] + 1.0) / 2.0)

    def alpha_subset(self, alpha: float, reference: StudentFuzzy | None = None,
                     point: float | None = None) -> list[int]:
        """Индексы величин, отобранных α-срезом.

        reference — величины, чей α-срез пересекается с α-срезом reference
                    (то есть Poss(reference = B) >= α);
        point     — величины, чьему α-срезу принадлежит точка x* (μ_B(x*) >= α).
        """
        if not 0 < alpha <= 1:
            raise ValueError("α должно лежать в интервале (0; 1]")
        if (reference is None) == (point is None):
            raise ValueError("нужно задать ровно один критерий: reference или point")
        scores = self.heights_with(reference) if reference is not None else self.memberships_at(point)
        return [int(i) for i in np.flatnonzero(scores >= alpha - 1e-12)]

    # ------------------------------------------------------------- файлы
    def to_list(self) -> list[dict]:
        return [v.to_dict() for v in self._items]

    @classmethod
    def from_list(cls, data: list[dict], name: str = "") -> "FuzzySet":
        return cls([StudentFuzzy.from_dict(d) for d in data], name)

    def save(self, path):
        Path(path).write_text(
            json.dumps({"type": "StudentFuzzySet", "items": self.to_list()}, ensure_ascii=False, indent=2),
            encoding="utf-8")

    @classmethod
    def load(cls, path) -> "FuzzySet":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        items = data["items"] if isinstance(data, dict) else data
        return cls.from_list(items, Path(path).stem)

    def __repr__(self):
        return f"FuzzySet({len(self)} величин)"
