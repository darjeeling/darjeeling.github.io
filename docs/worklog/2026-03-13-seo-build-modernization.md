# 2026-03-13 Worklog: Build, SEO, and Multilingual Foundation

## Why this document exists

This note records the engineering changes made on 2026-03-13 to modernize the blog build, improve SEO output, and prepare the site for new multilingual posts.

The main goal was:

- modernize dependency and CI management
- make canonical and sitemap output SEO-safe
- support new Korean/English posts with explicit translation pairing
- keep existing published URLs stable

## Recommended location for work logs

`docs/worklog/` is the right place for this kind of note.

Why:

- it separates engineering notes from blog content under `content/`
- it is date-based and easy to scan later
- it avoids mixing private draft writing with repository maintenance notes

## What changed

### 1. Build and dependency modernization

The project was moved from `requirements.txt`-driven installation to `uv` project management.

Changes:

- added `pyproject.toml`
- added `uv.lock`
- removed `requirements.txt`
- updated local Python target to `3.13` via `.python-version`
- updated `Makefile` to use `uv run pelican`
- updated GitHub Actions to use `uv sync --frozen --no-dev`

Relevant files:

- `pyproject.toml`
- `uv.lock`
- `.python-version`
- `Makefile`
- `.github/workflows/build_blog.yml`

### 2. Pelican configuration for SEO and translation grouping

Pelican config was updated to support explicit translation pairing and safer SEO defaults.

Changes:

- added `SEO_SITEURL = "https://iz4u.net"`
- added `META_DESCRIPTION`
- added `DEFAULT_METADATA = {"lang": "ko"}`
- enabled `ARTICLE_TRANSLATION_ID = "translation_key"`
- enabled `PAGE_TRANSLATION_ID = "translation_key"`
- added `OG_LOCALE_MAP`
- added local plugin path and plugin loading

Relevant file:

- `pelicanconf.py`

### 3. New local plugin for multilingual SEO behavior

A local plugin was added at `plugins/seo_i18n/`.

This plugin does four important jobs:

1. It normalizes content metadata such as `lang`, `translation_key`, and OG locale.
2. It gives new multilingual articles a directory-based URL structure:
   - `ko/posts/YYYY/MM/DD/slug/`
   - `en/posts/YYYY/MM/DD/slug/`
3. It creates a legacy redirect page for the old `slug-lang.html` path.
4. It fixes the generated sitemap output so alternate language links use `href=`, not `ref=`.

Important rule:

- only articles with explicit `Translation_Key` metadata are treated as multilingual SEO articles
- old published posts without `translation_key` keep their existing URLs

Relevant files:

- `plugins/seo_i18n/__init__.py`
- `plugins/seo_i18n/plugin.py`

## SEO decisions

### Existing posts

Existing posts keep their current published URLs.

Reason:

- existing URLs may already be indexed
- changing all historical URLs at once is high risk
- this keeps migration cost low while still improving new content

### New multilingual posts

New bilingual posts use language-prefixed directory URLs and `translation_key` to connect Korean and English versions.

Example:

- Korean: `/ko/posts/2026/03/13/example-slug/`
- English: `/en/posts/2026/03/13/example-slug/`

Each language page is self-canonical and links to the alternate language page with `hreflang`.

### Legacy redirect behavior

For new multilingual posts, the plugin writes a static redirect page for the old style path:

- old path: `/example-slug-ko.html`
- new path: `/ko/posts/2026/03/13/example-slug/`

The redirect page includes:

- immediate refresh redirect
- `rel="canonical"` pointing to the new URL
- `meta name="robots" content="noindex"`

This keeps old-style direct links usable while pushing search engines toward the new URL.

### Sitemap behavior

The generated sitemap now uses absolute URLs under `https://iz4u.net`.

For multilingual pages, alternate language links are also included in sitemap output.

## Template changes

Template work was done in the `pelican-chemistry` theme submodule.

### Why the theme had to change

The SEO behavior could not be completed from Python settings alone.

Canonical tags, `hreflang`, `html lang`, Open Graph tags, and Twitter metadata are emitted by the Jinja templates, so the theme needed direct changes.

### Files changed in the theme

- `pelican-chemistry/templates/base.html`
- `pelican-chemistry/templates/article.html`
- `pelican-chemistry/templates/page.html`
- `pelican-chemistry/templates/index.html`

### What changed in templates

#### `base.html`

- derive the current content object
- set `<html lang="...">` from page/article language
- compute canonical URL from content URL instead of raw output file path
- emit `rel="alternate"` links for translations
- emit shared Open Graph and Twitter metadata
- emit OG locale and alternate locales

#### `article.html`

- always emit a description using article summary or site fallback
- emit article OG/Twitter metadata
- show explicit language switch links when translations exist

#### `page.html`

- same pattern as article template
- page summary fallback for metadata
- translation switch links when translations exist

#### `index.html`

- emit site-level OG/Twitter metadata for the homepage

## Submodule note: why `pelican-chemistry` needed separate handling

`pelican-chemistry` is a git submodule, not a normal folder.

That means:

- the main repo stores only the submodule commit pointer
- the actual template contents live in the submodule repository

Because of that, the template changes had to be committed inside the submodule first, then the main repo had to be updated to point at that new submodule commit.

What happened:

- a local submodule commit was first created as `34d4c36`
- push to the original upstream failed because there was no permission
- a fork was created at `https://github.com/darjeeling/pelican-chemistry.git`
- the submodule remote was changed to the fork
- the commit was rebased onto the fork's current `main`
- the final pushed submodule commit became `c3cf433`
- `.gitmodules` was updated to use the fork URL

This was necessary so fresh clones and GitHub Actions can actually fetch the referenced submodule commit.

## Draft handling decision

Unfinished or not-yet-committed writing was moved to `content/draft/`.

Why:

- drafts should not affect the production build
- draft slug collisions can break output generation
- `content/draft/` is not part of `ARTICLE_PATHS`

Rule going forward:

- unfinished writing: `content/draft/`
- publishable writing: `content/articles/`
- if a post should remain in articles but stay out of publication flow, add explicit draft metadata

## Validation performed

The following checks were run:

- `uv run ruff check plugins pelicanconf.py publishconf.py tasks.py`
- production build via `uv run pelican content -o output -s publishconf.py`
- verification build with temporary bilingual test articles

What was confirmed:

- build succeeds
- new multilingual articles generate `/ko/...` and `/en/...`
- canonical tags point to absolute URLs
- `hreflang` links are emitted in page HTML
- legacy redirect pages are generated
- sitemap uses absolute URLs

## Current repository state after this work

Main repository:

- remote updated to `https://github.com/darjeeling/darjeeling.github.io.git`
- main branch pushed with the SEO/build changes

Theme submodule:

- remote updated to `https://github.com/darjeeling/pelican-chemistry.git`
- template SEO commit pushed there

## Follow-up ideas

- add a short authoring guide for multilingual posts with a `translation_key` example
- normalize tag/category/archive URLs into directory form later
- decide whether historical posts should ever migrate to language-prefixed URLs
- consider vendoring the theme instead of keeping it as a submodule if future customization grows
