"""Self-contained tests, running only against temporary databases."""

import sqlite3
from contextlib import closing
from unittest.mock import patch
import tempfile
import unittest
import zipfile
from pathlib import Path

from security.backup import create_backup, restore_backup, verify_backup, prune_backups


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        with closing(sqlite3.connect(self.root / "budget.db")) as db, db:
            db.execute("CREATE TABLE expenses (id INTEGER PRIMARY KEY, amount INTEGER)")
            db.execute("INSERT INTO expenses (amount) VALUES (150)")
        (self.root / "uploads").mkdir()
        (self.root / "uploads" / "receipt.png").write_bytes(b"demo-receipt")

    def tearDown(self):
        self.tmp.cleanup()

    def test_staging_occurs_on_destination_filesystem(self):
        from security import backup
        real_replace = backup.os.replace
        seen = []

        def checked_replace(src, dst):
            src, dst = Path(src), Path(dst)
            if src.name == "backup.zip":
                self.assertEqual(src.parent.parent, self.root / "backups")
                seen.append(True)
            return real_replace(src, dst)

        with patch("security.backup.os.replace", side_effect=checked_replace):
            create_backup(self.root)
        self.assertTrue(seen)

    def test_backup_and_verify(self):
        archive = create_backup(self.root)
        self.assertTrue(archive.exists())
        manifest = verify_backup(archive)
        self.assertIn("uploads/receipt.png", manifest["files"])
        self.assertIn("database/budget.db", manifest["files"])

    def test_restore(self):
        archive = create_backup(self.root)
        with closing(sqlite3.connect(self.root / "budget.db")) as db, db:
            db.execute("DELETE FROM expenses")
        (self.root / "uploads" / "receipt.png").unlink()
        restore_backup(self.root, archive, confirmed=True)
        with closing(sqlite3.connect(self.root / "budget.db")) as db, db:
            self.assertEqual(db.execute("SELECT amount FROM expenses").fetchone()[0], 150)
        self.assertEqual((self.root / "uploads" / "receipt.png").read_bytes(), b"demo-receipt")

    def test_restore_requires_confirmation(self):
        archive = create_backup(self.root)
        with self.assertRaises(ValueError):
            restore_backup(self.root, archive)

    def test_detect_corruption(self):
        archive = create_backup(self.root)
        bad = self.root / "tampered.zip"
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(bad, "w") as dst:
            for name in src.namelist():
                content = src.read(name)
                dst.writestr(name, b"changed" if name == "uploads/receipt.png" else content)
        with self.assertRaises(ValueError):
            verify_backup(bad)

    def test_rotation(self):
        for _ in range(3):
            create_backup(self.root, keep=2)
        self.assertEqual(len(list((self.root / "backups").glob("*.zip"))), 2)
        self.assertEqual(prune_backups(self.root, 1), 1)


if __name__ == "__main__":
    unittest.main()
