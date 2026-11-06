"""Светлая и тёмная темы: палитра Qt, стиль виджетов и цвета графиков matplotlib.

Каждое правило стиля задаёт И фон, И цвет текста, поэтому вид программы
не зависит от темы Windows (иначе бывает «белый текст на белой кнопке»).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

THEMES = {
    "light": {
        "window": "#f3f4f6", "base": "#ffffff", "alt_base": "#f2f5f9", "text": "#1f2328",
        "muted": "#5f6368", "title": "#2b4a6f", "border": "#c8ccd2", "header": "#e9edf2",
        "button": "#f4f6f8", "button_hover": "#e3eaf3", "button_pressed": "#d3dde9",
        "disabled_bg": "#eceef1", "disabled_text": "#9aa0a6",
        "accent": "#2b6cb0", "accent_hover": "#245a93", "accent_text": "#ffffff",
        "accent_disabled": "#d5dfeb", "accent_disabled_text": "#7a8899",
        "tooltip": "#ffffe1", "indicator": "#7d848d",
        # графики
        "fig": "#ffffff", "axes": "#ffffff", "fg": "#1f2328", "grid": "#b0b0b0",
        "pass": "#1f77b4", "fail": "#cfcfcf", "above_cut": "#9a9a9a",
    },
    "dark": {
        "window": "#1f2227", "base": "#2a2e35", "alt_base": "#30353d", "text": "#e6e8eb",
        "muted": "#a0a6ad", "title": "#8cb8e6", "border": "#474d56", "header": "#343a42",
        "button": "#363c45", "button_hover": "#424953", "button_pressed": "#4d5560",
        "disabled_bg": "#2a2e34", "disabled_text": "#737a83",
        "accent": "#3b82c4", "accent_hover": "#4a92d4", "accent_text": "#ffffff",
        "accent_disabled": "#2c3a4a", "accent_disabled_text": "#7f8d9c",
        "tooltip": "#343a42", "indicator": "#9aa2ab",
        "fig": "#262a30", "axes": "#1f2227", "fg": "#e6e8eb", "grid": "#4d535c",
        "pass": "#4da3e0", "fail": "#4a5058", "above_cut": "#80878f",
    },
}

NAMES = {"light": "светлая", "dark": "тёмная"}

_current = {"name": "light"}


def name() -> str:
    return _current["name"]


def color(key: str) -> str:
    """Цвет текущей темы (для графиков)."""
    return THEMES[_current["name"]][key]


def _palette(t: dict) -> QPalette:
    R = QPalette.ColorRole
    p = QPalette()
    for role, key in ((R.Window, "window"), (R.WindowText, "text"), (R.Base, "base"),
                      (R.AlternateBase, "alt_base"), (R.Text, "text"), (R.Button, "button"),
                      (R.ButtonText, "text"), (R.Highlight, "accent"), (R.HighlightedText, "accent_text"),
                      (R.ToolTipBase, "tooltip"), (R.ToolTipText, "text"), (R.PlaceholderText, "muted"),
                      (R.Link, "accent"), (R.Light, "button_hover"), (R.Midlight, "button"),
                      (R.Mid, "border"), (R.Dark, "border"), (R.Shadow, "window")):
        p.setColor(role, QColor(t[key]))
    for role in (R.Text, R.ButtonText, R.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(t["disabled_text"]))
    for role in (R.Base, R.Button):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(t["disabled_bg"]))
    return p


_STYLE = """
QWidget {{ font-size: 10pt; color: {text}; }}
QMainWindow, QDialog, QMessageBox, QStatusBar {{ background: {window}; color: {text}; }}
/* Сами QCheckBox/QRadioButton не стилизуются (иначе Qt перестаёт рисовать индикатор),
   оформляется только индикатор — чтобы рамка была видна и в тёмной теме. */
QCheckBox::indicator, QRadioButton::indicator {{ width: 14px; height: 14px;
    border: 1px solid {indicator}; background: {base}; }}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; image: url({check_svg}); }}
QRadioButton::indicator:checked {{ background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
    stop:0 {accent_text}, stop:0.35 {accent_text}, stop:0.45 {accent}, stop:1 {accent}); border-color: {accent}; }}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{ background: {disabled_bg}; border-color: {border}; }}

