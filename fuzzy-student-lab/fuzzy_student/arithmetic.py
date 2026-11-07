"""Арифметика нечётких величин Стьюдента.

Операции выполняются по принципу обобщения Заде через α-срезы:
для каждого уровня α результат — интервальная операция над α-срезами операндов.

    [a1; b1] + [a2; b2] = [a1 + a2;  b1 + b2]
    [a1; b1] - [a2; b2] = [a1 - b2;  b1 - a2]
    [a1; b1] · [a2; b2] = [min(a1a2, a1b2, b1a2, b1b2);  max(...)]
    [a1; b1] / [a2; b2] = [a1; b1] · [1/b2; 1/a2],  если 0 ∉ [a2; b2]

Сложение и вычитание величин с одинаковым ν дают снова величину Стьюдента
(L-R арифметика): T(x1; s1; ν) ± T(x2; s2; ν) = T(x1 ± x2; s1 + s2; ν).
В остальных случаях результат приближается величиной Стьюдента методом
наименьших квадратов по полуширинам α-срезов.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

import numpy as np

from .student import SUPPORT_ALPHA, StudentFuzzy, spread_factor

OPERATIONS = ("+", "-", "*", "/")
OPERATION_NAMES = {"+": "сложение", "-": "вычитание", "*": "умножение", "/": "деление"}

#: уровни α, на которых считается точный результат
DEFAULT_ALPHAS = np.linspace(SUPPORT_ALPHA, 1.0, 60)
#: сетка ν, по которой подбирается аппроксимация: целые числа степеней свободы
#: k = 1..300, как в [3] (табл. 2.2.5) — результат остаётся в том же семействе
_NU_GRID = np.arange(1.0, 301.0)


@dataclass
class CutResult:
    """Результат операции, заданный набором α-срезов [left(α); right(α)]."""

    alphas: np.ndarray
    left: np.ndarray
    right: np.ndarray

    def polygon(self) -> tuple[np.ndarray, np.ndarray]:
        """Точки ломаной μ(x) для рисования."""
        xs = np.concatenate([self.left, self.right[::-1]])
        ys = np.concatenate([self.alphas, self.alphas[::-1]])
        return xs, ys

    @property
    def core(self) -> float:
        return float((self.left[-1] + self.right[-1]) / 2)

    def membership(self, x: float) -> float | None:
        """μ(x) результата: уровень α, на котором x лежит на границе α-среза.

        Срезы вложены (левая граница растёт с α, правая убывает), поэтому μ(x)
        находится линейной интерполяцией. None — x вне нижнего среза (μ < α_min).
        """
        x = float(x)
        if x < self.left[0] or x > self.right[0]:
            return None
        if x < self.left[-1]:
            return float(np.interp(x, self.left, self.alphas))
        if x > self.right[-1]:
            return float(np.interp(x, self.right[::-1], self.alphas[::-1]))
        return 1.0


@dataclass
class OperationResult:
    value: StudentFuzzy      # результат в виде величины Стьюдента
    cuts: CutResult          # точный результат по α-срезам
    error: float             # относительная ошибка аппроксимации (0 — точно)
    exact: bool              # результат точный (замкнутая формула)


def _is_number(v) -> bool:
    return isinstance(v, Real) and not isinstance(v, bool)


def _cuts(v, alphas):
    if isinstance(v, StudentFuzzy):
        return v.alpha_cuts(alphas)
    c = np.full(len(alphas), float(v))
    return c, c.copy()


def interval_operation(l1, r1, l2, r2, op: str):
    """Интервальная операция над массивами границ."""
    if op == "+":
        return l1 + l2, r1 + r2
    if op == "-":
        return l1 - r2, r1 - l2
    if op == "*":
        p = np.stack([l1 * l2, l1 * r2, r1 * l2, r1 * r2])
        return p.min(axis=0), p.max(axis=0)
    if op == "/":
        if np.any((l2 <= 0) & (r2 >= 0)):
            raise ZeroDivisionError(
                f"деление невозможно: 0 попадает в α-срез делителя (α ≥ {SUPPORT_ALPHA})")
        return interval_operation(l1, r1, 1.0 / r2, 1.0 / l2, "*")
    raise ValueError(f"неизвестная операция {op!r}")


def exact_operation(a, b, op: str, alphas=DEFAULT_ALPHAS) -> CutResult:
    """Точный результат операции на уровнях alphas."""
    alphas = np.asarray(alphas, dtype=float)
    l1, r1 = _cuts(a, alphas)
    l2, r2 = _cuts(b, alphas)
    left, right = interval_operation(l1, r1, l2, r2, op)
    return CutResult(alphas, left, right)


def fit_student(cuts: CutResult, name: str = "") -> tuple[StudentFuzzy, float]:
    """Подбор T(x0; s; ν), наиболее близкой к результату по α-срезам.

    x0 — середина ядра (α = 1); для каждого целого ν = 1..300 масштаб s находится
    МНК по полуширинам h(α) ≈ s·g_ν(α); выбирается ν с наименьшей ошибкой.
    """
    mask = cuts.alphas < 1.0
    a = cuts.alphas[mask]
    h = (cuts.right[mask] - cuts.left[mask]) / 2.0
    g = spread_factor(_NU_GRID[:, None], a[None, :])          # (число ν, число α)
    s = (g @ h) / np.maximum((g * g).sum(axis=1), 1e-300)
    err = ((h[None, :] - s[:, None] * g) ** 2).sum(axis=1)
    best = int(np.argmin(err))
    norm = float((h * h).sum())
    rel = math.sqrt(err[best] / norm) if norm > 0 else 0.0
    s_best = max(float(s[best]), 1e-12)
    return StudentFuzzy(cuts.core, s_best, float(_NU_GRID[best]), name), rel


def operate_detailed(a, b, op: str, name: str = "") -> OperationResult:
    """Выполнить операцию op ('+', '-', '*', '/') над a и b (величины или числа)."""
    if op not in OPERATIONS:
        raise ValueError(f"неизвестная операция {op!r}")
    a_fuzzy, b_fuzzy = isinstance(a, StudentFuzzy), isinstance(b, StudentFuzzy)
    if not a_fuzzy and not b_fuzzy:
        raise TypeError("хотя бы один операнд должен быть нечёткой величиной")
    for v in (a, b):
        if not isinstance(v, StudentFuzzy) and not _is_number(v):
            raise TypeError(f"операнд должен быть StudentFuzzy или числом, а не {type(v).__name__}")

    cuts = exact_operation(a, b, op)

    # замкнутые формулы (результат — точно величина Стьюдента)
    closed = None
    if a_fuzzy and b_fuzzy and op in "+-" and math.isclose(a.nu, b.nu, rel_tol=1e-9):
        x0 = a.x0 + b.x0 if op == "+" else a.x0 - b.x0
        closed = StudentFuzzy(x0, a.s + b.s, a.nu, name)
    elif a_fuzzy and not b_fuzzy:
        c = float(b)
        if op == "+":
            closed = StudentFuzzy(a.x0 + c, a.s, a.nu, name)
        elif op == "-":
            closed = StudentFuzzy(a.x0 - c, a.s, a.nu, name)
        elif op == "*":
            if c == 0:
                raise ValueError("умножение на 0 даёт чёткое число 0, а не нечёткую величину")
            closed = StudentFuzzy(a.x0 * c, a.s * abs(c), a.nu, name)
        else:
            if c == 0:
                raise ZeroDivisionError("деление на 0")
            closed = StudentFuzzy(a.x0 / c, a.s / abs(c), a.nu, name)
    elif b_fuzzy and not a_fuzzy and op in "+-*":
        c = float(a)
        if op == "+":
            closed = StudentFuzzy(c + b.x0, b.s, b.nu, name)
        elif op == "-":
            closed = StudentFuzzy(c - b.x0, b.s, b.nu, name)
        else:
            if c == 0:
                raise ValueError("умножение на 0 даёт чёткое число 0, а не нечёткую величину")
            closed = StudentFuzzy(c * b.x0, b.s * abs(c), b.nu, name)

    if closed is not None:
        return OperationResult(closed, cuts, 0.0, True)
    value, err = fit_student(cuts, name)
    return OperationResult(value, cuts, err, False)


def operate(a, b, op: str, name: str = "") -> StudentFuzzy:
    return operate_detailed(a, b, op, name).value


def add(a, b, name=""):
    return operate(a, b, "+", name)


def subtract(a, b, name=""):
    return operate(a, b, "-", name)


def multiply(a, b, name=""):
    return operate(a, b, "*", name)


def divide(a, b, name=""):
    return operate(a, b, "/", name)
