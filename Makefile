SHELL := /bin/sh

ENV_FILE ?= stack/.env
VERSIONS_FILE ?= stack/versions.env
COMPOSE_FILE ?= stack/docker-compose.yml
COMPOSE = docker compose --env-file $(ENV_FILE) --env-file $(VERSIONS_FILE) -f $(COMPOSE_FILE)

.PHONY: init validate config safety test pull up down restart ps logs verify update-lock notifiarr-up notifiarr-down

init:
	@test -f stack/.env || cp stack/.env.example stack/.env
	@printf '%s\n' 'Edit stack/.env, then run: make test && make up'

validate:
	@$(COMPOSE) config --quiet
	@python3 scripts/validate_distribution.py --env-file $(ENV_FILE)

config:
	@$(COMPOSE) config

safety:
	@python3 scripts/check_repository_safety.py

test: safety validate
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

notifiarr-up:
	@COMPOSE_PROFILES=notifiarr $(COMPOSE) up -d notifiarr

notifiarr-down:
	@$(COMPOSE) --profile notifiarr stop notifiarr
	@$(COMPOSE) --profile notifiarr rm -f notifiarr

update-lock:
	@python3 scripts/update_image_lock.py
