# Phanes operations

[English](OPERATIONS.md) · [Русский](ru/OPERATIONS.md)

## Trusted access

The stack publishes management HTTP ports only through two Caddy gateways:

- LAN: `<LAN_IP>`
- Tailscale: `<TAILSCALE_IP>`

Application containers are not directly published. FlareSolverr and the Docker API proxy are internal-only. qBittorrent peer traffic and Jellyfin discovery remain LAN-only.

TorrServer is the deliberate exception: Chromecast/NUM clients receive a direct LAN socket at `${LAN_IP}:18090`. Tailscale access to the same port remains behind the Tailscale Caddy gateway.

Examples:

```text
Jellyfin     http://<LAN_IP>:8096     http://<TAILSCALE_IP>:8096
Homarr       http://<LAN_IP>:7575     http://<TAILSCALE_IP>:7575
Uptime Kuma  http://<LAN_IP>:3001     http://<TAILSCALE_IP>:3001
```

Tailscale Serve on HTTPS port 443 is already owned by the Hermes dashboard and is intentionally not modified by this stack.

## Container runtime: OrbStack

The production Compose stack runs in Docker context `orbstack`. OrbStack starts at login and owns all active Phanes containers; Docker Desktop is stopped and retained only as a rollback source with its old containers stopped.

Operational commands can select the runtime explicitly:

```sh
DOCKER_CONTEXT_NAME=orbstack RUN_DEEP_CHECKS=1 RUN_EXTERNAL_CHECKS=1 make verify
DOCKER_CONTEXT=orbstack make backup
```

The migration reuses host bind mounts, so no application database or media data is copied into a Docker-managed volume. Pinned images are pulled independently into OrbStack. FlareSolverr receives a larger shared-memory allocation, and Prowlarr waits for FlareSolverr health to avoid cold-start proxy failures.

Rollback procedure:

1. Stop the stack in OrbStack.
2. Start Docker Desktop.
3. Start the existing stopped Compose containers with context `desktop-linux`.
4. Do not run both stacks simultaneously against the shared `APPDATA_ROOT`.

## macOS firewall

The repository contains a narrowly scoped PF anchor that only governs media-stack ports. It permits `${LAN_CIDR}` to `${LAN_IP}` and the Tailscale CGNAT range `100.64.0.0/10` to `${TAILSCALE_IP}`, then blocks other sources for those exact ports. It does not set a global deny policy and does not touch Screen Sharing, AirPlay, Hermes, OrbStack, virtual machines, or other unrelated listeners. qBittorrent peer port `6881` is intentionally excluded.

Install it from an interactive macOS terminal with administrator authorization:

```sh
./scripts/install_macos_firewall.sh
```

The installer validates the complete PF configuration before loading it, creates `/etc/pf.conf.before-jellyfin-media-server`, enables the built-in macOS application firewall and stealth mode, and preserves automatic access for signed Apple/downloaded applications.

Remove only this project's PF anchor with:

```sh
./scripts/uninstall_macos_firewall.sh
```

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

The host watchdog complements Uptime Kuma by checking Docker/Compose state and
the primary LAN/Tailscale endpoints. A healthy run is silent. On instability it
performs bounded, non-upgrading recovery: restart failed services, reconcile the
existing digest-pinned Compose deployment, then probe it again. Its stdout is a
complete incident report suitable for a scheduler or notification gateway:

```sh
make watchdog
```

Run it every five minutes. Concurrent runs are locked, repeated unresolved
incidents are deduplicated for one hour, and no image pull, data deletion, or
configuration migration is attempted automatically. Set `WATCHDOG_DRY_RUN=1`
to test detection without remediation.

## Sonarr/Radarr manual-interaction queue

Persistent `Manual Interaction` notifications can be caused by completed
qBittorrent items remaining in the active `sonarr` or `radarr` category after
the library file is already present. The applications keep polling those
categories and report the old download again as `importPending` or
`importBlocked`.

Audit first:

```sh
make arr-queue-audit
```

The reconciler is fail-closed: it only moves a completed Radarr warning when
the corresponding movie has `hasFile=true`. It never deletes torrents or
payload data. Apply the verified repair with:

```sh
make arr-queue-reconcile
```

The successful production repair configured `sonarr-imported` and
`radarr-imported` as qBittorrent's post-import categories. Twenty-five stale
Radarr torrents whose movies were already present were moved to
`radarr-imported`. Two Sonarr items that did not represent importable episodes
were preserved under `manual-review`. The active queues then reported zero
manual-interaction warnings. Future successful imports leave the active
category automatically and can continue seeding from the unchanged save path.

## SDR-first media policy

The current television is optimized for SDR playback. Automatic acquisition uses
`RU 2160p SDR` with fallback to `RU 1080p SDR`; existing `RU 2160p SDR` and
`RU 2160p SDR Fallback 1080p SDR` assignments remain SDR-compatible. HDR profiles are retained as future-ready
profiles for a later display upgrade and are verified separately.

The canonical policy is stored in `stack/media-policy.json`. Validate it with:

```sh
make validate-media-policy
make verify-media-policy-live ENV_FILE=stack/.env
```

The live verifier is read-only and reports the distribution of Sonarr/Radarr
items by quality profile. Current HDR assignment count is zero. Radarr currently
has 40 items with the legacy `Unknown` profile; these are tracked for a reviewed,
one-library-at-a-time assignment to the SDR production profile.

The implementation plan is available at
`.hermes/plans/2026-08-28_135500-sdr-first-media-policy.md`.

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
