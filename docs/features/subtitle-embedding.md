# Subtitle Embedding

Embed subtitle tracks directly into video files so they are always available without separate `.srt` files.

Equivalent to yt-dlp's `--embed-subs`.

## Requirements

ffmpeg must be on `PATH`.

## CLI Usage

```bash
# Download video and embed English subtitles
pyt <url> -c en --embed-subs

# Download with ffmpeg merge and embed subtitles
pyt <url> -f --embed-subs -c en

# List available subtitle codes first
pyt <url> --list-captions
```

## Container Support

| Format | Subtitle codec |
|---|---|
| MP4, M4A | mov_text |
| MKV | SRT |
| WebM | WebVTT |

## Language Codes

Use the language code shown by `--list-captions`. Auto-generated captions have an `a.` prefix (e.g., `a.en`). pyt tries both `en` and `a.en` automatically.

Common codes: `en` (English), `es` (Spanish), `fr` (French), `de` (German), `ja` (Japanese), `ko` (Korean), `pt` (Portuguese), `zh-Hans` (Simplified Chinese).

## Python API

```python
from pyt import YouTube
from pyt.postprocessors import EmbedSubtitlePostProcessor

yt = YouTube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
stream = yt.streams.filter(progressive=False, subtype="mp4").order_by("resolution").last()
path = stream.download()

pp = EmbedSubtitlePostProcessor(lang_code="en")
path = pp.run(path, stream, yt)
```

## How It Works

1. The caption is downloaded as SRT to a temp file via `caption.generate_srt_captions()`
2. ffmpeg muxes it in with `-c copy -c:s <codec>` (no re-encoding of audio/video)
3. The language metadata tag is set on the subtitle stream
4. The temp SRT file is deleted
