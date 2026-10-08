# Entwicklungskern — Stand 15.09.2026

Der lokale Kern ist implementiert und offline ausführbar. Er ist **keine geborene Produktionsinstanz**. Es gibt keinen Birth-Befehl, keine angelegte Erbschaft, keine lokale Wallet-Sperre und keine tatsächlichen OpenAI-Aufrufe in der Validierung. Die erste öffentliche Beobachtungsansicht ist inzwischen ergänzt; finanzielle Live-Daten, Replay, Internet-/Payment-Tools und Produktionsbetrieb bleiben weitere Arbeitsschritte. Den neuen SSH-Deployment-Weg und die Grenze zum Hauptcomputer beschreibt `05_DEPLOYMENT_UND_ZUGRIFF.md`.

## Installation und erster Lauf

Python 3.12 oder neuer. Die hier geprüfte Version ist Python 3.12.14 auf Windows. Alle tatsächlich verwendeten Paketversionen stehen in `requirements-tested.txt`; das OpenAI-SDK ist 3.13.0. Für Linux müssen dieselben Versionen mit passenden Plattform-Wheels erneut geprüft werden.

Im Anwendungsverzeichnis:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements-tested.txt
.\.venv\Scripts\python.exe -m pip install --no-cache-dir --no-build-isolation --no-deps -e .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\kwod.exe --data ..\kwod-offline init
.\.venv\Scripts\kwod.exe --data ..\kwod-offline run --fixture fixtures\development.json --steps 3
.\.venv\Scripts\kwod.exe --data ..\kwod-offline inspect
.\.venv\Scripts\kwod.exe serve --public-db ..\kwod-offline\public\public.sqlite
```

In dieser bereits eingerichteten Arbeitsumgebung liegt die virtuelle Umgebung **eine Ebene höher**: `C:\workspace\projects\keepworkingordie\.venv`. Dort sind Paket und Tests installiert. Aus dem Anwendungsverzeichnis deshalb `..\.venv\Scripts\kwod.exe` bzw. `..\.venv\Scripts\python.exe` verwenden. Es ist kein globales Python notwendig.

Die drei Offline-Schritte persistieren einen Auftrag, schreiben `workspace/memory.md` und verarbeiten die zweite Fixture-Antwort. Der Agent endet in `idle` mit einem dauerhaften Wake-Zeitpunkt. Das ist eine technische Fixture, keine simulierte Lebensökonomie. `init` lässt bereits bestehende Instanzen unverändert. Ein Wechsel zwischen Fixture und echtem Provider oder zwischen Fixture-Dateien erfordert ein neues Datenverzeichnis.

Die API lauscht ausschließlich lokal auf `http://127.0.0.1:8000`. `/docs` zeigt ihre Schnittstellen. `serve` liest nur die ausdrücklich angegebene öffentliche SQLite-Datei und startet keinen Worker. Vor Geburt bleiben `/api/v1/assets` und `/api/v1/net-worth` leer. `/api/v1/status` unterscheidet `status=not_born` vom technischen `runtime_status`. Nach 30 Sekunden ohne neue Projektion ist die Worker-Beobachtung unbekannt; der letzte Status bleibt als veraltete Beobachtung sichtbar.

## Persistenz und Wiederaufnahme

`--data` enthält `private/state.sqlite`, `private/archive`, `workspace` und `public/public.sqlite`. Das Verzeichnis gehört außerhalb des Checkouts. Private Daten und Archiv niemals vom Webserver ausliefern. Ein Dateilock sperrt gleichzeitig laufende Worker, Imports und Backups aus. Die öffentliche API braucht diesen Lock nicht.

SQLite verwendet Foreign Keys, WAL und `synchronous=FULL`. Payloads und Datei-Inhalte erhalten SHA-256-Adressen, werden vor ihren DB-Referenzen geschrieben und synchronisiert. Große Terminalausgaben werden auf Dateien umgeleitet und blockweise archiviert. Die Modellansicht ist begrenzt; Vollinhalt und Kürzung bleiben privat nachvollziehbar. Ein Absturz zwischen Archivablage und DB-Commit kann eine unreferenzierte Archivdatei hinterlassen. Sie wird nicht still gelöscht.

