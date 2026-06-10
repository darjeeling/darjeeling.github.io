from apps.editor.api.social.text import adapt, compose, count_for


def test_compose_appends_link():
    assert compose("hello", "https://iz4u.net/a.html") == "hello\n\nhttps://iz4u.net/a.html"


def test_compose_skips_link_already_present():
    text = "hello https://iz4u.net/a.html"
    assert compose(text, "https://iz4u.net/a.html") == text


def test_mastodon_counts_urls_as_23():
    url = "https://iz4u.net/very/long/path/that/exceeds/twenty/three/characters.html"
    assert count_for("mastodon", url) == 23
    assert count_for("mastodon", f"hi {url}") == 26


def test_bluesky_counts_graphemes():
    # Korean syllables and emoji with modifiers count as single graphemes
    assert count_for("bluesky", "한글") == 2
    assert count_for("bluesky", "👍🏽") == 1


def test_adapt_within_limit_unchanged():
    text, count, truncated = adapt("bluesky", "짧은 글", "https://iz4u.net/a.html")
    assert text == "짧은 글\n\nhttps://iz4u.net/a.html"
    assert not truncated
    assert count == count_for("bluesky", text)


def test_adapt_truncates_but_keeps_link():
    body = "가나다라 마바사아 자차카타 " * 40
    link = "https://iz4u.net/a.html"
    text, count, truncated = adapt("bluesky", body, link)
    assert truncated
    assert text.endswith(link)
    assert "…" in text
    assert count <= 300


def test_adapt_truncates_at_word_boundary():
    body = "word " * 200
    text, _, truncated = adapt("mastodon", body, None)
    assert truncated
    assert not text.replace("…", "").endswith("wor")
