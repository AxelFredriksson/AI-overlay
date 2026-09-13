from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal

from llm.gemini_client import LLMError


class AskWorker(QThread):
    """Runs a streaming LLM call off the UI thread.

    ``func`` must return (session, chunk_iterator) where chunk_iterator yields
    the answer as text chunks (may raise LLMError while being consumed).
    """

    chunk_received = Signal(str)
    finished_ok = Signal(object, str)
    failed = Signal(str)
    stopped = Signal(object, str)

    def __init__(self, func: Callable[[], tuple[object, object]], parent=None):
        super().__init__(parent)
        self._func = func
        self._cancel = False

    def request_stop(self) -> None:
        """Best-effort cancellation: stops forwarding further chunks once one arrives."""
        self._cancel = True

    def run(self) -> None:
        try:
            session, stream = self._func()
        except LLMError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - last-resort UI safety net
            self.failed.emit(f"Oväntat fel: {exc}")
            return

        parts: list[str] = []
        try:
            for chunk_text in stream:
                if self._cancel:
                    self.stopped.emit(session, "".join(parts))
                    return
                parts.append(chunk_text)
                self.chunk_received.emit(chunk_text)
        except LLMError as exc:
            if self._cancel:
                self.stopped.emit(session, "".join(parts))
                return
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - last-resort UI safety net
            if self._cancel:
                self.stopped.emit(session, "".join(parts))
                return
            self.failed.emit(f"Oväntat fel: {exc}")
            return

        if self._cancel:
            self.stopped.emit(session, "".join(parts))
            return
        self.finished_ok.emit(session, "".join(parts))
