#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_media_policy.py"
POLICY = ROOT / "stack/media-policy.json"


class MediaPolicyTests(unittest.TestCase):
    def test_policy_validator_accepts_repository_policy(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), str(POLICY)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_active_profiles_are_sdr_and_future_profiles_include_hdr(self) -> None:
        data = json.loads(POLICY.read_text())
        for app, profile in data["active_production_profile"].items():
            self.assertIn("SDR", profile)
            self.assertNotIn("HDR", profile)
            self.assertTrue(data["future_profiles"][app])
            self.assertTrue(all("HDR" in value or "SDR" in value for value in data["future_profiles"][app]))

    def test_required_formats_cover_hdr_and_dv(self) -> None:
        data = json.loads(POLICY.read_text())
        for formats in data["required_custom_formats"].values():
            self.assertIn("RU HDR", formats)
            self.assertIn("RU DV", formats)
            self.assertIn("RU Reject HDR DV HLG", formats)


if __name__ == "__main__":
    unittest.main()
