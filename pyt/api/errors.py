"""Typed error hierarchy for the modern pyt API.

These wrap the legacy exceptions in :mod:`pyt.exceptions` so callers can
write a single ``except PytError`` block. Every error carries enough
identifying context (``video_id``, ``url``, ``client_used``) to file a
useful bug report without further plumbing.
"""
from __future__ import annotations

from typing import Optional


class PytError(Exception):
    """Root of the modern API exception tree."""

    video_id: Optional[str] = None
    url: Optional[str] = None


class VideoUnavailable(PytError):
    """Video is private, removed, region-blocked, or otherwise inaccessible."""

    def __init__(self, video_id: str, reason: str = "unavailable", url: Optional[str] = None):
        self.video_id = video_id
        self.url = url
        self.reason = reason
        super().__init__(f"video {video_id} is {reason}")


class AgeRestricted(VideoUnavailable):
    """Tier-3 age-gated content that requires OAuth to access."""

    def __init__(self, video_id: str, url: Optional[str] = None):
        super().__init__(video_id, reason="age-restricted", url=url)


class LiveStreamNotSupported(VideoUnavailable):
    """The URL points at a live stream; only metadata is available."""

    def __init__(self, video_id: str, url: Optional[str] = None):
        super().__init__(video_id, reason="a live stream (downloads not supported)", url=url)


class NoMatchingStream(PytError):
    """Raised by :meth:`StreamSet.best` / :meth:`StreamSet.one` when the
    filter chain produced zero matches (or, for ``.one()``, more than one).
    """

    def __init__(self, message: str, video_id: Optional[str] = None):
        self.video_id = video_id
        super().__init__(message)


class DownloadError(PytError):
    """The byte transfer itself failed (network, 403, SABR throttle exhaustion).

    Raised by the :class:`Download` builder, never by metadata fetches.
    """

    def __init__(
        self,
        message: str,
        video_id: Optional[str] = None,
        url: Optional[str] = None,
        client_used: Optional[str] = None,
    ):
        self.video_id = video_id
        self.url = url
        self.client_used = client_used
        super().__init__(message)


class PostProcessError(PytError):
    """A pipeline step failed (ffmpeg returned non-zero, mutagen wrote bad tags, etc.)."""

    def __init__(
        self,
        message: str,
        step: Optional[str] = None,
        partial_output_path: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ):
        self.step = step
        self.partial_output_path = partial_output_path
        self.cause = cause
        super().__init__(message)


class ConfigError(PytError):
    """A user-supplied :class:`Client` argument or ``~/.pyt.conf`` value is invalid."""
