# KEEP WORKING OR DIE — Übergabe, 15.09.2026

## Auftrag und Arbeitsweise

AKTUELL: Nutzer lieferte Pilot02-Inhalte als Anlage, vollständig gelesen. Agent wählte
FAQ-/E-Mail-Paket für Fahrradwerkstätten, fiktive Probe,89EUR-Preishypothese,
Selbstprüfung mit echten Textbefunden. Original gesichert unter
reports/pilot-02/originalausgabe.txt. Auf „Continue“ drei Entwicklungsartefakte
erstellt: auswertung.md, arbeitsprobe-geprueft.md, nachfragetest.md. Bereinigte Probe
und Konzepttest stammen ausdrücklich vom Entwicklungsassistenten, nicht vom autonomen
Agenten. Nachfrageprüfung vorbereitet, kein Kontakt gesucht/angeschrieben.0,09USD
gilt nur Trial01; Pilot02-Kosten unbekannt. Testpreis89EUR und zwei angenommene
Stunden sind keine validierte Ökonomie. Nächster fehlender Nachweis ist Käuferfeedback;
keine weiteren Pilotaufrufe oder Veröffentlichungen ohne konkreten nächsten Auftrag.

NEUESTER ERFOLG: Nutzer führte Pilot02 aus. Ergebnis work_trial=completed,
runtime_status=idle/turn_completed, profile=earning,5 Modellversuche,1 Handoff,
requests_remaining=1,missing_files=[], keine Providerdiagnose, keine Zahlung/Birth.
Alle vorgesehenen Dateien vorhanden; Inhalte und tatsächliche Kosten noch unbekannt.
Nächster Schritt: vorhandene works/entscheidung.md,arbeitsprobe.md,angebot.md,
pruefung.md auf Ubuntu read-only ausgeben lassen, danach inhaltlich beurteilen.
Nicht erneut starten; Abschluss ist berichtet, keine automatische Fortsetzung nötig.

NEUESTER SCHRITT: Auf weiteres „Weiter gehts“ Pilot02 vorbereitet: eigene kleine
verkäufliche Leistung/Produkt auswählen (max3 Optionen), echte kompakte Arbeitsprobe,
Angebot mit ungeprüfter Preis-/Nachfragehypothese, Checkpoint, kritische Prüfung und
ein nächstes Nachfrageexperiment. Keine Veröffentlichung/Akquise/Einnahmen erfinden.
Start: Test-WorkTrial.ps1 -Pilot. Eigener StateDirectory /var/lib/kwod-work-pilot-02,
Dienst kwod-work-pilot-02.service.6 Aufrufe je2048 Tokens, bisheriges Prepaid-Konto;
0,09USD von Trial01 ist nur Beobachtung, keine Preiszusage. Fortschritt/Restbudget aktiv.
Stop/Inspektion: Test-WorkTrial.ps1 -Pilot -StopAndInspect. Alte Resume-Modi mit
-Pilot abgewiesen. Trial01 bleibt unverändert. Dateien: works/entscheidung.md,
works/arbeitsprobe.md, works/angebot.md, works/pruefung.md, memory.md.17 Tests+11
Subtests und PS-Syntax bestanden. Pilot02 noch nicht auf Ubuntu gestartet; Nutzer-
Ausgabe steht aus. Keine andere Modellwahl, keine öffentlichen Handlungen.

KOSTENBEOBACHTUNG: Nutzer meldet0,09USD für Trial01. Gespeichert in
docs/work-trial-cost-observation.json als user_reported, nicht unabhängig verifiziert.
5 erfolgreiche Aufrufe => rechnerisch0,018USD je erfolgreichem Aufruf, keine belegte
Einzelverteilung. Keine EUR-Umrechnung, kein errechneter Restkontostand, kein zweiter
Ledgerabzug. Bestehende40EUR-Einzahlungsangabe davon getrennt behandeln.

