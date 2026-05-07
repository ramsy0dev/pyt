"""ffmpeg-merge helpers shared by the modern download path and the CLI.

Kept private (leading underscore) for now — the API may move once the new
``CombinedDownload`` shape settles. The CLI imports the same helper so
container-selection logic doesn't drift between code paths.
"""
from __future__ import annotations

import logging
import shutil
import subprocess  # nosec - we control all argv entries
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pyt.api.streams import StreamRef
    from pyt.streams import Stream as _LegacyStream


logger = logging.getLogger(__name__)


def pick_merge_container(video_codec: Optional[str], audio_codec: Optional[str]) -> str:
    """Pick the right container for muxing two codecs without re-encoding.

    YouTube serves video as one of: avc1 (H.264) in mp4, vp9 in webm, av01 in mp4.
    Audio: mp4a/aac in m4a, opus in webm.
    ``-codec copy`` requires the container to accept both codecs. mp4 takes
    avc1+aac and av01+aac; webm takes vp9+opus. mkv accepts everything and is
    the safe fallback for cross-family combinations.
    """
    v = (video_codec or "").lower()
    a = (audio_codec or "").lower()
    is_avc = v.startswith("avc")
    is_av1 = v.startswith("av01") or v.startswith("av1")
    is_vp9 = v.startswith("vp9") or v.startswith("vp09")
    is_aac = a.startswith("mp4a") or a.startswith("aac")
    is_opus = a.startswith("opus")

    if (is_avc or is_av1) and is_aac:
        return "mp4"
    if is_vp9 and is_opus:
        return "webm"
    return "mkv"


def pick_merge_container_for_streams(video, audio) -> str:
    """Convenience wrapper accepting either modern :class:`StreamRef` or
    legacy :class:`pyt.Stream` instances.
    """
    return pick_merge_container(
        getattr(video, "video_codec", None),
        getattr(audio, "audio_codec", None),
    )


class FFmpegNotFound(RuntimeError):
    pass


class FFmpegMergeError(RuntimeError):
    def __init__(self, returncode: int, stderr: str):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"ffmpeg merge failed (exit {returncode}): {stderr.strip()[:400]}")


def run_ffmpeg_merge(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    *,
    container: Optional[str] = None,
) -> Path:
    """Mux *video_path* + *audio_path* into *output_path* with ``-codec copy``.

    Raises :class:`FFmpegNotFound` when ffmpeg isn't on PATH and
    :class:`FFmpegMergeError` when ffmpeg returns non-zero. Caller is
    responsible for cleaning up the source files and the (possibly
    partial) output on failure.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise FFmpegNotFound("ffmpeg not found on PATH; cannot merge")

    ext = (container or output_path.suffix.lstrip(".")).lower()
    cmd = [
        ffmpeg_bin, "-y",
        "-loglevel", "warning", "-nostats",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "copy",
    ]
    if ext == "mp4":
        cmd += ["-movflags", "+faststart"]
    cmd.append(str(output_path))

    result = subprocess.run(cmd, capture_output=True, check=False)  # nosec
    if result.returncode != 0:
        raise FFmpegMergeError(
            result.returncode,
            result.stderr.decode("utf-8", errors="replace"),
        )
    return output_path
