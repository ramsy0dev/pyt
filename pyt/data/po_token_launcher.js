#!/usr/bin/env node
/*
 * po_token_launcher.js — generate a YouTube PO token via bgutils-js
 *
 * Vendored by pyt and installed by `pyt --doctor --install
 * po-token-generator`. Uses two community packages that implement the
 * BotGuard challenge in pure JavaScript:
 *
 *   - bgutils-js   pure-JS BotGuard challenge solver
 *   - youtubei.js  YouTube InnerTube client (used to fetch fresh
 *                  visitor data when the caller doesn't supply it)
 *
 * Both are npm-installed alongside this file under ~/.pyt/js/. The
 * wrapper at ~/.pyt/bin/pyt-po-token sets NODE_PATH so this script's
 * `require()` calls resolve from that local node_modules without
 * polluting the user's global npm.
 *
 * Usage:
 *   node po_token_launcher.js                 # fresh visitor data
 *   node po_token_launcher.js <visitor_data>  # caller-supplied
 *
 * Output:
 *   stdout: the PO token (one line, no trailing whitespace)
 *   stderr: warnings, partial progress, error messages
 *   exit:   0 on success, 1 on any failure
 *
 * The pyt CLI's --po-token-cmd plumbing reads stdout and takes the
 * last non-empty line, so warning messages on stderr won't pollute
 * the result.
 *
 * Maintenance note: if YouTube changes the BotGuard challenge wire
 * format, this launcher will stop working. Both upstream packages
 * are actively maintained — bumping the npm versions in pyt's
 * doctor installer is usually all that's needed.
 */

(async () => {
  // Lazy-require so an "Cannot find module" error from a missing
  // npm install lands as a clear stderr message instead of a stack
  // trace at process startup.
  let BG;
  let Innertube;
  try {
    ({ BG } = require('bgutils-js'));
    ({ Innertube } = require('youtubei.js'));
  } catch (e) {
    process.stderr.write(
      'po_token_launcher: missing npm dependencies. Reinstall with:\n' +
        '  pyt --doctor --install po-token-generator\n' +
        `(underlying error: ${e && e.message ? e.message : e})\n`,
    );
    process.exit(1);
  }

  // Some Node builds older than 18 lack a global fetch. We refuse to
  // run on those rather than silently producing wrong tokens.
  if (typeof fetch !== 'function') {
    process.stderr.write(
      'po_token_launcher: Node 18+ required for global fetch. ' +
        'Detected node ' + process.version + '\n',
    );
    process.exit(1);
  }

  const argVisitorData = process.argv[2];

  // Probe mode: pyt's doctor calls `pyt-po-token --check` to verify
  // the install. Just confirm the deps loaded (we already required
  // them above) and exit 0 — no network call.
  if (argVisitorData === '--check') {
    process.stdout.write('ok\n');
    process.exit(0);
  }

  // ── visitor data ──────────────────────────────────────────────────────
  // BotGuard ties tokens to a visitor identity. If the caller supplied
  // one (typically scraped from cookies), use it. Otherwise spin up an
  // InnerTube session just to get a fresh value.
  let visitorData = argVisitorData;
  if (!visitorData) {
    try {
      const innertube = await Innertube.create({
        retrieve_player: false,
        enable_session_cache: false,
      });
      visitorData = innertube.session.context.client.visitorData;
    } catch (e) {
      process.stderr.write(
        'po_token_launcher: could not initialize Innertube to fetch ' +
          'visitor data: ' + (e && e.message ? e.message : e) + '\n',
      );
      process.exit(1);
    }
  }

  if (!visitorData) {
    process.stderr.write('po_token_launcher: no visitor data available\n');
    process.exit(1);
  }

  // ── BotGuard challenge ────────────────────────────────────────────────
  // Constant from bgutils-js docs / yt-dlp's bgutil-pot. Identifies
  // the YouTube WebClient request key for the BotGuard endpoint.
  const requestKey = 'O43z0dpjhgX20SCx4KAo';

  const bgConfig = {
    fetch: (url, options) => fetch(url, options),
    globalObj: globalThis,
    identifier: visitorData,
    requestKey,
  };

  let challenge;
  try {
    challenge = await BG.Challenge.create(bgConfig);
  } catch (e) {
    process.stderr.write(
      'po_token_launcher: BG.Challenge.create failed: ' +
        (e && e.message ? e.message : e) + '\n',
    );
    process.exit(1);
  }

  if (!challenge) {
    process.stderr.write('po_token_launcher: empty BotGuard challenge\n');
    process.exit(1);
  }

  // The challenge ships an interpreter program — eval it to register
  // the global hook BotGuard uses to generate the token. `new Function`
  // gives us a fresh scope and avoids touching `eval`'s strict-mode
  // semantics. This is the same pattern bgutil-pot uses upstream.
  if (challenge.script) {
    const interpreter = challenge.script.find((s) => s !== null);
    if (interpreter) {
      new Function(interpreter)();
    }
  } else {
    process.stderr.write(
      'po_token_launcher: warning: BotGuard challenge had no script; ' +
        'token may be invalid\n',
    );
  }

  // ── token ─────────────────────────────────────────────────────────────
  let result;
  try {
    result = await BG.PoToken.generate({
      program: challenge.challenge,
      globalName: challenge.globalName,
      bgConfig,
    });
  } catch (e) {
    process.stderr.write(
      'po_token_launcher: BG.PoToken.generate failed: ' +
        (e && e.message ? e.message : e) + '\n',
    );
    process.exit(1);
  }

  if (!result || !result.poToken) {
    process.stderr.write(
      'po_token_launcher: BG.PoToken.generate returned no poToken\n',
    );
    process.exit(1);
  }

  // The pyt CLI takes the last non-empty stdout line as the token.
  process.stdout.write(result.poToken + '\n');
})().catch((err) => {
  process.stderr.write(
    'po_token_launcher: unhandled error: ' +
      (err && err.message ? err.message : err) + '\n',
  );
  process.exit(1);
});
