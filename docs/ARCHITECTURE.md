# Architecture

[English](ARCHITECTURE.md) · [Русский](ru/ARCHITECTURE.md)

## Data flow

```text
LAN 10.0.0.88 --------> Caddy gateway-lan -------> application HTTP ports
Tailscale 100.77.77.77 -> Caddy gateway-tailscale -> application HTTP ports
Indexer -> Prowlarr/Jackett -> Sonarr/Radarr -> qBittorrent
                                           -> MEDIA_ROOT
User -> Jellyseerr -> Sonarr/Radarr         -> Jellyfin -> Client
User -> Aperture ---------------------------> Jellyfin API
Bazarr ------------------------------------> subtitles
Recyclarr -> quality profiles in Sonarr/Radarr
Homarr/Notifiarr -> dashboard and notifications
Homarr -> restricted docker-socket-proxy -> Docker read-only APIs
Uptime Kuma -> internal HTTP health probes
```

## State boundaries

| Layer | Desired state | Runtime state | Recovery |
| --- | --- | --- | --- |
| Containers and network | `stack/docker-compose.yml` | Docker | Recreated |
| Image versions | `stack/versions.env` | Registry cache | Pulled by digest |
| Local paths and secrets | `stack/.env` | Outside Git | Manual or secret manager |
| Application settings | `APPDATA_ROOT` | SQLite/XML/JSON | Encrypted backup |
| Media library | `MEDIA_ROOT` | User files | Separate backup policy |
| Monitoring | Uptime Kuma definition + setup script | `APPDATA_ROOT/uptime-kuma` | Encrypted Restic backup |
| Encrypted backup | Backup/restore scripts | Restic repository outside Git | Tested temporary restore |

## Verification levels

- Implemented: Compose topology, immutable image lock, environment template, local checks, and CI.
- Locally verified: Compose structure, pinned images, repository safety, and documentation links.
- Live verified: `make verify` against a running Docker host.
- Manual: first-run UI setup, API-key exchange, and application pairing.

Without an `APPDATA_ROOT` backup, the repository restores the platform but not users, history, queues, or application settings.
