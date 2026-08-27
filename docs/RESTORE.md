# Restore and rollback

[English](RESTORE.md) · [Русский](ru/RESTORE.md)

## 1. Prepare the host

Install Git, Docker Engine/Desktop with Compose v2, Make, and Python 3. Confirm that the registries referenced by `stack/versions.env` are reachable.

## 2. Configure local inputs

```sh
make init
# Edit stack/.env: absolute paths, UID/GID, timezone, and a new Homarr key.
make test
```

Do not reuse credentials from Git history. `stack/.env` must remain untracked.

## 3. Start from clean state

```sh
make pull
make up
make ps
```

Configure applications in this order:

1. qBittorrent
2. Prowlarr and/or Jackett
3. Sonarr and Radarr
4. Bazarr and Recyclarr
5. Jellyfin
6. Jellyseerr and Aperture
7. Homarr and optional services

Use `/media` consistently inside every container to avoid import and hardlink path mismatches.

## 4. Restore application state

Stop the stack, restore an encrypted `APPDATA_ROOT` snapshot, and verify ownership against `PUID` and `PGID` before startup.

```sh
make up
make verify
```

Do not copy active SQLite databases without a consistent filesystem snapshot. Prefer each application's backup function or stop the relevant containers first.

## 5. Roll back

Return to the previous Git revision and restore a compatible `APPDATA_ROOT` snapshot. Running an older container against a database migrated by a newer release is not a safe rollback.
