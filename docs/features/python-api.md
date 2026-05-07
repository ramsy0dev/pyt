# Modern Python API

`pyt.Client` is the modern Python interface (debuted in 2.0). The legacy `pyt.YouTube`,
`pyt.Playlist`, and friends still work but emit `DeprecationWarning`
and will be removed from the top-level namespace in a future major
release. New code should use `Client`.

## Why the new API exists

The legacy interface had several footguns:

* **Hidden network I/O on attribute access.** `yt.title` could fire
  HTTP requests; surprises in async code, hard to mock, hard to
  time-out.
* **Module-level globals.** `pyt.__js__`, `pyt.__js_url__`, and the
  `Monostate` Borg pattern shared session state across instances —
  two `YouTube` objects in one process stepped on each other.
* **`.streams.filter(...).first()` returning `Optional[Stream]`** that
  then crashed with `AttributeError` on `.download()` if no stream
  matched.
* **Three ways to register progress callbacks** that drifted in
  behavior between versions.

The modern API fixes all of these.

## Quick start

```python
from pyt import Client

client = Client()
video = client.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

print(video.title)            # str
print(video.length)           # datetime.timedelta
print(video.author.name)      # str
print(video.published_at)     # tz-aware datetime
print(video.thumbnails)       # list[Thumbnail]

# Best progressive (video + audio in one file, no ffmpeg merge)
video.streams.progressive.best().download_to("downloads/").run()

# Best adaptive video + audio merged with ffmpeg in one SABR session
video.download_best("downloads/").run()
```

## Client

`Client` owns session state. Construct one per process / FastAPI app
/ notebook.

```python
client = Client(
    proxy="socks5://127.0.0.1:9050",
    cookies="/path/to/cookies.txt",       # XOR with cookies_from_browser
    cookies_from_browser="firefox",       # any of: chrome chromium firefox brave edge safari opera
    po_token=None,                        # PO token if needed for SABR
    use_oauth=False,
    on_progress=lambda stream, chunk, remaining: ...,
    on_complete=lambda stream, path: ...,
)
```

Validation runs eagerly: passing both `cookies=` and
`cookies_from_browser=` raises `ConfigError`, as does an unknown
browser name.

## Video

`client.video(url)` is the **network boundary** — it does the HTTP
work up-front and returns a fully-hydrated `Video` whose attributes
are pure getters on a typed dataclass.

```python
video.metadata        # VideoMeta dataclass (frozen)
video.video_id        # str
video.url             # str
video.title           # str
video.author          # Channel(id=, name=, url=)
video.length          # datetime.timedelta
video.description     # Optional[str]
video.published_at    # Optional[datetime]
video.views           # Optional[int]
video.thumbnails      # list[Thumbnail(url=, width=, height=)]
video.is_live         # bool

video.legacy          # the underlying pyt.YouTube — escape hatch
                      # for anything not yet on the modern surface
```

## StreamSet

Chainable, immutable filter view over the stream catalog.

```python
video.streams                     # StreamSet of all
    .audio                        # property; equivalent to .filter(kind="audio")
    .codec("opus")                # codec substring match
    .at_least(bitrate="128k")     # threshold filter
    .order_by("bitrate").desc()
    .first()                      # Optional[StreamRef]
```

**Discoverable shortcuts:**

* `.audio` — audio-only streams
* `.video` — anything with a video track
* `.progressive` — single-file (video+audio combined)
* `.adaptive` — DASH (video-only or audio-only)

**Filtering:**

* `.filter(kind=, subtype=, resolution=, codec=, custom=)`
* `.codec(name)` — codec substring (matches video or audio)
* `.at_least(resolution="1080p")` — keep streams ≥ that resolution
* `.at_least(bitrate="128k")` — keep streams ≥ that bitrate
* `.order_by(attribute)` + `.desc()`

**Terminal selectors:**

| Method | Returns | On empty |
|---|---|---|
| `.first()` | `Optional[StreamRef]` | `None` |
| `.last()` | `Optional[StreamRef]` | `None` |
| `.best()` | `StreamRef` | raises `NoMatchingStream` |
| `.one()` | `StreamRef` | raises if 0 or >1 match |
| `.best_pair(prefer_resolution=)` | `(video, audio)` | raises `NoMatchingStream` |

