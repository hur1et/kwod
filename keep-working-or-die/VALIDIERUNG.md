> Aktuell 16.09.2026: 133 Tests und 118 Subtests bestanden, 3 skips. [AP0-Bericht mit aktuellen Nachweisen und Grenzen](reports/ap0-status-2026-09-16.md). Die folgenden Abschnitte dokumentieren frühere Prüfstände.

# Validierung — Entwicklungskern

## Aktueller Stand · 15.09.2026

Implementiert und lokal installiert unter Python 3.12.14 / Windows. Die geprüften Abhängigkeiten sind in `requirements-tested.txt` festgeschrieben. `pip check` meldet keine Konflikte. Die ursprünglichen Planungsdateien wurden nicht durch Implementierungsannahmen ersetzt.

**50 Offline-Tests erfolgreich; zwei Linux-Integrationstests mangels Linux/Docker übersprungen.** Der maschinenlesbare Bericht liegt unter `reports/offline-tests.xml`. Die Tests verwenden ausschließlich Fixtures und lokale HTTP-Mocktransports, keine echten Modellcalls.

Ergänzung zum Deployment: Quellpaket-Whitelist ohne private Daten/Schlüssel, Manifestprüfung und Manipulationserkennung getestet. Beide PowerShell-Skripte wurden durch den PowerShell-Parser ohne Syntaxfehler geprüft. Die öffentliche HTML-Ansicht ist über FastAPI inklusive Sicherheitsheadern getestet. Eine lokale Vorschau ist lauffähig; der automatisierte Chrome-Screenshot scheiterte an der Browserumgebung, daher keine abgeschlossene visuelle Browserabnahme. Remote-Installer, echte SSH-Übertragung und Dienstaktivierung sind noch nicht ausgeführt. Der Alias `s340` ist hier nicht auflösbar, und der Zugriff auf die Windows-SSH-Konfiguration wurde verweigert.

Geprüft:

- Wiederholbare Migrationen, erhaltene Initialisierung, keine automatische Geburt oder Erbschaft.
- Exklusiver Worker-Lock; getrennte CLI-Prozesse führen denselben gespeicherten Ablauf fort.
- Crash vor Senden, nach Senden, nach Response-Empfang und -Persistierung, nach Dateiwirkung und nach Ergebnis-Commit; keine automatische Wiederholung unsicherer Aktionen.
- Datei schreiben, Sleep committen, Datenbank schließen/neu öffnen, vor Wake keinen Call erzeugen, danach gespeicherte Ergebnisse korrekt fortsetzen.
- Simulierte volle Platte vor Request und nach Response; Fail-stop und unbekannte Kosten statt behaupteter Nullverbrauch.
- Incomplete, Refusal, ungültige Argumente, Auth-/Quota-/Rate-Limit-/Serverfehler, mehrdeutige Timeouts; eigenständige Retry-Versuche und Backoff.
- Echtes OpenAI-SDK mit lokalem HTTP-Mock: Serialisierung, unbekannte Usage-Felder, Request-ID, ausgeschaltete SDK-Retries und ausschließlicher Entwicklungs-Key.
- Erhalt verschlüsselter Reasoning-Items und Function-Call-IDs bei `store=false`; Kontextlimit stoppt vor dem nächsten Call.
- Cache-Kategorien, Reasoning ohne Doppelzählung, unbekannte Usage, falsche Kategorien, Tarifversion pro Versuch und Schätzungen in Mikroeinheiten.
- Beleg-Deduplikation, Konflikte externer IDs, Transfer/Korrektur ohne zweite Bestandsbelastung, Verbrauch nur nach Bestandsstichtag, unbekannte Währungszuordnung und negative Bestände.
- Pfadausbrüche, Windows-Gerätenamen, symbolische Links und Hardlinks; kein unisolierter Terminal-Fallback.
- Container-Aufrufvertrag ohne Netz/Host-Keys/private Mounts, simuliertes Timeout mit Containerbereinigung, vollständige Ausgabe trotz gekürzter Modellansicht und erhaltene Spooldateien bei Archivfehler.
- Private Decision Records und feste Activity-Kategorien.
- Öffentliche Projektion mit Deduplikation, begrenztem Cursor, Nur-Lese-Zugriff und Geheimnis-Markern; API funktioniert ohne Zugriff auf private DB, meldet veraltete Daten und generische Fehler.
- SQLite-Backup samt gehashtem Archiv, Workspace und privaten Spooldateien; Wiederherstellung in neuem Verzeichnis, Integritätskontrolle und Ablehnung manipulierter Dateien.

