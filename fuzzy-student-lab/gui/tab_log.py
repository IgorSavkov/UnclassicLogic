"""Вкладка «Журнал»: просмотр лога работы программы."""
from __future__ import annotations

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class LogTab(QWidget):
    def __init__(self, state):
        super().__init__()
        journal = state.journal
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel(f"Файл журнала: {journal.path}"))
        bar.addStretch()
        b_open = QPushButton("Открыть файл журнала")
        b_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(journal.path))))
        bar.addWidget(b_open)
        b_clear = QPushButton("Очистить окно")
        bar.addWidget(b_clear)
        root.addLayout(bar)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Consolas", 9))
        root.addWidget(self.text)
        b_clear.clicked.connect(self.text.clear)
        journal.subscribe(self.text.appendPlainText)
