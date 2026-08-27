#!/usr/bin/env bash
set -euo pipefail

PF_CONF="/etc/pf.conf"
ANCHOR_DESTINATION="/etc/pf.anchors/com.yinon.jellyfin-media-server"
ANCHOR_DECLARATION='anchor "com.yinon.jellyfin-media-server"'
ANCHOR_LOAD='load anchor "com.yinon.jellyfin-media-server" from "/etc/pf.anchors/com.yinon.jellyfin-media-server"'

sudo cp -p "$PF_CONF" "/etc/pf.conf.before-jellyfin-firewall-removal"
sudo /usr/bin/python3 -c 'from pathlib import Path; import sys
path=Path(sys.argv[1]); remove=set(sys.argv[2:]); lines=[line for line in path.read_text().splitlines() if line not in remove]; path.write_text("\n".join(lines)+"\n")' "$PF_CONF" "$ANCHOR_DECLARATION" "$ANCHOR_LOAD"
sudo rm -f "$ANCHOR_DESTINATION"
sudo pfctl -nf "$PF_CONF"
sudo pfctl -f "$PF_CONF"
printf 'Removed only the Jellyfin PF anchor. The macOS application firewall remains enabled.\n'
