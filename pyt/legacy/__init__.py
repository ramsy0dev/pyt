"""Explicit-import home for the deprecated developer interface.

The legacy classes still emit :class:`DeprecationWarning` when constructed
from anywhere, including this module. The point of :mod:`pyt.legacy` is
twofold:

1. Make it grep-able which call sites are still on the old API
   (``from pyt.legacy import YouTube`` is unambiguous).
2. Survive the eventual removal of the same names from the top-level
   ``pyt`` namespace — a top-level ``YouTube`` will go away in v3, but
   ``pyt.legacy.YouTube`` will remain available for one more release
   to give users a migration window.

If you want to silence the deprecation warning while you migrate::

    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"pyt\\.")
"""
from pyt.__main__ import YouTube
from pyt.streams import Stream
from pyt.query import StreamQuery, CaptionQuery
from pyt.captions import Caption
from pyt.monostate import Monostate
from pyt.contrib.playlist import Playlist
from pyt.contrib.channel import Channel
from pyt.contrib.search import Search
from pyt.archive import DownloadArchive

__all__ = [
    "YouTube",
    "Stream",
    "StreamQuery",
    "CaptionQuery",
    "Caption",
    "Monostate",
    "Playlist",
    "Channel",
    "Search",
    "DownloadArchive",
]
