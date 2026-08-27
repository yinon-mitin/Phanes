# Эксплуатация

[English](../OPERATIONS.md) · [Русский](OPERATIONS.md)

## Доверенный доступ

Управляющие HTTP-порты публикуются только через два Caddy gateway:

- локальная сеть: `10.0.0.88`;
- Tailscale: `100.77.77.77`.

Контейнеры приложений напрямую не публикуются. FlareSolverr и Docker API proxy доступны только внутри Docker. Peer-трафик qBittorrent и discovery Jellyfin остаются только в LAN.

Примеры:

```text
Jellyfin     http://10.0.0.88:8096     http://100.77.77.77:8096
Homarr       http://10.0.0.88:7575     http://100.77.77.77:7575
Uptime Kuma  http://10.0.0.88:3001     http://100.77.77.77:3001
```

Tailscale Serve на HTTPS-порту 443 уже используется панелью Hermes и намеренно не изменяется этим стеком.

## Граница Docker API

Homarr больше не монтирует `/var/run/docker.sock`. Он использует внутренний `docker-socket-proxy` с разрешёнными read-only endpoint и `POST=0`. Proxy находится во внутренней Docker-сети и не имеет host-порта.

## Мониторинг

Uptime Kuma использует SQLite и настраивается идемпотентно:

```sh
make configure-monitoring
```

Учётные данные находятся вне Git:

```text
~/.config/jellyfin-media-server/uptime-kuma.env
```

Задача создаёт HTTP-мониторы для всех долгоживущих веб-сервисов. Для push-уведомлений нужно добавить notification provider через UI Uptime Kuma.

## Зашифрованный backup

На хосте используется Restic-репозиторий на внешнем медиадиске. Конфигурация и пароль не попадают в Git:

```text
~/.config/jellyfin-media-server/restic.env
~/.config/jellyfin-media-server/restic-password
```

Создание application-consistent backup:

```sh
make backup
```

Команда останавливает стек, сохраняет `APPDATA_ROOT` и `stack/.env`, гарантированно возобновляет стек даже при ошибке, проверяет репозиторий и применяет retention: 7 дневных, 4 недельных и 12 месячных snapshots.

Проверка реального восстановления:

```sh
make verify-backup
```

Проверка восстанавливает последний snapshot во временный каталог, выполняет `PRAGMA integrity_check` для каждой настоящей SQLite-базы, запускает `restic check` и удаляет временный plaintext.

## Проверка

```sh
make test
RUN_DEEP_CHECKS=1 RUN_EXTERNAL_CHECKS=1 make verify
```

Live-gate проверяет пути через LAN и Tailscale, Docker health, restart count, состояние Arr-приложений, внутренний FlareSolverr, ограниченный Docker API для Homarr, Recyclarr, qbit_manage и внешний HTTPS Prowlarr.

## Восстановление

Git-тег до изменений:

```text
pre-secure-operations-20260828
```

Runtime также восстанавливается из зашифрованного Restic snapshot. При неудачном rollout верните предыдущую версию Compose и выполните `make up`; не удаляйте `APPDATA_ROOT`.
