# AP1 — Arbeitsläufe beobachten und steuern

Stand 16.09.2026. Lokal implementiert und geprüft; Ubuntu-Abnahme steht aus.

## Anzeige und Datenfluss

Der Monitor zeigt Trial01, Pilot02 und einen gesonderten **Offline-Prüflauf**.
Je Lauf: Phase, beobachteter Dienstzustand, verwendete/verbleibende Aufrufe,
Kontextübergaben, Startmarker und feste Verweise auf erwartete Ergebnisdateien.
Fehler zählen zum Aufrufbudget. Das Budget ist kein Geldbetrag.

Ein separater Collector liest ausschließlich feste Statusfelder der Laufdatenbanken
und prüft die Existenz/nichtleere Größe fest registrierter Dateien. Er öffnet keine
Dateiinhalte, Modellantworten, report.json, Schlüssel oder freien Fehlermeldungen.
Alle fünf Sekunden ersetzt er atomar `/var/lib/kwod/public/work-runs.json`.
Der Collector läuft als root mit Gruppe kwod-public, ohne Netzwerk; nur der
öffentliche Ausgabeordner ist beschreibbar (plus privates temporäres Verzeichnis).
Root wird benötigt, um die getrennten DynamicUser-Laufverzeichnisse zu lesen.

Der HTTP-Dienst liest nur diesen Abzug und validiert dessen Felder erneut.
Private Laufverzeichnisse bleiben für ihn gesperrt. `/api/v1/work-runs` ist
schreibgeschützt; es gibt keine öffentlichen Start-/Stop-/Download-Endpunkte.
Ergebnisverweise sind feste Dateinamen im jeweiligen privaten Workspace,
keine Veröffentlichungsfreigabe oder öffentliche Downloadlinks.

Ein mehr als 30 Sekunden alter Abzug wird als veraltet gekennzeichnet.
Fehlender/defekter Abzug oder unlesbare Daten bedeutet unbekannt, nicht null.
Nach Abbruch einer gesendeten Anfrage oder laufenden Werkzeugaktion erscheint
„Ausgang prüfen“. Kein automatischer Retry. Falls SQLite nach hartem Abbruch
eine WAL-Wiederherstellung braucht, erfolgt sie nur bei bestätigtem Dienststillstand
an einer privaten temporären Kopie; Originaldaten bleiben unverändert.
Dienstzustände werden vor und nach der Beobachtung geprüft. Bei Änderung gilt
die Beobachtung nicht als sicherer laufender/gestoppter Zustand.

## Auf Ubuntu installieren

Im normalen Windows-PowerShell-Terminal ausführen (vorhandener SSH-/sudo-Weg):

```powershell
& 'C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\Deploy-Ubuntu.ps1' -Action Install
```

Das vorhandene Deployment erstellt ein neues Release samt Backup vorhandener
Hauptdaten, führt Offline- und Linux-Isolationstests aus, aktualisiert die öffentliche
Ansicht und installiert den Status-Collector samt Timer. Es verweigert die
Installation bei laufendem Hauptworker. Kein Modellworker, Pilot, Produktionsstart
oder Zahlung wird dadurch ausgelöst. Das Deployment nutzt Paketdownloads und
Docker wie bisher; der Collector selbst hat kein Netzwerk.

Danach Beobachtungstunnel in einem eigenen Terminal öffnen:

```powershell
& 'C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\Watch-Agent.ps1'
```

Browser: `http://127.0.0.1:8765`. Bereits vorhandene Trial-/Pilotdaten werden gelesen,
nicht erneut erzeugt. Historische Erwartung: Trial01 sechs Versuche/Budget erschöpft,
Pilot02 fünf Versuche/ein Aufruf übrig/abgeschlossen. Maßgeblich sind die tatsächlich
gelesenen Daten. Inhalte liegen weiterhin unter dem jeweiligen
`/var/lib/kwod-work-…/data/workspace/`.

## Ein Weg für Status, Stop und Start

```powershell
& 'C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\Work-Run.ps1' -Run Pilot02 -Action Status
& 'C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\Work-Run.ps1' -Run OfflineCheck -Action Start
& 'C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\Work-Run.ps1' -Run OfflineCheck -Action Stop
```

Standardaktion ist Status; sie stoppt keinen Prozess und liest keinen Schlüssel.
Status/Stop übertragen lediglich den geprüften Launcher, kein neues Quellenpaket.
`-Run` erlaubt Trial01, Pilot02 und OfflineCheck. Die vorhandenen bezahlten Piloten
nicht starten. Start verwendet unverändert den exklusiven Einmalmarker: auch ein
wiederholter Befehl nach Abbruch erzeugt keine zweite Modellaktion.
Alte Resume-Reparaturen werden im neuen Bedienweg nicht angeboten.

OfflineCheck ist eine rein technische Fixture in
`/var/lib/kwod-work-monitor-check`, ohne Credential und mit PrivateNetwork.
Sie benutzt drei feste Antworten mit jeweils 15 Sekunden Wartezeit, Dateischreiben
und Kontextübergabe; regulärer Abschluss nach ungefähr 45 Sekunden.
Die im Monitor gezählten Versuche sind dabei **simuliert**, ohne Providerverbrauch.
Start bleibt während des Laufs im Terminal; Status/Stop aus einem zweiten Terminal.
Stop wartet auf systemd und bestätigt nur inaktiv/fehlgeschlagen oder nicht geladen.
KillMode=control-group und TimeoutStopSec=15 begrenzen den Abbruch.

Für die Ubuntu-Abnahme den OfflineCheck einmal starten, im Monitor den Fortschritt
beobachten und während einer Wartephase stoppen. Anschließend Status prüfen:
Dienst beendet, Ausgang prüfen, Startmarker gesetzt. Wiederholter Start muss
am Marker scheitern und die Versuchszahl unverändert lassen. **Marker nicht löschen.**
Der reguläre Abschluss ist lokal mit derselben Fixture geprüft; der gestoppte
Ubuntu-Prüflauf muss nicht für eine zweite Abschlussdemonstration zurückgesetzt werden.
Ausgaben und beobachtete Anzeige danach in reports/arbeitspakete.md nachtragen.

## Lokale Vorschau

```powershell
Set-Location 'C:\workspace\projects\keepworkingordie\keep-working-or-die'
..\.venv\Scripts\python.exe scripts\preview_work_monitor.py
```

`http://127.0.0.1:8766` zeigt ausdrücklich markierte temporäre Offline-Fixtures.
Strg+C beendet Vorschau und entfernt deren temporäre Daten. Die Vorschau ist kein
Abbild der echten Piloten und keine Ubuntu-Abnahme.
