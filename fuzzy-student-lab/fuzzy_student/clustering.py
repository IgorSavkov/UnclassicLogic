"""Иерархическая (агломеративная) кластеризация множества нечётких величин.

Расстояние между нечёткими величинами — метрика по α-срезам:

    d(A, B) = ( ∫ [ (L_A(α) - L_B(α))² + (R_A(α) - R_B(α))² ] dα )^(1/2),

где [L(α); R(α)] — α-срез. Интеграл берётся по α ∈ [0.05; 1] по сетке уровней,
поэтому каждая величина превращается в вектор границ её α-срезов, а d —
обычное евклидово расстояние между такими векторами. Расстояние учитывает
все три параметра: центр x0, масштаб s и форму ν.

Алгоритм: сначала каждая величина — отдельный кластер, затем на каждом шаге
сливаются два ближайших кластера (по умолчанию — метод Уорда). История слияний —
дендрограмма. Разбиение получают, разрезав дерево:
  * на заданное количество кластеров k;
  * по критерию — порогу расстояния h (сливаются кластеры ближе h).
"""
from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage

from .student import SUPPORT_ALPHA, StudentFuzzy

METHODS = {
    "ward": "Уорда",
    "complete": "дальнего соседа",
    "average": "средней связи",
    "single": "ближнего соседа",
}

FEATURE_ALPHAS = np.linspace(SUPPORT_ALPHA, 1.0, 20)


def feature_vectors(items, alphas=FEATURE_ALPHAS) -> np.ndarray:
    """Векторы [L(α1..αm), R(α1..αm)], масштабированные под интеграл по α."""
    alphas = np.asarray(alphas, dtype=float)
    weight = np.sqrt((1.0 - alphas[0]) / len(alphas))
    rows = []
    for v in items:
        left, right = v.alpha_cuts(alphas)
        rows.append(np.concatenate([left, right]) * weight)
    return np.array(rows)


def fuzzy_distance(a: StudentFuzzy, b: StudentFuzzy, alphas=FEATURE_ALPHAS) -> float:
    """Расстояние между двумя величинами по α-срезам."""
    va, vb = feature_vectors([a, b], alphas)
    return float(np.linalg.norm(va - vb))


class ClusterAnalysis:
    """Кластерный анализ набора величин. Дерево строится один раз в конструкторе."""

    def __init__(self, items, method: str = "ward", alphas=FEATURE_ALPHAS):
        items = list(items)
        if len(items) < 2:
            raise ValueError("для кластеризации нужно хотя бы 2 величины")
        if method not in METHODS:
            raise ValueError(f"неизвестный метод {method!r}")
        self.items = items
        self.method = method
        self.features = feature_vectors(items, alphas)
        self.linkage = linkage(self.features, method=method)
        self._centers = np.array([v.x0 for v in items])

    @property
    def n(self) -> int:
        return len(self.items)

    @property
    def max_height(self) -> float:
        return float(self.linkage[-1, 2])

    # ---------------------------------------------------- срез дерева
    def threshold_for(self, k: int) -> float:
        """Высота, на которой надо разрезать дерево, чтобы получить k кластеров."""
        if not 1 <= k <= self.n:
            raise ValueError(f"количество кластеров должно быть от 1 до {self.n}")
        h = self.linkage[:, 2]
        if k == 1:
            return float(h[-1] * 1.05 + 1e-9)
        if k == self.n:
            return float(h[0] / 2)
        # после n-k слияний остаётся k кластеров: режем между (n-k)-м и (n-k+1)-м
        return float((h[self.n - k - 1] + h[self.n - k]) / 2)

    def labels_for_k(self, k: int) -> np.ndarray:
        """Номера кластеров (0..k-1) при разбиении на k кластеров."""
        if not 1 <= k <= self.n:
            raise ValueError(f"количество кластеров должно быть от 1 до {self.n}")
        return self._relabel(fcluster(self.linkage, k, criterion="maxclust"))

    def labels_for_threshold(self, threshold: float) -> np.ndarray:
        """Номера кластеров при разрезе дерева на высоте threshold (критерий)."""
        if threshold < 0:
            raise ValueError("порог расстояния не может быть отрицательным")
        return self._relabel(fcluster(self.linkage, threshold, criterion="distance"))

    def _relabel(self, raw: np.ndarray) -> np.ndarray:
        """Перенумеровать кластеры по возрастанию среднего центра (слева направо)."""
        ids = np.unique(raw)
        order = sorted(ids, key=lambda c: self._centers[raw == c].mean())
        mapping = {c: i for i, c in enumerate(order)}
        return np.array([mapping[c] for c in raw])

    # ------------------------------------------------------- результаты
    @staticmethod
    def groups(labels) -> list[list[int]]:
        labels = np.asarray(labels)
        return [list(np.flatnonzero(labels == c)) for c in range(labels.max() + 1)]

    def summary(self, labels) -> list[dict]:
        """Характеристики кластеров: размер, средние параметры, диапазон центров."""
        p = np.array([[v.x0, v.s, v.nu] for v in self.items])
        rows = []
        for c, idx in enumerate(self.groups(labels)):
            q = p[idx]
            rows.append({"cluster": c, "size": len(idx),
                         "x0_mean": q[:, 0].mean(), "x0_min": q[:, 0].min(), "x0_max": q[:, 0].max(),
                         "s_mean": q[:, 1].mean(), "nu_mean": q[:, 2].mean()})
        return rows

    def node_labels(self, labels) -> np.ndarray:
        """Кластер для каждого узла дерева (листья и слияния); -1 — узел выше среза."""
        labels = np.asarray(labels)
        nodes = np.empty(2 * self.n - 1, dtype=int)
        nodes[:self.n] = labels
        for i, (a, b, *_rest) in enumerate(self.linkage):
            la, lb = nodes[int(a)], nodes[int(b)]
            nodes[self.n + i] = la if la == lb else -1
        return nodes
