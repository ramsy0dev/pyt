"""SabrClient: YouTube SABR (Server Adaptive Bitrate Request) downloader.

Sends VideoPlaybackAbrRequest protobuf to serverAbrStreamingUrl, parses
the UMP (Unified Media Protocol) binary response, and yields raw media bytes.

The SABR protocol delivers content across multiple HTTP request/response
pairs (each identified by an incrementing rn= query parameter).  UMP parts
may span response boundaries; the stateful UmpParser handles reassembly.

Reference: yt-dlp PR #13515 (coletdjnz:feat/youtube/sabr)
Protobuf field numbers verified against:
  yt_dlp/extractor/youtube/_proto/videostreaming/video_playback_abr_request.py
"""
import base64
import logging
import socket
from typing import Iterator, Optional

from pyt.sabr.proto import (
    field_varint, field_bytes, field_message,
)
from pyt.sabr.ump import (
    UmpParser, parse_media_header,
    UMP_MEDIA_HEADER, UMP_MEDIA, UMP_MEDIA_END,
)
from pyt import request

logger = logging.getLogger(__name__)

# Stop after this many consecutive rounds with no UMP_MEDIA for any format.
_MAX_EMPTY_ROUNDS = 3


# ── Protobuf message builders ──────────────────────────────────────────────


def _format_id(itag: int) -> bytes:
    """FormatId { field 1: itag (Int32) }"""
    return field_varint(1, itag)


def _client_abr_state(track_types: int, player_time_ms: int = 0) -> bytes:
    """ClientAbrState { field 28: player_time_ms, field 40: enabled_track_types_bitfield }"""
    msg = b''
    if player_time_ms:
        msg += field_varint(28, player_time_ms)
    msg += field_varint(40, track_types)
    return msg


def _buffered_range(itag: int, start_time_ms: int, duration_ms: int) -> bytes:
    """BufferedRange { field 1: format_id, field 2: start_time_ms, field 3: duration_ms }"""
    msg = field_message(1, _format_id(itag))
    msg += field_varint(2, start_time_ms)
    msg += field_varint(3, duration_ms)
    return msg


def _streamer_context(po_token_bytes: bytes) -> bytes:
    """StreamerContext { field 2: po_token (Bytes) }"""
    return field_bytes(2, po_token_bytes)


def _build_vpabr(
    video_itag: Optional[int],
    audio_itag: Optional[int],
    ustreamer_config: Optional[bytes],
    po_token_bytes: Optional[bytes],
    initialized_itags: list,
    player_time_ms: int = 0,
    buffered_ranges: Optional[list] = None,
) -> bytes:
    """Build a VideoPlaybackAbrRequest protobuf message.

    Field numbers from yt-dlp PR #13515:
      1  client_abr_state              (message)
      2  initialized_format_ids        (repeated message) — formats already seen
      3  buffered_ranges               (repeated message) — content client already has
      4  player_time_ms                (Int64)
      5  video_playback_ustreamer_config (Bytes)
      16 preferred_audio_format_ids   (repeated message)
      17 preferred_video_format_ids   (repeated message)
      19 streamer_context              (message)
    """
    track_types = 0
    if video_itag:
        track_types |= 2
    if audio_itag:
        track_types |= 1

    msg = b''

    # Field 1: ClientAbrState
    msg += field_message(1, _client_abr_state(track_types, player_time_ms))

    # Field 2: initialized_format_ids (skip resending init segment for these)
    for itag in initialized_itags:
        msg += field_message(2, _format_id(itag))

    # Field 3: buffered_ranges — tells server what content we already have
    if buffered_ranges:
        for itag, start_ms, dur_ms in buffered_ranges:
            msg += field_message(3, _buffered_range(itag, start_ms, dur_ms))

    # Field 4: player_time_ms
    msg += field_varint(4, player_time_ms)

    # Field 5: videoPlaybackUstreamerConfig
    if ustreamer_config:
        msg += field_bytes(5, ustreamer_config)

    # Field 16: preferred audio formats
    if audio_itag:
        msg += field_message(16, _format_id(audio_itag))

    # Field 17: preferred video formats
    if video_itag:
        msg += field_message(17, _format_id(video_itag))

    # Field 19: StreamerContext (optional PO token)
    if po_token_bytes:
        msg += field_message(19, _streamer_context(po_token_bytes))

    return msg


# ── SabrClient ─────────────────────────────────────────────────────────────


