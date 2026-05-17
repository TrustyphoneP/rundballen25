# =============================================================================
# rundballen25 – Makefile
# Funktioniert auf Windows (mit Git Bash / WSL) und Ubuntu
# =============================================================================

.PHONY: help up down build shell migrate makemigrations createsuperuser \
        test lint format seed reset-db logs

help:
	@echo ""
	@echo "  rundballen25 – Dev-Befehle"
	@echo "  ────────────────────────────────────────"
	@echo "  make up              Container starten"
	@echo "  make down            Container stoppen"
	@echo "  make build           Docker-Image neu bauen"
	@echo "  make shell           Django Shell öffnen"
	@echo "  make migrate         Migrationen anwenden"
	@echo "  make makemigrations  Neue Migrationen erstellen"
	@echo "  make createsuperuser Admin-User anlegen"
	@echo "  make seed            Testdaten laden"
	@echo "  make test            Tests ausführen"
	@echo "  make lint            Ruff linter ausführen"
	@echo "  make format          Black formatter ausführen"
	@echo "  make logs            Logs anzeigen"
	@echo "  make reset-db        Datenbank zurücksetzen (⚠ löscht alles)"
	@echo ""

up:
	docker compose up

up-d:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

shell:
	docker compose exec web python manage.py shell_plus

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

createsuperuser:
	docker compose exec web python manage.py createsuperuser

seed:
	docker compose exec web python manage.py loaddata fixtures/initial_data.json

test:
	docker compose exec web pytest --cov=apps --cov-report=term-missing

lint:
	docker compose exec web ruff check .

format:
	docker compose exec web black .

logs:
	docker compose logs -f web

reset-db:
	@echo "⚠️  Datenbank wird GELÖSCHT und neu erstellt!"
	docker compose down -v
	docker compose up -d db
	sleep 3
	docker compose exec web python manage.py migrate
	@echo "✅ Datenbank zurückgesetzt."
