from __future__ import annotations

import re

import grapheme

from .facets import build_rich_text
from .models import CHAR_LIMITS

URL_RE = re.compile(r"https?://\S+")
ELLIPSIS = "…"

# Mastodon counts every URL as 23 characters regardless of actual length.
MASTODON_URL_LENGTH = 23


def count_for(network: str, text: str) -> int:
    if network == "bluesky":
        # count what will actually be posted: URLs get display-shortened
        final_text, _ = build_rich_text(text)
        return grapheme.length(final_text)
    if network == "mastodon":
        return len(URL_RE.sub("x" * MASTODON_URL_LENGTH, text))
    return len(text)


def compose(body: str, link: str | None) -> str:
    body = body.rstrip()
    if link and link not in body:
        return f"{body}\n\n{link}" if body else link
    return body


def adapt(network: str, body: str, link: str | None) -> tuple[str, int, bool]:
    """Fit body + link into the network limit.

    Returns (text, count, truncated). The trailing link line is always preserved;
    only the body is shortened, at a word boundary when one is close enough.
    """
    limit = CHAR_LIMITS[network]
    full = compose(body, link)
    count = count_for(network, full)
    if count <= limit:
        return full, count, False

    suffix = f"\n\n{link}" if link and link not in body else ""

    lo, hi = 0, len(body)
    best_len = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = body[:mid].rstrip() + ELLIPSIS + suffix
        if count_for(network, candidate) <= limit:
            best_len = mid
            lo = mid + 1
        else:
            hi = mid - 1

    prefix = body[:best_len]
    boundary = max(prefix.rfind(" "), prefix.rfind("\n"))
    if boundary > best_len - 20:
        prefix = prefix[:boundary]
    text = prefix.rstrip() + ELLIPSIS + suffix
    return text, count_for(network, text), True
