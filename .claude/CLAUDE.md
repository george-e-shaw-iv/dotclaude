This project contains different versions of my `~/.claude` directories for different operating systems. The common parts of this
directory lie within `common/`, Windows-specific additions live in `windows/`, and so on.

There is a `mise.toml` file that contains `python` and `uv` tool definitions. If either of those tools are unavailable on the
machine you're currently running on you can run `mise install` to get them installed.

## merge.py

`merge.py` at the repo root is the main script. It merges `common/` with an OS-specific directory and writes the result to
a destination (default: `~/.claude` / `%USERPROFILE%\.claude`).

**Merge rules:**
- `.json` files: deep-merged; OS-specific takes precedence (scalars and arrays replaced, dicts recursively merged)
- `.md` / `.txt` files: concatenated (common first, then OS-specific)
- All other file types: OS-specific wins outright

**Usage:**
```
uv run merge.py [--dest PATH] [--os windows|mac|linux|unix] [--dry-run]
```

**Tests:** `uv run pytest` — 27 tests in `tests/test_merge.py`

**Adding a new OS:** Create a new directory (e.g., `mac/`, `linux/`, `unix/`) at the repo root. `detect_os_dir()` in
`merge.py` handles `Windows`, `Darwin`, and Linux automatically, with a `unix/` fallback.