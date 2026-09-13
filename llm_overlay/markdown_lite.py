from __future__ import annotations

import html
import re

_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_ITALIC_UNDERSCORE_RE = re.compile(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")
_UNORDERED_RE = re.compile(r"^[-*]\s+(.*)")
_ORDERED_RE = re.compile(r"^\d+\.\s+(.*)")
_FENCE_RE = re.compile(r"^```\s*([A-Za-z0-9_+-]*)\s*$")


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = _CODE_RE.sub(r"<code>\1</code>", escaped)
    escaped = _BOLD_RE.sub(r"<b>\1</b>", escaped)
    escaped = _ITALIC_STAR_RE.sub(r"<i>\1</i>", escaped)
    escaped = _ITALIC_UNDERSCORE_RE.sub(r"<i>\1</i>", escaped)
    return escaped


def to_html(text: str) -> str:
    """Render a small, chat-friendly Markdown subset (bold/italic/code/lists/fences) as HTML.

    Escapes everything else so model output can never inject arbitrary markup.
    """
    lines = text.split("\n")
    out: list[str] = []
    list_tag: str | None = None
    index = 0

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    while index < len(lines):
        fence = _FENCE_RE.match(lines[index].strip())
        if fence:
            language = fence.group(1)
            index += 1
            body: list[str] = []
            while index < len(lines) and not _FENCE_RE.match(lines[index].strip()):
                body.append(lines[index])
                index += 1
            index += 1  # closing fence, if the answer has finished streaming
            close_list()
            out.append(
                f'<pre class="code-block" data-lang="{html.escape(language)}">'
                f"{html.escape(chr(10).join(body))}</pre>"
            )
            continue

        line = lines[index]
        index += 1
        stripped = line.strip()
        unordered = _UNORDERED_RE.match(stripped)
        ordered = _ORDERED_RE.match(stripped)
        item_text = None
        wanted_tag = None
        if unordered:
            item_text, wanted_tag = unordered.group(1), "ul"
        elif ordered:
            item_text, wanted_tag = ordered.group(1), "ol"

        if wanted_tag:
            if list_tag != wanted_tag:
                close_list()
                out.append(f"<{wanted_tag}>")
                list_tag = wanted_tag
            out.append(f"<li>{_inline(item_text)}</li>")
        else:
            close_list()
            out.append(_inline(line) if stripped else "")
            out.append("<br>")

    close_list()
    result = "".join(out)
    while result.endswith("<br>"):
        result = result[: -len("<br>")]
    return result
