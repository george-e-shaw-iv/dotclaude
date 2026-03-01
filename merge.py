#!/usr/bin/env python3
"""Merges common/ and an OS-specific directory into a destination ~/.claude directory."""

import argparse
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


def merge_directories(common_dir: Path, os_dir: Path | None, dest_dir: Path) -> None:
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
                dest_file.write_text(
                    json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            elif suffix in (".md", ".txt"):
                common_content = common_file.read_text(encoding="utf-8")
                os_content = os_file.read_text(encoding="utf-8")
                dest_file.write_text(merge_text(common_content, os_content), encoding="utf-8")
            else:
                # OS wins for unrecognized types
                shutil.copy2(os_file, dest_file)

        elif in_os:
            shutil.copy2(os_dir / rel_path, dest_file)  # type: ignore[operator]
        else:
            shutil.copy2(common_dir / rel_path, dest_file)


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

    merge_directories(common_dir, os_dir, args.dest)
    print(f"Merged into {args.dest}")


if __name__ == "__main__":
    main()
