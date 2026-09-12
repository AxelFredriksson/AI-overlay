from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal

from llm.gemini_client import LLMError


class AskWorker(QThread):
    """Runs a blocking LLM call off the UI thread."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, func: Callable[[], object], parent=None):
        super().__init__(parent)
        self._func = func

    def run(self) -> None:
        try:
            result = self._func()
        except LLMError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - last-resort UI safety net
            self.failed.emit(f"Oväntat fel: {exc}")
        else:
            self.succeeded.emit(result)
