#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("watchdog_stack", ROOT / "scripts/watchdog_stack.py")
assert SPEC and SPEC.loader
watchdog = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = watchdog
SPEC.loader.exec_module(watchdog)


class WatchdogContractTests(unittest.TestCase):
    def test_environment_parser_ignores_comments_and_preserves_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.env"
            path.write_text("# ignored\nLAN_IP=192.0.2.10\nVALUE='quoted'\n", encoding="utf-8")
            self.assertEqual(
                {"LAN_IP": "192.0.2.10", "VALUE": "quoted"},
                watchdog.read_environment(path),
            )

    def test_issue_signature_is_order_independent(self) -> None:
        self.assertEqual(
            watchdog.signature(["b", "a"]),
            watchdog.signature(["a", "b"]),
        )

    def test_unresolved_report_contains_attempts_and_manual_result(self) -> None:
        report = watchdog.format_report(
            resolved=False,
            issues=["Jellyfin недоступен"],
            attempts=["Перезапуск Jellyfin: успешно"],
            remaining=["Jellyfin недоступен"],
        )
        self.assertIn("сбой не устранён", report)
        self.assertIn("Попытки исправления", report)
        self.assertIn("ручное вмешательство", report)

    def test_resolved_report_has_success_result(self) -> None:
        report = watchdog.format_report(
            resolved=True,
            issues=["Docker недоступен"],
            attempts=["Docker daemon снова отвечает"],
        )
        self.assertIn("автоматически восстановлен", report)
        self.assertIn("все контрольные проверки проходят", report)


if __name__ == "__main__":
    unittest.main()
