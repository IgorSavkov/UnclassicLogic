"""Темы (светлая, тёмная, ночная): палитра Qt, стиль виджетов и цвета графиков matplotlib.

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
        "highlight": "#d97706",  # подсветка выделенных в таблице кривых (янтарный)
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
        "highlight": "#f5b73b",
        "fig": "#262a30", "axes": "#1f2227", "fg": "#e6e8eb", "grid": "#4d535c",
        "pass": "#4da3e0", "fail": "#4a5058", "above_cut": "#80878f",
    },
    # «Ночная»: чернильно-синий фон, карточки заливкой без контуров, вкладки-подчёркивания.
    # Акцент интерфейса — барвинковый: его нет среди цветов данных (красный — выбранная,
    # синий — подходят, серый — не подходят, янтарный — выделены), кнопки не спорят с кривыми.
    "night": {
        "window": "#10141b", "base": "#121721", "alt_base": "#161c27", "text": "#e3e8f1",
        "muted": "#8c97a8", "title": "#c3cee0", "border": "#2a3240", "header": "#171d28",
        "button": "#232b39", "button_hover": "#2c3647", "button_pressed": "#354055",
        "disabled_bg": "#171c25", "disabled_text": "#5c6779",
        "accent": "#6a75e8", "accent_hover": "#7c87f0", "accent_text": "#ffffff",
        "accent_disabled": "#262c45", "accent_disabled_text": "#6c7491",
        "tooltip": "#222a38", "indicator": "#5d6879",
        "highlight": "#f5b73b",
        # только для «ночной»
        "surface": "#1a1f2b", "card_border": "#222938", "selection": "#2e3566",
        "grid_line": "#1f2632", "scroll": "#343e50",
        # графики: фон рисунка в тон карточки, поле осей — «вдавленное», как таблицы
        "fig": "#1a1f2b", "axes": "#121721", "fg": "#c5cedc", "grid": "#2a3343",
        "spine": "#3a4456",
        "pass": "#58a6ee", "fail": "#455063", "above_cut": "#6f7a8c",
    },
}

NAMES = {"light": "светлая", "dark": "тёмная", "night": "ночная (современная)"}
DEFAULT = "night"

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

QLabel#big {{ font-size: 11pt; padding: 4px 2px; }}
QLabel#hint {{ color: {muted}; }}
"""

