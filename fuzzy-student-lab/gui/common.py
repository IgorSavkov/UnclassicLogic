"""Общие элементы интерфейса: холст matplotlib, цвета, поля ввода."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")

from matplotlib import colormaps, colors as mcolors  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import (QDoubleSpinBox, QMessageBox, QTableWidgetItem, QVBoxLayout,  # noqa: E402
                             QWidget)

# Цвета, одинаковые в обеих темах. Цвета, зависящие от темы, — gui.theme.color(...)
COLOR_SELECTED = "#d62728"
COLOR_A = "#1f77b4"
COLOR_B = "#ff7f0e"
COLOR_RESULT = "#2ca02c"


def app_dir() -> Path:
    """Папка программы: рядом с .exe для собранной версии, иначе корень проекта."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def cluster_colors(k: int) -> list[str]:
    if k <= 10:
        base = colormaps["tab10"].colors
    elif k <= 20:
        base = colormaps["tab20"].colors
    else:
        cmap = colormaps["hsv"]
        base = [cmap(i / k) for i in range(k)]
    return [mcolors.to_hex(base[i]) for i in range(k)]


class PlotWidget(QWidget):
    """Холст matplotlib с панелью инструментов (масштаб, сохранение картинки)."""

    def __init__(self, parent=None, toolbar: bool = True):
        super().__init__(parent)
        self.figure = Figure(layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar = NavigationToolbar2QT(self.canvas, self) if toolbar else None
        if self.toolbar:
            self._layout.addWidget(self.toolbar)
        self._layout.addWidget(self.canvas)

    def draw(self):
        self.canvas.draw_idle()

    def retheme(self):
        """Очистить фигуру под новую тему (оси нужно создать заново)."""
        self.figure.clear()
        self.figure.set_facecolor(matplotlib.rcParams["figure.facecolor"])
        if self.toolbar:  # иконки панели подбираются под светлый/тёмный фон при создании
            self._layout.removeWidget(self.toolbar)
            self.toolbar.deleteLater()
            self.toolbar = NavigationToolbar2QT(self.canvas, self)
            self._layout.insertWidget(0, self.toolbar)


class NumItem(QTableWidgetItem):
    """Ячейка таблицы с числом: правильно сортируется."""

    def __init__(self, value: float, digits: int = 3):
        super().__init__(f"{value:.{digits}f}")
        self.value = float(value)
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        if isinstance(other, NumItem):
            return self.value < other.value
        return super().__lt__(other)


def dspin(lo: float, hi: float, value: float, step: float = 0.1, decimals: int = 3) -> QDoubleSpinBox:
    w = QDoubleSpinBox()
    w.setRange(lo, hi)
    w.setDecimals(decimals)
    w.setSingleStep(step)
    w.setValue(value)
    w.setKeyboardTracking(False)
    return w


def show_error(parent, title: str, exc: Exception | str):
    QMessageBox.warning(parent, title, str(exc))
