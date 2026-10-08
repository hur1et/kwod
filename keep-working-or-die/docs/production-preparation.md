# Produktionsvorbereitung vor Birth

Stand 16. September 2026: Die fünf Voraussetzungen sind lokal umgesetzt. Der zuletzt bestätigte Ubuntu-Release ist dev-20260916-183502-0a6c94c5. Der neue Produktionspfad ist erst nach Installation und Prepare-Production auf dem Server eingerichtet und geprüft. Diese Vorbereitung ist keine Birth-Freigabe.

## Getrennte Instanzen

Entwicklung bleibt unter /var/lib/kwod mit Instanz dev. Produktion erhält /var/lib/kwod-production mit Instanz prod, eigener Datenbank, Archive, Workspace, Softwarehome und öffentlicher Projektion. Store weist den falschen Modus zurück. CLI verlangt für prod einen ausdrücklichen Datenpfad und den Produktionsanbieter. Runtime, Kontext, Buchhaltung und Projektion verwenden die jeweilige Instanz. Entwicklungsanbieter dürfen keine Produktionsinstanz betreiben. Entwicklungsruntime darf den produktiven Mail- und Browserkanal nicht verwenden.

## Gespeicherter Startauftrag

Configure-Production persistiert START_OBJECTIVE im Checkpoint und initialen Modellkontext. MISSION.md und RIGHTS_AND_LIMITS.md stehen im eigenen Workspace. Der Auftrag lautet: zuerst Umgebung, Werkzeuge, Depot und Mission verstehen, dann Julius an julius.weiske@gmx.de schreiben, was der Agent sieht, vorhat und plant. Bei Schwierigkeiten darf er den Betreiber kontaktieren. Kunden, Angebote und Einnahmen findet er selbst. Compute, Skills, Weiterbildung, Werkzeuge und Reserven bleiben seine Entscheidungen. Kein fiktives 50-Euro-Erbe wird gesetzt.

## Gemeinsamer Mailstand

Die vorhandene Mail-Outbound-Datenbank wird einmalig per SQLite-Backup in die Produktionsinstanz übernommen, sofern dort noch keine vorhanden ist. Ein vorhandener Restore-Prüfmarker wird ebenfalls übernommen. /etc/kwod-production/mail-ledger.path verweist auf diese kanonische Datenbank. Produktive Runtime und manuelle Mailprüfungen verwenden danach dieselbe Historie. Dedupe bindet einen Schlüssel an den Inhalt; unklar beendete SMTP-Vorgänge werden nicht automatisch wiederholt. SMTP-Annahme beweist keine Zustellung. Der unabhängige Safety-Dienst bleibt probabilistisch; die Mengenbegrenzung bleibt zehn reservierte Nachrichtenkandidaten pro 24 Stunden.

Prepare-Production startet die unabhängigen Wächter und Gateways mit dem installierten Code neu. Eine rootgeschützte Vorbereitungsspur erfasst Release, SHA256 aller Python-Module und tatsächliche systemd-InvocationIDs. Readiness vergleicht diese Angaben mit dem aktuellen Installationsstand. Ein neues Release erfordert erneute Vorbereitung; alte erfolgreiche Ausgaben gelten dafür nicht.

## Readiness aus dem Installationszustand

Test-ProductionReadiness führt ausschließlich den installierten Checker aus. Er liest SQLite im URI-readonly-Modus und prüft archivierte Inhalte gegen ihre Hashes. Geprüft werden Startkontext, Constitution, Modellkonfiguration, fehlende Birth und Modellversuche, geschützte Zugangsdaten, Ledgerintegrität, Quellmanifest, Prozesse, Unix-Sockets, deaktivierte Worker, Produktionsunit, Executor-Image, Browser-Firewall-Hooks und Produktionsprojektion. Fehler ergeben konkrete Blocker und einen fehlschlagenden Exitcode. Es erfolgt keine Modellanfrage, Mail oder Zahlung.

Diese Prüfung bestätigt die Produktionsvorbereitung. Sie ersetzt keine tatsächliche Erbfeststellung oder Birth-Freigabe. Am 17 September hat der Betreiber den Start ohne finanziertes Wallet und ohne vorherigen Zahlungstest freigegeben; dieser Test ist optional und wird nicht als erfolgreich ausgegeben. Die Firewallprüfung bestätigt eingebundene Chains, keinen vollständigen adversarialen Netzwerktest.

## Astra über OpenRouter

kwod-production.service verwendet --mode prod --data /var/lib/kwod-production run --openrouter-prod --forever. Der Anbieter liest den Key ausschließlich aus dem systemd-Credential openrouter.key. Entwicklungs-Umgebungsschlüssel werden nicht übernommen. Modell ist gpt-6-astra mit der bestehenden festgelegten OpenRouter-Routingkonfiguration.

Der Dienst bleibt deaktiviert und ungestartet. Sein erforderlicher /etc/kwod-production/BORN-Marker wird durch die Vorbereitung nicht erzeugt. Auch die Runtime lässt ohne born_at keinen Modellaufruf zu. Stop und Watchdog-Pause sperren zusätzlich. Der sichere Operator-Stopp umfasst jetzt beide Worker. Der Installer verweigert ein Upgrade bei laufendem Entwicklungs- oder Produktionsworker.

## Installation und Vorbereitung

```powershell
& .\deploy\Deploy-Ubuntu.ps1 -SshTarget s340 -Action Install
& .\deploy\Prepare-Production.ps1 -SshTarget s340
```

Danach muss all_five_preparation_checks_pass aus dem tatsächlichen Ubuntu-Lauf true sein. Worker und Birth bleiben dabei aus. Der einmalige Birth-Vorgang mit frisch belegtem OpenRouter-Erbe bleibt eine separate bewusste Aktion. Der Zahlungstest wird auf Wunsch des Betreibers nicht vor Birth durchgeführt.
