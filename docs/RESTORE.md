# Восстановление

## 1. Подготовка хоста

Установите Git, Docker Engine/Desktop с Compose v2, `make` и Python 3. Проверьте доступность всех registry из `stack/versions.env`.

## 2. Локальная конфигурация

```sh
make init
# Отредактируйте stack/.env: абсолютные пути, UID/GID, timezone и новый Homarr key.
make test
```

Не переносите старые ключи из Git history. `stack/.env` не должен попадать в repository.

## 3. Чистый запуск

```sh
make pull
make up
make ps
```

Откройте Jellyfin на `http://localhost:8096`, затем настройте сервисы в порядке:

1. qBittorrent;
2. Prowlarr и/или Jackett;
3. Sonarr и Radarr;
4. Bazarr и Recyclarr;
5. Jellyfin;
6. Jellyseerr;
7. Homarr, Notifiarr и остальные дополнения.

Используйте одинаковый container path `/media` во всех приложениях. Это снижает риск несовпадения путей при import и hardlink.

## 4. Восстановление состояния

Для полного восстановления остановите stack и восстановите зашифрованный snapshot `APPDATA_ROOT` в тот же абсолютный путь либо обновите `APPDATA_ROOT` в `.env`. Проверяйте ownership по `PUID`/`PGID` до запуска.

```sh
make up
make verify
```

SQLite-файлы нельзя надёжно копировать во время активной записи. Используйте built-in backup приложений или согласованный snapshot после остановки контейнеров.

## 5. Rollback

Верните предыдущий Git revision, восстановите совместимый snapshot `APPDATA_ROOT` и снова выполните `make up`. Downgrade контейнера поверх базы, уже мигрированной новой версией, не считается безопасным rollback.
