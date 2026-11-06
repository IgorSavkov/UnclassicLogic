"""Сравнение нечётких величин Стьюдента.

1. compare(A, B) — по чётким значениям (центрам): -1, 0, 1.
2. possibility_eq(A, B) — возможность равенства, высота пересечения:
       Poss(A = B) = sup_x min(μA(x), μB(x)).
   Это наибольшее α, при котором α-срезы A и B пересекаются:
       hA(α) + hB(α) >= |x0A - x0B|.
3. possibility_ge(A, B) — возможность того, что A >= B:
       Poss(A >= B) = sup_{x >= y} min(μA(x), μB(y))
   = 1, если x0A >= x0B, иначе высота пересечения.
"""
from __future__ import annotations

from numbers import Real

import numpy as np

from .student import StudentFuzzy, spread_factor

_BISECTION_STEPS = 60


def _center(v) -> float:
    if isinstance(v, StudentFuzzy):
        return v.x0
    if isinstance(v, Real):
        return float(v)
    raise TypeError(f"нельзя сравнивать с {type(v).__name__}")


def compare(a, b, tol: float = 1e-12) -> int:
    """-1, если A < B; 0, если центры равны; 1, если A > B."""
    d = _center(a) - _center(b)
    if abs(d) <= tol:
        return 0
    return 1 if d > 0 else -1


def intersection_heights(ref, x0, s, nu) -> np.ndarray:
    """Poss(ref = B_i) сразу для массива величин B_i = T(x0[i]; s[i]; nu[i]).

    Ищется бисекцией наибольшее α с hRef(α) + hB(α) >= |x0 - x0ref|
    (полуширины убывают по α, поэтому условие монотонно).
    """
    x0, s, nu = (np.atleast_1d(np.asarray(v, dtype=float)) for v in (x0, s, nu))
    if isinstance(ref, StudentFuzzy):
        c_ref, s_ref, nu_ref = ref.x0, ref.s, ref.nu
    else:
        c_ref, s_ref, nu_ref = _center(ref), 0.0, 1.0
    d = np.abs(x0 - c_ref)
    lo = np.zeros_like(d)
    hi = np.ones_like(d)
    for _ in range(_BISECTION_STEPS):
        mid = (lo + hi) / 2
        width = s_ref * spread_factor(nu_ref, mid) + s * spread_factor(nu, mid)
        ok = width >= d
        lo = np.where(ok, mid, lo)
        hi = np.where(ok, hi, mid)
    return np.where(d <= 1e-12, 1.0, lo)


def possibility_eq(a, b) -> float:
    """Возможность равенства (высота пересечения функций принадлежности)."""
    if isinstance(b, StudentFuzzy):
        return float(intersection_heights(a, b.x0, b.s, b.nu)[0])
    if isinstance(a, StudentFuzzy):
        return float(a.membership(_center(b)))
    return 1.0 if compare(a, b) == 0 else 0.0


def possibility_ge(a, b) -> float:
    """Возможность того, что A >= B."""
    if _center(a) >= _center(b):
        return 1.0
    return possibility_eq(a, b)


def necessity_ge(a, b) -> float:
    """Необходимость A >= B: Nec(A >= B) = 1 - Poss(B >= A)."""
    return 1.0 - possibility_ge(b, a)
