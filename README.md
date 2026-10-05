# Codex CLI Reset Notice

Get a short update about announced global Codex usage resets and resets completed
within the last 72 hours. News comes from [codex-reset.com](https://codex-reset.com/).
No API key, Python packages, or model calls are needed.

## Install

Run these two commands in your terminal, from any directory:

```sh
codex plugin marketplace add pkarstaedt/codex-cli-reset-notice
codex plugin add codex-cli-reset-notice@codex-cli-reset-notices
```

No cloning or ZIP download is required.

1. Start a new Codex session using your usual command, such as `codex` or `codex --yolo`.
2. Run `/hooks` and select **SessionStart**.
3. Select the hook whose command points to `codex-cli-reset-notice` and press **t** to trust it.
4. Start another new session and submit your first prompt to see the notice.

Requirements: Codex CLI with plugin and lifecycle-hook support (tested on
0.160.0), Python 3.9+, and Linux or macOS with system timezone data. On Windows,
use WSL.

The hook runs on startup, resume, and `/clear`, and skips compaction. On Codex
0.160.0, the startup notice appears when you submit the session's first prompt.

## Update

Refresh the marketplace and reinstall to get the latest version:

```sh
codex plugin marketplace upgrade codex-cli-reset-notices
codex plugin add codex-cli-reset-notice@codex-cli-reset-notices
```

Start a new Codex session. Review the reset hook in `/hooks` if prompted.

## Clean reinstall

```sh
codex plugin remove codex-cli-reset-notice@codex-cli-reset-notices
codex plugin marketplace remove codex-cli-reset-notices
codex plugin marketplace add pkarstaedt/codex-cli-reset-notice
codex plugin add codex-cli-reset-notice@codex-cli-reset-notices
```

Then follow the trust steps under **Install**.

## Remove

```sh
codex plugin remove codex-cli-reset-notice@codex-cli-reset-notices
codex plugin marketplace remove codex-cli-reset-notices
```

## Messages

| Case | Notice |
| --- | --- |
| Upcoming reset | `Global Codex usage reset announced for dd-mm on dd-mm. Source: https://codex-reset.com/` |
| Upcoming reset spanning dates | `Global Codex usage reset announced for dd-mm to dd-mm on dd-mm. Source: https://codex-reset.com/` |
| Announcement without timing | `Global Codex usage reset announced on dd-mm; timing unspecified. Source: https://codex-reset.com/` |
| Last reset within 72 hours, none upcoming | `Last Codex usage reset was on dd-mm.` |
| None upcoming or recently completed | `No Codex usage reset planned.` |
| Failed or unavailable check | `Cannot get usage reset news from https://codex-reset.com` |

For upcoming resets, the final “on dd-mm” is the announcement date. Dates default
to Europe/Berlin. To use another timezone, set `CODEX_RESET_TIMEZONE`:

```sh
CODEX_RESET_TIMEZONE=America/New_York codex
```

Forecast probabilities, hints, banked reset grants, and personal account quotas
are excluded. An expired announcement does not establish that a reset completed.

## Troubleshooting

**Hook missing from `/hooks`:** update first. Version 0.1.0 installed but did not
expose hooks on Codex 0.160.0; this was fixed in 0.1.1. If it is still missing,
try `codex --no-daemon` for a fresh process, then inspect `/hooks` again.
`--no-daemon` is optional troubleshooting, not a requirement of this plugin.

**Hooks disabled:** check whether your Codex configuration disables hooks.
Enable them with `hooks = true` under the existing `[features]` table in
`~/.codex/config.toml`, preserving other settings.

**Duplicate notices:** if you previously installed the standalone hook, remove
it with `python3 install.py --remove` from its source directory. Use one
installation method.

## Alternative installation

<details>
<summary>ZIP or standalone installation</summary>

Download and extract a ZIP from [Releases](https://github.com/pkarstaedt/codex-cli-reset-notice/releases).
To install it as a local marketplace, run from the extracted directory's parent:

```sh
codex plugin marketplace add ./codex-cli-reset-notice
codex plugin add codex-cli-reset-notice@codex-cli-reset-notices
```

Follow the trust steps under **Install**. Keep the extracted directory available
for later refreshes. Git marketplace upgrades apply to Git installs; to update a
local ZIP install, extract the new release and reinstall from that local source.

Alternatively, run `python3 install.py` from the extracted package to install a
standalone user hook. It copies the script to `$CODEX_HOME/hooks/codex_reset.py`
(default `~/.codex/hooks/codex_reset.py`) and adds a handler to `hooks.json`,
preserving other hooks and backing up configuration changes. Trust it through
`/hooks`. Remove it with `python3 install.py --remove`.

</details>

## Data and development

The hook reads only the public `GET /api/forecast` endpoint and identifies itself
with a User-Agent. It sends no account credentials or session input. It caches
responses for 60 seconds, respects HTTP 429 Retry-After, and reports unavailable
status when checks fail. The cache lives under
`$XDG_CACHE_HOME/codex-reset-session-hook` (default `~/.cache/...`).

The code is MIT-licensed; reset data remains subject to the
[provider's terms](https://codex-reset.com/developers).

From a source checkout:

```sh
python3 -m unittest -v
python3 verify_plugin.py
python3 build_release.py
```

The release builder creates a ZIP and SHA-256 checksum under `dist/`, using the
version in `.codex-plugin/plugin.json`. It excludes caches, local installations,
trust records, and secrets. Native verification checks that Codex discovers the
SessionStart hook and marks it as awaiting trust.

Official references: [plugin packaging](https://developers.openai.com/plugins/build/plugins)
and [hook behavior and trust](https://learn.chatgpt.com/docs/hooks).
