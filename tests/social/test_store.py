import pytest

from apps.editor.api.social.models import MentionEntry, NetworkRender, PublishResult
from apps.editor.api.social.store import SocialStore


@pytest.fixture
def store(tmp_path):
    return SocialStore(tmp_path / "social.db")


def test_draft_roundtrip(store):
    draft = store.create_draft(
        source="standalone", base_lang="ko", base_text="hello", link="https://x.test"
    )
    loaded = store.get_draft(draft.id)
    assert loaded.base_text == "hello"
    assert loaded.status == "draft"

    store.update_draft(draft.id, base_text="updated", status="published")
    assert store.get_draft(draft.id).base_text == "updated"
    assert store.get_draft(draft.id).status == "published"


def test_idempotency_history(store):
    draft = store.create_draft(source="standalone", base_lang="ko", base_text="x")
    sha = "abc123"
    assert not store.was_posted(draft.id, "mastodon-ko", sha)
    store.record_post(
        draft.id,
        "mastodon-ko",
        sha,
        PublishResult(account_id="mastodon-ko", ok=True, remote_url="https://m.test/1"),
    )
    assert store.was_posted(draft.id, "mastodon-ko", sha)
    assert not store.was_posted(draft.id, "bluesky-ko", sha)
    history = store.post_history(draft.id)
    assert len(history) == 1
    assert history[0].remote_url == "https://m.test/1"


def test_render_upsert(store):
    render = NetworkRender(
        draft_id="d1", account_id="bluesky-ko", lang="ko", text="v1"
    )
    store.upsert_render(render)
    store.upsert_render(render.model_copy(update={"text": "v2", "manually_edited": True}))
    loaded = store.get_render("d1", "bluesky-ko")
    assert loaded.text == "v2"
    assert loaded.manually_edited


def test_mention_cache_bump(store):
    entry = MentionEntry(network="bluesky", handle="@a.bsky.social", identifier="did:plc:1")
    store.upsert_mention(entry)
    store.upsert_mention(entry, bump_use=True)
    store.upsert_mention(entry, bump_use=True)
    found = store.search_mentions("bluesky", "a.bsky")
    assert len(found) == 1
    assert found[0].use_count == 2
    assert found[0].identifier == "did:plc:1"


def test_mention_upsert_preserves_identifier(store):
    store.upsert_mention(
        MentionEntry(network="bluesky", handle="@a.test", identifier="did:plc:1")
    )
    store.upsert_mention(MentionEntry(network="bluesky", handle="@a.test"))
    assert store.get_mention("bluesky", "@a.test").identifier == "did:plc:1"


def test_translation_cache(store):
    assert store.get_translation("d1", "en", "sha") is None
    store.save_translation("d1", "en", "sha", "hello")
    assert store.get_translation("d1", "en", "sha") == "hello"
