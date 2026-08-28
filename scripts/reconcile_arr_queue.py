#!/usr/bin/env python3
"""Safely reconcile stale Sonarr/Radarr manual-interaction queue items.

The command is dry-run by default. It never removes torrents or data. In apply
mode it configures qBittorrent imported categories and moves only completed
warning items whose library file is already confirmed present. Unmatched Sonarr
items require an explicit quarantine flag.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "stack/.env"
DOCKER_CONTEXT = "orbstack"
QBIT_CONTAINER = "jellyfin-media-server-qbittorrent-1"
QBIT_URL = "http://127.0.0.1:9090/api/v2"
CATEGORY_SAVE_PATH = "/media/downloads/torrents/complete"

APPS = {
    "sonarr": {
        "port": 8989,
        "id_field": "episodeId",
        "imported_field": "tvImportedCategory",
        "active_category": "sonarr",
        "imported_category": "sonarr-imported",
    },
    "radarr": {
        "port": 7878,
        "id_field": "movieId",
        "imported_field": "movieImportedCategory",
        "active_category": "radarr",
        "imported_category": "radarr-imported",
    },
}


def safe_completed_downloads(
    records: Iterable[Mapping[str, Any]],
    library_files: Mapping[int, bool],
    id_field: str,
) -> List[str]:
    hashes = {
        str(record.get("downloadId", "")).lower()
        for record in records
        if record.get("status") == "completed"
        and record.get("trackedDownloadStatus") == "warning"
        and isinstance(record.get(id_field), int)
        and library_files.get(int(record[id_field])) is True
        and record.get("downloadId")
    }
    return sorted(hashes)


def set_field(client: Dict[str, Any], field_name: str, value: str) -> bool:
    for field in client.get("fields", []):
        if field.get("name") == field_name:
            if field.get("value") == value:
                return False
            field["value"] = value
            return True
    raise KeyError("download-client field is absent: " + field_name)


def env_value(name: str) -> str:
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith(name + "="):
            return raw_line.split("=", 1)[1].strip()
    raise RuntimeError("missing environment value: " + name)


def api_key(app: str) -> str:
    value = ET.parse(ROOT / "appdata" / app / "config.xml").getroot().findtext("ApiKey")
    if not value:
        raise RuntimeError("missing API key for " + app)
    return value


def arr_request(app: str, path: str, method: str = "GET", body: Any = None) -> Any:
    config = APPS[app]
    url = "http://{}:{}/api/v3/{}".format(env_value("LAN_IP"), config["port"], path)
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"X-Api-Key": api_key(app), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read()
    return json.loads(payload) if payload else None


def qbit_http_success(status: int, allow_conflict: bool = False) -> bool:
    return 200 <= status < 300 or (allow_conflict and status == 409)


def qbit_post(
    endpoint: str,
    values: Mapping[str, str],
    allow_conflict: bool = False,
) -> None:
    command = [
        "docker",
        "--context",
        DOCKER_CONTEXT,
        "exec",
        QBIT_CONTAINER,
        "curl",
        "-sS",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "-X",
        "POST",
    ]
    for key, value in values.items():
        command.extend(["--data-urlencode", "{}={}".format(key, value)])
    command.append("{}/{}".format(QBIT_URL, endpoint))
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=30)
    try:
        status = int(result.stdout.strip())
    except ValueError:
        status = 0
    if result.returncode != 0 or not qbit_http_success(status, allow_conflict):
        raise RuntimeError("qBittorrent API request failed: " + endpoint)


def ensure_qbit_category(category: str) -> None:
    qbit_post(
        "torrents/createCategory",
        {"category": category, "savePath": CATEGORY_SAVE_PATH},
        allow_conflict=True,
    )


def set_qbit_category(hashes: Iterable[str], category: str) -> None:
    normalized = sorted({value.lower() for value in hashes if value})
    if normalized:
        qbit_post("torrents/setCategory", {"hashes": "|".join(normalized), "category": category})


def qbit_categories() -> Dict[str, Any]:
    command = [
        "docker",
        "--context",
        DOCKER_CONTEXT,
        "exec",
        QBIT_CONTAINER,
        "curl",
        "-fsS",
        "{}/torrents/categories".format(QBIT_URL),
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError("cannot read qBittorrent categories")
    return json.loads(result.stdout)


def queue_records(app: str) -> List[Dict[str, Any]]:
    payload = arr_request(
        app,
        "queue?page=1&pageSize=500&includeUnknownSeriesItems=true&includeSeries=true&includeEpisode=true&includeMovie=true",
    )
    return list(payload.get("records", []))


def library_file_map(app: str, records: Iterable[Mapping[str, Any]]) -> Dict[int, bool]:
    id_field = str(APPS[app]["id_field"])
    ids = sorted(
        {
            int(record[id_field])
            for record in records
            if isinstance(record.get(id_field), int)
        }
    )
    endpoint = "episode" if app == "sonarr" else "movie"
    return {
        item_id: bool(arr_request(app, "{}/{}".format(endpoint, item_id)).get("hasFile"))
        for item_id in ids
    }


def configure_imported_category(app: str, apply: bool) -> bool:
    clients = arr_request(app, "downloadclient")
    clients = [client for client in clients if client.get("implementation") == "QBittorrent"]
    if len(clients) != 1:
        raise RuntimeError("expected exactly one qBittorrent client in " + app)
    client = clients[0]
    changed = set_field(
        client,
        str(APPS[app]["imported_field"]),
        str(APPS[app]["imported_category"]),
    )
    if changed and apply:
        arr_request(app, "downloadclient/{}".format(client["id"]), method="PUT", body=client)
    return changed


def warning_records(records: Iterable[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    return [
        record
        for record in records
        if record.get("status") == "completed"
        and record.get("trackedDownloadStatus") == "warning"
        and record.get("downloadId")
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="apply safe category changes")
    parser.add_argument(
        "--quarantine-sonarr-warnings",
        action="store_true",
        help="move unmatched completed Sonarr warnings to manual-review",
    )
    args = parser.parse_args()

    existing_categories = qbit_categories()
    summaries = []
    for app in ("sonarr", "radarr"):
        imported_category = str(APPS[app]["imported_category"])
        config_changed = configure_imported_category(app, args.apply)
        records = queue_records(app)
        files = library_file_map(app, records)
        safe_hashes = safe_completed_downloads(records, files, str(APPS[app]["id_field"]))
        warnings = warning_records(records)
        warning_hashes = {str(record["downloadId"]).lower() for record in warnings}
        unresolved_hashes = sorted(warning_hashes - set(safe_hashes))

        if args.apply:
            if imported_category not in existing_categories:
                ensure_qbit_category(imported_category)
            set_qbit_category(safe_hashes, imported_category)

        quarantined = []
        if app == "sonarr" and args.quarantine_sonarr_warnings:
            quarantined = unresolved_hashes
            if args.apply and quarantined:
                if "manual-review" not in existing_categories:
                    ensure_qbit_category("manual-review")
                set_qbit_category(quarantined, "manual-review")

        summaries.append(
            {
                "app": app,
                "importedCategoryConfigChanged": config_changed,
                "completedWarnings": len(warnings),
                "safeAlreadyInLibrary": len(safe_hashes),
                "quarantinedForManualReview": len(quarantined),
                "remainingUnsafe": len(set(unresolved_hashes) - set(quarantined)),
            }
        )

    print(json.dumps({"applied": args.apply, "summary": summaries}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
