"""Tests for the experimental upscale post-processor.

We don't run real ffmpeg or the realesrgan binary — both are external
dependencies. The tests mock subprocess and verify orchestration:
algorithm dispatch, argv shape, file movement, error translation, and
the FutureWarning."""
from __future__ import annotations

import json
import subprocess
import warnings
from pathlib import Path
from unittest import mock

import pytest

from pyt.api import pipeline as pp
from pyt.api.errors import PostProcessError
from pyt.api.upscale import (
    _REALESRGAN_KNOWN_MODELS,
    _VALID_ALGORITHMS,
    _Upscale,
    _probe_fps,
    _probe_has_audio,
    _run_lanczos,
    _run_realesrgan,
)
import pyt.api.upscale as upscale_mod


@pytest.fixture(autouse=True)
def _reset_warning_flag():
    """Make the once-per-process FutureWarning fire fresh per test."""
    upscale_mod._EXPERIMENTAL_NOTICE_FIRED = False
    yield


# ── factory ──────────────────────────────────────────────────────────────


def test_default_algorithm_is_lanczos():
    """The typical user gets the algorithm that runs without a GPU.
    Don't change this default without thinking hard about it."""
    step = pp.upscale()
    assert step.algorithm == "lanczos"
    assert step.scale == 2


def test_factory_accepts_realesrgan():
    step = pp.upscale(scale=4, algorithm="realesrgan")
    assert step.algorithm == "realesrgan"
    assert step.scale == 4


def test_factory_rejects_unknown_algorithm():
    with pytest.raises(ValueError, match="must be one of"):
        pp.upscale(algorithm="bicubic")


def test_factory_passes_lanczos_kwargs():
    step = pp.upscale(scale=2, crf=20, preset="slow", sharpen=0.8)
    assert step.crf == 20
    assert step.preset == "slow"
    assert step.sharpen == 0.8


def test_factory_passes_realesrgan_kwargs():
    step = pp.upscale(
        scale=4, algorithm="realesrgan",
        binary="/opt/realesrgan", tile_size=128, keep_intermediate=True,
    )
    assert step.binary == "/opt/realesrgan"
    assert step.tile_size == 128
    assert step.keep_intermediate is True


# ── dispatch ─────────────────────────────────────────────────────────────