class SabrClient:
    """Download one YouTube stream via the SABR protocol."""

    def __init__(
        self,
        sabr_url: str,
        itag: int,
        ustreamer_config: Optional[bytes] = None,
        po_token: Optional[str] = None,
        is_video: bool = True,
        filesize: int = 0,
        duration_ms: int = 0,
        already_downloaded: int = 0,
    ):
        self._sabr_url = sabr_url
        self._itag = itag
        self._ustreamer_config = ustreamer_config
        self._is_video = is_video
        self._filesize = filesize
        self._duration_ms = duration_ms
        self._already_downloaded = already_downloaded

        self._po_token_bytes: Optional[bytes] = None
        if po_token:
            try:
                padded = po_token + '=' * (-len(po_token) % 4)
                self._po_token_bytes = base64.urlsafe_b64decode(padded)
            except Exception:
                self._po_token_bytes = po_token.encode('utf-8')

    def stream(
        self,
        timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
    ) -> Iterator[bytes]:
        """Yield raw media bytes for the requested itag.

        When already_downloaded > 0 (a resume), the first request sends
        buffered_ranges so the server skips content we already have and
        delivers only the remainder.
        """
        # Start downloaded counter at the resume offset so player_time_ms
        # and termination checks are computed relative to the full file.
        downloaded = self._already_downloaded
        player_time_ms = 0
        if self._already_downloaded and self._filesize and self._duration_ms:
            player_time_ms = int(
                self._already_downloaded * self._duration_ms / self._filesize
            )

        initialized_itags: list = []
        current_itag: Optional[int] = None
        rn = 0
        empty_rounds = 0

        parser = UmpParser()

        video_itag = self._itag if self._is_video else None
        audio_itag = self._itag if not self._is_video else None

        while True:
            # Tell the server what we already have so it delivers only the rest.
            buffered_ranges = None
            if downloaded > 0 and self._filesize and self._duration_ms:
                buf_ms = int(downloaded * self._duration_ms / self._filesize)
                buffered_ranges = [(self._itag, 0, buf_ms)]

            body = _build_vpabr(
                video_itag=video_itag,
                audio_itag=audio_itag,
                ustreamer_config=self._ustreamer_config,
                po_token_bytes=self._po_token_bytes,
                initialized_itags=initialized_itags,
                player_time_ms=player_time_ms,
                buffered_ranges=buffered_ranges,
            )

            sep = '&' if '?' in self._sabr_url else '?'
            url = f'{self._sabr_url}{sep}rn={rn}'

            response = request._execute_request(
                url,
                method='POST',
                headers={
                    'Content-Type': 'application/x-protobuf',
                    'Accept': 'application/vnd.yt-ump',
                    'Accept-Encoding': 'identity',
                },
                data=body,
                timeout=timeout,
            )

            got_media = False      # new bytes for our itag this round
            got_any_media = False  # UMP_MEDIA received for ANY format

            for part_type, payload in parser.feed(response):
                if part_type == UMP_MEDIA_HEADER:
                    info = parse_media_header(payload)
                    current_itag = info.get('itag')
                    logger.debug(
                        'SABR MEDIA_HEADER itag=%s content_length=%s',
                        current_itag, info.get('content_length'),
                    )
                    if current_itag and current_itag not in initialized_itags:
                        initialized_itags.append(current_itag)

                elif part_type == UMP_MEDIA:
                    got_any_media = True
                    if current_itag != self._itag:
                        continue
                    # Strip the leb128 sequence-number prefix (1 byte for seq 0-127).
                    # The prefix is present on every UMP_MEDIA part, not just seq=0.
                    chunk = payload[1:] if payload else b''
                    if chunk:
                        downloaded += len(chunk)
                        got_media = True
                        yield chunk

                elif part_type == UMP_MEDIA_END:
                    logger.debug('SABR MEDIA_END itag=%s downloaded=%d', current_itag, downloaded)
                    current_itag = None

                else:
                    logger.debug('SABR part type=%d len=%d (skipped)', part_type, len(payload))

            rn += 1

            if self._filesize and self._duration_ms and downloaded > 0:
                player_time_ms = int(downloaded * self._duration_ms / self._filesize)
                if player_time_ms >= self._duration_ms:
                    break

            if self._filesize and downloaded >= self._filesize:
                break

            if not got_any_media:
                empty_rounds += 1
                if empty_rounds >= _MAX_EMPTY_ROUNDS:
                    logger.debug(
                        'SABR: %d empty rounds, stopping (downloaded=%d itag=%d)',
                        empty_rounds, downloaded, self._itag,
                    )
                    break
            else:
                empty_rounds = 0
