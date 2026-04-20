---
name: yt-extract
description: "Extract and analyze YouTube videos — transcript, metadata, screenshots, comments. Use when user says /yt-extract or wants to analyze 1-3 YouTube URLs with optional summary, comments, and screenshot extraction."
user-invocable: true
disable-model-invocation: true
argument-hint: "<youtube-url> [url2] [url3] [--screenshots [timestamps]] [--comments] [--full-transcript] [--no-save] | --check [--screenshots]"
allowed-tools: "Bash, Agent, Write, Read, AskUserQuestion"
---

Analyze the YouTube URL(s) from: <user_request>$ARGUMENTS</user_request>

## Step 0 — Preparation

### 0.1 Detect the host OS

Determine the OS from the active environment / system prompt — you do not need to run a command. Store the value as `<OS>` and use it to resolve every OS-specific lookup below.

**Python launcher** by OS (used when building subagent prompts — substitute `<PY>` before dispatch):

| OS       | `<PY>`    |
|----------|-----------|
| Windows  | `python`  |
| macOS    | `python3` |
| Linux    | `python3` |

If OS detection fails, default to `<PY> = python3` (POSIX fallback). Never dispatch a subagent prompt that still contains a literal `<PY>` token.

### 0.2 Dependency install matrix

The skill offers install-on-demand for both dependencies. Each dependency has a per-OS list of valid install commands. When the list has **multiple** entries, the skill asks the user which to run. When the list has **one** entry, it runs that command directly (still behind a confirmation prompt).

**Each entry has two forms:**
- **label** — short, user-friendly string shown in the `AskUserQuestion` dialog (e.g., `winget`, `pip`, `apt`).
- **command** — the exact non-interactive command line the skill executes via Bash. These commands are crafted to never block on a license prompt, a confirmation prompt, or a sudo password prompt under the Claude Code Bash tool, which has no stdin channel.

**yt-dlp install options:**

| OS       | Options (label → exact executed command)                                                                                               |
|----------|----------------------------------------------------------------------------------------------------------------------------------------|
| Windows  | `pip` → `pip install yt-dlp` **or** `winget` → `winget install yt-dlp --accept-package-agreements --accept-source-agreements --silent --disable-interactivity`  (→ **ask user**) |
| macOS    | `brew` → `brew install yt-dlp`                                                                                                         |
| Linux    | `pip` → `pip install --user yt-dlp` **or** `pipx` → `pipx install yt-dlp`  (→ **ask user**)                                            |

**ffmpeg install options:**

| OS       | Options (label → exact executed command)                                                                                               |
|----------|----------------------------------------------------------------------------------------------------------------------------------------|
| Windows  | `winget` → `winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements --silent --disable-interactivity`        |
| macOS    | `brew` → `brew install ffmpeg`                                                                                                         |
| Linux    | auto-detect pkg-mgr (see note below), OR abort with manual-install instruction if `sudo` would prompt                                  |

**Linux ffmpeg — sudo handling (important):** `apt` and `dnf` both require root. Before attempting to run the install command, the helper probes `sudo -n true 2>/dev/null`. If that succeeds (active sudo session or passwordless sudo), the helper runs `sudo apt install -y ffmpeg` or `sudo dnf install -y ffmpeg`. If `sudo -n true` fails, the helper **does not execute** the install (it would hang on the password prompt). Instead it aborts with an English error message that shows the exact manual command for the user to run in their own terminal, plus the ffmpeg doc URL. If neither `apt` nor `dnf` is present, abort with doc link regardless of sudo state.

**Why these exact flags:**
- `--accept-package-agreements` / `--accept-source-agreements` (winget): auto-accept the third-party package and winget-source license terms. Without these flags, winget opens an interactive `y/n` prompt on first install of each source — which blocks the Bash tool indefinitely.
- `--silent` / `--disable-interactivity` (winget): suppresses the installer UI and aborts if any remaining interactive prompt appears, so the skill fails fast instead of hanging.
- `--user` (Linux `pip`): installs into the user-scope site-packages directory — avoids needing root and the resulting sudo-password prompt.
- `-y` (apt/dnf): auto-confirms the package install. Not sufficient by itself on Linux because `sudo` is still outside this scope — hence the `sudo -n` probe.

