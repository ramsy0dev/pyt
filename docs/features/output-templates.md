# Output Templates

Control the output filename and directory structure using a simple `{field}` syntax.

## CLI Usage

```bash
pyt <url> -o "{title}.{ext}"                               # default
pyt <url> -o "{author}/{title}.{ext}"                      # sub-directory per author
pyt <url> -o "{upload_date:%Y-%m-%d} - {title}.{ext}"     # date prefix
pyt <url> -o "{id}.{ext}"                                  # use video ID as name
pyt <url> -o "{playlist_index}. {title}.{ext}"            # playlist ordering
```

## Available Fields

| Field | Example value | Description |
|---|---|---|
| `{title}` | `Never Gonna Give You Up` | Video title |
| `{id}` | `dQw4w9WgXcQ` | YouTube video ID |
| `{author}` | `Rick Astley` | Channel / uploader name |
| `{channel_id}` | `UCuAXFkgsw1L7xaCfnd5JJOw` | Channel ID |
| `{upload_date}` | `19871027` | Upload date as YYYYMMDD |
| `{upload_date:%Y-%m-%d}` | `1987-10-27` | Upload date with custom format |
| `{ext}` | `mp4` | File extension |
| `{resolution}` | `1080p` | Video resolution |
| `{fps}` | `30` | Frames per second |
| `{abr}` | `128kbps` | Audio bitrate |
| `{filesize}` | `52428800` | Approximate file size in bytes |
| `{playlist_index}` | `03` | Zero-padded index within playlist |
| `{playlist_title}` | `Top Hits 1987` | Playlist title |

## Date Formatting

Add `:%Y-%m-%d` (or any strftime format) after `upload_date` to format the date:

```
{upload_date}           →  19871027
{upload_date:%Y-%m-%d}  →  1987-10-27
{upload_date:%Y/%m}     →  1987/10
{upload_date:%B %Y}     →  October 1987
```

## Directory Separators

Any `/` in the template creates sub-directories automatically:

```bash
# Downloads to ~/Downloads/Rick Astley/Never Gonna Give You Up.mp4
pyt <url> -t ~/Downloads -o "{author}/{title}.{ext}"

# Organised by year and month
pyt <url> -o "{upload_date:%Y}/{upload_date:%m} - {title}.{ext}"
```

## Python API

```python
from pyt import YouTube, OutputTemplate

yt = YouTube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
stream = yt.streams.get_highest_resolution()

template = OutputTemplate("{author} - {title}.{ext}")
filename = template.render(yt, stream)
# → "Rick Astley - Never Gonna Give You Up.mp4"

stream.download(filename=filename)
```

## Unsafe Character Handling

Characters that are illegal in filenames (`\ / : * ? " < > |`) are replaced with `_` in each path component. Leading/trailing dots and spaces are stripped per component.
