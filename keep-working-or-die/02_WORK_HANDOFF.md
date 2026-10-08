# Technische Übergabe an Work

Status: Umsetzung vorbereitet, noch nicht implementiert oder geboren.

## Auftrag

Implementiere KEEP WORKING OR DIE v0.1 gemäß `01_PROJEKTPLAN.md`. Beginne mit P1–P3, ohne Produktionsgeburt und ohne Ausgaben aus dem 50-€-Erbe. Die vorhandenen SQL-Dateien sind ein geprüfter Ausgangsentwurf; Migrationen und Anwendungstests müssen ergänzt werden. Python + FastAPI + SQLite, offizielles OpenAI-SDK, keine Agent-Frameworks. Ein GPT-Astra-Agent, direkter Provideraufruf, kein Billing-Proxy und keine künstliche Todeslogik. Alle realen Modellcalls während der Entwicklung brauchen getrennte Entwicklungsabrechnung.

Arbeite zuerst offline mit klar gekennzeichneten Test-Fixtures. Diese prüfen Technik, sie bilden keine simulierte Produktionsökonomie. Implementiere keine Fake-Balance im Lebensmodus. Fehlende reale Finanzdaten bleiben unbekannt. Keine API-Keys in Chat oder Repository ablegen.

## Empfohlener Aufbau

```text
src/kwod/
  config.py             # explizite dev/life-Konfiguration
  db.py                 # Migrationen, Transaktionen, WAL
  archive.py            # private Payloads, Hashes, Manifest
  runtime.py            # genau eine persistente Schleife
  context.py            # sichtbarer Kontext und Turn-Grenzen
  provider.py           # direktes OpenAI-SDK, protokollierte Versuche
  tools.py              # typisierte Toolverträge, serieller Dispatch
  executor.py           # separater netzloser Container
  accounting.py         # Beobachtung, Bewertung und Abgleich
  projection.py         # Whitelist in separate öffentliche DB
  api.py                # ausschließlich öffentliche Leseendpunkte
  cli.py                # init, run, inspect, import, backup; birth zuletzt
web/                    # HTML/CSS/JS, kein Framework notwendig
deploy/                 # systemd-Units und Executor-Image nach Isolationstest
tests/                  # Recovery, Kosten, Leakage, Linux-Integration
```

Persistente Betriebsdaten außerhalb des Checkouts: `/var/lib/kwod/private`, `/var/lib/kwod/workspace`, `/var/lib/kwod/public`. Besitzer und Zugriffsrechte entsprechend dem Plan. Public-API-User erhält ausschließlich Leserecht am öffentlichen Bestand. Runtime darf keine unbeschränkte Container-Verwaltung an den Agenten weiterreichen.

## Tickets in Implementierungsreihenfolge

1. **Bootstrap / Datenbank:** Paket, CLI `init`, Migrationen und leere Instanz im Modus dev. Keine automatische Birth-Anlage. SQL-Entwurf mit Typvalidierung ergänzen. Abnahme: Migration auf leerer DB, Wiederholung ohne Datenverlust.
2. **Journal / Archiv:** Event-Sequenz, atomare Payload-Ablage, Hashprüfung, Kontextmanifest, Append-only-Service. Abnahme: Absturz zwischen Payload und DB-Commit erzeugt höchstens erkennbaren Orphan, keinen falschen Erfolg.
3. **Provider:** Responses-Aufruf, Usage, Preisversion, Rohresponse, Fehlerklassifikation, `max_retries=0`. `store=false` soweit mit gewähltem Kontextverfahren kompatibel; erforderliche Response-Items lokal erhalten. Abnahme: abgeschlossene, incomplete, refusal und mehrdeutige Antworten über Fixtures.
4. **Tools / Isolation:** `read_file`, `write_file`, `list_files`, `terminal`, `clock`, `sleep`, `observe_assets`, `record_decision`, `set_activity`. Filesystem-Tools auf Workspace begrenzen; Shell über denselben isolierten Speicher. Keine Zahlungs- oder Browsertools. Abnahme: Symlink-Ausbruch, Hostzugriff, Netz und Keyzugriff scheitern.
5. **Loop / Recovery:** einmaliger Worker, Request/Tool-Zustände und UTC-Wake, SIGTERM/Neustart, keine Nebenwirkungswiederholung. Abnahme: konkrete Crash-Matrix unten.
6. **Ökonomie:** belegbasierter Import, Deduplikation, Cash/Credits/Fees, Usage-Schätzung und Reconciliation. Keine Geldprüfung vor Inferenz. Abnahme: Transfer plus Verbrauch verändert Vermögen nur um Aufwand, nicht doppelt.
7. **Öffentliche API:** Whitelist-Projektion in eigene DB, Cursor, Pagination und Datenaktualität. Vor Geburt leere finanzielle Anzeige. Abnahme: Geheimnis-Marker aus privaten Fixtures sind in keiner Antwort enthalten.
8. **Betrieb:** systemd, Backup über SQLite-Backup-API, Archivmanifest, Restore, 24-Stunden-Test. Docker nur für Executor erforderlich. Linux-Zieltests vor Produktivstart.
9. **Birth-Werkzeug:** prüft echte Belege, finanzierten Compute, Runtime-Version und Konfiguration; schreibt Erbe/Birth atomar und genau einmal. Nur nach separatem tatsächlichem Go-live mit realen Kontodaten ausführen.
10. **Website:** visuelle Vorgabe aus Plan, `03_DASHBOARD_DETAILS.md` und Referenz umsetzen, leere/stale/sleeping/blocked Zustände sichtbar. Keine erzeugten Demodaten im Produktionsmodus. Öffentliche Daten für späteres Replay versionieren; Replay selbst folgt nach dem ersten Live-Dashboard.

