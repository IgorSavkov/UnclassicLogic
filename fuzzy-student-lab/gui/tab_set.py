"""Вкладка «Множество»: генерация, ручной ввод, таблица величин, файлы."""
from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QAbstractItemView, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from fuzzy_student import SUPPORT_ALPHA, FuzzySet, StudentFuzzy, generate_set

from .common import COLOR_SELECTED, NumItem, PlotWidget, app_dir, dspin, show_error

COLUMNS = ["Имя", "Центр x0", "Масштаб s", "ν", "Левая граница*", "Правая граница*"]


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
        self.spin_n.setSingleStep(10)
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
        self.sp_nu = dspin(0.1, 1000, 5.0, step=1, decimals=2)
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
        btn_add = QPushButton("Добавить в множество")
        btn_add.clicked.connect(self.add_manual)
        f2.addRow(btn_add)
        for sp in (self.sp_x0, self.sp_s, self.sp_nu):
            sp.valueChanged.connect(self._update_preview)
        left.addWidget(man)

        files = QGroupBox("Множество")
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

        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(330)
        root.addWidget(left_w)

        right = QVBoxLayout()
        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("title")
        right.addWidget(self.lbl_title)
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
        right.addWidget(self.table)
        hint = QLabel(f"* практические границы носителя — α-срез на уровне α = {SUPPORT_ALPHA}. "
                      "Двойной щелчок по строке — открыть величину на вкладке «α-срез». "
                      "Щелчок по заголовку столбца — сортировка.")
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        right.addWidget(hint)
        root.addLayout(right, 1)

    # ------------------------------------------------------------ данные
    def refresh(self):
        fs = self.state.fset
        suffix = "  (подмножество)" if self.state.is_subset else ""
        self.lbl_title.setText(f"Множество: {len(fs)} величин{suffix}")
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

    def _row_index(self, row: int) -> int:
        return int(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))

    def _on_row_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if len(rows) == 1:
            self.state.select(self._row_index(rows[0].row()))

    def _select_row(self, index: int):
        for row in range(self.table.rowCount()):
            if self._row_index(row) == index:
                self.table.blockSignals(True)
                self.table.selectRow(row)
                self.table.blockSignals(False)
                self.table.scrollToItem(self.table.item(row, 0))
                return

    def on_theme_changed(self):
        self.preview.retheme()
        self.preview_ax = self.preview.figure.add_subplot()
        self._update_preview()

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