**Official doc URLs (used in error messages):**
- yt-dlp: `https://github.com/yt-dlp/yt-dlp/wiki/Installation`
- ffmpeg: `https://ffmpeg.org/download.html`

### 0.3 Check yt-dlp (always)

Run:
```bash
yt-dlp --version 2>&1
```

**If yt-dlp is present:** continue to 0.4.

**If yt-dlp is missing:** invoke the **install-dependency helper** (see 0.6) with:
- `dep_name = "yt-dlp"`
- `options = yt-dlp install options for <OS>`
- `doc_url = "https://github.com/yt-dlp/yt-dlp/wiki/Installation"`
- `on_decline = "abort"`
- `verify_cmd = "yt-dlp --version"`

If the helper aborts, stop processing. If it succeeds, continue.

### 0.4 Parse URLs and flags

**Parse URLs:**
Split $ARGUMENTS on whitespace/newlines. Keep only strings starting with `https://www.youtube.com/`, `https://youtube.com/`, `https://m.youtube.com/`, or `https://youtu.be/`. Take at most the first 3 URLs. If more than 3 were found, show: "Only the first 3 URLs will be processed."

**Parse flags:**
- `--comments` → fetch top comments (slow, therefore optional)
- `--full-transcript` → return the raw transcript instead of a summary
- `--screenshots` → extract screenshots at chapter markers (requires ffmpeg)
- `--screenshots 0:30,2:15,5:00` → extract screenshots at specific timestamps
- `--no-save` → disable auto-save (default: analysis is auto-saved as an MD file)
- `--check` → verify dependencies only, no extraction. Runs Step 0 (yt-dlp check, and ffmpeg check when combined with `--screenshots`), prints a readiness report, and stops. URLs are ignored in check mode.

### 0.5 Check ffmpeg (only when `--screenshots` is set)

If `--screenshots` was **not** parsed, skip this step entirely.

**Narration:** Before running the check, say in chat: "Verifying ffmpeg before screenshot extraction..." — so the user sees what is happening.

Otherwise, run:
```bash
ffmpeg -version 2>&1
```

**If ffmpeg is present:** continue to Step 1.

**If ffmpeg is missing:** invoke the install-dependency helper (see 0.6) with:
- `dep_name = "ffmpeg"`
- `options = ffmpeg install options for <OS>`
- `doc_url = "https://ffmpeg.org/download.html"`
- `on_decline = "skip_screenshots"` (set an internal `skip_screenshots = true` flag and continue; do NOT abort)
- `verify_cmd = "ffmpeg -version"`

When `skip_screenshots` is set, **omit the `--screenshots` flag from the subagent's script invocation** and make a note in the final output that screenshots were skipped because ffmpeg was not installed.

This Step-0 check replaces the per-subagent `FFMPEG_MISSING` handling. It also prevents parallel install prompts on multi-URL runs — exactly **one** ffmpeg prompt fires before subagent dispatch, regardless of URL count.

### 0.6 Install-dependency helper (shared flow)

This is the common flow invoked by 0.3 and 0.5. Inputs:
- `dep_name` — display name (e.g. `"yt-dlp"` or `"ffmpeg"`)
- `options` — ordered list of `{label, command}` pairs from the 0.2 matrix for the detected OS. `label` is the short user-facing string (e.g. `"winget"`). `command` is the full non-interactive Bash line to execute.
- `doc_url` — official-docs link for manual install instructions
- `on_decline` — `"abort"` (yt-dlp) or `"skip_screenshots"` (ffmpeg)
- `verify_cmd` — command that must exit 0 after a successful install

**Step A — Pre-flight check (Linux ffmpeg only).**

