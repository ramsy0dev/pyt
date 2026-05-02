```
┌─────────────────────────────────────────┐
│  pyt  ·  youtube downloader for python  │
└─────────────────────────────────────────┘
```

[![CI](https://github.com/ramsy0dev/pytube/actions/workflows/ci.yml/badge.svg)](https://github.com/ramsy0dev/pytube/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A maintained fork of pytube. The original project went quiet, streams stopped
working, and I needed it for my own stuff — so I fixed it and kept going.

No dependencies. Pure Python. Does what it says.

---

## What's fixed vs the original

YouTube kept changing things. This fork keeps up:

- **Multi-client extraction** — tries ANDROID → IOS → TV embedded → page HTML
  in order, uses the first one that returns real stream URLs
- **Pre-signed stream URLs** — mobile clients return URLs that don't need
  signature deciphering, so downloads just work
- **visitorData** — extracted automatically from the watch page and sent with
  API requests (YouTube started requiring this)
- **Self-updating web client version** — reads the current version from the
  live page instead of a hardcoded string that goes stale in weeks
- **Modern progress bar** — shows speed and ETA, not just a percentage
- **Colourised logger** — compact, readable, disabled automatically when
  piped to a file or CI

---

## Install

```bash
pip install git+https://github.com/ramsy0dev/pytube
```

---

## Quick start

```python
from pyt import YouTube

yt = YouTube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(yt.title)   # Rick Astley - Never Gonna Give You Up
print(yt.length)  # 212  (seconds)

# highest progressive quality (video + audio in one file)
yt.streams.get_highest_resolution().download()

# audio only
yt.streams.filter(only_audio=True).first().download()

# specific resolution
yt.streams.filter(res="1080p", progressive=False).first().download()

# with progress and completion callbacks
def show_progress(stream, chunk, remaining):
    done = stream.filesize - remaining
    print(f"\r{done / stream.filesize:.1%}", end="")

yt = YouTube(url, on_progress_callback=show_progress)
yt.streams.get_highest_resolution().download()
```

---

## CLI

```bash
# download best quality
pyt https://www.youtube.com/watch?v=dQw4w9WgXcQ

# list all streams
pyt https://www.youtube.com/watch?v=dQw4w9WgXcQ --list

# pick by itag
pyt https://www.youtube.com/watch?v=dQw4w9WgXcQ --itag=137

# specific resolution
pyt https://www.youtube.com/watch?v=dQw4w9WgXcQ -r 720p

# audio only (default mp4, pass format to override)
pyt https://www.youtube.com/watch?v=dQw4w9WgXcQ -a
pyt https://www.youtube.com/watch?v=dQw4w9WgXcQ -a webm

# merge best video + audio with ffmpeg
pyt https://www.youtube.com/watch?v=dQw4w9WgXcQ -f
pyt https://www.youtube.com/watch?v=dQw4w9WgXcQ -f 1080p

# save to a specific folder
pyt https://www.youtube.com/watch?v=dQw4w9WgXcQ -t ~/Downloads

# captions
pyt https://www.youtube.com/watch?v=dQw4w9WgXcQ --list-captions
pyt https://www.youtube.com/watch?v=dQw4w9WgXcQ -c en

# download a playlist
pyt https://www.youtube.com/playlist?list=PLxxxxxxxx
```

---

## Playlists and channels

```python
from pyt import Playlist

p = Playlist("https://www.youtube.com/playlist?list=PLxxxxxxxx")
print(p.title)
for video in p.videos:
    video.streams.get_highest_resolution().download()
```

---

## Known limitations

- **Age-restricted videos** — the bypass works for most, but tier-3
  age-gated content (country-level) cannot be unlocked without OAuth.
- **po_token** — YouTube's browser-attestation token is not generated
  here. If a video returns 403s on web-client streams it will fall
  back to the mobile client, which usually works without it.
- **Live streams** — metadata is accessible but downloading live HLS/DASH
  is not supported.

---

## Dev setup

```bash
git clone https://github.com/ramsy0dev/pytube
cd pytube
pip install poetry
poetry install --with dev
poetry run pytest tests/ -v
```

---

## Status

I maintain this in my spare time. It works for everything I've tested.
If something breaks, open an issue with a video URL and I'll look at it.
PRs are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
