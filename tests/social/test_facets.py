from apps.editor.api.social.facets import build_rich_text, shorten_url


def span_bytes(text: str, span) -> str:
    return text.encode("utf-8")[span.byte_start : span.byte_end].decode("utf-8")


def test_plain_text_unchanged():
    text, spans = build_rich_text("그냥 평범한 한글 텍스트")
    assert text == "그냥 평범한 한글 텍스트"
    assert spans == []


def test_url_shortened_with_link_facet():
    src = "글 보기 https://iz4u.net/very-long-slug-for-testing-2026.html 끝"
    text, spans = build_rich_text(src)
    assert len(spans) == 1
    span = spans[0]
    assert span.kind == "link"
    assert span.value == "https://iz4u.net/very-long-slug-for-testing-2026.html"
    assert span_bytes(text, span) == "iz4u.net/very-long-slug…"


def test_korean_text_byte_offsets():
    src = "한글 앞부분 #파이썬 그리고 @user.bsky.social 멘션"
    text, spans = build_rich_text(src)
    assert text == src
    tag = next(s for s in spans if s.kind == "tag")
    mention = next(s for s in spans if s.kind == "mention")
    assert span_bytes(text, tag) == "#파이썬"
    assert tag.value == "파이썬"
    assert span_bytes(text, mention) == "@user.bsky.social"
    assert mention.value == "user.bsky.social"


def test_handle_without_dot_not_mention():
    text, spans = build_rich_text("hello @plainname there")
    assert spans == []
    assert text == "hello @plainname there"


def test_email_not_mention():
    text, spans = build_rich_text("contact me at someone@example.com please")
    assert spans == []


def test_trailing_punctuation_excluded_from_url():
    src = "보세요: https://iz4u.net/a.html, 그리고요"
    text, spans = build_rich_text(src)
    assert spans[0].value == "https://iz4u.net/a.html"
    assert ", 그리고요" in text


def test_multiple_facets_offsets_consistent():
    src = "#tag1 본문 https://example.com/looooooooooooooooong-path 와 #한글태그 @a.bsky.social"
    text, spans = build_rich_text(src)
    assert [s.kind for s in spans] == ["tag", "link", "tag", "mention"]
    for span in spans:
        rendered = span_bytes(text, span)
        assert rendered.startswith(("#", "@")) or "…" in rendered or "example" in rendered


def test_shorten_url_strips_scheme_and_www():
    assert shorten_url("https://www.example.com/a") == "example.com/a"
    assert shorten_url("http://iz4u.net/x") == "iz4u.net/x"
