"""Нечёткая величина с функцией принадлежности вида распределения Стьюдента.

Источник — [3] Абчук В.А. и др. Справочник по исследованию операций, 1979,
табл. 2.2.5, с. 70–71. Плотность распределения Стьюдента с k степенями свободы:

    S_k(t) = Γ((k+1)/2) / (√(kπ)·Γ(k/2)) · (1 + t²/k) ^ (-(k+1)/2),   -∞ < t < +∞.

Для функции принадлежности нормирующий множитель отброшен (тогда max μ = 1),
и введены сдвиг x0 и масштаб s: t = (x - x0) / s, ν = k.

Функция принадлежности (плотность t-распределения, нормированная к max = 1):

    μ(x) = (1 + ((x - x0) / s)^2 / ν) ^ (-(ν + 1) / 2)

    x0 — центр (мода, μ(x0) = 1);
    s  — масштаб (ширина «колокола»);
    ν  — число степеней свободы (форма хвостов: ν = 1 — Коши, ν → ∞ — Гаусс).

α-срез:  A_α = { x : μ(x) >= α } = [x0 - s·g_ν(α);  x0 + s·g_ν(α)],
где g_ν(α) = sqrt(ν · (α^(-2/(ν+1)) - 1)).
"""
from __future__ import annotations

import math

import numpy as np

#: Уровень α, по которому берутся «практические» границы носителя.
#: Теоретически носитель величины Стьюдента — вся числовая ось.
SUPPORT_ALPHA = 0.05


def _as_alpha(alpha) -> np.ndarray:
    a = np.asarray(alpha, dtype=float)
    if np.any(~(a > 0)) or np.any(a > 1):
        raise ValueError("α должно лежать в интервале (0; 1]")
    return a


def spread_factor(nu, alpha) -> np.ndarray:
    """g_ν(α) — полуширина α-среза при s = 1 (работает и для массивов)."""
    a = _as_alpha(alpha)
    nu = np.asarray(nu, dtype=float)
    return np.sqrt(np.maximum(nu * (a ** (-2.0 / (nu + 1.0)) - 1.0), 0.0))


def _scalar_or_array(value):
    return float(value) if np.ndim(value) == 0 else value


