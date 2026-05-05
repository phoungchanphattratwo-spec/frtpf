"""
MainWindow — re-export shim.

Imports MainWindow from gui.py (the implementation file).
Use a lazy import here to avoid circular import chains:
  gui.py → src.automation.registration → src.ui.widgets → src.ui → src.ui.main_window → gui.py

The lazy import breaks that cycle.
"""

from __future__ import annotations


def _get_main_window():
    """Lazy import to avoid circular dependency at module load time."""
    from gui import MainWindow  # noqa: PLC0415
    return MainWindow


# Expose at module level for normal usage — only triggers when actually accessed
class _LazyMainWindow:
    """Proxy that resolves to the real MainWindow on first attribute access."""
    _cls = None

    def __class_getitem__(cls, item):
        return _get_main_window()[item]

    def __new__(cls, *args, **kwargs):
        real = _get_main_window()
        return real(*args, **kwargs)


# Direct import for code that does: from src.ui.main_window import MainWindow
# This is safe because by the time user code runs, all modules are initialized.
try:
    from gui import MainWindow  # noqa: F401
except ImportError:
    MainWindow = _LazyMainWindow  # type: ignore[assignment,misc]
