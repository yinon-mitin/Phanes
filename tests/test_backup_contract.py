#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / "scripts/backup_stack.sh"
RESTORE_TEST = ROOT / "scripts/verify_backup.sh"


class BackupContractTests(unittest.TestCase):
    def test_backup_script_is_fail_closed_and_resumes_stack(self) -> None:
        text = BACKUP.read_text()
        self.assertIn("set -euo pipefail", text)
        self.assertIn("trap resume_stack EXIT", text)
        self.assertIn("restic backup", text)
        self.assertIn("restic check", text)
        self.assertIn("restic forget", text)
        self.assertNotIn("RESTIC_PASSWORD=", text)

    def test_restore_verification_checks_sqlite_integrity(self) -> None:
        text = RESTORE_TEST.read_text()
        self.assertIn("restic restore", text)
        self.assertIn("integrity_check", text)
        self.assertIn("mktemp -d", text)
        self.assertIn("trap", text)


if __name__ == "__main__":
    unittest.main()
