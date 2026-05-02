"""
Pytube: a very serious Python library for downloading YouTube Videos.
"""
__title__ = "pyt"
__author__ = "Ronnie Ghose, Taylor Fox Dahlin, Nick Ficano"
__license__ = "The Unlicense (Unlicense)"
__js__ = None
__js_url__ = None

from pyt.version import __version__
from pyt.streams import Stream
from pyt.captions import Caption
from pyt.query import CaptionQuery, StreamQuery
from pyt.__main__ import YouTube
from pyt.contrib.playlist import Playlist
from pyt.contrib.channel import Channel
from pyt.contrib.search import Search
