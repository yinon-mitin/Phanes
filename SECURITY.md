# Security policy

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

- Keep the GitHub repository private.
- Review image-lock updates before deployment.
- Back up application state before container upgrades.
- Do not expose service ports directly to the public Internet without authentication, TLS, and an explicit network policy.
- Treat the Docker socket mount used by Homarr as privileged host access.
