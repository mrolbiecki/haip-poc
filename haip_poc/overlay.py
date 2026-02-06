"""Standard application window for the agent."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CloseButton(QPushButton):
    """Small X button to close the application."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("×", parent)
        self.setFixedSize(20, 20)
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(200, 60, 60, 180);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(220, 80, 80, 220);
            }
            QPushButton:pressed {
                background-color: rgba(180, 40, 40, 220);
            }
        """)


class AgentIcon(QWidget):
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


class AgentWindow(QWidget):
    """Main agent window with status and question display."""

    close_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HAIP Agent")
        self.resize(500, 300)
        
        # Determine background color based on system theme or default to dark
        # using a stylesheet for basic theming
        self.setStyleSheet("background-color: #2b2b2b; color: #ffffff;")

        # Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header: Icon + Status
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        self._icon = AgentIcon()
        self._status_label = QLabel("Ready")
        self._status_label.setFont(QFont("Sans", 10))
        self._status_label.setStyleSheet("color: #aaaaaa;")
        
        header_layout.addWidget(self._icon)
        header_layout.addWidget(self._status_label)
        header_layout.addStretch()

        # Question Display
        self._question_label = QLabel("")
        self._question_label.setWordWrap(True)
        self._question_label.setFont(QFont("Sans", 14))
        self._question_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # Add to main layout
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self._question_label, stretch=1)
        
        # Center on screen initially
        self._center_on_screen()

    # -- public API ----------------------------------------------------------

    @property
    def icon(self) -> AgentIcon:
        return self._icon

    def set_question(self, text: str) -> None:
        self._question_label.setText(text)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    # -- internal ------------------------------------------------------------

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        center = geo.center()
        frame_geo = self.frameGeometry()
        frame_geo.moveCenter(center)
        self.move(frame_geo.topLeft())
