# SponsorBlock Integration

Skip or label sponsored segments, intros, outros, and other non-content sections using data from the [SponsorBlock](https://sponsor.ajay.app) crowdsourced database.

Equivalent to yt-dlp's `--sponsorblock-mark` and `--sponsorblock-remove`.

## Requirements

ffmpeg must be installed and on `PATH`. No additional Python packages are needed — the SponsorBlock API is queried over HTTPS using Python's standard library.

## CLI Usage

```bash
# Mark sponsor segments as chapters (no re-encoding)
pyt <url> --sponsorblock-mark sponsor

# Mark multiple categories
pyt <url> --sponsorblock-mark sponsor,intro,outro

# Mark all categories
pyt <url> --sponsorblock-mark all

# Remove sponsor segments entirely (re-encodes the video)
pyt <url> --sponsorblock-remove sponsor

# Combine: mark some, remove others
pyt <url> --sponsorblock-mark intro,outro --sponsorblock-remove sponsor
```

## Available Categories

| Category | Label | Description |
|---|---|---|
| `sponsor` | Sponsor | Paid promotion content |
| `intro` | Intro | Recurring intro animation |
| `outro` | Outro | Outro / end screen |
| `selfpromo` | Self-Promotion | Non-paid self-promotion |
| `preview` | Preview | Preview of the video content |
| `filler` | Filler | Filler tangents |
| `interaction` | Interaction | Subscribe / like reminders |
| `music_offtopic` | Non-Music | Non-music sections in music videos |
| `hook` | Hook | Highlight shown at the start |
| `poi_highlight` | Highlight | Point of interest highlight |

Use `all` as a shortcut for all categories.

## Mark vs Remove

### Mark mode (`--sponsorblock-mark`)

Embeds the SponsorBlock segments as **chapter markers** in the video file. No re-encoding — a metadata sidecar file is muxed in via `ffmpeg -codec copy`. Compatible media players (VLC, mpv, etc.) will display chapter navigation with `[SponsorBlock] Sponsor` labels.

### Remove mode (`--sponsorblock-remove`)

**Cuts out** the flagged segments from the video using an ffmpeg `select` filter. This requires re-encoding the audio and video streams, so it is slower and may change quality. The resulting file has no gaps — segments are seamlessly removed.

## Python API

```python
from pyt import YouTube
from pyt.postprocessors import SponsorBlockPP

yt = YouTube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
stream = yt.streams.filter(progressive=False, subtype="mp4").order_by("resolution").last()
path = stream.download()

# Add chapter markers for sponsor segments
pp = SponsorBlockPP(mode="mark", categories=["sponsor", "intro", "outro"])
path = pp.run(path, stream, yt)

# Or remove sponsor segments entirely
pp = SponsorBlockPP(mode="remove", categories=["sponsor"])
path = pp.run(path, stream, yt)
```

## How It Works

1. pyt queries `https://sponsor.ajay.app/api/skipSegments?videoID=<id>&categories=[...]`
2. If no segments are found (404 or empty response), the file is returned unchanged
3. For **mark**: an ffmetadata INI file is generated with `[CHAPTER]` entries at the segment timestamps, then ffmpeg muxes it in (`-codec copy`)
4. For **remove**: an ffmpeg `select` expression excludes the flagged time ranges, then `setpts` and `asetpts` fix the timestamps
