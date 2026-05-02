# pytube

[![CI](https://github.com/ramsy0dev/pytube/actions/workflows/ci.yml/badge.svg)](https://github.com/ramsy0dev/pytube/actions/workflows/ci.yml)

An actively maintained fork of pytube — a lightweight, dependency-free Python library (and command-line utility) for downloading YouTube videos, updated to work with the current YouTube API.

## What's different from the original

- Multi-client fallback strategy: tries ANDROID → IOS → TV_EMBED → page HTML until a working stream source is found
- Mobile clients return pre-signed stream URLs, so signature deciphering is rarely needed
- `visitorData` token is automatically extracted from the watch page and sent with API requests
- Web client versions are read from the live page instead of hardcoded values
- All 216 tests passing on Python 3.10–3.13

## Installation

```bash
pip install git+https://github.com/ramsy0dev/pytube
```

## Quickstart

```python
from pytube import YouTube

yt = YouTube('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
print(yt.title)
print(yt.length, 'seconds')

# Download highest resolution
yt.streams.get_highest_resolution().download()

# Download audio only
yt.streams.filter(only_audio=True).first().download()

# Filter and pick
yt.streams.filter(progressive=True, file_extension='mp4') \
          .order_by('resolution') \
          .desc() \
          .first() \
          .download()
```

## CLI

```bash
# Download highest progressive quality
pytube https://www.youtube.com/watch?v=dQw4w9WgXcQ

# List available streams
pytube https://www.youtube.com/watch?v=dQw4w9WgXcQ --list

# Download by itag
pytube https://www.youtube.com/watch?v=dQw4w9WgXcQ --itag=22

# Download audio only
pytube https://www.youtube.com/watch?v=dQw4w9WgXcQ -a

# Download a playlist
pytube https://www.youtube.com/playlist?list=PLS1QulWo1RIaJECMeUT4LFwJ-ghgoSH6n
```

## Progress callbacks

```python
from pytube import YouTube

def on_progress(stream, chunk, bytes_remaining):
    total = stream.filesize
    downloaded = total - bytes_remaining
    print(f'{downloaded / total:.1%}')

def on_complete(stream, file_path):
    print(f'Saved to {file_path}')

yt = YouTube(
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    on_progress_callback=on_progress,
    on_complete_callback=on_complete,
)
yt.streams.first().download()
```

## Development

```bash
pip install poetry
poetry install --with dev
poetry run pytest tests/ -v
```
