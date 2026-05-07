"""Tests for the multi-format SABR orchestrator (pyt.api.combined)."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from pyt.api import CombinedDownload, NoMatchingStream
from pyt.api._merge import (
    FFmpegMergeError,
    FFmpegNotFound,
    pick_merge_container,
    pick_merge_container_for_streams,
)
from pyt.api.video import Video, _hydrate_meta


# ── pick_merge_container ───────────────────────────────────────────────────


@pytest.mark.parametrize("video_codec,audio_codec,expected", [
    ("avc1.640028", "mp4a.40.2", "mp4"),
    ("av01.0.08M.08", "mp4a.40.2", "mp4"),
    ("vp9", "opus", "webm"),
    ("vp09.00.50.08", "opus", "webm"),
    ("avc1.640028", "opus", "mkv"),       # cross-family
    ("vp9", "mp4a.40.2", "mkv"),          # cross-family
    (None, "mp4a.40.2", "mkv"),           # missing codec info
    ("avc1.640028", None, "mkv"),
])
def test_pick_merge_container(video_codec, audio_codec, expected):
    assert pick_merge_container(video_codec, audio_codec) == expected


def test_pick_merge_container_for_streams():
    v = mock.MagicMock(video_codec="avc1.640028")
    a = mock.MagicMock(audio_codec="mp4a.40.2")
    assert pick_merge_container_for_streams(v, a) == "mp4"


# ── StreamSet.best_pair ────────────────────────────────────────────────────


def _make_video(legacy):
    meta = _hydrate_meta(legacy, url=f"https://youtube.com/watch?v={legacy.video_id}")
    return Video(legacy, meta=meta)


def test_best_pair_returns_adaptive_video_and_audio(cipher_signature):
    video = _make_video(cipher_signature)
    v_stream, a_stream = video.streams.best_pair()
    assert v_stream.kind == "video"
    assert v_stream.is_adaptive
    assert a_stream.kind == "audio"


def test_best_pair_caps_at_prefer_resolution(cipher_signature):
    video = _make_video(cipher_signature)
    v_stream, _ = video.streams.best_pair(prefer_resolution="720p")
    if v_stream.resolution:
        assert int(v_stream.resolution.rstrip("p")) <= 720


def test_best_pair_falls_back_when_resolution_too_high(cipher_signature):
    """Asking for a resolution higher than what's available should return
    the highest available rather than raising."""
    video = _make_video(cipher_signature)
    v_stream, _ = video.streams.best_pair(prefer_resolution="9999p")
    assert v_stream is not None  # didn't raise


def test_best_pair_raises_when_no_adaptive_video(cipher_signature):
    """Filter the streams down to audio-only, then ask for a pair."""
    video = _make_video(cipher_signature)
    audio_only = video.streams.audio
    with pytest.raises(NoMatchingStream, match="adaptive video"):
        audio_only.best_pair()


# ── Video.download_best ────────────────────────────────────────────────────


def test_download_best_returns_combined_download(cipher_signature):
    video = _make_video(cipher_signature)
    plan = video.download_best("/tmp")
    assert isinstance(plan, CombinedDownload)


def test_combined_download_validates_video_kind(cipher_signature):
    video = _make_video(cipher_signature)
    audio = video.streams.audio.best()
    other_audio = audio  # both wrong-kind to satisfy the audio param too
    with pytest.raises(ValueError, match="kind='video'"):
        CombinedDownload(
            video=video,
            video_stream=audio,         # wrong kind
            audio_stream=other_audio,
        )


def test_combined_download_validates_audio_kind(cipher_signature):
    video = _make_video(cipher_signature)
    v_stream = video.streams.video.adaptive.first()
    if v_stream is None:
        pytest.skip("fixture has no adaptive video stream")
    with pytest.raises(ValueError, match="kind='audio'"):
        CombinedDownload(
            video=video,
            video_stream=v_stream,
            audio_stream=v_stream,        # wrong kind
        )


def test_combined_download_rejects_progressive(cipher_signature):
    video = _make_video(cipher_signature)
    progressive = video.streams.progressive.first()
    if progressive is None:
        pytest.skip("fixture has no progressive stream")
    audio = video.streams.audio.first()
    with pytest.raises(ValueError, match="progressive"):
        CombinedDownload(
            video=video,
            video_stream=progressive,    # progressive video, not allowed
            audio_stream=audio,
        )


# ── End-to-end: run() with mocked SABR + ffmpeg ─────────────────────────────


def _build_combined(cipher_signature, target_dir, *, video_size=64, audio_size=32):
    """Build a CombinedDownload pinned to a tmp dir.

    Pins expected sizes by writing directly to ``Stream._filesize`` (the
    cached attribute behind the ``.filesize`` property) so the values
    persist past this helper's frame. ``_pick_merge_container`` is
    overridden to ``mkv`` so the ffmpeg invocation is predictable.
    """
    video = _make_video(cipher_signature)
    v_stream = video.streams.video.adaptive.first()
    a_stream = video.streams.audio.first()
    if v_stream is None or a_stream is None:
        pytest.skip("fixture missing the required adaptive video / audio stream")

    v_stream.legacy._filesize = video_size
    a_stream.legacy._filesize = audio_size

    plan = CombinedDownload(
        video=video,
        video_stream=v_stream,
        audio_stream=a_stream,
        output_path=str(target_dir),
        filename="out.mkv",
        container="mkv",
    )
    return video, v_stream, a_stream, plan


def test_run_drives_sabr_and_invokes_ffmpeg(cipher_signature, tmp_path):
    video, v_stream, a_stream, plan = _build_combined(
        cipher_signature, tmp_path, video_size=10, audio_size=6
    )
    # Force a SABR URL so we actually exercise the multiplex path.
    video.legacy.stream_monostate.sabr_url = "https://sabr.example/play"
    video.legacy.stream_monostate.duration = 10
    video.legacy.stream_monostate.po_token = None

    fake_session = mock.MagicMock()
    fake_session.iter_chunks.return_value = iter([
        (v_stream.itag, b"V" * 10),
        (a_stream.itag, b"A" * 6),
    ])

    merge_called = {}

    def fake_merge(video_path, audio_path, output_path, *, container):
        merge_called["video"] = Path(video_path).read_bytes()
        merge_called["audio"] = Path(audio_path).read_bytes()
        merge_called["output"] = Path(output_path)
        merge_called["container"] = container
        Path(output_path).write_bytes(b"merged")
        return Path(output_path)

    with mock.patch("pyt.api.combined.SabrSession", return_value=fake_session) as session_cls, \
         mock.patch("pyt.api.combined.run_ffmpeg_merge", side_effect=fake_merge):
        result = plan.run()

    # SabrSession was constructed with both formats.
    formats_kwarg = session_cls.call_args.kwargs["formats"]
    assert (v_stream.itag, True) in formats_kwarg
    assert (a_stream.itag, False) in formats_kwarg

    # Bytes ended up in their respective .part inputs to ffmpeg.
    assert merge_called["video"] == b"V" * 10
    assert merge_called["audio"] == b"A" * 6
    assert merge_called["container"] == "mkv"
    assert result == tmp_path / "out.mkv"
    assert result.exists()

    # Source .part files cleaned up on success.
    assert not list(tmp_path.glob("*.part"))


def test_run_falls_back_to_range_when_sabr_short(cipher_signature, tmp_path):
    video, v_stream, a_stream, plan = _build_combined(
        cipher_signature, tmp_path, video_size=10, audio_size=6
    )
    video.legacy.stream_monostate.sabr_url = "https://sabr.example/play"
    video.legacy.stream_monostate.duration = 10

    # SABR delivers only 4 video bytes and nothing for audio, then ends.
    fake_session = mock.MagicMock()
    fake_session.iter_chunks.return_value = iter([
        (v_stream.itag, b"V" * 4),
    ])

    # Range-stream returns the missing tails.
    def fake_stream(url, *, timeout, max_retries, start_byte, extra_headers):
        if url == v_stream.legacy.url:
            assert start_byte == 4
            yield b"V" * 6
        elif url == a_stream.legacy.url:
            assert start_byte == 0
            yield b"A" * 6
        else:
            raise AssertionError(f"unexpected url {url!r}")

    captured = {}

    def fake_merge(video_path, audio_path, output_path, *, container):
        captured["video"] = Path(video_path).read_bytes()
        captured["audio"] = Path(audio_path).read_bytes()
        Path(output_path).write_bytes(b"x")
        return Path(output_path)

    with mock.patch("pyt.api.combined.SabrSession", return_value=fake_session), \
         mock.patch("pyt.api.combined.request.stream", side_effect=fake_stream), \
         mock.patch("pyt.api.combined.run_ffmpeg_merge", side_effect=fake_merge):
        plan.run()

    assert captured["video"] == b"V" * 10
    assert captured["audio"] == b"A" * 6


def test_run_uses_range_only_when_no_sabr_url(cipher_signature, tmp_path):
    """No serverAbrStreamingUrl means we skip SABR entirely and finish
    everything via the byte-range path."""
    video, v_stream, a_stream, plan = _build_combined(
        cipher_signature, tmp_path, video_size=10, audio_size=6
    )
    video.legacy.stream_monostate.sabr_url = None  # no SABR

    def fake_stream(url, *, timeout, max_retries, start_byte, extra_headers):
        assert start_byte == 0
        if url == v_stream.legacy.url:
            yield b"V" * 10
        elif url == a_stream.legacy.url:
            yield b"A" * 6
        else:
            raise AssertionError(f"unexpected url {url!r}")

    captured = {}

    def fake_merge(video_path, audio_path, output_path, *, container):
        captured["video"] = Path(video_path).read_bytes()
        captured["audio"] = Path(audio_path).read_bytes()
        Path(output_path).write_bytes(b"x")
        return Path(output_path)

    with mock.patch("pyt.api.combined.SabrSession") as session_cls, \
         mock.patch("pyt.api.combined.request.stream", side_effect=fake_stream), \
         mock.patch("pyt.api.combined.run_ffmpeg_merge", side_effect=fake_merge):
        plan.run()

    # SabrSession was never constructed.
    session_cls.assert_not_called()
    assert captured["video"] == b"V" * 10
    assert captured["audio"] == b"A" * 6


def test_run_then_chains_pipeline_steps(cipher_signature, tmp_path):
    video, v_stream, a_stream, plan = _build_combined(
        cipher_signature, tmp_path, video_size=2, audio_size=2
    )
    video.legacy.stream_monostate.sabr_url = "https://sabr.example/play"

    fake_session = mock.MagicMock()
    fake_session.iter_chunks.return_value = iter([
        (v_stream.itag, b"VV"),
        (a_stream.itag, b"AA"),
    ])

    from pyt.api.pipeline import PipelineStep

    seen = []

    class _Recording(PipelineStep):
        def apply(self, path, *, stream, video):
            seen.append((self.name, str(path)))
            return path + f".{self.name}"

    chained = plan.then(_Recording(name="one"), _Recording(name="two"))
    chained = chained | _Recording(name="three")

    def fake_merge(video_path, audio_path, output_path, *, container):
        Path(output_path).write_bytes(b"x")
        return Path(output_path)

    with mock.patch("pyt.api.combined.SabrSession", return_value=fake_session), \
         mock.patch("pyt.api.combined.run_ffmpeg_merge", side_effect=fake_merge):
        result = chained.run()

    assert [name for name, _ in seen] == ["one", "two", "three"]
    assert result == Path(str(tmp_path / "out.mkv") + ".one.two.three")


def test_run_ffmpeg_failure_raises_download_error(cipher_signature, tmp_path):
    from pyt.api.errors import DownloadError

    video, v_stream, a_stream, plan = _build_combined(
        cipher_signature, tmp_path, video_size=2, audio_size=2
    )
    video.legacy.stream_monostate.sabr_url = "https://sabr.example/play"

    fake_session = mock.MagicMock()
    fake_session.iter_chunks.return_value = iter([
        (v_stream.itag, b"VV"),
        (a_stream.itag, b"AA"),
    ])

    with mock.patch("pyt.api.combined.SabrSession", return_value=fake_session), \
         mock.patch(
             "pyt.api.combined.run_ffmpeg_merge",
             side_effect=FFmpegMergeError(1, "boom"),
         ):
        with pytest.raises(DownloadError, match="ffmpeg merge failed"):
            plan.run()

    # On merge failure the .part files are left on disk for the user.
    parts = list(tmp_path.glob("*.part"))
    assert len(parts) == 2


def test_run_ffmpeg_missing_raises_download_error(cipher_signature, tmp_path):
    from pyt.api.errors import DownloadError

    video, v_stream, a_stream, plan = _build_combined(
        cipher_signature, tmp_path, video_size=2, audio_size=2
    )
    video.legacy.stream_monostate.sabr_url = "https://sabr.example/play"

    fake_session = mock.MagicMock()
    fake_session.iter_chunks.return_value = iter([
        (v_stream.itag, b"VV"),
        (a_stream.itag, b"AA"),
    ])

    with mock.patch("pyt.api.combined.SabrSession", return_value=fake_session), \
         mock.patch(
             "pyt.api.combined.run_ffmpeg_merge",
             side_effect=FFmpegNotFound("not on PATH"),
         ):
        with pytest.raises(DownloadError, match="not on PATH"):
            plan.run()


def test_progress_callback_invoked_for_both_formats(cipher_signature, tmp_path):
    video, v_stream, a_stream, plan = _build_combined(
        cipher_signature, tmp_path, video_size=5, audio_size=4
    )
    video.legacy.stream_monostate.sabr_url = "https://sabr.example/play"

    progress_events = []
    video.legacy.stream_monostate.on_progress = (
        lambda stream, chunk, remaining: progress_events.append(
            (stream.itag, len(chunk), remaining)
        )
    )

    fake_session = mock.MagicMock()
    fake_session.iter_chunks.return_value = iter([
        (v_stream.itag, b"VVVVV"),
        (a_stream.itag, b"AAAA"),
    ])

    def fake_merge(video_path, audio_path, output_path, *, container):
        Path(output_path).write_bytes(b"x")
        return Path(output_path)

    with mock.patch("pyt.api.combined.SabrSession", return_value=fake_session), \
         mock.patch("pyt.api.combined.run_ffmpeg_merge", side_effect=fake_merge):
        plan.run()

    itags_seen = {ev[0] for ev in progress_events}
    assert v_stream.itag in itags_seen
    assert a_stream.itag in itags_seen
    # Final remaining for each format is 0.
    last_v = [ev for ev in progress_events if ev[0] == v_stream.itag][-1]
    last_a = [ev for ev in progress_events if ev[0] == a_stream.itag][-1]
    assert last_v[2] == 0
    assert last_a[2] == 0
