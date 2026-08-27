# Operations

[English](OPERATIONS.md) · [Русский](ru/OPERATIONS.md)

## Trusted access

The stack publishes management HTTP ports only through two Caddy gateways:

- LAN: `10.0.0.88`
- Tailscale: `100.77.77.77`

Application containers are not directly published. FlareSolverr and the Docker API proxy are internal-only. qBittorrent peer traffic and Jellyfin discovery remain LAN-only.

Examples:

```text
Jellyfin     http://10.0.0.88:8096     http://100.77.77.77:8096
Homarr       http://10.0.0.88:7575     http://100.77.77.77:7575
Uptime Kuma  http://10.0.0.88:3001     http://100.77.77.77:3001
```

Tailscale Serve on HTTPS port 443 is already owned by the Hermes dashboard and is intentionally not modified by this stack.

## Docker API boundary

Homarr no longer mounts `/var/run/docker.sock`. It uses an internal `docker-socket-proxy` with read-only endpoint allowlisting and `POST=0`. The proxy is on an internal Docker network and has no host port.

## Monitoring

Uptime Kuma is created with SQLite and can be initialized idempotently:

```sh
make configure-monitoring
```

Credentials live outside Git in:

```text
~/.config/jellyfin-media-server/uptime-kuma.env
```

The configuration job creates HTTP monitors for all long-running web services. Add a notification provider in the Uptime Kuma UI if push alerts are required.

## Encrypted backup

The host uses a Restic repository on the external media volume. Configuration and password files stay outside Git:

```text
~/.config/jellyfin-media-server/restic.env
~/.config/jellyfin-media-server/restic-password
```

Run an application-consistent backup:

```sh
make backup
```

The command stops the stack, backs up `APPDATA_ROOT` and `stack/.env`, resumes the stack even on failure, checks repository integrity, and applies retention: 7 daily, 4 weekly, and 12 monthly snapshots.

Prove restore usability:

```sh
make verify-backup
```

The restore check uses a disposable directory, restores the latest snapshot, validates every actual SQLite database with `PRAGMA integrity_check`, runs `restic check`, and deletes plaintext afterward.

## Verification

```sh
make test
RUN_DEEP_CHECKS=1 RUN_EXTERNAL_CHECKS=1 make verify
```

The live gate checks both LAN and Tailscale paths, Docker health, restart counts, Arr application health, FlareSolverr internal reachability, restricted Homarr Docker API access, Recyclarr, qbit_manage, and external Prowlarr HTTPS.

## Recovery

The pre-change Git tag is:

```text
pre-secure-operations-20260828
```

Runtime data also remains recoverable from the encrypted Restic snapshot. If a rollout fails, restore the previous Compose revision and run `make up`; do not delete `APPDATA_ROOT`.