## Toolverträge

Alle Tools erhalten eine persistente `call_id`; alle Ergebnisse enthalten `ok`, `artifact_ref` oder ein Ergebnisobjekt und einen klassifizierten Fehler. Argumente strikt validieren, unbekannte Felder ablehnen. Toolbeschreibung und effektive Limits gehören ins Kontextmanifest.

| Tool | Argumente | Semantik |
|---|---|---|
| read_file | path, offset, max_bytes | relative Workspace-Pfade; begrenzte Modellansicht |
| write_file | path, content | atomare Ersetzung; Vor-/Nachhash archivieren |
| list_files | path | begrenztes Verzeichnisresultat |
| terminal | command, timeout_seconds | Prozessgruppe im Executor; Arbeitsverzeichnis Workspace; vollständiges stdout/stderr privat |
| clock | keine | tatsächliche UTC-Zeit |
| sleep | wake_at | UTC in Zukunft; dauerhaft committen; kein bezahlter Heartbeat |
| observe_assets | keine | letzte Beobachtungen mit as_of/quality; unbekannt bleibt unbekannt |
| record_decision | action, brief_reason, optional expectations | Selbstbericht, keine Denkspur; mit Outcome verknüpfbar |
| set_activity | category | freigegebener Enum für öffentlichen Status |

Initiale technische Limits nach Linux-Test festlegen, als Konfiguration dokumentieren: z. B. 120 Sekunden Terminalzeit, 64 KiB Modellansicht pro Toolausgabe, 4.096 Output-Tokens, 24.000 Zielkontext-Tokens. Dies sind Startwerte für Zuverlässigkeit und Kontextgröße, keine Wallet-Sperren. Modellbedingte Unvollständigkeit sichtbar behandeln. `parallel_tool_calls=false` soweit unterstützt; unerwartete mehrere Calls deterministisch seriell verarbeiten.

## Crash-Matrix

| Abbruchpunkt | Erwartete Fortsetzung |
|---|---|
| vor API-Senden | ungesendeten Versuch eindeutig erkennen |
| nach Senden, vor Response-Persistierung | outcome_unknown; Kosten ungeklärt; nicht als kostenlos verbuchen |
| nach Response, vor Tool | persistierten Auftrag genau einmal starten |
| während Shell | recovery_required; nicht blind wiederholen |
| nach Resultat, vor nächstem Modellcall | gespeichertes Resultat verwenden |
| nach Sleep-Commit | bis wake_at warten, nach Reboot korrekt fortsetzen |
| während öffentlicher Projektion | per private_event_id deduplizieren und nachholen |

## Offene P0-Eingaben

Linux-Gerät und Distribution; dedizierter Entwicklungs-Key; später getrennte Produktionsabrechnung und Belege. Diese Eingaben blockieren Offline-Implementierung nicht. Linux-Dienste, Geldtransfer, Kontoeröffnung, Produktionscalls und Website-Veröffentlichung sind durch dieses Vorbereitungspaket nicht ausgeführt.

Liefere am Ende lauffähigen Code, festgeschriebene getestete Abhängigkeiten, Testbericht, Linux-Installationsanleitung und eine konkrete Birth-Checkliste mit tatsächlich noch fehlenden Nachweisen. Keine zusätzliche neue Work-Aufgabe voraussetzen: Dieses Paket ist der in sich geschlossene Implementierungsauftrag.
