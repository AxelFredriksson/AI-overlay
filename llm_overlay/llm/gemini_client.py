from __future__ import annotations

from collections.abc import Iterator

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .base import LLMBackend, LLMSession


class LLMError(Exception):
    """User-facing error message, already classified."""


DETAIL_INSTRUCTIONS = {
    "kort": "Svara mycket kortfattat och koncist, gärna i en enda mening.",
    "medel": "Svara med en lagom detaljerad förklaring, ungefär ett kort stycke.",
    "detaljerad": (
        "Svara utförligt och detaljerat. Förklara ditt resonemang och ge exempel "
        "där det är relevant."
    ),
}
DEFAULT_DETAIL_LEVEL = "medel"

FORMATTING_INSTRUCTION = (
    "Formatera svaret som enkel chatt-text: använd **fet text** för betoning och "
    "punktlistor där varje rad börjar med '- ' (eller '1. ' för numrerade listor). "
    "Använd INTE LaTeX eller matematisk notation som $...$, $$...$$, \\frac, \\sum "
    "eller liknande — sådan text visas inte korrekt i det här gränssnittet. Skriv "
    "istället matematiska uttryck med vanliga tecken och Unicode-symboler, t.ex. "
    "O(1), x^2 som x², kvadratrot som √, samt ≤, ≥, ×, ÷. Använd även de grekiska "
    "bokstäverna direkt som tecken för komplexitetsnotation — skriv Θ(n log n), "
    "Ω(n), Θ(n²) osv., INTE utskrivet som ord ('Theta', 'Omega')."
)

THINKING_LEVELS = {"low", "medium", "high"}
DEFAULT_THINKING_LEVEL = "dynamic"


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


def _stream_text(stream) -> Iterator[str]:
    try:
        for chunk in stream:
            text = chunk.text
            if text:
                yield text
    except Exception as exc:  # noqa: BLE001 - classify below
        raise _classify_error(exc) from exc


def _build_config(detail_level: str, thinking_level: str) -> "types.GenerateContentConfig":
    detail_instruction = DETAIL_INSTRUCTIONS.get(detail_level, DETAIL_INSTRUCTIONS[DEFAULT_DETAIL_LEVEL])
    instruction = f"{FORMATTING_INSTRUCTION}\n\n{detail_instruction}"
    kwargs = {"system_instruction": instruction}
    if thinking_level in THINKING_LEVELS:
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=thinking_level)
    return types.GenerateContentConfig(**kwargs)


class GeminiSession(LLMSession):
    def __init__(self, chat):
        self._chat = chat

    def ask(self, text: str) -> Iterator[str]:
        try:
            stream = self._chat.send_message_stream(text)
        except Exception as exc:  # noqa: BLE001 - classify below
            raise _classify_error(exc) from exc
        return _stream_text(stream)


class GeminiBackend(LLMBackend):
    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        if not api_key.strip():
            raise LLMError("Ingen Gemini API-nyckel har angetts.")
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def start_session(
        self,
        image_bytes: bytes,
        mime_type: str,
        question: str,
        detail_level: str = DEFAULT_DETAIL_LEVEL,
        thinking_level: str = DEFAULT_THINKING_LEVEL,
    ) -> tuple[LLMSession, Iterator[str]]:
        chat = self._client.chats.create(
            model=self._model,
            config=_build_config(detail_level, thinking_level),
        )
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        session = GeminiSession(chat)
        try:
            stream = chat.send_message_stream([question, part])
        except Exception as exc:  # noqa: BLE001 - classify below
            raise _classify_error(exc) from exc
        return session, _stream_text(stream)

    def start_text_session(
        self,
        question: str,
        detail_level: str = DEFAULT_DETAIL_LEVEL,
        thinking_level: str = DEFAULT_THINKING_LEVEL,
    ) -> tuple[LLMSession, Iterator[str]]:
        chat = self._client.chats.create(
            model=self._model,
            config=_build_config(detail_level, thinking_level),
        )
        session = GeminiSession(chat)
        try:
            stream = chat.send_message_stream(question)
        except Exception as exc:  # noqa: BLE001 - classify below
            raise _classify_error(exc) from exc
        return session, _stream_text(stream)
