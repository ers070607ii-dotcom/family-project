# Backup and recovery module

This is a standalone Python standard-library module. It does not modify `app.py`.

## Quick start

From the repository root:

```bash
python3 -m security.backup create --keep 7
python3 -m security.backup list
python3 -m security.backup verify backups/<your-backup-name>.zip
python3 -m unittest discover -s tests -v
```

The temporary archive is staged inside `backups/` to ensure the final atomic rename does not cross filesystem boundaries. SQLite connections are explicitly closed.

Each archive contains a consistent SQLite snapshot (`database/budget.db`), receipt files (`uploads/`), and a SHA-256 manifest. The `verify` command checks file hashes **and** SQLite integrity. The checksums detect accidental damage, **not** malicious modification of an archive and its manifest.

## Restore

1. Stop the Flask application and any workers using the database or uploads folder.
2. Preserve a separate copy of the current project data before attempting a restore.
3. Run:

```bash
python3 -m security.backup verify backups/<your-backup-name>.zip
python3 -m security.backup restore backups/<your-backup-name>.zip --yes
```

The restore operation replaces the database and uploads directory. It stages a validated backup before replacing live data and attempts rollback on a filesystem error. Test recovery with a **temporary copy**, not real user data, before relying on it.

## Scheduling on Ubuntu/Linux

Use cron on the machine actually running the app. Run `crontab -e` and add a line (replace the path and username):

```cron
0 2 * * * cd /home/USER/family-tracet && /usr/bin/python3 -m security.backup create --keep 7 >> /home/USER/family-tracet-backup.log 2>&1
```

A live SQLite database is backed up safely using the official `sqlite3.Connection.backup` API. Because uploaded files are separate from the database, there is no **atomic cross-resource snapshot** if receipts are added or removed during backup. Schedule backups at quiet times, or stop writes temporarily if guaranteed DB/receipt consistency is required.

Backups are stored locally under `backups/` with private file permissions. They are **not encrypted**. Keep the folder private and copy selected backups to a securely stored, access-controlled, encrypted off-device location for disaster recovery.

Do not commit real databases, receipt images, backup ZIPs, or `.env` files to Git. `.gitignore` does not untrack files already committed, including the repository's existing `budget.db` — coordinate removing those from Git and assess any sensitive data already in Git history.
