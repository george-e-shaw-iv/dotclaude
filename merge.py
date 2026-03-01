#!/usr/bin/env python3
"""Merges common/ and an OS-specific directory into a destination ~/.claude directory."""

import argparse
import difflib
import json
import os
import platform
import shutil
import sys
from pathlib import Path


def detect_os_dir(repo_root: Path) -> Path:
    """Return the OS-specific directory based on the current platform."""
    system = platform.system()
    if system == "Windows":
        candidate = repo_root / "windows"
    elif system == "Darwin":
        candidate = repo_root / "mac"
    else:
        candidate = repo_root / "linux"

    if candidate.exists():
        return candidate

    # Fall back to a generic unix/ directory
    unix_dir = repo_root / "unix"
    if unix_dir.exists():
        return unix_dir

    return candidate  # Return even if missing; callers check existence


def deep_merge_json(common: dict, os_specific: dict) -> dict:
    """Deep-merge two dicts with OS-specific taking precedence.

    Rules:
    - Dicts: recursively merged
    - Arrays: OS replaces common
    - Scalars: OS wins
    """
    result = dict(common)
    for key, os_val in os_specific.items():
        if key in result:
            common_val = result[key]
            if isinstance(common_val, dict) and isinstance(os_val, dict):
                result[key] = deep_merge_json(common_val, os_val)
            else:
                result[key] = os_val
        else:
            result[key] = os_val
    return result


def merge_text(common_content: str, os_content: str) -> str:
    """Concatenate common content and OS-specific content."""
    if common_content and not common_content.endswith("\n"):
        common_content += "\n"
    return common_content + os_content


def _unified_diff(path: Path, old: str, new: str) -> str:
    """Return a unified diff string between old and new content."""
    lines = list(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"existing/{path}",
            tofile=f"new/{path}",
        )
    )
    return "".join(lines)


def _confirm_overwrite(dest_file: Path, new_text: str) -> bool:
    """Show a diff and prompt the user to confirm overwriting dest_file.

    Returns True if the write should proceed, False to skip.
    Skips the prompt silently if content is identical.
    """
    existing = dest_file.read_text(encoding="utf-8")
    if existing == new_text:
        return True  # identical — skip silently

    diff = _unified_diff(dest_file, existing, new_text)
    print(f"\n{diff}", end="")
    while True:
        answer = input(f"Overwrite {dest_file}? [y/N] ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no", ""):
            return False


def _write_with_confirm(dest_file: Path, content: str, yes: bool) -> None:
    """Write text content to dest_file, prompting if it already exists with different content."""
    if dest_file.exists() and not yes:
        if not _confirm_overwrite(dest_file, content):
            return
    dest_file.write_text(content, encoding="utf-8")


def _copy_with_confirm(src: Path, dest_file: Path, yes: bool) -> None:
    """Copy src to dest_file, prompting if dest already exists with different content."""
    if dest_file.exists() and not yes:
        try:
            new_text = src.read_text(encoding="utf-8")
            if not _confirm_overwrite(dest_file, new_text):
                return
        except UnicodeDecodeError:
            # Binary file — prompt without a diff
            answer = input(f"Binary file {dest_file} exists. Overwrite? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                return
    shutil.copy2(src, dest_file)


def merge_directories(common_dir: Path, os_dir: Path | None, dest_dir: Path, yes: bool = False) -> None:
    """Merge common_dir and os_dir into dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    common_files: set[Path] = set()
    if common_dir.exists():
        common_files = {f.relative_to(common_dir) for f in common_dir.rglob("*") if f.is_file()}

    os_files: set[Path] = set()
    if os_dir is not None and os_dir.exists():
        os_files = {f.relative_to(os_dir) for f in os_dir.rglob("*") if f.is_file()}

    for rel_path in common_files | os_files:
        in_common = rel_path in common_files
        in_os = rel_path in os_files
        dest_file = dest_dir / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        if in_common and in_os:
            common_file = common_dir / rel_path
            os_file = os_dir / rel_path  # type: ignore[operator]
            suffix = rel_path.suffix.lower()

            if suffix == ".json":
                common_data = json.loads(common_file.read_text(encoding="utf-8"))
                os_data = json.loads(os_file.read_text(encoding="utf-8"))
                merged = deep_merge_json(common_data, os_data)
                _write_with_confirm(
                    dest_file,
                    json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
                    yes,
                )
            elif suffix in (".md", ".txt"):
                common_content = common_file.read_text(encoding="utf-8")
                os_content = os_file.read_text(encoding="utf-8")
                _write_with_confirm(dest_file, merge_text(common_content, os_content), yes)
            else:
                # OS wins for unrecognized types
                _copy_with_confirm(os_file, dest_file, yes)

        elif in_os:
            _copy_with_confirm(os_dir / rel_path, dest_file, yes)  # type: ignore[operator]
        else:
            _copy_with_confirm(common_dir / rel_path, dest_file, yes)


def default_dest() -> Path:
    """Return the default destination (~/.claude)."""
    if platform.system() == "Windows":
        base = Path(os.environ.get("USERPROFILE", "")).expanduser() if os.environ.get("USERPROFILE") else Path.home()
        return base / ".claude"
    return Path.home() / ".claude"


def main(argv: list[str] | None = None) -> None:
    repo_root = Path(__file__).parent
    dest_default = default_dest()

    parser = argparse.ArgumentParser(
        description="Merge common/ and OS-specific Claude config into a destination directory."
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=dest_default,
        help=f"Destination directory (default: {dest_default})",
    )
    parser.add_argument(
        "--os",
        dest="os_name",
        choices=["windows", "mac", "linux", "unix"],
        default=None,
        help="Override OS detection",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without writing any files",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Overwrite existing files without prompting",
    )
    args = parser.parse_args(argv)

    common_dir = repo_root / "common"
    if not common_dir.exists():
        print(f"Error: common/ directory not found at {common_dir}", file=sys.stderr)
        sys.exit(1)

    if args.os_name:
        os_dir: Path | None = repo_root / args.os_name
    else:
        os_dir = detect_os_dir(repo_root)

    if os_dir is not None and not os_dir.exists():
        print(f"Warning: OS directory '{os_dir.name}/' not found — using common/ only.", file=sys.stderr)
        os_dir = None

    if args.dry_run:
        print("Dry run — no files will be written.")
        print(f"  common/ : {common_dir}")
        print(f"  os dir  : {os_dir if os_dir else '(none)'}")
        print(f"  dest    : {args.dest}")
        return

    merge_directories(common_dir, os_dir, args.dest, yes=args.yes)
    print(f"Merged into {args.dest}")


if __name__ == "__main__":
    main()
