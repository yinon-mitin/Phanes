# Contributing

[English](CONTRIBUTING.md) · [Русский](CONTRIBUTING.ru.md)

This repository is a private infrastructure distribution. Keep changes small, reviewable, and free of runtime data.

## Workflow

1. Create a branch from `main`.
2. Change the Compose contract, documentation, or automation.
3. Run `make test ENV_FILE=stack/.env.example`.
4. If images change, run `make update-lock` and review every digest.
5. Open a pull request describing migration and rollback impact.

## Rules

- Never commit `.env`, `appdata`, media names, torrent state, API keys, tokens, databases, logs, or backups.
- Do not replace immutable digests with floating tags.
- Document new ports, mounts, state boundaries, and restore requirements.
- Treat database migrations as non-reversible until a restore has been tested.
- Keep GitHub Actions pinned by commit SHA.

## Acceptance

A change is ready when the static gate passes, the staged diff is reviewed, and any runtime-affecting change has a rollback path. A local Compose validation is not evidence of a successful production rollout.
