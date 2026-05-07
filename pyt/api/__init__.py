"""Modern, ergonomic Python API for pyt.

This package is the v1 of the redesigned developer interface described in
the system-design proposal. It is **additive** — it sits on top of the
existing :class:`pyt.YouTube`, :class:`pyt.Stream`, and post-processor
internals without changing them. The legacy classes remain importable from
``pyt`` for backwards compatibility.

The design goals are:

* a single, obvious entry point (:class:`Client`)
* explicit network boundaries (``client.video(url)`` is the I/O moment;
  attribute access is pure)
* chainable, immutable :class:`StreamSet` with ``.best`` / ``.one`` that
  raise typed errors instead of returning ``Optional[Stream]``
* a declarative post-processing :class:`Pipeline` you can read top-to-bottom

Async support is intentionally not in this v1. Adding it requires moving
``pyt.request`` to ``httpx`` and threading awaitables through the SABR
session — that lands as a separate milestone.
"""
from pyt.api.errors import (
    PytError,
    VideoUnavailable,
    AgeRestricted,
    LiveStreamNotSupported,
    NoMatchingStream,
    DownloadError,
    PostProcessError,
    ConfigError,
)
from pyt.api.models import VideoMeta, Channel, Thumbnail
from pyt.api.client import Client
from pyt.api.video import Video
from pyt.api.streams import StreamSet, StreamRef
from pyt.api.download import Download, ProgressEvent
from pyt.api.playlists import Playlist, ChannelFeed, SearchResults
from pyt.api import pipeline

__all__ = [
    "Client",
    "Video",
    "StreamSet",
    "StreamRef",
    "Download",
    "ProgressEvent",
    "Playlist",
    "ChannelFeed",
    "SearchResults",
    "pipeline",
    "VideoMeta",
    "Channel",
    "Thumbnail",
    "PytError",
    "VideoUnavailable",
    "AgeRestricted",
    "LiveStreamNotSupported",
    "NoMatchingStream",
    "DownloadError",
    "PostProcessError",
    "ConfigError",
]
