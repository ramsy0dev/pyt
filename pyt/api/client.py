"""The :class:`Client` — single entry point and owner of session state.

Construct one ``Client`` per "user" (process, FastAPI app, notebook). It
holds the proxy config, cookies, OAuth flag, and PO token, and produces
:class:`Video` instances. The legacy :class:`pyt.YouTube` global state
(``pyt.__js__``, ``pyt.__js_url__``, ``Monostate``) is still touched
internally — fully decoupling from it is a v2 task.
"""
from __future__ import annotations

import http.cookiejar
from typing import Any, Callable, Dict, Optional

from pyt.api.errors import ConfigError
from pyt.api.video import Video


_BROWSER_CHOICES = {"chrome", "chromium", "firefox", "brave", "edge", "safari", "opera"}

ProgressCallback = Callable[[Any, bytes, int], None]
CompleteCallback = Callable[[Any, Optional[str]], None]


class Client:
    """Holds the configuration shared by every video downloaded through it.

    Example::

        client = Client(proxy="socks5://127.0.0.1:9050", cookies_from_browser="firefox")
        video = client.video("https://youtu.be/dQw4w9WgXcQ")
        video.streams.audio.best().download_to("downloads/")
    """

    def __init__(
        self,
        *,
        proxy: Optional[str] = None,
        cookies: Optional[str] = None,
        cookies_from_browser: Optional[str] = None,
        po_token: Optional[str] = None,
        use_oauth: bool = False,
        allow_oauth_cache: bool = True,
        on_progress: Optional[ProgressCallback] = None,
        on_complete: Optional[CompleteCallback] = None,
    ):
        if cookies and cookies_from_browser:
            raise ConfigError(
                "pass either cookies=<file> or cookies_from_browser=<name>, not both"
            )
        if cookies_from_browser and cookies_from_browser.lower() not in _BROWSER_CHOICES:
            raise ConfigError(
                f"unknown browser '{cookies_from_browser}'. "
                f"choose from: {', '.join(sorted(_BROWSER_CHOICES))}"
            )

        self._proxy = proxy
        self._cookies_path = cookies
        self._cookies_browser = cookies_from_browser
        self._po_token = po_token
        self._use_oauth = use_oauth
        self._allow_oauth_cache = allow_oauth_cache
        self._on_progress = on_progress
        self._on_complete = on_complete

        self._cookies_installed = False

    # ── public ──────────────────────────────────────────────────────────────

    def video(self, url: str) -> Video:
        """Fetch a single video by URL or ID. This is the network boundary —
        all attribute access on the returned :class:`Video` is pure.
        """
        self._ensure_cookies_installed()
        proxies = self._proxies_dict()
        return Video._from_url(
            url,
            po_token=self._po_token,
            use_oauth=self._use_oauth,
            allow_oauth_cache=self._allow_oauth_cache,
            proxies=proxies,
            on_progress=self._on_progress,
            on_complete=self._on_complete,
        )

    def playlist(self, url: str):
        """Open a YouTube playlist."""
        from pyt.api.playlists import Playlist

        self._ensure_cookies_installed()
        return Playlist._from_url(url, client=self)

    def channel(self, url: str):
        """Open a channel's "Videos" feed."""
        from pyt.api.playlists import ChannelFeed

        self._ensure_cookies_installed()
        return ChannelFeed._from_url(url, client=self)

    def search(self, query: str):
        """Search YouTube. Returns :class:`SearchResults`."""
        from pyt.api.playlists import SearchResults

        self._ensure_cookies_installed()
        return SearchResults._from_query(query, client=self)

    # ── internals ───────────────────────────────────────────────────────────

    def _proxies_dict(self) -> Optional[Dict[str, str]]:
        if not self._proxy:
            return None
        return {"http": self._proxy, "https": self._proxy}

    def _ensure_cookies_installed(self) -> None:
        """Cookies are installed once per client. The legacy hook patches
        the module-level :func:`pyt.request._execute_request` — that's a
        global mutation we inherit from the old code path. v2 will lift
        this onto the client itself.
        """
        if self._cookies_installed:
            return
        if not (self._cookies_path or self._cookies_browser):
            self._cookies_installed = True
            return

        from pyt import cookies as cookie_loader

        if self._cookies_path:
            jar = cookie_loader.load_cookies_from_file(self._cookies_path)
        else:
            jar = cookie_loader.load_cookies_from_browser(self._cookies_browser)

        if not isinstance(jar, http.cookiejar.CookieJar):
            raise ConfigError("cookie loader did not return a CookieJar")

        cookie_loader.install_cookies(jar)
        self._cookies_installed = True
