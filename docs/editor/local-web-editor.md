# Local Web Editor

The local editor is a repository-native writing tool for draft-first blog work.

## Goals

- Run only on the local machine.
- Keep the backend and frontend separated so the UI can be replaced later.
- Save new posts to `content/draft/` by default.
- Support live markdown preview with the same markdown extension settings used by Pelican.
- Provide AI-assisted title, summary, tag, slug, and translation workflows.
- Preserve translation provenance in front matter and render it in the published theme.
- Publish through a guarded pipeline: build, commit, and push.

## Layout

- `apps/editor/api/`
  FastAPI app, content storage, markdown preview, git helpers, and AI services.
- `apps/editor/web/`
  Static HTML, CSS, and JavaScript frontend served by FastAPI.

The backend exposes JSON endpoints and serves the frontend as static assets. There is no server-side HTML rendering for editor views.

## Run

```bash
uv sync
uv run python -m apps.editor.api.main
```

Or:

```bash
make editor
```

Default address: `http://127.0.0.1:8765`

### Access from other devices (Tailscale)

The recommended way is `tailscale serve`: the editor stays bound to 127.0.0.1 and
Tailscale proxies it onto your tailnet with HTTPS. Both access paths work at the
same time - `http://127.0.0.1:8765` locally and
`https://{machine}.{tailnet}.ts.net` from any tailnet device:

```bash
make editor-tailscale       # tailscale serve --bg 8765 + run the editor
make editor-tailscale-off   # tailscale serve --https=443 off
```

The first HTTPS request after enabling may take a few seconds while Tailscale
provisions the TLS certificate.

The editor has no authentication, so avoid `BLOG_EDITOR_HOST=0.0.0.0` (exposes it
to the whole LAN) unless you know the network is trusted.

Note for SNS OAuth: the LinkedIn redirect defaults to
`http://127.0.0.1:8765/...`, which only resolves on the machine running the
editor. To authorize from another device, register the tailnet callback URL in the
LinkedIn app and set `BLOG_EDITOR_SNS_{ACCOUNT_ID}_REDIRECT_URI` accordingly
(Threads supports the same override).

## UI

Three views with a single navigation: **Posts** (list + new draft), **Write**
(metadata and AI tools as collapsible sections, markdown editor with live preview),
and **Social** (cross-posting). The layout is mobile-first:

- On phones the navigation is a fixed bottom tab bar, the editor shows a
  Write/Preview toggle, and actions (Save/Publish/...) sit in a floating bar above
  the navigation.
- On desktop (>=1024px) the navigation is a tab row under the app bar and the
  markdown editor and preview render side by side.

Selecting a post in Posts switches to Write automatically.

## Environment

- `BLOG_EDITOR_HOST` / `BLOG_EDITOR_PORT` (default `127.0.0.1:8765`)
- `OPENAI_API_KEY` or `BLOG_EDITOR_OPENAI_API_KEY`
- `OPENAI_MODEL` or `BLOG_EDITOR_OPENAI_MODEL`
- `OPENAI_BASE_URL` or `BLOG_EDITOR_OPENAI_BASE_URL`

Without an API key, the editor still works, but AI actions are disabled.

## Content Rules

- New documents are created in `content/draft/{year}/`.
- Publishing moves the file to `content/articles/{year}/`.
- The publish action runs the production Pelican build before committing and pushing.
- If the production build fails, the post is moved back to draft and the publish step stops.
- Unpublishing moves the file back to `content/draft/{year}/`.
- Saving recalculates the filename from `date`, `slug`, and `lang`.
- Non-default languages use the `-{lang}` filename suffix.

## Translation Metadata

AI-generated translations store provenance in front matter:

- `Translation_Model`
- `Translation_At`
- `Translation_Source_Lang`

The Pelican theme renders this metadata at the bottom of translated pages.

## API Surface

- `GET /api/posts`
- `POST /api/posts`
- `GET /api/posts/{path}`
- `PUT /api/posts/{path}`
- `POST /api/posts/{path}/preview`
- `POST /api/posts/{path}/publish`
- `POST /api/posts/{path}/unpublish`
- `POST /api/ai/title`
- `POST /api/ai/tags`
- `POST /api/ai/slug`
- `POST /api/ai/summary`
- `POST /api/ai/translate`
