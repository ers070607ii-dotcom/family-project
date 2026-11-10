"""Safe, standalone SQLite and receipt backup CLI for Family Budget Tracker.

Run from the project root: python3 -m security.backup create
Stop the Flask app before restoring (or for a fully consistent upload snapshot).
"""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_NAME = "budget.db"
BACKUP_PREFIX = "family-budget-"
MAX_ARCHIVE_BYTES = 2 * 1024**3
MAX_ARCHIVE_ENTRIES = 10000


def _checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _assert_db_healthy(db_path: Path) -> None:
    with closing(sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)) as db:
        result = db.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise ValueError("SQLite integrity check failed")


def _path_safe(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or "\\" in name or any(part in ("", ".", "..") for part in path.parts):
        return False
    return name == "database/budget.db" or (
        len(path.parts) >= 2 and path.parts[0] == "uploads"
    )


def create_backup(root: Path, keep: int = 7) -> Path:
    """Create a checked, zipped database snapshot with uploads; rotate old backups."""
    root = Path(root).resolve()
    db_path = root / DB_NAME
    uploads = root / "uploads"
    backups = root / "backups"
    if not db_path.is_file() or db_path.is_symlink():
        raise FileNotFoundError(f"Expected a regular SQLite file at {db_path}")
    if uploads.is_symlink():
        raise ValueError("Refusing to archive a symlinked uploads directory")
    if keep < 1:
        raise ValueError("--keep must be at least 1")
    backups.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = backups / f"{BACKUP_PREFIX}{stamp}-{uuid.uuid4().hex[:8]}.zip"
    # Stage privately inside backups/ so the final rename always stays on the same filesystem.
    with tempfile.TemporaryDirectory(dir=backups, prefix=".family-budget-create-") as temp:
        temp_dir = Path(temp)
        snapshot = temp_dir / DB_NAME
        with closing(sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(snapshot)) as dst:
                src.backup(dst)
        _assert_db_healthy(snapshot)
        partial = temp_dir / "backup.zip"
        manifest = {"version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "files": {}}
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            db_bytes = snapshot.read_bytes()
            zf.writestr("database/budget.db", db_bytes)
            manifest["files"]["database/budget.db"] = {
                "bytes": len(db_bytes), "sha256": _checksum(db_bytes)
            }
            if uploads.is_dir():
                for file in sorted(uploads.rglob("*")):
                    if file.is_symlink():
                        raise ValueError(f"Refusing to archive symlink: {file}")
                    if not file.is_file():
                        continue
                    relative = file.relative_to(uploads).as_posix()
                    archive_name = f"uploads/{relative}"
                    if not _path_safe(archive_name):
                        raise ValueError(f"Invalid receipt path: {relative}")
                    data = file.read_bytes()
                    zf.writestr(archive_name, data)
                    manifest["files"][archive_name] = {
                        "bytes": len(data), "sha256": _checksum(data)
                    }
            zf.writestr("manifest.json", json.dumps(manifest, sort_keys=True, indent=2))
        # Verifies the complete ZIP and the SQLite snapshot before publishing.
        verify_backup(partial)
        os.chmod(partial, 0o600)
        os.replace(partial, destination)
    prune_backups(root, keep)
    return destination


def _extract_verified(archive: Path, target: Path) -> dict:
    with zipfile.ZipFile(archive, "r") as zf:
        infos = zf.infolist()
        names = [i.filename for i in infos]
        if len(names) > MAX_ARCHIVE_ENTRIES or len(names) != len(set(names)):
            raise ValueError("Archive contains too many entries or duplicate names")
        if any(i.is_dir() for i in infos):
            raise ValueError("Unexpected directories in archive")
        if sum(i.file_size for i in infos) > MAX_ARCHIVE_BYTES:
            raise ValueError("Archive exceeds allowed uncompressed size")
        if names.count("manifest.json") != 1:
            raise ValueError("Missing or duplicate manifest")
        for i in infos:
            # Unix symlinks may be stored in ZIP external attributes.
            if (i.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Archive contains a symlink")
            if i.filename != "manifest.json" and not _path_safe(i.filename):
                raise ValueError("Unexpected archive member/path traversal")
        with zf.open("manifest.json") as m:
            manifest = json.load(m)
        if not isinstance(manifest, dict) or manifest.get("version") != 1:
            raise ValueError("Unsupported backup manifest")
        files = manifest.get("files")
        if not isinstance(files, dict) or "database/budget.db" not in files:
            raise ValueError("Missing database manifest record")
        if set(names) != set(files) | {"manifest.json"}:
            raise ValueError("Manifest/file list mismatch")
        for name, expected in files.items():
            if not _path_safe(name) or not isinstance(expected, dict):
                raise ValueError("Invalid manifest entry")
            if not isinstance(expected.get("bytes"), int) or expected["bytes"] < 0:
                raise ValueError("Invalid expected file size")
            if not isinstance(expected.get("sha256"), str):
                raise ValueError("Invalid expected checksum")
            path = target.joinpath(*PurePosixPath(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            byte_count = 0
            with zf.open(name) as src, path.open("wb") as out:
                while chunk := src.read(1024 * 1024):
                    digest.update(chunk)
                    byte_count += len(chunk)
                    if byte_count > expected["bytes"]:
                        raise ValueError(f"File too large: {name}")
                    out.write(chunk)
            if byte_count != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
                raise ValueError(f"Checksum mismatch: {name}")
    _assert_db_healthy(target / "database" / DB_NAME)
    return manifest


def verify_backup(archive: Path) -> dict:
    """Validate archive member paths, checksums, and SQLite integrity."""
    with tempfile.TemporaryDirectory(prefix="family-budget-verify-") as tmp:
        return _extract_verified(Path(archive), Path(tmp))


def restore_backup(root: Path, archive: Path, confirmed: bool = False) -> None:
    """Restore an archive after app shutdown, keeping an automatic rollback on failure."""
    if not confirmed:
        raise ValueError("Restoring replaces live data; pass --yes to confirm")
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    db = root / DB_NAME
    uploads = root / "uploads"
    if db.is_symlink() or uploads.is_symlink():
        raise ValueError("Refusing to restore over symlinked application paths")
    # Stage inside root to keep os.replace operations on the same filesystem.
    with tempfile.TemporaryDirectory(dir=root, prefix=".restore-stage-") as tmp:
        stage = Path(tmp)
        _extract_verified(Path(archive), stage)
        rollback = stage / "previous"
        rollback.mkdir()
        db_old, uploads_old = rollback / DB_NAME, rollback / "uploads"
        had_db, had_uploads = db.exists(), uploads.exists()
        moved_db = moved_uploads = installed_db = installed_uploads = False
        try:
            if had_db:
                os.replace(db, db_old)
                moved_db = True
            if had_uploads:
                os.replace(uploads, uploads_old)
                moved_uploads = True
            os.replace(stage / "database" / DB_NAME, db)
            installed_db = True
            restored_uploads = stage / "uploads"
            if not restored_uploads.exists():
                restored_uploads.mkdir()
            os.replace(restored_uploads, uploads)
            installed_uploads = True
        except Exception:
            if installed_db and db.exists():
                db.unlink()
            if installed_uploads and uploads.exists():
                shutil.rmtree(uploads)
            if moved_db:
                os.replace(db_old, db)
            if moved_uploads:
                os.replace(uploads_old, uploads)
            raise


def prune_backups(root: Path, keep: int) -> int:
    if keep < 1:
        raise ValueError("keep must be at least 1")
    backups = Path(root).resolve() / "backups"
    items = sorted(
        (p for p in backups.glob(f"{BACKUP_PREFIX}*.zip") if p.is_file() and not p.is_symlink()),
        key=lambda p: p.name,
        reverse=True,
    ) if backups.exists() else []
    for old in items[keep:]:
        old.unlink()
    return max(0, len(items) - keep)


def main() -> None:
    # Backup files contain sensitive financial data; avoid group/world-readable files.
    os.umask(0o077)
    p = argparse.ArgumentParser(description="Family Budget Tracker backup management")
    p.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Project root (default: inferred)")
    commands = p.add_subparsers(dest="action", required=True)
    create = commands.add_parser("create", help="Create database + receipt snapshot")
    create.add_argument("--keep", type=int, default=7, help="Number of local backups to retain")
    commands.add_parser("list", help="List local backups")
    verify = commands.add_parser("verify", help="Validate a backup ZIP")
    verify.add_argument("archive", type=Path)
    restore = commands.add_parser("restore", help="Restore with app stopped")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--yes", action="store_true", help="Confirm destructive restore")
    prune = commands.add_parser("prune", help="Delete oldest local backups")
    prune.add_argument("--keep", type=int, default=7)
    args = p.parse_args()
    try:
        if args.action == "create":
            print("Created:", create_backup(args.root, args.keep))
        elif args.action == "list":
            for path in sorted((args.root / "backups").glob(f"{BACKUP_PREFIX}*.zip")):
                print(path)
        elif args.action == "verify":
            manifest = verify_backup(args.archive)
            print("Verified:", args.archive, "| files:", len(manifest["files"]))
        elif args.action == "restore":
            restore_backup(args.root, args.archive, args.yes)
            print("Restored:", args.archive)
        elif args.action == "prune":
            print("Removed:", prune_backups(args.root, args.keep))
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile, KeyError) as exc:
        p.exit(1, f"Backup error: {exc}\n")


if __name__ == "__main__":
    main()
