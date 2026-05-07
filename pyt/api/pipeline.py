"""Declarative post-processing pipeline.

Each step is a small, frozen dataclass that wraps the imperative
post-processor in :mod:`pyt.postprocessors`. Use the factory functions
(``sponsorblock(...)``, ``embed_metadata()``, …) instead of constructing
the step classes directly — the factories give you stable kwargs and
hide the underlying class names.

Example::

    from pyt.api import pipeline as pp

    path = (
        stream.download_to("downloads/")
            | pp.sponsorblock(mark=["sponsor", "intro"])
            | pp.embed_metadata()
            | pp.embed_thumbnail()
            | pp.extract_audio("mp3")
    ).run()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

from pyt.postprocessors import (
    AudioExtractor,
    EmbedSubtitlePostProcessor,
    EmbedThumbnailPostProcessor,
    FFmpegMetadataEmbedder,
    SponsorBlockPP,
)

if TYPE_CHECKING:
    from pyt.api.streams import StreamRef
    from pyt.api.video import Video


# ── base ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PipelineStep:
    """A single step. Subclasses override :meth:`apply`. The ``name``
    field is used in error messages and logs.
    """

    name: str

    def apply(self, path: str, *, stream: "StreamRef", video: "Video") -> str:
        raise NotImplementedError


# ── concrete steps ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _SponsorBlock(PipelineStep):
    mode: str = "mark"
    categories: List[str] = field(default_factory=lambda: ["sponsor"])

    def apply(self, path: str, *, stream: "StreamRef", video: "Video") -> str:
        pp = SponsorBlockPP(mode=self.mode, categories=list(self.categories))
        return pp.run(path, stream.legacy, video.legacy)


@dataclass(frozen=True)
class _EmbedMetadata(PipelineStep):
    def apply(self, path: str, *, stream: "StreamRef", video: "Video") -> str:
        return FFmpegMetadataEmbedder().run(path, stream.legacy, video.legacy)


@dataclass(frozen=True)
class _EmbedThumbnail(PipelineStep):
    def apply(self, path: str, *, stream: "StreamRef", video: "Video") -> str:
        return EmbedThumbnailPostProcessor().run(path, stream.legacy, video.legacy)


@dataclass(frozen=True)
class _EmbedSubtitles(PipelineStep):
    lang: str = "en"

    def apply(self, path: str, *, stream: "StreamRef", video: "Video") -> str:
        return EmbedSubtitlePostProcessor(lang_code=self.lang).run(
            path, stream.legacy, video.legacy
        )


@dataclass(frozen=True)
class _ExtractAudio(PipelineStep):
    format: str = "mp3"
    quality: Optional[str] = None

    def apply(self, path: str, *, stream: "StreamRef", video: "Video") -> str:
        return AudioExtractor(format=self.format, quality=self.quality).run(
            path, stream.legacy, video.legacy
        )


# ── public factories ───────────────────────────────────────────────────────


def sponsorblock(
    *,
    mark: Optional[List[str]] = None,
    remove: Optional[List[str]] = None,
) -> PipelineStep:
    """Mark or remove SponsorBlock segments. Pass exactly one of
    ``mark=`` or ``remove=``."""
    if mark and remove:
        raise ValueError("pass either mark= or remove=, not both")
    if not mark and not remove:
        raise ValueError("sponsorblock(): one of mark= or remove= is required")
    if mark:
        return _SponsorBlock(name="sponsorblock", mode="mark", categories=list(mark))
    return _SponsorBlock(name="sponsorblock", mode="remove", categories=list(remove or []))


def embed_metadata() -> PipelineStep:
    """Embed title, artist, date, description (ffmpeg + mutagen for MP3)."""
    return _EmbedMetadata(name="embed_metadata")


def embed_thumbnail() -> PipelineStep:
    """Embed cover art into the file."""
    return _EmbedThumbnail(name="embed_thumbnail")


def embed_subtitles(lang: str = "en") -> PipelineStep:
    """Embed a subtitle track for *lang* into the file."""
    return _EmbedSubtitles(name="embed_subtitles", lang=lang)


def extract_audio(format: str = "mp3", *, quality: Optional[str] = None) -> PipelineStep:
    """Transcode the file to an audio-only container."""
    return _ExtractAudio(name="extract_audio", format=format, quality=quality)


__all__ = [
    "PipelineStep",
    "sponsorblock",
    "embed_metadata",
    "embed_thumbnail",
    "embed_subtitles",
    "extract_audio",
]
