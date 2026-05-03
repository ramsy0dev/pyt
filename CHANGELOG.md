# Changelog

## 1.1.0 — 2026-05-03

Major feature release closing the gap with yt-dlp for YouTube-specific use cases.
All changes are backward-compatible — existing scripts and CLI invocations continue
to work unchanged.

### Added

#### Post-processing pipeline

A chainable post-processor architecture (`pyt/postprocessors/`) lets you run
arbitrary transformations on the downloaded file without modifying any existing
`Stream` or `YouTube` code.

- **`AudioExtractor`** (`-x / --extract-audio`, `--audio-format FORMAT`) —
  strips the video track and converts to mp3, m4a, aac, flac, opus, vorbis,
  wav, or alac using ffmpeg. The original file is deleted after a successful
  conversion.
- **`FFmpegMetadataEmbedder`** (`--embed-metadata`) — embeds title, artist,
  upload date, and description. Uses `mutagen` for richer ID3 tags on MP3
  when the `[metadata]` extra is installed; falls back to ffmpeg otherwise.
- **`EmbedThumbnailPostProcessor`** (`--embed-thumbnail`) — downloads the
  video thumbnail and embeds it as cover art. MP4/M4A use ffmpeg's
  attached-picture method; MP3 uses a `mutagen` APIC frame.
- **`EmbedSubtitlePostProcessor`** (`--embed-subs`) — downloads a caption
  track and muxes it into the video without re-encoding. Supports MP4
  (`mov_text`), MKV (`srt`), and WebM (`webvtt`). Falls back to the
  auto-generated caption (`a.<lang>`) if a manual one is not available.
- **`SponsorBlockPP`** (`--sponsorblock-mark CATS`, `--sponsorblock-remove CATS`) —
  queries the SponsorBlock API (no new runtime dependency — uses stdlib
  urllib). Mark mode embeds chapter labels via an ffmetadata sidecar without
  re-encoding. Remove mode cuts segments with ffmpeg's `select` filter.
  Accepts comma-separated categories or `all`.

#### Output templates

`-o / --output TEMPLATE` controls the output filename and directory structure.
Syntax uses `{field}` placeholders:

```bash
pyt <url> -o "{author}/{upload_date:%Y-%m-%d} - {title}.{ext}"
```

Available fields: `title`, `id`, `author`, `channel_id`, `upload_date`
(supports strftime format via `{upload_date:%Y-%m-%d}`), `ext`, `resolution`,
`fps`, `abr`, `filesize`, `playlist_index`, `playlist_title`.
Each path component is sanitised for filesystem safety independently.

#### Download archive

`--download-archive FILE` tracks downloaded video IDs in a file compatible with
yt-dlp's archive format (`youtube <id>` per line). Already-downloaded videos
are skipped in batch and playlist mode. Writes are thread-safe.

#### Batch processing

`--batch-file FILE` reads one URL per line (blank lines and `#` comments
ignored) and downloads each with the full post-processing chain. Integrates
with `--download-archive` to skip already-downloaded videos.

#### Rate limiting

`--sleep-interval N` and `--max-sleep-interval N` add a fixed or random sleep
between downloads in batch and playlist mode.

#### Cookie authentication

`--cookies FILE` loads a Netscape-format cookie file (compatible with yt-dlp
and browser export extensions).
`--cookies-from-browser BROWSER` extracts cookies directly from Chrome,
Firefox, Brave, Edge, or Safari — requires `pip install pyt[cookies]`.
Cookies are injected into pyt's HTTP layer via a monkey-patched opener so all
subsequent requests carry them automatically.

#### Proxy support

`--proxy URL` passes HTTP, HTTPS, or SOCKS5 proxy configuration to the YouTube
HTTP layer. Examples: `http://user:pass@host:port`,
`socks5://127.0.0.1:9050`.

#### Geo-bypass

`--geo-bypass` injects a randomised `X-Forwarded-For` header.
`--geo-bypass-country CC` uses a specific country code (e.g. `US`, `DE`).

#### Configuration files

`pyt.conf` (INI format, `[default]` section) stores persistent defaults.
Searched in order: `./pyt.conf`, `~/.config/pyt/pyt.conf`, `~/.pyt.conf`.
CLI flags always override config values.

#### JSON dump mode

`-j / --dump-json` prints video metadata as JSON without downloading, useful
for scripting.

#### Docs

A full `docs/` folder was added covering every feature above, plus a
feature-comparison table against yt-dlp (`docs/comparison.md`).

### Optional dependencies

```bash
pip install pyt[metadata]   # mutagen — richer MP3/ID3 tags
pip install pyt[cookies]    # browser-cookie3 — browser cookie extraction
pip install pyt[all]        # both of the above
```

Core pyt remains dependency-free for users who don't need these extras.

### Tests

326 tests covering all new modules:
`test_template.py`, `test_archive.py`, `test_config.py`,
`test_cookies.py`, `test_postprocessors.py`.

---

## 1.0.0 — 2026-05-02

First release under the **pyt** name. This is a fork of the original
[pytube](https://github.com/pytube/pytube) project, which went unmaintained
while YouTube's API continued changing. Everything below was broken or missing
in the original and has been fixed here.

### Fixed

- **Multi-client extraction** — player data is now fetched by trying ANDROID →
  IOS → TV\_EMBED → page HTML in order. The first client that returns real
  stream URLs wins. This eliminates most 403s and "no streams" errors.
- **Pre-signed stream URLs** — ANDROID and IOS clients return URLs that don't
  require signature deciphering, so the vast majority of downloads work without
  touching the cipher at all.
- **visitorData** — extracted automatically from the watch page `ytcfg` blob
  and forwarded with every InnerTube player request. YouTube started requiring
  this for non-bot-looking traffic.
- **Self-updating web client version** — the `INNERTUBE_CLIENT_VERSION` is read
  from the live watch page instead of a hardcoded string that went stale within
  weeks of each release.
- **`video_id()` parsing** — the original used `url.split("=")[-1]`, which
  broke on playlist URLs and shorts. Replaced with a proper regex.
- **`apply_signature()`** — `parsed_url` was never assigned, causing a
  `NameError` at runtime. Fixed, along with a missing guard on the `n` param.
- **`datetime.utcfromtimestamp()` deprecation** — replaced with
  `datetime.fromtimestamp(..., timezone.utc)` throughout.
- **Lazy cipher initialisation** — the JS cipher is only fetched and parsed when
  actually needed (web-client fallback), not on every `YouTube()` construction.

### Changed

- Package renamed from `pytube` to `pyt`. CLI command is now `pyt`.
- `PytubeError` renamed to `PytError`.
- Logger redesigned: compact `HH:MM:SS  LVL  module  message` format,
  colourised on TTY, plain text when piped or in CI.
- CLI rewritten with a modern progress bar showing speed, ETA, and a `█`/`░`
  fill bar. Stream listing displays a formatted table.
- All stale InnerTube client version strings updated to current values.
- Dropped: `pipenv` / `.envrc`, `.deepsource.toml`, `.bumpversion.cfg`,
  `MANIFEST.in`, `docs/`, Sphinx dependencies.

### Dependencies

None. pyt has zero runtime dependencies — pure Python 3.10+.
