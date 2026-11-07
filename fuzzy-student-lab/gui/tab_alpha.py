"""Вкладка «α-срез»: все величины на одном графике, уровень α и отбор подмножества.

Управление одинаково на графике и в таблице:
  щелчок по кривой или строке          — сделать величину выбранной (красной);
  галочка ✓ в таблице, Ctrl+щелчок     — включить / исключить величину из подмножества;
  правый щелчок по кривой или строке   — меню: выбрать, включить/исключить, закрепить подсветку;
  наведение на строку таблицы          — временно подсветить её кривую на графике;
  перетаскивание мышью                 — линия α, линия x*, края окна [a; b].
"""
from __future__ import annotations

import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QCursor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QCompleter, QFormLayout, QGroupBox,
                             QHBoxLayout, QHeaderView, QLabel, QMenu, QMessageBox, QPushButton, QSlider,
                             QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from fuzzy_student import SUPPORT_ALPHA, spread_factor

from . import theme
from .common import COLOR_SELECTED, CurveReadout, NumItem, PlotWidget, card, dspin, side_column

MODE_INTERSECT, MODE_POINT, MODE_WINDOW = 0, 1, 2
ALPHA_STEPS = 1000      # шаг ползунка α = 0.001
ALPHA_MIN = 1 / ALPHA_STEPS  # α > 0: при α = 0 срез — вся числовая ось
COLOR_WINDOW = "#2ca02c"
NO_SELECTION = "— не выбрана —"
# Цвета подсветки выделенных в таблице величин: не красный (выбранная), не синий (подходят),
# не серый (не подходят). Первый — из темы, остальные одинаковые для обеих тем.
HIGHLIGHT_EXTRA = ("#10b981", "#d946ef", "#f97316", "#84cc16", "#f472b6", "#a78bfa", "#14b8a6", "#b45309")
LEGEND_MAX_HL = 4  # сколько выделенных величин перечислять в легенде (остальные — одной строкой)
_swatches: dict[str | None, QIcon] = {}


def highlight_palette() -> list[str]:
    return [theme.color("highlight"), *HIGHLIGHT_EXTRA]


def swatch(color: str | None) -> QIcon:
    """Цветной квадратик перед именем в таблице (виден и на выделенной строке, в отличие от цвета текста)."""
    if color not in _swatches:
        pix = QPixmap(12, 12)
        pix.fill(Qt.GlobalColor.transparent)
        if color is not None:
            p = QPainter(pix)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(QColor(color))
            p.setPen(QColor(color).darker(140))
            p.drawRoundedRect(1, 1, 10, 10, 2, 2)
            p.end()
        icon = QIcon(pix)
        icon.addPixmap(pix, QIcon.Mode.Selected)  # иначе Qt тонирует метку цветом выделения строки
        _swatches[color] = icon
    return _swatches[color]


CUT_COLUMNS = ["✓", "Имя", "Центр x0", "Масштаб s", "ν", "Степень*", "α-срез: левая", "α-срез: правая",
               "Ширина α-среза"]
CHECK_COL = 0   # столбец галочек «войдёт в подмножество» (отдельный: щелчок по нему не выбирает величину)
NAME_COL = 1
SORT_COL = 5    # «Степень»: по умолчанию подходящие сверху
GRAB_PX = 6     # насколько близко к линии α / x* / краю окна надо нажать, чтобы её потянуть
HELP_TEXT = ("Щелчок по строке или по кривой на графике — сделать величину выбранной (красной).\n"
             "Галочка ✓ — величина войдёт в подмножество (на графике — Ctrl+щелчок по кривой).\n"
             "Правый щелчок по строке или кривой — меню: выбрать, включить/исключить, закрепить подсветку.\n"
             "Наведите курсор на строку — её кривая подсветится на графике.\n"
             "* Степень — значение критерия отбора: величина подходит, если степень ≥ α.")


class AlphaTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.scores = np.empty(0)
        self.segments = None
        self.mask = np.empty(0, dtype=bool)
        self._unchecked: set[int] = set()  # подходящие величины, с которых сняли галочку
        # закреплённая подсветка (из меню по правому щелчку): индекс величины → цвет
        self._highlight: dict[int, str] = {}
        self._hover: int | None = None    # строка таблицы под курсором — её кривая подсвечена
        self._drag: str | None = None     # что тянут мышью: "alpha" | "x" | "a" | "b"
        self._cursor = None               # текущая форма курсора над графиком
        self._legend_key = None
        self._full = True  # нужна полная перерисовка графика (изменился фон), иначе — только слой
        self._table_timer = QTimer(self, singleShot=True, interval=120)  # таблица при движении α
        self._table_timer.timeout.connect(self._fill_table)
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
        # поиск: в списке 100–300 величин, листать долго — можно начать вводить имя (T05…)
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo.setToolTip("Начните вводить имя (например, T05) — список отфильтруется")
        completer = QCompleter(self.combo.model(), self)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.activated[str].connect(self._on_combo_text)
        self.combo.setCompleter(completer)
        self.combo.lineEdit().editingFinished.connect(lambda: self._on_combo_text(self.combo.lineEdit().text()))
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
        self.slider.setRange(1, ALPHA_STEPS)
        self.slider.setPageStep(ALPHA_STEPS // 100)
        self.slider.setValue(ALPHA_STEPS // 2)
        self.spin_alpha = dspin(ALPHA_MIN, 1.0, 0.5, step=ALPHA_MIN, decimals=3)  # стрелки — по 0.001
        self.spin_alpha.setToolTip("α ∈ (0; 1]. Стрелки — шаг 0.001, PageUp/PageDown — 0.01")
        self.spin_alpha.setKeyboardTracking(True)
        row.addWidget(self.slider, 1)
        row.addWidget(self.spin_alpha)
        fa.addLayout(row)
        self.slider.valueChanged.connect(self._on_slider)
        self.spin_alpha.valueChanged.connect(self._on_spin)
        left.addWidget(box_a)

        box_c = QGroupBox("Отбор подмножества по α")
        fc = QFormLayout(box_c)
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["α-срез пересекается со срезом выбранной",
                                  "точка x* лежит в α-срезе величины",
                                  "α-срез пересекает окно [a; b]"])
        self.combo_mode.setToolTip(
            "1) B отбирается, если A_α ∩ B_α ≠ ∅, т.е. Poss(A = B) ≥ α — величины, «похожие» на выбранную;\n"
            "2) B отбирается, если μ_B(x*) ≥ α — величины, для которых x* возможно со степенью не ниже α;\n"
            "3) B отбирается, если B_α ∩ [a; b] ≠ ∅ — величины, которые со степенью не ниже α "
            "попадают в окно [a; b].")
        self.combo_mode.currentIndexChanged.connect(self._on_mode)
        fc.addRow(QLabel("Критерий отбора величины B:"))
        fc.addRow(self.combo_mode)
        self.spin_x = dspin(-10000, 10000, 0.0, step=0.1)
        self.spin_a = dspin(-10000, 10000, -1.0, step=0.1)
        self.spin_b = dspin(-10000, 10000, 1.0, step=0.1)
        for sp in (self.spin_x, self.spin_a, self.spin_b):
            sp.setEnabled(False)
            sp.valueChanged.connect(self._on_param)
        fc.addRow("Точка x*:", self.spin_x)
        fc.addRow("Окно: левая граница a:", self.spin_a)
        fc.addRow("Окно: правая граница b:", self.spin_b)
        self.check_only = QCheckBox("Показать только подмножество (после среза)")
        self.check_only.toggled.connect(self._on_check_only)
        fc.addRow(self.check_only)
        left.addWidget(box_c)

        self.check_only.setToolTip("Выключено — «до среза»: на графике и в таблице все величины.\n"
                                   "Включено — «после среза»: только величины, прошедшие отбор.")
        self.lbl_count = QLabel()
        self.lbl_count.setObjectName("big")
        checks = QWidget()
        row_checks = QHBoxLayout(checks)
        row_checks.setContentsMargins(0, 0, 0, 0)
        for text, checked in (("Отметить все", True), ("Снять все", False)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, c=checked: self._check_all(c))
            row_checks.addWidget(b)
        self.btn_subset = QPushButton("Сделать подмножество рабочим множеством")
        self.btn_subset.setObjectName("primary")
        self.btn_subset.setToolTip("В подмножество войдут только отмеченные галочкой величины")
        self.btn_subset.clicked.connect(self._make_subset)
        self.btn_restore = QPushButton("Вернуть исходное множество")
        self.btn_restore.clicked.connect(self.state.restore_full_set)
        left.addWidget(card("Подмножество", self.lbl_count, checks, self.btn_subset, self.btn_restore))
        left.addStretch()

        root.addWidget(side_column(left))

        self.plot = PlotWidget()
        self.ax = self.plot.figure.add_subplot()
        self.readout = CurveReadout(self.plot, self._hover_rows)
        canvas = self.plot.canvas
        canvas.mpl_connect("button_press_event", self._on_plot_press)
        canvas.mpl_connect("motion_notify_event", self._on_plot_motion)
        canvas.mpl_connect("button_release_event", self._on_plot_release)
        plot_hint = QLabel("Линию α можно тянуть мышью (в режимах «точка x*» и «окно» — и их линии). "
                           "Щелчок по кривой — выбрать величину, правый щелчок — меню.")
        plot_hint.setWordWrap(True)
        plot_hint.setObjectName("hint")

        self.table = QTableWidget(0, len(CUT_COLUMNS))
        self.table.setHorizontalHeaderLabels(CUT_COLUMNS)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(CHECK_COL, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(CHECK_COL, 34)
        self.table.horizontalHeaderItem(CHECK_COL).setToolTip("Войдёт в подмножество")
        self.table.verticalHeader().setVisible(False)
        # одна выбранная строка = выбранная (красная) величина
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header.setSortIndicator(SORT_COL, Qt.SortOrder.DescendingOrder)  # подходящие сверху
        self.table.setSortingEnabled(True)
        self.table.itemChanged.connect(self._on_item_checked)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)  # события движения без нажатой кнопки — для наведения
        self.table.cellEntered.connect(lambda row, _col: self._set_hover(self._row_index(row)))
        self.table.viewport().installEventFilter(self)  # щелчок по галочке; уход курсора с таблицы
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_menu)
        self.table.setToolTip(HELP_TEXT)
        hint = QLabel("✓ — войдёт в подмножество. Щелчок по строке — выбрать величину, правый щелчок — меню. "
                      "* Степень ≥ α — величина подходит.")
        hint.setToolTip(HELP_TEXT)
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        self.table_box = card("α-срезы величин", self.table, hint, stretch=0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(card("Функции принадлежности", self.plot, plot_hint, stretch=0))
        splitter.addWidget(self.table_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

    # ----------------------------------------------------------- события
    def alpha(self) -> float:
        return self.spin_alpha.value()

    def _set_alpha(self, a: float):
        """Задать α программно: обновляются и ползунок, и поле."""
        a = min(max(float(a), ALPHA_MIN), 1.0)
        self._sync(self.spin_alpha, a)
        self._on_spin(a)

    def _on_slider(self, v: int):
        self._sync(self.spin_alpha, v / ALPHA_STEPS)
        self._alpha_changed()

    def _on_spin(self, a: float):
        # поле само себе значение не записывает — иначе при ручном вводе текст
        # переформатируется («0.96» → «0.960») прямо под курсором
        self._sync(self.slider, round(a * ALPHA_STEPS))
        self._alpha_changed()

    @staticmethod
    def _sync(widget, value):
        widget.blockSignals(True)
        widget.setValue(value)
        widget.blockSignals(False)

    def _alpha_changed(self):
        # пока α двигают, таблица догоняет с небольшой задержкой — график не ждёт её
        self._update_dynamic(defer_table=True)
        self._log_timer.start()

    def _on_combo(self, index: int):
        # нулевой пункт — «не выбрана», дальше величины по порядку
        if index >= 0:
            self.state.select(index - 1)

    def _on_combo_text(self, text: str):
        """Поиск в списке: точное совпадение или единственная величина, имя которой содержит текст."""
        query = text.strip().lower()
        items = [self.combo.itemText(i) for i in range(self.combo.count())]
        index = next((i for i, t in enumerate(items) if t.lower() == query), -1)
        if index < 0 and query:
            found = [i for i, t in enumerate(items) if i > 0 and query in t.lower()]
            index = found[0] if len(found) == 1 else -1
        if index >= 0 and index != self.combo.currentIndex():
            self.combo.setCurrentIndex(index)  # дальше — _on_combo
        else:  # ничего не нашлось или неоднозначно — вернуть подпись выбранной
            self.combo.lineEdit().setText(self.combo.currentText())

    def _reset_unchecked(self, reason: str):
        """Снятые галочки относятся к прежнему набору подходящих величин — при смене выбранной
        величины (в режиме пересечения) или критерия они сбрасываются, а не «залипают»."""
        if self._unchecked:
            self._unchecked.clear()
            self.state.log(f"Снятые галочки сброшены: {reason}")

    def _on_mode(self, mode: int):
        self._reset_unchecked("изменился критерий отбора")
        self.spin_x.setEnabled(mode == MODE_POINT)
        self.spin_a.setEnabled(mode == MODE_WINDOW)
        self.spin_b.setEnabled(mode == MODE_WINDOW)
        v = self.state.selected_value
        if v is not None:
            # начальные значения — вокруг выбранной величины
            defaults = {MODE_POINT: ((self.spin_x, v.x0),),
                        MODE_WINDOW: ((self.spin_a, round(v.x0 - v.s, 2)),
                                      (self.spin_b, round(v.x0 + v.s, 2)))}
            for sp, value in defaults.get(mode, ()):
                sp.blockSignals(True)
                sp.setValue(value)
                sp.blockSignals(False)
        self._refresh()
        self._log_timer.start()

    def _on_param(self, _value):
        # x*, a, b меняют только динамический слой графика — без полной перерисовки,
        # чтобы линию можно было плавно тянуть мышью; таблица догоняет с задержкой
        self._refresh(full=False, defer_table=True)
        self._log_timer.start()

    def _window(self) -> tuple[float, float]:
        """Окно [a; b]; если a > b, границы просто меняются местами."""
        a, b = self.spin_a.value(), self.spin_b.value()
        return (a, b) if a <= b else (b, a)

    def on_set_changed(self):
        fs = self.state.fset
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem(NO_SELECTION)
        self.combo.addItems([f"{v.name}   T({v.x0:.2f}; {v.s:.2f}; {v.nu:.1f})" for v in fs])
        self.combo.blockSignals(False)
        self._unchecked.clear()
        self._highlight.clear()
        self._hover = None
        self._build_static()
        self._refresh()

    def on_selection_changed(self, index: int):
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(index + 1)
        self.combo.blockSignals(False)
        if self.combo_mode.currentIndex() == MODE_INTERSECT:
            self._reset_unchecked("выбрана другая величина — изменился набор подходящих")
        self._refresh()
        if index >= 0:
            self._scroll_to(index)

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
        self.xs = np.linspace(lo, hi, 400)  # больше точек глазу не видно, а рисовать дольше
        p = fs.params()
        t = (self.xs[None, :] - p[:, 0:1]) / p[:, 1:2]
        mu = (1.0 + t * t / p[:, 2:3]) ** (-(p[:, 2:3] + 1.0) / 2.0)
        self.segments = np.stack([np.broadcast_to(self.xs, mu.shape), mu], axis=-1)

        fg, c_pass, c_fail = theme.color("fg"), theme.color("pass"), theme.color("fail")
        self.lc_fail = LineCollection([], colors=c_fail, linewidths=0.6, zorder=1)
        self.lc_off = LineCollection([], colors=c_pass, linewidths=0.8, alpha=0.35, linestyles="--", zorder=1.8)
        self.lc_pass = LineCollection([], colors=c_pass, linewidths=0.8, alpha=0.8, zorder=2)
        self.lc_hl = LineCollection([], colors=theme.color("highlight"), linewidths=2.2, zorder=3.5)
        # строка таблицы под курсором — её кривая цветом текста, толще остальных
        self.lc_hover = LineCollection([], colors=fg, linewidths=2.6, zorder=3.8)
        for lc in (self.lc_fail, self.lc_off, self.lc_pass, self.lc_hl, self.lc_hover):
            ax.add_collection(lc)
        (self.line_sel,) = ax.plot([], [], color=COLOR_SELECTED, lw=2.6, zorder=4)
        self.line_alpha = ax.axhline(0.5, color=fg, ls="--", lw=1.2, zorder=5)
        (self.line_cut,) = ax.plot([], [], color=COLOR_SELECTED, lw=5, alpha=0.7, zorder=6,
                                   solid_capstyle="butt")
        (self.line_l,) = ax.plot([], [], color=COLOR_SELECTED, ls=":", lw=1.2, zorder=6)
        (self.line_r,) = ax.plot([], [], color=COLOR_SELECTED, ls=":", lw=1.2, zorder=6)
        self.line_x = ax.axvline(0, color=COLOR_WINDOW, lw=1.8, ls="-.", zorder=6)
        self.span = Rectangle((0, 0), 0, 1.05, facecolor=COLOR_WINDOW, edgecolor="none",
                              alpha=0.12, zorder=0)
        # зона «x в окне и μ >= α»: величина проходит, если её кривая заходит в эту зону
        self.zone = Rectangle((0, 0), 0, 0, facecolor=to_rgba(COLOR_WINDOW, 0.28),
                              edgecolor=COLOR_WINDOW, lw=1.8, zorder=1.5)
        ax.add_patch(self.span)
        ax.add_patch(self.zone)
        # точка каждой величины: максимум μ_B на [a; b], т.е. (clip(x0, a, b); степень)
        self.dots = ax.scatter([], [], s=26, zorder=7, linewidths=0.8, edgecolors=fg)
        ax.set_xlim(lo, hi)
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("x")
        ax.set_ylabel("μ(x)")
        ax.grid(alpha=0.3)
        self._legend_key = None
        # Фон (рисуется редко): оси и все кривые серым (lc_fail). Всё, что меняется при движении α,
        # x*, окна, галочках и подсветке, — динамический слой поверх фона (порядок списка = порядок
        # рисования). Окно [a; b] (span) тоже в динамическом слое: его края тянут мышью.
        for artist in (self.span, self.zone, self.lc_off, self.lc_pass, self.lc_hl, self.lc_hover, self.line_sel,
                       self.dots, self.line_alpha, self.line_cut, self.line_l, self.line_r, self.line_x, ax.title):
            self.plot.add_animated(artist)
        self._full = True

    def _update_legend(self, mode: int, has_selected: bool, has_off: bool, hl: tuple):
        """hl — выделенные в таблице: ((имя, цвет), ...); каждая — отдельной строкой своим цветом."""
        key = (mode, has_selected, has_off, hl)
        if key == self._legend_key:
            return
        self._legend_key = key
        fg, c_pass, c_fail = theme.color("fg"), theme.color("pass"), theme.color("fail")
        handles = [Line2D([], [], color=COLOR_SELECTED, lw=2.6, label="выбранная величина")] if has_selected else []
        handles.append(Line2D([], [], color=c_pass, lw=1.5, label="подходят под α"))
        if has_off:
            handles.append(Line2D([], [], color=c_pass, lw=1.2, ls="--", alpha=0.5,
                                  label="подходят, но не отмечены"))
        shown = hl[:LEGEND_MAX_HL]
        handles += [Line2D([], [], color=c, lw=2.2, label=f"{name} (подсветка)") for name, c in shown]
        if len(hl) > len(shown):
            handles.append(Line2D([], [], ls="none", label=f"… и ещё с подсветкой: {len(hl) - len(shown)}"))
        handles += [Line2D([], [], color=c_fail, lw=1.5, label="не подходят"),
                    Line2D([], [], color=fg, ls="--", label="уровень α")]
        if mode == MODE_WINDOW:
            handles += [Rectangle((0, 0), 1, 1, facecolor=to_rgba(COLOR_WINDOW, 0.28),
                                  edgecolor=COLOR_WINDOW, label="зона: x ∈ [a; b] и μ ≥ α"),
                        Line2D([], [], ls="none", marker="o", markerfacecolor=c_pass,
                               markeredgecolor=fg, label="max μ_B на [a; b] — в зоне: подходит")]
        old = self.ax.get_legend()
        if old is not None:
            self.plot.remove_animated(old)
        # легенда — в динамическом слое, иначе подходящие кривые рисовались бы поверх неё
        self.plot.add_animated(self.ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9))

    def _hover_rows(self, event):
        """μ(x) выбранной величины и кривой, ближайшей к курсору."""
        fs, v, alpha = self.state.fset, self.state.selected_value, self.alpha()
        if self.segments is None or len(fs) == 0:
            return None
        x = event.xdata

        def where(mu):
            return "— x в α-срезе" if mu >= alpha - 1e-12 else "— x вне α-среза"

        rows = []
        if v is not None:
            mu = v.membership(x)
            rows.append((f"выбранная {v.name} T({v.x0:.2f}; {v.s:.2f}; {v.nu:g})", COLOR_SELECTED, mu, where(mu)))
        near = self._nearest_curve(event)
        if near is not None and near[0] != self.state.selected:
            i, mu = near
            u, passed = fs[i], bool(self.mask[i])
            color = self._highlight.get(i) or (theme.color("pass") if passed else theme.color("fail"))
            if passed:
                state = "исключена из подмножества" if i in self._unchecked else "войдёт в подмножество"
                note = f"подходит под отбор, {state}"
            else:
                note = "не подходит под отбор"
            note += "<br>щелчок — выбрать, правый щелчок — меню"
            rows.append((f"под курсором {u.name} T({u.x0:.2f}; {u.s:.2f}; {u.nu:g})", color, mu,
                         f"{where(mu)}; {note}"))
        return (self.ax, rows) if rows else None

    def _nearest_curve(self, event, radius_px: float = 10) -> tuple[int, float] | None:
        """Видимая кривая, ближайшая к курсору по вертикали (в пикселях): (индекс, μ) или None."""
        fs = self.state.fset
        if self.segments is None or len(fs) == 0 or event.xdata is None or len(self.mask) != len(fs):
            return None
        p = fs.params()
        t = (event.xdata - p[:, 0]) / p[:, 1]
        mu_all = (1.0 + t * t / p[:, 2]) ** (-(p[:, 2] + 1.0) / 2.0)
        py = self.ax.transData.transform(np.column_stack([np.full(len(p), event.xdata), mu_all]))[:, 1]
        dist = np.abs(py - event.y)
        if self.check_only.isChecked():
            dist[~self.mask] = np.inf
        i = int(np.argmin(dist))
        return (i, float(mu_all[i])) if dist[i] < radius_px else None

    # ------------------------------------------------- мышь на графике
    def _toolbar_busy(self) -> bool:
        """Включены лупа или сдвиг панели инструментов — щелчки и перетаскивание для них."""
        toolbar = self.plot.toolbar
        return toolbar is not None and bool(toolbar.mode)

    def _handle_at(self, event) -> str | None:
        """Какую линию можно потянуть в этой точке: "alpha", "x", "a", "b" или None."""
        if event.inaxes is not self.ax or event.x is None or self.segments is None:
            return None
        to_px = self.ax.transData.transform
        mode = self.combo_mode.currentIndex()
        candidates = [("alpha", abs(event.y - to_px((0, self.alpha()))[1]))]
        if mode == MODE_POINT:
            candidates.append(("x", abs(event.x - to_px((self.spin_x.value(), 0))[0])))
        elif mode == MODE_WINDOW:
            candidates.append(("a", abs(event.x - to_px((self.spin_a.value(), 0))[0])))
            candidates.append(("b", abs(event.x - to_px((self.spin_b.value(), 0))[0])))
        name, dist = min(candidates, key=lambda c: c[1])
        return name if dist <= GRAB_PX else None

    def _on_plot_press(self, event):
        """Левая кнопка: у линии α / x* / края окна — начать перетаскивание; у кривой — выбрать её
        (Ctrl — включить/исключить из подмножества). Правая кнопка у кривой — меню."""
        if event.inaxes is not self.ax or event.dblclick or self._toolbar_busy():
            return
        if event.button == 1:
            handle = self._handle_at(event)
            if handle is not None:
                self._drag = handle
                self.readout.paused = True
                return
            near = self._nearest_curve(event)
            if near is None:
                return
            if event.key == "control":
                self._toggle_check(near[0])
            else:
                self.state.select(near[0])  # дальше — on_selection_changed
        elif event.button == 3:
            near = self._nearest_curve(event)
            if near is not None or self._highlight:
                self._show_menu(near[0] if near is not None else None)

    def _on_plot_motion(self, event):
        if self._drag is not None:
            if event.x is None:
                return
            # координаты берём и за пределами осей: линию можно дотянуть до края
            x, y = self.ax.transData.inverted().transform((event.x, event.y))
            if self._drag == "alpha":
                self._set_alpha(y)
            else:
                {"x": self.spin_x, "a": self.spin_a, "b": self.spin_b}[self._drag].setValue(float(x))
            return
        # курсор-«двусторонняя стрелка» над линией, которую можно потянуть
        handle = None if self._toolbar_busy() else self._handle_at(event)
        shape = {"alpha": Qt.CursorShape.SizeVerCursor, "x": Qt.CursorShape.SizeHorCursor,
                 "a": Qt.CursorShape.SizeHorCursor, "b": Qt.CursorShape.SizeHorCursor}.get(handle)
        if shape != self._cursor:
            self._cursor = shape
            if shape is None:
                self.plot.canvas.unsetCursor()
            else:
                self.plot.canvas.setCursor(shape)

    def _on_plot_release(self, _event):
        if self._drag is not None:
            self._drag = None
            self.readout.paused = False

    # ------------------------------------------------- меню и действия
    def _on_table_menu(self, pos):
        index = self.table.indexAt(pos)
        if index.isValid():
            self._show_menu(self._row_index(index.row()))
        elif self._highlight:
            self._show_menu(None)

    def _show_menu(self, i: int | None):
        """Меню по правому щелчку на кривой или строке (i = None — щелчок мимо величин)."""
        fs = self.state.fset
        menu = QMenu(self)
        act_select = act_check = act_pin = None
        if i is not None:
            u = fs[i]
            menu.addAction(f"{u.name}   T({u.x0:.2f}; {u.s:.2f}; {u.nu:g})").setEnabled(False)
            menu.addSeparator()
            act_select = menu.addAction("Сделать выбранной")
            act_select.setEnabled(i != self.state.selected)
            if self.mask[i]:
                act_check = menu.addAction("Включить в подмножество" if i in self._unchecked
                                           else "Исключить из подмножества")
            else:
                menu.addAction("Не подходит под отбор — в подмножество не войдёт").setEnabled(False)
            act_pin = menu.addAction("Снять подсветку" if i in self._highlight else "Закрепить подсветку")
        act_clear = None
        if self._highlight:
            menu.addSeparator()
            act_clear = menu.addAction("Снять всю подсветку")
        chosen = menu.exec(QCursor.pos())
        if chosen is None:
            return
        if chosen is act_select:
            self.state.select(i)
        elif chosen is act_check:
            self._toggle_check(i)
        elif chosen is act_pin:
            self._toggle_pin(i)
        elif chosen is act_clear:
            self._highlight.clear()
            self._update_swatches()
            self._draw()

    def _toggle_check(self, i: int):
        """Включить / исключить подходящую величину из подмножества."""
        if not self.mask[i]:
            return
        self._unchecked ^= {i}
        self._fill_table()
        self._update_counts()
        self._draw()
        self._scroll_to(i)

    def _toggle_pin(self, i: int):
        """Закрепить / снять подсветку кривой. У каждой закреплённой — свой цвет из палитры."""
        if i in self._highlight:
            del self._highlight[i]
        else:
            palette = highlight_palette()
            free = [c for c in palette if c not in self._highlight.values()]
            self._highlight[i] = free[0] if free else palette[len(self._highlight) % len(palette)]
        self._update_swatches()
        self._draw()

    def _update_swatches(self):
        """Цветные метки закреплённой подсветки перед именами в таблице."""
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            self.table.item(row, NAME_COL).setIcon(swatch(self._highlight.get(self._row_index(row))))
        self.table.blockSignals(False)

    # ------------------------------------------------- мышь в таблице
    def eventFilter(self, obj, event):
        if obj is self.table.viewport():
            kind = event.type()
            if (kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                         QEvent.Type.MouseButtonDblClick)
                    and event.button() == Qt.MouseButton.LeftButton):
                index = self.table.indexAt(event.position().toPoint())
                if index.isValid() and index.column() == CHECK_COL:
                    # Галочку переключаем сами и событие дальше не отдаём: щелчок по галочке
                    # не должен делать величину выбранной (это поменяло бы набор подходящих).
                    if kind == QEvent.Type.MouseButtonPress:
                        item = self.table.item(index.row(), CHECK_COL)
                        checkable = Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                        if item is not None and (item.flags() & checkable) == checkable:
                            checked = item.checkState() == Qt.CheckState.Checked
                            item.setCheckState(Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked)
                    return True
            elif kind == QEvent.Type.Leave:
                self._set_hover(None)
        return super().eventFilter(obj, event)

    def _set_hover(self, i: int | None):
        if i != self._hover:
            self._hover = i
            self._draw()

    def _on_row_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            i = self._row_index(rows[0].row())
            # после выхода из обработчика: смена выбранной перестраивает таблицу,
            # а делать это посреди обработки щелчка мышью по ней же небезопасно
            QTimer.singleShot(0, lambda: self.state.select(i))

    def _scroll_to(self, index: int):
        for row in range(self.table.rowCount()):
            if self._row_index(row) == index:
                self.table.scrollToItem(self.table.item(row, 0))
                return

    def _refresh(self, full: bool = True, defer_table: bool = False):
        """Пересчитать оценки величин по критерию (не зависят от α).
        full=False — фон графика не менялся, достаточно обновить динамический слой."""
        fs, v = self.state.fset, self.state.selected_value
        if len(fs) == 0:
            self.scores = np.empty(0)
        elif self.combo_mode.currentIndex() == MODE_POINT:
            self.scores = fs.memberships_at(self.spin_x.value())
        elif self.combo_mode.currentIndex() == MODE_WINDOW:
            self.scores = fs.window_degrees(*self._window())
        elif v is not None:
            self.scores = fs.heights_with(v)
        else:
            self.scores = np.zeros(len(fs))
        if full:
            self._full = True
        self._update_dynamic(defer_table)

    def _on_check_only(self):
        self._full = True  # «до/после среза» — серые кривые фона показываются или нет
        self._update_dynamic()

    def _update_dynamic(self, defer_table: bool = False):
        """Быстрое обновление при движении α: таблица α-срезов, подписи, график."""
        n = len(self.state.fset)
        self.mask = self.scores >= self.alpha() - 1e-12 if len(self.scores) == n else np.zeros(n, dtype=bool)
        if defer_table:
            self._table_timer.start()
        else:
            self._table_timer.stop()
            self._fill_table()
        self._update_value_labels()
        self._update_counts()
        self._draw()

    def _row_index(self, row: int) -> int:
        return int(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))

    def _fill_table(self):
        """Таблица α-срезов. «До среза» — все величины (неподходящие серые, без галочки),
        «после среза» — только подходящие. Выделенная строка — выбранная (красная) величина."""
        fs, tbl, alpha = self.state.fset, self.table, self.alpha()
        only = self.check_only.isChecked()
        rows = np.flatnonzero(self.mask) if only else np.arange(len(fs))
        p = fs.params()
        half = p[:, 1] * spread_factor(p[:, 2], alpha) if len(p) else np.empty(0)
        dim = QBrush(QColor(theme.color("above_cut")))
        selected_brush = QBrush(QColor(COLOR_SELECTED))
        tbl.blockSignals(True)
        tbl.setSortingEnabled(False)
        tbl.clearSelection()
        tbl.setRowCount(len(rows))
        for row, i in enumerate(rows):
            i = int(i)
            u, passed = fs[i], bool(self.mask[i])
            check = QTableWidgetItem()
            check.setData(Qt.ItemDataRole.UserRole, i)
            # Флаги задаются явно: по умолчанию у ячейки Qt галочку можно поставить всегда,
            # и щелчок по пустой клетке неподходящей величины «включал» её.
            if passed:
                check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                               | Qt.ItemFlag.ItemIsUserCheckable)
                check.setCheckState(Qt.CheckState.Unchecked if i in self._unchecked else Qt.CheckState.Checked)
                check.setToolTip("Исключена из подмножества" if i in self._unchecked else "Войдёт в подмножество")
            else:
                # квадратик виден всегда, но у неподходящей величины он бледный и не нажимается
                check.setFlags(Qt.ItemFlag.ItemIsSelectable)
                check.setCheckState(Qt.CheckState.Unchecked)
                check.setToolTip(f"Не подходит под отбор при α = {alpha:.3f} — в подмножество не войдёт")
            name = QTableWidgetItem(u.name)
            name.setData(Qt.ItemDataRole.UserRole, i)
            name.setIcon(swatch(self._highlight.get(i)))  # цветная метка закреплённой подсветки
            cells = [check, name, NumItem(u.x0), NumItem(u.s), NumItem(u.nu, 2), NumItem(self.scores[i]),
                     NumItem(u.x0 - half[i]), NumItem(u.x0 + half[i]), NumItem(2 * half[i])]
            for col, item in enumerate(cells):
                if not passed:
                    item.setForeground(dim)
                tbl.setItem(row, col, item)
            if i == self.state.selected:  # выбранная величина — красным жирным, как её кривая
                font = name.font()
                font.setBold(True)
                name.setFont(font)
                name.setForeground(selected_brush)
        tbl.setSortingEnabled(True)  # заново сортирует по выбранному столбцу
        for row in range(tbl.rowCount()):  # строка выбранной величины — выделена
            if self._row_index(row) == self.state.selected:
                tbl.selectRow(row)
                break
        tbl.blockSignals(False)
        view = "после среза — только подходящие" if only else "до среза — все величины"
        self.table_box.setTitle(f"α-срезы величин при α = {alpha:.3f} ({view})")

    def _chosen(self) -> list[int]:
        """Индексы величин, которые войдут в подмножество: подходят под α и отмечены галочкой."""
        return [int(i) for i in np.flatnonzero(self.mask) if int(i) not in self._unchecked]

    def _update_counts(self):
        n, k, m = len(self.state.fset), int(self.mask.sum()), len(self._chosen())
        if n and self.combo_mode.currentIndex() == MODE_INTERSECT and self.state.selected_value is None:
            self.lbl_count.setText("Для этого критерия выберите величину<br>в блоке «Выбранная величина»")
        else:
            self.lbl_count.setText(f"Под уровень α = {self.alpha():.3f} подходит: <b>{k}</b> из {n}<br>"
                                   f"Отмечено для подмножества: <b>{m}</b>")
        self.btn_subset.setEnabled(0 < m < n)
        self.btn_restore.setEnabled(self.state.is_subset)

    def _update_value_labels(self):
        v = self.state.selected_value
        if v is None:
            for w in self.lbl.values():
                w.setText("—")
            return
        left, right = v.alpha_cut(self.alpha())
        self.lbl["x0"].setText(f"{v.x0:.4f}")
        self.lbl["s"].setText(f"{v.s:.4f}")
        self.lbl["nu"].setText(f"{v.nu:.2f}")
        self.lbl["L"].setText(f"{left:.4f}")
        self.lbl["R"].setText(f"{right:.4f}")
        self.lbl["W"].setText(f"{right - left:.4f}")
        sl, sr = v.alpha_cut(SUPPORT_ALPHA)
        self.lbl["sup"].setText(f"[{sl:.3f}; {sr:.3f}]")

    def _on_item_checked(self, item: QTableWidgetItem):
        if item.column() != 0 or not self.mask[int(item.data(Qt.ItemDataRole.UserRole))]:
            return
        i = int(item.data(Qt.ItemDataRole.UserRole))
        if item.checkState() == Qt.CheckState.Checked:
            self._unchecked.discard(i)
        else:
            self._unchecked.add(i)
        self._update_counts()
        self._draw()

    def _check_all(self, checked: bool):
        """Отметить / снять все величины, которые сейчас подходят под α."""
        passed = {int(i) for i in np.flatnonzero(self.mask)}
        if checked:
            self._unchecked -= passed
        else:
            self._unchecked |= passed
        self._fill_table()
        self._update_counts()
        self._draw()

    def _flags(self, indices: set[int]) -> np.ndarray:
        """Маска величин из набора индексов."""
        flags = np.zeros(len(self.mask), dtype=bool)
        flags[[i for i in indices if i < len(flags)]] = True
        return flags

    def _draw(self):
        if self.segments is None:
            return
        fs, v, alpha = self.state.fset, self.state.selected_value, self.alpha()
        n, k = len(fs), int(self.mask.sum())
        # не отмеченные — только среди подходящих; подсветить можно любую строку таблицы
        off = self._flags(self._unchecked) & self.mask
        only = self.check_only.isChecked()
        hl = [(i, c) for i, c in self._highlight.items() if i < n and (self.mask[i] or not only)]
        self.lc_pass.set_segments(self.segments[self.mask & ~off])
        self.lc_off.set_segments(self.segments[off])
        self.lc_hl.set_segments(self.segments[[i for i, _c in hl]] if hl else [])
        self.lc_hl.set_color([c for _i, c in hl] or theme.color("highlight"))
        hov = self._hover  # строка таблицы под курсором (выбранная и так видна красной)
        show_hover = (hov is not None and hov < n and hov != self.state.selected
                      and (bool(self.mask[hov]) or not only))
        self.lc_hover.set_segments(self.segments[[hov]] if show_hover else [])
        self.line_alpha.set_ydata([alpha, alpha])
        mode = self.combo_mode.currentIndex()
        self._update_legend(mode, v is not None, bool(off.any()), tuple((fs[i].name, c) for i, c in hl))
        self.line_sel.set_visible(v is not None)
        if v is not None:
            left, right = v.alpha_cut(alpha)
            self.line_sel.set_data(self.xs, v.membership(self.xs))
            self.line_cut.set_data([left, right], [alpha, alpha])
            self.line_l.set_data([left, left], [0, alpha])
            self.line_r.set_data([right, right], [0, alpha])
        # в режиме окна срез выбранной величины не участвует в критерии — не показываем его
        for line in (self.line_cut, self.line_l, self.line_r):
            line.set_visible(v is not None and mode != MODE_WINDOW)
        self.line_x.set_visible(mode == MODE_POINT)
        if mode == MODE_POINT:
            x = self.spin_x.value()
            self.line_x.set_xdata([x, x])
        for artist in (self.span, self.zone, self.dots):
            artist.set_visible(mode == MODE_WINDOW)
        if mode == MODE_WINDOW:
            a, b = self._window()
            self.span.set_x(a)
            self.span.set_width(b - a)
            self.zone.set_bounds(a, alpha, b - a, 1.0 - alpha)
            self._update_dots(a, b)
        view = "после среза" if self.check_only.isChecked() else "все величины"
        m = k - int(off.sum())
        marked = f", отмечено {m}" if m != k else ""
        self.ax.set_title(f"Функции принадлежности ({view}): α = {alpha:.3f}, подходит {k} из {n}{marked}")
        if self._full:
            # фон: все кривые серым («до среза»); подходящие рисуются поверх него в динамическом слое
            self.lc_fail.set_segments([] if self.check_only.isChecked() else self.segments)
            self._full = False
            self.plot.draw()
        else:
            self.plot.update_animated()

    def _update_dots(self, a: float, b: float):
        """Точки (clip(x0, a, b); степень): над линией α — величина проходит."""
        x0 = self.state.fset.params()[:, 0]
        show = self.mask if self.check_only.isChecked() else np.ones(len(x0), dtype=bool)
        colors = np.where(self.mask, theme.color("pass"), theme.color("fail"))[show]
        self.dots.set_offsets(np.column_stack([np.clip(x0, a, b), self.scores])[show])
        self.dots.set_facecolors([to_rgba(c) for c in colors])

    # ----------------------------------------------------------- действия
    def _criterion_text(self) -> str:
        if self.combo_mode.currentIndex() == MODE_POINT:
            return f"μ_B(x*) ≥ α при x* = {self.spin_x.value():.3f}"
        if self.combo_mode.currentIndex() == MODE_WINDOW:
            a, b = self._window()
            return f"B_α ∩ [{a:.3f}; {b:.3f}] ≠ ∅"
        v = self.state.selected_value
        return f"Poss({v.name if v else '?'} = B) ≥ α"

    def _log_alpha(self):
        if self.combo_mode.currentIndex() == MODE_INTERSECT and self.state.selected_value is None:
            return  # критерий не определён: величина не выбрана
        if len(self.state.fset):
            self.state.log(f"α-срез: α = {self.alpha():.3f}, критерий {self._criterion_text()}: "
                           f"подходит {int(self.mask.sum())} из {len(self.state.fset)}")

    def _make_subset(self):
        indices = self._chosen()
        if not indices:
            QMessageBox.information(self, "Подмножество", "Не отмечено ни одной подходящей величины")
            return
        fs = self.state.fset
        sel = self.state.selected
        new_sel = indices.index(sel) if sel in indices else (-1 if sel < 0 else 0)
        excluded = sorted(fs[i].name for i in self._unchecked if i < len(fs) and self.mask[i])
        manual = f"; вручную исключены: {', '.join(excluded)}" if excluded else ""
        msg = (f"Выделено подмножество: {len(indices)} из {len(fs)} величин "
               f"(α = {self.alpha():.3f}, {self._criterion_text()}{manual})")
        self.state.set_fuzzy_set(fs.subset(indices), msg, is_subset=True, selected=new_sel)
