"""
i18n engine — translate(), register_widget(), apply_language().

Usage:
    from src.i18n import _T, _reg, apply_language

    label = _reg(QLabel(), "tab_dashboard")          # auto-sets text + registers
    apply_language("ខ្មែរ")                           # updates all registered widgets
"""

from __future__ import annotations
from typing import List, Tuple

from .translations import TRANSLATIONS

# ── mutable singleton so closures can mutate it ──────────────────────────────
_CURRENT_LANG: List[str] = ["EN"]

# Registry: (widget, translation_key, attribute)
# attribute is one of: "text" | "placeholder" | "title" | "window_title"
_REGISTRY: List[Tuple] = []

# Alias used by legacy gui.py code that references _I18N_REGISTRY directly
_I18N_REGISTRY = _REGISTRY

# Cached Khmer font family (loaded once on first use)
_KHMER_FONT_FAMILY: List[str | None] = [None]


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

def translate(key: str) -> str:
    """Return the translated string for *key* in the current language.
    Falls back to EN if the key is missing in the active language."""
    lang = _CURRENT_LANG[0]
    return (
        TRANSLATIONS.get(lang, TRANSLATIONS["EN"])
        .get(key, TRANSLATIONS["EN"].get(key, key))
    )

# Convenient short alias used throughout the codebase
_T = translate


def register_widget(widget, key: str, attr: str = "text"):
    """Register *widget* for automatic language updates and apply text now.

    Args:
        widget: Any Qt widget with setText / setPlaceholderText / setTitle /
                setWindowTitle.
        key:    Translation key from TRANSLATIONS.
        attr:   Which setter to call — "text" | "placeholder" | "title" |
                "window_title".

    Returns the widget so calls can be chained:
        label = _reg(QLabel(), "tab_dashboard")
    """
    _REGISTRY.append((widget, key, attr))
    _apply_widget(widget, key, attr)
    return widget

# Convenient short alias
_reg = register_widget


def get_current_lang() -> str:
    """Return the active language code, e.g. "EN", "VI", "ខ្មែរ"."""
    return _CURRENT_LANG[0]


def apply_language(lang: str) -> None:
    """Switch the active language and refresh every registered widget."""
    if lang not in TRANSLATIONS:
        return

    _CURRENT_LANG[0] = lang

    from PyQt6.QtGui import QFont as _QFont
    from PyQt6.QtWidgets import QApplication

    if lang == "ខ្មែរ":
        font_family = _get_khmer_font()
        _apply_khmer_stylesheet(font_family)
    else:
        _remove_khmer_stylesheet()
        font_family = "Segoe UI"

    for widget, key, attr in _REGISTRY:
        try:
            _apply_widget(widget, key, attr)
            if attr == "text" and lang == "ខ្មែរ" and hasattr(widget, "setFont"):
                widget.setFont(_QFont(font_family, 22))
        except RuntimeError:
            pass  # widget was already destroyed — skip silently


# ─────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _apply_widget(widget, key: str, attr: str) -> None:
    text = translate(key)
    if attr == "text" and hasattr(widget, "setText"):
        widget.setText(text)
    elif attr == "placeholder" and hasattr(widget, "setPlaceholderText"):
        widget.setPlaceholderText(text)
    elif attr == "title" and hasattr(widget, "setTitle"):
        widget.setTitle(text)
    elif attr == "window_title" and hasattr(widget, "setWindowTitle"):
        widget.setWindowTitle(text)


def _load_khmer_font() -> str:
    """Download NotoSansKhmer to temp dir (once) and register it with Qt."""
    import os
    import tempfile
    from PyQt6.QtGui import QFontDatabase

    tmp = os.path.join(tempfile.gettempdir(), "NotoSansKhmer-Regular.ttf")
    if not os.path.exists(tmp):
        try:
            import urllib.request
            urllib.request.urlretrieve(
                "https://github.com/googlefonts/noto-fonts/raw/main/"
                "hinted/ttf/NotoSansKhmer/NotoSansKhmer-Regular.ttf",
                tmp,
            )
        except Exception:
            return "Khmer UI"

    fid = QFontDatabase.addApplicationFont(tmp)
    if fid >= 0:
        families = QFontDatabase.applicationFontFamilies(fid)
        if families:
            return families[0]
    return "Khmer UI"


def _get_khmer_font() -> str:
    if _KHMER_FONT_FAMILY[0] is None:
        _KHMER_FONT_FAMILY[0] = _load_khmer_font()
    return _KHMER_FONT_FAMILY[0]


def _apply_khmer_stylesheet(font_family: str) -> None:
    from PyQt6.QtWidgets import QApplication

    override = f"""
    QMainWindow, QWidget, QLabel, QPushButton, QLineEdit, QTextEdit, QGroupBox {{
        font-family: '{font_family}', 'Segoe UI', sans-serif !important;
        font-size: 22px !important;
    }}
    QTabBar::tab {{
        font-family: '{font_family}', 'Segoe UI', sans-serif !important;
        font-size: 20px !important;
    }}
    """
    app = QApplication.instance()
    if not app:
        return
    style = app.styleSheet()
    if "/* KHMER_OVERRIDE */" in style:
        style = style.split("/* KHMER_OVERRIDE */")[0]
    app.setStyleSheet(style + "\n/* KHMER_OVERRIDE */\n" + override)


def _remove_khmer_stylesheet() -> None:
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if not app:
        return
    style = app.styleSheet()
    if "/* KHMER_OVERRIDE */" in style:
        app.setStyleSheet(style.split("/* KHMER_OVERRIDE */")[0])
