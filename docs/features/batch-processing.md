# Batch Processing

Download multiple videos from a text file of URLs, with optional sleep intervals to avoid rate limiting.

Equivalent to yt-dlp's `--batch-file` / `-a`.

## CLI Usage

```bash
# Create a file with one URL per line
cat urls.txt
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/watch?v=9bZkp7q19f0
# This is a comment — ignored

# Download all
pyt --batch-file urls.txt

# With archive tracking (skip already downloaded)
pyt --batch-file urls.txt --download-archive archive.txt

# With sleep between downloads to avoid rate-limiting
pyt --batch-file urls.txt --sleep-interval 3

# With random sleep (between 2 and 8 seconds)
pyt --batch-file urls.txt --sleep-interval 2 --max-sleep-interval 8

# Full pipeline: best quality, extract audio, embed metadata
pyt --batch-file urls.txt -x --audio-format mp3 --embed-metadata --embed-thumbnail
```

## Batch File Format

```
# Lines starting with # are comments
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/watch?v=9bZkp7q19f0

# Blank lines are ignored

https://youtu.be/jNQXAC9IVRw
```

URLs can be in any YouTube format (`watch?v=`, `youtu.be/`, `/shorts/`).

## Combining with Playlists

The `url` positional argument and `--batch-file` can be combined:

```bash
# Download one URL and also all URLs from a file
pyt <url> --batch-file more-urls.txt
```

## Sleep Intervals

`--sleep-interval N` and `--max-sleep-interval M` add a pause between each download. If only `--sleep-interval` is set, the delay is exactly N seconds. If both are set, the delay is a random number between N and M seconds.

This mirrors yt-dlp's `--sleep-interval` / `--max-sleep-interval` flags.
