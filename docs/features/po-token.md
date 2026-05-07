# PO Tokens

## What this is

YouTube's SABR streaming endpoint sometimes returns
`STREAM_PROTECTION_STATUS=ATTESTATION_REQUIRED`. When that happens,
the server refuses to deliver bytes until the request carries a
**Proof-of-Origin (PO) token** — a base64url string proving the
request came from a real browser session.

PO tokens are produced by a BotGuard JavaScript challenge running in
a real browser. We can't generate them in pure Python; the BotGuard
logic is private and changes frequently. What pyt does instead:

- Detects `ATTESTATION_REQUIRED` and translates it to a typed
  `AttestationRequired` error.
- Lets you plug in any external generator: a static token, a Python
  callable, a shell command, or a JavaScript file.
- Caches the token for the client lifetime so generators don't run
  on every request.
- Auto-retries the download once with a freshly-generated token when
  attestation fails mid-stream.

## When you need one

Most public videos work without a PO token. You'll typically hit
`ATTESTATION_REQUIRED` when:

- The video has age / region restrictions
- Your account state has been flagged as bot-like
- You're hitting YouTube from a fresh IP / new session

If `pp.upscale` / `download_best` / `Stream.download` raise
`AttestationRequired`, you need a PO token.

## Three ways to provide a token

### 1. Static token (`po_token=`)

Fastest if you can grab one manually. Open YouTube in your browser,
open DevTools → Network tab, look for a request to
`/youtubei/v1/player`, copy the `poToken` field from the JSON body.

```python
from pyt import Client

client = Client(po_token="abcdef1234...")
video = client.video(url)
video.download_best("./").run()
```

```bash
pyt <url> --po-token "abcdef1234..."
```

The static path doesn't auto-refresh. If the token expires mid-run,
you'll need to grab a new one.

### 2. Python callable (`po_token_provider=`)

Wrap any Python callable that returns a token string. The callable
runs on first use and again when `AttestationRequired` triggers a
retry.

```python
def my_generator():
    # call your existing token generator here
    return fetch_from_internal_service()

client = Client(po_token_provider=my_generator)
```

The provider's result is cached for 30 minutes by default. Pass
`force_refresh=True` on the provider object to bypass the cache.

### 3. Shell command (`po_token_cmd=`)

Drop-in for tools that print a token to stdout. The first non-empty
last line is taken as the token.

```python
client = Client(po_token_cmd="bgutil-pot --visitor-data $VD")
```

```bash
pyt <url> --po-token-cmd "bgutil-pot --visitor-data $VD"
```

`shlex.split` parses string commands; pass a list to skip parsing:

```python
Client(po_token_cmd=["bgutil-pot", "--visitor-data", visitor_data])
```

### 4. JavaScript file (`po_token_script=`)

Runs a JS file with the first available JS runtime on `PATH`
(`node` → `bun` → `deno`, in preference order). The script's stdout
is the token.

```python
client = Client(po_token_script="/path/to/po_token_gen.js")
```

```bash
pyt <url> --po-token-script ~/.local/lib/po_token_gen.js
```

`pyt --doctor` reports which runtimes are installed:

```
$ pyt --doctor
[OK]   node           v20.10.0
       path:    /usr/local/bin/node
       used by: JS runtime for PO-token generators (bgutil-pot, etc.)
```

## How auto-retry works

When `CombinedDownload.run()` (or any download path going through
SABR) hits `ATTESTATION_REQUIRED`:

1. The session translates `SabrAttestationRequired` →
   `AttestationRequired` at the API boundary.
2. If the parent `Client` has a provider configured, we ask it to
   refresh the token (`provider.invalidate()` + `provider.get(force_refresh=True)`).
3. The legacy `Monostate.po_token` is updated in-place so the next
   SABR session picks up the new token.
4. The part files are reset (truncated + reopened) and the SABR
   exchange runs once more.
5. If the second attempt also fails, the error propagates.

This means a typical download fires the generator at most twice: once
to seed the cache, and once if the server rejects the cached token.

## Generators that work today

The community has a few token generators we know work:

| Generator | Notes |
|---|---|
| [`bgutil-pot`](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) | Node-based; designed for yt-dlp but works standalone. Use with `--po-token-cmd` |
| [`youtube-po-token-generator`](https://www.npmjs.com/package/youtube-po-token-generator) | npm package; runs on Node. Use with `--po-token-script` after writing a small wrapper |
| Manual extraction (DevTools) | Slowest but most reliable. Use with `--po-token` |

We don't bundle any of these — token generators move fast and live
better as their own projects.

## Doctor

Run `pyt --doctor` to see what's available for token generation:

```
Tools
------------------------------------------------------------
  [OK]   node           v20.10.0
  [--]   bun            not installed  (install: https://bun.sh)
  [--]   deno           not installed  (install: https://deno.com)
  [--]   bgutil-pot     not installed  (install: https://github.com/Brainicism/bgutil-ytdlp-pot-provider)

Features
------------------------------------------------------------
  [OK]   PO token auto-generation (for ATTESTATION_REQUIRED)
```

The "PO token auto-generation" feature flips to `[OK]` as soon as
*any one* of node / bun / deno / bgutil-pot is on `PATH`. None of
them are required if you're providing tokens manually via
`--po-token`.

## Errors

```python
from pyt import Client, AttestationRequired

try:
    Client().video(url).download_best("./").run()
except AttestationRequired as exc:
    print(f"Need PO token for {exc.video_id} ({exc.url})")
    # Configure a provider and retry
    client = Client(po_token_cmd="bgutil-pot")
    client.video(url).download_best("./").run()
```

The error message itself spells out the three ways to provide a
token, so users hitting it for the first time get inline guidance.

## Limitations

- **We don't generate tokens.** That requires running BotGuard JS,
  which is its own project. Use one of the community generators
  above.
- **Auto-retry happens at most once.** If the second attempt fails,
  the error propagates so the user can investigate (perhaps the
  generator is broken, or the requested video is genuinely gated
  beyond what a token can unlock).
- **The legacy `Stream.download` path doesn't auto-retry.** Only the
  modern `CombinedDownload` does. The CLI's `pyt <url>` command runs
  the generator once at startup and passes the result as a static
  token; if it expires mid-download, re-run.
