#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from typing import Any

import socketio  # type: ignore[import-not-found]
from uptime_kuma_api import MonitorType, UptimeKumaApi  # type: ignore[import-not-found]
from uptime_kuma_api.api import _check_arguments_monitor, _convert_monitor_input  # type: ignore[import-not-found]

# Uptime Kuma 2.x behind Caddy is reliable over WebSocket; the client library
# otherwise starts with long polling, which the setup endpoint does not answer.
_socketio_connect = socketio.Client.connect


def _websocket_connect(self: socketio.Client, *args: Any, **kwargs: Any) -> Any:
    kwargs["transports"] = ["websocket"]
    return _socketio_connect(self, *args, **kwargs)


socketio.Client.connect = _websocket_connect

API_URL = os.environ.get("UPTIME_KUMA_URL", "http://127.0.0.1:3001")
USERNAME = os.environ.get("UPTIME_KUMA_USERNAME")
PASSWORD = os.environ.get("UPTIME_KUMA_PASSWORD")

MONITORS: tuple[dict[str, Any], ...] = (
    {"name": "Jellyfin", "url": "http://jellyfin:8096/System/Info/Public"},
    {"name": "Jellyseerr", "url": "http://jellyseerr:5055/api/v1/status"},
    {"name": "Aperture", "url": "http://aperture:3000/"},
    {"name": "qBittorrent", "url": "http://qbittorrent:9090/"},
    {"name": "Prowlarr", "url": "http://prowlarr:9696/"},
    {"name": "Sonarr", "url": "http://sonarr:8989/"},
    {"name": "Radarr", "url": "http://radarr:7878/"},
    {"name": "Bazarr", "url": "http://bazarr:6767/"},
    {"name": "Jackett", "url": "http://jackett:9117/UI/Dashboard", "accepted_statuscodes": ["200-299", "300-399", "400", "401", "403"]},
    {"name": "FlareSolverr", "url": "http://flaresolverr:8191/"},
    {"name": "Autobrr", "url": "http://autobrr:7474/"},
    {"name": "TorrServer", "url": "http://torrserver:18090/"},
    {"name": "Profilarr", "url": "http://profilarr:6868/"},
    {"name": "Homarr", "url": "http://homarr:7575/"},
)


def require_credentials() -> None:
    if not USERNAME or not PASSWORD:
        raise SystemExit("Set UPTIME_KUMA_USERNAME and UPTIME_KUMA_PASSWORD")


def main() -> int:
    require_credentials()
    with UptimeKumaApi(API_URL) as api:
        if api.need_setup():
            api.setup(USERNAME, PASSWORD)
        api.login(USERNAME, PASSWORD)
        existing = {monitor["name"] for monitor in api.get_monitors()}
        added = 0
        for monitor in MONITORS:
            if monitor["name"] in existing:
                continue
            data = api._build_monitor_data(
                type=MonitorType.HTTP,
                name=monitor["name"],
                url=monitor["url"],
                interval=60,
                retryInterval=20,
                maxretries=2,
                timeout=10,
                accepted_statuscodes=monitor.get("accepted_statuscodes", ["200-299", "300-399", "401", "403"]),
            )
            # Uptime Kuma 2.x made `conditions` non-null; uptime-kuma-api
            # 1.2.1 still targets the 1.x schema and omits this field.
            data["conditions"] = []
            _convert_monitor_input(data)
            _check_arguments_monitor(data)
            api._call("add", data)
            added += 1
        print(f"Uptime Kuma configured: {len(existing)} existing, {added} added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
