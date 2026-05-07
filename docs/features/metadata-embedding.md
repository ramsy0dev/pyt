# Metadata Embedding

Embed video metadata (title, artist, date, description) into downloaded files so they display correctly in media players and music libraries.

Equivalent to yt-dlp's `--embed-metadata`.

## Requirements

ffmpeg must be on `PATH`. `mutagen` (used for richer MP3 ID3 tags) ships as
a base dependency — no extra install step.

## CLI Usage

```bash
# Embed metadata into downloaded file
pyt <url> --embed-metadata

# Combine with other post-processing
pyt <url> -x --audio-format mp3 --embed-metadata --embed-thumbnail
```

## Embedded Fields

| Field | Source | ffmpeg tag |
|---|---|---|
| Title | `youtube.title` | `title` |
| Artist | `youtube.author` | `artist` |
| Date | `youtube.publish_date` | `date` (YYYYMMDD) |
| Description | `youtube.description` (first 500 chars) | `comment` |

## Container Support

| Format | Method |
|---|---|
| MP4, M4A, MOV | ffmpeg `-metadata` + `-codec copy` |
| WebM, OGG, FLAC, Opus | ffmpeg `-metadata` + `-codec copy` |
| MP3 | mutagen ID3 (TIT2, TPE1, TDRC, COMM) or ffmpeg fallback |

## Python API

```python
from pyt import YouTube
from pyt.postprocessors import FFmpegMetadataEmbedder

yt = YouTube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
stream = yt.streams.filter(only_audio=True).order_by("abr").last()
path = stream.download()

embedder = FFmpegMetadataEmbedder()
path = embedder.run(path, stream, yt)
```
