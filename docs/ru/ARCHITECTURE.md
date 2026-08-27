# Архитектура

[English](../ARCHITECTURE.md) · [Русский](ARCHITECTURE.md)

## Поток данных

```text
LAN 10.0.0.88 --------> Caddy gateway-lan -------> HTTP-порты приложений
Tailscale 100.77.77.77 -> Caddy gateway-tailscale -> HTTP-порты приложений
Индексатор -> Prowlarr/Jackett -> Sonarr/Radarr -> qBittorrent
                                               -> MEDIA_ROOT
Пользователь -> Jellyseerr -> Sonarr/Radarr     -> Jellyfin -> Клиент
Пользователь -> Aperture ----------------------> Jellyfin API
Bazarr ----------------------------------------> Субтитры
Recyclarr -> Профили качества Sonarr/Radarr
Homarr/Notifiarr -> Панель управления и уведомления
Homarr -> ограниченный docker-socket-proxy -> read-only Docker API
Uptime Kuma -> внутренние HTTP health-пробы
```

## Границы состояния

| Слой | Желаемая конфигурация | Рабочее состояние | Восстановление |
| --- | --- | --- | --- |
| Контейнеры и сеть | `stack/docker-compose.yml` | Docker | Пересоздаётся |
| Версии образов | `stack/versions.env` | Кэш registry | Загружается по digest |
| Локальные пути и секреты | `stack/.env` | Вне Git | Вручную или из secret manager |
| Настройки приложений | `APPDATA_ROOT` | SQLite/XML/JSON | Из зашифрованного backup |
| Медиатека | `MEDIA_ROOT` | Пользовательские файлы | Отдельная политика backup |
| Мониторинг | Uptime Kuma и setup-скрипт | `APPDATA_ROOT/uptime-kuma` | Зашифрованный Restic backup |
| Зашифрованный backup | Backup/restore-скрипты | Restic-репозиторий вне Git | Проверенное временное восстановление |

## Уровни проверки

- Реализовано: топология Compose, lock-файл образов, шаблон окружения, локальные проверки и CI.
- Проверяется локально: структура Compose, закреплённые образы, безопасность репозитория и ссылки документации.
- Проверяется на работающем хосте: `make verify`.
- Настраивается вручную: первый запуск UI, обмен API-ключами и связывание приложений.

Без backup `APPDATA_ROOT` репозиторий восстанавливает платформу, но не пользователей, историю, очереди и настройки приложений.