AKTUELLER FOKUS NACH ERGEBNIS: Nutzer lieferte Gedicht „Restlaufzeit“, passende
Werkbeschreibung und präzise memory.md-Übergabe. Inhalt wurde als brauchbarer
erster technischer Test beurteilt; keine Aussage über Einnahmen/Verkäuflichkeit.
Nutzer fragte, ob dies die Aufgabe war: klargestellt, dass Gedichtaufgabe vom
Assistenten für Funktionstest gewählt wurde, nicht vom Nutzer konkret vorgegeben.
Auf „Weiter gehts“ lokale Verbesserung: LimitedProvider zeigt vor JEDEM Aufruf
Versuchsnummer/Restbudget inkl Fehlversuchen, expliziten Abschluss bei letztem
Aufruf und Hinweise zu Tool-Bündelung/Checkpoint-Folgeaufruf. Exakte gefilterte
Trialanfrage inklusive Hinweis wird als work_trial_request privat archiviert.
Report ergänzt requests_remaining, stop_reason, missing_files.22 Tests+13 Subtests
bestanden. Noch nicht auf Ubuntu installiert, kein weiterer Modellaufruf; ursprünglicher
Trial ausgeschöpft und gestoppt. Nicht noch ein Gedicht erzeugen oder alte Trialmarker
zurücksetzen. Nächster inhaltlicher Schwerpunkt bleibt selbstständiges nützliches
Arbeiten und später Einnahmen; dieser Trial hat das noch nicht nachgewiesen.

NEUESTER BESTÄTIGTER STAND: -StopAndInspect erfolgreich. Dienst gestoppt/nicht aktiv.
6 gespeicherte Modellversuche: erster404, danach5 completed am15.09.2026 UTC von
23:17:10 bis23:17:43 (~33s zusammen).5 Toolcalls completed. Runtime ready mit
tool_round_completed. works/entwurf.md, works/beschreibung.md und memory.md vorhanden;
works/review.md fehlt. Damit echter OpenRouter-Zugang und Werkzeugausführung belegt,
Trial aber inhaltlich unvollständig. Limit6 inkl404 erreicht; kein automatisches
Nachstarten/keine weitere Resume-Option hinzufügen. Inhalte, Usage und tatsächlicher
Checkpoint-Verlauf noch nicht gelesen. Nächster Schritt: vorhandene drei Textdateien
vom Nutzer read-only per SSH ausgeben lassen, Inhalt beurteilen. Keine zusätzlichen
Modellkosten nur zum Vervollständigen der Review auslösen. Ursache der früheren404
weiterhin nicht eindeutig (geänderte Parameter wurden inzwischen angenommen).

LETZTER FEHLER: -StopAndInspect meldete UnboundLocalError. Ursache lokaler
`import json` später in launcher.main überschattete globalen Import im frühen
StopAndInspect-Zweig. Lokalen Import entfernt. Stoppschritt steht vor Fehlerstelle;
Statusausgabe/DB-Inspektion wurde nicht erreicht. Neuer Regressionstest ruft main
mit exakt --stop-inspect auf und liest echte lokale Fixture-DB, ohne Dienststart.
Nutzer soll -StopAndInspect erneut ausführen; kein Trial-/Modellneustart.

NEUESTER VORGANG: Nutzer führte -ResumeRejected aus, brach Warten mit Strg+C ab.
Launcher-Trace bei subprocess.run/systemd-run; tatsächlicher Dienst-/Modellstatus
unbekannt. Nicht erneut starten. Neu: Test-WorkTrial.ps1 -StopAndInspect beendet
explizit kwod-work-trial-01.service und liest SQLite nur read-only (Versuchsstatus,
Zeitpunkte, Toolstatus, feste Werkdatei-Präsenz). Kein Modellaufruf. Künftiger
KeyboardInterrupt stoppt Dienst vor Quellenbereinigung. Fortschrittsmeldungen vor/
nach Provideraufruf ergänzt. Nutzer fragt Laufzeit: RuntimeMaxSec900=15min, HTTP-
Timeout90s pro Netzwerkwartephase, nach erstem404 noch max5 Versuche. Bisher keine
Zwischenmeldungen, daher scheinbares Hängen. Ausgabe von -StopAndInspect steht aus.

