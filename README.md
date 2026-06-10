# blog

Pelican-powered blog for [iz4u.net](https://iz4u.net), with a local web editor and
SNS cross-posting. Korean is the default language; posts can have English
translations linked via `translation_key`.

## Requirements

- Python 3.13 with [uv](https://docs.astral.sh/uv/)
- Git submodule for the theme: `git submodule update --init` (pelican-chemistry)

```bash
uv sync
```

## Blog: build and serve

```bash
make html          # build the site into output/
make devserver     # serve at http://localhost:8000 with auto-regeneration
make publish       # production build (publishconf.py, absolute URLs)
make github        # production build + push to gh-pages
make clean         # remove output/
```

Deployment also runs automatically via GitHub Actions on push to `main`
(`.github/workflows/build_blog.yml`).

Content layout:

- `content/draft/{year}/` - unpublished drafts
- `content/articles/{year}/` - published posts (URL: `https://iz4u.net/{slug}-{lang}.html`)
- `content/pages/`, `content/images/`, `content/extra/` - pages and static assets

## Local web editor

```bash
make editor        # http://127.0.0.1:8765
```

A FastAPI + vanilla JS app for draft-first writing: metadata editing, live markdown
preview (same extensions as Pelican), AI-assisted title/tags/slug/summary/translation,
and a guarded publish pipeline (production build, then git commit and push; rolls back
to draft if the build fails).

The UI is mobile-first (bottom tab navigation, Write/Preview toggle, floating action
bar). To write from a phone, share the editor on your tailnet - the server stays
bound to 127.0.0.1 and Tailscale proxies it over HTTPS, so both
`http://127.0.0.1:8765` and `https://{machine}.{tailnet}.ts.net` work:

```bash
make editor-tailscale       # editor + tailscale serve
make editor-tailscale-off   # stop sharing on the tailnet
```

(Alternative without Tailscale: `BLOG_EDITOR_HOST=0.0.0.0 make editor` exposes it to
the whole LAN - the editor has no auth, so prefer the tailnet route.)

Details: [docs/editor/local-web-editor.md](docs/editor/local-web-editor.md)

## SNS cross-posting (Social tab)

Write a short post once (or derive one from a published article with the
**Cross-post** button), click **Preview all** to get per-network preview cards
(translated to each account's language and fitted to each network's length limit),
edit them inline, then **Confirm & publish** to post sequentially with live
per-network status. Instagram is generate-only: optimized image + caption for
manual posting.

Setup summary:

1. List accounts in `apps/editor/social_accounts.json` (no secrets; id, network,
   lang, handle).
2. Put credentials in `.env` as `BLOG_EDITOR_SNS_{ACCOUNT_ID}_{KEY}`, for example:

   ```
   BLOG_EDITOR_SNS_BLUESKY_KO_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   BLOG_EDITOR_SNS_MASTODON_KO_ACCESS_TOKEN=...
   BLOG_EDITOR_SNS_THREADS_KO_CLIENT_ID=...
   BLOG_EDITOR_SNS_THREADS_KO_CLIENT_SECRET=...
   BLOG_EDITOR_SNS_LINKEDIN_EN_CLIENT_ID=...
   BLOG_EDITOR_SNS_LINKEDIN_EN_CLIENT_SECRET=...
   ```

3. Threads and LinkedIn need developer apps and a one-time **Authorize** click in
   the accounts strip (LinkedIn uses a localhost callback; Threads uses a paste-back
   flow). Bluesky and Mastodon work with just the secret above.

SNS drafts can sync across devices through the repo itself: each draft is committed
as an age-encrypted bundle under `apps/editor/drafts/` (key in `.env`, never in the
repo). OAuth tokens and images stay local-only.

Full setup guide, OAuth flows, and API surface:
[docs/editor/social-cross-posting.md](docs/editor/social-cross-posting.md)

## Environment variables

Start from the template - it documents every key with where to get each credential:

```bash
cp .env.example .env
```

All optional keys live in `.env` at the repo root (gitignored):

| Key | Purpose |
| --- | --- |
| `OPENAI_API_KEY` (or `BLOG_EDITOR_OPENAI_API_KEY`) | enables AI features (suggestions, translation, alt text) |
| `OPENAI_MODEL` (or `BLOG_EDITOR_OPENAI_MODEL`) | model override, default `gpt-4.1-mini` |
| `OPENAI_BASE_URL` (or `BLOG_EDITOR_OPENAI_BASE_URL`) | OpenAI-compatible endpoint |
| `BLOG_EDITOR_SNS_*` | SNS credentials (see above) |
| `BLOG_EDITOR_DRAFTS_KEY` | enables encrypted SNS-draft sync via git (generate: `uv run python -m apps.editor.api.social.sync`) |

Without an OpenAI key the editor and cross-posting still work; AI actions are
disabled and untranslated previews are flagged for manual editing.

Local editor data (sqlite, processed images) lives in `apps/editor/data/`
(gitignored).

## Tests

```bash
uv run pytest tests/
uv run ruff check apps/ tests/
```
