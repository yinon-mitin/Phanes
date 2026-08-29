# Security policy

[English](SECURITY.md) · [Русский](SECURITY.ru.md)

## Reporting

Do not open an issue containing credentials, server addresses, media names, logs, database excerpts, or screenshots with private data. Report security findings privately to the repository owner through an agreed private channel.

## Repository boundaries

This repository must contain only reproducible infrastructure definitions and sanitized templates. Runtime state belongs under `APPDATA_ROOT`; media belongs under `MEDIA_ROOT`; secrets belong in `stack/.env` or a secret manager. All are excluded from Git.

Before every push, run:

```sh
make safety
git diff --cached
```

If a secret is committed, removing the file in a later commit is insufficient. Rotate the credential immediately and rewrite Git history before sharing the repository.

## Deployment

- Keep runtime state, credentials, and sensitive infrastructure details private; the repository itself is public.
- Review image-lock updates before deployment.
- Back up application state before container upgrades.
- Do not expose service ports directly to the public Internet without authentication, TLS, and an explicit network policy.
- Keep the Docker socket mounted only in `docker-socket-proxy`; Homarr must use the internal proxy with `POST=0` and no host-published proxy port.
- Keep management HTTP ports bound only to the configured LAN and Tailscale interface gateways.
