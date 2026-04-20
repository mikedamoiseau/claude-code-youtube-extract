# Changelog

All notable changes to `yt-extract` are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] — 2026-04-20

Script-owned output folder layout and deterministic progress output. The intermediate `yt-screenshots/` staging folder is gone — the Python script now writes directly into the final `yt-extract_<DATE>_<slug>/` folder, with screenshots in a sibling `screenshots/` subfolder. The skill only orchestrates `--output-base` and saves the consolidated markdown.

### yt-extract.py (backend)

#### Added
- `--output-base <dir>` CLI flag (default: current directory). The script creates `<base>/yt-extract_<DATE>_<slug>/` and writes screenshots into `<base>/yt-extract_<DATE>_<slug>/screenshots/` directly. No more staging, no moves, no rmdir cleanup.
- `--force` CLI flag — overwrite an existing target folder. Without it, the script exits with code `2` and emits `FOLDER_EXISTS: <path>` on stderr so the caller can ask the user.
- **Progress stage markers on stderr.** The script emits lines like `[1/5] Fetching metadata...`, `[2/5] Downloading transcript...`, `[3/5] Extracting 7 screenshots...`, flushed immediately. Stage count is adaptive — `[1/3]` for metadata + transcript + output, `[1/5]` when `--comments` and `--screenshots` are both set, etc. Visible in the Bash tool output during runs.
- **`OUTPUT_FOLDER: <path>` trailer** as the final stdout line of every successful run. The skill parses it to decide where to write the consolidated markdown. Uses forward slashes so it is stable across platforms.

#### Changed
- `extract_screenshots()` signature: takes `out_dir` directly instead of constructing `yt-screenshots/<slug>` from `slug`. Returns `(timestamp, filename)` tuples instead of `(timestamp, full_path)` — callers build the markdown-relative path themselves.
- The `### Screenshots` section no longer emits a `screenshot_dir:` line. Image paths in the markdown are now plain relative paths (`screenshots/NNN_HHmmss.png`) resolved against the folder where the MD lives.
- The script now creates the target folder unconditionally after metadata fetch (before transcript/screenshot work). The collision guard runs before creation, so re-runs without `--force` fail cleanly.

### yt-extract skill

#### Added
- `--output-base` and `--force` are passed by the skill automatically — users do not need to specify them. `--output-base .` for single-URL runs, `--output-base ./yt-extract_<DATE>_<N>-videos` for 2–3-URL runs (parent folder created before dispatch).
- **Narration block before subagent dispatch.** For 1 URL: `Extracting from <url>. This typically takes 30–60 seconds...`. For 2–3 URLs: `Dispatching <N> parallel extractions...`. As each subagent returns, a one-line status is surfaced.
- **Progress surfacing in subagent prompts.** Subagents are now instructed to forward the `[k/N]` stage markers they see on stderr as one-line updates, so the main chat keeps showing motion during long-running extractions.
- **FOLDER_EXISTS handling.** If the script exits with code 2 and `FOLDER_EXISTS: <path>` is on stderr, the subagent asks the user via `AskUserQuestion` and re-runs with `--force`. For multi-URL runs, the skill also checks the parent folder upfront and asks before dispatching any subagents.
- Parent folder for multi-URL runs is created explicitly by the skill before subagent dispatch (`mkdir -p ./yt-extract_<DATE>_<N>-videos`).

#### Changed
- **Auto-save flow radically simplified.** The old 8-step flow (mkdir → move screenshots → rewrite paths → rmdir staging) collapses to: read `OUTPUT_FOLDER:` from subagent output → prepend YAML frontmatter → write MD. For multi-video consolidation, the only path rewrite is prefixing each video's paths with its per-video folder name. No filesystem moves.
- **`--no-save` semantics.** Script always creates the target folder (required for screenshots + `OUTPUT_FOLDER:` trailer). When the user declines saving at the end, the skill now removes the folder with `rm -rf` instead of leaving it orphaned.
- **Multi-URL folder layout.** Each video lives in its own per-video folder inside the parent (`./yt-extract_DATE_N-videos/yt-extract_DATE_slug1/screenshots/`), instead of sharing a flat `./yt-extract_DATE_N-videos/screenshots/slug1/` layout. Each per-video folder is now a complete, standalone extraction unit.

#### Removed
- The intermediate `yt-screenshots/` top-level folder and all related staging / move / cleanup logic.
- The `screenshot_dir:` line from the `### Screenshots` section — redundant with the new `OUTPUT_FOLDER:` trailer.
- The "Shell-command hygiene" warning block in Step 3 that applied to the old `mv` + `Measure-Object` flow.

#### Migration notes
- Standalone script users (`python scripts/yt-extract.py <url>`) will see a new folder `./yt-extract_<DATE>_<slug>/` in their CWD where previously only `yt-screenshots/<slug>/` appeared. This is the intended new behavior.
- Multi-URL consolidated markdown references screenshots via a deeper path (`yt-extract_DATE_slug1/screenshots/...` instead of `screenshots/slug1/...`). Old saved markdown files still render correctly because they use relative paths — only the relative structure inside new folders changes.
- In the rare multi-URL + FOLDER_EXISTS race (two subagents hit a collision simultaneously), users may see more than one `AskUserQuestion` prompt in parallel. Known limitation; acceptable for now.

- @mucky

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