When running on Linux AND the dep is ffmpeg AND the detected command uses `sudo`: probe `sudo -n true 2>/dev/null`. If that fails (no active sudo session, no `NOPASSWD`), skip Step A's AskUserQuestion entirely and go straight to Step B's abort path with this message:

```
ffmpeg is not installed, and installing it on Linux requires sudo.

I cannot run `sudo` from here without blocking on the password prompt. Please install ffmpeg manually in your own terminal:

  - sudo apt install -y ffmpeg    (Debian/Ubuntu)
  - sudo dnf install -y ffmpeg    (Fedora/RHEL)

Then re-run /yt-extract.

Docs: https://ffmpeg.org/download.html
```

Set `skip_screenshots = true` (because `on_decline == "skip_screenshots"` for ffmpeg) and return to the caller. The user is already informed; no second prompt needed.

For all other cases, continue to Step A's regular flow below.

**Step A — Ask the user.**

If `options.length == 1`:
```
AskUserQuestion
  question: "[dep_name] is not installed. Install with `[options[0].label]` (`[options[0].command]`)?"
  options:
    - "Yes, install it"
    - "No"
```

If `options.length > 1`:
```
AskUserQuestion
  question: "[dep_name] is not installed. Which install method should I use?"
  options:
    - one option per entry in `options` — label = `options[i].label`; description = `"Runs: [options[i].command]"`
    - "No, do not install"
```

**Step B — On decline.**

- If `on_decline == "abort"`:
  ```
  [dep_name] is required but was not installed.

  Install it manually with one of:
    - [options[0].command]
    - [options[1].command]   (if present)

  Then re-run /yt-extract.

  Docs: [doc_url]
  ```
  **Abort the skill.**

- If `on_decline == "skip_screenshots"`: set `skip_screenshots = true` and return to the caller (no abort).

**Step C — On accept: run the chosen install command.**

Execute `options[chosen_index].command` via Bash exactly as written (the command already contains all non-interactive flags). Capture exit code and stderr.

**Winget "already installed" special case:** If the command is a `winget` command and the exit code is `43` (package already installed, no upgrade available), treat this as exit code `0` — the package is present on the system. Proceed to Step D to verify PATH availability.

**Step D — Verify.**

Run `verify_cmd`. If it succeeds (exit 0), the install worked — return success to the caller.

**Step E — On verification failure (install command returned exit 0, or winget exit 43, but binary still not on PATH).**

```
Installation completed but [dep_name] is still not on PATH.

This usually means the shell hasn't picked up the new PATH entry yet.
Please restart your terminal and re-run /yt-extract.

If the problem persists, install [dep_name] manually:
  - [options[0].command]
  - [options[1].command]   (if present)

Docs: [doc_url]
```

**Abort the skill** regardless of `on_decline` — a half-installed dep is not a "skip screenshots" situation, it's broken.

**Note:** Step E is the expected behavior on Windows+winget after a first-time install — winget updates the user PATH but the current shell's PATH is stale. The message is designed to guide the user through the one-time restart, not to signal a broken install.

**Step F — On install command itself failing (non-zero exit).**

```
Failed to install [dep_name].

Command: [chosen command]
Exit code: [N]
Error: [first line of stderr]

Please install [dep_name] manually:
  - [options[0].command]
  - [options[1].command]   (if present)

Docs: [doc_url]
```

**Abort the skill.**

### 0.7 Short-circuit when `--check` is set

If the `--check` flag was parsed, print a readiness report and **stop**. Do NOT proceed to Step 1 or dispatch any subagents. Ignore any URLs the user passed.

Capture the current tool versions:

```bash
yt-dlp --version
```

If `--screenshots` was also set, also capture:

```bash
ffmpeg -version 2>&1 | head -1
```

Then output:

```
✅ Dependencies ready:
  - yt-dlp: [yt-dlp version string]
  - ffmpeg: [ffmpeg first line — only if --screenshots was set; omit otherwise]

Ready to extract. Run `/yt-extract <url>` to analyze a video.
```

