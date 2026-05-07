"""pyt — YouTube downloader for Python 3."""
__title__ = "pyt"
__author__ = "ramsy0dev"
__license__ = "MIT"
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
from pyt.archive import DownloadArchive
from pyt.template import OutputTemplate
from pyt.postprocessors import (
    AudioExtractor,
    FFmpegMetadataEmbedder,
    EmbedThumbnailPostProcessor,
    EmbedSubtitlePostProcessor,
    SponsorBlockPP,
    PostProcessorError,
)

# Modern API — see pyt.api for the full surface. The legacy classes above
# remain importable until the next major bump but emit DeprecationWarning.
# Modern Playlist/ChannelFeed/SearchResults live under pyt.api to avoid
# colliding with the legacy ``pyt.Playlist`` / ``pyt.Channel``.
from pyt.api import (
    Client,
    Video,
    StreamSet,
    StreamRef,
    Download,
    CombinedDownload,
    ChannelFeed,
    SearchResults,
    pipeline,
    VideoMeta,
    Thumbnail,
    PytError,
    VideoUnavailable,
    AgeRestricted,
    LiveStreamNotSupported,
    NoMatchingStream,
    DownloadError,
    PostProcessError,
    ConfigError,
)
