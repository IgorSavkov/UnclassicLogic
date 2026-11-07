"""Вкладка «Кластеризация»: дендрограмма + величины, раскрашенные по кластерам."""
from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout,
                             QHBoxLayout, QHeaderView,
                             QLabel,
                             QRadioButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                             QToolTip, QVBoxLayout, QWidget)
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, NullFormatter
from scipy.cluster.hierarchy import dendrogram

from fuzzy_student import METHODS, ClusterAnalysis

from . import theme
from .common import NumItem, PlotWidget, card, cluster_colors, show_error

SUMMARY_COLUMNS = ["Кластер", "Размер", "Средний центр x0", "Центры от", "Центры до", "Средний s", "Среднее ν",
                   "Состав"]
HOVER_RADIUS_PX = 7       # насколько близко к точке должен быть курсор
HOVER_MAX_ITEMS = 12      # сколько величин перечислять в подсказке
LEGEND_MAX_K = 12         # легенда — только при небольшом числе кластеров
LABELS_MAX_K = 20         # номера кластеров в кружках — только при небольшом числе кластеров
SIZES_MAX_SHOWN = 15      # сколько размеров кластеров перечислять в подписи
GRAB_PX = 6               # насколько близко к линии среза надо нажать, чтобы её потянуть


def sizes_text(sizes: list[int]) -> str:
    """Размеры кластеров для подписи и журнала; длинный список сокращается."""
    if len(sizes) <= SIZES_MAX_SHOWN:
        return str(sizes)
    head = ", ".join(map(str, sizes[:SIZES_MAX_SHOWN]))
    return f"[{head}, … ещё {len(sizes) - SIZES_MAX_SHOWN}] (от {min(sizes)} до {max(sizes)})"


class ThresholdSpin(QDoubleSpinBox):
    """Поле порога расстояния h.

    Стрелки, колесо мыши и PageUp/PageDown переводят срез к соседнему уровню дерева —
    середине между соседними высотами слияний. Один шаг меняет число кластеров ровно на 1
    (PageUp/PageDown — на 10). С постоянным шагом стрелки то перепрыгивали через десятки
    уровней внизу дерева, то ничего не меняли наверху. Вручную можно ввести любое h."""

    def __init__(self):
        super().__init__()
        self.setRange(0.0, 1e6)
        self.setDecimals(4)
        self.setKeyboardTracking(False)
        self.levels = np.empty(0)

    def set_heights(self, heights):
        h = np.sort(np.asarray(heights, dtype=float))
        if len(h) == 0:
            self.levels = np.empty(0)
            return
        # 0 — каждая величина отдельно; середины между слияниями — k = n-1 … 2; выше корня — k = 1
        levels = np.concatenate([[0.0], (h[:-1] + h[1:]) / 2, [h[-1] * 1.05]])
        self.levels = np.unique(np.round(levels, self.decimals()))

    def stepBy(self, steps: int):
        if len(self.levels) == 0:
            super().stepBy(steps)
            return
        cur = round(self.value(), self.decimals())
        if steps > 0:   # вверх: первый уровень выше текущего, затем ещё steps-1
            i = np.searchsorted(self.levels, cur, side="right") + steps - 1
        else:           # вниз: последний уровень ниже текущего, затем ещё |steps|-1
            i = np.searchsorted(self.levels, cur, side="left") + steps
        self.setValue(float(self.levels[int(np.clip(i, 0, len(self.levels) - 1))]))


class ClusterTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.analysis: ClusterAnalysis | None = None
        self.labels = None
        self._scatter = None     # все точки — одна коллекция (цвет каждой точки — цвет её кластера)
        self._point_rgba = None  # исходные цвета точек (для подсветки кластера)
        self._groups = []        # индексы величин каждого кластера (считаются один раз за перерисовку)
        self._centers = None     # центры кластеров на плоскости (x0, s)
        self._tip = ""
        self._quiet = False  # перерисовка без записи в журнал (смена темы)
        self._log_timer = QTimer(self, singleShot=True, interval=700)
        self._log_timer.timeout.connect(self._log_result)
        # линия среза на дендрограмме: её можно тянуть мышью
        self._cut_line = None
        self._cut_text = None
        self._drag_h: float | None = None  # порог, до которого дотянули линию (None — не тянут)
        self._cursor = None
        # пока тянут, линия двигается сразу, а дерево перекрашивается, когда мышь остановилась
        # (полная перерисовка дендрограммы — доли секунды, на каждое движение она не успевает)
        self._drag_timer = QTimer(self, singleShot=True, interval=150)
        self._drag_timer.timeout.connect(self._apply_drag)
        self._build()
        state.set_changed.connect(self.recompute)

    def _build(self):
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.radio_k = QRadioButton("Количество кластеров k:")
        self.radio_h = QRadioButton("По критерию — порог расстояния h:")
        self.radio_k.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.radio_k)
        group.addButton(self.radio_h)
        self.spin_k = QSpinBox()
        self.spin_k.setRange(1, 300)
        self.spin_k.setValue(7)
        self.spin_h = ThresholdSpin()
        self.spin_h.setValue(1.0)
        self.spin_h.setToolTip("Порог расстояния h: сливаются кластеры, расстояние между которыми меньше h.\n"
                               "Стрелки и колесо — к соседнему уровню дерева (число кластеров ±1),\n"
                               "PageUp/PageDown — ±10 кластеров. Можно ввести любое значение вручную.")
        self.spin_h.setEnabled(False)
        self.combo_method = QComboBox()
        for key, title in METHODS.items():
            self.combo_method.addItem(f"метод {title}", key)
        # две строки, а не одна: в одну строку панель не помещалась на узком экране
        bar.setContentsMargins(0, 0, 0, 0)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.addWidget(self.radio_k, 0, 0)
        grid.addWidget(self.spin_k, 0, 1)
        grid.addWidget(self.radio_h, 1, 0)
        grid.addWidget(self.spin_h, 1, 1)
        bar.addLayout(grid)
        bar.addSpacing(24)
        self.check_log = QCheckBox("Логарифмическая шкала высот")
        self.check_log.setChecked(True)
        self.check_log.setToolTip(
            "Верхние слияния дерева происходят на высоте в десятки раз больше, чем внутри кластеров.\n"
            "На линейной шкале кластеры и линия среза сжимаются в узкую полосу у нижнего края;\n"
            "на логарифмической видно всё дерево. Подписи оси — настоящие расстояния.")
        method = QGridLayout()
        method.setContentsMargins(0, 0, 0, 0)
        method.addWidget(QLabel("Связь кластеров:"), 0, 0)
        method.addWidget(self.combo_method, 0, 1)
        method.addWidget(self.check_log, 1, 0, 1, 2)
        bar.addLayout(method)
        bar.addSpacing(24)
        # итог — справа от параметров, а не отдельной строкой: по высоте место нужнее графику
        self.lbl_info = QLabel()
        self.lbl_info.setObjectName("big")
        self.lbl_info.setWordWrap(True)  # иначе длинный список размеров кластеров распирает окно
        bar.addWidget(self.lbl_info, 1)
        bar_w = QWidget()
        bar_w.setLayout(bar)
        root.addWidget(card("Параметры кластеризации", bar_w))

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.plot = PlotWidget()
        self._create_axes()
        plot_hint = QLabel("Линию среза на дендрограмме можно тянуть мышью: в режиме k она встаёт на ближайший "
                           "уровень дерева, в режиме «по критерию» задаёт порог h.")
        plot_hint.setWordWrap(True)
        plot_hint.setObjectName("hint")
        splitter.addWidget(card("Дендрограмма и величины по кластерам", self.plot, plot_hint, stretch=0))
        self.table = QTableWidget(0, len(SUMMARY_COLUMNS))
        self.table.setHorizontalHeaderLabels(SUMMARY_COLUMNS)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(SUMMARY_COLUMNS) - 1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._highlight_selected)
        self.table.setToolTip("Щёлкните строку, чтобы выделить кластер на графике")
        splitter.addWidget(card("Состав кластеров", self.table, stretch=0))
        splitter.setSizes([600, 200])
        # при изменении высоты окна график получает втрое больше, чем таблица
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.spin_k.valueChanged.connect(self.redraw)
        self.spin_h.valueChanged.connect(self.redraw)
        self.radio_k.toggled.connect(self._on_mode)
        self.combo_method.currentIndexChanged.connect(self.recompute)
        self.check_log.toggled.connect(self._redraw_quiet)
        self.plot.canvas.mpl_connect("motion_notify_event", self._on_hover)
        self.plot.canvas.mpl_connect("axes_leave_event", lambda _e: self._hide_tip())
        self.plot.canvas.mpl_connect("button_press_event", self._on_press)
        self.plot.canvas.mpl_connect("motion_notify_event", self._on_drag_motion)
        self.plot.canvas.mpl_connect("button_release_event", self._on_release)

    def _create_axes(self):
        grid = self.plot.figure.add_gridspec(1, 2, width_ratios=[1.15, 1])
        self.ax_tree = self.plot.figure.add_subplot(grid[0])
        self.ax_points = self.plot.figure.add_subplot(grid[1])

    def on_theme_changed(self):
        self.plot.retheme()
        self._create_axes()
        self._redraw_quiet()

    def _redraw_quiet(self):
        """Перерисовать без записи в журнал: разбиение не изменилось (тема, шкала)."""
        self._quiet = True
        try:
            self.redraw()
        finally:
            self._quiet = False

    # ------------------------------------------------------------- логика
    def _on_mode(self, by_k: bool):
        self.spin_k.setEnabled(by_k)
        self.spin_h.setEnabled(not by_k)
        if self.analysis is not None and self.labels is not None:
            k = int(self.labels.max()) + 1
            if by_k:
                self.spin_k.blockSignals(True)
                self.spin_k.setValue(k)
                self.spin_k.blockSignals(False)
            else:
                self.spin_h.blockSignals(True)
                self.spin_h.setValue(self.analysis.threshold_for(k))
                self.spin_h.blockSignals(False)
        self.redraw()

    def recompute(self):
        """Построить дерево заново (новое множество или другой метод)."""
        items = list(self.state.fset)
        self.analysis = None
        if len(items) >= 2:
            try:
                self.analysis = ClusterAnalysis(items, self.combo_method.currentData())
            except ValueError as e:
                show_error(self, "Кластеризация", e)
        if self.analysis is not None:
            n = self.analysis.n
            self.spin_k.blockSignals(True)
            self.spin_k.setMaximum(n)
            self.spin_k.blockSignals(False)
            self.spin_h.blockSignals(True)
            self.spin_h.setMaximum(self.analysis.max_height * 1.05)  # = верхний уровень (k = 1)
            self.spin_h.set_heights(self.analysis.linkage[:, 2])
            if self.radio_h.isChecked():
                self.spin_h.setValue(self.analysis.threshold_for(min(self.spin_k.value(), n)))
            self.spin_h.blockSignals(False)
        self.redraw()

    def redraw(self):
        for ax in (self.ax_tree, self.ax_points):
            ax.clear()
        ca = self.analysis
        if ca is None:
            self.labels = None
            self.lbl_info.setText("Для кластеризации нужно хотя бы 2 величины.")
            self.table.setRowCount(0)
            self.plot.draw()
            return

        if self.radio_k.isChecked():
            k = self.spin_k.value()
            labels = ca.labels_for_k(k)
            threshold = ca.threshold_for(k)
            criterion = f"задано k = {k}"
        else:
            threshold = self.spin_h.value()
            labels = ca.labels_for_threshold(threshold)
            criterion = f"порог h = {threshold:.3f}"
        self.labels = labels
        k = int(labels.max()) + 1
        colors = cluster_colors(k)
        nodes = ca.node_labels(labels)

        # дендрограмма: ветви внутри кластера — цветом кластера, выше среза — серые
        fg, above = theme.color("fg"), theme.color("above_cut")
        dendrogram(ca.linkage, ax=self.ax_tree, no_labels=True,
                   link_color_func=lambda i: colors[nodes[i]] if nodes[i] >= 0 else above)
        line_y = threshold
        if self.check_log.isChecked():
            # h = 0 на логарифмической оси не существует — линию среза рисуем у нижнего края
            low = self._log_scale(ca.linkage[:, 2], threshold)
            if threshold <= 0:
                line_y = low * 1.2
        # линия среза и подпись — в динамическом слое: при перетаскивании двигаются без перерисовки дерева
        self._cut_line = self.plot.add_animated(self.ax_tree.axhline(line_y, color=fg, ls="--", lw=1.6))
        self._cut_text = self.plot.add_animated(
            self.ax_tree.text(0.01, line_y, f" срез: {k} кл.", transform=self.ax_tree.get_yaxis_transform(),
                              va="bottom", fontsize=8))
        self.ax_tree.set_title(f"Дендрограмма — метод {METHODS[ca.method]}")
        self.ax_tree.set_ylabel("расстояние между кластерами")
        self.ax_tree.set_xlabel(f"{ca.n} величин (листья дерева)")

        # Все точки — одной коллекцией: при 200 кластерах 200 отдельных scatter рисовались секундами.
        groups = ca.groups(labels)
        self._groups = groups
        p = np.array([[v.x0, v.s] for v in ca.items])
        self._points, self._colors = p, colors
        rgba = np.array([to_rgba(c) for c in colors])
        self._point_rgba = rgba[labels]
        self._scatter = self.ax_points.scatter(p[:, 0], p[:, 1], s=26, c=self._point_rgba,
                                               edgecolors="white", linewidths=0.4)
        self._centers = np.array([p[idx].mean(axis=0) for idx in groups])
        if k <= LABELS_MAX_K:  # при сотне кластеров номера в кружках только закрывают точки
            for c, center in enumerate(self._centers):
                self.ax_points.annotate(str(c + 1), center, fontsize=10, fontweight="bold", ha="center",
                                        va="center", color="white",
                                        bbox=dict(boxstyle="circle,pad=0.2", fc=colors[c], ec=fg, lw=0.6))
        self.ax_points.set_title("Величины по кластерам (центр x0, масштаб s)")
        self.ax_points.set_xlabel("центр x0")
        self.ax_points.set_ylabel("масштаб s")
        self.ax_points.grid(alpha=0.3)
        if k <= LEGEND_MAX_K:
            handles = [Line2D([], [], ls="none", marker="o", markersize=6, markerfacecolor=colors[c],
                              markeredgecolor="white", label=f"кластер {c + 1} ({len(idx)})")
                       for c, idx in enumerate(groups)]
            self.ax_points.legend(handles=handles, fontsize=7, loc="best", framealpha=0.85)
        self.plot.draw()

        sizes = [len(g) for g in groups]
        self.lbl_info.setText(f"Кластеров: <b>{k}</b> ({criterion}, порог среза h = {threshold:.4g}); "
                              f"размеры: {sizes_text(sizes)}")
        self._fill_table(ca.summary(labels), colors)
        if not self._quiet:
            self._log_timer.start()

    def _log_scale(self, heights: np.ndarray, threshold: float) -> float:
        """Логарифмическая ось высот дендрограммы; возвращает нижнюю границу оси.

        Листья стоят на высоте 0, которой на логарифмической оси нет: их вертикальные линии
        просто уходят к нижнему краю. Низ оси — чуть ниже самого низкого слияния (и среза)."""
        positive = heights[heights > 0]
        if len(positive) == 0:
            return 0.0
        low = min(float(positive.min()), threshold if threshold > 0 else np.inf) * 0.6
        self.ax_tree.set_yscale("log", nonpositive="clip")
        self.ax_tree.set_ylim(low, float(heights.max()) * 1.4)
        self.ax_tree.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: f"{v:g}"))
        self.ax_tree.yaxis.set_minor_formatter(NullFormatter())
        return low

    def _fill_table(self, rows, colors):
        # Столбцы «по содержимому» пересчитывают ширину по всем строкам после КАЖДОЙ вставленной
        # ячейки: при 200 кластерах заполнение шло ~18 с, и окно «не отвечало». Поэтому на время
        # заполнения режим отключается, а ширина считается один раз в конце.
        header = self.table.horizontalHeader()
        last = len(SUMMARY_COLUMNS) - 1
        for col in range(last):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self.table.setUpdatesEnabled(False)
        try:
            self._fill_rows(rows, colors)
        finally:
            for col in range(last):
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            self.table.setUpdatesEnabled(True)

    def _fill_rows(self, rows, colors):
        self.table.clearSelection()
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            item = QTableWidgetItem(f"  {row['cluster'] + 1}")
            item.setBackground(QColor(colors[r]))
            item.setForeground(QColor("white"))
            self.table.setItem(r, 0, item)
            for col, key, digits in ((1, "size", 0), (2, "x0_mean", 3), (3, "x0_min", 3), (4, "x0_max", 3),
                                     (5, "s_mean", 3), (6, "nu_mean", 2)):
                self.table.setItem(r, col, NumItem(row[key], digits))
            names = [self.analysis.items[i].name for i in self._groups[r]]
            members = QTableWidgetItem(", ".join(names))
            members.setToolTip("<br>".join(", ".join(names[i:i + 8]) for i in range(0, len(names), 8)))
            self.table.setItem(r, 7, members)

    # ------------------------------------------------- выделение кластера
    def _highlight_selected(self):
        if self._scatter is None or self.labels is None:
            return
        rows = {i.row() for i in self.table.selectedIndexes()}
        selected = rows.pop() if rows else None
        face = self._point_rgba.copy()
        edge = np.tile(to_rgba("white"), (len(face), 1))
        if selected is not None:  # точки остальных кластеров — почти прозрачные
            others = self.labels != selected
            face[others, 3] = 0.12
            edge[others, 3] = 0.12
        self._scatter.set_facecolors(face)
        self._scatter.set_edgecolors(edge)
        self.plot.draw()

    # ------------------------------------------- перетаскивание линии среза
    def _toolbar_busy(self) -> bool:
        toolbar = self.plot.toolbar
        return toolbar is not None and bool(toolbar.mode)

    def _near_cut(self, event) -> bool:
        """Курсор у линии среза (по вертикали ближе GRAB_PX пикселей)."""
        if self._cut_line is None or event.inaxes is not self.ax_tree or event.y is None:
            return False
        py = self.ax_tree.transData.transform((0, self._cut_line.get_ydata()[0]))[1]
        return abs(event.y - py) <= GRAB_PX

    def _k_at(self, h: float) -> int:
        """Число кластеров при срезе на высоте h: выполнены все слияния не выше h."""
        return self.analysis.n - int(np.count_nonzero(self.analysis.linkage[:, 2] <= h))

    def _on_press(self, event):
        if (event.button == 1 and not event.dblclick and not self._toolbar_busy()
                and self.analysis is not None and self._near_cut(event)):
            self._drag_h = float(self._cut_line.get_ydata()[0])
            self._hide_tip()

    def _on_drag_motion(self, event):
        if self._drag_h is None:
            # над линией среза — курсор-«двусторонняя стрелка»: её можно потянуть
            shape = Qt.CursorShape.SizeVerCursor if not self._toolbar_busy() and self._near_cut(event) else None
            if shape != self._cursor:
                self._cursor = shape
                if shape is None:
                    self.plot.canvas.unsetCursor()
                else:
                    self.plot.canvas.setCursor(shape)
            return
        if event.x is None or self._cut_line is None:
            return
        y = float(self.ax_tree.transData.inverted().transform((event.x, event.y))[1])
        self._drag_h = float(np.clip(y, 0.0, self.analysis.max_height * 1.05))
        lo, hi = sorted(self.ax_tree.get_ylim())
        line_y = min(max(y, lo), hi)  # линия не уходит за пределы осей
        self._cut_line.set_ydata([line_y, line_y])
        self._cut_text.set_y(line_y)
        self._cut_text.set_text(f" срез: {self._k_at(self._drag_h)} кл., h = {self._drag_h:.3g}")
        self.plot.update_animated()
        self._drag_timer.start()

    def _on_release(self, _event):
        if self._drag_h is not None:
            self._drag_timer.stop()
            self._apply_drag()
            self._drag_h = None

    def _apply_drag(self):
        """Применить порог, до которого дотянули линию: в режиме k — число кластеров на этой
        высоте (линия встаёт на уровень дерева), в режиме «по критерию» — сам порог h."""
        if self._drag_h is None or self.analysis is None:
            return
        if self.radio_k.isChecked():
            self.spin_k.setValue(max(1, self._k_at(self._drag_h)))
        else:
            self.spin_h.setValue(self._drag_h)

    # ------------------------------------------------ подсказка у курсора
    def _hide_tip(self):
        if self._tip:
            self._tip = ""
            QToolTip.hideText()

    def _on_hover(self, event):
        """Какие величины (и центр какого кластера) под курсором."""
        if (self._drag_h is not None or event.inaxes is not self.ax_points or self.labels is None
                or self._centers is None
                or event.x is None):
            self._hide_tip()
            return
        to_px = self.ax_points.transData.transform
        cursor = np.array([event.x, event.y])
        lines = []
        d_center = np.hypot(*(to_px(self._centers) - cursor).T)
        for c in np.flatnonzero(d_center < 2 * HOVER_RADIUS_PX):
            idx = self._groups[c]
            x0m, sm = self._centers[c]
            lines.append(f'<span style="color:{self._colors[c]}">●</span> <b>центр кластера {c + 1}</b>: '
                         f'{len(idx)} величин, x̄<sub>0</sub> = {x0m:.3f}, s̄ = {sm:.3f}')
        d = np.hypot(*(to_px(self._points) - cursor).T)
        hits = np.argsort(d)[:np.count_nonzero(d < HOVER_RADIUS_PX)]
        for i in hits[:HOVER_MAX_ITEMS]:
            v, c = self.analysis.items[i], int(self.labels[i])
            lines.append(f'<span style="color:{self._colors[c]}">■</span> <b>{v.name}</b> '
                         f'T({v.x0:.3f}; {v.s:.3f}; {v.nu:g}) — кластер {c + 1}')
        if len(hits) > HOVER_MAX_ITEMS:
            lines.append(f"… и ещё {len(hits) - HOVER_MAX_ITEMS}")
        if not lines:
            self._hide_tip()
            return
        text = "<br>".join(lines)
        if text != self._tip:
            self._tip = text
            QToolTip.showText(QCursor.pos(), text, self.plot.canvas)

    def _log_result(self):
        if self.analysis is None or self.labels is None:
            return
        sizes = [len(g) for g in self._groups]
        mode = (f"k = {self.spin_k.value()}" if self.radio_k.isChecked()
                else f"порог h = {self.spin_h.value():.4g}")
        self.state.log(f"Кластеризация (метод {METHODS[self.analysis.method]}, {mode}): "
                       f"{len(sizes)} кластеров, размеры {sizes_text(sizes)}")
