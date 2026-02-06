"""Transparent always-on-top overlay window using PyQt6."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class OverlayIcon(QWidget):
    """Small circular indicator that pulses when the agent is active."""

    RADIUS = 28

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.RADIUS * 2, self.RADIUS * 2)
        self._color = QColor(100, 100, 100, 180)
        self._pulse_on = False

        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._toggle_pulse)

    def set_active(self, active: bool) -> None:
        if active:
            self._color = QColor(46, 204, 113, 220)
            self._pulse_timer.start(600)
        else:
            self._color = QColor(100, 100, 100, 180)
            self._pulse_timer.stop()
            self._pulse_on = False
        self.update()

    def set_listening(self, listening: bool) -> None:
        if listening:
            self._color = QColor(231, 76, 60, 220)
            self._pulse_timer.start(400)
        else:
            self.set_active(True)

    def _toggle_pulse(self) -> None:
        self._pulse_on = not self._pulse_on
        self.update()

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(self._color)
        if self._pulse_on:
            color.setAlpha(max(color.alpha() - 60, 80))

        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)

        path = QPainterPath()
        path.addEllipse(2, 2, self.RADIUS * 2 - 4, self.RADIUS * 2 - 4)
        painter.drawPath(path)

        # Mic icon (simple lines)
        painter.setPen(QColor(255, 255, 255, 230))
        cx, cy = self.RADIUS, self.RADIUS
        painter.drawLine(cx, cy - 8, cx, cy + 4)
        painter.drawLine(cx - 5, cy + 4, cx + 5, cy + 4)
        painter.drawLine(cx - 5, cy - 2, cx - 5, cy + 4)
        painter.drawLine(cx + 5, cy - 2, cx + 5, cy + 4)
        painter.end()


class OverlayPanel(QWidget):
    """Expanded panel showing current question and status."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self._question_label = QLabel("")
        self._question_label.setWordWrap(True)
        self._question_label.setFont(QFont("Sans", 12))
        self._question_label.setStyleSheet("color: white;")

        self._status_label = QLabel("")
        self._status_label.setFont(QFont("Sans", 10))
        self._status_label.setStyleSheet("color: rgba(255,255,255,0.7);")

        layout.addWidget(self._question_label)
        layout.addWidget(self._status_label)

    def set_question(self, text: str) -> None:
        self._question_label.setText(text)
        self.adjustSize()

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(30, 30, 30, 210))
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        painter.drawPath(path)
        painter.end()


class OverlayWindow(QWidget):
    """Main overlay window – positions itself in the bottom-right corner."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.setGraphicsEffect(shadow)

        # Layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self._panel = OverlayPanel()
        self._icon = OverlayIcon()

        main_layout.addWidget(self._panel)
        main_layout.addWidget(self._icon)

        self._panel.hide()
        self._reposition()

    # -- public API ----------------------------------------------------------

    @property
    def panel(self) -> OverlayPanel:
        return self._panel

    @property
    def icon(self) -> OverlayIcon:
        return self._icon

    def expand(self) -> None:
        self._panel.show()
        self.adjustSize()
        self._reposition()

    def collapse(self) -> None:
        self._panel.hide()
        self.adjustSize()
        self._reposition()

    # -- internal ------------------------------------------------------------

    def _reposition(self) -> None:
        """Place the widget in the bottom-right of the primary screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.adjustSize()
        x = geo.right() - self.width() - 24
        y = geo.bottom() - self.height() - 24
        self.move(x, y)