QMenuBar {{ background: {window}; color: {text}; }}
QMenuBar::item:selected {{ background: {button_hover}; color: {text}; }}
QMenu {{ background: {base}; color: {text}; border: 1px solid {border}; }}
QMenu::item:selected {{ background: {accent}; color: {accent_text}; }}

QTabWidget::pane {{ border: 1px solid {border}; background: {window}; top: -1px; }}
QTabBar::tab {{ padding: 7px 18px; background: {button}; color: {text}; border: 1px solid {border};
    border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {window}; color: {text}; font-weight: bold; }}
QTabBar::tab:hover:!selected {{ background: {button_hover}; }}

QGroupBox {{ font-weight: bold; color: {text}; border: 1px solid {border}; border-radius: 6px;
    margin-top: 10px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: {title}; }}
QGroupBox * {{ font-weight: normal; }}

QPushButton {{ padding: 5px 10px; border-radius: 4px; border: 1px solid {border};
    background: {button}; color: {text}; }}
QPushButton:hover {{ background: {button_hover}; color: {text}; }}
QPushButton:pressed {{ background: {button_pressed}; color: {text}; }}
QPushButton:disabled {{ background: {disabled_bg}; color: {disabled_text}; border-color: {border}; }}
QPushButton#primary {{ background: {accent}; color: {accent_text}; border: 1px solid {accent}; font-weight: bold; }}
QPushButton#primary:hover {{ background: {accent_hover}; color: {accent_text}; }}
QPushButton#primary:pressed {{ background: {accent_hover}; color: {accent_text}; }}
QPushButton#primary:disabled {{ background: {accent_disabled}; color: {accent_disabled_text};
    border-color: {accent_disabled}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {base}; color: {text};
    selection-background-color: {accent}; selection-color: {accent_text}; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    background: {disabled_bg}; color: {disabled_text}; }}
QComboBox QAbstractItemView {{ background: {base}; color: {text};
    selection-background-color: {accent}; selection-color: {accent_text}; }}

QPlainTextEdit, QListWidget, QTableWidget {{ background: {base}; color: {text};
    alternate-background-color: {alt_base}; gridline-color: {border};
    selection-background-color: {accent}; selection-color: {accent_text}; }}
QHeaderView::section {{ background: {header}; color: {text}; padding: 4px; border: 0;
    border-right: 1px solid {border}; border-bottom: 1px solid {border}; font-weight: bold; }}
QTableCornerButton::section {{ background: {header}; border: 0; }}

QToolBar {{ background: {fig}; border: 0; }}
QToolButton {{ background: transparent; color: {text}; border: 0; border-radius: 3px; padding: 2px; }}
QToolButton:hover {{ background: {button_hover}; }}
QToolButton:checked {{ background: {button_pressed}; }}
QToolTip {{ background: {tooltip}; color: {text}; border: 1px solid {border}; }}

QLabel#title {{ font-size: 13pt; font-weight: bold; color: {title}; }}
QLabel#big {{ font-size: 11pt; padding: 4px 2px; }}
QLabel#hint {{ color: {muted}; }}
"""


def _mpl_rc(t: dict) -> dict:
    return {
        "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
        "figure.facecolor": t["fig"], "savefig.facecolor": t["fig"],
        "axes.facecolor": t["axes"], "axes.edgecolor": t["fg"], "axes.labelcolor": t["fg"],
        "axes.titlecolor": t["fg"], "text.color": t["fg"],
        "xtick.color": t["fg"], "ytick.color": t["fg"], "grid.color": t["grid"],
        "legend.facecolor": t["axes"], "legend.edgecolor": t["grid"], "legend.labelcolor": t["fg"],
    }


def apply(app, theme_name: str):
    """Применить тему ко всему приложению. Графики после этого нужно перерисовать."""
    if theme_name not in THEMES:
        theme_name = "light"
    _current["name"] = theme_name
    t = THEMES[theme_name]
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):  # Qt 6.8+: не подстраиваться под тему Windows
        hints.setColorScheme(Qt.ColorScheme.Dark if theme_name == "dark" else Qt.ColorScheme.Light)
    app.setStyle("Fusion")
    app.setPalette(_palette(t))
    check_svg = (Path(__file__).resolve().parent / "check.svg").as_posix()
    app.setStyleSheet(_STYLE.format(**t, check_svg=check_svg))
    matplotlib.rcParams.update(_mpl_rc(t))
