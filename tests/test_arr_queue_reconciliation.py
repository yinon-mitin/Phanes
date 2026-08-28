#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reconcile_arr_queue", ROOT / "scripts/reconcile_arr_queue.py"
)
assert SPEC and SPEC.loader
reconcile = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reconcile
SPEC.loader.exec_module(reconcile)


class ArrQueueReconciliationTests(unittest.TestCase):
    def test_selects_completed_radarr_warning_when_movie_is_already_present(self) -> None:
        records = [
            {
                "downloadId": "ABC",
                "status": "completed",
                "trackedDownloadStatus": "warning",
                "movieId": 7,
            }
        ]
        self.assertEqual(
            ["abc"],
            reconcile.safe_completed_downloads(records, {7: True}, "movieId"),
        )

    def test_does_not_select_warning_when_library_file_is_missing(self) -> None:
        records = [
            {
                "downloadId": "ABC",
                "status": "completed",
                "trackedDownloadStatus": "warning",
                "movieId": 7,
            }
        ]
        self.assertEqual(
            [],
            reconcile.safe_completed_downloads(records, {7: False}, "movieId"),
        )

    def test_deduplicates_download_hashes(self) -> None:
        records = [
            {
                "downloadId": "ABC",
                "status": "completed",
                "trackedDownloadStatus": "warning",
                "movieId": 7,
            },
            {
                "downloadId": "abc",
                "status": "completed",
                "trackedDownloadStatus": "warning",
                "movieId": 7,
            },
        ]
        self.assertEqual(
            ["abc"],
            reconcile.safe_completed_downloads(records, {7: True}, "movieId"),
        )

    def test_updates_only_the_imported_category_field(self) -> None:
        client = {
            "name": "qBittorrent",
            "fields": [
                {"name": "host", "value": "qbittorrent"},
                {"name": "movieImportedCategory", "value": None},
            ],
        }
        changed = reconcile.set_field(client, "movieImportedCategory", "radarr-imported")
        self.assertTrue(changed)
        self.assertEqual("qbittorrent", client["fields"][0]["value"])
        self.assertEqual("radarr-imported", client["fields"][1]["value"])

    def test_missing_imported_category_field_fails_closed(self) -> None:
        with self.assertRaises(KeyError):
            reconcile.set_field({"fields": []}, "movieImportedCategory", "radarr-imported")

    def test_existing_qbittorrent_category_is_an_idempotent_success(self) -> None:
        self.assertTrue(reconcile.qbit_http_success(409, allow_conflict=True))
        self.assertFalse(reconcile.qbit_http_success(409, allow_conflict=False))


if __name__ == "__main__":
    unittest.main()
