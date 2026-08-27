#!/usr/bin/env python3
"""Validate local documentation links and English/Russian document parity."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PAIRS = {
    "README.md": "README.ru.md",
    "CONTRIBUTING.md": "CONTRIBUTING.ru.md",
    "SECURITY.md": "SECURITY.ru.md",
    "CONTRIBUTORS.md": "CONTRIBUTORS.ru.md",
    "docs/ARCHITECTURE.md": "docs/ru/ARCHITECTURE.md",
    "docs/REPRODUCIBILITY.md": "docs/ru/REPRODUCIBILITY.md",
    "docs/RESTORE.md": "docs/ru/RESTORE.md",
    "docs/OPERATIONS.md": "docs/ru/OPERATIONS.md",
    "components/aperture.md": "components/aperture.ru.md",
}
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
HTML_SOURCE = re.compile(r"(?:src|href)=\"([^\"]+)\"")


def local_target(document: Path, raw: str) -> Path | None:
    target = unquote(raw).split("#", 1)[0]
    if not target or target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    return (document.parent / target).resolve()


def repository_markdown() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return sorted(ROOT / relative for relative in set(result.stdout.splitlines()) if relative)


def main() -> int:
    errors: list[str] = []
    documents = repository_markdown()

    for english, russian in PAIRS.items():
        for relative in (english, russian):
            if not (ROOT / relative).is_file():
                errors.append(f"missing required document: {relative}")

    for document in documents:
        text = document.read_text(encoding="utf-8")
        links = MARKDOWN_LINK.findall(text) + HTML_SOURCE.findall(text)
        for raw in links:
            target = local_target(document, raw)
            if target is not None and not target.exists():
                location = document.relative_to(ROOT)
                errors.append(f"{location}: broken local link: {raw}")

    if errors:
        print("Documentation validation FAILED:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Documentation validation passed ({len(documents)} Markdown files, {len(PAIRS)} bilingual pairs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
