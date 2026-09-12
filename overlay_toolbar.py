from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

TOOLBAR_HEIGHT = 32
TOOLBAR_MARGIN = 6


class OverlayToolbar(QWidget):
    ask_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setFixedHeight(TOOLBAR_HEIGHT)
        self.setStyleSheet(
            "QWidget { background-color: #222; border-radius: 4px; }"
            "QPushButton { color: white; background-color: #3a3a3a; border: none;"
            " padding: 4px 12px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #555; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        self.ask_button = QPushButton("Fråga")
        self.ask_button.clicked.connect(self.ask_clicked.emit)
        layout.addWidget(self.ask_button)

        self.close_button = QPushButton("✕")
        self.close_button.setFixedWidth(28)
        self.close_button.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self.close_button)

        self.adjustSize()

    def follow(self, box_geometry: QRect) -> None:
        width = self.width()
        x = box_geometry.center().x() - width // 2
        y = box_geometry.top() - TOOLBAR_HEIGHT - TOOLBAR_MARGIN
        screen = QGuiApplication.screenAt(box_geometry.center()) or QGuiApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        if y < screen_rect.top():
            y = box_geometry.bottom() + TOOLBAR_MARGIN
        x = max(screen_rect.left(), min(x, screen_rect.right() - width))
        self.move(x, y)
