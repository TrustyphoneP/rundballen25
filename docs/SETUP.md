# rundballen25 – Setup-Anleitung

## Voraussetzungen

| Tool | Download |
|------|---------|
| Docker Desktop for Windows | https://www.docker.com/products/docker-desktop/ |
| Git for Windows | https://git-scm.com/download/win |
| VS Code (empfohlen) | https://code.visualstudio.com/ |

Docker Desktop muss laufen (Taskleiste: Docker-Symbol sichtbar) bevor irgendwelche
`docker`-Befehle funktionieren.

---

## Erstmaliges Setup (Windows – PowerShell oder Git Bash)

```powershell
# 1. Projektordner öffnen (den umbenannten Ordner)
cd rundballen25

# 2. Umgebungsvariablen anlegen
copy .env.example .env
# .env in Editor öffnen, SECRET_KEY setzen (beliebiger langer String)

# 3. Docker-Images bauen (einmalig, dauert 2–3 Min)
docker compose build

# 4. Datenbank + Redis starten, Migrationen ausführen
docker compose up -d db redis
docker compose run --rm web python manage.py migrate

# 5. Admin-Benutzer anlegen
docker compose run --rm web python manage.py createsuperuser

# 6. Alle Services starten
docker compose up
```

Browser öffnen: **http://localhost:8000**
Admin-Interface: **http://localhost:8000/admin**

---

## Tägliche Entwicklung (Windows)

```powershell
# Server starten
docker compose up

# Server im Hintergrund starten
docker compose up -d

# Neue Migration erstellen (nach Modeländerung)
docker compose exec web python manage.py makemigrations

# Migration anwenden
docker compose exec web python manage.py migrate

# Django Shell
docker compose exec web python manage.py shell_plus

# Logs anzeigen
docker compose logs -f web

# Stoppen
docker compose down
```

**Tipp:** In VS Code die Extension „Docker" installieren – dann per Klick
Container starten/stoppen und Logs einsehen.

---

## Windows-spezifische Hinweise

### Line Endings
Das Projekt enthält `.gitattributes` mit `eol=lf` für alle Python/HTML-Dateien.
Git for Windows setzt CRLF automatisch zurück. Keine manuelle Konfiguration nötig.

### Ports belegt?
Falls Port 8000, 5432 oder 6379 schon lokal belegt sind:
In `docker-compose.yml` den Host-Port ändern, z.B.:
```yaml
ports:
  - "8001:8000"   # → dann http://localhost:8001
```

### Docker Desktop: WSL 2 Backend
Docker Desktop sollte im WSL 2-Modus laufen (Standard seit Desktop 4.x).
Einstellung: Docker Desktop → Settings → General → „Use WSL 2 based engine"

### Volume-Performance
Code liegt unter `volumes: - .:/app` – auf Windows mit WSL2-Backend ist die
Performance gut. Läuft es langsam: Projektordner in das WSL2-Dateisystem
verschieben (`\\wsl$\Ubuntu\home\user\rundballen25`).

---

## Erster Start nach dem Klonen

1. Docker Desktop starten und warten bis das Symbol grün ist
2. PowerShell / Git Bash im Projektordner öffnen
3. `docker compose up` – beim ersten Start werden Images gebaut (~3 Min)
4. `http://localhost:8000/admin` → mit Superuser anmelden
5. Freizeit anlegen: Admin → Freizeiten → Hinzufügen
6. Dann: `http://localhost:8000` → Dashboard erscheint mit Freizeitdaten

---

## Produktions-Deployment (Self-Hosted, HTTPS)

```bash
# Auf Linux-Server:
git clone ... && cd rundballen25
cp .env.example .env
# .env: DEBUG=False, ALLOWED_HOSTS=deine-domain.de, sichere Passwörter setzen

# In docker/nginx.prod.conf: "example.com" durch eigene Domain ersetzen

# Certbot einmalig initialisieren:
docker compose -f docker-compose.prod.yml run --rm certbot \
  certonly --webroot -w /var/www/certbot -d deine-domain.de \
  --email admin@example.com --agree-tos --no-eff-email

# Produktionsserver starten:
docker compose -f docker-compose.prod.yml up -d
```