## Download

`stream.download_to(...)` returns a lazy `Download` builder. Call
`.run()` to execute, or chain post-processing first:

```python
from pyt import pipeline as pp

stream = video.streams.audio.best()
path = (
    stream.download_to("downloads/")
        | pp.sponsorblock(mark=["sponsor", "intro"])
        | pp.embed_metadata()
        | pp.embed_thumbnail()
        | pp.extract_audio("mp3")
).run()
```

The `|` operator is sugar for `.then(...)`. Use whichever you prefer;
they produce identical pipelines.

## Pipeline steps

| Factory | Purpose |
|---|---|
| `pp.sponsorblock(mark=[...])` / `pp.sponsorblock(remove=[...])` | Mark or remove SponsorBlock segments |
| `pp.embed_metadata()` | Title / artist / date / description tags |
| `pp.embed_thumbnail()` | Cover art |
| `pp.embed_subtitles(lang="en")` | Subtitle track |
| `pp.extract_audio("mp3", quality=...)` | Transcode to audio-only |
| `pp.upscale(scale=2)` | **Experimental.** Lanczos / Real-ESRGAN — see [upscale.md](upscale.md) |

Steps run in order. Each is a small frozen dataclass — introspectable,
picklable, testable.

## Combined adaptive download

For "best video-only + best audio merged with ffmpeg", use
`video.download_best(...)`. It drives one SABR session for both
formats. See [combined-download.md](combined-download.md).

## Playlists, channels, search

```python
playlist = client.playlist("https://www.youtube.com/playlist?list=PL...")
print(playlist.title, len(playlist))
for video in playlist:                    # lazy: one HTTP per video at iter time
    video.streams.audio.best().download_to("music/").run()

channel = client.channel("https://www.youtube.com/@somechannel")
print(channel.name, channel.channel_id)

results = client.search("python tutorial")
for video in results.videos:
    print(video.title, video.url)
```

## Errors

All modern errors inherit from `pyt.PytError`:

| Exception | When raised |
|---|---|
| `VideoUnavailable` | private, removed, region-blocked, members-only |
| `AgeRestricted` | tier-3 age gate (needs OAuth) |
| `LiveStreamNotSupported` | URL is a live stream |
| `NoMatchingStream` | `.best()` / `.one()` saw an empty filter chain |
| `DownloadError` | byte transfer failed (network, 403, SABR exhaustion) |
| `PostProcessError` | a pipeline step failed; carries `step=`, `partial_output_path=`, `cause=` |
| `ConfigError` | invalid `Client(...)` argument |

Every error carries enough context to file a useful bug report:
`video_id`, `url`, and (for `DownloadError`) `client_used`.

## Sync vs async

The modern API is sync-only at the moment. Async support is on the
roadmap but requires moving the request layer to `httpx` and
threading through SABR — substantial work that hasn't landed yet.

## Migration from the legacy API

| Old | New |
|---|---|
| `YouTube(url)` | `Client().video(url)` |
| `YouTube.from_id(vid)` | `Client().video(f"https://youtu.be/{vid}")` |
| `yt.streams.get_highest_resolution()` | `video.streams.progressive.best()` |
| `yt.streams.filter(only_audio=True).first()` | `video.streams.audio.best()` |
| `yt.streams.filter(res="1080p").first()` | `video.streams.video.filter(resolution="1080p").best()` |
| `yt.register_on_progress_callback(cb)` | `Client(on_progress=cb)` |
| `Playlist(url)` | `Client().playlist(url)` |
| `Channel(url)` | `Client().channel(url)` |
| `Search(query)` | `Client().search(query)` |
| Manual PP chain | `download \| pp.sponsorblock(...) \| pp.embed_metadata()` |
| `from pyt.exceptions import …` | `from pyt import PytError, VideoUnavailable, NoMatchingStream, …` |

To silence the deprecation warnings while you migrate:

```python
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"pyt\..*")
```

…or import explicitly from `pyt.legacy` (`from pyt.legacy import
YouTube`) so it's grep-able which call sites are still on the old
surface. `pyt.legacy.*` will outlive the top-level removal by one
more release cycle.
