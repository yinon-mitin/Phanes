#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/stack/.env}"
RESTIC_REPOSITORY="${RESTIC_REPOSITORY:?Set RESTIC_REPOSITORY}"
RESTIC_PASSWORD_FILE="${RESTIC_PASSWORD_FILE:?Set RESTIC_PASSWORD_FILE}"
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE

command -v restic >/dev/null 2>&1 || { printf 'restic is required\n' >&2; exit 2; }
command -v sqlite3 >/dev/null 2>&1 || { printf 'sqlite3 is required\n' >&2; exit 2; }

restore_dir="$(mktemp -d)"
cleanup() { rm -rf "$restore_dir"; }
trap cleanup EXIT

restic restore latest --tag jellyfin-media-server --target "$restore_dir"
chmod -R u+rwX "$restore_dir"

appdata_root="$(python3 -c 'import sys; lines=open(sys.argv[1]).read().splitlines(); print(next(line.split("=",1)[1] for line in lines if line.startswith("APPDATA_ROOT=")))' "$ENV_FILE")"
restored_appdata="$restore_dir$appdata_root"
[[ -d "$restored_appdata" ]] || { printf 'Restored APPDATA_ROOT is missing: %s\n' "$restored_appdata" >&2; exit 1; }

checked=0
while IFS= read -r -d '' database; do
  if ! python3 -c 'import sys; raise SystemExit(0 if open(sys.argv[1], "rb").read(16) == b"SQLite format 3\x00" else 1)' "$database"; then
    continue
  fi
  sqlite_scratch="$(mktemp -d "$restore_dir/sqlite.XXXXXX")"
  cp "$database" "$sqlite_scratch/database.db"
  [[ ! -f "${database}-wal" ]] || cp "${database}-wal" "$sqlite_scratch/database.db-wal"
  [[ ! -f "${database}-shm" ]] || cp "${database}-shm" "$sqlite_scratch/database.db-shm"
  if ! result="$(sqlite3 "$sqlite_scratch/database.db" 'PRAGMA integrity_check;' 2>&1)"; then
    printf 'Unable to inspect SQLite database: %s\n%s\n' "$database" "$result" >&2
    exit 1
  fi
  if [[ "$result" != ok ]]; then
    printf 'SQLite integrity failure: %s\n%s\n' "$database" "$result" >&2
    exit 1
  fi
  checked=$((checked + 1))
done < <(find "$restored_appdata" -type f \( -name '*.db' -o -name '*.sqlite' \) -print0)

[[ "$checked" -gt 0 ]] || { printf 'No SQLite databases were restored\n' >&2; exit 1; }
restic check
printf 'Restore verification passed: %d SQLite databases are consistent.\n' "$checked"
