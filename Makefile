SHELL := /bin/sh

ENV_FILE ?= stack/.env
VERSIONS_FILE ?= stack/versions.env
COMPOSE_FILE ?= stack/docker-compose.yml
BACKUP_ENV_FILE ?= $(HOME)/.config/jellyfin-media-server/restic.env
UPTIME_KUMA_ENV_FILE ?= $(HOME)/.config/jellyfin-media-server/uptime-kuma.env
COMPOSE = docker compose --env-file $(ENV_FILE) --env-file $(VERSIONS_FILE) -f $(COMPOSE_FILE)

.PHONY: init validate validate-docs validate-security validate-caddy validate-media-policy verify-media-policy-live config safety test pull up down restart ps logs verify watchdog arr-queue-audit arr-queue-reconcile configure-monitoring backup verify-backup update-lock notifiarr-up notifiarr-down

init:
	@test -f stack/.env || cp stack/.env.example stack/.env
	@printf '%s\n' 'Edit stack/.env, then run: make test && make up'

validate:
	@$(COMPOSE) config --quiet
	@python3 scripts/validate_distribution.py --env-file $(ENV_FILE)

validate-docs:
	@python3 scripts/validate_docs.py

validate-security:
	@python3 -m unittest discover -s tests -v

validate-caddy:
	@docker run --rm -v "$(CURDIR)/stack/Caddyfile:/etc/caddy/Caddyfile:ro" $$(grep '^CADDY_IMAGE=' $(VERSIONS_FILE) | cut -d= -f2-) caddy validate --config /etc/caddy/Caddyfile

validate-media-policy:
	@python3 scripts/validate_media_policy.py

verify-media-policy-live:
	@python3 scripts/verify_media_policy_live.py

config:
	@$(COMPOSE) config

safety:
	@python3 scripts/check_repository_safety.py

test: safety validate validate-docs validate-security validate-caddy validate-media-policy
	@git diff --check

pull:
	@$(COMPOSE) pull

up:
	@$(COMPOSE) up -d --remove-orphans

down:
	@$(COMPOSE) down

restart:
	@$(COMPOSE) restart

ps:
	@$(COMPOSE) ps

logs:
	@$(COMPOSE) logs --follow --tail=200

verify:
	@ENV_FILE=$(ENV_FILE) VERSIONS_FILE=$(VERSIONS_FILE) stack/verify-stack.sh

watchdog:
	@ENV_FILE=$(ENV_FILE) VERSIONS_FILE=$(VERSIONS_FILE) python3 scripts/watchdog_stack.py

arr-queue-audit:
	@python3 scripts/reconcile_arr_queue.py

arr-queue-reconcile:
	@python3 scripts/reconcile_arr_queue.py --apply --quarantine-sonarr-warnings

configure-monitoring:
	@set -a; . $(UPTIME_KUMA_ENV_FILE); set +a; uv run --with uptime-kuma-api==1.2.1 python3 scripts/configure_uptime_kuma.py

backup:
	@set -a; . $(BACKUP_ENV_FILE); set +a; ENV_FILE=$(ENV_FILE) VERSIONS_FILE=$(VERSIONS_FILE) scripts/backup_stack.sh

verify-backup:
	@set -a; . $(BACKUP_ENV_FILE); set +a; ENV_FILE=$(ENV_FILE) scripts/verify_backup.sh

notifiarr-up:
	@COMPOSE_PROFILES=notifiarr $(COMPOSE) up -d notifiarr

notifiarr-down:
	@$(COMPOSE) --profile notifiarr stop notifiarr
	@$(COMPOSE) --profile notifiarr rm -f notifiarr

update-lock:
	@python3 scripts/update_image_lock.py
