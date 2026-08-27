#!/usr/bin/env python3
"""Validate the immutable Jellyfin media-server distribution contract."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "stack/docker-compose.yml"
VERSIONS_FILE = ROOT / "stack/versions.env"
DIGEST = re.compile(r"^[a-z0-9][a-z0-9./_-]*@sha256:[0-9a-f]{64}$")
EXPECTED_SERVICES = {
    "aperture", "autobrr", "bazarr", "flaresolverr", "homarr", "jackett", "jellyfin",
    "jellyseerr", "notifiarr", "profilarr", "prowlarr", "qbit_manage",
    "qbittorrent", "radarr", "recyclarr", "sonarr", "torrserver",
}


def env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        if key in values:
            raise ValueError(f"{path}:{number}: duplicate key {key}")
        values[key] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default="stack/.env.example")
    args = parser.parse_args()
    env_file = (ROOT / args.env_file).resolve()
    errors: list[str] = []

    try:
        locks = env_values(VERSIONS_FILE)
    except (OSError, ValueError) as exc:
        print(f"Distribution validation FAILED: {exc}")
        return 1

    for key, image in sorted(locks.items()):
        if key.endswith("_IMAGE") and not DIGEST.fullmatch(image):
            errors.append(f"{key} is not pinned by sha256 digest")

    command = [
        "docker", "compose",
        "--profile", "*",
        "--env-file", str(env_file),
        "--env-file", str(VERSIONS_FILE),
        "-f", str(COMPOSE_FILE),
        "config", "--format", "json",
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        errors.append("Compose config failed: " + (result.stderr.strip() or result.stdout.strip()))
    else:
        config = json.loads(result.stdout)
        services = config.get("services", {})
        actual = set(services)
        if actual != EXPECTED_SERVICES:
            missing = sorted(EXPECTED_SERVICES - actual)
            extra = sorted(actual - EXPECTED_SERVICES)
            errors.append(f"service contract mismatch; missing={missing}, extra={extra}")
        for name, service in sorted(services.items()):
            image = service.get("image", "")
            if not DIGEST.fullmatch(image):
                errors.append(f"service {name} resolved to a floating image reference")
        if config.get("name") != "jellyfin-media-server":
            errors.append("Compose project name must be jellyfin-media-server")

    if errors:
        print("Distribution validation FAILED:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Distribution validation passed ({len(EXPECTED_SERVICES)} services, all images immutable).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
