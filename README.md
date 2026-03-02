# dotclaude

Manages `~/.claude` configurations across different operating systems using a merge script.

## Structure

- `common/` — shared config for all OSes
- `windows/`, `mac/`, `linux/`, `wsl/`, `unix/` — OS-specific overrides

## Usage

```
uv run merge.py [--dest PATH] [--os windows|mac|linux|unix] [--dry-run]
```

Merges `common/` with the detected (or specified) OS directory and writes the result to `~/.claude` (or `%USERPROFILE%\.claude` on Windows). Omit `--os` to auto-detect.

## Merge Rules

| File type | Behavior |
|-----------|----------|
| `.json` | Deep-merged; OS-specific values take precedence |
| `.md` / `.txt` | Concatenated (common first, then OS-specific) |
| All others | OS-specific wins outright |

## Setup

Requires Python and `uv`. If either is missing, install via [mise](https://mise.jdx.dev/):

```
mise install
```

## Tests

```
uv run pytest
```
