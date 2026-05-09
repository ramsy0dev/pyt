# Video Upscaling (experimental)

> **Experimental.** API and defaults may change between releases. The
> first call emits a `FutureWarning`.

`pp.upscale(...)` runs the downloaded video through one of two
upscalers. Pick `algorithm=` based on your hardware.

| | `algorithm="lanczos"` (default) | `algorithm="realesrgan"` |
|---|---|---|
| Method | ffmpeg's Lanczos resize + light unsharp pass | Real-ESRGAN neural network |
| Adds detail? | No (cleaner interpolation) | Yes (model-hallucinated) |
| Speed | Real-time on any CPU | GPU-bound; ~1 hour per minute of 720p without a GPU |
| Peak disk (5-min 720p × 4×) | A few hundred MB (single ffmpeg pass) | ~6 GB chunked (default), ~45 GB unchunked |
| Extra install | None (ffmpeg already required) | `realesrgan-ncnn-vulkan` binary on `PATH` |
| Best at | 2× (360→720, 720→1440) | 4× when you have the hardware |

## Lanczos (default)

Single ffmpeg invocation: `scale=iw*N:ih*N:flags=lanczos` followed by
a conservative `unsharp` pass to recover the edge sharpness Lanczos
blurs. Real-time on any modern CPU; no extra installs.

```python
from pyt import Client, pipeline as pp

video = Client().video(url)
path = (
    video.download_best("downloads/", prefer_resolution="720p")
        | pp.upscale(scale=2)
).run()
```

**Lanczos arguments:**

| Argument | Default | Notes |
|---|---|---|
| `scale` | `2` | 2, 3, or 4 |
| `crf` | `18` | x264 CRF for the re-encode (lower = larger / higher quality) |
| `preset` | `"medium"` | x264 speed/efficiency preset; `"slow"` trades CPU for ~10% smaller output |
| `sharpen` | `0.4` | unsharp amount, 0.0–1.5; `0` disables the sharpen pass |

## Real-ESRGAN (opt-in)

Neural-net super-resolution that recovers detail (within reason).
Install the binary **and models** with a single command:

```bash
pyt --doctor --install realesrgan
```

This downloads the `xinntao/Real-ESRGAN` release bundle, which packages
the `realesrgan-ncnn-vulkan` binary together with the model files
(`realesrgan-x4plus.bin/.param`, etc.) in one zip. After install the
models live at `~/.pyt/bin/models/` and pyt passes `-m ~/.pyt/bin/models`
to the binary automatically, so inference works regardless of the
current working directory.

Or download manually from
[xinntao/Real-ESRGAN releases](https://github.com/xinntao/Real-ESRGAN/releases)
and put the binary **and** its `models/` directory on `PATH` / in the
same directory.

```python
path = (
    video.download_best("downloads/", prefer_resolution="720p")
        | pp.upscale(scale=4, algorithm="realesrgan")
        | pp.embed_metadata()
).run()
```

The pipeline processes the video in **N-second chunks** (default 30s)
so peak disk usage is bounded by chunk size, not video length:

1. Extract one chunk's frames as PNG
2. Upscale them with Real-ESRGAN
3. Re-encode that chunk to a small mp4
4. Drop both PNG dirs
5. (After all chunks) ffmpeg concat (no re-encode) + remux original audio

Concrete numbers for a 5-minute 720p × 4× upscale:

| | Default chunked (30s) | Unchunked (`chunk_seconds=0`) |
|---|---|---|
| Peak intermediate disk | **~6 GB** | ~45 GB |
| Wall-clock | GPU-bound (chunking doesn't speed inference) | GPU-bound |
| Final output size | identical | identical |

Wall-clock is dominated by per-frame inference, which is GPU-bound.
Without a GPU, Real-ESRGAN is effectively unusable on anything longer
than a few minutes regardless of chunk size — use lanczos instead.

**Real-ESRGAN arguments:**

| Argument | Default | Notes |
|---|---|---|
| `scale` | `2` (set `4` for native ratio) | 2, 3, or 4 |
| `model` | `"realesrgan-x4plus"` | also `realesrgan-x4plus-anime`, `realesr-animevideov3` |
| `binary` | auto-detected on `PATH` | explicit path override |
| `tile_size` | `0` (auto) | lower (e.g. 64, 128) if you hit GPU memory errors |
| `chunk_seconds` | `30` | size of each processing window in seconds; `0` disables chunking |
| `threads` | `None` (binary picks `1:2:2`) | passes through to `realesrgan-ncnn-vulkan -j load:proc:save` — try `"1:4:1"` or `"1:8:2"` if your GPU has spare memory |
| `keep_intermediate` | `False` | keep extracted PNG frames for debugging |

## Error handling

Subprocess failures (ffmpeg, ffprobe, realesrgan-ncnn-vulkan) translate
to `PostProcessError` with the failing command's stderr inlined:

```python
from pyt.api.errors import PostProcessError

try:
    (video.download_best("./") | pp.upscale(scale=2)).run()
except PostProcessError as exc:
    print(f"Step '{exc.step}' failed: {exc}")
    print(f"Partial output kept at: {exc.partial_output_path}")
```

If the upscale fails partway through, the original source bytes are
restored from a `.pre-upscale` backup — you never lose your input
file even if the GPU runs out of memory mid-frame.

## Silencing the experimental warning

The first call emits a `FutureWarning`:

```
FutureWarning: pyt.pipeline.upscale is experimental: API and defaults
may change, and output quality varies by algorithm and source content.
See README.
```

Filter it once you've read this page:

```python
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module=r"pyt\..*")
```