**Stop here.** `--check` is for verifying install only — it does not produce a Markdown file, does not fetch any video data, and does not dispatch subagents.

---

## Step 1 — Dispatch subagents

**IMPORTANT: Use the Agent tool (subagent_type: general-purpose, model: "sonnet") for each URL. With 2-3 URLs, dispatch all in parallel (in a single message with multiple Agent-tool calls).**

### Narration before dispatch

Before the Agent-tool call(s), say in chat what is about to happen. One short line is enough — the user has no other signal that work has started.

- **1 URL:** `Extracting from <shortened URL or known title>. This typically takes 30–60 seconds...`
- **2-3 URLs:** `Dispatching <N> parallel extractions...`

As each subagent returns, announce its result on one line (`URL <i>/<N> done: <OUTPUT_FOLDER>` or similar). This, combined with the `[k/N]` stage markers the Python script emits on stderr, gives the user continuous feedback even when an individual run runs long.

### `--output-base` resolution

Every subagent invocation must include `--output-base <path>`. The value depends on URL count:

- **1 URL:** `--output-base "."` — script creates `./yt-extract_[DATE]_[slug]/` directly in CWD.
- **2-3 URLs:** `--output-base "./yt-extract_[DATE]_[N]-videos"` — **before** dispatching subagents, create this parent folder with `mkdir -p`. Each subagent's script then writes into `./yt-extract_[DATE]_[N]-videos/yt-extract_[DATE]_[slug]/`.

When the parent folder (multi-URL case) already exists, ask the user via AskUserQuestion "Folder `<path>` already exists. Overwrite?" **before** creating it. On "yes": remove the existing folder (`rm -rf`) and re-create, then dispatch subagents **with `--force`** appended to each script invocation so per-video collisions inside the parent are also overwritten silently. On "no": abort the skill with a short message.

### FOLDER_EXISTS handling (per-subagent)

If a subagent reports that the Python script exited with code 2 and stderr contained `FOLDER_EXISTS: <path>`, the per-video folder already exists from a previous run. The subagent prompt instructs it to resolve this via its own AskUserQuestion and re-run with `--force`. In the rare multi-URL case where multiple subagents hit this simultaneously, multiple prompts may surface — acceptable for now (documented in CHANGELOG under "Known limitations").

### When --full-transcript is NOT set (default):

Each subagent gets this prompt (substitute URL, flags, and `--output-base` path per Step 1 resolution rules above):

---

Extract all data for this YouTube video and summarize the transcript.

1. Run:
```bash
<PY> "${CLAUDE_PLUGIN_ROOT}/scripts/yt-extract.py" "[URL]" --output-base "[OUTPUT_BASE]" [--force if the orchestrator said so] [--comments if requested] [--screenshots if requested, with optional timestamps]
```

**Progress surfacing (stderr stage markers):** The Python script emits lines like `[1/5] Fetching metadata...`, `[2/5] Downloading transcript...`, `[3/5] Extracting 7 screenshots...` on stderr, flushed immediately. When each stage completes, surface the marker as a one-line update in your returned message so the user sees forward motion during long runs.

**FOLDER_EXISTS handling (exit code 2):** If the Bash command exits with code 2 AND stderr contains `FOLDER_EXISTS: <path>`, the target folder already exists. Ask the user via AskUserQuestion: `Folder "[path]" already exists. Overwrite?` with options "Yes, overwrite" and "No, abort". On Yes: re-run the exact same Bash command with `--force` appended. On No: return a short message "User declined overwrite for [URL]" and stop this subagent (the orchestrator will treat it as a failed extraction).

