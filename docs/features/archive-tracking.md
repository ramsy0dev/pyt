# Download Archive

Keep a record of downloaded video IDs so pyt skips them on future runs. Compatible with yt-dlp archive files.

## CLI Usage

```bash
# Record downloads to archive.txt; skip any already recorded
pyt <url> --download-archive archive.txt

# Works with playlists (skip previously downloaded videos)
pyt <playlist_url> --download-archive archive.txt

# Batch download with archive
pyt --batch-file urls.txt --download-archive archive.txt
```

## Archive File Format

One entry per line, compatible with yt-dlp:

```
youtube dQw4w9WgXcQ
youtube 9bZkp7q19f0
youtube jNQXAC9IVRw
```

If the archive file does not exist, pyt creates it automatically.

## Python API

```python
from pyt import YouTube, DownloadArchive

archive = DownloadArchive("archive.txt")

video_id = "dQw4w9WgXcQ"
if not archive.is_downloaded(video_id):
    yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
    yt.streams.get_highest_resolution().download()
    archive.mark_downloaded(video_id)
else:
    print("Already downloaded, skipping.")
```

## Thread Safety

`DownloadArchive.mark_downloaded()` is thread-safe — file writes are protected by a lock. Multiple workers can share the same archive instance.

## Importing a yt-dlp Archive

Because the format is identical, you can use an existing yt-dlp archive directly:

```bash
# If you used yt-dlp before switching to pyt:
pyt <playlist_url> --download-archive yt-dlp-archive.txt
```
