#!/usr/bin/env python3
"""Restore the latest admin static backup into management/static/admin.

Run:
  python scripts/restore_admin_static_backup.py
"""
from __future__ import annotations

from pathlib import Path
import shutil
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    static_root = repo_root / "management" / "static"
    admin_dir = static_root / "admin"

    if admin_dir.exists():
        print(f"Refusing to overwrite existing admin directory: {admin_dir}")
        return 1

    backups = sorted(static_root.glob("_backup_admin_*/"))
    if not backups:
        print("No admin static backups found.")
        return 1

    latest_backup = backups[-1]
    backup_admin = latest_backup / "admin"
    if not backup_admin.exists():
        print(f"No admin directory inside backup: {backup_admin}")
        return 1

    shutil.move(str(backup_admin), str(admin_dir))
    print("Restored admin static overrides:")
    print(f"  from: {backup_admin}")
    print(f"  to:   {admin_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