AKTUELLSTER STAND: CheckProvider erfolgreich. openai/gpt-6-astra und openai-Route
vorhanden. supported_parameters enthält weder parallel_tool_calls noch service_tier.
Vermutung: require_parameters=true filterte deswegen alle Routen (nicht bewiesen,
ursprünglicher Errorbody wurde verworfen). OpenRouterProvider entfernt jetzt nur
diese beiden direkten API-Felder; strict routing/tool/reasoning bleibt. Runtime
verarbeitet mehrere Toolcalls weiter seriell. Fehler werden künftig als feste
Kategorien ohne Rawmessage klassifiziert und im Trialreport ausgegeben.
Neu: Test-WorkTrial.ps1 -ResumeRejected. Akzeptiert ausschließlich genau einen
failed/openrouter_http_404-Versuch, passenden provider_unavailable-Zustand, keinen
pending_attempt, gleiche Objective und null Toolcalls. Einmalmarker verhindert
Doppelstart. Vorheriger Versuch bleibt, Gesamtgrenze6 (also max5 weitere). Eingriff
und Adapterquellhash privat protokolliert.22 Tests+13 Subtests/PS-Syntax bestanden.
Nächster Schritt: Nutzer führt -ResumeRejected aus, Ausgabe auswerten. Noch kein
erfolgreicher Modelloutput. Payment/Support weiterhin zurückgestellt.

NEUESTER NACHTRAG: -ResumeUnstarted lief auf Ubuntu bis OpenRouter, ein Versuch
mit HTTP404, state provider_unavailable, keine Handoffs, kein Werk. Damit ist
-ResumeUnstarted jetzt NICHT mehr zulässig. Kein automatischer Retry. Öffentlicher
OpenRouter-Katalog listet openai/gpt-6-astra;404-Ursache weiterhin ungeklärt (Adapter
verwarf Errorbody). Neu: Test-WorkTrial.ps1 -CheckProvider führt ausschließlich zwei
GETs auf models und models/openai/gpt-6-astra/endpoints im Serversandboxprozess aus.
Gibt Modellverfügbarkeit und Provider-/Parameter-Metadaten aus; keine Inference,
keine Trialdatenänderung. Nächster Schritt: Ausgabe dieses Modus auswerten.

NEUESTER STAND: Trial-Diagnose erhalten: Marker+DB existieren, keine Modellversuche,
Credential/CWD/StateDirectory okay. EPERM beim chmod2770 in FileTools.__init__.
Korrigiert durch workspace_shared=False für Trial (700/600 ohne setgid); normale
Containerrechte bleiben Standard. Nutzer soll Test-WorkTrial.ps1 -ResumeUnstarted
ausführen. Diese Fortsetzung akzeptiert nur vorhandenen Marker+DB und leere Tabellen
instance/model_attempt/tool_call/trajectory_event sowie leeren Workspace. Exklusiver
resume-unstarted-used-Marker verhindert Doppelstarts; keine Marker werden gelöscht.
47 Tests+18 Subtests und PS-Syntax bestanden. Korrigierter Ubuntu-Lauf steht aus.

AKTUELLER FOKUS: Nutzer hat am Ende ausdrücklich weitere Arbeit an den relevanten
Agentenfunktionen verlangt. Automatischer Compute-Nachkauf und Support-Anfrage sind
zurückgestellt; NICHT versenden oder erneut zum Hauptthema machen. Bereits gemeldetes
OpenRouter-Guthaben: 40 EUR. Kein Produktionsstart aus dieser Entwicklungsfreigabe
ableiten. Die folgenden Payment-Abschnitte sind Hintergrund, kein aktueller Auftrag.

