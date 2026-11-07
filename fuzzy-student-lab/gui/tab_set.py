"""Вкладка «Множество»: генерация, ручной ввод, таблица величин, файлы."""
from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from fuzzy_student import SUPPORT_ALPHA, FuzzySet, StudentFuzzy, generate_set

from . import theme
from .common import (COLOR_SELECTED, CurveReadout, NumItem, PlotWidget, app_dir, card, dspin, show_error,
                     side_column)

COLUMNS = ["Имя", "Центр x0", "Масштаб s", "ν", "Левая граница*", "Правая граница*"]
# параметры для отбора: ключ filter_by_params, подпись, (min, max, шаг, знаков)
FILTER_PARAMS = (("x0", "Центр x0", (-10000, 10000, 0.1, 3)),
                 ("s", "Масштаб s", (0.0, 10000, 0.05, 3)),
                 ("nu", "Степени свободы ν", (1, 1000, 1, 0)))


class SetTab(QWidget):
    open_requested = pyqtSignal(int)  # двойной щелчок по величине

    def __init__(self, state):
        super().__init__()
        self.state = state
        self._build()
        state.set_changed.connect(self.refresh)
        state.selection_changed.connect(self._select_row)
        self._update_preview()

    # ---------------------------------------------------------------- UI
    def _build(self):
        root = QHBoxLayout(self)

        left = QVBoxLayout()
        gen = QGroupBox("Генерация набора величин")
        f = QFormLayout(gen)
        self.spin_n = QSpinBox()
        self.spin_n.setRange(100, 300)
        self.spin_n.setValue(200)
        self.spin_n.setSingleStep(1)  # стрелки/колесо — по 1, PageUp/PageDown — по 10
        self.spin_n.setToolTip("Любое целое от 100 до 300 (диапазон по заданию).\n"
                               "Стрелки и колесо мыши — шаг 1, PageUp/PageDown — шаг 10")
        self.spin_groups = QSpinBox()
        self.spin_groups.setRange(0, 12)
        self.spin_groups.setValue(5)
        self.spin_groups.setToolTip("0 — параметры полностью случайны;\n"
                                    "k > 0 — величины разбросаны вокруг k «типичных» (видны кластеры)")
        self.edit_seed = QLineEdit()
        self.edit_seed.setPlaceholderText("случайное")
        self.edit_seed.setToolTip("Одинаковое зерно даёт одинаковый набор — удобно для повторения опыта")
        f.addRow("Количество (100–300):", self.spin_n)
        f.addRow("Число групп:", self.spin_groups)
        f.addRow("Зерно (seed):", self.edit_seed)
        btn_gen = QPushButton("Сгенерировать")
        btn_gen.setObjectName("primary")
        btn_gen.clicked.connect(self.generate)
        f.addRow(btn_gen)
        left.addWidget(gen)

        man = QGroupBox("Ручной ввод величины T(x0; s; ν)")
        f2 = QFormLayout(man)
        self.sp_x0 = dspin(-10000, 10000, 0.0)
        self.sp_s = dspin(0.001, 10000, 1.0)
        self.sp_nu = dspin(1, 1000, 5.0, step=1, decimals=0)
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("авто")
        f2.addRow("Центр x0:", self.sp_x0)
        f2.addRow("Масштаб s:", self.sp_s)
        f2.addRow("Степени свободы ν:", self.sp_nu)
        f2.addRow("Имя:", self.ed_name)
        self.preview = PlotWidget(toolbar=False)
        self.preview.setMinimumHeight(150)
        self.preview_ax = self.preview.figure.add_subplot()
        f2.addRow(self.preview)
        CurveReadout(self.preview, self._preview_rows)
        btn_add = QPushButton("Добавить в множество")
        btn_add.clicked.connect(self.add_manual)
        f2.addRow(btn_add)
        for sp in (self.sp_x0, self.sp_s, self.sp_nu):
            sp.valueChanged.connect(self._update_preview)
        left.addWidget(man)

        files = QGroupBox("Действия с множеством")
        g = QGridLayout(files)
        buttons = [("Сохранить…", self.save), ("Загрузить…", self.load),
                   ("Удалить выделенные", self.delete_selected), ("Очистить", self.clear),
                   ("Вывести в журнал", self.dump_to_journal)]
        for i, (text, slot) in enumerate(buttons):
            b = QPushButton(text)
            b.clicked.connect(slot)
            g.addWidget(b, i // 2, i % 2)
        left.addWidget(files)
        left.addStretch()

        root.addWidget(side_column(left))

        right = QVBoxLayout()
        right.addWidget(self._build_filter())
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.cellDoubleClicked.connect(lambda row, _c: self.open_requested.emit(self._row_index(row)))
        hint = QLabel(f"* практические границы носителя — α-срез на уровне α = {SUPPORT_ALPHA}. "
                      "Двойной щелчок по строке — открыть величину на вкладке «α-срез». "
                      "Щелчок по заголовку столбца — сортировка.")
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        # заголовок карточки показывает размер множества (обновляется в refresh)
        self.table_box = card("Множество", self.table, hint, stretch=0)
        right.addWidget(self.table_box, 1)
        root.addLayout(right, 1)

    def _build_filter(self) -> QGroupBox:
        """Блок «Подмножество по параметрам»: x0, s, ν в заданных диапазонах."""
        box = QGroupBox("Подмножество по параметрам (условия объединяются по «И»)")
        g = QGridLayout(box)
        self.flt = {}
        for row, (key, title, (lo, hi, step, digits)) in enumerate(FILTER_PARAMS):
            check = QCheckBox(title)
            sp_lo, sp_hi = dspin(lo, hi, lo, step, digits), dspin(lo, hi, hi, step, digits)
            check.toggled.connect(self._update_filter)
            for sp in (sp_lo, sp_hi):
                # правка границы сразу включает условие
                sp.valueChanged.connect(lambda _v, c=check: c.setChecked(True) if not c.isChecked()
                                        else self._update_filter())
            g.addWidget(check, row, 0)
            g.addWidget(QLabel("от"), row, 1)
            g.addWidget(sp_lo, row, 2)
            g.addWidget(QLabel("до"), row, 3)
            g.addWidget(sp_hi, row, 4)
            self.flt[key] = (check, sp_lo, sp_hi)
        g.setColumnStretch(2, 1)
        g.setColumnStretch(4, 1)
        self.lbl_filter = QLabel()
        self.lbl_filter.setObjectName("big")
        self.btn_filter = QPushButton("Сделать подмножество рабочим множеством")
        self.btn_filter.setObjectName("primary")
        self.btn_filter.clicked.connect(self._make_filter_subset)
        self.btn_filter_restore = QPushButton("Вернуть исходное множество")
        self.btn_filter_restore.clicked.connect(self.state.restore_full_set)
        btn_reset = QPushButton("Сбросить условия")
        btn_reset.clicked.connect(self._reset_filter)
        g.addWidget(self.lbl_filter, 0, 5, 1, 2)
        g.addWidget(self.btn_filter, 1, 5, 1, 2)
        g.addWidget(self.btn_filter_restore, 2, 5)
        g.addWidget(btn_reset, 2, 6)
        return box

    def _filter_conditions(self) -> dict:
        """Включённые условия в виде аргументов FuzzySet.filter_by_params."""
        cond = {}
        for key, (check, sp_lo, sp_hi) in self.flt.items():
            if check.isChecked():
                lo, hi = sp_lo.value(), sp_hi.value()
                cond[key] = (min(lo, hi), max(lo, hi))  # перепутанные границы — меняем местами
        return cond

    def _filter_text(self, cond: dict) -> str:
        names = {"x0": "x0", "s": "s", "nu": "ν"}
        return ", ".join(f"{names[k]} ∈ [{lo:g}; {hi:g}]" for k, (lo, hi) in cond.items())

    def _reset_filter(self):
        for check, *_ in self.flt.values():
            check.blockSignals(True)
            check.setChecked(False)
            check.blockSignals(False)
        self._fit_filter_ranges()
        self._update_filter()

    def _fit_filter_ranges(self):
        """Выключенные условия показывают фактический диапазон параметров множества."""
        p = self.state.fset.params()
        if len(p) == 0:
            return
        for col, (check, sp_lo, sp_hi) in enumerate(self.flt.values()):
            if check.isChecked():
                continue
            for sp, value in ((sp_lo, p[:, col].min()), (sp_hi, p[:, col].max())):
                sp.blockSignals(True)
                sp.setValue(value)
                sp.blockSignals(False)

    def _update_filter(self):
        """Пересчитать отбор: счётчик и серые строки у неподходящих величин."""
        fs = self.state.fset
        cond = self._filter_conditions()
        self._filter_hits = fs.filter_by_params(**cond)
        n, k = len(fs), len(self._filter_hits)
        if cond:
            self.lbl_filter.setText(f"Подходит: <b>{k}</b> из {n}")
        else:
            self.lbl_filter.setText("Условия не заданы — включите x0, s или ν")
        self.btn_filter.setEnabled(bool(cond) and 0 < k < n)
        self.btn_filter_restore.setEnabled(self.state.is_subset)
        hit = set(self._filter_hits) if cond else None
        dim = QBrush(QColor(theme.color("above_cut")))
        for row in range(self.table.rowCount()):
            brush = dim if hit is not None and self._row_index(row) not in hit else QBrush()
            for col in range(self.table.columnCount()):
                self.table.item(row, col).setForeground(brush)

    def _make_filter_subset(self):
        cond = self._filter_conditions()
        indices = self.state.fset.filter_by_params(**cond)
        if not indices:
            return
        fs = self.state.fset
        msg = f"Подмножество по параметрам ({self._filter_text(cond)}): {len(indices)} из {len(fs)} величин"
        self.state.set_fuzzy_set(fs.subset(indices), msg, is_subset=True)

    # ------------------------------------------------------------ данные
    def refresh(self):
        fs = self.state.fset
        suffix = "  (подмножество)" if self.state.is_subset else ""
        self.table_box.setTitle(f"Множество: {len(fs)} величин{suffix}")
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(len(fs))
        for row, v in enumerate(fs):
            name = QTableWidgetItem(v.name)
            name.setData(Qt.ItemDataRole.UserRole, row)
            left, right = v.alpha_cut(SUPPORT_ALPHA)
            self.table.setItem(row, 0, name)
            for col, value, digits in ((1, v.x0, 3), (2, v.s, 3), (3, v.nu, 2), (4, left, 3), (5, right, 3)):
                self.table.setItem(row, col, NumItem(value, digits))
        self.table.blockSignals(False)
        self.table.setSortingEnabled(True)
        self._fit_filter_ranges()
        self._update_filter()

    def _row_index(self, row: int) -> int:
        return int(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))

    def _on_row_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if len(rows) == 1:
            self.state.select(self._row_index(rows[0].row()))

    def _select_row(self, index: int):
        if index < 0:
            self.table.blockSignals(True)
            self.table.clearSelection()
            self.table.blockSignals(False)
            return
        for row in range(self.table.rowCount()):
            if self._row_index(row) == index:
                self.table.blockSignals(True)
                self.table.selectRow(row)
                self.table.blockSignals(False)
                self.table.scrollToItem(self.table.item(row, 0))
                return

    def _preview_rows(self, event):
        try:
            v = StudentFuzzy(self.sp_x0.value(), self.sp_s.value(), self.sp_nu.value())
        except ValueError:
            return None
        return self.preview_ax, [(f"T({v.x0:g}; {v.s:g}; {v.nu:g})", COLOR_SELECTED, v.membership(event.xdata))]

    def on_theme_changed(self):
        self.preview.retheme()
        self.preview_ax = self.preview.figure.add_subplot()
        self._update_preview()
        self._update_filter()

    def _update_preview(self):
        ax = self.preview_ax
        ax.clear()
        try:
            v = StudentFuzzy(self.sp_x0.value(), self.sp_s.value(), self.sp_nu.value())
        except ValueError:
            return
        lo, hi = v.alpha_cut(0.02)
        xs = np.linspace(lo, hi, 300)
        ax.plot(xs, v.membership(xs), color=COLOR_SELECTED, lw=2)
        ax.fill_between(xs, v.membership(xs), color=COLOR_SELECTED, alpha=0.1)
        ax.set_ylim(0, 1.08)
        ax.set_title("Предпросмотр μ(x)", fontsize=9)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.3)
        self.preview.draw()

    # ---------------------------------------------------------- действия
    def generate(self):
        text = self.edit_seed.text().strip()
        try:
            seed = int(text) if text else None
        except ValueError:
            show_error(self, "Генерация", "Зерно должно быть целым числом")
            return
        n, groups = self.spin_n.value(), self.spin_groups.value()
        fs = generate_set(n, groups=groups, seed=seed)
        p = fs.params()
        self.state.set_fuzzy_set(
            fs, f"Сгенерировано {n} величин (групп: {groups}, seed: {seed if seed is not None else 'случайное'}); "
                f"x0 ∈ [{p[:, 0].min():.2f}; {p[:, 0].max():.2f}], s ∈ [{p[:, 1].min():.2f}; {p[:, 1].max():.2f}], "
                f"ν ∈ [{p[:, 2].min():.0f}; {p[:, 2].max():.0f}]")

    def add_manual(self):
        try:
            v = StudentFuzzy(self.sp_x0.value(), self.sp_s.value(), self.sp_nu.value(), self.ed_name.text().strip())
        except ValueError as e:
            show_error(self, "Ввод величины", e)
            return
        self.state.add_value(v)
        self.ed_name.clear()

    def delete_selected(self):
        rows = self.table.selectionModel().selectedRows()
        self.state.remove_values(self._row_index(r.row()) for r in rows)

    def clear(self):
        self.state.set_fuzzy_set(FuzzySet(), "Множество очищено")

    def dump_to_journal(self):
        fs = self.state.fset
        self.state.log(f"Содержимое множества ({len(fs)} величин):")
        for v in fs:
            left, right = v.alpha_cut(SUPPORT_ALPHA)
            self.state.log(f"  {v}  носитель(α={SUPPORT_ALPHA}) = [{left:.3f}; {right:.3f}]")

    def save(self):
        folder = app_dir() / "data"
        folder.mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить множество", str(folder / "set.json"),
                                              "Множество величин (*.json)")
        if not path:
            return
        try:
            self.state.fset.save(path)
            self.state.log(f"Множество ({len(self.state.fset)} величин) сохранено в файл {path}")
        except OSError as e:
            show_error(self, "Сохранение", e)

    def load(self):
        folder = app_dir() / "data"
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить множество", str(folder if folder.exists() else app_dir()),
                                              "Множество величин (*.json)")
        if not path:
            return
        try:
            fs = FuzzySet.load(path)
        except (OSError, ValueError, KeyError, TypeError) as e:
            show_error(self, "Загрузка", f"Не удалось прочитать файл:\n{e}")
            return
        self.state.set_fuzzy_set(fs, f"Загружено {len(fs)} величин из файла {path}")
