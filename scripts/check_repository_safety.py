#!/usr/bin/env python3
"""Fail if Git would publish runtime data, media indexes, or likely secrets."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROHIBITED_PREFIXES = (
    "appdata/",
    "stack/homarr/appdata/",
    "stack/aperture/",
)
PROHIBITED_NAMES = {
    ".env",
    "frpc.toml",
    "movies.txt",
    "movies.csv",
    "movies.json",
    "films.txt",
    "films.csv",
    "films.json",
}
PROHIBITED_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".torrent", ".fastresume", ".nzb",
    ".m3u", ".m3u8", ".nfo", ".srt", ".ass", ".vtt", ".pem",
    ".p12", ".pfx", ".key", ".mkv", ".mp4", ".avi", ".mov",
    ".mp3", ".flac", ".iso",
}
TEXT_SECRET_RULES = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "hard-coded credential": re.compile(
        r"(?i)\b(?:password|passwd|api[_-]?key|auth\.token|secret(?:_encryption)?_key|jwt_secret)\b"
        r"\s*[:=]\s*[\"']?(?!\$\{|<|replace-|put_|example|none|false|true)[^\s#\"']{8,}"
    ),
}


def git_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    return sorted(set(filter(None, result.stdout.splitlines())))


def main() -> int:
    findings: list[tuple[str, str]] = []
    for rel in git_files():
        normalized = rel.replace("\\", "/")
        path = ROOT / rel
        lower_name = path.name.lower()
        lower_suffix = path.suffix.lower()
        if normalized.startswith(PROHIBITED_PREFIXES):
            findings.append((rel, "prohibited runtime/vendor path"))
            continue
        if lower_name in PROHIBITED_NAMES or lower_suffix in PROHIBITED_SUFFIXES:
            findings.append((rel, "prohibited secret/state/media filename"))
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            findings.append((rel, f"cannot read: {exc}"))
            continue
        if b"\x00" in raw[:8192]:
            continue
        text = raw.decode("utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), 1):
            if normalized.endswith(".example") or normalized.endswith(".example.toml"):
                # Examples are still checked for real provider tokens/private keys,
                # but placeholder credential assignments are allowed.
                rules = {k: v for k, v in TEXT_SECRET_RULES.items() if k != "hard-coded credential"}
            else:
                rules = TEXT_SECRET_RULES
            for label, pattern in rules.items():
                if pattern.search(line):
                    findings.append((f"{rel}:{line_no}", label))
    if findings:
        print("Repository safety check FAILED; values are intentionally not printed:")
        for location, reason in findings:
            print(f"- {location}: {reason}")
        return 1
    print(f"Repository safety check passed ({len(git_files())} publishable files scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