2. **Check the `### Screenshots` section for `SCREENSHOTS_ASK_USER`:**
   - If `SCREENSHOTS_ASK_USER` appears in the `### Screenshots` section: The video has no chapter markers. Ask the user via AskUserQuestion: "This video has no chapter markers. How should screenshots be taken?" with options: A) "Evenly distributed (1 per 2 min, max 10)" B) "Enter manual timestamps". On A: compute timestamps based on `video_duration` from the `### Screenshots` section, build a comma-separated list, re-run the script with `--screenshots T1,T2,T3,...` **and `--force`** (the first run already created the target folder). On B: wait for user input, re-run with the entered timestamps and `--force`. IMPORTANT: When re-running, DISCARD the first run's output entirely and replace it with the new one.
   - `FFMPEG_MISSING` should not appear at this stage — Step 0.5 already verified ffmpeg presence before dispatch. If it does appear (defense-in-depth), treat it as a hard error and surface the message from Step 0.6.E to the user.

3. Return the **Metadata**, **Description**, **Chapters** (if present), and **Comments** sections UNCHANGED.

4. Return the **Screenshots** and **Screenshot Status** sections (if present) UNCHANGED — they contain relative image paths (like `screenshots/NNN_HHmmss.png`) and error/success messages that must be preserved.

**Preserve the trailing `OUTPUT_FOLDER: <path>` line** that the script emits after the Comments section. The orchestrator parses this to decide where to write the consolidated markdown. Return it verbatim at the end of your response.

5. Replace the raw transcript with a **STRUCTURED SUMMARY**:
   - Keep the **Transcript Info** (auto-generated/manual, language) as the first line
   - If no transcript is available: return only the note "No transcript available."
   - Build the summary with exactly this structure:

```
### Transcript Info
[auto-generated/manual, language — taken from the script output]

### Transcript Summary

#### Core Thesis
[1-2 sentences: What is the video about? What is the central claim?]

#### Main Points
[Numbered list of the most important arguments/insights, 1-2 sentences each. Cover all essential content — the goal is that the user should not need to watch the video again.]

#### Tools & Resources Mentioned
[All concrete tools, libraries, links, repos, products named in the video — with URL if included in transcript or description]

#### Key Quotes & Numbers
[Concrete metrics, statistics, verbatim statements that are particularly relevant or quotable]
```

   - Language of the summary = language of the transcript
   - DETAILED enough that watching the video again is unnecessary
   - If screenshots are embedded in the transcript (image references): REMOVE them from the summary — the Screenshots section shows them separately.

---

### When --full-transcript IS set:

Each subagent gets this prompt (substitute URL, flags, and `--output-base` path per Step 1 resolution rules above):

---

Extract all data for this YouTube video. Return exclusively the output of the Python script — no additional explanation, no preamble, no wrapper.

Run exactly this one command:
```bash
<PY> "${CLAUDE_PLUGIN_ROOT}/scripts/yt-extract.py" "[URL]" --output-base "[OUTPUT_BASE]" [--force if the orchestrator said so] [--comments if requested] [--screenshots if requested, with optional timestamps]
```

**Progress surfacing:** The script emits `[k/N]` stage markers on stderr throughout the run. Surface each one as a one-line update so the user sees forward motion.

**FOLDER_EXISTS handling (exit code 2):** If the command exits with code 2 AND stderr contains `FOLDER_EXISTS: <path>`, ask the user via AskUserQuestion: `Folder "[path]" already exists. Overwrite?` with options "Yes, overwrite" and "No, abort". On Yes: re-run with `--force` appended. On No: return "User declined overwrite for [URL]" and stop.

**Check the `### Screenshots` section for `SCREENSHOTS_ASK_USER`** (identical to default mode): ask user for timestamps, re-run the script **with `--force` appended** (first run already created the folder), discard the first output entirely and replace it with the new one. `FFMPEG_MISSING` is handled in Step 0.5 before dispatch and should not appear here.

Return the complete script output as the answer — including the trailing `OUTPUT_FOLDER: <path>` line, which the orchestrator needs to locate the target folder. Add nothing, omit nothing. Screenshot image references inside the transcript and the `### Screenshot Status` section are preserved.

