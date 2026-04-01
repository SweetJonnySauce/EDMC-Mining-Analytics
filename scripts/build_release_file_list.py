#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import subprocess
from pathlib import Path


def load_patterns(path: Path) -> list[str]:
    patterns: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def is_excluded(relpath: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if pattern.endswith("/"):
            # Directory prefix rule.
            if relpath == pattern[:-1] or relpath.startswith(pattern):
                return True
            continue

        if any(token in pattern for token in "*?[]"):
            if fnmatch.fnmatch(relpath, pattern):
                return True
            continue

        if relpath == pattern:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Build null-delimited release file list from git-tracked files.")
    parser.add_argument("--exclude-file", required=True, type=Path, help="Pattern file path")
    parser.add_argument("--output", required=True, type=Path, help="Output null-delimited file list")
    args = parser.parse_args()

    patterns = load_patterns(args.exclude_file)

    tracked = subprocess.check_output(["git", "ls-files", "-z"])
    tracked_files = [entry.decode("utf-8") for entry in tracked.split(b"\0") if entry]

    included = [path for path in tracked_files if not is_excluded(path, patterns)]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = b"".join(item.encode("utf-8") + b"\0" for item in included)
    args.output.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
