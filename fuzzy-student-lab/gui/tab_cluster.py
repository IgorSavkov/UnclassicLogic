"""Вкладка «Кластеризация»: дендрограмма + величины, раскрашенные по кластерам."""
from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QHBoxLayout, QHeaderView, QLabel,
                             QRadioButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QWidget)
from scipy.cluster.hierarchy import dendrogram

from fuzzy_student import METHODS, ClusterAnalysis

from . import theme
from .common import NumItem, PlotWidget, cluster_colors, dspin, show_error

SUMMARY_COLUMNS = ["Кластер", "Размер", "Средний центр x0", "Центры от", "Центры до", "Средний s", "Среднее ν"]


class ClusterTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.analysis: ClusterAnalysis | None = None
        self.labels = None
        self._quiet = False  # перерисовка без записи в журнал (смена темы)
        self._log_timer = QTimer(self, singleShot=True, interval=700)
        self._log_timer.timeout.connect(self._log_result)
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
        self.spin_h = dspin(0.0, 1e6, 1.0, step=0.1)
        self.spin_h.setEnabled(False)
        self.combo_method = QComboBox()
        for key, title in METHODS.items():
            self.combo_method.addItem(f"метод {title}", key)
        bar.addWidget(self.radio_k)
        bar.addWidget(self.spin_k)
        bar.addSpacing(20)
        bar.addWidget(self.radio_h)
        bar.addWidget(self.spin_h)
        bar.addSpacing(20)
        bar.addWidget(QLabel("Связь кластеров:"))
        bar.addWidget(self.combo_method)
        bar.addStretch()
        root.addLayout(bar)

        self.lbl_info = QLabel()
        self.lbl_info.setObjectName("big")
        root.addWidget(self.lbl_info)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.plot = PlotWidget()
        self._create_axes()
        splitter.addWidget(self.plot)
        self.table = QTableWidget(0, len(SUMMARY_COLUMNS))
        self.table.setHorizontalHeaderLabels(SUMMARY_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.table)
        splitter.setSizes([560, 170])
        root.addWidget(splitter, 1)

        self.spin_k.valueChanged.connect(self.redraw)
        self.spin_h.valueChanged.connect(self.redraw)
        self.radio_k.toggled.connect(self._on_mode)
        self.combo_method.currentIndexChanged.connect(self.recompute)

    def _create_axes(self):
        grid = self.plot.figure.add_gridspec(1, 2, width_ratios=[1.15, 1])
        self.ax_tree = self.plot.figure.add_subplot(grid[0])
        self.ax_points = self.plot.figure.add_subplot(grid[1])

    def on_theme_changed(self):
        self.plot.retheme()
        self._create_axes()
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
            self.spin_h.setMaximum(self.analysis.max_height * 1.2)
            self.spin_h.setSingleStep(max(self.analysis.max_height / 200, 0.001))
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
        self.ax_tree.axhline(threshold, color=fg, ls="--", lw=1.2)
        self.ax_tree.text(0.01, threshold, f" срез: {k} кл.", transform=self.ax_tree.get_yaxis_transform(),
                          va="bottom", fontsize=8)
        self.ax_tree.set_title(f"Дендрограмма — метод {METHODS[ca.method]}")
        self.ax_tree.set_ylabel("расстояние между кластерами")
        self.ax_tree.set_xlabel(f"{ca.n} величин (листья дерева)")

        p = np.array([[v.x0, v.s] for v in ca.items])
        for c, idx in enumerate(ca.groups(labels)):
            q = p[idx]
            self.ax_points.scatter(q[:, 0], q[:, 1], s=26, color=colors[c], edgecolors="white", linewidths=0.4,
                                   label=f"кластер {c + 1} ({len(idx)})")
            self.ax_points.annotate(str(c + 1), q.mean(axis=0), fontsize=10, fontweight="bold", ha="center",
                                    va="center", color="white",
                                    bbox=dict(boxstyle="circle,pad=0.2", fc=colors[c], ec=fg, lw=0.6))
        self.ax_points.set_title("Величины по кластерам (центр x0, масштаб s)")
        self.ax_points.set_xlabel("центр x0")
        self.ax_points.set_ylabel("масштаб s")
        self.ax_points.grid(alpha=0.3)
        if k <= 12:
            self.ax_points.legend(fontsize=7, loc="best", framealpha=0.85)
        self.plot.draw()

        sizes = [len(g) for g in ca.groups(labels)]
        self.lbl_info.setText(f"Кластеров: <b>{k}</b> ({criterion}, порог среза h = {threshold:.3f}); "
                              f"размеры: {sizes}")
        self._fill_table(ca.summary(labels), colors)
        if not self._quiet:
            self._log_timer.start()

    def _fill_table(self, rows, colors):
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            item = QTableWidgetItem(f"  {row['cluster'] + 1}")
            item.setBackground(QColor(colors[r]))
            item.setForeground(QColor("white"))
            self.table.setItem(r, 0, item)
            for col, key, digits in ((1, "size", 0), (2, "x0_mean", 3), (3, "x0_min", 3), (4, "x0_max", 3),
                                     (5, "s_mean", 3), (6, "nu_mean", 2)):
                self.table.setItem(r, col, NumItem(row[key], digits))

    def _log_result(self):
        if self.analysis is None or self.labels is None:
            return
        sizes = [len(g) for g in self.analysis.groups(self.labels)]
        mode = (f"k = {self.spin_k.value()}" if self.radio_k.isChecked()
                else f"порог h = {self.spin_h.value():.3f}")
        self.state.log(f"Кластеризация (метод {METHODS[self.analysis.method]}, {mode}): "
                       f"{len(sizes)} кластеров, размеры {sizes}")
