# Changelog

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