16.09.2026: Nutzer hat den begrenzten echten OpenRouter-Arbeitslauf mit „los“
beauftragt. Dafür neu: deploy/Test-WorkTrial.ps1, deploy/run_work_trial.py und
src/kwod/work_trial.py. Befehl in Nutzer-PowerShell:
& 'C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\Test-WorkTrial.ps1'
Maximal6 Modellaufrufe, je2048 Output-Tokens, kein Provider-Retry; nutzt ausdrücklich
das vorhandene Prepaid-Konto via systemd LoadCredential im getrennten DynamicUser.
Nur Datei-/Checkpoint-/Decision-Tools; keine Shell/Wallet/Veröffentlichung. Aufgabe:
deutscher Textentwurf + Werkbeschreibung, Übergabe, danach kritische Review.
Laufordner /var/lib/kwod-work-trial-01, exklusiver trial-started-Marker verhindert
erneute Kosten bei Wiederholung. Marker NICHT löschen, um nach Fehler blind neu
zu starten. Bei unklarem Ausgang erst report.json/private DB prüfen. Kein Birth,
kein dauerhafter Dienst, keine Installation eines neuen Haupt-Releases.
20 Tests +15 Subtests bestanden; PS/Python-Syntax und Paket geprüft. Noch NICHT
auf Ubuntu gelaufen, Nutzer-Ausgabe steht aus. Neueste Quellen werden im Test
temporär rootgeschützt bereitgestellt; vorhandene /opt/kwod/current/.venv wird
für Python-Abhängigkeiten genutzt. Linux/systemd-Verhalten noch unbestätigt.
NACHTRAG: Erster Nutzerstart scheiterte vor Dienststart mit „Failed to parse IP
address prefix: localhost“. Ursache anhand systemd v255 bus-unit-util.c bestätigt:
Aliase werden nur als Gesamtwert erkannt, nicht in Listen numerischer Präfixe.
run_work_trial.py nutzt jetzt ausschließlich numerische IPv4/IPv6-Präfixe in der
Deny-Liste. Loopback/LAN bleiben gesperrt,127.0.0.53 bleibt DNS-Ausnahme. Erster
Versuch startete keinen Testprozess/Modellaufruf; derselbe PS-Befehl kann mit dem
korrigierten Launcher erneut ausgeführt werden. Keine Marker löschen. Zusätzlicher
Regressionstest test_work_trial_launcher.py prüft die tatsächlichen CLI-Präfixe.
WEITERER NUTZERLAUF: Prozess meldete PermissionError ohne Fundstelle. Ursache noch
NICHT geklärt; keine Aussage „keine Modellkosten“ aus dieser Ausgabe ableiten.
Diagnosemodus ergänzt: Test-WorkTrial.ps1 -Diagnose. Liest rootseitig nur Marker und
DB-Versuchszähler, startet denselben Sandboxzugriff ohne Netzwerk/Provideraufruf,
prüft Credential per Öffnen/Schließen OHNE Inhaltslesen sowie StateDirectory,
temporäre Store-Initialisierung und Workspace-Schreiben. Vorhandene Trialdaten
werden nicht verändert, keine Marker entfernt. Fehlermeldungen enthalten jetzt
errno und Dateibasename/Funktion/Zeile, keine Exceptiontexte oder Schlüsselwerte.
7 Tests +11 Subtests und PS-Syntax bestanden. Nächster Schritt: Nutzer führt
-Diagnose aus und liefert Ergebnis; erst dann gezielte Rechtekorrektur/Resume.
Hinweis: allgemeiner OpenRouterProvider bleibt ein Dev-Adapter ohne Dateikeyzugriff;
nur der ausdrücklich autorisierte Trial injiziert das systemd-Credential kurz
bei Konstruktion und entfernt es danach aus der Umgebung.

Neue lokale Entwicklung: `checkpoint(memory)` lässt den Agenten eine eigene
Arbeitsübergabe (max.16384 UTF-8-Bytes) als memory.md sichern und nach vollständig
abgeschlossener Toolrunde mit frischem Kontext fortsetzen. Letzter Call der Antwort
erforderlich; Byteverbrauch wird im Request angezeigt. Alte Interaktion bleibt privat
archiviert; keine automatische Zusammenfassung/zusätzliche Modellkosten. Noch kein
Ubuntu-Deployment. Details in 04_ENTWICKLUNGSKERN.md, Tests test_context_checkpoint.py.
Gesamtlauf nach Änderung: 115 Tests +107 Subtests bestanden,3 skips (Linux/Crypto).
Keine echte Inference. Aktueller nächster Schwerpunkt: begrenzten tatsächlichen
Arbeitslauf über OpenRouter vorbereiten/prüfen, danach Ergebnisse und Fortsetzung
beobachten. Noch kein eigenmächtiger Produktionsstart. Alte Unterlagen nennen teils
direkte OpenAI-API; aktueller vorhandener Adapter ist OpenRouterProvider mit
--openrouter-dev, der absichtlich nur KWOD_DEV_OPENROUTER_API_KEY liest.

