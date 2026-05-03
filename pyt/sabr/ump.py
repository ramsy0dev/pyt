"""UMP (Unified Media Protocol) response stream parser.

Each UMP part has the form:
  [ump-varint: part_type][ump-varint: payload_length][bytes: payload]

UMP uses an RFC8794-based varint encoding (NOT standard protobuf LEB128).
The top N bits of the first byte determine byte count:
  0xxxxxxx  → 1 byte,  value = first & 0x7F
  10xxxxxx  → 2 bytes, value = (next << 6) | (first & 0x3F)
  110xxxxx  → 3 bytes, value = LE-uint16(next2) | (first & 0x1F)
  1110xxxx  → 4 bytes, value = LE-uint24(next3) | (first & 0x0F)
  11110xxx  → 5 bytes, value = LE-uint32(next4)  (ignores low 3 bits of first)

Parts MAY span multiple HTTP responses (chunked delivery). This parser is
therefore stateful: create one instance and call feed() once per HTTP response.
The caller (SabrClient) is responsible for sending follow-up requests.
"""
import struct
import logging
from typing import Iterator, Optional

from pyt.sabr.proto import parse_fields

logger = logging.getLogger(__name__)

# Part types we act on
UMP_MEDIA_HEADER = 20  # protobuf: itag, lmt, content_length
UMP_MEDIA        = 21  # raw media bytes, prefixed with a single null byte
UMP_MEDIA_END    = 22  # empty terminator

_READ_SIZE = 65536


def _ump_varint(data: bytes, pos: int):
    """Decode one UMP RFC8794 varint from *data* starting at *pos*.

    Returns (value, new_pos).  Raises ValueError when more bytes are needed.
    """
    if pos >= len(data):
        raise ValueError("need more bytes")

    first = data[pos]

    if not (first & 0x80):          # 0xxxxxxx — 1 byte
        return first, pos + 1

    if not (first & 0x40):          # 10xxxxxx — 2 bytes
        if pos + 1 >= len(data):
            raise ValueError("need more bytes")
        return (data[pos + 1] << 6) | (first & 0x3F), pos + 2

    if not (first & 0x20):          # 110xxxxx — 3 bytes
        if pos + 2 >= len(data):
            raise ValueError("need more bytes")
        return (first & 0x1F) | (data[pos + 1] << 5) | (data[pos + 2] << 13), pos + 3

    if not (first & 0x10):          # 1110xxxx — 4 bytes
        if pos + 3 >= len(data):
            raise ValueError("need more bytes")
        return (first & 0x0F) | (data[pos + 1] << 4) | (data[pos + 2] << 12) | (data[pos + 3] << 20), pos + 4

    # 11110xxx — 5 bytes; reads 4-byte LE uint32 from the next 4 bytes
    if pos + 4 >= len(data):
        raise ValueError("need more bytes")
    return struct.unpack_from('<I', data, pos + 1)[0], pos + 5


class UmpParser:
    """Stateful UMP parser.  Feed one HTTP response at a time via feed().

    Yields (part_type: int, payload: bytes) for complete UMP parts.
    Incomplete parts are buffered and completed by subsequent feed() calls.
    """

    def __init__(self):
        self._buf = b''
        self._pending_type: Optional[int] = None
        self._pending_remaining: int = 0
        self._pending_chunks: list = []

    def _drain(self) -> Iterator[tuple]:
        """Parse as many complete parts from self._buf as possible."""
        # Complete any pending cross-response part first
        if self._pending_type is not None:
            avail = len(self._buf)
            if avail == 0:
                return
            if avail >= self._pending_remaining:
                self._pending_chunks.append(self._buf[:self._pending_remaining])
                payload = b''.join(self._pending_chunks)
                self._buf = self._buf[self._pending_remaining:]
                pt = self._pending_type
                self._pending_type = None
                self._pending_remaining = 0
                self._pending_chunks = []
                yield pt, payload
            else:
                self._pending_chunks.append(self._buf)
                self._pending_remaining -= avail
                self._buf = b''
                return

        # Parse new parts
        while True:
            if not self._buf:
                break
            pos = 0

            try:
                part_type, pos = _ump_varint(self._buf, pos)
            except ValueError:
                break

            try:
                length, pos = _ump_varint(self._buf, pos)
            except ValueError:
                break

            payload_end = pos + length
            if len(self._buf) >= payload_end:
                payload = self._buf[pos:payload_end]
                self._buf = self._buf[payload_end:]
                yield part_type, payload
            else:
                available = self._buf[pos:]
                self._pending_type = part_type
                self._pending_remaining = length - len(available)
                self._pending_chunks = [available]
                self._buf = b''
                break

    @property
    def has_pending(self) -> bool:
        """True if a part has started but not yet finished."""
        return self._pending_type is not None

    def feed(self, response) -> Iterator[tuple]:
        """Read one HTTP response and yield complete (part_type, payload) pairs."""
        while True:
            chunk = response.read(_READ_SIZE)
            if not chunk:
                break
            self._buf += chunk
            yield from self._drain()


def parse_media_header(payload: bytes) -> dict:
    """Decode part-20 (MEDIA_HEADER) protobuf payload.

    Known fields (from UMP spec and yt-dlp research):
      field 2: lmt (last-modified, microseconds)
      field 3: itag
      field 4: lmt_url_param
      field 14: content_length (missing for live streams)
    """
    fields = parse_fields(payload)
    return {
        'itag':           fields.get(3, [None])[0],
        'lmt':            fields.get(2, [None])[0],
        'content_length': fields.get(14, [None])[0],
    }