Terminalausgaben bleiben zusätzlich im privaten `spool` erhalten, auch bei Archiv- oder Bereinigungsfehlern. Das Backup schließt diese Dateien ein. Es gibt noch keine automatische Bereinigung oder Retention; Kapazitätsplanung und geschützte Sicherung sind Betreiberaufgaben.

Ein Request durchläuft `prepared → sent → completed/incomplete/refused/failed/outcome_unknown`. Ein geplanter, noch nicht gesendeter Request ist wiederaufnehmbar. Nach einem unsicheren Sendezeitpunkt wird er nicht automatisch wiederholt. Netzwerk-/Serverfehler können trotz fehlender Usage Kosten verursacht haben; fehlende Werte bleiben `null`. Explizite temporäre Ablehnungen werden höchstens dreimal mit 30/60/120 Sekunden Backoff wiederholt, jeweils als eigener Versuch. Auth- oder Quota-Ablehnungen haben keinen automatischen Retry und bedeuten keinen Tod.

Tool-Intent, Vorzustand und Startmarkierung werden vor der Handlung persistiert. Ergebnis, Nachzustand, Function-Call-Output und gegebenenfalls Wake-Zeit werden gemeinsam committed. Nach einem unbekannten Tool-Ausgang stoppt die Wiederaufnahme. Container werden zuerst entfernt; bei nicht überprüfbarer Bereinigung wird nicht weitergearbeitet. Bereits gespeicherte Ergebnisse werden wiederverwendet. Ein Sleep wartet ohne Modellcall; UTC-Wake übersteht einen Prozessneustart. Die Loop kann mit `--forever` kontinuierlich laufen, SIGINT/SIGTERM beenden sie nach dem aktuellen begrenzten Schritt.

Für einen geprüften technischen Eingriff:

```powershell
..\.venv\Scripts\kwod.exe --data ..\kwod-offline resolve --reason "Ausgang am Archiv und Workspace geprüft; offenen Turn verwerfen"
```

Das verwirft den offenen Turn und startet einen frischen Kontext; es wiederholt **keine** unsichere Aktion. Unbekannte Modellversuche behalten ihren Status und werden nicht nachträglich zu kostenfreien Versuchen umgedeutet. Der Eingriff wird privat protokolliert. Vor diesem Befehl muss der Betreiber den unklaren Ausgang tatsächlich prüfen.

Neue abgeschlossene Turns lesen `memory.md` (maximal 16 KiB). Innerhalb einer Tool-Runde bleiben alle Response-Items einschließlich verschlüsselter Reasoning-Items und passenden Call-IDs erhalten. `store=false` verwendet keine dauerhafte Provider-Konversation. Ein Kontextlimit führt zu `recovery_required`, statt offene Tool-Calls oder Ergebnisse zu verlieren. Das Limit ist in Bytes definiert, keine vorgetäuschte exakte Tokenmessung.

Der Agent kann mit `checkpoint(memory)` seine vollständige Arbeitsübergabe in `memory.md` speichern und im nächsten Modellaufruf einen frischen Kontext beginnen. Die Notiz enthält offene Aufgaben, wichtige Dateien, bereits erledigte Aktionen und den nächsten Schritt; maximal 16.384 UTF-8-Bytes. Sie ersetzt die bisherige Datei. Das Werkzeug muss allein oder zuletzt in einer Antwort aufgerufen werden. Andere Platzierungen und ungültige Notizen liefern einen Toolfehler ohne Kontextwechsel. Der aktuelle Byteverbrauch wird jedem Modellaufruf mitgegeben, damit der Agent frühzeitig sichern kann. Eine zu spät gewählte Übergabe oder eine zu große neue Ausgangsnachricht führt weiterhin zum expliziten Kontextlimit.