Deutsch, knapp, praktisch. Nutzer möchte frische Chats nach größeren Etappen gegen
Kontextaufbau, mit kompakter Dateiübergabe statt vollständigem Chat-Fork.
Er hat die weitere Entwicklung autorisiert („arbeite einfach weiter“). Keine
erneuten allgemeinen Bestätigungsfragen. Keine Zahlung allein aus Testfreigaben
ableiten. Keine Nachrichten an Dritte ohne ausdrücklichen Auftrag.

Projekt: autonomer Kunst-Agent soll mit 50 EUR Startvermögen Geld verdienen und
Compute selbst nachkaufen. Später Forschungsagent möglich, aktuell kein Umbauauftrag.
OpenRouter prepaid: Nutzer meldet 40 EUR eingezahlt, keine gespeicherte Zahlungsmethode.
Nicht in USD umrechnen/erfinden. Normale API-Key-Prüfung bestanden, Key gespeichert
rootgeschützt unter /etc/kwod-openrouter/api.key, kein Management-Key. Keine echte
Inference getestet, kein Produktionsworker/Birth-Event, keine Zahlung ausgelöst.
Agent darf nicht auf Hauptcomputer/LAN zugreifen. Schlüssel bleibt isoliert.

## Umgebung

Workspace C:\workspace\projects\keepworkingordie; Code-Unterordner keep-working-or-die.
Keine Git-Repo laut Projekttool. Lokales Python ..\.venv\Scripts\python.exe vom
Codeverzeichnis. PowerShell. Direktes SSH dieser Sitzung funktionierte nicht;
Nutzer führt fertige Deploy/Test-PS1-Dateien selbst aus Windows PowerShell aus.
Keine erneuten SSH-Konfigurations-/Schlüssel-Suchen nötig. Shell-Netzzugriff war
ebenfalls eingeschränkt. Web-Recherche über verfügbare Webtools.

Ubuntu: ssh s340, Benutzer huriet, 192.168.0.118, Ubuntu 24.04.x LTS.
Public observer localhost:8000, Windows Watch-Agent.ps1 Tunnel:8765 funktioniert.
kwod-runtime getrennt; Agent-Docker network=none. Öffentliches SQLite-DB-Rechteproblem
behoben. Node /opt/kwod-wallet/node v24.21.0, npm11.19.0.
Signer /opt/kwod-signer/venv/bin/python enthält eth-account0.14.0; lokale venv nicht.
kwod-signer Dienst offline/AF_UNIX, signing_enabled=false, separate Walletidentität
unter /var/lib/kwod-signer (0700), identity.json0600. Betriebsschlüssel niemals auslesen.
Wallet: 0x939DB49B1EAbB40C8afE5c6a12fB1694a242C5b6, Base8453.
Letzte bestätigte finalized Beobachtung: ETH=0, USDC=0 (kein aktueller Kontostand).
Verschlüsseltes, hashgeprüftes Backup bereits auf Windows-Laptop vorhanden.

## Relevante Implementierung

src/kwod/payments.py: offline ETH/USDC-Transfer-Signer, durable nonce/request journal.
src/kwod/payment_relay.py: interne Transferkoordination, identische Bytes nach
Timeout, Finalität getrennt von Inclusion; Netzwerkadapter/Produktionsanbindung fehlen.
src/kwod/auth_capture.py: strikte Offline-Prüfung des beobachteten x402-Subsets.
src/kwod/auth_capture_signing.py: EIP3009 ReceiveWithAuthorization, nonce bindet
PaymentInfo an Chain/Escrow. AuthorizationJournal speichert Salt/Fristen vor Signatur,
Ergebnis vor Rückgabe, immutable Checkout-ID; abgelaufene unvollständige Freigaben
keine automatische Erneuerung. Nur explizite konsistente Vertragsversionen erlaubt.
Keine Produktions-API-Anbindung dafür. sign_plan ist interner vertrauenswürdiger
Baustein, kein sicherer Endpunkt für beliebige fremde vorbereitete Daten.
Weitere Details docs/payment-relay-status.md (historische Abschnitte beachten).

