from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QRect, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication, QPixmap
from PySide6.QtWidgets import QVBoxLayout, QWidget

from llm_overlay.capture import pixmap_to_png_bytes
from llm_overlay.config import Config
from llm_overlay.history import HistoryStore
from llm_overlay.llm.base import LLMBackend
from llm_overlay.llm.gemini_client import supports_thinking
from llm_overlay.markdown_lite import to_html
from llm_overlay.theme import ThemeManager, css_variables
from llm_overlay.ui.webview import build_web_view
from llm_overlay.worker import AskWorker

PANEL_WIDTH = 436
PANEL_HEIGHT = 620
PANEL_MARGIN = 10

SHORT_DETAIL_LABELS = {"kort": "kort", "medel": "medel", "detaljerad": "detaljerad"}
SHORT_THINKING_LABELS = {"dynamic": "standard", "low": "låg", "medium": "medel", "high": "hög"}
THEME_LABELS = {"system": "system", "light": "ljust", "dark": "mörkt"}


def _format_hotkey(combo: str) -> str:
    return "+".join(part.capitalize() for part in combo.split("+") if part)


def _date_group_label(when: datetime) -> str:
    today = datetime.now().date()
    day = when.date()
    if day == today:
        return "IDAG"
    if day == today - timedelta(days=1):
        return "IGÅR"
    return day.strftime("%d %b").upper()