def test_apply_dispatches_to_lanczos(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    step = _Upscale(name="upscale", algorithm="lanczos", scale=2)
    with mock.patch("pyt.api.upscale._run_lanczos", return_value=str(src)) as fake_lanczos, \
         mock.patch("pyt.api.upscale._run_realesrgan") as fake_realesrgan:
        step.apply(str(src), stream=mock.MagicMock(), video=mock.MagicMock())
    fake_lanczos.assert_called_once()
    fake_realesrgan.assert_not_called()


def test_apply_dispatches_to_realesrgan(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    step = _Upscale(name="upscale", algorithm="realesrgan", scale=4)
    with mock.patch("pyt.api.upscale._run_lanczos") as fake_lanczos, \
         mock.patch("pyt.api.upscale._run_realesrgan", return_value=str(src)) as fake_realesrgan:
        step.apply(str(src), stream=mock.MagicMock(), video=mock.MagicMock())
    fake_realesrgan.assert_called_once()
    fake_lanczos.assert_not_called()


def test_apply_unknown_algorithm_raises_postprocesserror(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    # Bypass factory validation to construct a malformed step.
    step = _Upscale(name="upscale", algorithm="nope", scale=2)
    with pytest.raises(PostProcessError, match="unknown algorithm"):
        step.apply(str(src), stream=mock.MagicMock(), video=mock.MagicMock())


# ── lanczos algorithm ────────────────────────────────────────────────────


def test_lanczos_rejects_bad_scale(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    with pytest.raises(PostProcessError, match="scale must be one of"):
        _run_lanczos(input_path=src, scale=8, crf=18, preset="medium", sharpen=0.4)


def test_lanczos_missing_input(tmp_path):
    with pytest.raises(PostProcessError, match="input file not found"):
        _run_lanczos(
            input_path=tmp_path / "missing.mp4",
            scale=2, crf=18, preset="medium", sharpen=0.4,
        )


def test_lanczos_missing_ffmpeg(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    with mock.patch("pyt.api.upscale.shutil.which", return_value=None):
        with pytest.raises(PostProcessError, match="ffmpeg not found"):
            _run_lanczos(input_path=src, scale=2, crf=18, preset="medium", sharpen=0.4)


def test_lanczos_invokes_ffmpeg_with_lanczos_filter(tmp_path):
    src = tmp_path / "video.mp4"
    src.write_bytes(b"original")

    captured_cmd = {}

    def fake_run(cmd, **kwargs):
        captured_cmd["cmd"] = cmd
        # Emulate ffmpeg writing the output file.
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"upscaled")
        return mock.Mock(returncode=0)

    with mock.patch("pyt.api.upscale.shutil.which", return_value="/usr/bin/ffmpeg"), \
         mock.patch("pyt.api.upscale.subprocess.run", side_effect=fake_run):
        result = _run_lanczos(
            input_path=src, scale=2, crf=20, preset="slow", sharpen=0.6,
        )

    assert Path(result) == src
    assert src.read_bytes() == b"upscaled"
    cmd = captured_cmd["cmd"]
    # -vf argument right after "-vf"
    vf_idx = cmd.index("-vf")
    vf = cmd[vf_idx + 1]
    assert "scale=iw*2:ih*2:flags=lanczos" in vf
    assert "unsharp=5:5:0.60:" in vf  # sharpen=0.6
    # CRF + preset propagate
    assert "20" in cmd
    assert "slow" in cmd
    # Audio is copied, not re-encoded.
    assert "-c:a" in cmd
    assert cmd[cmd.index("-c:a") + 1] == "copy"


def test_lanczos_no_sharpen_omits_unsharp_filter(tmp_path):
    src = tmp_path / "video.mp4"
    src.write_bytes(b"x")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        Path(cmd[-1]).write_bytes(b"y")
        return mock.Mock(returncode=0)

    with mock.patch("pyt.api.upscale.shutil.which", return_value="/usr/bin/ffmpeg"), \
         mock.patch("pyt.api.upscale.subprocess.run", side_effect=fake_run):
        _run_lanczos(input_path=src, scale=2, crf=18, preset="medium", sharpen=0.0)

    vf = captured["cmd"][captured["cmd"].index("-vf") + 1]
    assert "unsharp" not in vf
    assert "lanczos" in vf


def test_lanczos_subprocess_failure_restores_source(tmp_path):
    src = tmp_path / "video.mp4"
    src.write_bytes(b"original")

    err = subprocess.CalledProcessError(
        returncode=1,
        cmd=["ffmpeg"],
        output=b"",
        stderr=b"invalid filter",
    )

    with mock.patch("pyt.api.upscale.shutil.which", return_value="/usr/bin/ffmpeg"), \
         mock.patch("pyt.api.upscale.subprocess.run", side_effect=err):
        with pytest.raises(PostProcessError, match="exit 1"):
            _run_lanczos(input_path=src, scale=2, crf=18, preset="medium", sharpen=0.4)

    # Source bytes preserved on failure.
    assert src.read_bytes() == b"original"
    # Workdir cleaned up.
    assert not list(tmp_path.glob("pyt-upscale-*"))


# ── realesrgan algorithm ─────────────────────────────────────────────────


def _which_factory(*available):
    paths = {name: f"/usr/bin/{name}" for name in available}
    return lambda name: paths.get(name)


def test_realesrgan_rejects_bad_scale(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    with pytest.raises(PostProcessError, match="scale must be one of"):
        _run_realesrgan(
            input_path=src, scale=8, model="realesrgan-x4plus",
            binary_override=None, tile_size=0, keep_intermediate=False,
        )


def test_realesrgan_missing_binary(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    with mock.patch("pyt.api.upscale.shutil.which", return_value=None):
        with pytest.raises(PostProcessError, match="realesrgan-ncnn-vulkan not found"):
            _run_realesrgan(
                input_path=src, scale=4, model="realesrgan-x4plus",
                binary_override=None, tile_size=0, keep_intermediate=False,
            )


def test_realesrgan_binary_override_skips_path_lookup(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")

    def fake_which(name):
        return "/usr/bin/ffmpeg" if name == "ffmpeg" else None

    with mock.patch("pyt.api.upscale.shutil.which", side_effect=fake_which), \
         mock.patch("pyt.api.upscale._extract_frames"), \
         mock.patch("pyt.api.upscale._upscale_frames_realesrgan"), \
         mock.patch("pyt.api.upscale._recombine"), \
         mock.patch("pyt.api.upscale._probe_fps", return_value=30.0), \
         mock.patch("pyt.api.upscale._probe_has_audio", return_value=True), \
         mock.patch("pyt.api.upscale.os.replace"):
        _run_realesrgan(
            input_path=src, scale=4, model="realesrgan-x4plus",
            binary_override="/opt/upscaler/realesrgan-ncnn-vulkan",
            tile_size=0, keep_intermediate=False,
        )


def test_realesrgan_missing_ffmpeg(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    with mock.patch(
        "pyt.api.upscale.shutil.which",
        side_effect=lambda name: "/opt/realesrgan-ncnn-vulkan" if name == "realesrgan-ncnn-vulkan" else None,
    ):
        with pytest.raises(PostProcessError, match="ffmpeg not found"):
            _run_realesrgan(
                input_path=src, scale=4, model="realesrgan-x4plus",
                binary_override=None, tile_size=0, keep_intermediate=False,
            )


def test_realesrgan_full_pipeline(tmp_path):
    src = tmp_path / "video.mp4"
    src.write_bytes(b"original-bytes")

    upscale_call = {}
    recombine_call = {}

    def fake_extract(ffmpeg, source, target_dir):
        target_dir.mkdir(exist_ok=True)
        (target_dir / "frame_00000001.png").write_bytes(b"PNG")

    def fake_upscale(binary, src_dir, target_dir, *, model, scale, tile_size):
        upscale_call.update(model=model, scale=scale, tile_size=tile_size)
        target_dir.mkdir(exist_ok=True)
        (target_dir / "frame_00000001.png").write_bytes(b"PNG-up")

    def fake_recombine(ffmpeg, *, frames_dir, audio_source, output, fps):
        recombine_call.update(audio_source=audio_source, fps=fps)
        output.write_bytes(b"upscaled-bytes")

    with mock.patch("pyt.api.upscale.shutil.which",
                    side_effect=_which_factory("realesrgan-ncnn-vulkan", "ffmpeg")), \
         mock.patch("pyt.api.upscale._extract_frames", side_effect=fake_extract), \
         mock.patch("pyt.api.upscale._upscale_frames_realesrgan", side_effect=fake_upscale), \
         mock.patch("pyt.api.upscale._recombine", side_effect=fake_recombine), \
         mock.patch("pyt.api.upscale._probe_fps", return_value=29.97), \
         mock.patch("pyt.api.upscale._probe_has_audio", return_value=True):
        result = _run_realesrgan(
            input_path=src, scale=4, model="realesrgan-x4plus",
            binary_override=None, tile_size=128, keep_intermediate=False,
        )

    assert Path(result) == src
    assert src.read_bytes() == b"upscaled-bytes"
    assert not list(tmp_path.glob("pyt-upscale-*"))   # cleaned up
    assert upscale_call["scale"] == 4
    assert upscale_call["tile_size"] == 128
    assert recombine_call["fps"] == pytest.approx(29.97)
    assert recombine_call["audio_source"] == src


def test_realesrgan_no_audio_skips_audio_source(tmp_path):
    src = tmp_path / "video.mp4"
    src.write_bytes(b"x")

    captured = {}

    def fake_recombine(ffmpeg, *, frames_dir, audio_source, output, fps):
        captured["audio_source"] = audio_source
        output.write_bytes(b"y")

    with mock.patch("pyt.api.upscale.shutil.which",
                    side_effect=_which_factory("realesrgan-ncnn-vulkan", "ffmpeg")), \
         mock.patch("pyt.api.upscale._extract_frames"), \
         mock.patch("pyt.api.upscale._upscale_frames_realesrgan"), \
         mock.patch("pyt.api.upscale._recombine", side_effect=fake_recombine), \
         mock.patch("pyt.api.upscale._probe_fps", return_value=30.0), \
         mock.patch("pyt.api.upscale._probe_has_audio", return_value=False):
        _run_realesrgan(
            input_path=src, scale=4, model="realesrgan-x4plus",
            binary_override=None, tile_size=0, keep_intermediate=False,
        )

    assert captured["audio_source"] is None


def test_realesrgan_keep_intermediate_preserves_workdir(tmp_path):
    src = tmp_path / "video.mp4"
    src.write_bytes(b"x")

    def fake_recombine(ffmpeg, *, frames_dir, audio_source, output, fps):
        output.write_bytes(b"y")

    with mock.patch("pyt.api.upscale.shutil.which",
                    side_effect=_which_factory("realesrgan-ncnn-vulkan", "ffmpeg")), \
         mock.patch("pyt.api.upscale._extract_frames"), \
         mock.patch("pyt.api.upscale._upscale_frames_realesrgan"), \
         mock.patch("pyt.api.upscale._recombine", side_effect=fake_recombine), \
         mock.patch("pyt.api.upscale._probe_fps", return_value=30.0), \
         mock.patch("pyt.api.upscale._probe_has_audio", return_value=False):
        _run_realesrgan(
            input_path=src, scale=4, model="realesrgan-x4plus",
            binary_override=None, tile_size=0, keep_intermediate=True,
        )

    workdirs = list(tmp_path.glob("pyt-upscale-*"))
    assert len(workdirs) == 1


def test_realesrgan_subprocess_failure_restores_source(tmp_path):
    src = tmp_path / "video.mp4"
    src.write_bytes(b"original")

    err = subprocess.CalledProcessError(
        returncode=1,
        cmd=["realesrgan-ncnn-vulkan"],
        output=b"",
        stderr=b"VRAM allocation failed",
    )

    with mock.patch("pyt.api.upscale.shutil.which",
                    side_effect=_which_factory("realesrgan-ncnn-vulkan", "ffmpeg")), \
         mock.patch("pyt.api.upscale._extract_frames"), \
         mock.patch("pyt.api.upscale._upscale_frames_realesrgan", side_effect=err), \
         mock.patch("pyt.api.upscale._probe_fps", return_value=30.0), \
         mock.patch("pyt.api.upscale._probe_has_audio", return_value=False):
        with pytest.raises(PostProcessError) as exc_info:
            _run_realesrgan(
                input_path=src, scale=4, model="realesrgan-x4plus",
                binary_override=None, tile_size=0, keep_intermediate=False,
            )

    assert exc_info.value.step == "upscale"
    assert "exit 1" in str(exc_info.value)
    assert "VRAM allocation failed" in str(exc_info.value)
    assert src.read_bytes() == b"original"


def test_realesrgan_unknown_model_warns_but_proceeds(tmp_path, caplog):
    src = tmp_path / "video.mp4"
    src.write_bytes(b"x")

    def fake_recombine(ffmpeg, *, frames_dir, audio_source, output, fps):
        output.write_bytes(b"y")

    with caplog.at_level("WARNING", logger="pyt.api.upscale"):
        with mock.patch("pyt.api.upscale.shutil.which",
                        side_effect=_which_factory("realesrgan-ncnn-vulkan", "ffmpeg")), \
             mock.patch("pyt.api.upscale._extract_frames"), \
             mock.patch("pyt.api.upscale._upscale_frames_realesrgan"), \
             mock.patch("pyt.api.upscale._recombine", side_effect=fake_recombine), \
             mock.patch("pyt.api.upscale._probe_fps", return_value=30.0), \
             mock.patch("pyt.api.upscale._probe_has_audio", return_value=False):
            _run_realesrgan(
                input_path=src, scale=4, model="my-custom-model",
                binary_override=None, tile_size=0, keep_intermediate=False,
            )

    assert any("not in known set" in r.message for r in caplog.records)


# ── experimental warning ────────────────────────────────────────────────


def test_apply_emits_future_warning_once(tmp_path):
    src = tmp_path / "video.mp4"
    src.write_bytes(b"x")
    step = _Upscale(name="upscale", algorithm="lanczos", scale=2)

    with mock.patch("pyt.api.upscale._run_lanczos", return_value=str(src)):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", FutureWarning)
            step.apply(str(src), stream=mock.MagicMock(), video=mock.MagicMock())
            step.apply(str(src), stream=mock.MagicMock(), video=mock.MagicMock())

    future = [w for w in caught if issubclass(w.category, FutureWarning)]
    assert len(future) == 1
    assert "experimental" in str(future[0].message).lower()


# ── ffprobe helpers ─────────────────────────────────────────────────────


def test_probe_fps_parses_avg_frame_rate(tmp_path):
    fake_stdout = json.dumps({"streams": [{"avg_frame_rate": "30000/1001"}]}).encode()
    with mock.patch("pyt.api.upscale.shutil.which", return_value="/usr/bin/ffprobe"), \
         mock.patch(
             "pyt.api.upscale.subprocess.run",
             return_value=mock.Mock(stdout=fake_stdout),
         ):
        fps = _probe_fps(tmp_path / "v.mp4")
    assert fps == pytest.approx(29.97, rel=1e-3)


def test_probe_fps_returns_none_when_ffprobe_missing(tmp_path):
    with mock.patch("pyt.api.upscale.shutil.which", return_value=None):
        assert _probe_fps(tmp_path / "v.mp4") is None


def test_probe_has_audio_true(tmp_path):
    with mock.patch("pyt.api.upscale.shutil.which", return_value="/usr/bin/ffprobe"), \
         mock.patch(
             "pyt.api.upscale.subprocess.run",
             return_value=mock.Mock(stdout=b"audio\n"),
         ):
        assert _probe_has_audio(tmp_path / "v.mp4") is True


def test_probe_has_audio_false(tmp_path):
    with mock.patch("pyt.api.upscale.shutil.which", return_value="/usr/bin/ffprobe"), \
         mock.patch(
             "pyt.api.upscale.subprocess.run",
             return_value=mock.Mock(stdout=b""),
         ):
        assert _probe_has_audio(tmp_path / "v.mp4") is False


def test_probe_has_audio_assumes_yes_on_ffprobe_missing(tmp_path):
    """No ffprobe = we assume audio. Recombine fails loudly otherwise,
    which is preferable to silently dropping the audio track."""
    with mock.patch("pyt.api.upscale.shutil.which", return_value=None):
        assert _probe_has_audio(tmp_path / "v.mp4") is True


# ── registry ───────────────────────────────────────────────────────────


def test_default_realesrgan_model_in_known_set():
    assert "realesrgan-x4plus" in _REALESRGAN_KNOWN_MODELS


def test_lanczos_in_valid_algorithms():
    assert "lanczos" in _VALID_ALGORITHMS
    assert "realesrgan" in _VALID_ALGORITHMS
