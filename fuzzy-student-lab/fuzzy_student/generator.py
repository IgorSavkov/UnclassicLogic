"""Генерация набора нечётких величин Стьюдента."""
from __future__ import annotations

import numpy as np

from .fuzzy_set import FuzzySet
from .student import StudentFuzzy


def generate_set(n: int = 200, *, groups: int = 5, seed=None,
                 center_range=(-10.0, 10.0), scale_range=(0.3, 1.5),
                 nu_range=(1, 30)) -> FuzzySet:
    """Сгенерировать n величин T(x0; s; ν).

    groups = 0 — параметры равномерно случайны во всех диапазонах;
    groups > 0 — величины разбросаны вокруг groups случайных «типичных»
                 величин (тогда в данных есть естественные кластеры).
    seed — зерно генератора (одинаковое зерно → одинаковый набор).
    """
    if n < 1:
        raise ValueError("количество величин должно быть не меньше 1")
    if groups < 0:
        raise ValueError("число групп не может быть отрицательным")
    (c_lo, c_hi), (s_lo, s_hi), (nu_lo, nu_hi) = center_range, scale_range, nu_range
    if not (c_lo < c_hi and 0 < s_lo < s_hi and 0 < nu_lo <= nu_hi):
        raise ValueError("неверные диапазоны параметров")

    rng = np.random.default_rng(seed)
    if groups == 0:
        x0 = rng.uniform(c_lo, c_hi, n)
        s = rng.uniform(s_lo, s_hi, n)
        nu = rng.integers(nu_lo, nu_hi + 1, n).astype(float)
    else:
        g_x0 = rng.uniform(c_lo, c_hi, groups)
        g_s = rng.uniform(s_lo, s_hi, groups)
        g_nu = rng.integers(nu_lo, nu_hi + 1, groups)
        label = rng.integers(0, groups, n)
        x0 = g_x0[label] + rng.normal(0.0, (c_hi - c_lo) / (8 * groups), n)
        s = np.clip(g_s[label] + rng.normal(0.0, 0.08 * (s_hi - s_lo), n), s_lo, s_hi)
        nu = np.clip(np.round(g_nu[label] + rng.normal(0.0, 1.5, n)), nu_lo, nu_hi)

    return FuzzySet([StudentFuzzy(x0[i], s[i], nu[i], f"T{i + 1:03d}") for i in range(n)],
                    name=f"Сгенерировано {n}")
