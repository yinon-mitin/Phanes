#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/stack/.env}"
VERSIONS_FILE="${VERSIONS_FILE:-$ROOT/stack/versions.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/stack/docker-compose.yml}"
RESTIC_REPOSITORY="${RESTIC_REPOSITORY:?Set RESTIC_REPOSITORY to the encrypted backup destination}"
RESTIC_PASSWORD_FILE="${RESTIC_PASSWORD_FILE:?Set RESTIC_PASSWORD_FILE outside the repository}"
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE

command -v restic >/dev/null 2>&1 || { printf 'restic is required\n' >&2; exit 2; }
[[ -r "$ENV_FILE" ]] || { printf 'Missing environment file: %s\n' "$ENV_FILE" >&2; exit 2; }
[[ -r "$RESTIC_PASSWORD_FILE" ]] || { printf 'Missing restic password file: %s\n' "$RESTIC_PASSWORD_FILE" >&2; exit 2; }

compose=(docker compose --env-file "$ENV_FILE" --env-file "$VERSIONS_FILE" -f "$COMPOSE_FILE")
"${compose[@]}" config --quiet

appdata_root="$(python3 -c 'import sys; lines=open(sys.argv[1]).read().splitlines(); print(next(line.split("=",1)[1] for line in lines if line.startswith("APPDATA_ROOT=")))' "$ENV_FILE")"
[[ -d "$appdata_root" ]] || { printf 'APPDATA_ROOT does not exist: %s\n' "$appdata_root" >&2; exit 2; }

if ! restic snapshots >/dev/null 2>&1; then
  if [[ "${INITIALIZE_REPOSITORY:-0}" != 1 ]]; then
    printf 'Restic repository is not initialized; rerun once with INITIALIZE_REPOSITORY=1\n' >&2
    exit 2
  fi
  restic init
fi

stack_stopped=0
resume_stack() {
  if [[ "$stack_stopped" == 1 ]]; then
    "${compose[@]}" up -d
    stack_stopped=0
  fi
}
trap resume_stack EXIT

printf 'Stopping stack for an application-consistent snapshot...\n'
"${compose[@]}" stop
stack_stopped=1

restic backup "$appdata_root" "$ENV_FILE" \
  --tag jellyfin-media-server \
  --exclude-caches \
  --exclude '*/logs/*' \
  --exclude '*/log/*'

resume_stack

restic check --read-data-subset="${RESTIC_CHECK_SUBSET:-5%}"
restic forget \
  --tag jellyfin-media-server \
  --keep-daily "${RESTIC_KEEP_DAILY:-7}" \
  --keep-weekly "${RESTIC_KEEP_WEEKLY:-4}" \
  --keep-monthly "${RESTIC_KEEP_MONTHLY:-12}" \
  --prune

printf 'Encrypted backup completed and stack resumed.\n'
