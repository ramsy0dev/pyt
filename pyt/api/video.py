"""The :class:`Video` — a thin, typed facade over :class:`pyt.YouTube`."""
from __future__ import annotations

import logging
import warnings
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import pyt.exceptions as legacy_exc
from pyt.__main__ import YouTube as _LegacyYouTube


logger = logging.getLogger(__name__)
from pyt.api.errors import (
    AgeRestricted,
    LiveStreamNotSupported,
    PytError,
    VideoUnavailable,
)
from pyt.api.models import Channel, Thumbnail, VideoMeta
from pyt.api.streams import StreamSet


def _translate(exc: BaseException, *, video_id: Optional[str], url: Optional[str]) -> PytError:
    """Map a legacy exception onto the modern error tree."""
    if isinstance(exc, legacy_exc.AgeRestrictedError):
        return AgeRestricted(video_id=exc.video_id, url=url)
    if isinstance(exc, legacy_exc.LiveStreamError):
        return LiveStreamNotSupported(video_id=exc.video_id, url=url)
    if isinstance(exc, legacy_exc.VideoUnavailable):
        reason_map = {
            legacy_exc.VideoPrivate: "private",
            legacy_exc.MembersOnly: "members-only",
            legacy_exc.VideoRegionBlocked: "region-blocked",
            legacy_exc.RecordingUnavailable: "recording unavailable",
        }
        reason = reason_map.get(type(exc), "unavailable")
        return VideoUnavailable(video_id=exc.video_id, reason=reason, url=url)
    if isinstance(exc, legacy_exc.PytError):
        wrapped = PytError(str(exc))
        wrapped.video_id = video_id
        wrapped.url = url
        return wrapped
    return None  # not ours; let it propagate


