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

Requirements: Codex CLI with plugin and lifecycle-hook support, Python 3.9+,
and Linux or macOS with system timezone data. On Windows, use WSL.

The hook runs on startup, resume, and `/clear`, and skips compaction. The startup
notice appears when you submit the session's first prompt.

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

## Timezone

Dates and 24-hour times default to UTC. To use another timezone:

```sh
CODEX_RESET_TIMEZONE=Europe/Berlin codex
```

## Troubleshooting

**Hook missing from `/hooks`:** update the plugin and start a new session.
If it is still missing, try `codex --no-daemon` for a fresh process, then inspect
`/hooks` again. This flag is optional troubleshooting.

**Hooks disabled:** check whether your Codex configuration disables hooks.
Enable them with `hooks = true` under the existing `[features]` table in
`~/.codex/config.toml`, preserving other settings.

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
