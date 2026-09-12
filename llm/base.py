from __future__ import annotations

from abc import ABC, abstractmethod


class LLMSession(ABC):
    """A multi-turn conversation about a single captured image."""

    @abstractmethod
    def ask(self, text: str) -> str:
        """Send a follow-up text-only message and return the answer."""


class LLMBackend(ABC):
    """Factory for starting a new image-grounded conversation."""

    @abstractmethod
    def start_session(
        self, image_bytes: bytes, mime_type: str, question: str
    ) -> tuple[LLMSession, str]:
        """Start a session with an initial image + question, return (session, first_answer)."""
