# pyt
### formerly pytube

[![CI](https://github.com/ramsy0dev/pyt/actions/workflows/ci.yml/badge.svg)](https://github.com/ramsy0dev/pyt/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> **Heads-up:** SABR support is still under active development. Some videos
> won't download yet, others will be slow or 403 partway through. If a download
> fails, that's why. See [Why downloads break sometimes (SABR)](#why-downloads-break-sometimes-sabr)
> for the full story.

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

## Why downloads break sometimes (SABR)

YouTube has been rolling out SABR ("Server Adaptive Bitrate Request") for a
while now. Instead of handing your player a signed CDN URL and letting it pull
bytes with a normal `Range:` request, the server hands you a `serverAbrStreamingUrl`
and expects you to POST a protobuf describing what you've already buffered, on
which it streams back a binary UMP response with the next chunk it feels like
giving you. The protocol is undocumented, the server holds back delivery
based on player-time/readahead heuristics, and it's the official direction —
fewer and fewer client variants still get plain signed URLs.

What this means in practice:

- **Some videos download fine, others crawl or 403.** That's the SABR rollout
  hitting different itag/client combinations.
- **The `ANDROID_VR` client at version ≤1.65** is the current "give me real
  URLs" loophole, and it's the priority client here. When Google closes that
  (they will), there's no escape from SABR.
- **Slow downloads ≠ your network.** SABR's readahead throttle is real —
  server says "wait 8 seconds" between chunks, you wait, the file lands at
  approximately playback speed. We work around this by lying about the
  player's position so the server stops throttling.

### What I'm doing about it

There's a real SABR implementation under [pyt/sabr/](pyt/sabr/). It's modeled
after [yt-dlp's PR #13515](https://github.com/yt-dlp/yt-dlp/pull/13515) (massive
thanks to coletdjnz for reverse-engineering the wire format). It currently
handles:

- The full UMP part taxonomy — `MEDIA_HEADER`, `MEDIA`, `MEDIA_END`,
  `NEXT_REQUEST_POLICY`, `FORMAT_INITIALIZATION_METADATA`, `SABR_REDIRECT`,
  `SABR_ERROR`, `STREAM_PROTECTION_STATUS`, `SABR_CONTEXT_UPDATE` /
  `SABR_CONTEXT_SENDING_POLICY`, `SABR_SEEK`.
- Audio + video multiplex on one session via `header_id → itag` demux.
- Segment-aligned `BufferedRange` (start/end segment indices), not byte-fraction
  guesswork.
- Proper `StreamerContext` with full `ClientInfo`, PO token, playback cookie,
  and the SABR contexts the server tells you to echo back (this is the
  unskippable-ad enforcement channel).
- `player_time_ms` set forward to the buffered edge so the server stops
  throttling.
- Backoff cap outside ad windows. Ad-scoped backoffs are honored in full.
- Token refresh, redirect follow, retry/backoff on transport errors.

What's missing / works but not great:

- **PO token.** Required by some accounts for some videos. We can ship it if
  you have one; we can't generate it (BotGuard attestation runs in a real
  browser). Long-term plan: vendor a generator like `bgutil-pot`. For now: if
  you hit `ATTESTATION_REQUIRED`, pass `po_token=...` to `YouTube(...)` and
  it'll work.
- **Live streams.** Metadata yes, downloads no. SABR live needs `SABR_SEEK` /
  `LIVE_METADATA` handling we haven't wired up.
- **Multi-format download orchestrator.** SabrSession can multiplex but
  `Stream.download()` still opens one session per stream. Fixing this is
  next on the list — see ADR notes in commits.
- **Tests on recorded UMP fixtures.** Coming. For now SABR is exercised by
  end-to-end downloads only, which means failures land in your terminal first.

If something downloads slow or 403s, file an issue with the URL and your
client (anonymized — no account info needed). I do this in spare time so
turnaround is days-to-weeks, not hours.

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
