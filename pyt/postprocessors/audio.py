"""Audio extraction post-processor."""
from __future__ import annotations

import os
from typing import Optional, TYPE_CHECKING

from pyt.postprocessors.ffmpeg import FFmpegPostProcessor, PostProcessorError

if TYPE_CHECKING:
    from pyt.streams import Stream
    from pyt.__main__ import YouTube

# Maps user-facing format name → (ffmpeg codec, file extension)
_CODEC_MAP = {
    "mp3":    ("libmp3lame", ".mp3"),
    "m4a":    ("aac",        ".m4a"),
    "aac":    ("aac",        ".aac"),
    "flac":   ("flac",       ".flac"),
    "opus":   ("libopus",    ".opus"),
    "vorbis": ("libvorbis",  ".ogg"),
    "wav":    ("pcm_s16le",  ".wav"),
    "alac":   ("alac",       ".m4a"),
}

SUPPORTED_FORMATS = list(_CODEC_MAP)


class AudioExtractor(FFmpegPostProcessor):
    """Extract and convert audio from a downloaded stream.

    Equivalent to yt-dlp's ``-x / --extract-audio`` + ``--audio-format``.
    Removes the video track and converts to the target audio format using ffmpeg.
    The original file is deleted after a successful conversion.
    """

    def __init__(self, format: str = "mp3", quality: Optional[str] = None) -> None:
        """
        :param format: Target audio format. One of: mp3, m4a, aac, flac, opus,
            vorbis, wav, alac. Default: mp3.
        :param quality: Optional ffmpeg quality value passed as ``-q:a``.
            ``"0"`` means best VBR quality.
        """
        super().__init__()
        fmt = format.lower()
        if fmt not in _CODEC_MAP:
            raise PostProcessorError(
                f"Unsupported audio format '{format}'. "
                f"Choose from: {', '.join(_CODEC_MAP)}"
            )
        self._format = fmt
        self._codec, self._ext = _CODEC_MAP[fmt]
        self._quality = quality

    def run(self, file_path: str, stream: "Stream", youtube: "YouTube") -> str:
        base, original_ext = os.path.splitext(file_path)
        out_path = base + self._ext

        tmp = self._temp_path(file_path, self._ext)
        args = ["-i", file_path, "-vn", "-acodec", self._codec]
        if self._quality:
            args += ["-q:a", self._quality]
        args.append(tmp)
        self._run_ffmpeg(args)

        os.unlink(file_path)
        if os.path.exists(out_path):
            os.unlink(out_path)
        os.replace(tmp, out_path)
        return out_path