Dateien und Vollarchiv bleiben erhalten; die alte Unterhaltung wird beim frischen Aufruf nicht mitgesendet. Gedächtnisqualität hängt von der selbst geschriebenen Übergabe ab. Das private Ereignis `context_checkpoint` verknüpft den abgeschlossenen Kontext und die gespeicherte Notiz. Ergebnis und Kontextwechsel werden gemeinsam committed. Nach einem Neustart wird eine bereits gespeicherte Übergabe übernommen; ein Absturz nach dem Schreiben vor dem Commit bleibt ein unklarer Toolausgang und verlangt Recovery. Dafür entsteht kein zusätzlicher Zusammenfassungsaufruf. Änderungen bislang nur lokal, noch nicht auf Ubuntu installiert.

## Provider und Kosten

`gpt-6-astra`, direkte Responses API, `reasoning.effort=low`, 4.096 Output-Tokens, `parallel_tool_calls=false`, SDK-Retries aus. Der HTTP-Client verwendet keine geerbten Proxy-Variablen. Die Umsetzung folgt der [offiziellen Responses-Referenz](https://developers.openai.com/api/reference/python/resources/responses/methods/create) und [Function-Calling-Dokumentation](https://developers.openai.com/api/docs/guides/function-calling).

Ein echter Entwicklungsaufruf braucht ein **neues** Datenverzeichnis und ausschließlich `KWOD_DEV_OPENAI_API_KEY` aus einem separat abgerechneten Entwicklungszugang. Ein generischer `OPENAI_API_KEY` wird nicht verwendet. Den Schlüssel außerhalb des Repositories und außerhalb des Chats bereitstellen. Erst nach Bereitstellung dieses Zugangs:

```text
kwod --data /var/lib/kwod-dev-api init --executor-image kwod-executor:test
kwod --data /var/lib/kwod-dev-api import-tariff config/astra-standard-2026-09-15.json
kwod --data /var/lib/kwod-dev-api run --openai-dev --steps 1
```

Die Tarifdatei hält den am 15.09.2026 dokumentierten Standardtarif und die Usage-Zuordnung fest. Grundlage: [Modell/Tarif](https://developers.openai.com/api/docs/models/gpt-6-astra), [Response-Usage-Beispiele](https://developers.openai.com/api/reference/python/resources/responses/methods/create), SDK 3.13.0 `InputTokensDetails`. Es ist eine **Schätzung**, keine Accountabrechnung. Aktivierung geschieht explizit per Import; kein Tarif wird still als Kontowahrheit angenommen.

Berechnung in Integer-Mikroeinheiten: normale Input-Tokens = Input gesamt minus Cache-Reads minus Cache-Writes. Jede Kategorie wird einmal berechnet; Reasoning ist bereits Teil des Outputs. Fehlende Kategorien, unbekannter Tarif, falscher Service-Tier, abweichender Modellname oder mehr als 272.000 Input-Tokens liefern `null`. Long-Context-/Flex-/Fast-/Batch-Tarife sind hier nicht implementiert. Weder EUR-Umrechnung noch Creditsaldo wird erfunden. Jeder Versuch behält seine vor dem Senden festgehaltene Preisversion.

`import-observation` importiert einen belegten Bestand; `import-transaction` dokumentiert Transfer, Aufwand, Einnahme, Gebühr oder Korrektur. Die JSON-Verträge stehen in `accounting.py`, Beispiele ausschließlich als Fixtures in den Tests. Wiederholte externe IDs mit identischem Inhalt werden dedupliziert; abweichender Inhalt verlangt eine neue Korrektur. Es gibt keinen automatischen Kontoabruf. „confirmed“ bedeutet: vom Betreiber als belegt importiert, nicht vom Programm beim Anbieter überprüft.

`reconcile --asset-id credits` zeigt privat den Bestand in Originalwährung abzüglich zuordenbarer geschätzter Nutzung nach dessen Stichtag. Der Betreiber muss das richtige Compute-Asset angeben. Transaktionsjournal und Rechnungsbelege belasten den bereits beobachteten Bestand nicht ein zweites Mal. Überlappende Zeitfenster, unbekannte Nutzung oder Währungen bleiben ungeklärt. Negative belegte Werte werden nicht auf null gekappt. Portfolioübergreifende EUR-Bewertung, automatischer Rechnungsabgleich und Produktionsökonomie sind noch offen.

## Logging und öffentliche Projektion

Privat: Verfassung/Konfiguration/Quellhash, exakte vorbereitete Requests, Response-Objekte einschließlich unbekannter SDK-Felder, Provider-Fehler, Usage, Toolargumente, Vollausgaben, sichtbare Kürzungen, Vor-/Nachmanifeste samt Datei-Inhalten, Entscheidungen als kurze Selbstberichte und Eingriffe. API-Key und Auth-Header sind kein Archivinhalt. Nicht ausgelieferte Providerantworten und Zwischenzustände innerhalb eines Terminalprozesses sind nicht vollständig beobachtbar. Ein Log-/Datenträgerfehler stoppt weitere Arbeit; selbst wenn kein Fehlerdatensatz mehr geschrieben werden kann, bleibt der Worker beendet.

Öffentlich: separate DB mit eigener monotoner Event-ID, Schema-Version, beobachtetem und veröffentlichtem Zeitpunkt. Projektion und Cursor werden atomar fortgeschrieben; wiederholtes Projizieren erzeugt keine Duplikate. Nur feste Labels und ausgewählte Statusfelder gelangen hinein. Keine Rohpayload, Shellbefehle, Pfade, Dateitexte oder Begründungen. Freitext-Entscheidungsüberschriften und finanzielle Produktionswerte werden vor Geburt nicht veröffentlicht. Historisches Replay ist damit vorbereitet; eine Replay-Oberfläche ist noch nicht gebaut.

## Backup und Restore

```powershell
..\.venv\Scripts\kwod.exe --data ..\kwod-offline backup ..\kwod-backup-001
..\.venv\Scripts\kwod.exe --data ..\kwod-restored restore ..\kwod-backup-001
..\.venv\Scripts\kwod.exe --data ..\kwod-restored inspect
```

Zielverzeichnisse dürfen nicht existieren. Das Backup hält den Worker-Lock, lehnt unklare Toolausgänge ab, nutzt die SQLite-Backup-API, kopiert das überprüfte Archiv und den ruhenden Workspace und schreibt zuletzt das Hashmanifest. Die öffentliche Projektion wird beim Restore aus privaten Ereignissen neu erzeugt. Ein Backup umfasst private Inhalte und gehört entsprechend geschützt. Hashes erkennen Beschädigung, ersetzen aber keine signierte Herkunft oder extern gesicherte Kopie. Windows-Prozessneustart und Restore sind getestet; Stromausfall, volle reale Platte und Linux-Dateisystemdurabilität sind noch separat zu prüfen.

## Linux-Voraussetzungen und verbleibende Abnahme

Festgelegter Deployment-Weg: Steuerung und Upload von Windows 11 per SSH auf einen Ubuntu-Host. Runtime, privates Archiv, Workspace, Executor und öffentlicher Lesedienst laufen auf Ubuntu; Windows ist der Verwaltungsrechner. SSH-Ziel, Benutzer, Ubuntu-Version und CPU-Architektur sind noch nicht angegeben. Es wurde noch keine SSH-Verbindung hergestellt oder ein Deployment ausgeführt. Der Entwicklungs-Key wird geschützt auf dem Ubuntu-Host bereitgestellt; die Dienstvorlage liest `/etc/kwod/development.env` mit `KWOD_DEV_OPENAI_API_KEY`.

Ein Konto zum Empfang von Einnahmen ist weiterhin weder ausgewählt noch angebunden. Die Architektur sieht einen realen, getrennt nachvollziehbaren Bestand unter der Betreiberidentität vor. OpenAI-Compute-Guthaben und ein späterer Zahlungseingangskanal sind getrennte Komponenten; der jetzige Belegimport ist noch keine Zahlungsintegration.

Die Vorlagen unter `deploy/` sind vorbereitet, **nicht installiert oder auf Linux abgenommen**. Runtime und öffentlicher Dienst benötigen getrennte Benutzer. Der Executor erhält UID/GID 65532 und nur den Workspace-Mount. Beispielhafte Provisionierung durch den Betreiber auf einem passenden Linux-Ziel:

```sh
sudo groupadd --gid 65532 kwod-workspace
sudo useradd --system --gid kwod-workspace --no-create-home kwod-runtime
sudo useradd --system --user-group --no-create-home kwod-public
sudo install -d -o kwod-runtime -g kwod-public -m 0750 /var/lib/kwod
sudo install -d -o kwod-runtime -g kwod-workspace -m 0700 /var/lib/kwod/private
sudo install -d -o kwod-runtime -g kwod-workspace -m 2770 /var/lib/kwod/workspace
sudo install -d -o kwod-runtime -g kwod-public -m 2750 /var/lib/kwod/public
docker build -f deploy/Executor.Dockerfile -t kwod-executor:test .
```

Vorhandene UID/GID-Kollisionen müssen auf dem tatsächlichen Ziel geklärt werden. Der vertrauenswürdige Runtime-Benutzer braucht Docker-Zugriff; dies ist Host-Verwaltungsbefugnis und darf nie in den Executor gelangen. Die Dienstvorlage setzt keine Docker-Gruppenmitgliedschaft voraus oder stillschweigend durch. Docker-Socket, Private-DB, Schlüsselverzeichnis und Host-Home werden nicht gemountet. Rootless Docker braucht eine gesonderte UID-/GID-/Socket-Konfiguration und ist hier noch nicht nachgewiesen.

Container: kein Netz, read-only Root-FS, keine Capabilities, `no-new-privileges`, Prozess-/RAM-/CPU-Limits, begrenztes `/tmp`. Nach jedem Befehl werden Container und alle Hintergrundprozesse entfernt. Persistiert werden Workspace-Dateien; laufende Prozesse und Paketinstallationen im Container-Root bleiben nicht erhalten. Keine Host-Shell als Fallback. Ohne Image/Docker liefert das Tool einen Fehler. Für Produktion das Basisimage und das gebaute Executor-Image per Digest fixieren; das vorliegende Dockerfile ist eine Entwicklungsvorlage.

Dateitools setzen einen exklusiv durch den Worker verwalteten Workspace voraus. Keine konkurrierenden Host-Schreiber zulassen. Container-Ausführungen müssen vor Dateizugriffen vollständig beendet sein. Symbolische Links, Junctions, Hardlinks, Geräte und Pfadausbrüche werden abgewiesen. Absichtlich unlesbare oder ungültige Workspace-Dateien können Recovery erfordern. Quota für den Workspace und überwachte Archivkapazität auf Linux provisionieren; eine RAM-Begrenzung des Containers ist keine Host-Diskquota.

Linux-Integration ausdrücklich aktivieren, nachdem Image, Identitäten, Gruppenrechte und Docker-Zugriff bereitstehen:

```sh
KWOD_RUN_LINUX_ISOLATION=1 KWOD_EXECUTOR_IMAGE=kwod-executor:test python -m pytest tests/test_linux_executor.py -v
```

Vor Geburt fehlen: diese Isolationstests, Dienst-/SIGTERM-/echte Reboot-Prüfung, 24 Stunden Offline-Testbetrieb mit Restore, getrennt bezahlter Provider-Smoke-Test, tatsächliche Account-/Tarif-/Cache-Abrechnung, nachgewiesene Produktionsfinanzierung und Belege über das 50-Euro-Erbe, geklärte Nachbelastungsgrenze und ein fixiertes Release. Danach erst Birth-Werkzeug implementieren und separat freigeben. Diese Voraussetzungen sind keine Hindernisse für den gelieferten Offline-Entwicklungskern.

Für den noch ausstehenden 24-Stunden-Lauf liegt ein Harness mit echten Wartezeiten, wiederholter Datenbank-Wiederöffnung und abschließendem Restore bereit:

```sh
python scripts/offline_soak.py --seconds 86400 --data /var/lib/kwod-soak-01 --report reports/soak-24h.json
```

Es verwendet ausschließlich markierte Fixtures. Der kurze lokale Probelauf ist kein Ersatz für 24 Stunden und keinen Linux-Reboot.
