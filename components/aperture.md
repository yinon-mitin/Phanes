# Aperture component lock

[English](aperture.md) · [Русский](aperture.ru.md)

Aperture is a third-party source checkout and is not vendored into this backup.

- Upstream: https://github.com/akhilmulpurii/aperture.git
- Branch at audit time: `main`
- Revision: `21394ca` (`v1.2.72`)
- Local customization: `patches/aperture-Dockerfile.patch`
- Compose status: active as the pinned `akhilmulpuri/aperture-web` amd64 image.

The active distribution consumes the immutable upstream image from
`stack/versions.env`. The checkout and patch below are retained as the source
contract for a future custom image; they are not used by `make up` today.

Restore the source checkout:

```sh
git clone https://github.com/akhilmulpurii/aperture.git stack/aperture
git -C stack/aperture checkout 21394ca
git -C stack/aperture apply --unidiff-zero ../../patches/aperture-Dockerfile.patch
```

The patch changes the Dockerfile's exposed/health-check port from 3000 to 3232. Before enabling the service, verify that the application itself is configured to listen on 3232; `EXPOSE` alone does not change the listening port.
