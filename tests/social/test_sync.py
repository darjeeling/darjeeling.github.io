import pytest
from pyrage import x25519

from apps.editor.api.social.models import NetworkRender
from apps.editor.api.social.store import SocialStore
from apps.editor.api.social.sync import DraftSync, SyncDisabledError


@pytest.fixture
def key():
    return str(x25519.Identity.generate())


@pytest.fixture
def store_a(tmp_path):
    return SocialStore(tmp_path / "a.db")


@pytest.fixture
def store_b(tmp_path):
    return SocialStore(tmp_path / "b.db")


def make_draft(store, text="첫 드래프트"):
    draft = store.create_draft(
        source="standalone", base_lang="ko", base_text=text, link="https://iz4u.net/x.html"
    )
    store.upsert_render(
        NetworkRender(draft_id=draft.id, account_id="mastodon-ko", lang="ko", text=text)
    )
    store.save_translation(draft.id, "en", "sha1", "first draft")
    return store.get_draft(draft.id)


def test_disabled_without_key(store_a, tmp_path):
    sync = DraftSync(store_a, tmp_path / "drafts", None)
    assert not sync.enabled
    assert sync.export_draft("whatever") is False
    with pytest.raises(SyncDisabledError):
        sync.import_all()


def test_roundtrip_between_devices(store_a, store_b, tmp_path, key):
    drafts_dir = tmp_path / "drafts"
    draft = make_draft(store_a)

    sync_a = DraftSync(store_a, drafts_dir, key)
    assert sync_a.export_draft(draft.id) is True
    assert (drafts_dir / f"{draft.id}.age").exists()
    # bundle is encrypted: plaintext must not appear in the file
    raw = (drafts_dir / f"{draft.id}.age").read_bytes()
    assert "첫 드래프트".encode() not in raw

    sync_b = DraftSync(store_b, drafts_dir, key)
    counts = sync_b.import_all()
    assert counts == {"imported": 1, "skipped": 0, "errors": 0}

    imported = store_b.get_draft(draft.id)
    assert imported.base_text == draft.base_text
    assert imported.updated_at == draft.updated_at
    renders = store_b.get_renders(draft.id)
    assert len(renders) == 1 and renders[0].text == "첫 드래프트"
    assert store_b.get_translation(draft.id, "en", "sha1") == "first draft"


def test_unchanged_content_not_rewritten(store_a, tmp_path, key):
    drafts_dir = tmp_path / "drafts"
    draft = make_draft(store_a)
    sync = DraftSync(store_a, drafts_dir, key)
    assert sync.export_draft(draft.id) is True
    first_bytes = (drafts_dir / f"{draft.id}.age").read_bytes()
    assert sync.export_draft(draft.id) is False
    assert (drafts_dir / f"{draft.id}.age").read_bytes() == first_bytes


def test_newer_wins(store_a, store_b, tmp_path, key):
    drafts_dir = tmp_path / "drafts"
    draft = make_draft(store_a)
    sync_a = DraftSync(store_a, drafts_dir, key)
    sync_b = DraftSync(store_b, drafts_dir, key)
    sync_a.export_draft(draft.id)
    sync_b.import_all()

    # device B edits later -> B's version must win on A
    store_b.update_draft(draft.id, base_text="B에서 수정함")
    sync_b.export_draft(draft.id)
    counts = sync_a.import_all()
    assert counts["imported"] == 1
    assert store_a.get_draft(draft.id).base_text == "B에서 수정함"

    # stale bundle does not clobber newer local state
    counts = sync_a.import_all()
    assert counts == {"imported": 0, "skipped": 1, "errors": 0}


def test_wrong_key_counts_as_error(store_a, store_b, tmp_path, key):
    drafts_dir = tmp_path / "drafts"
    draft = make_draft(store_a)
    DraftSync(store_a, drafts_dir, key).export_draft(draft.id)
    other_key = str(x25519.Identity.generate())
    counts = DraftSync(store_b, drafts_dir, other_key).import_all()
    assert counts == {"imported": 0, "skipped": 0, "errors": 1}


def test_remove_draft_deletes_file(store_a, tmp_path, key):
    drafts_dir = tmp_path / "drafts"
    draft = make_draft(store_a)
    sync = DraftSync(store_a, drafts_dir, key)
    sync.export_draft(draft.id)
    sync.remove_draft(draft.id)
    assert not (drafts_dir / f"{draft.id}.age").exists()
