# Codex Reset Notice

Uses the public [codex-reset.com API](https://codex-reset.com/developers) to show
a single visible CLI notice on startup, resume, and `/clear`. Compaction does
not trigger a notice. Dates use `dd-mm` and default to Europe/Berlin.
Set `CODEX_RESET_TIMEZONE` to another IANA timezone to change it, for example
`CODEX_RESET_TIMEZONE=America/New_York codex`. Invalid zones report unavailable.

Verified on Codex CLI 0.160.0: the startup hook runs and its visible notice
appears when the session's first prompt is submitted, rather than while the
empty prompt is waiting. The hook itself makes no model calls.

## Recommended installation: Codex plugin

Requirements: a Codex CLI that supports lifecycle hooks and plugins (tested
with 0.160.0), Python 3.9+, and Linux or macOS with system timezone data.
Native Windows is not supported; use WSL. No Python packages or API key needed.

Download the release ZIP, unzip it, and run these commands from its parent:

```sh
codex plugin marketplace add ./codex-reset-notice
codex plugin add codex-reset-notice@codex-reset-notices
```

Restart Codex and use `/hooks` to review and trust **only** the new reset hook.
Make sure hooks are enabled (`[features] hooks = true` in Codex config).
Plugin hooks use `${PLUGIN_ROOT}` so they work regardless of installation path.

Once this repository is hosted on GitHub, users can install without downloading
an archive. Replace `OWNER/REPO` with its actual repository name:

```sh
codex plugin marketplace add OWNER/REPO
codex plugin add codex-reset-notice@codex-reset-notices
```

The repository includes `.agents/plugins/marketplace.json` and the portable
`plugin.json` manifest. The plugin is available through that marketplace;
this package has not been submitted to the public OpenAI directory.

To update from a Git marketplace, refresh it and reinstall the plugin:

```sh
codex plugin marketplace upgrade codex-reset-notices
codex plugin add codex-reset-notice@codex-reset-notices
```

To uninstall the plugin:

```sh
codex plugin remove codex-reset-notice@codex-reset-notices
```

Use one installation method. If switching from the standalone hook below,
first run `python3 install.py --remove` to prevent duplicate notices. Remove
only this package's standalone hook; preserve other hooks.

## Alternative: standalone hook

From the extracted package directory:

```sh
python3 install.py
```

Installation copies the script to `$CODEX_HOME/hooks/codex_reset.py` (default
`~/.codex/hooks/codex_reset.py`) and appends a handler to `hooks.json`. Existing
hooks are preserved and changes get a timestamped backup. Reinstalling is
idempotent. Hooks must be enabled in Codex configuration.

In Codex, open `/hooks`, select the reset hook, review its command, and trust it.
This uses Codex's native trust workflow; the installer does not modify trust
records. After trusting, restart or resume a session to see the notice.
See [Codex hook documentation](https://learn.chatgpt.com/docs/hooks).

Messages, in priority order:

- `Global reset announced for dd-mm on dd-mm.` An unexpired official window
  newer than the last completed reset; windows spanning local dates show a range.
- `Global reset announced on dd-mm; timing unspecified.` An official signal
  with no usable timing.
- `Last reset was on dd-mm.` The latest reset was within the previous 72 hours.
- `No reset planned.` No current official signal or recent completed reset.
- `Reset status unavailable.` Network failure, stale data, or unsupported payload.

Successful notices include the source URL. Forecast probabilities, hints,
banked resets, and personal account quotas do not affect the message. An expired
announcement does not establish that a reset completed. All classification
comes from the independent tracker; there is no OpenAI account access or LLM call.

The script uses Python 3.9+ on Linux or macOS with system timezone data and no packages.
It sends an identifying User-Agent, reads only `GET /api/forecast`, and uses a
locked cache at `$XDG_CACHE_HOME/codex-reset-session-hook` (default `~/.cache/...`).
Requests are limited to once per minute, including after failures; HTTP 429
respects Retry-After. A contending session waits at most 0.4 seconds for the cache
lock. Network I/O has a 3-second timeout; Codex limits the hook to 5 seconds.
Failures return a notice and exit successfully so sessions can continue.

Manual check:

```sh
echo '{"hook_event_name":"SessionStart","source":"startup"}' | python3 codex_reset.py
```

Remove only this hook:

```sh
python3 install.py --remove
```

Removal preserves all other hooks. The cache can optionally be deleted separately.


## Distribution and development

Publish the source directory as a Git repository, or share the generated ZIP.
The license is MIT; third-party reset data remains subject to the
[API provider's terms](https://codex-reset.com/developers). Notices include credit
and requests identify the project. Network traffic contains no session input,
account data, or credentials; it is a GET to the forecast endpoint.

```sh
python3 -m unittest -v
python3 build_release.py
```

This creates `dist/codex-reset-notice-0.1.0.zip` and its SHA-256 file. The archive
contains a single plugin directory, source, tests, marketplace, instructions,
and license. It excludes caches, local installations, trust records, and secrets.
The allowlisted build is reproducible. Bump `plugin.json`'s version for releases.

A local marketplace installation copies the package into Codex's plugin cache.
To distribute changes, build a new archive (or push the source repo), refresh
its marketplace, and reinstall. An extracted local marketplace source should
remain available for later refreshes.

Official references: [plugin packaging](https://developers.openai.com/plugins/build/plugins)
and [hook behavior and trust](https://learn.chatgpt.com/docs/hooks).
