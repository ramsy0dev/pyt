# Cookie Authentication

Supply YouTube session cookies to access age-restricted, members-only, or otherwise authenticated content.

Equivalent to yt-dlp's `--cookies` and `--cookies-from-browser`.

## Requirements

**From file**: No additional packages needed (Python stdlib `http.cookiejar`).

**From browser**: Install browser-cookie3:

```bash
pip install pyt[cookies]
```

## CLI Usage

### From a cookie file

Export your YouTube cookies in Netscape format using a browser extension such as "Get cookies.txt LOCALLY" (Chrome/Firefox), then:

```bash
pyt <url> --cookies ~/youtube-cookies.txt
```

### From a browser (auto-extraction)

```bash
pyt <url> --cookies-from-browser chrome
pyt <url> --cookies-from-browser firefox
pyt <url> --cookies-from-browser brave
pyt <url> --cookies-from-browser edge
pyt <url> --cookies-from-browser safari
```

The cookies are extracted from the browser's local cookie store for `.youtube.com` only.

## Python API

```python
from pyt import YouTube
from pyt.cookies import install_cookies, load_cookies_from_file, load_cookies_from_browser

# From file
jar = load_cookies_from_file("cookies.txt")
install_cookies(jar)

# From browser (requires browser-cookie3)
jar = load_cookies_from_browser("firefox")
install_cookies(jar)

# Now YouTube objects will use the cookies
yt = YouTube("https://www.youtube.com/watch?v=<members_only_id>")
yt.streams.get_highest_resolution().download()
```

`install_cookies()` must be called before any `YouTube` object is created.

## Cookie File Format

Netscape format (compatible with yt-dlp):

```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	FALSE	0	SAPISID	<value>
.youtube.com	TRUE	/	FALSE	0	__Secure-3PAPISID	<value>
```

## Security Note

Cookie files contain session credentials. Keep them private and do not commit them to version control. Add `*.txt` or `cookies.txt` to `.gitignore` as appropriate.
