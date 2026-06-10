from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import EditorSettings
from .models import PostDocument


class TitleSuggestions(BaseModel):
    titles: list[str]


class TagSuggestions(BaseModel):
    tags: list[str]


class SlugSuggestion(BaseModel):
    slug: str


class SummarySuggestion(BaseModel):
    summary: str


class TranslationResult(BaseModel):
    title: str
    summary: str
    body_markdown: str


class ShortTranslation(BaseModel):
    text: str


class AltTextResult(BaseModel):
    text: str


@dataclass
class AIDependencies:
    settings: EditorSettings


class AIService:
    def __init__(self, settings: EditorSettings):
        self.settings = settings
        self._provider = None

    async def suggest_titles(self, document: PostDocument) -> list[str]:
        result = await self._title_agent().run(self._document_prompt(document), deps=self._deps())
        return result.output.titles

    async def suggest_tags(self, document: PostDocument) -> list[str]:
        result = await self._tag_agent().run(self._document_prompt(document), deps=self._deps())
        return result.output.tags

    async def suggest_slug(self, document: PostDocument) -> str:
        result = await self._slug_agent().run(self._document_prompt(document), deps=self._deps())
        return result.output.slug

    async def suggest_summary(self, document: PostDocument) -> str:
        result = await self._summary_agent().run(self._document_prompt(document), deps=self._deps())
        return result.output.summary

    async def translate(self, document: PostDocument, target_lang: str) -> TranslationResult:
        prompt = (
            f"Translate this blog post from {document.lang} to {target_lang}.\n"
            "Preserve markdown structure, code blocks, links, and headings.\n"
            "Return translated title, summary, and body.\n\n"
            f"{self._document_prompt(document)}"
        )
        result = await self._translation_agent().run(prompt, deps=self._deps())
        return result.output

    async def translate_short(self, text: str, source_lang: str, target_lang: str) -> str:
        prompt = (
            f"Translate this social media post from {source_lang} to {target_lang}:\n\n{text}"
        )
        result = await self._short_translation_agent().run(prompt, deps=self._deps())
        return result.output.text

    async def describe_image(self, data: bytes, media_type: str, lang: str) -> str:
        result = await self._alt_text_agent().run(
            [
                f"Write alt text in {lang} for this image.",
                BinaryContent(data=data, media_type=media_type),
            ],
            deps=self._deps(),
        )
        return result.output.text

    def translation_metadata(self) -> tuple[str, str]:
        return self.settings.openai_model, datetime.now(UTC).isoformat()

    def ensure_available(self) -> None:
        if not self.settings.ai_enabled:
            raise ValueError("AI features are disabled. Set OPENAI_API_KEY or BLOG_EDITOR_OPENAI_API_KEY.")

    def _deps(self) -> AIDependencies:
        self.ensure_available()
        return AIDependencies(settings=self.settings)

    def _model(self) -> OpenAIModel:
        self.ensure_available()
        provider = self._provider or OpenAIProvider(
            base_url=self.settings.openai_base_url,
            api_key=self.settings.openai_api_key,
        )
        self._provider = provider
        return OpenAIModel(self.settings.openai_model, provider=provider)

    def _title_agent(self) -> Agent[AIDependencies, TitleSuggestions]:
        return Agent(
            self._model(),
            output_type=TitleSuggestions,
            system_prompt=(
                "You help write technical and personal blog posts. "
                "Suggest 5 concise, publishable titles. "
                "Return only strong titles, not explanations."
            ),
        )

    def _tag_agent(self) -> Agent[AIDependencies, TagSuggestions]:
        return Agent(
            self._model(),
            output_type=TagSuggestions,
            system_prompt=(
                "Suggest 3 to 6 blog tags. "
                "Keep them lowercase, short, and publication-ready."
            ),
        )

    def _slug_agent(self) -> Agent[AIDependencies, SlugSuggestion]:
        return Agent(
            self._model(),
            output_type=SlugSuggestion,
            system_prompt=(
                "Generate a concise URL slug for a blog post. "
                "Return lowercase ASCII words separated by hyphens only."
            ),
        )

    def _summary_agent(self) -> Agent[AIDependencies, SummarySuggestion]:
        return Agent(
            self._model(),
            output_type=SummarySuggestion,
            system_prompt=(
                "Write a 1 or 2 sentence summary for a blog post. "
                "Keep it suitable for metadata and previews."
            ),
        )

    def _translation_agent(self) -> Agent[AIDependencies, TranslationResult]:
        return Agent(
            self._model(),
            output_type=TranslationResult,
            system_prompt=(
                "You are an expert technical blog translator. "
                "Preserve formatting, links, structure, and code blocks. "
                "Do not add commentary."
            ),
        )

    def _short_translation_agent(self) -> Agent[AIDependencies, ShortTranslation]:
        return Agent(
            self._model(),
            output_type=ShortTranslation,
            system_prompt=(
                "You translate short social media posts. "
                "Keep hashtags, @mentions, and URLs exactly as they are. "
                "Match a natural, conversational social media tone and keep it concise. "
                "Do not add commentary."
            ),
        )

    def _alt_text_agent(self) -> Agent[AIDependencies, AltTextResult]:
        return Agent(
            self._model(),
            output_type=AltTextResult,
            system_prompt=(
                "Write concise, descriptive alt text for social media images. "
                "One or two sentences describing what is visible, for screen reader users. "
                "No 'image of' prefix, no hashtags, no commentary."
            ),
        )

    def _document_prompt(self, document: PostDocument) -> str:
        return (
            f"Title: {document.title}\n"
            f"Date: {document.date}\n"
            f"Category: {document.category}\n"
            f"Lang: {document.lang}\n"
            f"Tags: {', '.join(document.tags)}\n"
            f"Summary: {document.summary}\n\n"
            "Body:\n"
            f"{document.body_markdown}"
        )
