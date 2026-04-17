# Changelog

All notable changes to `yt-extract` are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] — 2026-04-17

Unified install-on-demand flow for both system dependencies (yt-dlp and ffmpeg),
with per-OS install commands, user choice when multiple install methods are valid,
and actionable error messages that link to the official documentation.

### yt-extract skill

#### Added
- yt-dlp install-on-demand: when yt-dlp is missing, the skill now offers to install it via `AskUserQuestion` instead of hard-aborting. On Windows and Linux, the user picks between valid options (Windows: pip vs winget; Linux: pip vs pipx). macOS runs `brew install yt-dlp` behind a confirmation.
- ffmpeg install check moved to Step 0.5 — fires **only** when `--screenshots` is requested, and **before** subagent dispatch. Multi-URL runs now produce exactly one ffmpeg prompt instead of one per subagent.
- Install-dependency helper (Step 0.6) — shared flow for both deps: ask → run → verify → on verification failure show "restart your terminal" hint and abort with doc link.
- Doc URLs surfaced in every failure path: `https://github.com/yt-dlp/yt-dlp/wiki/Installation` and `https://ffmpeg.org/download.html`.
- Linux ffmpeg install auto-detects apt vs dnf via `command -v` (no user prompt for distro-determined choice).
- **Non-interactive install commands across the board** so Bash calls never hang on a license, confirmation, or sudo password prompt:
  - Windows winget commands now include `--accept-package-agreements --accept-source-agreements --silent --disable-interactivity`.
  - Linux pip for yt-dlp is `pip install --user yt-dlp` (user-scope, no sudo).
  - Linux ffmpeg install is gated by a `sudo -n true` probe: if no active sudo session exists, the helper does NOT attempt the install (avoids the password hang) and instead shows the exact manual command for the user to run, then sets `skip_screenshots`.
- Install-option entries in the Step 0.2 matrix now use a `{label, command}` pair: the short label (e.g. `winget`, `pip`) appears in `AskUserQuestion`, while the full non-interactive command is what the helper actually executes.
- `--check` flag — verify dependencies without doing any video extraction. Runs Step 0 (OS detection, `yt-dlp` check, optional `ffmpeg` check when combined with `--screenshots`), prints a readiness report, and stops. URLs are ignored in check mode. Primary use case: first-time install verification and the Windows shell-restart retry loop, without generating Markdown files or fetching video data.
- **Chapter-aligned screenshot embedding.** When `--screenshots` is taken at chapter markers (default behavior when no explicit timestamps are passed), screenshots are now embedded directly below each entry in the `## Chapters` section of the saved Markdown — one image per chapter line, in context. The standalone `## Screenshots` section is suppressed in this case to avoid duplication. Custom-timestamp screenshots (`--screenshots 0:30,2:15,...`) still render as a standalone list because they cannot be mapped to chapters.
- **"What next?" follow-up invitation.** Every successful run ends with a concise, context-aware block that lists 3–4 concrete follow-up queries (extract tools as a checklist, write a blog draft, drill into a specific chapter, translate the summary) plus re-run hints for any flags not used in the current invocation (`--comments`, `--full-transcript`, `--screenshots`) and a `/yt-extract url1 url2` compare hint for single-URL runs. Makes it obvious that the extracted transcript + summary remain in the Claude Code session's context and can be queried further without re-running. The block is suppressed in `--check` mode and on error paths.

#### Changed
- yt-dlp missing no longer silently aborts with a one-line error — it now runs through the full install-on-demand helper.
- Subagent prompts (default and `--full-transcript`) no longer handle `FFMPEG_MISSING` — Step 0.5 guarantees ffmpeg presence or skip-screenshots before dispatch. The sentinel is still emitted by the Python script as defense-in-depth but should not be reached in normal flow.
- Declining the ffmpeg install prompt now sets a `skip_screenshots` flag and continues (previously: continue silently). The final output notes why screenshots were skipped.

#### Fixed
- Step 0.6.C now treats winget exit code `43` ("no upgrade available" — package already installed) the same as exit 0, proceeding to Step D for PATH verification. Previously, exit 43 would have incorrectly triggered Step F ("Failed to install") and aborted the skill. This matters because `winget install yt-dlp` pulls `yt-dlp.FFmpeg` as a dependency — when the user later accepts a `Gyan.FFmpeg` install, winget reports "already installed" with exit 43, and without the fix the skill would misread this as a failure.

- @mucky

## [1.0.0] — 2026-04-16

Initial public release. Migrated from the private `yt-analyze` command to a distributable
Claude Code plugin.

### yt-extract skill

#### Added
- `/yt-extract <url>` skill (replaces `/yt-analyze`)
- Structured transcript summary: Core Thesis, Main Points, Tools & Resources, Key Quotes & Numbers
- Raw transcript mode via `--full-transcript`
- Top-10 comments via `--comments`
- Screenshot extraction via `--screenshots` (chapter markers or custom timestamps)
- Multi-video mode (2-3 URLs) with parallel subagent dispatch and cross-video synthesis
- Auto-save into dated folders with YAML frontmatter and organized screenshots
- `--no-save` flag to opt out of auto-save
- `FFMPEG_MISSING` and `SCREENSHOTS_ASK_USER` sentinel markers for Claude-mediated resolution
- `allowed-tools` scoping in frontmatter: `Bash, Agent, Write, Read, AskUserQuestion`
- `<user_request>` wrapper around `$ARGUMENTS` for prompt-injection safety
- URL filter accepts `youtube.com`, `www.youtube.com`, `m.youtube.com`, `youtu.be`

- OS-aware script invocation: Windows uses `python`, macOS/Linux uses `python3` — resolved in Step 0 and substituted via `<PY>` placeholder
- OS-aware ffmpeg install prompt: `winget install Gyan.FFmpeg` (Windows) / `brew install ffmpeg` (macOS) / `apt install ffmpeg` or `dnf install ffmpeg` (Linux)
- yt-dlp install hint also OS-specific (brew / pip+pipx / pip+winget)
- Post-save confirmation reads the screenshot count from the script's `### Screenshot Status` output instead of running a filesystem `Measure-Object` pipeline — prevents noisy PowerShell permission prompts on Windows

#### Changed
- Renamed: `yt-analyze` → `yt-extract`
- Output folder name: `yt-analyze_DATE_slug/` → `yt-extract_DATE_slug/`
- Script path: `~/.claude/scripts/yt-extract.py` → `${CLAUDE_PLUGIN_ROOT}/scripts/yt-extract.py`
- All user-facing output translated from German to English

### yt-extract.py (backend)

#### Added
- Chapter extraction and output
- VTT parser with timestamp preservation for screenshot alignment inside transcripts
- ffmpeg availability check with sentinel output
- `screenshot_dir:` hint inside the `### Screenshots` section for auto-save handlers

#### Changed
- All section headers translated from German to English (`### Metadata`, `### Description`, `### Chapters`, `### Transcript`, `### Comments`, `### Screenshot Status`)
- All warning and status messages translated to English

- @mucky
