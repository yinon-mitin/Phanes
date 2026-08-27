#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$ROOT/ops/com.example.jellyfin-media-server.backup.plist.template"
DESTINATION="$HOME/Library/LaunchAgents/com.yinon.jellyfin-media-server.backup.plist"
mkdir -p "$(dirname "$DESTINATION")" "$HOME/Library/Logs"

python3 -c 'import pathlib,sys; template=pathlib.Path(sys.argv[1]).read_text(); template=template.replace("com.example.jellyfin-media-server.backup", "com.yinon.jellyfin-media-server.backup").replace("__REPO_ROOT__", sys.argv[2]).replace("__HOME__", str(pathlib.Path.home())); pathlib.Path(sys.argv[3]).write_text(template)' "$TEMPLATE" "$ROOT" "$DESTINATION"
plutil -lint "$DESTINATION"

service="gui/$(id -u)/com.yinon.jellyfin-media-server.backup"
if launchctl print "$service" >/dev/null 2>&1; then
  launchctl bootout "$service"
fi
launchctl bootstrap "gui/$(id -u)" "$DESTINATION"
launchctl enable "$service"
printf 'Installed daily backup job: %s\n' "$DESTINATION"
