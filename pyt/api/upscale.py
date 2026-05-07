"""Experimental video upscaling post-processor.

Two algorithms, picked by ``algorithm=`` on :func:`pyt.api.pipeline.upscale`:

``"lanczos"`` (default)
    Pure ffmpeg: ``scale`` filter with the Lanczos resampler followed
    by a conservative ``unsharp`` pass to compensate for Lanczos's
    natural edge softening. Single ffmpeg invocation — no frame
    extraction, no temp-dir explosion. Real-time or faster on any
    modern CPU. **No extra install.** Best at 2× (360→720, 720→1440);
    quality drops above that. Doesn't add detail the source doesn't
    have, but produces a noticeably cleaner result than naive bilinear
    or YouTube's player upscaling.

``"realesrgan"``
    `Real-ESRGAN <https://github.com/xinntao/Real-ESRGAN>`_ via the
    standalone ``realesrgan-ncnn-vulkan`` binary. Actual neural-net
    detail recovery; native 4× ratio. **Heavy.** A 5-minute 720p clip
    can use 20–30 GB of intermediate disk and 1–2 hours of CPU time
    without a GPU. Pipeline: ffmpeg extracts PNG frames → Real-ESRGAN
    upscales each → ffmpeg recombines with original audio.

The whole feature is experimental and emits a one-shot
:class:`FutureWarning` on first use. API and defaults may change.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess  # nosec — argv is fully constructed by us
import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from pyt.api.errors import PostProcessError
from pyt.api.pipeline import PipelineStep

if TYPE_CHECKING:
    from pyt.api.streams import StreamRef
    from pyt.api.video import Video


logger = logging.getLogger(__name__)

_EXPERIMENTAL_NOTICE_FIRED = False
_VALID_ALGORITHMS = ("lanczos", "realesrgan")


def _emit_experimental_warning_once() -> None:
    global _EXPERIMENTAL_NOTICE_FIRED
    if _EXPERIMENTAL_NOTICE_FIRED:
        return
    _EXPERIMENTAL_NOTICE_FIRED = True
    warnings.warn(
        "pyt.pipeline.upscale is experimental: API and defaults may change, "
        "and output quality varies by algorithm and source content. See README.",
        FutureWarning,
        stacklevel=4,
    )


# Algorithm-specific defaults / metadata.
_REALESRGAN_BINARY = "realesrgan-ncnn-vulkan"
_REALESRGAN_KNOWN_MODELS = {
    "realesrgan-x4plus",
    "realesrgan-x4plus-anime",
    "realesr-animevideov3",
    "realesrnet-x4plus",
}


@dataclass(frozen=True)
class _Upscale(PipelineStep):
    """Internal pipeline step. Constructed by
    :func:`pyt.api.pipeline.upscale`; not meant to be instantiated directly."""

    algorithm: str = "lanczos"
    scale: int = 2

    # ── lanczos kwargs ─────────────────────────────────────────────────────
    crf: int = 18                 # x264 CRF for the re-encode
    preset: str = "medium"        # x264 speed/efficiency preset
    sharpen: float = 0.4          # unsharp amount; 0 disables the sharpen pass

    # ── realesrgan kwargs ──────────────────────────────────────────────────
    model: str = "realesrgan-x4plus"
    binary: Optional[str] = None
    tile_size: int = 0            # 0 = auto. Lower if GPU OOMs.
    keep_intermediate: bool = False

    def apply(self, path: str, *, stream: "StreamRef", video: "Video") -> str:
        _emit_experimental_warning_once()
        if self.algorithm == "lanczos":
            return _run_lanczos(
                input_path=Path(path),
                scale=self.scale,
                crf=self.crf,
                preset=self.preset,
                sharpen=self.sharpen,
            )
        if self.algorithm == "realesrgan":
            return _run_realesrgan(
                input_path=Path(path),
                scale=self.scale,
                model=self.model,
                binary_override=self.binary,
                tile_size=self.tile_size,
                keep_intermediate=self.keep_intermediate,
            )
        raise PostProcessError(
            f"upscale: unknown algorithm {self.algorithm!r} "
            f"(choose from {sorted(_VALID_ALGORITHMS)})",
            step="upscale",
            partial_output_path=path,
        )


# ── shared helpers ────────────────────────────────────────────────────────


def _check_input(input_path: Path, scale: int, allowed_scales=(2, 3, 4)) -> None:
    if scale not in allowed_scales:
        raise PostProcessError(
            f"upscale: scale must be one of {allowed_scales} (got {scale!r})",
            step="upscale",
            partial_output_path=str(input_path),
        )
    if not input_path.is_file():
        raise PostProcessError(
            f"upscale: input file not found: {input_path}",
            step="upscale",
        )


def _atomic_swap(input_path: Path, new_file: Path) -> None:
    """Replace *input_path* with *new_file* via a .pre-upscale backup.

    On any os.replace failure we roll the backup back so the user's
    original bytes survive.
    """
    backup = input_path.with_suffix(input_path.suffix + ".pre-upscale")
    os.replace(input_path, backup)
    try:
        os.replace(new_file, input_path)
    except OSError:
        os.replace(backup, input_path)
        raise
    backup.unlink(missing_ok=True)


def _translate_subprocess_failure(exc: subprocess.CalledProcessError, partial: Path) -> None:
    stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
    raise PostProcessError(
        f"upscale: external command failed ({exc.cmd[0]}): "
        f"exit {exc.returncode}\n{stderr.strip()[:600]}",
        step="upscale",
        partial_output_path=str(partial),
        cause=exc,
    ) from exc


# ── lanczos algorithm ─────────────────────────────────────────────────────


def _run_lanczos(
    *,
    input_path: Path,
    scale: int,
    crf: int,
    preset: str,
    sharpen: float,
) -> str:
    _check_input(input_path, scale, allowed_scales=(2, 3, 4))
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise PostProcessError(
            "ffmpeg not found on PATH (required for lanczos upscaling)",
            step="upscale",
            partial_output_path=str(input_path),
        )

    # Build the ffmpeg filter chain. Lanczos for the resize, optional
    # unsharp pass to recover the edge sharpness lanczos blurs.
    filters = [f"scale=iw*{scale}:ih*{scale}:flags=lanczos"]
    if sharpen > 0:
        # unsharp luma_msize_x:luma_msize_y:luma_amount:chroma_msize_x:chroma_msize_y:chroma_amount
        # Conservative defaults — the goal is "less soft", not "looks fake".
        filters.append(f"unsharp=5:5:{sharpen:.2f}:3:3:{(sharpen * 0.5):.2f}")
    vf = ",".join(filters)

    workdir = Path(tempfile.mkdtemp(prefix="pyt-upscale-", dir=str(input_path.parent)))
    output_tmp = workdir / f"out{input_path.suffix}"
    try:
        cmd = [
            ffmpeg, "-y",
            "-loglevel", "error",
            "-i", str(input_path),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(output_tmp),
        ]
        logger.debug("upscale[lanczos]: %s", " ".join(cmd))
        try:
            subprocess.run(cmd, capture_output=True, check=True)  # nosec
        except subprocess.CalledProcessError as exc:
            _translate_subprocess_failure(exc, input_path)

        _atomic_swap(input_path, output_tmp)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    return str(input_path)


# ── realesrgan algorithm ──────────────────────────────────────────────────


def _run_realesrgan(
    *,
    input_path: Path,
    scale: int,
    model: str,
    binary_override: Optional[str],
    tile_size: int,
    keep_intermediate: bool,
) -> str:
    _check_input(input_path, scale, allowed_scales=(2, 3, 4))

    binary = binary_override or shutil.which(_REALESRGAN_BINARY)
    if not binary:
        raise PostProcessError(
            "realesrgan-ncnn-vulkan not found on PATH. "
            "Install from https://github.com/xinntao/Real-ESRGAN/releases "
            "and ensure the binary is on PATH (or pass binary=...).",
            step="upscale",
            partial_output_path=str(input_path),
        )
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise PostProcessError(
            "ffmpeg not found on PATH (required to extract / recombine frames)",
            step="upscale",
            partial_output_path=str(input_path),
        )

    if model not in _REALESRGAN_KNOWN_MODELS:
        # Don't hard-error — Real-ESRGAN ships with a model registry the user
        # can extend. Just warn so the typo'd-model case is loud.
        logger.warning(
            "upscale[realesrgan]: model %r not in known set %s; passing through verbatim",
            model, sorted(_REALESRGAN_KNOWN_MODELS),
        )

    fps = _probe_fps(input_path) or 30.0
    has_audio = _probe_has_audio(input_path)

    workdir = Path(tempfile.mkdtemp(prefix="pyt-upscale-", dir=str(input_path.parent)))
    frames_dir = workdir / "frames"
    upscaled_dir = workdir / "upscaled"
    frames_dir.mkdir()
    upscaled_dir.mkdir()
    output_tmp = workdir / f"out{input_path.suffix}"

    try:
        try:
            _extract_frames(ffmpeg, input_path, frames_dir)
            _upscale_frames_realesrgan(
                binary, frames_dir, upscaled_dir,
                model=model, scale=scale, tile_size=tile_size,
            )
            _recombine(
                ffmpeg,
                frames_dir=upscaled_dir,
                audio_source=input_path if has_audio else None,
                output=output_tmp,
                fps=fps,
            )
        except subprocess.CalledProcessError as exc:
            _translate_subprocess_failure(exc, input_path)

        _atomic_swap(input_path, output_tmp)
    finally:
        if not keep_intermediate:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            logger.info("upscale[realesrgan]: kept intermediates at %s", workdir)

    return str(input_path)


def _extract_frames(ffmpeg: str, source: Path, target_dir: Path) -> None:
    cmd = [
        ffmpeg, "-y",
        "-loglevel", "error",
        "-i", str(source),
        # PNG to avoid recompression artifacts going into the upscaler.
        str(target_dir / "frame_%08d.png"),
    ]
    logger.debug("upscale: extracting frames -> %s", target_dir)
    subprocess.run(cmd, capture_output=True, check=True)  # nosec


def _upscale_frames_realesrgan(
    binary: str,
    source_dir: Path,
    target_dir: Path,
    *,
    model: str,
    scale: int,
    tile_size: int,
) -> None:
    cmd: List[str] = [
        binary,
        "-i", str(source_dir),
        "-o", str(target_dir),
        "-n", model,
        "-s", str(scale),
        "-f", "png",
    ]
    if tile_size:
        cmd += ["-t", str(tile_size)]
    logger.debug("upscale[realesrgan]: %s", " ".join(cmd))
    subprocess.run(cmd, capture_output=True, check=True)  # nosec


def _recombine(
    ffmpeg: str,
    *,
    frames_dir: Path,
    audio_source: Optional[Path],
    output: Path,
    fps: float,
) -> None:
    cmd: List[str] = [
        ffmpeg, "-y",
        "-loglevel", "error",
        "-framerate", f"{fps:.6f}",
        "-i", str(frames_dir / "frame_%08d.png"),
    ]
    if audio_source is not None:
        cmd += ["-i", str(audio_source), "-map", "0:v:0", "-map", "1:a:0", "-c:a", "copy"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(output)]
    logger.debug("upscale: recombining -> %s", output)
    subprocess.run(cmd, capture_output=True, check=True)  # nosec


# ── ffprobe helpers ───────────────────────────────────────────────────────


def _probe_fps(path: Path) -> Optional[float]:
    """Return the video stream's FPS via ffprobe, or None if unavailable.
    ffprobe ships with ffmpeg, so if ffmpeg is on PATH this usually is too.
    """
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(  # nosec
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=avg_frame_rate",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            check=True,
            timeout=15,
        )
        data = json.loads(result.stdout.decode("utf-8") or "{}")
        rate = (data.get("streams") or [{}])[0].get("avg_frame_rate", "")
        if "/" in rate:
            num, den = rate.split("/", 1)
            num_f, den_f = float(num), float(den)
            if den_f > 0:
                return num_f / den_f
        elif rate:
            return float(rate)
    except (subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        logger.debug("upscale: ffprobe fps lookup failed (%s)", exc)
    return None


def _probe_has_audio(path: Path) -> bool:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return True  # assume yes — recombine fails loudly if it isn't
    try:
        result = subprocess.run(  # nosec
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True,
            check=True,
            timeout=15,
        )
        return bool(result.stdout.strip())
    except subprocess.SubprocessError as exc:
        logger.debug("upscale: ffprobe audio detection failed (%s)", exc)
        return True
