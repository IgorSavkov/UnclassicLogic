"""Общие элементы интерфейса: холст matplotlib, цвета, поля ввода."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")

from matplotlib import colormaps, colors as mcolors  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
import numpy as np  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QColor, QCursor, QPalette  # noqa: E402
from PyQt6.QtWidgets import (QDoubleSpinBox, QFormLayout, QFrame, QGroupBox, QLayout, QMessageBox,  # noqa: E402
                             QScrollArea, QTableWidgetItem, QToolTip, QVBoxLayout, QWidget)

SIDE_WIDTH = 360  # ширина левой колонки с настройками — одна на всех вкладках

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
    """Холст matplotlib с панелью инструментов (масштаб, сохранение картинки).

    Быстрая перерисовка (blitting), три слоя:
      фон        — всё обычное; рисуется полностью только в draw() и запоминается картинкой;
      слой 0     — «анимированные» художники (add_animated): update_animated() рисует их
                   поверх запомненного фона, не трогая остальное;
      слой 1     — подсказка у курсора (add_animated(..., overlay=True)): update_overlay()
                   рисует только её поверх фона со слоем 0.
    Полная перерисовка 200 кривых занимает ~100+ мс, обновление слоёв — единицы-десятки мс.
    """

    def __init__(self, parent=None, toolbar: bool = True):
        super().__init__(parent)
        self.figure = Figure(layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self._sync_background()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar = NavigationToolbar2QT(self.canvas, self) if toolbar else None
        if self.toolbar:
            self._layout.addWidget(self.toolbar)
        self._layout.addWidget(self.canvas)
        self._layers: tuple[list, list] = ([], [])
        self._bg = [None, None]          # фон без слоёв; фон со слоем 0
        self._full_pending = True        # полная перерисовка уже запрошена
        self.canvas.mpl_connect("draw_event", self._on_draw)

    def _sync_background(self):
        """Фон холста — в цвет рисунка. При дробном масштабе Windows (125–175 %) картинка
        matplotlib на долю пикселя меньше виджета, а остаток matplotlib стирает фоном виджета,
        который сам же задаёт белым, — по краю графика была видна белая линия."""
        pal = self.canvas.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(mcolors.to_hex(self.figure.get_facecolor())))
        self.canvas.setPalette(pal)

    def draw(self):
        """Полная перерисовка (когда меняется фон: данные, оси, режим)."""
        self._full_pending = True
        self.canvas.draw_idle()

    def add_animated(self, artist, overlay: bool = False):
        artist.set_animated(True)  # при полной перерисовке такие художники пропускаются
        layer = self._layers[int(overlay)]
        if artist not in layer:
            layer.append(artist)
        return artist

    def remove_animated(self, artist):
        for layer in self._layers:
            if artist in layer:
                layer.remove(artist)

    def _attached(self, artist) -> bool:
        """Художник всё ещё на графике. После ax.clear() matplotlib создаёт НОВЫЕ заголовок
        и легенду, а у старых ссылка на фигуру остаётся — поэтому проверяем по составу осей."""
        ax = artist.axes
        return ax is not None and ax in self.figure.axes and artist in ax.get_children()

    def _draw_layer(self, i: int):
        layer = self._layers[i]
        layer[:] = [a for a in layer if self._attached(a)]
        for artist in layer:
            if artist.get_visible():
                self.figure.draw_artist(artist)

    def _on_draw(self, _event):
        # вызывается в конце полной перерисовки: запомнить фон и дорисовать слои
        self._full_pending = False
        self._bg[0] = self.canvas.copy_from_bbox(self.figure.bbox)
        self._draw_layer(0)
        self._bg[1] = self.canvas.copy_from_bbox(self.figure.bbox)
        self._draw_layer(1)

    def update_animated(self):
        """Перерисовать только слой 0 (и подсказку) поверх запомненного фона."""
        if self._full_pending or self._bg[0] is None:
            self.draw()
            return
        self.canvas.restore_region(self._bg[0])
        self._draw_layer(0)
        self._bg[1] = self.canvas.copy_from_bbox(self.figure.bbox)
        self._draw_layer(1)
        self.canvas.blit(self.figure.bbox)

    def update_overlay(self):
        """Перерисовать только подсказку у курсора."""
        if self._full_pending or self._bg[1] is None:
            return  # подсказка дорисуется в конце уже запрошенной полной перерисовки
        self.canvas.restore_region(self._bg[1])
        self._draw_layer(1)
        self.canvas.blit(self.figure.bbox)

    def retheme(self):
        """Очистить фигуру под новую тему (оси нужно создать заново)."""
        for layer in self._layers:
            layer.clear()
        self._bg = [None, None]
        self.figure.clear()
        self.figure.set_facecolor(matplotlib.rcParams["figure.facecolor"])
        self._sync_background()
        if self.toolbar:  # иконки панели подбираются под светлый/тёмный фон при создании
            self._layout.removeWidget(self.toolbar)
            self.toolbar.deleteLater()
            self.toolbar = NavigationToolbar2QT(self.canvas, self)
            self._layout.insertWidget(0, self.toolbar)


class CurveReadout:
    """Показания у курсора на графике функций принадлежности.

    При движении мыши над осями рисует вертикальную линию на текущем x,
    точки на кривых и всплывающую подсказку «x = …; μ(x) каждой кривой».

    provider(event) возвращает (ax, rows) или None, где rows — список
    (подпись, цвет, μ или None[, дополнительный текст]); μ = None — кривая
    в этой точке не определена (точка на графике не ставится).
    """

    def __init__(self, plot: PlotWidget, provider):
        self.plot = plot
        self.provider = provider
        self.paused = False  # True — подсказка не показывается (например, пока тянут линию α)
        self._ax = None
        self._tip = ""
        canvas = plot.canvas
        canvas.mpl_connect("motion_notify_event", self._on_move)
        canvas.mpl_connect("axes_leave_event", lambda _e: self.hide())
        canvas.mpl_connect("figure_leave_event", lambda _e: self.hide())

    def _artists(self, ax):
        """Линия и точки создаются заново, если оси очищены или пересозданы."""
        if self._ax is not ax or self._vline.axes is None or self._dots.axes is None:
            self._ax = ax
            fg = matplotlib.rcParams["axes.labelcolor"]
            self._vline = self.plot.add_animated(ax.axvline(0, color=fg, lw=0.8, ls=":", alpha=0.8, zorder=8),
                                                 overlay=True)
            self._dots = self.plot.add_animated(ax.scatter([], [], s=36, zorder=9, edgecolors=fg, linewidths=0.8),
                                                overlay=True)
        return self._vline, self._dots

    def hide(self):
        if self._tip:
            self._tip = ""
            QToolTip.hideText()
        if self._ax is not None and self._vline.axes is not None and self._vline.get_visible():
            self._vline.set_visible(False)
            self._dots.set_visible(False)
            self.plot.update_overlay()

    def _on_move(self, event):
        if self.paused:
            self.hide()
            return
        result = self.provider(event) if event.inaxes is not None else None
        if not result or event.inaxes is not result[0] or event.xdata is None:
            self.hide()
            return
        ax, rows = result
        x = float(event.xdata)
        vline, dots = self._artists(ax)
        points = [(x, mu, color) for _label, color, mu, *_ in rows if mu is not None]
        vline.set_xdata([x, x])
        dots.set_offsets(np.array([(px, py) for px, py, _c in points]) if points else np.empty((0, 2)))
        dots.set_facecolors([c for *_xy, c in points])
        vline.set_visible(True)
        dots.set_visible(True)
        self.plot.update_overlay()

        lines = [f"<b>x = {x:.3f}</b>"]
        for label, color, mu, *extra in rows:
            value = "&lt; 0.05 (вне носителя)" if mu is None else f"{mu:.3f}"
            note = f" {extra[0]}" if extra and extra[0] else ""
            lines.append(f'<span style="color:{color}">■</span> {label}: μ = <b>{value}</b>{note}')
        text = "<br>".join(lines)
        if text != self._tip:
            self._tip = text
            QToolTip.showText(QCursor.pos(), text, self.plot.canvas)


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


class _SideColumn(QWidget):
    def showEvent(self, event):
        # Подписи всех форм колонки — одной ширины, чтобы поля ввода стояли в одну линию.
        # Считается при показе: только тогда шрифт из таблицы стилей уже применён.
        labels = [form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget()
                  for form in self.findChildren(QFormLayout) for row in range(form.rowCount())
                  if form.itemAt(row, QFormLayout.ItemRole.LabelRole) is not None]
        if labels:
            width = max(label.sizeHint().width() for label in labels)
            for label in labels:
                label.setMinimumWidth(width)
        super().showEvent(event)


def side_column(layout: QLayout) -> QScrollArea:
    """Левая колонка вкладки. Без собственных отступов, чтобы карточки слева и справа
    начинались и заканчивались на одной линии.

    Колонка лежит в области прокрутки: если по высоте она не помещается (ноутбук, крупный
    масштаб Windows), появляется полоса прокрутки. Без этого Qt сжимает поля меньше их
    минимального размера, и подписи налезают друг на друга."""
    layout.setContentsMargins(0, 0, 0, 0)
    inner = _SideColumn()
    inner.setLayout(layout)
    area = QScrollArea()
    area.setWidget(inner)
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setFixedWidth(SIDE_WIDTH)
    # прозрачный фон: колонка выглядит так же, как без прокрутки
    area.viewport().setAutoFillBackground(False)
    inner.setAutoFillBackground(False)
    return area


def card(title: str, *widgets: QWidget, stretch: int | None = None) -> QGroupBox:
    """Карточка с заголовком: все блоки интерфейса оформлены одинаково.
    stretch — номер виджета, который забирает свободное место по высоте."""
    box = QGroupBox(title)
    v = QVBoxLayout(box)
    for i, w in enumerate(widgets):
        v.addWidget(w, 1 if i == stretch else 0)
    return box


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
