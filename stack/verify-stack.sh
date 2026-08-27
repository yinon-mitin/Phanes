#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/stack/.env}"
VERSIONS_FILE="${VERSIONS_FILE:-$ROOT/stack/versions.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/stack/docker-compose.yml}"
failures=0

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

if [[ ! -f "$ENV_FILE" ]]; then
  printf 'Missing environment file: %s\n' "$ENV_FILE"
  exit 2
fi

docker_cmd=(docker)
if [[ -n "${DOCKER_CONTEXT_NAME:-}" ]]; then
  docker_cmd+=(--context "$DOCKER_CONTEXT_NAME")
fi
compose=("${docker_cmd[@]}" compose --env-file "$ENV_FILE" --env-file "$VERSIONS_FILE" -f "$COMPOSE_FILE")
if [[ "${ENABLE_NOTIFIARR:-0}" == 1 ]]; then
  compose+=(--profile notifiarr)
fi

if "${compose[@]}" config --quiet; then
  pass "Compose configuration"
else
  fail "Compose configuration"
fi

expected=(qbittorrent prowlarr sonarr radarr bazarr jellyseerr flaresolverr jellyfin profilarr homarr recyclarr autobrr torrserver jackett qbit_manage aperture)
if [[ "${ENABLE_NOTIFIARR:-0}" == 1 ]]; then
  expected+=(notifiarr)
fi
for service in "${expected[@]}"; do
  cid="$("${compose[@]}" ps -q "$service" 2>/dev/null || true)"
  if [[ -z "$cid" ]]; then
    fail "$service container exists"
    continue
  fi
  state="$("${docker_cmd[@]}" inspect --format '{{.State.Status}}' "$cid" 2>/dev/null || true)"
  health="$("${docker_cmd[@]}" inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || true)"
  restarts="$("${docker_cmd[@]}" inspect --format '{{.RestartCount}}' "$cid" 2>/dev/null || printf 999)"
  [[ "$state" == running ]] && pass "$service running" || fail "$service running (state=$state)"
  [[ "$health" != unhealthy ]] && pass "$service health=$health" || fail "$service health=unhealthy"
  [[ "$restarts" =~ ^[0-9]+$ && "$restarts" -lt 10 ]] && pass "$service restarts=$restarts" || fail "$service excessive restarts=$restarts"
done

http_checks=(
  'qbittorrent|9090|/' 'prowlarr|9696|/' 'sonarr|8989|/' 'radarr|7878|/'
  'bazarr|6767|/' 'jellyseerr|5055|/api/v1/status' 'flaresolverr|8191|/'
  'jellyfin|8096|/System/Info/Public' 'profilarr|6868|/' 'homarr|7575|/'
  'autobrr|7474|/' 'torrserver|18090|/'
  'jackett|9117|/UI/Dashboard' 'aperture|3000|/'
)
if [[ "${ENABLE_NOTIFIARR:-0}" == 1 ]]; then
  http_checks+=('notifiarr|5454|/')
fi
for spec in "${http_checks[@]}"; do
  IFS='|' read -r name port path <<<"$spec"
  code="$(curl -sS -o /dev/null --connect-timeout 2 --max-time 8 -w '%{http_code}' "http://127.0.0.1:${port}${path}" 2>/dev/null || true)"
  if [[ "$code" =~ ^(200|204|301|302|401|403)$ ]]; then
    pass "$name HTTP $code"
  else
    fail "$name HTTP ${code:-000}"
  fi
done

if [[ "${RUN_DEEP_CHECKS:-0}" == 1 ]]; then
  app_health_checks=('prowlarr|9696|v1' 'sonarr|8989|v3' 'radarr|7878|v3')
  appdata_root="$(python3 -c 'import sys; lines=open(sys.argv[1]).read().splitlines(); print(next(line.split("=",1)[1] for line in lines if line.startswith("APPDATA_ROOT=")))' "$ENV_FILE")"
  for spec in "${app_health_checks[@]}"; do
    IFS='|' read -r service port api_version <<<"$spec"
    if python3 -c 'import json,sys,urllib.request,xml.etree.ElementTree as ET; key=ET.parse(sys.argv[1]).getroot().findtext("ApiKey"); req=urllib.request.Request(sys.argv[2],headers={"X-Api-Key":key}); raise SystemExit(0 if json.load(urllib.request.urlopen(req,timeout=10)) == [] else 1)' "$appdata_root/$service/config.xml" "http://127.0.0.1:${port}/api/${api_version}/health" 2>/dev/null; then
      pass "$service application health"
    else
      fail "$service application health"
    fi
  done

  if "${compose[@]}" exec -T recyclarr recyclarr sync --preview >/dev/null 2>&1; then
    pass "Recyclarr preview sync"
  else
    fail "Recyclarr preview sync"
  fi

  if qbm_output="$("${compose[@]}" exec -T qbit_manage sh -lc 'python3 qbit_manage.py --run --dry-run' 2>&1)"; then
    [[ "$qbm_output" == *'Config Error:'* ]] && fail "qbit_manage configuration" || pass "qbit_manage configuration"
  else
    fail "qbit_manage execution"
  fi
fi

if [[ "${RUN_EXTERNAL_CHECKS:-0}" == 1 ]]; then
  if "${compose[@]}" exec -T prowlarr curl -4 -fsS -o /dev/null --connect-timeout 5 --max-time 15 'https://prowlarr.servarr.com/v1/update/master/changes?os=docker'; then
    pass "Prowlarr external DNS/HTTPS"
  else
    fail "Prowlarr external DNS/HTTPS"
  fi

  if [[ "${ENABLE_NOTIFIARR:-0}" == 1 ]]; then
    notifiarr_logs="$("${compose[@]}" --profile notifiarr logs --since 5m notifiarr 2>&1 || true)"
    if [[ "$notifiarr_logs" == *'401 Unauthorized'* ]]; then
      fail "Notifiarr account authentication"
    else
      pass "Notifiarr account authentication"
    fi
  fi
fi

if [[ $failures -eq 0 ]]; then
  printf '\nStack verification passed.\n'
  exit 0
fi
printf '\nStack verification failed: %d check(s).\n' "$failures"
exit 1
