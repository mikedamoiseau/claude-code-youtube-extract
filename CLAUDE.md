# CLAUDE.md — yt-extract plugin

Context for Claude Code when working inside this plugin repository.

## What this plugin is

`yt-extract` is a single-skill Claude Code plugin that extracts structured data
from YouTube videos (metadata, transcript, comments, screenshots) and produces a
Markdown file. The skill orchestrates a Python backend and dispatches one
subagent per URL for transcript summarization.

## Components

| Type   | Path                          | Purpose                                   |
|--------|-------------------------------|-------------------------------------------|
| Skill  | `skills/yt-extract/SKILL.md`  | User-invocable workflow (`/yt-extract`)   |
| Script | `scripts/yt-extract.py`       | Python backend — yt-dlp + ffmpeg + VTT    |

Current version: **1.1.0** — see [CHANGELOG.md](CHANGELOG.md).

## Architectural conventions

- **Script invocation:** Always call the Python script via `${CLAUDE_PLUGIN_ROOT}/scripts/yt-extract.py`. Never use absolute or home-relative paths — the plugin must work regardless of install location.
- **Language:** All user-facing output (SKILL.md body, script stdout, README, CHANGELOG) is in English. Do not mix languages.
- **Section headers:** The Python script emits a fixed set of Markdown section headers (`### Metadata`, `### Description`, `### Chapters`, `### Transcript Info`, `### Transcript`, `### Screenshots`, `### Screenshot Status`, `### Comments`). The SKILL.md subagent prompts parse these verbatim. If you rename a header, update both sides.
- **Sentinel markers:** `FFMPEG_MISSING` and `SCREENSHOTS_ASK_USER` are the only non-content strings inside the `### Screenshots` section. `SCREENSHOTS_ASK_USER` is reacted to by the subagent (missing chapter markers). `FFMPEG_MISSING` is emitted by the Python script for defense-in-depth but is normally unreachable since v1.1.0 — ffmpeg presence is verified in Step 0.5 before subagent dispatch. Do not introduce new sentinels without updating the skill's marker-handling block.
- **Subagent dispatch:** Multi-URL runs dispatch one subagent per URL in parallel (single message, multiple Agent-tool calls). Preserve this pattern — sequential dispatch multiplies latency.

## Out-of-scope changes

- **No hooks, no MCP servers, no other skills.** Keep the plugin to one skill + one script. If functionality must grow, propose splitting into a separate plugin.
- **Do not rename output folder schemes** (`yt-extract_DATE_slug/`) without a migration note in CHANGELOG — downstream users may grep their filesystem for these.

## Testing

No automated tests yet. Verification is manual: install the plugin locally and
run `/yt-extract <real-youtube-url>` with and without `--screenshots`,
`--comments`, `--full-transcript`. Confirm the auto-save folder layout and
Markdown headers match the documented output structure.

## Cross-platform invocation

The skill is expected to run on macOS, Linux, and Windows. Step 0 of SKILL.md
resolves OS-dependent values from lookup tables:

**Python launcher** (substituted as `<PY>` in subagent prompts):

| OS      | `<PY>`    |
|---------|-----------|
| Windows | `python`  |
| macOS   | `python3` |
| Linux   | `python3` |

Never hardcode `python` anywhere in SKILL.md — always use the placeholder.
The Python script itself is fully portable and needs no OS detection.

## Dependencies (install-on-demand)

Since v1.1.0, both system dependencies share a single install-on-demand flow
(SKILL.md Step 0.6). When a dependency is missing, the skill asks the user
whether to install it. When the detected OS has **multiple** valid install
methods for that dependency, the user picks which one. On failure, the user
sees an English error message with a link to the official documentation.

All install commands are written in a **non-interactive form** so the Claude
Code Bash tool — which has no stdin channel — never hangs on a license, a
y/n confirmation, or a sudo password prompt. The user-facing `AskUserQuestion`
dialog shows a short `label` (e.g. `winget`, `pip`), while the skill executes
the exact `command` below.

**yt-dlp** (required — always checked in Step 0.3):

| OS       | Options (label → executed command)                                                                                                     |
|----------|----------------------------------------------------------------------------------------------------------------------------------------|
| Windows  | `pip` → `pip install yt-dlp` **or** `winget` → `winget install yt-dlp --accept-package-agreements --accept-source-agreements --silent --disable-interactivity` (**user picks**) |
| macOS    | `brew` → `brew install yt-dlp`                                                                                                         |
| Linux    | `pip` → `pip install --user yt-dlp` **or** `pipx` → `pipx install yt-dlp` (**user picks**)                                             |

Declining the yt-dlp install prompt aborts the skill with an error listing
both options. Doc URL: `https://github.com/yt-dlp/yt-dlp/wiki/Installation`.

**ffmpeg** (optional, only checked in Step 0.5 when `--screenshots` is set):

| OS       | Options (label → executed command)                                                                                                     |
|----------|----------------------------------------------------------------------------------------------------------------------------------------|
| Windows  | `winget` → `winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements --silent --disable-interactivity`        |
| macOS    | `brew` → `brew install ffmpeg`                                                                                                         |
| Linux    | auto-detect pkg-mgr (see below)                                                                                                        |

**Linux ffmpeg + sudo:** Step 0.6.A probes `sudo -n true 2>/dev/null` first. If
there is no active sudo session (or no `NOPASSWD` rule), the helper does NOT
execute `sudo apt install -y ffmpeg` / `sudo dnf install -y ffmpeg` (it would
block on the password prompt). Instead it shows the exact manual commands to
the user and sets `skip_screenshots = true`. When `sudo -n` succeeds, the
install proceeds via the detected package manager.

Declining the ffmpeg install prompt sets `skip_screenshots` and continues
(no abort). Doc URL: `https://ffmpeg.org/download.html`.

**Design rules:**
1. When SKILL.md prompts the user for install choice, the options list in the
   `AskUserQuestion` call must match the matrix above for the detected OS. If
   you add a new valid install method for an OS, update both this matrix and
   the matrix in SKILL.md Step 0.2.
2. Every executable command in the matrix must be **non-interactive**. No
   prompts for license, confirmation, or sudo password may surface during
   Bash execution — they would hang the skill. Prefer `--user`-scope pip
   installs, winget `--accept-*-agreements` flags, and the `sudo -n` probe
   for any command requiring elevation.
3. **winget exit code 43** ("no upgrade available") means the package is already
   installed. SKILL.md Step 0.6.C treats this the same as exit 0 — proceed to
   Step D (verify). Do NOT treat it as a failed install (Step F). This matters
   because `yt-dlp.FFmpeg` (installed as a winget dependency of yt-dlp) and
   `Gyan.FFmpeg` can both exist, causing redundant installs with exit 43.