# Дополнение для «ночной» темы: поверх общих правил (позже — значит важнее).
# Если у поля ввода задана рамка, Qt рисует его целиком по стилю — поэтому стрелки
# счётчиков и списков заданы явно (arrow_up/down.svg).
_NIGHT = """
QWidget {{ font-family: "Segoe UI Variable Text", "Segoe UI"; }}
QStatusBar {{ border-top: 1px solid {card_border}; color: {muted}; }}
QStatusBar QLabel {{ color: {muted}; }}

QMenuBar {{ padding: 3px 6px; }}
QMenuBar::item {{ padding: 4px 10px; border-radius: 5px; background: transparent; }}
QMenuBar::item:selected {{ background: {button_hover}; }}
QMenu {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 28px 6px 14px; border-radius: 5px; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 4px 8px; }}

QTabWidget::pane {{ border: none; border-top: 1px solid {card_border}; background: {window}; top: 0px; }}
QTabBar::tab {{ background: transparent; color: {muted}; border: none; border-bottom: 2px solid transparent;
    padding: 9px 16px 7px 16px; margin-right: 2px; }}
QTabBar::tab:selected {{ background: transparent; color: {text}; border-bottom: 2px solid {accent}; font-weight: 600; }}
QTabBar::tab:hover:!selected {{ background: transparent; color: {text}; border-bottom: 2px solid {border}; }}

/* карточки: заливка чуть светлее фона, заголовок — шапка внутри карточки.
   Левый край заголовка = левый край содержимого: рамка 1 + отступ 8 + поле layout 9 = 18px. */
QGroupBox {{ background: {surface}; border: 1px solid {card_border}; border-radius: 10px;
    margin-top: 0px; padding: 30px 8px 8px 8px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: padding; subcontrol-position: top left; left: 17px; top: 11px;
    padding: 0; color: {title}; background: transparent; }}
QSplitter::handle {{ background: transparent; }}

QPushButton {{ padding: 6px 12px; border-radius: 7px; border: 1px solid {border}; }}
QPushButton:focus {{ border-color: {accent}; }}
QPushButton#primary {{ border: 1px solid {accent}; padding: 6px 8px; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ border: 1px solid {border}; border-radius: 6px;
    padding: 3px 6px; min-height: 20px; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {accent}; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ border-color: {card_border}; }}
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; width: 18px; border: none; background: transparent; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-position: top right; margin: 2px 2px 0 0; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-position: bottom right; margin: 0 2px 2px 0; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: {button_hover}; border-radius: 4px; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({arrow_up}); width: 10px; height: 10px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QComboBox::down-arrow {{ image: url({arrow_down});
    width: 10px; height: 10px; }}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled, QSpinBox::down-arrow:disabled,
QDoubleSpinBox::down-arrow:disabled, QComboBox::down-arrow:disabled {{ image: none; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 22px; border: none; }}
QComboBox QLineEdit {{ border: none; padding: 0px; background: transparent; min-height: 0px; }}
QComboBox QAbstractItemView {{ border: 1px solid {border}; border-radius: 6px; padding: 4px; outline: 0; }}

QCheckBox::indicator, QRadioButton::indicator {{ width: 15px; height: 15px; }}
QCheckBox::indicator {{ border-radius: 4px; }}

QSlider::groove:horizontal {{ height: 4px; background: {border}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {text}; border: 3px solid {accent}; width: 10px; height: 10px;
    margin: -6px 0; border-radius: 8px; }}
QSlider::handle:horizontal:hover {{ background: #ffffff; }}

QPlainTextEdit, QListWidget, QTableWidget {{ border: 1px solid {card_border}; border-radius: 8px;
    gridline-color: {grid_line}; selection-background-color: {selection}; selection-color: {text}; }}
QHeaderView::section {{ background: {header}; color: {muted}; border: none;
    border-bottom: 1px solid {border}; padding: 6px 8px; font-weight: 600; }}
QTableCornerButton::section {{ background: {header}; border: none; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {scroll}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:horizontal {{ background: {scroll}; border-radius: 3px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: {muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolButton {{ border-radius: 6px; padding: 3px; }}
QToolTip {{ border-radius: 6px; padding: 6px; }}
"""


def _mpl_rc(t: dict) -> dict:
    night = "surface" in t
    return {
        # шрифт и рамка задаются во всех темах — иначе после «ночной» они остались бы в других
        "font.family": ["Segoe UI", "DejaVu Sans"] if night else ["DejaVu Sans"],
        "axes.spines.top": not night, "axes.spines.right": not night,
        "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
        "figure.facecolor": t["fig"], "savefig.facecolor": t["fig"],
        "axes.facecolor": t["axes"], "axes.edgecolor": t.get("spine", t["fg"]), "axes.labelcolor": t["fg"],
        "axes.titlecolor": t["fg"], "text.color": t["fg"],
        "xtick.color": t["fg"], "ytick.color": t["fg"], "grid.color": t["grid"],
        "legend.facecolor": t.get("surface", t["axes"]), "legend.edgecolor": t.get("border", t["grid"]),
        "legend.labelcolor": t["fg"],
    }


def apply(app, theme_name: str):
    """Применить тему ко всему приложению. Графики после этого нужно перерисовать."""
    if theme_name not in THEMES:
        theme_name = DEFAULT
    _current["name"] = theme_name
    t = THEMES[theme_name]
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):  # Qt 6.8+: не подстраиваться под тему Windows
        hints.setColorScheme(Qt.ColorScheme.Light if theme_name == "light" else Qt.ColorScheme.Dark)
    app.setStyle("Fusion")
    app.setPalette(_palette(t))
    here = Path(__file__).resolve().parent
    icons = {k: (here / f"{k}.svg").as_posix() for k in ("check", "arrow_up", "arrow_down")}
    style = _STYLE.format(**t, check_svg=icons["check"])
    if theme_name == "night":
        style += _NIGHT.format(**t, **icons)
    app.setStyleSheet(style)
    matplotlib.rcParams.update(_mpl_rc(t))
