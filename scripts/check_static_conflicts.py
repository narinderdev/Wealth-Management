#!/usr/bin/env python3
"""Guard against admin static conflicts before collectstatic.

Run:
  python scripts/check_static_conflicts.py
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys


CONFLICT_SNIPPET = "Found another file with the destination path"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    admin_dir = repo_root / "management" / "static" / "admin"

    if admin_dir.exists():
        print("ERROR: management/static/admin exists. Remove it and rely on Django admin static from site-packages.")
        return 1

    manage_py = repo_root / "manage.py"
    if not manage_py.exists():
        print("ERROR: manage.py not found; run this script from the repo root.")
        return 1

    cmd = [
        sys.executable,
        str(manage_py),
        "collectstatic",
        "--noinput",
        "--dry-run",
        "-v",
        "2",
    ]

    result = subprocess.run(
        cmd,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    output = (result.stdout or "") + (result.stderr or "")
    conflict_lines = [
        line for line in output.splitlines() if CONFLICT_SNIPPET in line
    ]

    if conflict_lines:
        print("WARNING: collectstatic conflicts detected:", file=sys.stderr)
        for line in conflict_lines:
            print(f"  {line}", file=sys.stderr)

    if result.returncode != 0:
        print("ERROR: collectstatic dry-run failed.", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())
