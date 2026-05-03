# Thumbnail Embedding

Embed the video thumbnail as cover art so it displays in media players, file explorers, and music apps.

Equivalent to yt-dlp's `--embed-thumbnail`.

## Requirements

ffmpeg must be on `PATH`. For MP3 files, install mutagen for APIC frame support:

```bash
pip install pyt[metadata]
```

## CLI Usage

```bash
pyt <url> --embed-thumbnail

# Common combination: audio with cover art and metadata
pyt <url> -x --audio-format mp3 --embed-thumbnail --embed-metadata
```

## Container Support

| Format | Method |
|---|---|
| MP4, M4A, MOV | ffmpeg attached picture (`-disposition:v:1 attached_pic`) |
| OGG, Opus, FLAC | ffmpeg metadata stream |
| MP3 | mutagen APIC frame (requires `pyt[metadata]`), else ffmpeg |

## Python API

```python
from pyt import YouTube
from pyt.postprocessors import EmbedThumbnailPostProcessor

yt = YouTube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
stream = yt.streams.filter(only_audio=True).order_by("abr").last()
path = stream.download()

pp = EmbedThumbnailPostProcessor()
path = pp.run(path, stream, yt)
```

## How It Works

1. The highest-resolution thumbnail is downloaded to a temp JPEG file
2. ffmpeg muxes it into the video/audio container with `-codec copy` (no re-encoding for most formats)
3. The temp thumbnail file is cleaned up
