"""Modern :class:`Playlist`, :class:`ChannelFeed`, and :class:`SearchResults`.

These wrap the legacy ``pyt.contrib.{playlist,channel,search}`` classes.
The shape mirrors :class:`pyt.api.Video`: construction is the I/O moment,
attributes are pure, and iterating yields modern :class:`Video` objects.

The async-iteration and progressive paging shape from the design proposal
is left for v3 — for now ``Playlist.videos`` is a synchronous lazy
generator, which preserves the legacy memory characteristics (one HTTP
fetch per video at iteration time).
"""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Iterator, List, Optional

if TYPE_CHECKING:
    from pyt.api.client import Client
    from pyt.api.video import Video


def _suppress_legacy() -> "warnings.catch_warnings":
    """Context manager that silences the legacy DeprecationWarning."""
    cm = warnings.catch_warnings()
    cm.__enter__()
    warnings.simplefilter("ignore", DeprecationWarning)
    return cm


class Playlist:
    """A YouTube playlist. Construct via :meth:`Client.playlist`."""

    def __init__(self, *, legacy, client: "Client"):
        self._legacy = legacy
        self._client = client

    @classmethod
    def _from_url(cls, url: str, *, client: "Client") -> "Playlist":
        from pyt.contrib.playlist import Playlist as _LegacyPlaylist

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            legacy = _LegacyPlaylist(url, proxies=client._proxies_dict())
        return cls(legacy=legacy, client=client)

    # ── metadata ────────────────────────────────────────────────────────────

    @property
    def playlist_id(self) -> str:
        return self._legacy.playlist_id

    @property
    def url(self) -> str:
        return self._legacy.playlist_url

    @property
    def title(self) -> Optional[str]:
        return self._legacy.title

    @property
    def description(self) -> str:
        return self._legacy.description

    @property
    def length(self) -> int:
        """Number of videos in the playlist."""
        return self._legacy.length

    @property
    def owner(self) -> Optional[str]:
        return self._legacy.owner

    @property
    def owner_url(self) -> Optional[str]:
        return self._legacy.owner_url

    @property
    def video_urls(self) -> List[str]:
        return list(self._legacy.video_urls)

    # ── iteration ───────────────────────────────────────────────────────────

    def __iter__(self) -> Iterator["Video"]:
        return self.videos()

    def videos(self) -> Iterator["Video"]:
        """Yield each :class:`Video` lazily; one HTTP fetch per iteration."""
        for url in self._legacy.video_urls:
            yield self._client.video(url)

    def __len__(self) -> int:
        return self.length

    def __repr__(self) -> str:
        return f"<Playlist id={self.playlist_id!r} title={self.title!r}>"

    @property
    def legacy(self):
        return self._legacy


class ChannelFeed(Playlist):
    """A channel's "Videos" feed. Behaves like a :class:`Playlist`."""

    @classmethod
    def _from_url(cls, url: str, *, client: "Client") -> "ChannelFeed":
        from pyt.contrib.channel import Channel as _LegacyChannel

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            legacy = _LegacyChannel(url, proxies=client._proxies_dict())
        return cls(legacy=legacy, client=client)

    @property
    def name(self) -> Optional[str]:
        return getattr(self._legacy, "channel_name", None) or self.title

    @property
    def channel_id(self) -> Optional[str]:
        return getattr(self._legacy, "channel_id", None)

    def __repr__(self) -> str:
        return f"<ChannelFeed id={self.channel_id!r} name={self.name!r}>"


class SearchResults:
    """A YouTube search result set.

    :class:`SearchResults` is *not* a :class:`Playlist` — search results
    can mix videos, channels, and playlists, and YouTube returns them
    paged via continuation tokens. We expose the first page as
    :attr:`videos`; advanced paging is on the legacy object.
    """

    def __init__(self, *, legacy, client: "Client"):
        self._legacy = legacy
        self._client = client

    @classmethod
    def _from_query(cls, query: str, *, client: "Client") -> "SearchResults":
        from pyt.contrib.search import Search as _LegacySearch

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            legacy = _LegacySearch(query)
        return cls(legacy=legacy, client=client)

    @property
    def query(self) -> str:
        return self._legacy.query

    @property
    def videos(self) -> List["Video"]:
        """First page of video results, materialized as :class:`Video`."""
        out: List["Video"] = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            raw = list(self._legacy.results or [])
        for legacy_yt in raw:
            try:
                out.append(self._client.video(legacy_yt.watch_url))
            except Exception:
                continue
        return out

    @property
    def legacy(self):
        return self._legacy

    def __repr__(self) -> str:
        return f"<SearchResults query={self.query!r}>"
