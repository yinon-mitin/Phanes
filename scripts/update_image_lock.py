#!/usr/bin/env python3
"""Resolve source tags to immutable multi-architecture digests."""
from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = ROOT / "stack/versions.env"
SOURCES = {
    "QBITTORRENT_IMAGE": "lscr.io/linuxserver/qbittorrent:latest",
    "PROWLARR_IMAGE": "lscr.io/linuxserver/prowlarr:latest",
    "SONARR_IMAGE": "lscr.io/linuxserver/sonarr:latest",
    "RADARR_IMAGE": "lscr.io/linuxserver/radarr:latest",
    "BAZARR_IMAGE": "lscr.io/linuxserver/bazarr:latest",
    "JELLYSEERR_IMAGE": "ghcr.io/seerr-team/seerr:latest",
    "FLARESOLVERR_IMAGE": "ghcr.io/flaresolverr/flaresolverr:latest",
    "JELLYFIN_IMAGE": "lscr.io/linuxserver/jellyfin:latest",
    "PROFILARR_IMAGE": "santiagosayshey/profilarr:latest",
    "HOMARR_IMAGE": "ghcr.io/homarr-labs/homarr:latest",
    "RECYCLARR_IMAGE": "ghcr.io/recyclarr/recyclarr:8",
    "NOTIFIARR_IMAGE": "golift/notifiarr:latest",
    "AUTOBRR_IMAGE": "ghcr.io/autobrr/autobrr:latest",
    "TORRSERVER_IMAGE": "ghcr.io/yourok/torrserver:latest",
    "JACKETT_IMAGE": "lscr.io/linuxserver/jackett:latest",
    "QBIT_MANAGE_IMAGE": "ghcr.io/stuffanthings/qbit_manage:latest",
    "APERTURE_IMAGE": "akhilmulpuri/aperture-web:latest",
    "DOCKER_SOCKET_PROXY_IMAGE": "tecnativa/docker-socket-proxy:latest",
    "UPTIME_KUMA_IMAGE": "louislam/uptime-kuma:2",
    "CADDY_IMAGE": "caddy:2.10.2-alpine",
}
DIGEST_LINE = re.compile(r"^Digest:\s+(sha256:[0-9a-f]{64})$", re.MULTILINE)


def resolve(image: str) -> str:
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", image],
        cwd=ROOT, text=True, capture_output=True,
    )
    match = DIGEST_LINE.search(result.stdout)
    if result.returncode or not match:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"cannot resolve {image}: {message}")
    repository = image.rsplit(":", 1)[0]
    return f"{repository}@{match.group(1)}"


def main() -> int:
    resolved: dict[str, str] = {}
    try:
        for variable, source in SOURCES.items():
            print(f"Resolving {source}...", flush=True)
            resolved[variable] = resolve(source)
    except RuntimeError as exc:
        print(f"Image lock update FAILED: {exc}", file=sys.stderr)
        return 1

    timestamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lines = [
        "# Immutable OCI image manifests and multi-architecture indexes.",
        f"# Resolved from the source tags on {timestamp}.",
        "# Update intentionally with: make update-lock",
        "",
    ]
    lines.extend(f"{key}={value}" for key, value in resolved.items())
    LOCK_FILE.write_text("\n".join(lines) + "\n")
    print(f"Updated {LOCK_FILE.relative_to(ROOT)} with {len(resolved)} immutable references.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