---

## Step 2 — Format and output the results

Once all subagents have finished, parse the markdown blocks from the results and format the output:

### With exactly 1 URL:

```
## [Title]
**Channel:** [Channel] | **Date:** [YYYY-MM-DD] | **Duration:** [HH:MM:SS] | **Views:** [n] | **Likes:** [n]

---

## Description
[from subagent — keep chapter markers and relevant links]

---

## Chapters
[If present: list of chapter markers with timestamps.]
[**Chapter-aligned screenshot embedding:** If `--screenshots` was set AND the number of screenshots in the subagent's `### Screenshots` section equals the number of chapter markers AND each screenshot's timestamp matches a chapter timestamp → embed the screenshot IMMEDIATELY below its matching chapter line, indented with 2 spaces. Use the image reference from the subagent's `### Screenshots` section verbatim. Format:]

```
- [0:00] Intro

  ![Intro](screenshots/001_00m00s_intro.png)

- [2:15] Docker install

  ![Docker install](screenshots/002_02m15s_docker.png)
```

[If chapters are not present: omit the section entirely.]

---

## Transcript Summary
[If auto-generated: > ℹ️ Auto-generated subtitles ([language])]
[If livestream: > ℹ️ Livestream recording]
[If no transcript: > ❌ No transcript available.]

[Structured summary: Core Thesis, Main Points, Tools & Resources, Quotes & Numbers]

> 💡 Full transcript available — re-run with `--full-transcript` if needed.

---

