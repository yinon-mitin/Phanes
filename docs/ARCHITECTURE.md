# Архитектура

## Поток данных

```text
Indexer -> Prowlarr/Jackett -> Sonarr/Radarr -> qBittorrent
                                           -> MEDIA_ROOT
User -> Jellyseerr -> Sonarr/Radarr         -> Jellyfin -> Client
User -> Aperture ---------------------------> Jellyfin API
Bazarr ------------------------------------> subtitles
Recyclarr -> quality profiles in Sonarr/Radarr
Homarr/Notifiarr -> dashboard and notifications
```

## Границы состояния

| Слой | Desired state | Runtime state | Восстановление |
| --- | --- | --- | --- |
| Контейнеры и сеть | `stack/docker-compose.yml` | Docker | пересоздаётся |
| Версии образов | `stack/versions.env` | registry cache | пересоздаётся по digest |
| Локальные пути/секреты | `stack/.env` | вне Git | вручную или из secret manager |
| Настройки приложений | `APPDATA_ROOT` | SQLite/XML/JSON | только из зашифрованного backup |
| Медиатека | `MEDIA_ROOT` | файлы пользователя | отдельная стратегия backup |

## Уровни зрелости

- Реализовано: Compose-топология, immutable image lock, шаблон окружения, локальная и CI-валидация.
- Локально проверяется: структура Compose, отсутствие floating tags и секретов.
- Live-проверка: `make verify` на запущенном Docker host.
- Не автоматизировано: первичная настройка UI, создание API-ключей и связей между приложениями.

Последний пункт принципиален: без backup `APPDATA_ROOT` репозиторий воспроизводит платформу, но не пользовательские аккаунты, историю и внутренние настройки приложений.
