from __future__ import annotations

from html import escape

from markdown import Markdown

from pelicanconf import MARKDOWN


def render_markdown(markdown_text: str) -> str:
    extension_configs = MARKDOWN["extension_configs"]
    renderer = Markdown(
        extensions=list(extension_configs.keys()),
        extension_configs=extension_configs,
        output_format="html5",
    )
    return renderer.convert(markdown_text)


def render_translation_provenance(
    translation_model: str | None,
    translation_at: str | None,
    translation_source_lang: str | None,
) -> str | None:
    if not translation_model or not translation_at:
        return None
    source_lang = translation_source_lang or "unknown"
    return (
        '<aside class="translation-provenance">'
        "<strong>AI translation metadata</strong>"
        f"<p>Translated from {escape(source_lang)} with {escape(translation_model)} "
        f"at {escape(translation_at)}.</p>"
        "</aside>"
    )
