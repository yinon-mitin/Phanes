#!/usr/bin/env python3
"""Bounded Phanes watchdog with safe Docker Compose self-healing.

Healthy runs are silent. Incident and recovery reports are written to stdout so
Hermes cron can deliver them without invoking an LLM.
"""
from __future__ import annotations

import concurrent.futures
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path(os.environ.get("ENV_FILE", ROOT / "stack/.env"))
VERSIONS_FILE = Path(os.environ.get("VERSIONS_FILE", ROOT / "stack/versions.env"))
COMPOSE_FILE = Path(os.environ.get("COMPOSE_FILE", ROOT / "stack/docker-compose.yml"))
DOCKER_CONTEXT = os.environ.get("DOCKER_CONTEXT_NAME", "orbstack")
STATE_DIR = Path(
    os.environ.get(
        "WATCHDOG_STATE_DIR",
        Path.home() / "Library/Application Support/Phanes",
    )
)
STATE_FILE = STATE_DIR / "watchdog.json"
LOCK_FILE = STATE_DIR / "watchdog.lock"
REMINDER_SECONDS = 3600

EXPECTED_SERVICES = {
    "aperture",
    "autobrr",
    "bazarr",
    "docker-socket-proxy",
    "flaresolverr",
    "gateway-lan",
    "gateway-tailscale",
    "homarr",
    "jackett",
    "jellyfin",
    "jellyseerr",
    "profilarr",
    "prowlarr",
    "qbittorrent",
    "qbit_manage",
    "radarr",
    "recyclarr",
    "sonarr",
    "torrserver",
    "uptime-kuma",
}
HTTP_CHECKS = (
    ("Jellyfin", 8096, "/System/Info/Public"),
    ("Jellyseerr", 5055, "/api/v1/status"),
    ("qBittorrent", 9090, "/"),
    ("Sonarr", 8989, "/"),
    ("Radarr", 7878, "/"),
    ("TorrServer", 18090, "/"),
    ("Uptime Kuma", 3001, "/"),
)
ACCEPTED_HTTP = {200, 204, 301, 302, 307, 401, 403}


@dataclass
class ProbeResult:
    issues: list[str]
    restart_counts: dict[str, int]
    unhealthy_services: list[str]
    daemon_available: bool


def run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout
        stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=stdout or "",
            stderr=stderr or "command timed out",
        )


def docker_command(*arguments: str) -> list[str]:
    return ["docker", "--context", DOCKER_CONTEXT, *arguments]


def compose_command(*arguments: str) -> list[str]:
    return docker_command(
        "compose",
        "--env-file",
        str(ENV_FILE),
        "--env-file",
        str(VERSIONS_FILE),
        "-f",
        str(COMPOSE_FILE),
        *arguments,
    )


