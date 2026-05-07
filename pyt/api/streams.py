"""Chainable, immutable stream selection.

Each filter returns a new :class:`StreamSet` rather than mutating in place,
so storing intermediate results in variables is cheap and doesn't leak
mutation across call sites.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable, Iterator, List, Optional, Sequence, Tuple

from pyt.api.errors import NoMatchingStream

if TYPE_CHECKING:
    from pyt.streams import Stream as _LegacyStream
    from pyt.api.download import Download
    from pyt.api.video import Video


# ── helpers ────────────────────────────────────────────────────────────────

_RES_RE = re.compile(r"^(\d+)p$")
_BITRATE_RE = re.compile(r"^(\d+)\s*kbps$", re.IGNORECASE)


def _resolution_to_int(res: Optional[str]) -> Optional[int]:
    if not res:
        return None
    m = _RES_RE.match(res.strip().lower())
    return int(m.group(1)) if m else None


def _bitrate_to_int(abr: Optional[str]) -> Optional[int]:
    if not abr:
        return None
    m = _BITRATE_RE.match(abr.strip())
    return int(m.group(1)) if m else None


def _parse_threshold(value) -> Optional[int]:
    """Accept ``"1080p"``, ``"128kbps"``, ``128``, ``1080`` — return int or None."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return _resolution_to_int(value) or _bitrate_to_int(value)
    return None


# ── StreamRef ──────────────────────────────────────────────────────────────


class StreamRef:
    """A single stream selected from a :class:`StreamSet`.

    This is the object you call :meth:`download_to` on. It is a thin
    wrapper around :class:`pyt.Stream` — everything not redefined here
    is forwarded via :attr:`legacy`.
    """

    def __init__(self, legacy: "_LegacyStream", *, video: "Video"):
        self._legacy = legacy
        self._video = video

    # ── identity ────────────────────────────────────────────────────────────

    @property
    def itag(self) -> int:
        return int(self._legacy.itag)

    @property
    def mime_type(self) -> str:
        return self._legacy.mime_type

    @property
    def kind(self) -> str:
        """``"audio"`` or ``"video"`` (per the MIME top-level type)."""
        return self._legacy.type

    @property
    def subtype(self) -> str:
        return self._legacy.subtype

    @property
    def is_progressive(self) -> bool:
        return bool(self._legacy.is_progressive)

    @property
    def is_adaptive(self) -> bool:
        return bool(self._legacy.is_adaptive)

    @property
    def is_audio_only(self) -> bool:
        return self.kind == "audio"

    @property
    def is_video_only(self) -> bool:
        return self.kind == "video" and not self.is_progressive

    @property
    def resolution(self) -> Optional[str]:
        return getattr(self._legacy, "resolution", None)

    @property
    def fps(self) -> Optional[int]:
        return getattr(self._legacy, "fps", None)

    @property
    def abr(self) -> Optional[str]:
        return getattr(self._legacy, "abr", None)

    @property
    def bitrate(self) -> Optional[int]:
        return getattr(self._legacy, "bitrate", None)

    @property
    def video_codec(self) -> Optional[str]:
        return getattr(self._legacy, "video_codec", None)

    @property
    def audio_codec(self) -> Optional[str]:
        return getattr(self._legacy, "audio_codec", None)

    @property
    def filesize(self) -> int:
        return int(getattr(self._legacy, "filesize", 0) or 0)

    @property
    def video(self) -> "Video":
        return self._video

    @property
    def legacy(self) -> "_LegacyStream":
        return self._legacy

    # ── action ──────────────────────────────────────────────────────────────

    def download_to(
        self,
        output_path: Optional[str] = None,
        *,
        filename: Optional[str] = None,
        filename_prefix: Optional[str] = None,
        skip_existing: bool = True,
        timeout: Optional[int] = None,
        max_retries: int = 0,
    ) -> "Download":
        """Build a lazy :class:`Download`. Call ``.run()`` (or chain a
        pipeline with ``.then(...)`` / ``|``) to actually transfer bytes.
        """
        from pyt.api.download import Download

        return Download(
            stream=self,
            output_path=output_path,
            filename=filename,
            filename_prefix=filename_prefix,
            skip_existing=skip_existing,
            timeout=timeout,
            max_retries=max_retries,
        )

    def __repr__(self) -> str:
        bits = [f"itag={self.itag}", f"kind={self.kind}"]
        if self.resolution:
            bits.append(f"res={self.resolution}")
        if self.abr:
            bits.append(f"abr={self.abr}")
        if self.subtype:
            bits.append(f"ext={self.subtype}")
        return f"<StreamRef {' '.join(bits)}>"


# ── StreamSet ──────────────────────────────────────────────────────────────


