from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QFrame, QPushButton, QWidget

from llm_overlay.theme import Palette, qss

TOOLBAR_HEIGHT = 44
TOOLBAR_MARGIN = 10

_SEGMENT_SHAPE = (
    "border:none; border-radius:9px; padding:7px 13px;"
    " font-family:'Segoe UI',sans-serif; font-size:13px;"
)


def _segment_style(palette: Palette, *, primary: bool, faint: bool) -> str:
    if primary:
        return qss(
            ("QPushButton", f"background:{palette.accent}; color:{palette.accent_on};"
                            f" {_SEGMENT_SHAPE} font-weight:600;"),
            ("QPushButton:hover", f"background:{palette.accent_hover};"),
        )
    color = palette.ink_faint if faint else palette.ink_soft
    return qss(
        ("QPushButton", f"background:transparent; color:{color}; {_SEGMENT_SHAPE} font-weight:500;"),
        ("QPushButton:hover", f"background:{palette.bubble}; color:{palette.ink}; font-weight:600;"),
        ("QPushButton:disabled", f"color:{palette.ink_faint}; background:transparent;"),
    )


class OverlayToolbar(QWidget):
    ask_clicked = Signal()
    chat_clicked = Signal()
    close_clicked = Signal()
    settings_clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._palette: Palette | None = None
        self._busy = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(TOOLBAR_HEIGHT)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._pill = QFrame(self)
        self._pill.setObjectName("pill")
        layout = QHBoxLayout(self._pill)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        outer.addWidget(self._pill)

        self.ask_button = QPushButton("Fråga")
        self.ask_button.clicked.connect(self.ask_clicked.emit)
        layout.addWidget(self.ask_button)

        self.chat_button = QPushButton("Chatt")
        self.chat_button.setToolTip("Öppna chatten utan skärmdump")
        self.chat_button.clicked.connect(self.chat_clicked.emit)
        layout.addWidget(self.chat_button)

        self.settings_button = QPushButton("Inställningar")
        self.settings_button.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_button)

        self._separator = QFrame()
        self._separator.setFixedSize(1, 20)
        layout.addWidget(self._separator)

        self.close_button = QPushButton("Dölj")
        self.close_button.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self.close_button)

        for button in (self.ask_button, self.chat_button, self.settings_button, self.close_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.adjustSize()

    # -- theming -------------------------------------------------------

    def apply_theme(self, palette: Palette) -> None:
        self._palette = palette
        self._pill.setStyleSheet(
            qss(("#pill", f"background:{palette.surface}; border:1px solid {palette.border};"
                          " border-radius:13px;"))
        )
        self._separator.setStyleSheet(qss(("QFrame", f"background:{palette.border_soft}; border:none;")))
        self._restyle_buttons()

    def _restyle_buttons(self) -> None:
        if self._palette is None:
            return
        p = self._palette
        if self._busy:
            self.ask_button.setStyleSheet(
                qss(("QPushButton", f"background:{p.bubble}; color:{p.accent};"
                                    f" {_SEGMENT_SHAPE} font-weight:600;"))
            )
        else:
            self.ask_button.setStyleSheet(_segment_style(p, primary=True, faint=False))
        self.chat_button.setStyleSheet(_segment_style(p, primary=False, faint=self._busy))
        self.settings_button.setStyleSheet(_segment_style(p, primary=False, faint=self._busy))
        self.close_button.setStyleSheet(_segment_style(p, primary=False, faint=True))

    # -- state -----------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.ask_button.setText("Fångar…" if busy else "Fråga")
        self.chat_button.setEnabled(not busy)
        self.settings_button.setEnabled(not busy)
        self.close_button.setVisible(not busy)
        self._separator.setVisible(not busy)
        self._restyle_buttons()
        self.adjustSize()

    # -- layout ------------------------------------------------------------

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
