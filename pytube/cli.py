#!/usr/bin/env python3
"""pytube — YouTube downloader CLI."""
import os
import sys
import json
import gzip
import math
import shutil
import logging
import argparse
import subprocess  # nosec
import time
import datetime as dt
import pytube.exceptions as exceptions

from typing import List, Optional

from pytube import __version__
from pytube import CaptionQuery, Playlist, Stream, YouTube
from pytube.helpers import setup_logger, safe_filename

logger = logging.getLogger(__name__)

# ── Terminal colour helpers ───────────────────────────────────────────────────

_COLOUR = sys.stdout.isatty()

if _COLOUR and sys.platform == "win32":
    os.system("")  # activate ENABLE_VIRTUAL_TERMINAL_PROCESSING

def _c(code: str) -> str:
    return f"\033[{code}m" if _COLOUR else ""

R  = _c("0")       # reset
B  = _c("1")       # bold
DM = _c("2")       # dim
CY = _c("36")      # cyan
GR = _c("32")      # green
YL = _c("33")      # yellow
RD = _c("31")      # red
MG = _c("35")      # magenta
BCY = _c("96")     # bright cyan
BGN = _c("92")     # bright green
BYL = _c("93")     # bright yellow
BRD = _c("91")     # bright red
BWH = _c("97")     # bright white

# ── Output helpers ────────────────────────────────────────────────────────────

def _print_info(label: str, value: str) -> None:
    pad = 10
    sys.stdout.write(f"  {B}{BWH}{label:<{pad}}{R}  {value}\n")

def _print_ok(msg: str) -> None:
    sys.stdout.write(f"\n  {BGN}✓{R}  {msg}\n")

def _print_err(msg: str) -> None:
    sys.stdout.write(f"\n  {BRD}✗{R}  {msg}\n")

def _print_warn(msg: str) -> None:
    sys.stdout.write(f"  {BYL}!{R}  {msg}\n")

def _print_section(title: str) -> None:
    sys.stdout.write(f"\n  {B}{BCY}{title}{R}\n")

def _fmt_bytes(n: int) -> str:
    """Human-readable byte count."""
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB"):
        n /= 1024
        if n < 1024:
            return f"{n:.1f} {unit}"
    return f"{n:.1f} TB"

