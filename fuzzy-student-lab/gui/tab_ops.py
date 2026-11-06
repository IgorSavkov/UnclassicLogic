"""Вкладка «Операции»: арифметика и сравнение двух величин."""
from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                             QLabel, QPushButton, QRadioButton, QVBoxLayout, QWidget)

from fuzzy_student import (OPERATION_NAMES, compare, necessity_ge, operate_detailed, possibility_eq,
                           possibility_ge)

from . import theme
from .common import COLOR_A, COLOR_B, COLOR_RESULT, PlotWidget, dspin, show_error

SYMBOLS = {"+": "+", "-": "−", "*": "×", "/": "÷"}


class OpsTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.result = None
        self._last_action = None  # для перерисовки графика при смене темы
        self._build()
        state.set_changed.connect(self.refresh)

    def _build(self):
        root = QHBoxLayout(self)
        left = QVBoxLayout()

        box = QGroupBox("Операнды")
        f = QFormLayout(box)
        self.combo_a = QComboBox()
        self.combo_b = QComboBox()
        f.addRow("A:", self.combo_a)
        self.radio_fuzzy = QRadioButton("B — нечёткая величина")
        self.radio_number = QRadioButton("B — чёткое число")
        self.radio_fuzzy.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.radio_fuzzy)
        group.addButton(self.radio_number)
        f.addRow(self.radio_fuzzy)
        f.addRow("B:", self.combo_b)
        f.addRow(self.radio_number)
        self.spin_c = dspin(-10000, 10000, 2.0)
        self.spin_c.setEnabled(False)
        f.addRow("число c:", self.spin_c)
        self.radio_number.toggled.connect(lambda on: (self.spin_c.setEnabled(on), self.combo_b.setEnabled(not on)))
        left.addWidget(box)

        box_ops = QGroupBox("Действие")
        g = QGridLayout(box_ops)
        for i, op in enumerate("+-*/"):
            b = QPushButton(f"A {SYMBOLS[op]} B")
            b.setToolTip(OPERATION_NAMES[op].capitalize())
            b.clicked.connect(lambda _=False, o=op: self.run_operation(o))
            g.addWidget(b, i // 2, i % 2)
        b_cmp = QPushButton("Сравнить A и B")
        b_cmp.clicked.connect(self.run_compare)
        g.addWidget(b_cmp, 2, 0, 1, 2)
        left.addWidget(box_ops)

        box_res = QGroupBox("Результат")
        v = QVBoxLayout(box_res)
        self.lbl_result = QLabel("Выберите операнды и действие.")
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setMinimumHeight(160)
        v.addWidget(self.lbl_result)
        self.btn_add = QPushButton("Добавить результат в множество")
        self.btn_add.setEnabled(False)
        self.btn_add.clicked.connect(self.add_result)
        v.addWidget(self.btn_add)
        left.addWidget(box_res)
        left.addStretch()

        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(340)
        root.addWidget(left_w)
        self.plot = PlotWidget()
        self.ax = self.plot.figure.add_subplot()
        root.addWidget(self.plot, 1)
        self._draw_placeholder()

    def _draw_placeholder(self):
        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.text(0.5, 0.5, "Выберите A и B и нажмите кнопку действия —\n"
                               "здесь появятся графики операндов и результата",
                     ha="center", va="center", fontsize=11, color=theme.color("fg"), transform=self.ax.transAxes)
        self.plot.draw()

    def refresh(self):
        fs = self.state.fset
        names = [f"{v.name}   T({v.x0:.2f}; {v.s:.2f}; {v.nu:.1f})" for v in fs]
        for combo, default in ((self.combo_a, 0), (self.combo_b, 1)):
            old = combo.currentIndex()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            combo.setCurrentIndex(old if 0 <= old < len(names) else min(default, len(names) - 1))
            combo.blockSignals(False)

    def _operands(self):
        fs = self.state.fset
        ia = self.combo_a.currentIndex()
        if ia < 0:
            raise ValueError("Множество пусто — сначала сгенерируйте или добавьте величины")
        a = fs[ia]
        if self.radio_number.isChecked():
            return a, self.spin_c.value(), f"{self.spin_c.value():g}"
        ib = self.combo_b.currentIndex()
        if ib < 0:
            raise ValueError("Выберите величину B")
        return a, fs[ib], fs[ib].name

    # -------------------------------------------------------------- действия
    def on_theme_changed(self):
        self.plot.retheme()
        self.ax = self.plot.figure.add_subplot()
        if self._last_action is not None:
            self._last_action()
        else:
            self._draw_placeholder()

    def run_operation(self, op: str, log: bool = True):
        try:
            a, b, b_name = self._operands()
            res = operate_detailed(a, b, op, name=f"({a.name}{SYMBOLS[op]}{b_name})")
        except (ValueError, ZeroDivisionError, TypeError) as e:
            if log:
                show_error(self, "Операция", e)
                self.state.journal.error(f"Операция {OPERATION_NAMES[op]}: {e}")
            return
        self._last_action = lambda: self.run_operation(op, log=False)
        self.result = res.value
        r = res.value
        how = ("точно (L-R арифметика, форма сохраняется)" if res.exact
               else f"приближение по α-срезам, отн. ошибка {res.error:.2%}")
        self.lbl_result.setText(
            f"<b>{OPERATION_NAMES[op].capitalize()}</b>: {a.name} {SYMBOLS[op]} {b_name}<br><br>"
            f"Результат: <b>T({r.x0:.4f}; {r.s:.4f}; {r.nu:.2f})</b><br>"
            f"центр x0 = {r.x0:.4f}<br>масштаб s = {r.s:.4f}<br>ν = {r.nu:.2f}<br>"
            f"α-срез 0.5: [{r.alpha_cut(0.5)[0]:.4f}; {r.alpha_cut(0.5)[1]:.4f}]<br><br>"
            f"Способ: {how}")
        self.btn_add.setEnabled(True)
        if log:
            self.state.log(f"Операция {OPERATION_NAMES[op]}: {a} {SYMBOLS[op]} "
                           f"{b if not isinstance(b, float) else b_name} = {r} ({how})")

        ax = self.ax
        ax.clear()
        ax.set_axis_on()
        self._draw_value(a, COLOR_A, f"A = {a.name}")
        if isinstance(b, float):
            ax.axvline(b, color=COLOR_B, lw=2, label=f"B = {b_name} (число)")
        else:
            self._draw_value(b, COLOR_B, f"B = {b.name}")
        xs, ys = res.cuts.polygon()
        ax.plot(xs, ys, color=COLOR_RESULT, lw=2.5, label="результат по α-срезам (точно)")
        ax.fill(xs, ys, color=COLOR_RESULT, alpha=0.12)
        self._draw_value(r, theme.color("fg"), "результат как величина Стьюдента", ls="--", lw=1.4,
                         span=(xs.min(), xs.max()))
        ax.set_title(f"{OPERATION_NAMES[op].capitalize()}: A {SYMBOLS[op]} B")
        self._finish_axes()

    def run_compare(self, log: bool = True):
        try:
            a, b, b_name = self._operands()
        except ValueError as e:
            if log:
                show_error(self, "Сравнение", e)
            return
        self._last_action = lambda: self.run_compare(log=False)
        c = compare(a, b)
        sign = {-1: "<", 0: "=", 1: ">"}[c]
        p_ab, p_ba, p_eq, n_ab = possibility_ge(a, b), possibility_ge(b, a), possibility_eq(a, b), necessity_ge(a, b)
        self.result = None
        self.btn_add.setEnabled(False)
        self.lbl_result.setText(
            f"<b>Сравнение</b> {a.name} и {b_name}<br><br>"
            f"По центрам (дефаззификация): <b>A {sign} B</b><br><br>"
            f"Poss(A ≥ B) = {p_ab:.4f}<br>Poss(B ≥ A) = {p_ba:.4f}<br>"
            f"Nec(A ≥ B) = {n_ab:.4f}<br>"
            f"Poss(A = B) = {p_eq:.4f} — высота пересечения")
        if log:
            self.state.log(f"Сравнение {a} и {b_name}: A {sign} B; Poss(A≥B) = {p_ab:.4f}, "
                           f"Poss(B≥A) = {p_ba:.4f}, Poss(A=B) = {p_eq:.4f}")

        ax = self.ax
        ax.clear()
        ax.set_axis_on()
        self._draw_value(a, COLOR_A, f"A = {a.name}")
        if isinstance(b, float):
            ax.axvline(b, color=COLOR_B, lw=2, label=f"B = {b_name} (число)")
        else:
            self._draw_value(b, COLOR_B, f"B = {b.name}")
        ax.axhline(p_eq, color=theme.color("fg"), ls="--", lw=1, label=f"Poss(A = B) = {p_eq:.3f}")
        ax.set_title(f"Сравнение: A {sign} B")
        self._finish_axes()

    def _draw_value(self, v, color, label, ls="-", lw=2.0, span=None):
        lo, hi = v.alpha_cut(0.02)
        if span is not None:
            lo, hi = min(lo, span[0]), max(hi, span[1])
        xs = np.linspace(lo, hi, 600)
        self.ax.plot(xs, v.membership(xs), color=color, ls=ls, lw=lw, label=label)

    def _finish_axes(self):
        self.ax.set_ylim(0, 1.08)
        self.ax.set_xlabel("x")
        self.ax.set_ylabel("μ(x)")
        self.ax.grid(alpha=0.3)
        self.ax.legend(loc="upper right", fontsize=8)
        self.plot.draw()

    def add_result(self):
        if self.result is not None:
            self.state.add_value(self.result.copy(), f"В множество добавлен результат операции {self.result}")
            self.btn_add.setEnabled(False)
