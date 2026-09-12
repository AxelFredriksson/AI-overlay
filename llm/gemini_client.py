from __future__ import annotations

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .base import LLMBackend, LLMSession


class LLMError(Exception):
    """User-facing error message, already classified."""


def _classify_error(exc: Exception) -> LLMError:
    code = getattr(exc, "code", None)
    if isinstance(exc, (genai_errors.ClientError, genai_errors.ServerError)):
        if code in (401, 403):
            return LLMError("Ogiltig eller saknad API-nyckel. Kontrollera inställningarna.")
        if code == 429:
            return LLMError("Rate limit nådd — vänta en stund och försök igen.")
        if code == 404:
            return LLMError(
                "Modellen är inte tillgänglig längre. Byt 'model' i settings.json "
                "till en aktuell modell (t.ex. gemini-3.6-flash)."
            )
        return LLMError(f"Gemini-fel ({code}): {exc}")
    if isinstance(exc, ConnectionError):
        return LLMError("Nätverksfel — kontrollera din internetanslutning.")
    return LLMError(f"Oväntat fel: {exc}")


class GeminiSession(LLMSession):
    def __init__(self, chat):
        self._chat = chat

    def ask(self, text: str) -> str:
        try:
            response = self._chat.send_message(text)
        except Exception as exc:  # noqa: BLE001 - classify below
            raise _classify_error(exc) from exc
        return response.text or ""


class GeminiBackend(LLMBackend):
    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        if not api_key.strip():
            raise LLMError("Ingen Gemini API-nyckel har angetts.")
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def start_session(
        self, image_bytes: bytes, mime_type: str, question: str
    ) -> tuple[LLMSession, str]:
        chat = self._client.chats.create(model=self._model)
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        try:
            response = chat.send_message([question, part])
        except Exception as exc:  # noqa: BLE001 - classify below
            raise _classify_error(exc) from exc
        return GeminiSession(chat), (response.text or "")
