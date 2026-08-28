#!/usr/bin/env python3
"""Validate the repository's SDR-first and future-HDR media policy."""
from __future__ import annotations

import json
import sys
from pathlib import Path

APPS = ("sonarr", "radarr")


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("policy") != "sdr-first":
        errors.append("policy must be sdr-first")
    active = data.get("active_production_profile", {})
    future = data.get("future_profiles", {})
    formats = data.get("required_custom_formats", {})
    for app in APPS:
        profile = active.get(app)
        if not isinstance(profile, str) or "SDR" not in profile or "HDR" in profile:
            errors.append(f"{app}: active production profile must be SDR-only")
        future_profiles = future.get(app)
        if not isinstance(future_profiles, list) or len(future_profiles) != len(set(future_profiles)):
            errors.append(f"{app}: future profiles must be a unique list")
        elif not all("SDR" in item or "HDR" in item for item in future_profiles):
            errors.append(f"{app}: future profiles contain an unknown media policy")
        required = set(formats.get(app, []))
        for name in ("RU SDR", "RU HDR", "RU DV", "RU Reject HDR DV HLG", "RU Reject AV1"):
            if name not in required:
                errors.append(f"{app}: missing required custom format {name}")
    rules = data.get("rules", {})
    if rules.get("automatic_acquisition") != "active_production_profile_only":
        errors.append("automatic acquisition must use the active production profile only")
    if rules.get("hdr_profiles") != "manual_or_future_hardware":
        errors.append("HDR profiles must remain manual/future-hardware profiles")
    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("stack/media-policy.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Media policy validation failed: {exc}")
        return 2
    errors = validate(data)
    if errors:
        print("Media policy validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Media policy validation passed ({path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
