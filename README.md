# pyt
### formerly pytube

[![CI](https://github.com/ramsy0dev/pyt/actions/workflows/ci.yml/badge.svg)](https://github.com/ramsy0dev/pyt/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A maintained pytube fork. The original went unmaintained while YouTube's API
kept changing. Everything that was broken has been fixed, and a full
post-processing pipeline has been added so pyt can hold its own against yt-dlp
for YouTube-specific use cases.

---

## Features

| Category | What pyt does |
|---|---|
| **Download** | 144p – 8K, progressive & DASH, audio-only, auto-merge with ffmpeg |
| **Audio extraction** | Convert to mp3, m4a, flac, opus, vorbis, wav, aac, alac |
| **Metadata** | Embed title, artist, date, description (ffmpeg + optional mutagen) |
| **Thumbnails** | Embed cover art into mp4, m4a, mp3, ogg, flac |
| **Subtitles** | Embed SRT/VTT into mp4, mkv, webm; 100+ language codes |
| **SponsorBlock** | Mark segments as chapters or cut them out entirely |
| **Output templates** | `{author}/{upload_date:%Y-%m-%d} - {title}.{ext}` and more |
| **Archive tracking** | Skip already-downloaded videos across runs |
| **Batch processing** | Download from a file of URLs |
| **Authentication** | Netscape cookie files, browser cookie extraction |
| **Proxy / geo-bypass** | HTTP, HTTPS, SOCKS5 proxy; `X-Forwarded-For` spoofing |
| **Config files** | `~/.pyt.conf` for persistent defaults |
| **Playlists & channels** | Full playlist and channel support |

---

## Install

```bash
pip install git+https://github.com/ramsy0dev/pyt

# With richer MP3/ID3 tag support:
pip install "git+https://github.com/ramsy0dev/pyt#egg=pyt[metadata]"

# With browser cookie extraction:
pip install "git+https://github.com/ramsy0dev/pyt#egg=pyt[cookies]"

# Everything:
pip install "git+https://github.com/ramsy0dev/pyt#egg=pyt[all]"
```

ffmpeg is required for post-processing (audio conversion, metadata/thumbnail/subtitle
embedding, SponsorBlock). Get it at https://ffmpeg.org/download.html.

---

## Quick start — CLI

```bash
# Best quality (auto-merges video + audio with ffmpeg)
pyt "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Extract audio as MP3 with metadata and cover art
pyt <url> -x --audio-format mp3 --embed-metadata --embed-thumbnail

# Custom output path
pyt <url> -o "{author}/{upload_date:%Y-%m-%d} - {title}.{ext}" -t ~/Downloads

# SponsorBlock chapters (no re-encode)
pyt <url> --sponsorblock-mark sponsor,intro,outro

# Batch download with archive (skips already downloaded)
pyt --batch-file urls.txt --download-archive archive.txt --sleep-interval 2

# Playlist
pyt "https://www.youtube.com/playlist?list=PLxxxxxxxx"

# Behind a proxy
pyt <url> --proxy socks5://127.0.0.1:9050

# Cookies from browser
pyt <url> --cookies-from-browser firefox
```

---

## Quick start — Python API

```python
from pyt import YouTube

yt = YouTube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(yt.title)   # Rick Astley - Never Gonna Give You Up
print(yt.length)  # 212 seconds

# Highest progressive quality (video + audio in one file, no ffmpeg needed)
yt.streams.get_highest_resolution().download()

# Audio only
yt.streams.filter(only_audio=True).first().download()

# Specific resolution
yt.streams.filter(res="1080p", progressive=False).first().download()

# Progress callback
def on_progress(stream, chunk, remaining):
    pct = (stream.filesize - remaining) / stream.filesize
    print(f"\r{pct:.1%}", end="")

yt = YouTube(url, on_progress_callback=on_progress)
yt.streams.get_highest_resolution().download()
```

### Post-processing

```python
from pyt import YouTube
from pyt.postprocessors import AudioExtractor, FFmpegMetadataEmbedder, SponsorBlockPP

yt = YouTube(url)
stream = yt.streams.filter(only_audio=True).order_by("abr").last()
path = stream.download()

path = SponsorBlockPP(mode="mark", categories=["sponsor", "intro"]).run(path, stream, yt)
path = FFmpegMetadataEmbedder().run(path, stream, yt)
path = AudioExtractor(format="mp3").run(path, stream, yt)
```

---

## CLI reference

```
pyt [url] [options]

Stream selection:
  -f, --ffmpeg [RES]       Merge best video + audio with ffmpeg (default: best)
  -r, --resolution RES     Download specific resolution (e.g. 1080p)
  -a, --audio [FMT]        Download audio-only stream
  --itag N                 Download by itag number
  -l, --list               List available streams

Post-processing:
  -x, --extract-audio      Extract audio track
  --audio-format FMT       Target format: mp3 m4a aac flac opus vorbis wav alac
  --embed-metadata         Embed title, artist, date, description
  --embed-thumbnail        Embed cover art
  --embed-subs             Embed subtitle track
  --sponsorblock-mark CATS Mark SponsorBlock segments as chapters
  --sponsorblock-remove CATS  Cut SponsorBlock segments out

Output:
  -o, --output TEMPLATE    Filename template, e.g. "{author}/{title}.{ext}"
  -t, --target DIR         Download directory (default: current dir)
  -j, --dump-json          Print video info as JSON, don't download

Captions:
  -c, --caption-code LANG  Download / embed caption language (e.g. en)
  --list-captions          List available caption tracks

Network:
  --proxy URL              HTTP/HTTPS/SOCKS5 proxy URL
  --cookies FILE           Netscape cookie file
  --cookies-from-browser B Extract cookies from browser (chrome firefox brave edge safari)
  --geo-bypass             Spoof X-Forwarded-For with a random IP
  --geo-bypass-country CC  Use a specific country code (e.g. US)

Batch:
  --batch-file FILE        File of URLs to download (one per line)
  --download-archive FILE  Record downloaded IDs; skip if already present
  --sleep-interval N       Sleep N seconds between downloads
  --max-sleep-interval N   Random sleep between N and max-N seconds

Debug:
  -v, --verbose            Verbose logging
  --build-playback-report  Dump playback report to file
```

---

## Config file

Store defaults in `~/.pyt.conf` (also checked: `./pyt.conf`,
`~/.config/pyt/pyt.conf`):

```ini
[default]
target = ~/Downloads
output = {author}/{title}.{ext}
embed_metadata = true
embed_thumbnail = true
sponsorblock_mark = sponsor,intro,outro
sleep_interval = 2
```

CLI flags always override config values.

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
  here. If a video returns 403s on web-client streams it falls back to
  the mobile client, which usually works without it.
- **Live streams** — metadata is accessible but downloading live HLS/DASH
  is not supported.

---

## Dev setup

```bash
git clone https://github.com/ramsy0dev/pyt
cd pyt
pip install poetry
poetry install --with dev
poetry run pytest tests/ -v
```

---

## Status

I maintain this in my spare time. It works for everything I've tested.
If something breaks, open an issue with a video URL and I'll look at it.
PRs are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