## Aktueller Zahlungsweg und offene Fragen

Coinbase Checkout für OpenRouter wurde im Browser geprüft: 10,50 USD an OpenRouter,
expliziter x402-Link. Keine Wallet verbunden. MetaMask nicht nötig, Projektkey dort
nicht importieren. Coinbase Agentic Wallet/Electron aufgegeben; eigenes Wallet bleibt.
Unsigned Probe deploy/Check-Checkout.ps1 auf Ubuntu bestanden:
auth-capture, eip155:8453, native USDC0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913,
amount10500000, maxTimeoutSeconds3600, EIP3009 domain USD Coin/version2,
minFeeBps=maxFeeBps100, captureDeadline=refundDeadline1821005089 (15.09.2027 UTC).
Frist für erstmaligen Einzug ist 1h; bereits eingezogene Gelder könnten bis zur
Capture/Reclaim-Frist liegen. 1% wird laut Spezifikation vom Capturebetrag verteilt;
Compute-Gutschrift ist damit nicht nachgewiesen.
Checkout nennt tokenCollector v1.0, aber kein authCaptureEscrow. Aktuelle Spec
defaultet auf v1.1. Nicht raten oder live Requirements eigenmächtig umschreiben.
Automatische Erzeugung neuer OpenRouter Checkouts und Gutschriftabgleich ungelöst;
alte /credits Kauf-API410. Coinbase Business Merchant-API gehört OpenRouter, kein
eigenes CDP-Konto als vermeintliche Lösung. Regulärer OpenRouter-Key liest nicht
den gesamten Accountsaldo. Kein Management-Key dafür vom Nutzer verlangen.

## Tests / letzter Stand

Nutzer hat Test-AuthCapture.ps1 ohne Zusatz auf Ubuntu erfolgreich ausgeführt:
echte Kryptografie mit öffentlichem Testkey1, 11 Mutationen, Restart-Replay passed,
Netz aus, kein Projektschlüssel gelesen, keine Zahlung. Regressionstestwert ist
in tests/test_auth_capture_crypto.py erfasst (kein unabhängiger Clientvektor).
32 lokale Tests/46 Subtests bestanden; Crypto pytest lokal wegen fehlendem Paket skip.

Aktuell unabhängiger Vergleich:
deploy/Test-AuthCapture.ps1 -SshTarget s340 -OfficialClient
packt auth_capture_compare.py, auth_capture_official.mjs plus Pythonmodule.
run_auth_capture_compare.py lädt @x402/evm2.17.0 und2.25.0 unter npm-Aliasnamen sowie
viem2.48.11 in temporären Bereich unter /run, User nobody, ignore-scripts. Danach
Vergleich ohne IP-Sockets, Schlüsselpfade unzugänglich, keine Dienständerungen.
Transitive Pakete nicht produktionsgelockt. Alles nur Testkey1/synthetische Empfänger.
Node Client createPaymentPayload(2, requirements) läuft, Python rekonstruiert mit
dessen Salt/Frist für beide Vertragsversionen und vergleicht vollständiges Payload.

Zwei Nutzerläufe:
1 npm double-loading /dev/null -> behoben durch zwei separate leere Konfigdateien;
   lokaler npm config-Test bestanden.
2 Paketinstallation erfolgreich (18 Pakete), Vergleich scheiterte für2.17.0 mit
   „Official payload does not uniquely match a supported deployment“.
   Die eigentlichen Felddaten wurden leider nicht ausgegeben.

LETZTE ÄNDERUNG bereits fertig: auth_capture_compare.py payload_differences()
vergleicht nur from/to-Adressen case-insensitiv, alle anderen Felder weiterhin
streng. Fehlende/zusätzliche Felder und Zahltypen bleiben Fehler. Beide Versionen
werden nun ausgewertet und bei Fehler werden erwartete/tatsächliche Testwerte pro
Feld/Deployment ausgegeben. 9 Tests/6 Subtests für Vergleich+Journal bestanden.
Adressschreibweise ist nur vermutete Ursache, NICHT bestätigte Lösung.

