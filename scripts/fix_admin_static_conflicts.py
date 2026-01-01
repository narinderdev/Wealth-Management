#!/usr/bin/env python3
"""Move project admin static overrides out of STATICFILES paths.

Run:
  python scripts/fix_admin_static_conflicts.py
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    static_root = repo_root / "management" / "static"
    admin_dir = static_root / "admin"

    if not admin_dir.exists():
        print("No admin static overrides found.")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = static_root / f"_backup_admin_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    dest = backup_dir / "admin"
    shutil.move(str(admin_dir), str(dest))

    print("Moved admin static overrides:")
    print(f"  from: {admin_dir}")
    print(f"  to:   {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