Kurzer zusätzlicher Offline-Dauerlauf: 12 Sekunden angeforderte Laufzeit, rund 14 Sekunden einschließlich Backup/Restore, 82 Datenbank-Wiederöffnungen, sieben Fixture-Modellversuche und erfolgreich überprüfter Restore. Details: `reports/offline-soak-smoke.json`. Dieser Lauf erfolgte vor der letzten Spool-Ergänzung; deren Sicherung und Fehlerverhalten sind durch die abschließenden Unit-Tests geprüft. Der Kurzlauf ersetzt keinen 24-Stunden-Test.

Verbleibende Voraussetzungen:

- Echter Linux-Containerlauf mit Zugriffsschutz, Prozessgruppen-/Timeout-/Netzprüfung; die dafür vorgesehenen zwei Tests wurden hier nicht ausgeführt.
- Tatsächliche Linux-Benutzer-/Gruppen-/Socket-Rechte, Image-Digests, Dienstinstallation, Reboot, SIGTERM und Datenträger-/Quota-Verhalten.
- 24-Stunden-Lauf und Restore auf dem Zielsystem. Harness: `scripts/offline_soak.py`.
- Separat bezahlter Provider-Smoke-Test mit `gpt-6-astra`, Kontozugang und tatsächlicher Abrechnung. SDK-Mocktests beweisen keinen Accountzugang.
- Reale Produktionsbelege, finanzielle Isolation, Nachbelastungsgrenzen, vollständige EUR-Portfoliobewertung und automatischer Rechnungsabgleich.
- Birth-Werkzeug, Produktionsgeburt, finanzielle Live-Daten/Replay, offener Internetzugriff und Payment bleiben offen. Eine erste öffentliche Beobachtungsansicht unter `/` ist inzwischen implementiert.

Eine DeprecationWarning stammt aus der installierten Starlette/AnyIO-Testclient-Kombination. Sie beeinträchtigt die bestandenen Tests nicht. Der letzte Testlauf deaktiviert den optionalen Pytest-Cache, weil dessen bestehendes Verzeichnis in dieser Arbeitsumgebung Schreibrechte verweigert hat.

Installation und Start: `04_ENTWICKLUNGSKERN.md`.

## Separater Wallet-Signierkern (15.09.2026)

13 gezielte Tests und 25 Subtests für Signierkern und Deployment bestanden.
Geprüft: feste Base-/USDC-Transaktionsstruktur, ungültige Zahlen/Adressen,
gesperrtes Signieren im Prüfmodus, idempotente Rückgabe nach Journal-Neustart,
Nonce-/Auftragskonflikte, Rollback bei Signier- und Commitfehlern und Bindung
des Journals an genau ein Wallet. Lokale Unit-Tests simulieren die Signatur;
echte Kryptografie und Linux-Dienstisolation wurden zusätzlich vom Installer auf
Ubuntu geprüft und vom Betreiber erfolgreich bestätigt: `signer_selftest=passed`,
`network_used=false`, `isolation_checks=passed`. Der Dienst meldet null signierte
Transaktionen und deaktiviertes Signieren/Broadcast; der Worker blieb aus.
PowerShell-Syntax und Python-Kompilierung bestanden. Es gab keine reale Signatur
mit dem Betreiber-Wallet und keinen Broadcast.

## Arbeitsübergabe des Agenten (15.09.2026)

`checkpoint(memory)` ergänzt einen vom Agenten gewählten Kontextwechsel mit
dauerhafter Arbeitsnotiz. Sieben neue Tests prüfen Werkdatei-Erhalt, Neustart nach
Commit, unklaren Schreibausgang, falsche Call-Reihenfolge, ungültige Notizen,
Fortsetzung nach einer langen Toolrunde und Archivfehler. Die Tests verwenden
Fixture-Antworten; sie belegen nicht die Qualität realer Modellübergaben.

Gesamtlauf: **115 Tests und 107 Subtests bestanden, 3 übersprungen** (lokal fehlende
Kryptografie-Abhängigkeit bzw. explizite Linux-Isolationstests). Eine bekannte
Starlette/AnyIO-DeprecationWarning. Befehl: `python -m pytest -q -p no:cacheprovider`.
Kein echter Provideraufruf, keine Produktionsgeburt, kein Ubuntu-Update in diesem
Schritt. Der automatische Zahlungsnachkauf ist auf Nutzerwunsch zurückgestellt.

## Historische Prüfung des Vorbereitungspakets

14.09.2026: Beide SQL-Entwürfe erfolgreich in getrennten leeren SQLite-Datenbanken ausgeführt; integrity_check und foreign_key_check bestanden. Eindeutigkeit einer Lebensinstanz und eines Birth-Ereignisses durch abgewiesene Doppelanlagen geprüft. JSON-Konfiguration lesbar und auf Entwicklung ohne Geburt eingestellt. Referenzbild vorhanden.

Diese ursprüngliche Prüfung betraf ausschließlich Datenbankentwurf und Übergabepaket. Der aktuelle Implementierungs- und Prüfstand steht oben; insbesondere ist eine Produktions-Birth-Transaktion weiterhin nicht implementiert.

