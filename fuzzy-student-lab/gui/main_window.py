"""Главное окно приложения."""
from __future__ import annotations

import sys

from PyQt6.QtCore import QLocale, QSettings
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QMessageBox, QTabWidget

from fuzzy_student import Journal, __version__, generate_set

from . import theme
from .common import app_dir
from .state import AppState
from .tab_alpha import AlphaTab
from .tab_cluster import ClusterTab
from .tab_log import LogTab
from .tab_ops import OpsTab
from .tab_set import SetTab

APP_TITLE = "Нечёткие величины Стьюдента — кластерный анализ"

ABOUT = f"""<h3>{APP_TITLE}</h3>
<p>Версия {__version__}. Комплексное практическое занятие по дисциплине «Неклассические логики».</p>
<p><b>Вариант:</b> нечёткая величина с функцией принадлежности вида распределения Стьюдента</p>
<p style="font-size:12pt">μ(x) = (1 + ((x − x0)/s)² / ν)<sup>−(ν+1)/2</sup></p>
<p>x0 — центр, s — масштаб, ν — число степеней свободы.<br>
α-срез: [x0 − s·g; x0 + s·g], g = √(ν(α<sup>−2/(ν+1)</sup> − 1)).</p>
<p>Вкладки: <b>Множество</b> — генерация и ввод; <b>α-срез</b> — все величины на одном графике и отбор
подмножества; <b>Операции</b> — + − × ÷ и сравнение; <b>Кластеризация</b> — иерархическая
кластеризация с дендрограммой; <b>Журнал</b> — лог действий.</p>"""


def settings() -> QSettings:
    """Настройки хранятся в settings.ini рядом с программой (портативно, без реестра)."""
    return QSettings(str(app_dir() / "settings.ini"), QSettings.Format.IniFormat)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1440, 880)
        self.state = AppState(Journal(app_dir() / "logs" / "fuzzy_log.txt"))

        self.tabs = QTabWidget()
        self.tab_set = SetTab(self.state)
        self.tab_alpha = AlphaTab(self.state)
        self.tab_ops = OpsTab(self.state)
        self.tab_cluster = ClusterTab(self.state)
        self.tab_log = LogTab(self.state)
        for widget, title in ((self.tab_set, "1. Множество величин"), (self.tab_alpha, "2. α-срез"),
                              (self.tab_ops, "3. Операции"), (self.tab_cluster, "4. Кластеризация"),
                              (self.tab_log, "5. Журнал")):
            self.tabs.addTab(widget, title)
        self.setCentralWidget(self.tabs)
        self.tab_set.open_requested.connect(self._open_in_alpha)

        self.status = QLabel()
        self.statusBar().addPermanentWidget(self.status)
        self.state.set_changed.connect(self._update_status)
        self._build_menu()

        self.state.log("=== Запуск программы ===")
        self.state.set_fuzzy_set(generate_set(200, groups=5), "Стартовый набор: сгенерировано 200 величин (5 групп)")

    def _build_menu(self):
        m = self.menuBar().addMenu("Файл")
        for text, shortcut, slot in (("Сохранить множество…", QKeySequence.StandardKey.Save, self.tab_set.save),
                                     ("Загрузить множество…", QKeySequence.StandardKey.Open, self.tab_set.load)):
            act = QAction(text, self)
            act.setShortcut(shortcut)
            act.triggered.connect(slot)
            m.addAction(act)
        m.addSeparator()
        act_exit = QAction("Выход", self)
        act_exit.triggered.connect(self.close)
        m.addAction(act_exit)

        v = self.menuBar().addMenu("Вид")
        self.act_dark = QAction("Тёмная тема", self)
        self.act_dark.setCheckable(True)
        self.act_dark.setChecked(theme.name() == "dark")
        self.act_dark.setShortcut("Ctrl+T")
        self.act_dark.toggled.connect(lambda on: self.set_theme("dark" if on else "light"))
        v.addAction(self.act_dark)

        h = self.menuBar().addMenu("Справка")
        act_about = QAction("О программе", self)
        act_about.triggered.connect(lambda: QMessageBox.about(self, "О программе", ABOUT))
        h.addAction(act_about)

    def set_theme(self, name: str):
        theme.apply(QApplication.instance(), name)
        for tab in (self.tab_set, self.tab_alpha, self.tab_ops, self.tab_cluster):
            tab.on_theme_changed()
        settings().setValue("theme", name)
        self.state.log(f"Тема оформления: {theme.NAMES[name]}")

    def _open_in_alpha(self, index: int):
        self.state.select(index)
        self.tabs.setCurrentWidget(self.tab_alpha)

    def _update_status(self):
        n = len(self.state.fset)
        extra = f" — подмножество из {len(self.state.full_set)}" if self.state.is_subset else ""
        self.status.setText(f"Величин в множестве: {n}{extra}   ")

    def closeEvent(self, event):
        self.state.log("=== Завершение работы ===")
        super().closeEvent(event)


def run() -> int:
    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))  # точка в дробях
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    theme.apply(app, str(settings().value("theme", "light")))
    window = MainWindow()
    window.show()
    return app.exec()
