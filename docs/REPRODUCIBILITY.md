# Phanes reproducibility

[English](REPRODUCIBILITY.md) · [Русский](ru/REPRODUCIBILITY.md)

A release is reproducible when the same Git revision and local inputs produce the same Compose topology and OCI image references.

## Pinned inputs

- All 17 images are pinned in `stack/versions.env`.
- Sixteen images provide amd64 and arm64 manifests; Aperture is explicitly limited to `linux/amd64`.
- Compose does not select floating versions.
- `stack/.env.example` defines the machine-specific input contract without real secrets.
- The active Aperture image is pinned by digest. Its optional source checkout is pinned by Git revision and patch.
- Runtime databases and media catalogues are not Git inputs.

## Validation

```sh
make test ENV_FILE=stack/.env.example
```

The check rejects floating image references, missing image variables, unpinned digests, unexpected services, prohibited runtime files, and invalid Compose.

## Updating images

```sh
make update-lock
make test ENV_FILE=stack/.env.example
git diff -- stack/versions.env
```

Review each upstream changelog. Test the new lock against disposable state, then against a copy of production state before rollout.

## Limits

A digest fixes an OCI artifact. It does not fix the CPU, kernel, Docker Engine, filesystem behavior, or external APIs. Production promotion should test the target architecture and record the Docker/Compose version.

The Jellyfin Intro Skipper Docker Mod is excluded because its registry did not allow anonymous digest resolution. It should not return to the baseline without an immutable reference.