def _data_url(pixmap: QPixmap, width: int, height: int) -> str:
    scaled = pixmap.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    encoded = base64.b64encode(pixmap_to_png_bytes(scaled)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


class PanelBridge(QObject):
    """Owns the conversation; the web page is a pure view over the state it publishes."""

    stateChanged = Signal(str)
    chunkReceived = Signal(str)
    historyLoaded = Signal(str)
    openSettingsRequested = Signal()
    closeRequested = Signal()

    def __init__(
        self,
        config: Config,
        backend: LLMBackend | None,
        history: HistoryStore,
        theme_manager: ThemeManager,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._backend = backend
        self._history = history
        self._theme = theme_manager

        self._messages: list[dict] = []
        self._session = None
        self._session_id = ""
        self._session_title = "Ny session"
        self._image_bytes: bytes | None = None
        self._image_thumbnail = ""
        self._image_meta = ""
        self._image_rel_path = None
        self._capture_pixmap: QPixmap | None = None
        self._turn = 0
        self._view = "transcript"
        self._streaming = False
        self._pending_answer = ""
        self._pending_question = ""
        self._worker: AskWorker | None = None

        self._theme.changed.connect(self._push_state)

    # -- state ---------------------------------------------------------------

    def _state(self) -> dict:
        image = (
            {"thumbnail": self._image_thumbnail, "meta": self._image_meta}
            if self._image_bytes is not None
            else None
        )
        return {
            "theme": {
                "mode": self._theme.mode,
                "label": THEME_LABELS.get(self._theme.mode, self._theme.mode),
                "vars": css_variables(self._theme.palette),
            },
            "hasBackend": self._backend is not None,
            "sessionTitle": self._session_title,
            "image": image,
            "messages": self._messages,
            "streaming": self._streaming,
            "view": self._view,
            "meta": {
                "model": self._config.model,
                "detail": SHORT_DETAIL_LABELS.get(self._config.detail_level, self._config.detail_level),
                # Gemma ignores the thinking level, so don't claim one in the footer.
                "thinking": (
                    SHORT_THINKING_LABELS.get(self._config.thinking_level, self._config.thinking_level)
                    if supports_thinking(self._config.model)
                    else "–"
                ),
                "hotkey": _format_hotkey(self._config.hotkey),
            },
        }

    # Every method connected to a signal below must stay @Slot-decorated. Connecting a signal to an
    # undecorated Python method of the object registered on the QWebChannel makes PySide rebuild its
    # metaobject, which invalidates the signal indices the channel captured during the handshake —
    # the page then silently stops receiving updates from the first streamed answer onwards.
    @Slot()
    def _push_state(self) -> None:
        self.stateChanged.emit(json.dumps(self._state()))

    # -- slots called from the page --------------------------------------------

    @Slot()
    def ready(self) -> None:
        self._push_state()

    @Slot(str)
    def send(self, question: str) -> None:
        self.submit(question.strip())

    @Slot()
    def stop(self) -> None:
        if self._worker is not None:
            self._worker.request_stop()

    @Slot()
    def regenerate(self) -> None:
        if self._streaming or not self._pending_question:
            return
        while self._messages and self._messages[-1]["role"] == "assistant":
            self._messages.pop()
        if self._messages and self._messages[-1]["role"] == "user":
            self._messages.pop()
        self.submit(self._pending_question)

    @Slot()
    def newSession(self) -> None:  # noqa: N802 - JS-facing name
        self.start_chat()

    @Slot()
    def removeImage(self) -> None:  # noqa: N802 - JS-facing name
        self._image_bytes = None
        self._image_thumbnail = ""
        self._push_state()

    @Slot()
    def openSettings(self) -> None:  # noqa: N802 - JS-facing name
        self.openSettingsRequested.emit()

    @Slot()
    def closePanel(self) -> None:  # noqa: N802 - JS-facing name
        self.closeRequested.emit()

    @Slot()
    def cycleTheme(self) -> None:  # noqa: N802 - JS-facing name
        self._theme.cycle()

    @Slot(str)
    def setView(self, view: str) -> None:  # noqa: N802 - JS-facing name
        self._view = "history" if view == "history" else "transcript"
        self._push_state()
        if self._view == "history":
            self.searchHistory("")

    @Slot(str)
    def searchHistory(self, query: str) -> None:  # noqa: N802 - JS-facing name
        sessions = self._history.list_sessions()
        needle = query.strip().lower()
        groups: list[dict] = []
        for summary in sessions:
            if needle and needle not in summary.first_question.lower():
                continue
            label = _date_group_label(summary.started_at)
            if not groups or groups[-1]["label"] != label:
                groups.append({"label": label, "items": []})
            groups[-1]["items"].append(
                {
                    "id": summary.session_id,
                    "title": summary.first_question,
                    "time": summary.started_at.strftime("%H:%M"),
                    "turns": summary.turn_count,
                    "thumbnail": self._session_thumbnail(summary.image_path),
                }
            )
        self.historyLoaded.emit(json.dumps({"groups": groups, "total": len(sessions)}))

    @staticmethod
    def _session_thumbnail(image_path) -> str:
        if image_path is None or not image_path.exists():
            return ""
        pixmap = QPixmap(str(image_path))
        return "" if pixmap.isNull() else _data_url(pixmap, 92, 62)

    @Slot(str)
    def openSession(self, session_id: str) -> None:  # noqa: N802 - JS-facing name
        turns = self._history.load_session(session_id)
        # Past sessions can't be resumed (the backend session object isn't persisted), so this
        # replays the old turns for reference and opens a fresh session underneath: sending a new
        # message starts a brand-new, correctly-numbered conversation.
        self._begin_session(has_image=False)
        detail = SHORT_DETAIL_LABELS.get(self._config.detail_level, self._config.detail_level)
        for turn in turns:
            self._messages.append({"role": "user", "html": to_html(turn.question)})
            self._messages.append(
                {
                    "role": "assistant",
                    "html": to_html(turn.answer),
                    "text": turn.answer,
                    "caption": f"Gemini · {detail}",
                    "canRegenerate": False,
                }
            )
        if turns:
            self._set_title(turns[0].question)
        self._view = "transcript"
        self._push_state()

    @Slot()
    def openHistoryFolder(self) -> None:  # noqa: N802 - JS-facing name
        self._history.base_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._history.base_dir)))

    @Slot(str)
    def copyText(self, text: str) -> None:  # noqa: N802 - JS-facing name
        QGuiApplication.clipboard().setText(text)

    # -- session lifecycle -----------------------------------------------------

    def set_backend(self, backend: LLMBackend | None) -> None:
        self._backend = backend
        self._push_state()

    def start_capture(self, pixmap: QPixmap) -> None:
        self._capture_pixmap = pixmap
        self._image_bytes = pixmap_to_png_bytes(pixmap)
        self._image_thumbnail = _data_url(pixmap, 148, 92)
        self._image_meta = (
            f"{pixmap.width()} × {pixmap.height()} px · {datetime.now().strftime('%H:%M')}"
        )
        self._begin_session(has_image=True)
        self._push_state()

    def start_chat(self) -> None:
        self._capture_pixmap = None
        self._image_bytes = None
        self._image_thumbnail = ""
        self._begin_session(has_image=False)
        self._push_state()

    def _begin_session(self, *, has_image: bool) -> None:
        self._session = None
        self._messages = []
        self._turn = 0
        self._session_title = "Ny session"
        self._pending_question = ""
        self._view = "transcript"
        if self._config.save_history:
            self._session_id = self._history.new_session_id()
            self._image_rel_path = (
                self._history.save_image(self._session_id, self._capture_pixmap) if has_image else None
            )
        else:
            self._session_id = ""
            self._image_rel_path = None

    def _set_title(self, question: str) -> None:
        title = question.strip().splitlines()[0] if question.strip() else "Ny session"
        if len(title) > 40:
            title = title[:39].rstrip() + "…"
        self._session_title = title or "Ny session"

    # -- asking ----------------------------------------------------------------

    def submit(self, question: str) -> None:
        if not question or self._backend is None or self._streaming:
            return
        self._pending_question = question
        if self._turn == 0:
            self._set_title(question)

        self._messages.append({"role": "user", "html": to_html(question)})
        thinking = SHORT_THINKING_LABELS.get(self._config.thinking_level, self._config.thinking_level)
        self._messages.append(
            {
                "role": "assistant",
                "html": "",
                "text": "",
                "caption": f"Gemini tänker · {thinking}",
                "canRegenerate": False,
            }
        )
        self._pending_answer = ""
        self._streaming = True
        self._view = "transcript"
        self._push_state()

        if self._session is None:
            detail_level = self._config.detail_level
            thinking_level = self._config.thinking_level
            if self._image_bytes is not None:
                image_bytes = self._image_bytes
                func = lambda: self._backend.start_session(
                    image_bytes, "image/png", question, detail_level, thinking_level
                )
            else:
                func = lambda: self._backend.start_text_session(question, detail_level, thinking_level)
        else:
            session = self._session
            func = lambda: (session, session.ask(question))

        self._worker = AskWorker(func)
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.finished_ok.connect(self._on_success)
        self._worker.failed.connect(self._on_failure)
        self._worker.stopped.connect(self._on_stopped)
        self._worker.start()

    @Slot(str)
    def _on_chunk(self, text: str) -> None:
        self._pending_answer += text
        self.chunkReceived.emit(to_html(self._pending_answer))

    def _complete_answer(self, session, answer: str) -> None:
        self._session = session
        self._streaming = False
        detail = SHORT_DETAIL_LABELS.get(self._config.detail_level, self._config.detail_level)
        self._messages[-1] = {
            "role": "assistant",
            "html": to_html(answer),
            "text": answer,
            "caption": f"Gemini · {detail}",
            "canRegenerate": True,
        }
        self._turn += 1
        if self._config.save_history and answer:
            self._history.append_turn(
                self._session_id,
                self._turn,
                self._image_rel_path,
                self._config.model,
                self._pending_question,
                answer,
            )
        self._push_state()

    @Slot(object, str)
    def _on_success(self, session, answer: str) -> None:
        self._complete_answer(session, answer)

    @Slot(object, str)
    def _on_stopped(self, session, partial_answer: str) -> None:
        self._complete_answer(session, partial_answer)

    @Slot(str)
    def _on_failure(self, message: str) -> None:
        self._streaming = False
        self._messages[-1] = {
            "role": "assistant",
            "html": to_html(message),
            "text": message,
            "caption": "Fel",
            "canRegenerate": True,
        }
        self._push_state()