class Video:
    """A YouTube video and its attached :class:`StreamSet`.

    Construct via :meth:`Client.video`. Direct construction is not part
    of the public API — the legacy class is needed for that.
    """

    def __init__(self, legacy: _LegacyYouTube, *, meta: VideoMeta):
        self._legacy = legacy
        self._meta = meta
        self._streams: Optional[StreamSet] = None

    # ── construction ────────────────────────────────────────────────────────

    @classmethod
    def _from_url(
        cls,
        url: str,
        *,
        po_token: Optional[str],
        use_oauth: bool,
        allow_oauth_cache: bool,
        proxies: Optional[Dict[str, str]],
        on_progress: Optional[Callable[[Any, bytes, int], None]],
        on_complete: Optional[Callable[[Any, Optional[str]], None]],
    ) -> "Video":
        try:
            with warnings.catch_warnings():
                # The legacy YouTube class emits a DeprecationWarning at the
                # boundary; suppress it here because we *are* the new API and
                # the user is doing the right thing.
                warnings.simplefilter("ignore", DeprecationWarning)
                yt = _LegacyYouTube(
                    url,
                    on_progress_callback=on_progress,
                    on_complete_callback=on_complete,
                    proxies=proxies,
                    use_oauth=use_oauth,
                    allow_oauth_cache=allow_oauth_cache,
                    po_token=po_token,
                )
        except legacy_exc.PytError as exc:
            logger.warning("Video._from_url: legacy YouTube ctor failed for %s: %s", url, exc)
            translated = _translate(exc, video_id=None, url=url)
            raise translated if translated is not None else exc

        logger.debug("Video._from_url: legacy YouTube ctor OK, video_id=%s", yt.video_id)

        try:
            meta = _hydrate_meta(yt, url=url)
        except legacy_exc.PytError as exc:
            logger.warning(
                "Video._from_url: hydrate_meta failed for %s: %s",
                getattr(yt, "video_id", "?"), exc,
            )
            translated = _translate(exc, video_id=getattr(yt, "video_id", None), url=url)
            raise translated if translated is not None else exc

        return cls(yt, meta=meta)

    # ── public surface ──────────────────────────────────────────────────────

    @property
    def metadata(self) -> VideoMeta:
        return self._meta

    @property
    def video_id(self) -> str:
        return self._meta.video_id

    @property
    def url(self) -> str:
        return self._meta.url

    @property
    def title(self) -> str:
        return self._meta.title

    @property
    def author(self) -> Channel:
        return self._meta.author

    @property
    def length(self) -> timedelta:
        return self._meta.length

    @property
    def description(self) -> Optional[str]:
        return self._meta.description

    @property
    def published_at(self) -> Optional[datetime]:
        return self._meta.published_at

    @property
    def views(self) -> Optional[int]:
        return self._meta.views

    @property
    def thumbnails(self) -> List[Thumbnail]:
        return list(self._meta.thumbnails)

    @property
    def is_live(self) -> bool:
        return self._meta.is_live

    @property
    def streams(self) -> StreamSet:
        """The video's stream catalog. Lazily fetched once, then cached."""
        if self._streams is None:
            logger.debug("video.streams: hydrating stream catalog for %s", self.video_id)
            try:
                fmt_streams = self._legacy.fmt_streams
            except legacy_exc.PytError as exc:
                logger.warning(
                    "video.streams: fmt_streams failed for %s: %s", self.video_id, exc,
                )
                translated = _translate(exc, video_id=self.video_id, url=self.url)
                raise translated if translated is not None else exc
            self._streams = StreamSet._from_legacy(fmt_streams, video=self)
            logger.info(
                "video.streams: %s catalog has %d streams",
                self.video_id, len(self._streams),
            )
        return self._streams

    # ── combined download ──────────────────────────────────────────────────

    def download_best(
        self,
        output_path: Optional[str] = None,
        *,
        prefer_resolution: Optional[str] = None,
        filename: Optional[str] = None,
        container: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """Pick the best adaptive video + audio pair and run them through
        a single multiplexed SABR session, then merge with ffmpeg.

        :param prefer_resolution: e.g. ``"1080p"``. When unset, picks the
            highest available adaptive video. When the requested resolution
            isn't available, returns the highest one at-or-below it.
        :param container: override the merge container. Auto-detected from
            the codec pair by default (mp4 / webm / mkv).
        :returns: a :class:`CombinedDownload` builder. Call ``.run()`` (or
            chain post-processing with ``.then(...)`` / ``|``) to execute.
        """
        from pyt.api.combined import CombinedDownload

        video_stream, audio_stream = self.streams.best_pair(
            prefer_resolution=prefer_resolution,
        )
        return CombinedDownload(
            video=self,
            video_stream=video_stream,
            audio_stream=audio_stream,
            output_path=output_path,
            filename=filename,
            container=container,
            timeout=timeout,
        )

    # ── escape hatch ────────────────────────────────────────────────────────

    @property
    def legacy(self) -> _LegacyYouTube:
        """The underlying :class:`pyt.YouTube`. Use this when you need
        functionality not yet exposed by the modern API. We treat any
        attribute reachable through ``.legacy`` as semi-public — it won't
        be removed without notice.
        """
        return self._legacy

    def __repr__(self) -> str:
        return f"<Video id={self.video_id!r} title={self.title!r}>"


def _hydrate_meta(yt: _LegacyYouTube, *, url: str) -> VideoMeta:
    """Eagerly read everything we need from the legacy object so the
    :class:`Video` we return has no remaining hidden network I/O.
    """
    yt.check_availability()
    details = yt.vid_info.get("videoDetails", {}) or {}

    raw_thumbs = details.get("thumbnail", {}).get("thumbnails", []) or []
    thumbnails = [
        Thumbnail(
            url=t["url"],
            width=t.get("width"),
            height=t.get("height"),
        )
        for t in raw_thumbs
        if t.get("url")
    ]

    channel_id = details.get("channelId")
    author = Channel(
        id=channel_id,
        name=details.get("author", "unknown"),
        url=f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
    )

    try:
        length = timedelta(seconds=int(details.get("lengthSeconds", 0) or 0))
    except (TypeError, ValueError):
        length = timedelta(0)

    try:
        views = int(details.get("viewCount")) if details.get("viewCount") else None
    except (TypeError, ValueError):
        views = None

    rating = details.get("averageRating")

    published_at: Optional[datetime] = None
    try:
        published_at = yt.publish_date
    except Exception:
        pass

    return VideoMeta(
        video_id=yt.video_id,
        url=url,
        title=details.get("title") or yt.title,
        author=author,
        length=length,
        description=details.get("shortDescription"),
        published_at=published_at,
        views=views,
        rating=float(rating) if rating is not None else None,
        keywords=list(details.get("keywords", []) or []),
        thumbnails=thumbnails,
        is_live=bool(details.get("isLive") or details.get("isLiveContent")),
    )
