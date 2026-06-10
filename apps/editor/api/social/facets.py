from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

# URL, then @handle (must contain a dot, like user.bsky.social), then #tag.
# Mentions/tags only match at a word edge so emails and URL fragments are skipped.
RICH_TEXT_RE = re.compile(
    r"(?P<url>https?://[^\s<>\"]+)"
    r"|(?<![\w@.])@(?P<handle>[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,})"
    r"|(?<![\w&])#(?P<tag>[^\s#.,;:!?'\"()\[\]{}]+)",
    re.UNICODE,
)

TRAILING_PUNCTUATION = ".,;:!?)”’"
MAX_URL_DISPLAY = 24


@dataclass
class FacetSpan:
    kind: Literal["link", "mention", "tag"]
    value: str  # full URL / bare handle / bare tag
    byte_start: int
    byte_end: int


def shorten_url(url: str) -> str:
    display = re.sub(r"^https?://(www\.)?", "", url)
    if len(display) > MAX_URL_DISPLAY:
        display = display[: MAX_URL_DISPLAY - 1] + "…"
    return display


def build_rich_text(text: str) -> tuple[str, list[FacetSpan]]:
    """Transform text for Bluesky: shorten URL display, locate facet byte ranges.

    Returns the final post text and spans with UTF-8 byte offsets into it.
    """
    parts: list[str] = []
    spans: list[FacetSpan] = []
    byte_len = 0
    pos = 0

    def append(piece: str) -> None:
        nonlocal byte_len
        parts.append(piece)
        byte_len += len(piece.encode("utf-8"))

    for match in RICH_TEXT_RE.finditer(text):
        append(text[pos : match.start()])
        pos = match.end()
        start = byte_len
        if match.group("url"):
            url = match.group("url").rstrip(TRAILING_PUNCTUATION)
            trailing = match.group("url")[len(url) :]
            append(shorten_url(url))
            spans.append(FacetSpan("link", url, start, byte_len))
            append(trailing)
        elif match.group("handle"):
            handle = match.group("handle")
            append(f"@{handle}")
            spans.append(FacetSpan("mention", handle, start, byte_len))
        else:
            tag = match.group("tag")
            append(f"#{tag}")
            spans.append(FacetSpan("tag", tag, start, byte_len))
    append(text[pos:])
    return "".join(parts), spans
