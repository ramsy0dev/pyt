# Configuration Files

Store default pyt options in a config file so you don't have to type them every time.

Equivalent to yt-dlp's `yt-dlp.conf`.

## File Locations

pyt looks for a config file in this order:

1. `./pyt.conf` (current directory)
2. `~/.config/pyt/pyt.conf` (XDG config)
3. `~/.pyt.conf` (home directory)

The first file found is used. CLI flags always override config values.

## Format

INI format with a `[default]` section:

```ini
[default]
# Output directory
target = ~/Downloads

# Output template
output = {author}/{title}.{ext}

# Post-processing defaults
embed_metadata = true
embed_thumbnail = true
sponsorblock_mark = sponsor,intro,outro
sleep_interval = 2

# Proxy (uncomment to enable)
# proxy = socks5://127.0.0.1:9050
```

## Supported Keys

All CLI flags are supported as config keys. Replace `-` with `_`:

| CLI flag | Config key |
|---|---|
| `--target DIR` | `target` |
| `--output TEMPLATE` | `output` |
| `--embed-metadata` | `embed_metadata` |
| `--embed-thumbnail` | `embed_thumbnail` |
| `--embed-subs` | `embed_subs` |
| `--extract-audio` | `extract_audio` |
| `--audio-format FMT` | `audio_format` |
| `--sponsorblock-mark CATS` | `sponsorblock_mark` |
| `--sponsorblock-remove CATS` | `sponsorblock_remove` |
| `--download-archive FILE` | `download_archive` |
| `--sleep-interval N` | `sleep_interval` |
| `--max-sleep-interval N` | `max_sleep_interval` |
| `--proxy URL` | `proxy` |
| `--cookies FILE` | `cookies` |
| `--cookies-from-browser BROWSER` | `cookies_from_browser` |
| `--geo-bypass` | `geo_bypass` |
| `--geo-bypass-country CC` | `geo_bypass_country` |
| `-v / --verbose` | `verbose` |

## Example: Music Download Config

```ini
[default]
extract_audio = true
audio_format = mp3
embed_metadata = true
embed_thumbnail = true
output = {author}/{title}.{ext}
target = ~/Music
download_archive = ~/Music/archive.txt
sponsorblock_mark = sponsor,intro,outro
sleep_interval = 1
max_sleep_interval = 5
```

With this config, just running `pyt <url>` downloads as MP3 with metadata and cover art into `~/Music/<Author>/`, skipping anything in the archive.
