from __future__ import annotations

from html import escape
from pathlib import Path

from pelican import signals
from pelican.contents import Article, Page


LOCALE_FALLBACKS = {
    "ko": "ko_KR",
    "en": "en_US",
}


def _metadata_keys(content) -> set[str]:
    return {key.lower() for key in getattr(content, "metadata", {})}


def _has_explicit_metadata(content, name: str) -> bool:
    return name.lower() in _metadata_keys(content)


def _get_setting(content, key: str, default):
    return content.settings.get(key, default)


def _normalize_content_metadata(content):
    content.lang = getattr(content, "lang", _get_setting(content, "DEFAULT_LANG", "ko")).lower()
    content.translation_key = getattr(content, "translation_key", content.slug)
    content.has_translation_key = _has_explicit_metadata(content, "translation_key")
    content.seo_multilingual = isinstance(content, Article) and content.has_translation_key

    locale_map = _get_setting(content, "OG_LOCALE_MAP", LOCALE_FALLBACKS)
    content.og_locale = locale_map.get(content.lang, content.lang)


def _apply_multilingual_article_url(article: Article):
    article.override_url = (
        f"{article.lang}/posts/"
        f"{article.date:%Y}/{article.date:%m}/{article.date:%d}/{article.slug}/"
    )
    article.override_save_as = (
        f"{article.lang}/posts/"
        f"{article.date:%Y}/{article.date:%m}/{article.date:%d}/{article.slug}/index.html"
    )

    legacy_url = getattr(article, "legacy_url", None) or f"{article.slug}-{article.lang}.html"
    article.legacy_redirect_url = legacy_url
    article.legacy_redirect_save_as = legacy_url


def prepare_content(content):
    if not isinstance(content, (Article, Page)):
        return

    _normalize_content_metadata(content)

    if isinstance(content, Article) and content.seo_multilingual:
        _apply_multilingual_article_url(content)


def _all_articles(generator) -> list[Article]:
    buckets = [
        getattr(generator, "articles", []),
        getattr(generator, "translations", []),
        getattr(generator, "hidden_articles", []),
        getattr(generator, "hidden_translations", []),
        getattr(generator, "drafts", []),
        getattr(generator, "drafts_translations", []),
    ]
    articles: list[Article] = []
    for bucket in buckets:
        articles.extend(bucket)
    return articles


def validate_redirects(generator):
    seen_redirects: dict[str, str] = {}
    live_paths = {article.save_as for article in _all_articles(generator)}

    for article in _all_articles(generator):
        redirect_path = getattr(article, "legacy_redirect_save_as", None)
        if not redirect_path:
            continue
        if redirect_path == article.save_as:
            continue
        if redirect_path in live_paths:
            raise RuntimeError(
                f"Redirect path {redirect_path} for {article.source_path} collides with a live page"
            )
        previous = seen_redirects.get(redirect_path)
        if previous and previous != article.source_path:
            raise RuntimeError(
                f"Redirect path {redirect_path} is duplicated between {previous} and {article.source_path}"
            )
        seen_redirects[redirect_path] = article.source_path


def _absolute_url(site_url: str, path: str) -> str:
    site = site_url.rstrip("/")
    rel = path.lstrip("/")
    if not rel:
        return f"{site}/"
    return f"{site}/{rel}"


def _write_redirect(path, context):
    article = context.get("article")
    if not isinstance(article, Article):
        return
    if context.get("output_file") != article.save_as:
        return

    redirect_path = getattr(article, "legacy_redirect_save_as", None)
    if not redirect_path or redirect_path == article.save_as:
        return

    target_url = _absolute_url(context.get("SEO_SITEURL") or context["SITEURL"], article.url)
    title = escape(str(article.title))
    body = f"""<!DOCTYPE html>
<html lang="{escape(article.lang)}">
  <head>
    <meta charset="utf-8">
    <title>{title}</title>
    <meta http-equiv="refresh" content="0; url={escape(target_url)}">
    <meta name="robots" content="noindex">
    <link rel="canonical" href="{escape(target_url)}">
  </head>
  <body>
    <p>This page moved to <a href="{escape(target_url)}">{escape(target_url)}</a>.</p>
  </body>
</html>
"""

    output_path = Path(article.settings["OUTPUT_PATH"]) / redirect_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(body, encoding="utf-8")


def _fix_sitemap(pelican):
    sitemap_path = Path(pelican.settings["OUTPUT_PATH"]) / "sitemap.xml"
    if not sitemap_path.exists():
        return

    content = sitemap_path.read_text(encoding="utf-8")
    fixed = content.replace(" ref=", " href=")
    if fixed != content:
        sitemap_path.write_text(fixed, encoding="utf-8")


def register():
    signals.content_object_init.connect(prepare_content)
    signals.article_generator_finalized.connect(validate_redirects)
    signals.content_written.connect(_write_redirect)
    signals.finalized.connect(_fix_sitemap)
