# Static Asset Conflict Cleanup

## Fix admin static conflicts

Run the cleanup script to move project admin overrides out of static collection paths:

```
python scripts/fix_admin_static_conflicts.py
```

Expected output:

```
Moved admin static overrides:
  from: /path/to/repo/management/static/admin
  to:   /path/to/repo/management/static/_backup_admin_YYYYMMDD_HHMMSS/admin
```

If no overrides exist:

```
No admin static overrides found.
```

## Restore admin static overrides

Run the restore script to put the latest backup back in place:

```
python scripts/restore_admin_static_backup.py
```

Expected output:

```
Restored admin static overrides:
  from: /path/to/repo/management/static/_backup_admin_YYYYMMDD_HHMMSS/admin
  to:   /path/to/repo/management/static/admin
```

## Verify conflicts are gone

```
python manage.py collectstatic --noinput --clear -v 2 | grep "Found another file with the destination path" | head
```

Expected result:
- Conflicts for `admin/*` should be 0 (or drastically reduced if intentional overrides remain).
