import pytest

from apps.editor.api.social.clients import SocialApiError
from apps.editor.api.social.clients.linkedin import escape_commentary
from apps.editor.api.social.clients.threads import ThreadsClient
from apps.editor.api.social.images import instagram_variant, process_upload
from apps.editor.api.social.store import SocialStore


def test_linkedin_commentary_escaping():
    assert escape_commentary("100% (test) [link]") == "100% \\(test\\) \\[link\\]"
    assert escape_commentary("plain text") == "plain text"


def test_threads_parse_redirect():
    # Threads appends #_ to the redirect URL
    code, state = ThreadsClient.parse_redirect(
        "https://iz4u.net/threads-callback/?state=st1&code=abc123#_"
    )
    assert code == "abc123"
    assert state == "st1"


def test_threads_parse_redirect_code_with_suffix():
    # naive copy where #_ ends up glued to the code value
    code, _ = ThreadsClient.parse_redirect(
        "https://iz4u.net/threads-callback/?code=abc123%23_"
    )
    assert code == "abc123"


def test_threads_parse_redirect_without_code():
    with pytest.raises(SocialApiError):
        ThreadsClient.parse_redirect("https://iz4u.net/threads-callback/?state=st1")


def test_oauth_state_roundtrip(tmp_path):
    store = SocialStore(tmp_path / "s.db")
    state = store.create_oauth_state("linkedin-en")
    assert store.consume_oauth_state(state) == "linkedin-en"
    assert store.consume_oauth_state(state) is None  # single use


def test_image_pipeline(tmp_path):
    from PIL import Image
    import io

    img = Image.new("RGB", (3200, 2400), (120, 80, 40))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    processed, width, height = process_upload(buffer.getvalue())
    assert (width, height) == (1600, 1200)
    assert len(processed) <= 976 * 1024

    variant = instagram_variant(processed, "portrait")
    from PIL import Image as PILImage

    out = PILImage.open(io.BytesIO(variant))
    assert out.size == (1080, 1350)
