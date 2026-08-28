# SDR-first Jellyfin Media Policy Implementation Plan

> **For Hermes:** Execute this plan task-by-task with tests before mutations.

**Goal:** Make SDR the only automatically acquired and preferred production media format while preserving validated HDR profiles for future television hardware.

**Architecture:** Sonarr and Radarr retain separate SDR and HDR quality profiles. SDR profiles are assigned to active libraries and download automation; HDR profiles remain available but isolated from automatic acquisition. Recyclarr/Profilarr owns profile definitions, while this repository owns the policy contract and verification.

**Tech Stack:** Docker Compose, OrbStack, Sonarr API v3, Radarr API v3, Recyclarr, Profilarr, qBittorrent, Python contract tests, Uptime Kuma.

---

## Current verified state

Live Sonarr and Radarr expose the following profiles:

- `RU 1080p SDR`
- `RU 2160p SDR`
- `RU 1080p HDR`
- `RU 2160p HDR`
- `RU 2160p SDR Fallback 1080p SDR`
- `RU 2160p HDR Fallback 1080p HDR`

Live custom formats include SDR/HDR/DV signals and rejection formats for HDR DV HLG, AV1, AI, BR-DISK, low quality, and upscale content.

- `RU 2160p SDR` is the active production profile for automatic acquisition.
- `RU 1080p SDR` is the fallback when no suitable 2160p SDR release exists.
- Existing `RU 2160p SDR` and `RU 2160p SDR Fallback 1080p SDR` assignments remain SDR-compatible.
- HDR profiles remain future-ready and available for manual assignment.
- HDR/DV releases receive a lower score or rejection under SDR profiles.
- SDR fallback profiles remain available for future 4K SDR adoption.
- No library migration or mass replacement is performed automatically.

## Tasks

### Task 1: Record the media policy manifest

Files:

- Create: `stack/media-policy.json`
- Modify: `docs/OPERATIONS.md`
- Modify: `docs/ru/OPERATIONS.md`

Define the canonical profile names, active profile, future profiles, required custom formats, and SDR/HDR policy. Keep this file declarative and secret-free.

Validation:

```sh
python3 scripts/validate_media_policy.py
```

### Task 2: Add static policy contract tests

Files:

- Create: `scripts/validate_media_policy.py`
- Create: `tests/test_media_policy.py`
- Modify: `Makefile`

Verify:

- both Sonarr and Radarr have all six profile names;
- exactly one active production profile is selected per application;
- active profiles contain `SDR`;
- future profiles contain `HDR`;
- required HDR/DV rejection formats are declared;
- no profile name is ambiguous or duplicated.

### Task 3: Add live Arr policy verification

Files:

- Create: `scripts/verify_media_policy_live.py`
- Modify: `Makefile`
- Modify: `stack/verify-stack.sh`

Use local API keys from existing ignored XML config files. Print only profile names, IDs, and pass/fail status. Verify live Sonarr/Radarr profile names and active profile assignment without changing Arr state.

### Task 4: Confirm active library assignments

Run read-only API inventory for every Sonarr series and Radarr movie:

- current quality profile;
- library path;
- HDR/SDR policy classification;
- missing or ambiguous assignment.

Produce a redacted report. Apply changes only to explicitly classified SDR libraries after review.

### Task 5: Verify Recyclarr/Profilarr ownership

Run:

```sh
make arr-queue-audit
make configure-monitoring
```

Then verify that profile synchronization preserves SDR active profiles and HDR future profiles. Keep one owner for profile writes and use the other tool for validation or explicitly scoped synchronization.

### Task 6: Add media quality smoke checks

Validate representative releases against the policy:

- SDR 1080p WEB-DL accepted;
- SDR 2160p accepted for future profile;
- HDR10/HDR10+ rejected or deprioritized by SDR profiles;
- Dolby Vision rejected or deprioritized by SDR profiles;
- AV1 handled according to the current hardware policy;
- 10-bit SDR remains accepted where supported.

No downloads are started by this check.

### Task 7: Add operational safeguards

Document:

- current television policy: SDR-first;
- future HDR activation procedure;
- profile ownership;
- backup before profile changes;
- one-library-at-a-time migration;
- rollback through previous profile assignment.

### Task 8: Add CI and update gates

Extend CI with:

- static media policy validation;
- live verification as an optional local target;
- immutable image checks;
- Recyclarr preview;
- Arr API health;
- documentation parity.

### Task 9: Final verification and release

Run:

```sh
make test ENV_FILE=stack/.env.example
make arr-queue-audit
make verify-media-policy-live ENV_FILE=stack/.env
RUN_DEEP_CHECKS=1 RUN_EXTERNAL_CHECKS=1 make verify ENV_FILE=stack/.env
make verify-backup ENV_FILE=stack/.env
```

Commit in separate logical commits:

1. `docs: define SDR-first media policy`
2. `test: validate media profile contract`
3. `feat: verify live Arr media policy`
4. `docs: document HDR activation workflow`

Open a PR and merge only after CI and live verification pass.

## Risks and boundaries

- Existing media files remain untouched.
- Existing torrents remain untouched.
- Profile changes are declarative and reviewed before application.
- HDR remains available for future hardware.
- Chromecast smoke testing stays manual because the current playback path is already verified and working.
- Secrets remain in ignored runtime configuration.
