"""
Reusable custom Qt widgets.

  LogSignal      — thread-safe signal carrier for log / status / finished
  RingChartWidget — donut/ring chart for success-rate visualization
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QObject, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


# ─────────────────────────────────────────────────────────────────────────────
#  LogSignal
# ─────────────────────────────────────────────────────────────────────────────

class LogSignal(QObject):
    """
    Thread-safe signal carrier used by background automation threads to
    communicate with the main UI thread.

    Signals:
        log(str)      — append a line to the log output widget
        status(str)   — update the status label
        finished()    — automation task completed
    """

    log      = pyqtSignal(str)
    status   = pyqtSignal(str)
    finished = pyqtSignal()


# ─────────────────────────────────────────────────────────────────────────────
#  RingChartWidget
# ─────────────────────────────────────────────────────────────────────────────

class RingChartWidget(QWidget):
    """
    Minimal donut / ring chart that displays a single percentage value.

    Usage:
        chart = RingChartWidget()
        chart.set_percentage(72)   # 0–100
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._percentage: int = 0
        self.setMinimumSize(120, 120)

    # ── public API ────────────────────────────────────────────────────────────

    def set_percentage(self, value: int) -> None:
        """Set the fill percentage (0–100) and trigger a repaint."""
        self._percentage = max(0, min(100, int(value)))
        self.update()

    @property
    def percentage(self) -> int:
        return self._percentage

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size   = min(self.width(), self.height())
        margin = 15
        rect   = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)

        # Background ring
        bg_pen = QPen(QColor("#333333"))
        bg_pen.setWidth(10)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Progress arc
        if self._percentage > 0:
            color = (
                QColor("#4CAF50") if self._percentage >= 70
                else QColor("#FF9800") if self._percentage >= 40
                else QColor("#f44336")
            )
            fg_pen = QPen(color)
            fg_pen.setWidth(10)
            fg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(fg_pen)
            span = int(self._percentage * 3.6 * 16)
            painter.drawArc(rect, 90 * 16, -span)
