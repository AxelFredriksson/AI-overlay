from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from capture import pixmap_to_png_bytes
from config import Config
from history import HistoryStore
from llm.base import LLMBackend
from worker import AskWorker

PANEL_WIDTH = 340
PANEL_MARGIN = 10
THUMB_MAX = 220


class PanelWindow(QWidget):
    def __init__(
        self,
        config: Config,
        backend: LLMBackend | None,
        history: HistoryStore,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._backend = backend
        self._history = history
        self._session = None
        self._session_id = ""
        self._image_rel_path = None
        self._turn = 0
        self._worker: AskWorker | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedWidth(PANEL_WIDTH)
        self.setStyleSheet(
            "QWidget { background-color: #1e1e1e; color: #eee; }"
            "QTextEdit { background-color: #141414; border: 1px solid #333; }"
            "QLineEdit { background-color: #2a2a2a; border: 1px solid #444; padding: 4px; color: #eee; }"
            "QPushButton { background-color: #3a6ea5; border: none; padding: 6px 14px; color: white; border-radius: 3px; }"
            "QPushButton:disabled { background-color: #555; }"
            "QPushButton:hover:!disabled { background-color: #4a82c0; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setFixedHeight(THUMB_MAX)
        layout.addWidget(self.thumbnail_label)

        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setMinimumHeight(180)
        layout.addWidget(self.transcript)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #ff6b6b;")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        input_row = QHBoxLayout()
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("Ställ en fråga om skärmdumpen...")
        self.question_input.returnPressed.connect(self._on_send)
        input_row.addWidget(self.question_input)

        self.send_button = QPushButton("Skicka")
        self.send_button.clicked.connect(self._on_send)
        input_row.addWidget(self.send_button)
        layout.addLayout(input_row)

        if self._backend is None:
            self._disable_input("Ingen Gemini API-nyckel konfigurerad.")

    # -- public API --------------------------------------------------------

    def start_capture(self, pixmap: QPixmap) -> None:
        self._image_bytes = pixmap_to_png_bytes(pixmap)
        self._session = None
        self._turn = 0
        self._session_id = self._history.new_session_id()
        self._image_rel_path = self._history.save_image(self._session_id, pixmap)

        scaled = pixmap.scaled(
            PANEL_WIDTH - 20,
            THUMB_MAX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.thumbnail_label.setPixmap(scaled)
        self.transcript.clear()
        self.status_label.hide()
        self.question_input.clear()
        if self._backend is not None:
            self._set_input_enabled(True)
        self.show()
        self.question_input.setFocus()

    def position_near(self, box_geometry: QRect) -> None:
        screen = QGuiApplication.screenAt(box_geometry.center()) or QGuiApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        x = box_geometry.right() + PANEL_MARGIN
        if x + self.width() > screen_rect.right():
            x = box_geometry.left() - self.width() - PANEL_MARGIN
        if x < screen_rect.left():
            x = screen_rect.right() - self.width()
        y = max(screen_rect.top(), min(box_geometry.top(), screen_rect.bottom() - self.height()))
        self.move(x, y)

    # -- internal ------------------------------------------------------------

    def _on_send(self) -> None:
        question = self.question_input.text().strip()
        if not question or self._backend is None:
            return
        self._pending_question = question
        self.transcript.append(f"<b>Du:</b> {question}")
        self.question_input.clear()
        self._set_input_enabled(False)
        self.status_label.hide()

        if self._session is None:
            func = lambda: self._backend.start_session(self._image_bytes, "image/png", question)
        else:
            session = self._session
            func = lambda: session.ask(question)

        self._worker = AskWorker(func)
        self._worker.succeeded.connect(self._on_success)
        self._worker.failed.connect(self._on_failure)
        self._worker.start()

    def _on_success(self, result) -> None:
        if isinstance(result, tuple):
            session, answer = result
            self._session = session
        else:
            answer = result
        self.transcript.append(f"<b>LLM:</b> {answer}")
        self._turn += 1
        self._history.append_turn(
            self._session_id,
            self._turn,
            self._image_rel_path,
            self._config.model,
            self._pending_question,
            answer,
        )
        self._set_input_enabled(True)
        self.question_input.setFocus()

    def _on_failure(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.show()
        self._set_input_enabled(True)

    def _set_input_enabled(self, enabled: bool) -> None:
        self.question_input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)

    def _disable_input(self, reason: str) -> None:
        self._set_input_enabled(False)
        self.status_label.setText(reason)
        self.status_label.show()
