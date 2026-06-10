# SNS Cross-Posting

The editor's Social tab cross-posts a short text (standalone or derived from a blog
post) to Bluesky, Mastodon, Threads, and LinkedIn. Instagram is generate-only: the
editor produces an optimized image and caption, and you post manually.

## How it works

1. Write base text once (Korean or English) in the Social tab, or click **Cross-post**
   on a published blog post to prefill title + summary + link (previews render
   automatically in that case).
2. **Preview all** saves the draft and renders one editable preview card per account:
   text translated to the account's language (per-account setting in
   `apps/editor/social_accounts.json`) and fitted to each network's limit:
   Bluesky 300 graphemes (URLs display-shortened), Mastodon 500 (URL = 23 chars),
   Threads 500, LinkedIn 3000, Instagram caption 2200.
3. Edit any per-network preview card inline. Manual edits survive re-renders.
4. Uncheck any account you want to skip, then **Confirm & publish**. After a
   confirmation dialog, posts go out one network at a time in card order; each card
   shows live status (Posting... / Posted with a link / error). Identical re-sends
   are blocked (idempotency) unless forced.

For article drafts, if a human-written translation of the post exists (same
`translation_key`), its real title/summary and language-specific URL are used instead
of machine translation.

Mentions: type `@` in a preview to search people. Bluesky and Mastodon search their
APIs (results cached in sqlite); Threads and LinkedIn use the local cache only - add
handles once via the API (`POST /api/social/people`) or let usage build the cache.

Images: attach in the compose card. They are normalized (EXIF stripped, max 1600x1600,
JPEG under 976KB) and uploaded with alt text to Bluesky/Mastodon/LinkedIn. Alt text can
be AI-generated per language. Threads posts are text + link only (its API requires a
public image URL). **Instagram package** produces a 1080x1350 or 1080x1080 crop plus
the caption for manual posting.

## Account setup

Accounts live in `apps/editor/social_accounts.json` (no secrets - the repo is public).
Each entry: `id`, `network`, `lang` (which language this account receives), `handle`,
and network-specific `host`/`service_url`. Multiple accounts per network are fine
(e.g. `mastodon-ko` and `mastodon-en`).

Secrets go in `.env`, named `BLOG_EDITOR_SNS_{ACCOUNT_ID}_{KEY}` with the account id
upper-snake-cased. `cp .env.example .env` gives you a commented template covering
every key:

```
# Bluesky: app password from Settings > App Passwords
BLOG_EDITOR_SNS_BLUESKY_KO_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Mastodon: access token from Preferences > Development > New application
# (scopes: write:statuses write:media read:search)
BLOG_EDITOR_SNS_MASTODON_KO_ACCESS_TOKEN=...

# Threads: Meta developer app (threads_basic, threads_content_publish)
BLOG_EDITOR_SNS_THREADS_KO_CLIENT_ID=...
BLOG_EDITOR_SNS_THREADS_KO_CLIENT_SECRET=...
# optional, default https://iz4u.net/threads-callback/
BLOG_EDITOR_SNS_THREADS_KO_REDIRECT_URI=...

# LinkedIn: developer app with "Share on LinkedIn" + "Sign In with LinkedIn
# using OpenID Connect" products; add the redirect URL below in the app settings
BLOG_EDITOR_SNS_LINKEDIN_EN_CLIENT_ID=...
BLOG_EDITOR_SNS_LINKEDIN_EN_CLIENT_SECRET=...
```

## OAuth flows

- **LinkedIn**: redirect URL `http://127.0.0.1:8765/api/social/oauth/linkedin/callback`
  must be registered in the LinkedIn app. Click **Authorize** in the accounts strip;
  the callback stores the token in sqlite. Standard apps get no refresh token, so
  re-authorize every ~60 days when the chip shows "expired".
- **Threads**: Threads requires an HTTPS redirect URI, so the flow is paste-back.
  Register `https://iz4u.net/threads-callback/` (any HTTPS URL on the domain works,
  even a 404) as the redirect URI in the Meta app. Click **Authorize**, approve in the
  new tab, then copy the resulting URL from the address bar and paste it into the
  prompt. Long-lived tokens (~60 days) auto-refresh when used within 7 days of expiry.
- Bluesky (app password) and Mastodon (access token) need no OAuth flow.

## Storage

`apps/editor/data/` (gitignored): `social.db` (drafts, per-network renders, post
history, mention cache, OAuth tokens) and `images/` (processed uploads and Instagram
variants).

## Multi-device draft sync (encrypted, via git)

SNS drafts can follow the repo across devices. Each draft is exported as one
encrypted bundle (`apps/editor/drafts/{id}.age`, age format, X25519) containing the
draft, its per-network renders, and its translation cache. OAuth tokens, the mention
cache, post history, and images deliberately stay local-only.

Setup (same key on every device):

```bash
uv run python -m apps.editor.api.social.sync
# prints: BLOG_EDITOR_DRAFTS_KEY=AGE-SECRET-KEY-1...  -> add to .env
```

How it works:

- Every draft change re-exports its bundle; unchanged drafts are never re-encrypted,
  so git only sees real changes. Commit and push `apps/editor/drafts/` like any
  other content (the editor does not auto-commit).
- On startup, and via the **Sync** button in the Social drafts panel, bundles pulled
  from other devices are imported; the newer `updated_at` wins per draft.
- Files are standard age format: `age -d -i <(echo $KEY) {id}.age` decrypts manually.
- Limitations: deleting a draft removes its file locally (propagates on push), but
  images do not sync (the UI marks them "not on this device"), and editing the same
  draft on two devices before syncing resolves to the newer one - the older edit is
  lost. Without `BLOG_EDITOR_DRAFTS_KEY` the feature is off and everything stays in
  the local sqlite.

The key never goes into the repo. Anyone cloning the public repo sees only
ciphertext; treat the key like the rest of `.env`.

## Tests

```
uv run pytest tests/social/
```

Covers text counting/truncation, Bluesky facet byte offsets with Korean text, the
sqlite store, OAuth state, redirect parsing, and the image pipeline.
