# Audio Extraction

Extract and convert audio from any YouTube video using ffmpeg.

Equivalent to yt-dlp's `-x / --extract-audio` + `--audio-format`.

## Requirements

ffmpeg must be installed and on `PATH`.

## CLI Usage

```bash
# Extract audio as MP3 (default)
pyt <url> -x

# Specify format
pyt <url> -x --audio-format flac
pyt <url> -x --audio-format m4a
pyt <url> -x --audio-format opus

# Combine with metadata and thumbnail embedding
pyt <url> -x --audio-format mp3 --embed-metadata --embed-thumbnail
```

## Supported Formats

| Format | Codec | Extension |
|---|---|---|
| mp3 (default) | libmp3lame | .mp3 |
| m4a | aac | .m4a |
| aac | aac | .aac |
| flac | flac | .flac |
| opus | libopus | .opus |
| vorbis | libvorbis | .ogg |
| wav | pcm_s16le | .wav |
| alac | alac | .m4a |

## Python API

```python
from pyt import YouTube
from pyt.postprocessors import AudioExtractor

yt = YouTube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

# Download best audio stream
stream = yt.streams.filter(only_audio=True).order_by("abr").last()
path = stream.download()

# Convert to MP3
extractor = AudioExtractor(format="mp3")
mp3_path = extractor.run(path, stream, yt)
print(mp3_path)  # → "Never Gonna Give You Up.mp3"
```

## How It Works

1. The best audio stream is downloaded (WebM/Opus or MP4/AAC)
2. `ffmpeg -vn -acodec <codec>` strips the video track and converts
3. The original file is deleted; the converted file takes its place

The stream selection picks the highest-bitrate audio-only stream available. For music, this is typically 160 kbps Opus (WebM) or 128 kbps AAC (M4A).