## Screenshots
[**Conditional rendering:**]
[• If screenshots are chapter-aligned (already embedded under `## Chapters` above): OMIT this section entirely to avoid duplication. The chapter embedding replaces it.]
[• If screenshots are NOT chapter-aligned (custom timestamps, or no chapters, or count mismatch): render the standalone list with image references and timestamps — from the subagent's `### Screenshots` section UNCHANGED.]
[• If `--screenshots` was requested but produced nothing: > ℹ️ No screenshots extracted.]
[• If `--screenshots` was not requested: omit the section.]

## Screenshot Status
[If present: success/error messages from subagent UNCHANGED — keep the `"N screenshots requested, M successfully extracted"` line even when the `## Screenshots` section above was suppressed due to chapter embedding.]
[If `--screenshots` was not requested: omit the section.]

---

## Top Comments
[If present: numbered list]
[If skipped: > ℹ️ Comments not requested. Enable with `--comments`.]
[If error: > ℹ️ Comments could not be loaded.]
```

**With --full-transcript:** the section is called `## Transcript` and shows the raw prose with embedded screenshot references (as before). No hint about --full-transcript needed.

### With 2 or 3 URLs:

```
# Analysis: [N] videos

---

## Video 1: [Title]
**Channel:** [Channel] | **Date:** [YYYY-MM-DD] | **Duration:** [HH:MM:SS] | **Views:** [n] | **Likes:** [n]

### Description
[from subagent]

### Chapters
[If present: apply the same chapter-aligned screenshot embedding rule as single-video mode — when `--screenshots` count matches chapter count and timestamps align, embed each screenshot indented below its matching chapter line.]

### Transcript Summary
[Info + structured summary]

### Screenshots
[Apply the same conditional-rendering rule as single-video mode: omit if chapter-aligned (already embedded above); otherwise show the standalone list.]

### Screenshot Status
[If present: success/error messages — kept even when Screenshots section was suppressed due to chapter embedding]

### Top Comments
[List or hint]

---

## Video 2: [Title]
[same structure]

---

## Synthesis

**Shared themes:** [content that appears across multiple/all videos]

**Differences & contradictions:** [diverging approaches, conflicting statements]

**Overall key takeaways:** [the most important insights across all videos]

**Tools & resources mentioned:** [consolidated list of all links, tools, repos]
```

**With --full-transcript:** sections are called `### Transcript` and show the raw prose with embedded screenshot references.

---

## Step 3 — File saving

**Default behavior (auto-save):** The analysis is automatically saved as a Markdown file in its own folder. The output still appears in full in the chat.

**With `--no-save`:** The Python script still runs normally and creates the target folder (it has to — screenshots and the OUTPUT_FOLDER trailer depend on it). After the chat output, ask: "📁 Should I save the analysis as a Markdown file?" On "yes" → same flow as auto-save (including the follow-up invitation at the end). On "no" → **remove the folder(s) the script created** with `rm -rf <OUTPUT_FOLDER>` (for 1 video) or `rm -rf ./yt-extract_[DATE]_[N]-videos/` (for multi-video), then emit the follow-up invitation at the very end (with phrasing "The analysis is in context — you can ask me to:" since no file was saved).

### Folder structure

The Python script owns the per-video folder layout. The skill only orchestrates `--output-base` and, for multi-video runs, the parent folder + consolidated MD.

**For 1 video:**
```
./yt-extract_[YYYY-MM-DD]_[slug]/
  yt-extract_[YYYY-MM-DD]_[slug].md     ← written by the skill (from subagent output)
  screenshots/                          ← created by the script, only with --screenshots
    001_00m30s_intro.png
    002_02m15s_installing-docker.png
```

**For 2-3 videos:**
```
./yt-extract_[YYYY-MM-DD]_[N]-videos/
  yt-extract_[YYYY-MM-DD]_[N]-videos.md     ← written by the skill (consolidated)
  yt-extract_[YYYY-MM-DD]_[slug-video1]/    ← created by subagent 1's script
    screenshots/
      001_00m30s.png
  yt-extract_[YYYY-MM-DD]_[slug-video2]/    ← created by subagent 2's script
    screenshots/
      001_01m00s.png
```

- Slug: title lowercased, special chars removed, spaces → hyphens, max. 50 chars
- YYYY-MM-DD: today's date

### Auto-save flow

The Python script creates the per-video folder and any screenshots inside it directly — no staging, no moves. The skill's job is three things: pass the right `--output-base` on dispatch, read the `OUTPUT_FOLDER:` trailer from subagent output, and write the consolidated markdown.

1. **Read `OUTPUT_FOLDER: <path>` from each subagent's output.** This is always the last non-empty line the script emits. Trim it from the markdown before further processing — it is an orchestration marker, not analysis content. The path uses forward slashes and is relative to CWD.

2. **Prepend YAML frontmatter** (see below) to the markdown.

3. **Rewrite screenshot paths (multi-video only).** Per-video subagent output references screenshots as `screenshots/NNN_foo.png` (relative to the per-video folder). In the consolidated multi-video MD, rewrite each video's paths to `yt-extract_[DATE]_[slug]/screenshots/NNN_foo.png` (relative to the parent folder where the consolidated MD lives). Use the slug from that video's OUTPUT_FOLDER. Single-video mode needs no rewrite — paths already resolve correctly because the MD lives next to the `screenshots/` folder.

4. **Write the MD file** with the Write tool:
   - **1 video:** `<OUTPUT_FOLDER>/yt-extract_[DATE]_[slug].md` — derive the filename from the last path segment of OUTPUT_FOLDER.
   - **2-3 videos:** `./yt-extract_[DATE]_[N]-videos/yt-extract_[DATE]_[N]-videos.md`.

5. **Show confirmation in chat:**
   - With screenshots: `📁 Saved: [folder]/[file].md ([N] screenshots)` — **take `[N]` from the `### Screenshot Status` line that the script already printed (format: "`N screenshots requested, M successfully extracted`" — use `M`, summed across all videos for multi-URL). Do NOT run a filesystem count to verify; the script is the source of truth.**
   - Without screenshots: `📁 Saved: [folder]/[file].md`

6. **Follow-up invitation.** After the `📁 Saved:` line (or directly after the content when `--no-save` was used and the user declined saving), emit one blank line, then a **"What next?"** block that invites follow-up queries.

    Exact structure:

    ```
    💬 **What next?** The full analysis is in context — you can ask me to:
    - Extract all tools & resources as a bulleted checklist
    - Write a LinkedIn post / blog draft from the summary
    - [conditional 4th leverage bullet, see below]
    - Translate the summary to another language

    Or re-run with more data:
    - [conditional re-run bullets, see below]
    ```

    **Conditional 4th leverage bullet (chapter drill-down):**
    - If the current run rendered at least one `### Chapters` section: include `Drill into a specific chapter (e.g. "more on [HH:MM] Chapter Title")` — substitute `[HH:MM] Chapter Title` with an **actual** entry picked from the run's chapters (first video's chapters if multi-video).
    - Else if multi-video (2–3 URLs) with no chapters anywhere: include `Pick the best video for your specific use case from the synthesis`.
    - Else (single video, no chapters): omit this bullet entirely (block has 3 leverage bullets only).

    **Conditional re-run sub-block.** Include the `Or re-run with more data:` line AND the bullets below it ONLY when at least one of these conditions is true. Omit the whole sub-block otherwise.
    - `--comments` was NOT used → include `` `--comments` to add top viewer comments ``
    - `--full-transcript` was NOT used → include `` `--full-transcript` for raw text instead of summary ``
    - `--screenshots` was NOT used → include `` `--screenshots` for chapter-aligned frame captures ``
    - Single URL (not multi-video) → include `Compare to related videos: /yt-extract <url1> <url2> [<url3>]`

    **Do NOT emit the follow-up invitation in these cases:**
    - `--check` mode (Step 0.7 short-circuit — it has its own "Ready to extract." message).
    - Any error path where the subagent failed or aborted before content was assembled (e.g. yt-dlp install declined, Step 0.6.E stale-PATH abort). The block is contingent on a successful extraction with formatted content in the chat.