class PanelWindow(QWidget):
    open_settings_requested = Signal()

    def __init__(
        self,
        config: Config,
        backend: LLMBackend | None,
        history: HistoryStore,
        theme_manager: ThemeManager,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._config = config

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(PANEL_WIDTH)
        self.resize(PANEL_WIDTH, PANEL_HEIGHT)

        self.bridge = PanelBridge(config, backend, history, theme_manager, self)
        self.bridge.openSettingsRequested.connect(self.open_settings_requested.emit)
        self.bridge.closeRequested.connect(self.hide)

        self.view = build_web_view("panel.html", self.bridge, transparent=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    # -- public API -------------------------------------------------------------

    def set_backend(self, backend: LLMBackend | None) -> None:
        self.bridge.set_backend(backend)

    def start_capture(self, pixmap: QPixmap) -> None:
        self.bridge.start_capture(pixmap)
        self.show()
        self.view.setFocus()

    def start_chat(self) -> None:
        self.bridge.start_chat()
        self.show()
        self.view.setFocus()

    def submit_auto(self) -> None:
        self.bridge.submit(self._config.auto_send_question)

    def position_near(self, box_geometry: QRect) -> None:
        screen = QGuiApplication.screenAt(box_geometry.center()) or QGuiApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        max_height = screen_rect.height() - 2 * PANEL_MARGIN
        if self.height() > max_height:
            self.resize(self.width(), max_height)
        x = box_geometry.right() + PANEL_MARGIN
        if x + self.width() > screen_rect.right():
            x = box_geometry.left() - self.width() - PANEL_MARGIN
        if x < screen_rect.left():
            x = screen_rect.right() - self.width()
        y = max(screen_rect.top(), min(box_geometry.top(), screen_rect.bottom() - self.height()))
        self.move(x, y)
