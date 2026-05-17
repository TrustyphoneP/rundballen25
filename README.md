# rundballen25

**Camp- und Gruppenevents-Planungssystem** für Freizeiten mit ~100 Teilnehmern und ~30 Betreuern.

## Features

- 🏕 **Freizeiten-Verwaltung** – Lager, Tage, Teilnehmer
- ⚠️ **Unverträglichkeiten** – alle 14 EU-Pflichtallergene + Erweiterungen, pro Person erfasst
- 🍽 **Mahlzeitenplanung** – Frühstück/Mittag/Abend/Snack mit Rezept-Zuordnung
- 📋 **Rezeptverwaltung** – Mengenberechnung skaliert automatisch auf Personenzahl
- 🧺 **Einkaufslistengenerator** – aggregiert alle Zutaten, CSV-Export
- 🍞 **Brotberechnung** – automatisch nach Personenzahl
- 💬 **Anonymes Feedback** – Teilnehmer per QR-Code, Betreuer sehen Auswertung
- 🗳 **Betreuer-Abstimmung** – einmalig pro Jahr für Gerichteauswahl (anonym per Token)
- 📱 **Mobile** – PWA, funktioniert wie eine App
- 🔒 **Self-hosted** – Docker + HTTPS, keine Cloud-Abhängigkeit

## Stack

| Schicht | Technologie |
|---------|------------|
| Backend | Django 5.x |
| Frontend | HTMX + Alpine.js + Tailwind CSS |
| Datenbank | PostgreSQL 16 |
| Cache / WS | Redis 7 + Django Channels |
| Deploy | Docker Compose + Nginx + Let's Encrypt |

## Schnellstart

```bash
cp .env.example .env   # Werte anpassen
docker compose build
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose up
# → http://localhost:8000
```

Vollständige Anleitung: [docs/SETUP.md](docs/SETUP.md)

## Primärfarbe

RAL 210 30 25 · Tiefatlantikblau · `#1e4c59`
