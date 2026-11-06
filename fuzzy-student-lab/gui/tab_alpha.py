"""Вкладка «α-срез»: все величины на одном графике, уровень α и отбор подмножества."""
from __future__ import annotations

import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                             QListWidget, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget)

from fuzzy_student import SUPPORT_ALPHA

from . import theme
from .common import COLOR_SELECTED, PlotWidget, dspin

MODE_INTERSECT, MODE_POINT = 0, 1


class AlphaTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.scores = np.empty(0)
        self.segments = None
        self.mask = np.empty(0, dtype=bool)
        self._log_timer = QTimer(self, singleShot=True, interval=800)
        self._log_timer.timeout.connect(self._log_alpha)
        self._build()
        state.set_changed.connect(self.on_set_changed)
        state.selection_changed.connect(self.on_selection_changed)

    # ---------------------------------------------------------------- UI
    def _build(self):
        root = QHBoxLayout(self)
        left = QVBoxLayout()

        box_v = QGroupBox("Выбранная величина")
        fv = QFormLayout(box_v)
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._on_combo)
        fv.addRow(self.combo)
        self.lbl = {}
        for key, title in (("x0", "Центр x0:"), ("s", "Масштаб s:"), ("nu", "Степени свободы ν:"),
                           ("L", "Левая граница α-среза:"), ("R", "Правая граница α-среза:"),
                           ("W", "Ширина α-среза:"), ("sup", f"Носитель (α = {SUPPORT_ALPHA}):")):
            self.lbl[key] = QLabel("—")
            self.lbl[key].setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            fv.addRow(title, self.lbl[key])
        left.addWidget(box_v)

        box_a = QGroupBox("Уровень α")
        fa = QVBoxLayout(box_a)
        row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.setValue(50)
        self.spin_alpha = dspin(0.01, 1.0, 0.5, step=0.01, decimals=2)
        self.spin_alpha.setKeyboardTracking(True)
        row.addWidget(self.slider, 1)
        row.addWidget(self.spin_alpha)
        fa.addLayout(row)
        self.slider.valueChanged.connect(lambda v: self._set_alpha(v / 100))
        self.spin_alpha.valueChanged.connect(self._set_alpha)
        left.addWidget(box_a)

        box_c = QGroupBox("Отбор подмножества по α")
        fc = QFormLayout(box_c)
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["α-срез пересекается со срезом выбранной",
                                  "точка x* лежит в α-срезе величины"])
        self.combo_mode.setToolTip(
            "1) B отбирается, если A_α ∩ B_α ≠ ∅, т.е. Poss(A = B) ≥ α — величины, «похожие» на выбранную;\n"
            "2) B отбирается, если μ_B(x*) ≥ α — величины, для которых x* возможно со степенью не ниже α.")
        self.combo_mode.currentIndexChanged.connect(self._on_mode)
        fc.addRow(QLabel("Критерий отбора величины B:"))
        fc.addRow(self.combo_mode)
        self.spin_x = dspin(-10000, 10000, 0.0, step=0.1)
        self.spin_x.setEnabled(False)
        self.spin_x.valueChanged.connect(self._on_point)
        fc.addRow("Точка x*:", self.spin_x)
        self.check_only = QCheckBox("Показать только подмножество (после среза)")
        self.check_only.toggled.connect(self._update_dynamic)
        fc.addRow(self.check_only)
        left.addWidget(box_c)

        self.lbl_count = QLabel()
        self.lbl_count.setObjectName("big")
        left.addWidget(self.lbl_count)
        self.list_subset = QListWidget()
        self.list_subset.itemDoubleClicked.connect(
            lambda item: self.state.select(item.data(Qt.ItemDataRole.UserRole)))
        left.addWidget(self.list_subset, 1)
        self.btn_subset = QPushButton("Сделать подмножество рабочим множеством")
        self.btn_subset.setObjectName("primary")
        self.btn_subset.clicked.connect(self._make_subset)
        self.btn_restore = QPushButton("Вернуть исходное множество")
        self.btn_restore.clicked.connect(self.state.restore_full_set)
        left.addWidget(self.btn_subset)
        left.addWidget(self.btn_restore)

        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(340)
        root.addWidget(left_w)

        self.plot = PlotWidget()
        self.ax = self.plot.figure.add_subplot()
        root.addWidget(self.plot, 1)

    # ----------------------------------------------------------- события
    def alpha(self) -> float:
        return self.spin_alpha.value()

    def _set_alpha(self, a: float):
        a = min(max(float(a), 0.01), 1.0)
        for w, val in ((self.slider, round(a * 100)), (self.spin_alpha, a)):
            w.blockSignals(True)
            w.setValue(val)
            w.blockSignals(False)
        self._update_dynamic()
        self._log_timer.start()

    def _on_combo(self, index: int):
        if index >= 0:
            self.state.select(index)

    def _on_mode(self, mode: int):
        self.spin_x.setEnabled(mode == MODE_POINT)
        if mode == MODE_POINT and self.state.selected_value is not None:
            self.spin_x.blockSignals(True)
            self.spin_x.setValue(self.state.selected_value.x0)
            self.spin_x.blockSignals(False)
        self._refresh()
        self._log_timer.start()

    def _on_point(self, _x):
        self._refresh()
        self._log_timer.start()

    def on_set_changed(self):
        fs = self.state.fset
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems([f"{v.name}   T({v.x0:.2f}; {v.s:.2f}; {v.nu:.1f})" for v in fs])
        self.combo.blockSignals(False)
        self._build_static()
        self._refresh()

    def on_selection_changed(self, index: int):
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)
        self._refresh()

    # ------------------------------------------------------------ график
    def on_theme_changed(self):
        self.plot.retheme()
        self.ax = self.plot.figure.add_subplot()
        self._build_static()
        self._refresh()

    def _build_static(self):
        """Кривые всех величин считаются один раз — при смене множества."""
        ax = self.ax
        ax.clear()
        fs = self.state.fset
        self.segments = None
        if len(fs) == 0:
            ax.text(0.5, 0.5, "Множество пусто — сгенерируйте или добавьте величины",
                    ha="center", va="center", transform=ax.transAxes)
            self.plot.draw()
            return
        lo, hi = fs.bounds(0.02)
        pad = 0.03 * (hi - lo)
        lo, hi = lo - pad, hi + pad
        self.xs = np.linspace(lo, hi, 700)
        p = fs.params()
        t = (self.xs[None, :] - p[:, 0:1]) / p[:, 1:2]
        mu = (1.0 + t * t / p[:, 2:3]) ** (-(p[:, 2:3] + 1.0) / 2.0)
        self.segments = np.stack([np.broadcast_to(self.xs, mu.shape), mu], axis=-1)

        fg, c_pass, c_fail = theme.color("fg"), theme.color("pass"), theme.color("fail")
        self.lc_fail = LineCollection([], colors=c_fail, linewidths=0.6, zorder=1)
        self.lc_pass = LineCollection([], colors=c_pass, linewidths=0.8, alpha=0.8, zorder=2)
        ax.add_collection(self.lc_fail)
        ax.add_collection(self.lc_pass)
        (self.line_sel,) = ax.plot([], [], color=COLOR_SELECTED, lw=2.6, zorder=4)
        self.line_alpha = ax.axhline(0.5, color=fg, ls="--", lw=1.2, zorder=5)
        (self.line_cut,) = ax.plot([], [], color=COLOR_SELECTED, lw=5, alpha=0.7, zorder=6,
                                   solid_capstyle="butt")
        (self.line_l,) = ax.plot([], [], color=COLOR_SELECTED, ls=":", lw=1.2, zorder=6)
        (self.line_r,) = ax.plot([], [], color=COLOR_SELECTED, ls=":", lw=1.2, zorder=6)
        self.line_x = ax.axvline(0, color="#2ca02c", lw=1.8, ls="-.", zorder=6)
        ax.set_xlim(lo, hi)
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("x")
        ax.set_ylabel("μ(x)")
        ax.grid(alpha=0.3)
        ax.legend(handles=[Line2D([], [], color=COLOR_SELECTED, lw=2.6, label="выбранная величина"),
                           Line2D([], [], color=c_pass, lw=1.5, label="подходят под α"),
                           Line2D([], [], color=c_fail, lw=1.5, label="не подходят"),
                           Line2D([], [], color=fg, ls="--", label="уровень α")],
                  loc="upper right", fontsize=8, framealpha=0.9)

    def _refresh(self):
        """Пересчитать оценки величин по критерию (не зависят от α)."""
        fs, v = self.state.fset, self.state.selected_value
        if len(fs) == 0:
            self.scores = np.empty(0)
        elif self.combo_mode.currentIndex() == MODE_POINT:
            self.scores = fs.memberships_at(self.spin_x.value())
        elif v is not None:
            self.scores = fs.heights_with(v)
        else:
            self.scores = np.zeros(len(fs))
        self._update_dynamic()

    def _update_dynamic(self):
        """Быстрое обновление при движении α: только раскраска и линии."""
        fs, v, alpha = self.state.fset, self.state.selected_value, self.alpha()
        n = len(fs)
        self.mask = self.scores >= alpha - 1e-12 if len(self.scores) == n else np.zeros(n, dtype=bool)
        k = int(self.mask.sum())

        self.lbl_count.setText(f"Под уровень α = {alpha:.2f} подходит: <b>{k}</b> из {n}")
        self.list_subset.clear()
        for i in np.flatnonzero(self.mask):
            u = fs[int(i)]
            self.list_subset.addItem(f"{u.name}   x0 = {u.x0:.2f}   степень {self.scores[i]:.2f}")
            self.list_subset.item(self.list_subset.count() - 1).setData(Qt.ItemDataRole.UserRole, int(i))
        self.btn_subset.setEnabled(0 < k < n)
        self.btn_restore.setEnabled(self.state.is_subset)

        if v is not None:
            left, right = v.alpha_cut(alpha)
            self.lbl["x0"].setText(f"{v.x0:.4f}")
            self.lbl["s"].setText(f"{v.s:.4f}")
            self.lbl["nu"].setText(f"{v.nu:.2f}")
            self.lbl["L"].setText(f"{left:.4f}")
            self.lbl["R"].setText(f"{right:.4f}")
            self.lbl["W"].setText(f"{right - left:.4f}")
            sl, sr = v.alpha_cut(SUPPORT_ALPHA)
            self.lbl["sup"].setText(f"[{sl:.3f}; {sr:.3f}]")
        else:
            for w in self.lbl.values():
                w.setText("—")

        if self.segments is None:
            return
        self.lc_pass.set_segments(self.segments[self.mask])
        self.lc_fail.set_segments([] if self.check_only.isChecked() else self.segments[~self.mask])
        self.line_alpha.set_ydata([alpha, alpha])
        if v is not None:
            self.line_sel.set_data(self.xs, v.membership(self.xs))
            self.line_cut.set_data([left, right], [alpha, alpha])
            self.line_l.set_data([left, left], [0, alpha])
            self.line_r.set_data([right, right], [0, alpha])
        point_mode = self.combo_mode.currentIndex() == MODE_POINT
        self.line_x.set_visible(point_mode)
        if point_mode:
            x = self.spin_x.value()
            self.line_x.set_xdata([x, x])
        view = "после среза" if self.check_only.isChecked() else "все величины"
        self.ax.set_title(f"Функции принадлежности ({view}): α = {alpha:.2f}, подходит {k} из {n}")
        self.plot.draw()

    # ----------------------------------------------------------- действия
    def _criterion_text(self) -> str:
        if self.combo_mode.currentIndex() == MODE_POINT:
            return f"μ_B(x*) ≥ α при x* = {self.spin_x.value():.3f}"
        v = self.state.selected_value
        return f"Poss({v.name if v else '?'} = B) ≥ α"

    def _log_alpha(self):
        if len(self.state.fset):
            self.state.log(f"α-срез: α = {self.alpha():.2f}, критерий {self._criterion_text()}: "
                           f"подходит {int(self.mask.sum())} из {len(self.state.fset)}")

    def _make_subset(self):
        indices = [int(i) for i in np.flatnonzero(self.mask)]
        if not indices:
            QMessageBox.information(self, "Подмножество", "Под текущий уровень α не подходит ни одна величина")
            return
        fs = self.state.fset
        sel = self.state.selected
        new_sel = indices.index(sel) if sel in indices else 0
        msg = (f"Выделено подмножество: {len(indices)} из {len(fs)} величин "
               f"(α = {self.alpha():.2f}, {self._criterion_text()})")
        self.state.set_fuzzy_set(fs.subset(indices), msg, is_subset=True, selected=new_sel)
