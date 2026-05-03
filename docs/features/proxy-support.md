# Proxy Support

Route all pyt requests through an HTTP, HTTPS, or SOCKS5 proxy.

## CLI Usage

```bash
# HTTP proxy
pyt <url> --proxy http://127.0.0.1:8080

# SOCKS5 proxy (e.g. Tor)
pyt <url> --proxy socks5://127.0.0.1:9050

# Authenticated proxy
pyt <url> --proxy http://user:password@proxy.example.com:3128
```

## Geo-Bypass

If you cannot access a video due to geographic restrictions, use the geo-bypass options to spoof your location:

```bash
# Auto geo-bypass (defaults to a US IP)
pyt <url> --geo-bypass

# Specify a country
pyt <url> --geo-bypass-country GB
pyt <url> --geo-bypass-country DE
pyt <url> --geo-bypass-country AU
```

Supported country codes: US, GB, CA, AU, DE (and any code — US is the fallback).

Geo-bypass works by adding a fake `X-Forwarded-For` header to every request. It is effective for videos that check the IP via this header. For strict geo-blocks that verify via the YouTube backend, use a proxy instead.

## Python API

```python
from pyt import YouTube

# HTTP proxy
yt = YouTube("https://www.youtube.com/watch?v=dQw4w9WgXcQ",
             proxies={"http": "http://127.0.0.1:8080",
                      "https": "http://127.0.0.1:8080"})

# SOCKS5 proxy
yt = YouTube(url, proxies={"http": "socks5://127.0.0.1:9050",
                            "https": "socks5://127.0.0.1:9050"})
```

## Configuration File

Set a default proxy in `~/.pyt.conf` so you don't need to pass it every time:

```ini
[default]
proxy = socks5://127.0.0.1:9050
```
