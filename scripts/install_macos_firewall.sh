#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/stack/.env}"
ANCHOR_SOURCE="$ROOT/ops/pf.anchors/com.yinon.jellyfin-media-server.template"
ANCHOR_DESTINATION="/etc/pf.anchors/com.yinon.jellyfin-media-server"
RENDERED_ANCHOR="$(mktemp)"
PF_CONF="/etc/pf.conf"
BACKUP="/etc/pf.conf.before-jellyfin-media-server"
ANCHOR_DECLARATION='anchor "com.yinon.jellyfin-media-server"'
ANCHOR_LOAD='load anchor "com.yinon.jellyfin-media-server" from "/etc/pf.anchors/com.yinon.jellyfin-media-server"'
FIREWALL_TOOL="/usr/libexec/ApplicationFirewall/socketfilterfw"

cleanup() { rm -f "$RENDERED_ANCHOR"; }
trap cleanup EXIT

[[ -f "$ANCHOR_SOURCE" ]] || { printf 'Missing anchor: %s\n' "$ANCHOR_SOURCE" >&2; exit 2; }
[[ -f "$ENV_FILE" ]] || { printf 'Missing environment file: %s\n' "$ENV_FILE" >&2; exit 2; }

python3 -c 'from pathlib import Path; import sys
values={};
for raw in Path(sys.argv[1]).read_text().splitlines():
    if raw and not raw.startswith("#") and "=" in raw:
        key,value=raw.split("=",1); values[key]=value
required=("LAN_IP","TAILSCALE_IP","LAN_CIDR")
missing=[key for key in required if not values.get(key)]
if missing: raise SystemExit("Missing values: "+", ".join(missing))
text=Path(sys.argv[2]).read_text()
for key in required: text=text.replace("__"+key+"__",values[key])
Path(sys.argv[3]).write_text(text)' "$ENV_FILE" "$ANCHOR_SOURCE" "$RENDERED_ANCHOR"

sudo cp -p "$PF_CONF" "$BACKUP"
sudo install -m 600 "$RENDERED_ANCHOR" "$ANCHOR_DESTINATION"

sudo /usr/bin/python3 -c 'from pathlib import Path; import sys
path=Path(sys.argv[1]); declaration=sys.argv[2]; load=sys.argv[3]; text=path.read_text(); lines=[] if not text.endswith("\n") else []; additions=[line for line in (declaration,load) if line not in text]; path.write_text(text+("" if text.endswith("\n") else "\n")+"\n".join(additions)+( "\n" if additions else ""))' "$PF_CONF" "$ANCHOR_DECLARATION" "$ANCHOR_LOAD"

sudo pfctl -nf "$PF_CONF"
sudo pfctl -f "$PF_CONF"
if ! sudo pfctl -s info | /usr/bin/grep -q 'Status: Enabled'; then
  sudo pfctl -E
fi

sudo "$FIREWALL_TOOL" --setglobalstate on
sudo "$FIREWALL_TOOL" --setstealthmode on
sudo "$FIREWALL_TOOL" --setallowsigned on
sudo "$FIREWALL_TOOL" --setallowsignedapp on

printf 'Installed scoped PF anchor and enabled the macOS application firewall.\n'
printf 'Backup of the prior PF configuration: %s\n' "$BACKUP"
printf 'Review active rules with: sudo pfctl -a com.yinon.jellyfin-media-server -sr\n'
