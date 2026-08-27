# Воспроизводимость

Релиз считается воспроизводимым, когда одинаковый Git revision и одинаковые локальные входы создают одну и ту же Compose-топологию и используют те же OCI image indexes.

## Зафиксированные входы

- все 17 активных образов закреплены digest в `stack/versions.env`; 16 основных образов имеют amd64/arm64 manifests, а Aperture явно ограничен `linux/amd64`;
- Compose не содержит `latest` и не выбирает версию самостоятельно;
- локальные пути и секреты имеют явный контракт в `stack/.env.example`;
- активный Aperture image закреплён digest; локальный checkout дополнительно закреплён Git revision и patch для самостоятельной сборки;
- media catalogue и runtime databases не являются входом Git-сборки.

## Проверка

```sh
make test ENV_FILE=stack/.env.example
```

Проверка отклоняет floating image tags, отсутствующие image variables, незакреплённые digest, запрещённые runtime-файлы и некорректный Compose.

## Обновление

Обновления не происходят автоматически. Для осознанного обновления:

```sh
make update-lock
make test ENV_FILE=stack/.env.example
git diff -- stack/versions.env
```

После просмотра changelog каждого сервиса изменения следует проверить на временном `APPDATA_ROOT`, затем на копии production state. Новый digest меняет фактический артефакт даже при том же source tag.

## Ограничения

Digest гарантирует неизменность образа, но не гарантирует идентичность CPU, kernel, Docker Engine, filesystem semantics или внешних API. Для production-релиза фиксируйте также версию Docker/Compose и проверяйте обе целевые архитектуры (`linux/amd64`, `linux/arm64`).

Jellyfin Intro Skipper Docker Mod исключён из базовой сборки: его registry endpoint не разрешил анонимно получить digest. Возвращать мод в baseline без immutable digest нельзя.
