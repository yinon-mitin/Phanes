#!/usr/bin/env python3
"""Read-only verification of the live Sonarr/Radarr media policy."""
from __future__ import annotations

import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "stack/media-policy.json"
ENV = ROOT / "stack/.env"
APPS = {"sonarr": {"port": 8989, "version": "v3", "items": "series"}, "radarr": {"port": 7878, "version": "v3", "items": "movie"}}


def env_value(name: str) -> str:
    for raw in ENV.read_text(encoding="utf-8").splitlines():
        if raw.startswith(name + "="):
            return raw.split("=", 1)[1].strip().strip("\"'")
    raise RuntimeError(f"missing {name} in {ENV}")


def api_key(app: str) -> str:
    value = ET.parse(ROOT / "appdata" / app / "config.xml").getroot().findtext("ApiKey")
    if not value:
        raise RuntimeError(f"missing {app} API key")
    return value


def request(app: str, endpoint: str) -> Any:
    config = APPS[app]
    url = f"http://{env_value('LAN_IP')}:{config['port']}/api/{config['version']}/{endpoint}"
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key(app), "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def verify(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for app, config in APPS.items():
        profiles = request(app, "qualityprofile")
        profile_names = {int(item["id"]): str(item["name"]) for item in profiles}
        active_name = policy["active_production_profile"][app]
        if active_name not in profile_names.values():
            errors.append(f"{app}: active profile missing: {active_name}")
        for required in policy["future_profiles"][app]:
            if required not in profile_names.values():
                errors.append(f"{app}: future profile missing: {required}")
        items = request(app, config["items"])
        counts = Counter(profile_names.get(int(item.get("qualityProfileId", -1)), "unknown") for item in items)
        print(f"{app}: items={len(items)} profiles={dict(sorted(counts.items()))}")
        hdr_assigned = sorted(name for name in counts if "HDR" in name)
        if hdr_assigned:
            print(f"{app}: HDR-assigned items={sum(counts[name] for name in hdr_assigned)}")
    return errors


def main() -> int:
    try:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        errors = verify(policy)
    except Exception as exc:
        print(f"Live media policy verification failed: {type(exc).__name__}: {exc}")
        return 2
    if errors:
        print("Live media policy verification failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Live media policy verification passed (read-only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