class StreamSet(Sequence[StreamRef]):
    """Chainable, immutable view over a tuple of :class:`StreamRef`."""

    def __init__(self, streams: Tuple[StreamRef, ...], *, video: "Video"):
        self._streams = streams
        self._video = video

    @classmethod
    def _from_legacy(cls, fmt_streams: List["_LegacyStream"], *, video: "Video") -> "StreamSet":
        refs = tuple(StreamRef(s, video=video) for s in fmt_streams)
        return cls(refs, video=video)

    # ── Sequence protocol ───────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._streams)

    def __getitem__(self, index):  # type: ignore[override]
        if isinstance(index, slice):
            return StreamSet(self._streams[index], video=self._video)
        return self._streams[index]

    def __iter__(self) -> Iterator[StreamRef]:
        return iter(self._streams)

    def __repr__(self) -> str:
        return f"<StreamSet n={len(self._streams)}>"

    # ── grouped-filter shortcuts (read like English) ───────────────────────

    @property
    def audio(self) -> "StreamSet":
        return self._where(lambda s: s.is_audio_only)

    @property
    def video(self) -> "StreamSet":
        return self._where(lambda s: s.kind == "video")

    @property
    def progressive(self) -> "StreamSet":
        return self._where(lambda s: s.is_progressive)

    @property
    def adaptive(self) -> "StreamSet":
        return self._where(lambda s: s.is_adaptive)

    # ── filters ─────────────────────────────────────────────────────────────

    def filter(
        self,
        *,
        kind: Optional[str] = None,
        subtype: Optional[str] = None,
        resolution: Optional[str] = None,
        codec: Optional[str] = None,
        custom: Optional[Callable[[StreamRef], bool]] = None,
    ) -> "StreamSet":
        """Apply zero or more keyword filters. All criteria are AND-ed.
        ``codec`` matches either video or audio codec via substring.
        """

        def _check(s: StreamRef) -> bool:
            if kind is not None and s.kind != kind:
                return False
            if subtype is not None and s.subtype != subtype:
                return False
            if resolution is not None and s.resolution != resolution:
                return False
            if codec is not None:
                vc = (s.video_codec or "").lower()
                ac = (s.audio_codec or "").lower()
                if codec.lower() not in vc and codec.lower() not in ac:
                    return False
            if custom is not None and not custom(s):
                return False
            return True

        return self._where(_check)

    def codec(self, name: str) -> "StreamSet":
        return self.filter(codec=name)

    def at_least(
        self,
        resolution: Optional[str] = None,
        *,
        bitrate: Optional[str] = None,
    ) -> "StreamSet":
        """Keep streams whose resolution / bitrate is at least the given threshold."""
        res_min = _parse_threshold(resolution)
        br_min = _parse_threshold(bitrate)

        def _check(s: StreamRef) -> bool:
            if res_min is not None:
                their_res = _resolution_to_int(s.resolution)
                if their_res is None or their_res < res_min:
                    return False
            if br_min is not None:
                their_br = _parse_threshold(s.abr) or (s.bitrate // 1000 if s.bitrate else None)
                if their_br is None or their_br < br_min:
                    return False
            return True

        return self._where(_check)

    # ── ordering ────────────────────────────────────────────────────────────

    def order_by(self, attribute: str) -> "StreamSet":
        """Stable sort ascending by attribute name. Streams missing the
        attribute (None) sort to the end.
        """

        def _key(s: StreamRef):
            value = getattr(s, attribute, None)
            if attribute == "resolution":
                value = _resolution_to_int(value)
            elif attribute == "abr":
                value = _parse_threshold(value)
            return (value is None, value)

        return StreamSet(tuple(sorted(self._streams, key=_key)), video=self._video)

    def desc(self) -> "StreamSet":
        return StreamSet(tuple(reversed(self._streams)), video=self._video)

    # ── terminal selectors ──────────────────────────────────────────────────

    def first(self) -> Optional[StreamRef]:
        """Return the first stream or ``None`` when empty."""
        return self._streams[0] if self._streams else None

    def last(self) -> Optional[StreamRef]:
        return self._streams[-1] if self._streams else None

    def best(self) -> StreamRef:
        """Return the highest-quality stream remaining in the set.

        For mixed kinds, audio streams rank by bitrate, video streams by
        resolution. Raises :class:`NoMatchingStream` when the set is empty.
        """
        if not self._streams:
            raise NoMatchingStream(
                "no streams matched the current filters",
                video_id=self._video.video_id,
            )

        def _quality(s: StreamRef) -> Tuple[int, int]:
            res = _resolution_to_int(s.resolution) or 0
            br = _parse_threshold(s.abr) or (s.bitrate // 1000 if s.bitrate else 0)
            return (res, br)

        return max(self._streams, key=_quality)

    def one(self) -> StreamRef:
        """Return the sole matching stream — raise if 0 or >1 match.
        Use this when your filter chain is supposed to be unambiguous and
        you want a loud failure if it's not.
        """
        if len(self._streams) != 1:
            raise NoMatchingStream(
                f"expected exactly 1 stream, got {len(self._streams)}",
                video_id=self._video.video_id,
            )
        return self._streams[0]

    # ── private ─────────────────────────────────────────────────────────────

    def _where(self, predicate: Callable[[StreamRef], bool]) -> "StreamSet":
        return StreamSet(
            tuple(s for s in self._streams if predicate(s)),
            video=self._video,
        )