def _fmt_seconds(secs: float) -> str:
    secs = int(secs)
    if secs < 60:
        return f"{secs}s"
    m, s = divmod(secs, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"

def _fmt_duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

# ── Progress bar ──────────────────────────────────────────────────────────────

_DL_STATE: dict = {}

BAR_FILL  = "█"
BAR_EMPTY = "░"

def _draw_progress(bytes_recv: int, filesize: int, speed: float, eta: float) -> None:
    cols     = shutil.get_terminal_size().columns
    pct      = bytes_recv / filesize if filesize else 0
    pct_str  = f"{pct * 100:5.1f}%"
    size_str = f"{_fmt_bytes(bytes_recv)} / {_fmt_bytes(filesize)}"
    spd_str  = f"{_fmt_bytes(int(speed))}/s" if speed > 0 else "-- B/s"
    eta_str  = f"ETA {_fmt_seconds(eta)}" if eta > 0 and pct < 1 else ("Done" if pct >= 1 else "")

    right = f"  {DM}{size_str}{R}  {CY}{spd_str}{R}  {DM}{eta_str}{R}"
    right_plain_len = len(size_str) + len(spd_str) + len(eta_str) + 8

    bar_space = cols - 4 - len(pct_str) - right_plain_len - 2
    bar_space = max(10, bar_space)

    filled    = int(bar_space * pct)
    remaining = bar_space - filled
    bar       = f"{BGN}{BAR_FILL * filled}{R}{DM}{BAR_EMPTY * remaining}{R}"

    line = f"\r  {bar}  {B}{pct_str}{R}{right}"
    sys.stdout.write(line)
    sys.stdout.flush()


def on_progress(stream: Stream, chunk: bytes, bytes_remaining: int) -> None:
    filesize     = stream.filesize
    bytes_recv   = filesize - bytes_remaining
    now          = time.monotonic()

    if not _DL_STATE:
        _DL_STATE["start"] = now
        _DL_STATE["last_t"] = now
        _DL_STATE["last_b"] = 0

    elapsed = now - _DL_STATE["start"]
    speed   = bytes_recv / elapsed if elapsed > 0 else 0
    eta     = bytes_remaining / speed if speed > 0 else 0

    _draw_progress(bytes_recv, filesize, speed, eta)


# ── Stream table ──────────────────────────────────────────────────────────────

def display_streams(youtube: YouTube) -> None:
    streams = list(youtube.streams)
    if not streams:
        _print_warn("No streams found.")
        return

    _print_section(f"Available streams — {youtube.title}")

    col_itag  = 6
    col_type  = 14
    col_fmt   = 6
    col_qual  = 10
    col_size  = 9

    header = (
        f"  {DM}"
        f"{'itag':>{col_itag}}  "
        f"{'type':<{col_type}}  "
        f"{'fmt':<{col_fmt}}  "
        f"{'quality':<{col_qual}}  "
        f"{'~size':>{col_size}}  "
        f"codec{R}"
    )
    sep = f"  {DM}{'─' * (col_itag + col_type + col_fmt + col_qual + col_size + 18)}{R}"

    sys.stdout.write(f"\n{header}\n{sep}\n")

    for s in streams:
        if s.includes_audio_track and s.includes_video_track:
            kind = "progressive"
            kind_col = f"{GR}{kind:<{col_type}}{R}"
        elif s.includes_video_track:
            kind = "video only"
            kind_col = f"{CY}{kind:<{col_type}}{R}"
        else:
            kind = "audio only"
            kind_col = f"{MG}{kind:<{col_type}}{R}"

        quality = str(s.resolution or s.abr or "—")
        subtype = str(s.subtype or "?")
        try:
            size = _fmt_bytes(s.filesize_approx)
        except (TypeError, ValueError):
            size = "—"

        codecs = []
        if s.video_codec:
            codecs.append(str(s.video_codec))
        if s.audio_codec:
            codecs.append(str(s.audio_codec))
        codec_str = f"{DM}" + " + ".join(codecs) + f"{R}"

        sys.stdout.write(
            f"  {BCY}{s.itag:>{col_itag}}{R}  "
            f"{kind_col}  "
            f"{subtype:<{col_fmt}}  "
            f"{quality:<{col_qual}}  "
            f"{size:>{col_size}}  "
            f"{codec_str}\n"
        )
    sys.stdout.write("\n")


# ── Video info header ─────────────────────────────────────────────────────────

def _show_video_info(youtube: YouTube) -> None:
    try:
        title   = youtube.title
        author  = youtube.author
        length  = _fmt_duration(youtube.length)
        views   = f"{youtube.views:,}"
        url     = youtube.watch_url
    except Exception:
        return

    sys.stdout.write("\n")
    _print_info("Title",  f"{B}{BWH}{title}{R}")
    _print_info("Author", author)
    _print_info("Length", f"{length}  ·  Views  {views}")
    _print_info("URL",    f"{DM}{url}{R}")
    sys.stdout.write("\n")


# ── Download helpers ──────────────────────────────────────────────────────────

def _download(
    stream: Stream,
    target: Optional[str] = None,
    filename: Optional[str] = None,
) -> None:
    _DL_STATE.clear()
    name = filename or stream.default_filename
    try:
        size = _fmt_bytes(stream.filesize_approx)
    except (TypeError, ValueError):
        size = "?"

    _print_section(f"Downloading  {BWH}{name}{R}  {DM}[{size}]{R}")
    sys.stdout.write("\n")

    file_path = stream.get_file_path(filename=filename, output_path=target)
    if stream.exists_at_path(file_path):
        _print_warn(f"Already exists at  {DM}{file_path}{R}")
        return

    stream.download(output_path=target, filename=filename)
    sys.stdout.write("\n")
    _print_ok(f"Saved to  {DM}{file_path}{R}")


def _unique_name(base: str, subtype: str, media_type: str, target: str) -> str:
    counter = 0
    while True:
        name = f"{base}_{media_type}_{counter}"
        if not os.path.exists(os.path.join(target, f"{name}.{subtype}")):
            return name
        counter += 1


# ── Download commands ─────────────────────────────────────────────────────────

def download_by_itag(youtube: YouTube, itag: int, target: Optional[str] = None) -> None:
    stream = youtube.streams.get_by_itag(itag)
    if stream is None:
        _print_err(f"No stream with itag {itag}. Available streams:")
        display_streams(youtube)
        sys.exit(1)
    youtube.register_on_progress_callback(on_progress)
    try:
        _download(stream, target=target)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        _print_warn("Interrupted.")
        sys.exit(1)


def download_by_resolution(youtube: YouTube, resolution: str, target: Optional[str] = None) -> None:
    stream = youtube.streams.get_by_resolution(resolution)
    if stream is None:
        _print_err(f"No stream at {resolution}. Available streams:")
        display_streams(youtube)
        sys.exit(1)
    youtube.register_on_progress_callback(on_progress)
    try:
        _download(stream, target=target)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        _print_warn("Interrupted.")
        sys.exit(1)


def download_highest_resolution_progressive(youtube: YouTube, target: Optional[str] = None) -> None:
    youtube.register_on_progress_callback(on_progress)
    try:
        stream = youtube.streams.get_highest_resolution()
    except exceptions.VideoUnavailable as err:
        _print_err(f"Video unavailable: {err}")
        sys.exit(1)
    try:
        _download(stream, target=target)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        _print_warn("Interrupted.")
        sys.exit(1)


def download_audio(youtube: YouTube, filetype: str, target: Optional[str] = None) -> None:
    audio = (
        youtube.streams.filter(only_audio=True, subtype=filetype)
        .order_by("abr")
        .last()
    )
    if audio is None:
        _print_err(f"No {filetype} audio stream found. Available streams:")
        display_streams(youtube)
        sys.exit(1)
    youtube.register_on_progress_callback(on_progress)
    try:
        _download(audio, target=target)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        _print_warn("Interrupted.")
        sys.exit(1)


def download_caption(
    youtube: YouTube, lang_code: Optional[str], target: Optional[str] = None
) -> None:
    try:
        caption = youtube.captions[lang_code]
        path    = caption.download(title=youtube.title, output_path=target)
        _print_ok(f"Caption saved to  {DM}{path}{R}")
    except KeyError:
        _print_err(f"No caption with code '{lang_code}'. Available:")
        _print_available_captions(youtube.captions)


def _print_available_captions(captions: CaptionQuery) -> None:
    codes = "  ".join(f"{BCY}{c.code}{R}" for c in captions)
    sys.stdout.write(f"  {codes}\n")


def ffmpeg_process(youtube: YouTube, resolution: str, target: Optional[str] = None) -> None:
    youtube.register_on_progress_callback(on_progress)
    target = target or os.getcwd()

    if resolution == "best":
        video_stream = (
            youtube.streams.filter(progressive=False, subtype="mp4")
            .order_by("resolution")
            .last()
        ) or (
            youtube.streams.filter(progressive=False)
            .order_by("resolution")
            .last()
        )
    else:
        video_stream = (
            youtube.streams.filter(progressive=False, resolution=resolution, subtype="mp4").first()
            or youtube.streams.filter(progressive=False, resolution=resolution).first()
        )

    if video_stream is None:
        _print_err(f"No stream at {resolution}. Available streams:")
        display_streams(youtube)
        sys.exit(1)

    audio_stream = (
        youtube.streams.get_audio_only(video_stream.subtype)
        or youtube.streams.filter(only_audio=True).order_by("abr").last()
    )
    if audio_stream is None:
        _print_err("No audio stream found.")
        sys.exit(1)

    _ffmpeg_downloader(audio_stream=audio_stream, video_stream=video_stream, target=target)


def _ffmpeg_downloader(audio_stream: Stream, video_stream: Stream, target: str) -> None:
    base         = safe_filename(video_stream.title)
    video_name   = _unique_name(base, video_stream.subtype, "video", target)
    audio_name   = _unique_name(base, audio_stream.subtype, "audio", target)

    _download(stream=video_stream, target=target, filename=video_name)
    _DL_STATE.clear()
    _download(stream=audio_stream, target=target, filename=audio_name)

    video_path = os.path.join(target, f"{video_name}.{video_stream.subtype}")
    audio_path = os.path.join(target, f"{audio_name}.{audio_stream.subtype}")
    final_path = os.path.join(target, f"{base}.{video_stream.subtype}")

    _print_section("Merging with ffmpeg")
    subprocess.run(  # nosec
        ["ffmpeg", "-i", video_path, "-i", audio_path, "-codec", "copy", final_path],
        check=False,
    )
    os.unlink(video_path)
    os.unlink(audio_path)
    _print_ok(f"Merged to  {DM}{final_path}{R}")


def build_playback_report(youtube: YouTube) -> None:
    ts = int(dt.datetime.now(dt.UTC).timestamp())
    fp = os.path.join(os.getcwd(), f"yt-video-{youtube.video_id}-{ts}.json.gz")
    with gzip.open(fp, "wb") as fh:
        fh.write(json.dumps({
            "url":        youtube.watch_url,
            "js":         youtube.js,
            "watch_html": youtube.watch_html,
            "video_info": youtube.vid_info,
        }).encode("utf-8"))
    _print_ok(f"Playback report saved to  {DM}{fp}{R}")


# ── Argument parsing ──────────────────────────────────────────────────────────

def _parse_args(
    parser: argparse.ArgumentParser, args: Optional[List] = None
) -> argparse.Namespace:
    parser.add_argument("url", nargs="?", help="YouTube watch or playlist URL")
    parser.add_argument("--version", action="version", version=f"pytube {__version__}")
    parser.add_argument("--itag", type=int, metavar="ITAG",
                        help="Download the stream with this itag")
    parser.add_argument("-r", "--resolution", metavar="RES",
                        help="Download the stream at this resolution (e.g. 1080p)")
    parser.add_argument("-l", "--list", action="store_true",
                        help="List all available streams")
    parser.add_argument("-a", "--audio", const="mp4", nargs="?", metavar="FMT",
                        help="Download audio only (default format: mp4)")
    parser.add_argument("-f", "--ffmpeg", const="best", nargs="?", metavar="RES",
                        help="Download video+audio separately and merge with ffmpeg")
    parser.add_argument("-c", "--caption-code", metavar="LANG",
                        help="Download captions for the given language code (e.g. en)")
    parser.add_argument("-lc", "--list-captions", action="store_true",
                        help="List available caption language codes")
    parser.add_argument("-t", "--target", metavar="DIR",
                        help="Output directory (default: current directory)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--logfile", metavar="FILE",
                        help="Write log output to this file")
    parser.add_argument("--build-playback-report", action="store_true",
                        help="Save raw HTML/JS/vid-info to a gzip report for debugging")
    return parser.parse_args(args)


# ── Entry point ───────────────────────────────────────────────────────────────

def _perform_args_on_youtube(youtube: YouTube, args: argparse.Namespace) -> None:
    no_action = not any([
        args.list, args.list_captions, args.build_playback_report,
        args.itag, args.caption_code, args.resolution, args.audio, args.ffmpeg,
    ])

    _show_video_info(youtube)

    if no_action:
        download_highest_resolution_progressive(youtube=youtube, target=args.target)
        return

    if args.list:
        display_streams(youtube)
    if args.list_captions:
        _print_section("Available captions")
        _print_available_captions(youtube.captions)
    if args.build_playback_report:
        build_playback_report(youtube)
    if args.itag:
        download_by_itag(youtube=youtube, itag=args.itag, target=args.target)
    if args.caption_code:
        download_caption(youtube=youtube, lang_code=args.caption_code, target=args.target)
    if args.resolution:
        download_by_resolution(youtube=youtube, resolution=args.resolution, target=args.target)
    if args.audio:
        download_audio(youtube=youtube, filetype=args.audio, target=args.target)
    if args.ffmpeg:
        ffmpeg_process(youtube=youtube, resolution=args.ffmpeg, target=args.target)


def main() -> None:
    """YouTube downloader — download videos, audio, and captions from YouTube."""
    parser = argparse.ArgumentParser(
        prog="pytube",
        description=main.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    args = _parse_args(parser)

    if args.verbose:
        setup_logger(logging.DEBUG, log_filename=args.logfile)
        logger.debug("pytube %s", __version__)

    if not args.url or "youtu" not in args.url:
        parser.print_help()
        sys.exit(1)

    if "/playlist" in args.url:
        sys.stdout.write(f"\n  {DM}Loading playlist …{R}\n")
        playlist = Playlist(args.url)
        if not args.target:
            args.target = safe_filename(playlist.title)
        for video in playlist.videos:
            try:
                _perform_args_on_youtube(video, args)
            except exceptions.PytubeError as exc:
                _print_err(f"{video.watch_url}  —  {exc}")
    else:
        sys.stdout.write(f"\n  {DM}Fetching  {args.url} …{R}\n")
        youtube = YouTube(args.url)
        _perform_args_on_youtube(youtube, args)


if __name__ == "__main__":
    main()
