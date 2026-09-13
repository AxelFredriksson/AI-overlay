from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator


class LLMSession(ABC):
    """A multi-turn conversation about a single captured image."""

    @abstractmethod
    def ask(self, text: str) -> Iterator[str]:
        """Send a follow-up text-only message, yielding the answer as text chunks."""


class LLMBackend(ABC):
    """Factory for starting a new image-grounded conversation."""

    @abstractmethod
    def start_session(
        self,
        image_bytes: bytes,
        mime_type: str,
        question: str,
        detail_level: str = "medel",
        thinking_level: str = "dynamic",
    ) -> tuple[LLMSession, Iterator[str]]:
        """Start a session with an initial image + question.

        Returns (session, answer_chunks) where answer_chunks yields the first
        answer as it streams in.
        """

    @abstractmethod
    def start_text_session(
        self,
        question: str,
        detail_level: str = "medel",
        thinking_level: str = "dynamic",
    ) -> tuple[LLMSession, Iterator[str]]:
        """Start a text-only session (no screenshot), e.g. from the toolbar's Chat button."""
