# Doctor Command

`pyt --doctor` reports which external tools are installed, derives
which features that unlocks, and can download missing binaries on
your behalf into a managed location (`~/.pyt/bin/`).

## Status report

```bash
$ pyt --doctor
pyt doctor - linux/x86_64, python 3.13
Managed bin dir: /home/you/.pyt/bin

Tools
------------------------------------------------------------
  [OK]   ffmpeg         ffmpeg version 7.1
         path:    /usr/bin/ffmpeg
         used by: muxing, audio extraction, post-processing, upscale re-encode
  [OK]   ffprobe        ffprobe version 7.1
         path:    /usr/bin/ffprobe
         used by: duration / fps / audio detection (ships with ffmpeg)
  [--]   realesrgan     not installed  (run: pyt --doctor --install realesrgan)
         used by: Real-ESRGAN neural upscaler (optional, for pp.upscale algorithm='realesrgan')

Features
------------------------------------------------------------
  [OK]   Stream download (SABR + byte-range)
  [OK]   Audio extraction / format conversion
  [OK]   Combined video+audio merge (CombinedDownload)
  [OK]   Metadata / thumbnail / subtitle embedding
  [OK]   SponsorBlock chapter marking
  [OK]   Upscale (algorithm='lanczos')
  [--]   Upscale (algorithm='realesrgan')  (needs: realesrgan)
```

The exit code is always `0` for the report — it's a status command,
not a check that fails on missing tools.

## Auto-install

```bash
pyt --doctor --install ffmpeg                # Windows / Linux only
pyt --doctor --install realesrgan            # Windows / Linux / macOS
pyt --doctor --install po-token-generator    # needs Node 18+ on PATH
pyt --doctor --install all
```

The **po-token-generator** install is npm-based, not archive-based:
it writes `package.json` to `~/.pyt/js/`, runs `npm install bgutils-js
youtubei.js`, copies pyt's vendored launcher (`po_token_launcher.js`)
into the same directory, and drops a wrapper at
`~/.pyt/bin/pyt-po-token` that runs the launcher with the right
`NODE_PATH`. After that, `--po-token-cmd "pyt-po-token"` gets you a
fresh token; the modern `Client` auto-refreshes on
`ATTESTATION_REQUIRED`. See [po-token.md](po-token.md) for the full
flow.

Each install:

1. Downloads the right archive for your platform (with progress)
2. Extracts to a temp directory
3. Locates the binary, copies it (plus any siblings like `ffprobe` or
   the Real-ESRGAN `models/` folder) to `~/.pyt/bin/`
4. Sets the executable bit on POSIX
5. Verifies by running the binary's version flag

If verification fails, the installed file is removed and you get a
clear error rather than a half-installed tool.

## Where binaries go

Installed binaries land in `~/.pyt/bin/`. pyt prepends that directory
to its own `PATH` at module import time, so `shutil.which("ffmpeg")`
finds them automatically. The mutation is **process-local** — it
never touches your shell profile or system `PATH`.

You can verify by running `pyt --doctor` after install:

```
[OK]   ffmpeg         ffmpeg version 7.1
       path:    /home/you/.pyt/bin/ffmpeg
```

## Sources per platform

| Tool | Windows x86_64 | Linux x86_64 | Linux arm64 | macOS |
|---|---|---|---|---|
| ffmpeg | [gyan.dev essentials](https://www.gyan.dev/ffmpeg/builds/) | [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases) | BtbN linuxarm64 | use `brew install ffmpeg` |
| realesrgan-ncnn-vulkan | [xinntao/Real-ESRGAN releases](https://github.com/xinntao/Real-ESRGAN/releases) | xinntao | xinntao | xinntao |

**macOS ffmpeg note:** auto-downloading a working build for both Intel
and Apple Silicon, with the codec set we use, is genuinely harder than
the rest combined. Homebrew's bottle is the right answer:

```bash
brew install ffmpeg
```

The doctor will refuse to auto-install ffmpeg on macOS with this
message and a link to Homebrew.

## Python API

The doctor module is callable directly if you want to integrate it
into a setup script:

```python
from pyt.api import doctor

tools = doctor.detect_all()
features = doctor.feature_status(tools)
print(doctor.render_status(tools, features))

# Install programmatically
try:
    path = doctor.install("realesrgan")
    print(f"Installed at {path}")
except doctor.InstallError as exc:
    print(f"Install failed: {exc}")
```

`doctor.plan_install(tool_name)` returns an `InstallPlan` with the
URL, archive format, and target paths — useful if you want to preview
what an install would do without triggering the network call.
