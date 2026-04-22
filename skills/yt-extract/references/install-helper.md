# Install-dependency helper

Shared install flow used by SKILL.md Steps 0.3.b (yt-dlp missing) and 0.5 (ffmpeg missing). The main skill file references this helper and only loads it when a dependency actually needs to be installed — on the happy path (all deps already present) this file is never read.

## Inputs

- `dep_name` — display name (e.g. `"yt-dlp"` or `"ffmpeg"`)
- `options` — ordered list of `{label, command}` pairs from the SKILL.md Step 0.2 matrix for the detected OS. `label` is the short user-facing string (e.g. `"winget"`). `command` is the full non-interactive Bash line to execute.
- `doc_url` — official-docs link for manual install instructions
- `on_decline` — `"abort"` (yt-dlp) or `"skip_screenshots"` (ffmpeg)
- `verify_cmd` — command that must exit 0 after a successful install

## Step A0 — Pre-flight checks (package manager availability)

Before asking the user anything, verify that the install command in `options` can actually run. If it cannot, asking the user to confirm an install that will fail 127 with "command not found" is worse than useless — it wastes a prompt and then produces a Step F error message that tells the user to run the same failing command manually.

**macOS Homebrew availability.** When running on macOS AND every entry in `options` uses `brew`: probe `command -v brew`. If brew is NOT installed, skip Step A entirely and emit this message:

```
[dep_name] requires Homebrew to install on macOS, but Homebrew is not present on this system.

Install Homebrew first by following the instructions at https://brew.sh (a single curl command), then re-run /yt-extract.
```

In practice this triggers only for ffmpeg — yt-dlp on macOS has both `brew` and `pip3` options in the Step 0.2 matrix, so the probe short-circuits to Step A (which offers pip3 as a valid alternative).

If `on_decline == "abort"`: abort the skill. If `on_decline == "skip_screenshots"` (ffmpeg): set `skip_screenshots = true` and return to the caller (no abort).

**Linux ffmpeg sudo availability.** When running on Linux AND the dep is ffmpeg AND the detected command uses `sudo`: probe `sudo -n true 2>/dev/null`. If that fails (no active sudo session, no `NOPASSWD`), skip Step A entirely and emit this message:

```
ffmpeg is not installed, and installing it on Linux requires sudo.

I cannot run `sudo` from here without blocking on the password prompt. Please install ffmpeg manually in your own terminal:

  - sudo apt install -y ffmpeg    (Debian/Ubuntu)
  - sudo dnf install -y ffmpeg    (Fedora/RHEL)

Then re-run /yt-extract.

Docs: https://ffmpeg.org/download.html
```

Set `skip_screenshots = true` and return to the caller. The user is already informed; no second prompt needed.

For all other cases, continue to Step A below.

## Step A — Ask the user

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

## Step B — On decline

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

## Step C — On accept: run the chosen install command

Execute `options[chosen_index].command` via Bash exactly as written (the command already contains all non-interactive flags). Capture exit code and stderr.

**Winget "already installed" special case:** If the command is a `winget` command and the exit code is `43` (package already installed, no upgrade available), treat this as exit code `0` — the package is present on the system. Proceed to Step D to verify PATH availability.

## Step D — Verify

Run `verify_cmd`. If it succeeds (exit 0), the install worked — return success to the caller.

## Step E — On verification failure

(Install command returned exit 0, or winget exit 43, but binary still not on PATH.)

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

**Note:** Step E is the expected behavior after a first-time install in two cases:
- **Windows + winget:** winget updates the user PATH but the current shell's PATH is stale.
- **macOS + brew on Apple Silicon:** brew appends `/opt/homebrew/bin` to the shell rc (`.zprofile` / `.zshrc`), but the current Bash session's PATH was captured before that change.

In both cases the install actually succeeded — the message is designed to guide the user through the one-time terminal restart, not to signal a broken install.

## Step F — On install command itself failing (non-zero exit)

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
