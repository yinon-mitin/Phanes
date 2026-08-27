# Компонент Aperture

[English](aperture.md) · [Русский](aperture.ru.md)

Aperture используется как сторонний компонент и не копируется в этот репозиторий.

- Upstream: https://github.com/akhilmulpurii/aperture.git
- Ветка на момент аудита: `main`
- Ревизия: `21394ca` (`v1.2.72`)
- Локальное изменение: `patches/aperture-Dockerfile.patch`
- Статус Compose: активный закреплённый amd64-образ `akhilmulpuri/aperture-web`

Активная сборка использует immutable-образ из `stack/versions.env`. Checkout и patch сохранены как исходный контракт для будущего собственного образа; команда `make up` их не использует.

Восстановление исходного кода:

```sh
git clone https://github.com/akhilmulpurii/aperture.git stack/aperture
git -C stack/aperture checkout 21394ca
git -C stack/aperture apply --unidiff-zero ../../patches/aperture-Dockerfile.patch
```

Patch меняет exposed port и health check Dockerfile с 3000 на 3232. Перед включением собственного образа убедитесь, что приложение действительно слушает 3232: инструкция `EXPOSE` сама по себе порт процесса не меняет.