### YAML frontmatter

**For 1 video:**
```yaml
---
title: "[video title]"
channel: "[channel name]"
date: "[upload date YYYY-MM-DD]"
url: "[YouTube URL]"
analyzed: "[today's date YYYY-MM-DD]"
flags: [screenshots, comments]
---
```

**For 2-3 videos:**
```yaml
---
analyzed: "[today's date YYYY-MM-DD]"
flags: [screenshots, comments]
videos:
  - title: "[title video 1]"
    channel: "[channel 1]"
    date: "[date 1]"
    url: "[url 1]"
  - title: "[title video 2]"
    channel: "[channel 2]"
    date: "[date 2]"
    url: "[url 2]"
---
```

- `flags` contains only the flags actually used (empty array `[]` when none)
- All string values in YAML are quoted to handle special characters in titles

---

## Edge cases

- **Video unavailable/private:** the section shows an error message; synthesis is based on available videos
- **No transcript:** ❌ hint in the section, summary is omitted for that video, synthesis uses available transcripts
- **Live livestream:** "Ongoing livestream — transcript available only after it ends"; metadata is still shown
- **YouTube Short (< 3 min):** process normally, no length hint
- **Manual subtitles only:** use them (no "auto-generated" hint)
- **ffmpeg not installed:** handled in Step 0.5 before subagent dispatch (install-on-demand with per-OS command). `FFMPEG_MISSING` marker in the script output is defensive-only — normally unreachable.
- **--screenshots without chapter markers and without timestamps:** `SCREENSHOTS_ASK_USER` marker → ask user for strategy (evenly distributed or manual input)
- **Stream URL expired:** ffmpeg error during screenshot extraction → fetch a fresh URL once and retry
- **Timestamp outside video duration:** skipped by the Python script with a WARNING, no interruption
- **Target folder already exists:** script exits 2 with `FOLDER_EXISTS: <path>` on stderr → subagent prompts the user via AskUserQuestion and re-runs with `--force` on confirmation. Multi-URL parent-folder collisions are handled by the skill itself before dispatch (see Step 1).
