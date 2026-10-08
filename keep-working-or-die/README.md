> Aktueller Stand 16.09.2026: AP0 lokal abgenommen, 133 Tests und 118 Subtests bestanden, 3 skips. Zwei echte Entwicklungsläufe sind erfolgt; keine Produktionsgeburt. Verbindlicher Status: [AP0-Bericht](reports/ap0-status-2026-09-16.md) und [Arbeitsplan](ARBEITSPLAN.md). Nachfolgende ältere Aussagen zu noch fehlenden Modellläufen sind historisch.

# KEEP WORKING OR DIE

Entwicklungskern v0.1.dev1 · 15.09.2026

Der lokale Python-Kern ist implementiert: persistenter Agentenablauf, Responses-Adapter, Datei-Tools, Container-Executor, Sleep/Wake, privates Journal, Kostenbeobachtung, öffentliche FastAPI-Leseendpunkte und Backup/Restore. Entwicklung und Produktionsgeburt bleiben getrennt.

**Installation, Start und Grenzen:** [04_ENTWICKLUNGSKERN.md](04_ENTWICKLUNGSKERN.md). Die bereits installierte virtuelle Umgebung liegt unter `../.venv`. Aus diesem Ordner:

**Ubuntu-Deployment und Beobachtung vom Hauptcomputer:** [05_DEPLOYMENT_UND_ZUGRIFF.md](05_DEPLOYMENT_UND_ZUGRIFF.md). Der Betreiber hat Installation auf `s340`, reparierten Healthcheck und Browseranzeige über den Windows-SSH-Tunnel bestätigt. Der öffentliche Lesedienst besitzt eine monochrome Browseransicht unter `/`. Der Modell-Worker wurde dabei nicht gestartet.

```powershell
..\.venv\Scripts\kwod.exe --data ..\kwod-offline init
..\.venv\Scripts\kwod.exe --data ..\kwod-offline run --fixture fixtures\development.json --steps 3
..\.venv\Scripts\kwod.exe serve --public-db ..\kwod-offline\public\public.sqlite
```

Die folgenden Dokumente bilden die ursprüngliche Planung und Übergabe ab:

1. `01_PROJEKTPLAN.md`: Scope, Architektur, Datenmodell, Meilensteine, Risiken, Abnahme und Budget.
2. `02_WORK_HANDOFF.md`: direkt ausführbarer Implementierungsauftrag mit Tickets und Toolverträgen.
3. `schema/private.sql`, `schema/public.sql`: SQLite-Startentwurf.
4. `config.example.json`: nicht aktive Entwicklungskonfiguration.
5. `reference/dashboard.png`: Referenz aus dem ursprünglichen Gespräch.
6. `VALIDIERUNG.md`: Prüfung dieses Vorbereitungspakets.
7. `03_DASHBOARD_DETAILS.md`: Übernahme weiterer Referenzdetails, insbesondere Replay, Kosten pro Call und Arbeitsblöcke.

Es wurden keine echten Modellcalls ausgeführt, kein Geld transferiert und kein Birth-Event erzeugt. Die erste Beobachtungsansicht ist lokal implementiert; finanzielle Live-Daten und Replay fehlen noch. Linux-Isolation, echter Providerzugang und der 24-Stunden-Test bleiben vor Geburt nachzuweisen. Den aktuellen Prüfstand dokumentiert `VALIDIERUNG.md`.