def read_environment(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def load_state() -> dict[str, Any]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    temporary.replace(STATE_FILE)


def parse_compose_rows(output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def check_http(name: str, address: str, port: int, path: str) -> str | None:
    request = urllib.request.Request(
        f"http://{address}:{port}{path}",
        headers={"User-Agent": "Phanes-watchdog/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    except (OSError, urllib.error.URLError) as error:
        return f"{name} недоступен через {address} ({type(error).__name__})"
    if status not in ACCEPTED_HTTP:
        return f"{name} вернул HTTP {status} через {address}"
    return None


def probe(previous_restarts: dict[str, int] | None = None) -> ProbeResult:
    previous_restarts = previous_restarts or {}
    daemon = run(docker_command("info", "--format", "{{.ServerVersion}}"), timeout=10)
    if daemon.returncode != 0:
        return ProbeResult(
            issues=[f"Docker/OrbStack недоступен (context={DOCKER_CONTEXT})"],
            restart_counts={},
            unhealthy_services=[],
            daemon_available=False,
        )

    result = run(compose_command("ps", "--all", "--format", "json"), timeout=20)
    if result.returncode != 0:
        return ProbeResult(
            issues=["Не удалось получить состояние Docker Compose"],
            restart_counts={},
            unhealthy_services=[],
            daemon_available=True,
        )

    try:
        rows = parse_compose_rows(result.stdout)
    except json.JSONDecodeError:
        return ProbeResult(
            issues=["Docker Compose вернул некорректный статус"],
            restart_counts={},
            unhealthy_services=[],
            daemon_available=True,
        )

    by_service = {str(row.get("Service")): row for row in rows}
    issues: list[str] = []
    unhealthy: list[str] = []
    restart_counts: dict[str, int] = {}

    for service in sorted(EXPECTED_SERVICES):
        row = by_service.get(service)
        if row is None:
            issues.append(f"Контейнер {service} отсутствует")
            continue
        state = str(row.get("State", "unknown")).lower()
        health = str(row.get("Health", "")).lower()
        if state != "running":
            issues.append(f"{service}: state={state}")
            unhealthy.append(service)
        elif health == "unhealthy":
            issues.append(f"{service}: health=unhealthy")
            unhealthy.append(service)

        container_id = str(row.get("ID", ""))
        if not container_id:
            continue
        inspected = run(
            docker_command("inspect", "--format", "{{.RestartCount}}", container_id),
            timeout=5,
        )
        try:
            count = int(inspected.stdout.strip())
        except ValueError:
            continue
        restart_counts[service] = count
        previous = int(previous_restarts.get(service, count))
        if count - previous >= 3:
            issues.append(f"{service}: {count - previous} рестартов с прошлой проверки")
            if service not in unhealthy:
                unhealthy.append(service)

    if ENV_FILE.is_file():
        environment = read_environment(ENV_FILE)
        addresses = [environment.get("LAN_IP", ""), environment.get("TAILSCALE_IP", "")]
        jobs = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for address in filter(None, addresses):
                for name, port, path in HTTP_CHECKS:
                    jobs.append(executor.submit(check_http, name, address, port, path))
            for job in jobs:
                issue = job.result()
                if issue:
                    issues.append(issue)
    else:
        issues.append(f"Отсутствует runtime-конфигурация: {ENV_FILE}")

    if os.environ.get("WATCHDOG_FORCE_FAILURE") == "1":
        issues.append("Принудительный тестовый сбой watchdog")

    return ProbeResult(
        issues=sorted(set(issues)),
        restart_counts=restart_counts,
        unhealthy_services=sorted(set(unhealthy)),
        daemon_available=True,
    )


def recover(initial: ProbeResult) -> list[str]:
    if os.environ.get("WATCHDOG_DRY_RUN") == "1":
        return ["DRY-RUN: исправления отключены"]

    attempts: list[str] = []
    if not initial.daemon_available:
        if sys.platform == "darwin" and shutil.which("open"):
            launched = run(["open", "-gja", "OrbStack"], timeout=10)
            attempts.append(
                "Запуск OrbStack через launch services: "
                + ("успешно" if launched.returncode == 0 else "ошибка")
            )
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                status = run(docker_command("info"), timeout=5)
                if status.returncode == 0:
                    attempts.append("Docker daemon снова отвечает")
                    break
                time.sleep(2)
        else:
            attempts.append("Автозапуск Docker недоступен на этом хосте")

    if initial.daemon_available and initial.unhealthy_services:
        restarted = run(
            compose_command("restart", *initial.unhealthy_services),
            timeout=45,
        )
        attempts.append(
            "Перезапуск проблемных сервисов "
            + ", ".join(initial.unhealthy_services)
            + (": успешно" if restarted.returncode == 0 else ": ошибка")
        )

    started = run(compose_command("up", "-d", "--remove-orphans"), timeout=90)
    attempts.append(
        "Восстановление declarative Compose-состояния: "
        + ("успешно" if started.returncode == 0 else "ошибка/таймаут")
    )
    return attempts


def signature(issues: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(issues)).encode()).hexdigest()


def format_report(
    *,
    resolved: bool,
    issues: list[str],
    attempts: list[str],
    remaining: list[str] | None = None,
) -> str:
    title = "✅ Phanes: сервис автоматически восстановлен" if resolved else "🚨 Phanes: сбой не устранён"
    lines = [title, "", "Обнаружено:"]
    lines.extend(f"• {issue}" for issue in issues[:12])
    if len(issues) > 12:
        lines.append(f"• …ещё {len(issues) - 12}")
    lines.extend(["", "Попытки исправления:"])
    lines.extend(f"• {attempt}" for attempt in (attempts or ["Не выполнялись"]))
    if remaining:
        lines.extend(["", "Осталось неисправным:"])
        lines.extend(f"• {issue}" for issue in remaining[:12])
    lines.extend(["", "Результат: " + ("все контрольные проверки проходят." if resolved else "нужно ручное вмешательство.")])
    return "\n".join(lines)


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0

        state = load_state()
        previous_restarts = state.get("restart_counts", {})
        initial = probe(previous_restarts if isinstance(previous_restarts, dict) else {})
        now = int(time.time())

        if not initial.issues:
            if state.get("incident_open"):
                print(
                    format_report(
                        resolved=True,
                        issues=list(state.get("last_issues", ["Предыдущий сбой"])),
                        attempts=["Очередная проверка подтвердила восстановление"],
                    )
                )
            save_state(
                {
                    "incident_open": False,
                    "last_alert_at": state.get("last_alert_at", 0),
                    "last_signature": "",
                    "last_issues": [],
                    "restart_counts": initial.restart_counts,
                }
            )
            return 0

        attempts = recover(initial)
        final = probe(initial.restart_counts)
        resolved = not final.issues
        current_signature = signature(final.issues or initial.issues)
        should_report = resolved or (
            current_signature != state.get("last_signature")
            or now - int(state.get("last_alert_at", 0)) >= REMINDER_SECONDS
        )
        if should_report:
            print(
                format_report(
                    resolved=resolved,
                    issues=initial.issues,
                    attempts=attempts,
                    remaining=final.issues if final.issues else None,
                )
            )

        save_state(
            {
                "incident_open": not resolved,
                "last_alert_at": now if should_report else state.get("last_alert_at", 0),
                "last_signature": "" if resolved else current_signature,
                "last_issues": [] if resolved else final.issues,
                "restart_counts": final.restart_counts,
            }
        )
        return 0 if resolved else 1


if __name__ == "__main__":
    sys.exit(main())
