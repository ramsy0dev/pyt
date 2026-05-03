# pyt vs yt-dlp Feature Comparison

pyt is a YouTube-first library that covers all major yt-dlp features for YouTube content. This table documents the current parity status.

## Feature Table

| Feature | yt-dlp | pyt | Notes |
|---|---|---|---|
| **Download** | | | |
| Video download (144p – 8K) | ✅ | ✅ | |
| Audio-only download | ✅ | ✅ | |
| Progressive streams | ✅ | ✅ | |
| DASH adaptive streams | ✅ | ✅ | |
| ffmpeg stream merging | ✅ | ✅ | |
| HDR / 3D streams | ✅ | ✅ | |
| Live stream (HLS) | ✅ | 🔜 Phase 2 | |
| DASH/HLS fragmented download | ✅ | 🔜 Phase 3 | |
| Concurrent fragment downloads | ✅ | 🔜 Phase 3 | |
| **Audio Extraction** | | | |
| Extract audio (`-x`) | ✅ | ✅ | |
| MP3 output | ✅ | ✅ | |
| M4A output | ✅ | ✅ | |
| FLAC output | ✅ | ✅ | |
| Opus / Vorbis / WAV / ALAC | ✅ | ✅ | |
| **Subtitles** | | | |
| Download subtitles | ✅ | ✅ | SRT, XML, JSON |
| Auto-generated captions | ✅ | ✅ | |
| Embed subtitles in video | ✅ | ✅ | MP4, MKV, WebM |
| Subtitle format conversion | ✅ | ✅ | SRT |
| **Metadata & Tags** | | | |
| Embed title / artist / date | ✅ | ✅ | |
| MP3 ID3 tags (mutagen) | ✅ | ✅ | requires `pip install pyt[metadata]` |
| Embed thumbnail as cover art | ✅ | ✅ | MP4, M4A, OGG, FLAC, MP3 |
| Write `.description` file | ✅ | 🔜 Phase 3 | |
| Write `.info.json` file | ✅ | 🔜 Phase 3 | |
| **SponsorBlock** | | | |
| Mark segments as chapters | ✅ | ✅ | no re-encode |
| Remove segments from video | ✅ | ✅ | requires re-encode |
| All 10 categories | ✅ | ✅ | |
| **Output & Organisation** | | | |
| Output filename templates | ✅ | ✅ | `%(title)s`, `%(author)s`, etc. |
| Date strftime formatting | ✅ | ✅ | `%(upload_date>%Y-%m-%d)s` |
| Per-author sub-directories | ✅ | ✅ | via template path separators |
| Download archive | ✅ | ✅ | yt-dlp compatible format |
| JSON info dump (`-j`) | ✅ | ✅ | |
| **Batch & Playlists** | | | |
| Playlist download | ✅ | ✅ | |
| Channel download | ✅ | ✅ | |
| Batch file (`--batch-file`) | ✅ | ✅ | |
| Sleep between downloads | ✅ | ✅ | `--sleep-interval` |
| Random sleep interval | ✅ | ✅ | `--max-sleep-interval` |
| Filter by playlist index | ✅ | 🔜 Phase 2 | |
| **Authentication** | | | |
| Netscape cookie file | ✅ | ✅ | |
| Browser cookie extraction | ✅ | ✅ | requires `pip install pyt[cookies]` |
| Age-restricted bypass | ✅ | ✅ | mobile client fallback |
| Members-only (OAuth) | ✅ | 🔜 Phase 2 | |
| **Network** | | | |
| HTTP / HTTPS proxy | ✅ | ✅ | |
| SOCKS5 proxy | ✅ | ✅ | via urllib |
| Geo-bypass (X-Forwarded-For) | ✅ | ✅ | `--geo-bypass` |
| Country-specific geo-bypass | ✅ | ✅ | `--geo-bypass-country CC` |
| External downloaders (aria2c) | ✅ | ❌ | out of scope |
| **Search** | | | |
| YouTube search | ✅ | ✅ | Python API |
| Search from CLI | ✅ | 🔜 Phase 2 | |
| **Configuration** | | | |
| Config file (`~/.pyt.conf`) | ✅ | ✅ | INI format |
| Per-URL options | ✅ | ❌ | |
| **Site Support** | | | |
| YouTube | ✅ | ✅ | |
| 1800+ other sites | ✅ | ❌ | pyt is YouTube-first |

**Legend:** ✅ Implemented · 🔜 Planned · ❌ Not planned / out of scope

## Key Advantages of pyt Over yt-dlp (for YouTube)

| Aspect | pyt | yt-dlp |
|---|---|---|
| **Runtime dependencies** | Zero (stdlib only) | ~5 required packages |
| **Install size** | Tiny | Large |
| **Python API** | First-class, typed | CLI-first, awkward API |
| **Ease of embedding** | Drop-in library | Subprocess or yt_dlp module |
| **YouTube-specific fixes** | Rapid | Slower (1800+ sites to maintain) |
| **License** | MIT | Unlicense |