BESTÄTIGTES ERGEBNIS des erneuten Nutzerlaufs am 15.09.2026:
official_client_comparison=passed. Client2.17.0 entspricht v1.0 und berücksichtigt
den legacy tokenCollector; Client2.25.0 entspricht v1.1 und berücksichtigt diesen
Hinweis nicht. Bei beiden stimmen Nonce und Signatur überein. Nur öffentlicher
Testkey, kein Signaturnetzwerk, Backend nicht verifiziert, keine Zahlungsfreigabe,
kein Workerstart. Die Ausgabe enthält keine vollständigen Payloads; daraus lassen
sich keine unabhängigen Payload-Fixtures rekonstruieren. Kein weiterer Testlauf
nötig, um dieses Ergebnis zu bestätigen. Adressschreibweise bleibt als Ursache
des früheren Fehlers unbewiesen, weil dessen Felddiagnose fehlt.

NÄCHSTER SCHRITT: Backend-Vertragsversion des tatsächlichen Checkouts anhand
belastbarer, unsignierter Informationen klären. Der erfolgreiche Clientvergleich
belegt die lokale Konstruktion für beide Versionen, aber löst den Widerspruch
im Checkout nicht. Die vorhandene Sperre explicit_consistent_deployment_required
bleibt bestehen. Keine Live-Requirements umschreiben oder aus dem Clientverhalten
eine Zahlungsfreigabe ableiten. Backend-Akzeptanz und Compute-Gutschrift bleiben offen.

Fortsetzung: Offizielle Coinbase-Anleitung und aktuelle Scheme-Spec erneut gelesen.
Spec bestätigt v1.1-Default, Coinbase dokumentiert keine sessionspezifische Version.
Keine belastbare Zuordnung des tatsächlichen Backends gefunden. Checkout-URL fehlt
in der Übergabe; im aktuellen Chat per Eingabefeld beim Nutzer angefragt. Sobald sie
vorliegt, vorhandene unsignierte Probe/Browserprüfung nutzen; keine neue Signaturprobe.
Details und Grenzen im neuesten Abschnitt von docs/payment-relay-status.md.

AKTUELLER NACHTRAG: Nutzer hat Checkout-Link geliefert, gespeichert in
docs/checkout-observation-2026-09-15.json zusammen mit unveränderten Requirements.
Direkte lokale Probe funktionierte nach Netzwerkfreigabe für diesen Turn (SSH
weiterhin nicht geprüft). Antwort weiterhin legacy v1.0-Collector ohne Escrow;
Offline-review bestätigt collector_conflicts_with_resolved_escrow. Keine Signatur,
keine Zahlung. Link nicht erneut erfragen und Probe nicht ohne Anlass wiederholen.
Clientvergleich abgeschlossen; offene externe Frage bleibt die verbindliche
Backend-Version für diese Session. Keine weitere lokale Kryptografiekorrektur
aus diesem Ergebnis ableitbar. Keine Nachricht an Coinbase/OpenRouter autorisiert.

Nutzer sagte anschließend „Los geht“ zur weiteren Klärung. Offizielle Supportadresse
support@openrouter.ai über OpenRouter-FAQ verifiziert; kein veröffentlichter Fix in
den durchgeführten Suchen gefunden. Fertige private Support-Anfrage mit Session-Link,
beiden Client-Ergebnissen und drei konkreten Fragen liegt unter
docs/openrouter-x402-support-request.md. Noch NICHT versendet; kein E-Mail-Connector
verfügbar. Keine Zahlung und kein Agentenstart. Nächster Schritt: Versand über das
OpenRouter-Konto des Nutzers bzw. dessen E-Mail und anschließend Antwort auswerten.

## Primärquellen

https://docs.cdp.coinbase.com/coinbase-business/checkout-apis/accept-x402-payments
https://github.com/x402-foundation/x402/blob/main/specs/schemes/auth-capture/scheme_auth_capture_evm.md
https://github.com/x402-foundation/x402/blob/main/typescript/packages/mechanisms/evm/src/auth-capture/nonce.ts
https://openrouter.ai/docs/cookbook/administration/crypto-api

Webcache lieferte teils unterschiedliche Quellstand-Daten. Offizieller Clientvergleich
soll Vermutungen über diese Versionsunterschiede durch tatsächliche Tests ersetzen.
