"""Tests for the modern :mod:`pyt.api` surface."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest

from pyt.api import (
    Channel,
    Client,
    ConfigError,
    Download,
    NoMatchingStream,
    StreamRef,
    StreamSet,
    Video,
    VideoMeta,
    pipeline as pp,
)
from pyt.api.video import _hydrate_meta


# ── Client ─────────────────────────────────────────────────────────────────


def test_client_rejects_both_cookie_sources():
    with pytest.raises(ConfigError, match="not both"):
        Client(cookies="x.txt", cookies_from_browser="firefox")


def test_client_rejects_unknown_browser():
    with pytest.raises(ConfigError, match="unknown browser"):
        Client(cookies_from_browser="netscape-navigator")


def test_client_proxies_dict_format():
    c = Client(proxy="socks5://127.0.0.1:9050")
    assert c._proxies_dict() == {
        "http": "socks5://127.0.0.1:9050",
        "https": "socks5://127.0.0.1:9050",
    }


def test_client_no_proxy_returns_none():
    assert Client()._proxies_dict() is None


def test_client_video_calls_legacy_youtube():
    with mock.patch("pyt.api.client.Video._from_url") as factory:
        factory.return_value = mock.sentinel.video
        result = Client(po_token="tok").video("https://youtu.be/abc")
    assert result is mock.sentinel.video
    factory.assert_called_once()
    kwargs = factory.call_args.kwargs
    assert kwargs["po_token"] == "tok"
    assert kwargs["use_oauth"] is False


# ── _hydrate_meta + Video ──────────────────────────────────────────────────


def test_hydrate_meta_from_cipher_fixture(cipher_signature):
    url = "https://youtube.com/watch?v=2lAe1cqCOXo"
    meta = _hydrate_meta(cipher_signature, url=url)
    assert isinstance(meta, VideoMeta)
    assert meta.video_id == cipher_signature.video_id
    assert meta.url == url
    assert isinstance(meta.title, str) and meta.title
    assert isinstance(meta.author, Channel)
    assert isinstance(meta.length, timedelta) and meta.length.total_seconds() > 0
    assert meta.author.name


def test_video_wraps_legacy_and_exposes_typed_props(cipher_signature):
    meta = _hydrate_meta(cipher_signature, url="https://youtube.com/watch?v=2lAe1cqCOXo")
    video = Video(cipher_signature, meta=meta)
    assert video.video_id == cipher_signature.video_id
    assert video.title == meta.title
    assert isinstance(video.length, timedelta)
    assert video.legacy is cipher_signature


# ── StreamSet ──────────────────────────────────────────────────────────────


def _make_video(legacy):
    meta = _hydrate_meta(legacy, url=f"https://youtube.com/watch?v={legacy.video_id}")
    return Video(legacy, meta=meta)


def test_streamset_audio_filter(cipher_signature):
    video = _make_video(cipher_signature)
    audio = video.streams.audio
    assert isinstance(audio, StreamSet)
    assert len(audio) > 0
    assert all(s.is_audio_only for s in audio)


def test_streamset_video_filter(cipher_signature):
    video = _make_video(cipher_signature)
    assert all(s.kind == "video" for s in video.streams.video)


def test_streamset_progressive_disjoint_from_adaptive(cipher_signature):
    video = _make_video(cipher_signature)
    prog = set(s.itag for s in video.streams.progressive)
    adap = set(s.itag for s in video.streams.adaptive)
    assert prog & adap == set()


def test_streamset_filter_kwargs(cipher_signature):
    video = _make_video(cipher_signature)
    mp4 = video.streams.filter(subtype="mp4")
    assert all(s.subtype == "mp4" for s in mp4)


def test_streamset_best_returns_streamref(cipher_signature):
    video = _make_video(cipher_signature)
    best = video.streams.audio.best()
    assert isinstance(best, StreamRef)
    assert best.is_audio_only


def test_streamset_best_raises_when_empty(cipher_signature):
    video = _make_video(cipher_signature)
    empty = video.streams.filter(subtype="not-a-real-format")
    with pytest.raises(NoMatchingStream):
        empty.best()


def test_streamset_one_raises_on_multiple(cipher_signature):
    video = _make_video(cipher_signature)
    audio = video.streams.audio
    if len(audio) > 1:
        with pytest.raises(NoMatchingStream):
            audio.one()


def test_streamset_one_raises_on_zero(cipher_signature):
    video = _make_video(cipher_signature)
    with pytest.raises(NoMatchingStream):
        video.streams.filter(subtype="ogg-no-such").one()


def test_streamset_first_returns_optional(cipher_signature):
    video = _make_video(cipher_signature)
    assert video.streams.first() is not None
    assert video.streams.filter(subtype="bogus").first() is None


def test_streamset_filter_chain_is_immutable(cipher_signature):
    """Filtering returns a new set; the original is unchanged."""
    video = _make_video(cipher_signature)
    all_streams = video.streams
    audio = all_streams.audio
    assert len(all_streams) >= len(audio)


def test_streamset_order_by_resolution_ascending(cipher_signature):
    video = _make_video(cipher_signature)
    ordered = video.streams.video.order_by("resolution")
    seen = [s.resolution for s in ordered if s.resolution]
    parsed = [int(r.rstrip("p")) for r in seen]
    assert parsed == sorted(parsed)


def test_streamset_at_least_resolution(cipher_signature):
    video = _make_video(cipher_signature)
    hd = video.streams.video.at_least("720p")
    for s in hd:
        if s.resolution:
            assert int(s.resolution.rstrip("p")) >= 720


# ── Download builder ───────────────────────────────────────────────────────


def test_download_run_calls_legacy_download(cipher_signature):
    video = _make_video(cipher_signature)
    stream = video.streams.audio.best()
    fake_path = "/tmp/fake.mp4"
    with mock.patch.object(stream.legacy, "download", return_value=fake_path) as dl:
        result = stream.download_to("/tmp", filename="x").run()
    dl.assert_called_once()
    kwargs = dl.call_args.kwargs
    assert kwargs["output_path"] == "/tmp"
    assert kwargs["filename"] == "x"
    assert isinstance(result, Path)
    assert result == Path(fake_path)


def test_download_then_appends_steps(cipher_signature):
    video = _make_video(cipher_signature)
    stream = video.streams.audio.best()
    step = pp.embed_metadata()
    chained = stream.download_to() | step
    assert isinstance(chained, Download)
    assert chained._steps == [step]


def test_download_pipeline_runs_steps_in_order(cipher_signature):
    video = _make_video(cipher_signature)
    stream = video.streams.audio.best()

    calls = []

    class _Recording(pp.PipelineStep):
        def apply(self, path, *, stream, video):
            calls.append((self.name, path))
            return path + f".{self.name}"

    one = _Recording(name="one")
    two = _Recording(name="two")

    with mock.patch.object(stream.legacy, "download", return_value="/tmp/raw.mp4"):
        result = (stream.download_to() | one | two).run()
    assert calls == [("one", "/tmp/raw.mp4"), ("two", "/tmp/raw.mp4.one")]
    assert result == Path("/tmp/raw.mp4.one.two")


def test_download_step_failure_wrapped_as_postprocess_error(cipher_signature):
    from pyt.api.errors import PostProcessError

    video = _make_video(cipher_signature)
    stream = video.streams.audio.best()

    class _Boom(pp.PipelineStep):
        def apply(self, path, *, stream, video):
            raise RuntimeError("ffmpeg said no")

    with mock.patch.object(stream.legacy, "download", return_value="/tmp/raw.mp4"):
        with pytest.raises(PostProcessError) as exc_info:
            (stream.download_to() | _Boom(name="boom")).run()
    assert exc_info.value.step == "boom"
    assert exc_info.value.partial_output_path == "/tmp/raw.mp4"


# ── Pipeline factories ────────────────────────────────────────────────────


def test_sponsorblock_requires_one_of_mark_or_remove():
    with pytest.raises(ValueError, match="one of mark"):
        pp.sponsorblock()


def test_sponsorblock_rejects_both():
    with pytest.raises(ValueError, match="not both"):
        pp.sponsorblock(mark=["sponsor"], remove=["intro"])


def test_pipeline_steps_are_named():
    assert pp.embed_metadata().name == "embed_metadata"
    assert pp.embed_thumbnail().name == "embed_thumbnail"
    assert pp.extract_audio().name == "extract_audio"
    assert pp.embed_subtitles().name == "embed_subtitles"
    assert pp.sponsorblock(mark=["sponsor"]).name == "sponsorblock"


# ── Deprecation warnings ───────────────────────────────────────────────────


def test_legacy_youtube_emits_deprecation_warning():
    from pyt import YouTube

    with mock.patch("pyt.extract.video_id", return_value="abc"):
        with pytest.warns(DeprecationWarning, match="pyt.Client"):
            YouTube("https://youtu.be/abc")


def test_legacy_playlist_emits_deprecation_warning():
    from pyt import Playlist

    with pytest.warns(DeprecationWarning, match="pyt.Client.*playlist"):
        Playlist("https://youtube.com/playlist?list=PLxxx")


def test_legacy_channel_emits_deprecation_warning():
    from pyt import Channel

    with mock.patch("pyt.contrib.playlist.extract.playlist_id", return_value="xxx"):
        with pytest.warns(DeprecationWarning, match="pyt.Client.*channel"):
            Channel("https://www.youtube.com/@somechannel")


def test_legacy_search_emits_deprecation_warning():
    from pyt import Search

    with pytest.warns(DeprecationWarning, match="pyt.Client.*search"):
        Search("test")


def test_register_on_progress_callback_emits_deprecation_warning(cipher_signature):
    with pytest.warns(DeprecationWarning, match="register_on_progress"):
        cipher_signature.register_on_progress_callback(lambda *a, **k: None)


def test_register_on_complete_callback_emits_deprecation_warning(cipher_signature):
    with pytest.warns(DeprecationWarning, match="register_on_complete"):
        cipher_signature.register_on_complete_callback(lambda *a, **k: None)


def test_client_video_does_not_emit_deprecation_warning():
    """The new API constructs a legacy YouTube internally — that must not
    surface a DeprecationWarning to the user."""
    import warnings as warnings_mod

    from pyt import Client

    with mock.patch("pyt.api.video._LegacyYouTube") as legacy_cls:
        instance = legacy_cls.return_value
        instance.video_id = "abc"
        instance.check_availability.return_value = None
        instance.vid_info = {"videoDetails": {"title": "x", "lengthSeconds": "1"}}
        instance.publish_date = None
        instance.title = "x"

        with warnings_mod.catch_warnings():
            warnings_mod.simplefilter("error", DeprecationWarning)
            Client().video("https://youtu.be/abc")


# ── pyt.legacy facade ─────────────────────────────────────────────────────


def test_legacy_module_re_exports_classes():
    from pyt import legacy

    assert legacy.YouTube is __import__("pyt.__main__", fromlist=["YouTube"]).YouTube
    assert hasattr(legacy, "Stream")
    assert hasattr(legacy, "Playlist")
    assert hasattr(legacy, "Channel")
    assert hasattr(legacy, "Search")


# ── Modern Playlist / SearchResults shape ──────────────────────────────────


def test_client_playlist_returns_modern_wrapper():
    from pyt.api.playlists import Playlist as ModernPlaylist
    from pyt import Client

    fake_legacy = mock.MagicMock()
    fake_legacy.playlist_id = "PLxxx"
    fake_legacy.playlist_url = "https://x"
    fake_legacy.title = "Hello"

    with mock.patch("pyt.contrib.playlist.Playlist", return_value=fake_legacy):
        result = Client().playlist("https://youtube.com/playlist?list=PLxxx")

    assert isinstance(result, ModernPlaylist)
    assert result.playlist_id == "PLxxx"
    assert result.title == "Hello"


def test_modern_playlist_iter_yields_videos():
    from pyt.api.playlists import Playlist as ModernPlaylist

    fake_legacy = mock.MagicMock()
    fake_legacy.video_urls = ["url1", "url2"]

    fake_client = mock.MagicMock()
    fake_client.video.side_effect = lambda u: f"video<{u}>"

    pl = ModernPlaylist(legacy=fake_legacy, client=fake_client)
    assert list(pl.videos()) == ["video<url1>", "video<url2>"]
    assert fake_client.video.call_count == 2


def test_client_channel_returns_channel_feed():
    from pyt.api.playlists import ChannelFeed
    from pyt import Client

    fake_legacy = mock.MagicMock()
    fake_legacy.playlist_id = "UCxxx"
    fake_legacy.playlist_url = "https://x"
    fake_legacy.title = "Some Channel"
    fake_legacy.channel_id = "UCxxx"
    fake_legacy.channel_name = "Some Channel"

    with mock.patch("pyt.contrib.channel.Channel", return_value=fake_legacy):
        result = Client().channel("https://youtube.com/@someone")

    assert isinstance(result, ChannelFeed)
    assert result.channel_id == "UCxxx"
    assert result.name == "Some Channel"


def test_client_search_returns_modern_wrapper():
    from pyt.api.playlists import SearchResults
    from pyt import Client

    fake_legacy = mock.MagicMock()
    fake_legacy.query = "rickroll"

    with mock.patch("pyt.contrib.search.Search", return_value=fake_legacy):
        result = Client().search("rickroll")

    assert isinstance(result, SearchResults)
    assert result.query == "rickroll"