class StudentFuzzy:
    """Нечёткая величина T(x0; s; ν)."""

    __slots__ = ("x0", "s", "nu", "name")
    __hash__ = None  # изменяемый объект, сравнение по параметрам

    def __init__(self, x0: float = 0.0, s: float = 1.0, nu: float = 5.0, name: str = ""):
        x0, s, nu = float(x0), float(s), float(nu)
        if not math.isfinite(x0):
            raise ValueError("центр x0 должен быть конечным числом")
        if not (math.isfinite(s) and s > 0):
            raise ValueError("масштаб s должен быть больше 0")
        if not (math.isfinite(nu) and nu >= 1):
            raise ValueError("число степеней свободы ν должно быть не меньше 1")
        self.x0, self.s, self.nu = x0, s, nu
        self.name = name

    # ----------------------------------------------------------- принадлежность
    def membership(self, x):
        """μ(x); x — число или массив."""
        t = (np.asarray(x, dtype=float) - self.x0) / self.s
        return _scalar_or_array((1.0 + t * t / self.nu) ** (-(self.nu + 1.0) / 2.0))

    __call__ = membership

    def half_width(self, alpha):
        """Полуширина α-среза."""
        return _scalar_or_array(self.s * spread_factor(self.nu, alpha))

    def alpha_cut(self, alpha: float) -> tuple[float, float]:
        """α-срез [левая граница; правая граница]."""
        h = self.half_width(alpha)
        return self.x0 - h, self.x0 + h

    def alpha_cuts(self, alphas) -> tuple[np.ndarray, np.ndarray]:
        h = self.s * spread_factor(self.nu, alphas)
        return self.x0 - h, self.x0 + h

    @property
    def center(self) -> float:
        return self.x0

    @property
    def left(self) -> float:
        """Практическая левая граница (α = SUPPORT_ALPHA)."""
        return self.alpha_cut(SUPPORT_ALPHA)[0]

    @property
    def right(self) -> float:
        """Практическая правая граница (α = SUPPORT_ALPHA)."""
        return self.alpha_cut(SUPPORT_ALPHA)[1]

    def contains(self, x: float, alpha: float) -> bool:
        """Принадлежит ли x α-срезу величины."""
        return self.membership(x) >= alpha

    def defuzzify(self) -> float:
        """Чёткое значение. Функция симметрична, поэтому это центр x0."""
        return self.x0

    def sample(self, size=None, rng=None):
        """Случайное значение по закону Стьюдента.

        Способ из [3], табл. 2.2.5, с. 71: моделируются k + 1 нормальных
        чисел η_0i (x0 = 0, σ = 1) и

            t = η_0,k+1 / sqrt( (1/k) · Σ_{i=1..k} η_0i² ),   x = x0 + s·t.

        В справочнике под суммой напечатано η_0i без квадрата — это опечатка:
        сумма нормальных чисел бывает отрицательной, а Σ η² — это χ²_k,
        и только с ней отношение распределено по Стьюденту.
        Для дробного ν (возможно лишь у величин из старых файлов) вместо
        суммы квадратов берётся χ²_ν напрямую — это та же формула.
        """
        rng = np.random.default_rng(rng)
        shape = () if size is None else tuple(np.atleast_1d(size))
        k = self.nu
        if float(k).is_integer():
            k = int(k)
            eta = rng.standard_normal(shape + (k + 1,))
            chi2 = (eta[..., :k] ** 2).sum(axis=-1)
            z = eta[..., k]
        else:
            z = rng.standard_normal(shape)
            chi2 = rng.chisquare(k, shape)
        return _scalar_or_array(self.x0 + self.s * z / np.sqrt(chi2 / k))

    # ------------------------------------------------------------- арифметика
    def __add__(self, other):
        from .arithmetic import operate
        return operate(self, other, "+")

    def __radd__(self, other):
        from .arithmetic import operate
        return operate(other, self, "+")

    def __sub__(self, other):
        from .arithmetic import operate
        return operate(self, other, "-")

    def __rsub__(self, other):
        from .arithmetic import operate
        return operate(other, self, "-")

    def __mul__(self, other):
        from .arithmetic import operate
        return operate(self, other, "*")

    def __rmul__(self, other):
        from .arithmetic import operate
        return operate(other, self, "*")

    def __truediv__(self, other):
        from .arithmetic import operate
        return operate(self, other, "/")

    def __rtruediv__(self, other):
        from .arithmetic import operate
        return operate(other, self, "/")

    def __neg__(self):
        return StudentFuzzy(-self.x0, self.s, self.nu, f"-{self.name}" if self.name else "")

    # -------------------------------------------------------------- сравнение
    def __eq__(self, other):
        if not isinstance(other, StudentFuzzy):
            return NotImplemented
        return (math.isclose(self.x0, other.x0, abs_tol=1e-9)
                and math.isclose(self.s, other.s, rel_tol=1e-9)
                and math.isclose(self.nu, other.nu, rel_tol=1e-9))

    def __lt__(self, other):
        from .compare import compare
        return compare(self, other) < 0

    def __le__(self, other):
        from .compare import compare
        return compare(self, other) <= 0

    def __gt__(self, other):
        from .compare import compare
        return compare(self, other) > 0

    def __ge__(self, other):
        from .compare import compare
        return compare(self, other) >= 0

    # ------------------------------------------------------------- служебное
    def copy(self, name: str | None = None) -> "StudentFuzzy":
        return StudentFuzzy(self.x0, self.s, self.nu, self.name if name is None else name)

    def to_dict(self) -> dict:
        return {"name": self.name, "x0": self.x0, "s": self.s, "nu": self.nu}

    @classmethod
    def from_dict(cls, d: dict) -> "StudentFuzzy":
        return cls(d["x0"], d["s"], d["nu"], d.get("name", ""))

    def __repr__(self):
        return f"StudentFuzzy(x0={self.x0:.4g}, s={self.s:.4g}, nu={self.nu:.4g}, name={self.name!r})"

    def __str__(self):
        label = f"{self.name} = " if self.name else ""
        return f"{label}T({self.x0:.3f}; {self.s:.3f}; {self.nu:.2f})"
