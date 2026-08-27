# Эксплуатация Phanes

[English](../OPERATIONS.md) · [Русский](OPERATIONS.md)

## Доверенный доступ

Управляющие HTTP-порты публикуются только через два Caddy gateway:

- локальная сеть: `<LAN_IP>`;
- Tailscale: `<TAILSCALE_IP>`.

Контейнеры приложений напрямую не публикуются. FlareSolverr и Docker API proxy доступны только внутри Docker. Peer-трафик qBittorrent и discovery Jellyfin остаются только в LAN.

TorrServer — намеренное исключение: клиенты Chromecast/NUM получают прямой LAN socket `${LAN_IP}:18090`. Доступ через Tailscale к тому же порту остаётся за Tailscale Caddy gateway.

Примеры:

```text
Jellyfin     http://<LAN_IP>:8096     http://<TAILSCALE_IP>:8096
Homarr       http://<LAN_IP>:7575     http://<TAILSCALE_IP>:7575
Uptime Kuma  http://<LAN_IP>:3001     http://<TAILSCALE_IP>:3001
```

Tailscale Serve на HTTPS-порту 443 уже используется панелью Hermes и намеренно не изменяется этим стеком.

## Container runtime: OrbStack

Production Compose stack работает в Docker context `orbstack`. OrbStack запускается при входе в систему и владеет всеми активными контейнерами Phanes; Docker Desktop остановлен и сохранён только для rollback, его старые контейнеры остановлены.

Runtime можно выбирать явно:

```sh
DOCKER_CONTEXT_NAME=orbstack RUN_DEEP_CHECKS=1 RUN_EXTERNAL_CHECKS=1 make verify
DOCKER_CONTEXT=orbstack make backup
```

Миграция повторно использует host bind mounts, поэтому базы приложений и медиаданные не копируются в Docker-managed volume. Pinned images загружены в OrbStack отдельно. FlareSolverr получил увеличенный shared memory, а Prowlarr ожидает его health, что предотвращает ошибки proxy при холодном старте.

Rollback:

1. Остановить stack в OrbStack.
2. Запустить Docker Desktop.
3. Запустить существующие остановленные Compose-контейнеры через context `desktop-linux`.
4. Никогда не запускать оба stack одновременно с общим `APPDATA_ROOT`.

## Firewall macOS

В репозитории есть узкий PF anchor только для портов медиастека. Он разрешает `${LAN_CIDR}` доступ к `${LAN_IP}`, а Tailscale CGNAT `100.64.0.0/10` — к `${TAILSCALE_IP}`, после чего блокирует другие источники только для этих портов. Глобальный default deny не включается; Screen Sharing, AirPlay, Hermes, OrbStack, виртуальные машины и другие listeners не затрагиваются. Peer-порт qBittorrent `6881` намеренно исключён.

Установка из интерактивного Terminal macOS с авторизацией администратора:

```sh
./scripts/install_macos_firewall.sh
```

Installer проверяет полную PF-конфигурацию до загрузки, сохраняет `/etc/pf.conf.before-jellyfin-media-server`, включает встроенный Application Firewall и stealth mode, сохраняя автоматический доступ для подписанных Apple/downloaded приложений.

Удаление только PF anchor этого проекта:

```sh
./scripts/uninstall_macos_firewall.sh
```

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

Host-watchdog дополняет Uptime Kuma: проверяет состояние Docker/Compose и
основные endpoints через LAN и Tailscale. Успешная проверка ничего не выводит.
При нестабильности watchdog выполняет ограниченное восстановление без обновления
образов: перезапускает неисправные сервисы, приводит существующий digest-pinned
Compose deployment к декларативному состоянию и снова выполняет проверки.
Полный отчёт об инциденте выводится в stdout для scheduler или notification
gateway:

```sh
make watchdog
```

Запускайте его каждые пять минут. Параллельные запуски блокируются, повторные
уведомления об одном нерешённом инциденте ограничены одним в час. Watchdog не
выполняет image pull, удаление данных или миграцию конфигурации. Для проверки
детектора без исправлений задайте `WATCHDOG_DRY_RUN=1`.

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
