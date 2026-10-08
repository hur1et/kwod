> AP1-Update 16.09.2026: Nutzer bestätigt erfolgreiche Ubuntu-Installation dev-20260916-112800-6da3e1a0. Nächster Schritt: Monitoranzeige und einmaliger kostenloser OfflineCheck mit Stop-/Wiederholungsprüfung gemäß docs/work-monitor.md. Keine bezahlten Piloten neu starten.

> Fortschritt AP1, 16.09.2026: Laufkarten/Collector und Work-Run.ps1 (Status/Stop/Start) lokal implementiert. Gesamtlauf 145 Tests + 120 Subtests, 3 skips; abschließende Statushärtung danach mit 16 Tests + 11 Subtests geprüft. Ubuntu-Abnahme bleibt offen. Einstieg: keep-working-or-die/reports/ap1-status-2026-09-16.md und docs/work-monitor.md. Vorbereiteter separater OfflineCheck ohne Credential/Netzwerk; echte Piloten nicht erneut starten. Deployment und OfflineCheck wurden hier nicht auf Ubuntu ausgeführt. AP2 kann lokal folgen.

> Fortschritt 16.09.2026: AP0 lokal abgenommen. Aktueller Gesamtlauf: 133 Tests + 118 Subtests bestanden, 3 skips, Exitcode 0. Nachweise: keep-working-or-die/reports/ap0-status-2026-09-16.md und reports/arbeitspakete.md. Nächster Einstieg AP1, danach AP2; ältere AP0-Aufforderungen unten sind erledigt.

# AP4-Update 16.09.2026: Planung korrigiert. Der Agent soll Nachfrageprüfung selbst entwickeln; unser Dokument enthält nur Sicherheitsgrenzen und leere Auswertung, keinen vorgegebenen Leitfaden. Ein selbstständiger Agentenversuch ist offen; Scheitern gilt als gültiges Ergebnis. Keine Betriebe gesucht/angeschrieben; contact_authorized=false.

# KEEP WORKING OR DIE — kompakte Übergabe
Stand: 16.09.2026. Diese Datei ist der aktuelle Einstieg.

## Aktueller Nutzerauftrag
Konkreter überprüfbarer Arbeitsplan mit Paketen/Zeiten und neuer Chat zum Kontext-
sparen. Plan erstellt: keep-working-or-die/ARBEITSPLAN.md. Abnahmen führen in
keep-working-or-die/reports/arbeitspakete.md. Im neuen Chat mit AP0 beginnen, danach
AP1/2. Keine weiteren beliebigen Schreibpiloten. Alte Payment-Arbeit zurückgestellt.

## Ziel
Kunstprojekt: ein Agent soll mit 50 EUR realem Startvermögen Geld verdienen und
Compute selbst nachkaufen. Noch keine Produktionsgeburt, keine Einnahmen. Erstes
Zwischenziel: begleiteter echter Auftrag; langfristig selbstständige Wirtschaft.
Deutsch, knapp, praktisch. Reversible Entwicklung ist autorisiert. Keine erneuten
allgemeinen Bestätigungsfragen. Externe Nachrichten, Zahlungen und Produktionsstart
brauchen konkreten Auftrag; bislang keine Kundenansprache autorisiert.

## Umgebung
Workspace C:\workspace\projects\keepworkingordie; Code in keep-working-or-die.
Kein Git laut Projekttool. Python .venv\Scripts\python.exe im Workspace, eine Ebene
über Code. Ubuntu24.04 auf s340/huriet,192.168.0.118. Nutzer führt fertige PS1-Skripte
mit SSH/sudo aus; direkter SSH-Zugang dieser Sitzung bisher nicht nutzbar. Nicht
wieder Schlüssel/SSH-Konfiguration suchen. Hauptrechner/LAN für Agent tabu.
Ubuntu /opt/kwod/current/.venv/bin/python, Runtime und öffentlicher Leser getrennt.
Monitor vorhanden, aber zeigt bisher Hauptinstanz und keine Piloten. Kein Worker-
Dauerbetrieb. OpenRouter-Key rootgeschützt /etc/kwod-openrouter/api.key; nie ausgeben.

## Funktionierender Kern
Persistente SQLite-/Archiv-Runtime, Dateiwerkzeuge, netzloser Containerexecutor,
Sleep/Wake, Backup/Restore, separate öffentliche Projektion, OpenRouter Responses-
Adapter. Modell openai/gpt-6-astra; nur OpenAI-Routing, Fallbacks aus. Routeradapter
entfernt service_tier/parallel_tool_calls; Runtime führt Tools seriell aus.
Checkpoint-Werkzeug schreibt memory.md (max16384 UTF-8-Bytes) und setzt frischen
Kontext nach abgeschlossener Toolrunde; alter Kontext privat archiviert. Muss letzter
Call einer Antwort sein. Trial zeigt tatsächliches Restbudget inkl Fehlversuchen.

## Reale Läufe / nicht erneut starten
Trial01: /var/lib/kwod-work-trial-01. Erster Versuch404, danach5 completed in33s.
Entwurf „Restlaufzeit“, Beschreibung, memory vorhanden, Review fehlt; Budget6 erschöpft.
Nutzer unterbrach Launcher; Dienst später per StopAndInspect bestätigt beendet.
Pilot02: /var/lib/kwod-work-pilot-02.5 Aufrufe,1 Handoff,alle5 Dateien,completed/idle,
1 Aufruf ungenutzt. Agent wählte FAQ-/E-Mail-Paket für Fahrradwerkstätten, fiktive
Arbeitsprobe,89EUR-Preishypothese und konkrete Selbstkritik. Texte vom Nutzer gelesen.
Kein Käuferfeedback/Verkauf. Selbstprüfung sagt Dateien im frischen Kontext gelesen;
vollständiger Ereignistrace noch nicht separat kontrolliert.
Original: reports/pilot-02/originalausgabe.txt. Assistentenüberarbeitungen ausdrücklich
separat: auswertung.md,arbeitsprobe-geprueft.md,nachfragetest.md. Keine Kundenkontakte.

## Kosten — aktuelle Nutzerangaben
Trial01 0,09USD. Pilot02 Saldo39,91→39,60USD =>0,31USD; beide zusammen0,40USD.
Pilot02-Zuordnung gilt unter Annahme keines anderen Verbrauchs/keiner Korrektur.
Letzter gemeldeter Saldo39,60USD ist nicht live geprüft. Früher40EUR eingezahlt laut
Nutzer; keine Währungsumrechnung erfinden. Quellen docs/work-trial-cost-observation.json
und docs/pilot-02-cost-observation.json. Noch keine zusätzliche Ledgerbelastung.

## Launcher und Fehlerhistorie, nur bei Bedarf
Test-WorkTrial.ps1: Standard Trial01; -Pilot wählt Pilot02, -StopAndInspect stoppt/
liest gewählten Lauf. -Diagnose offline Rechteprüfung, -CheckProvider nur Metadaten.
-ResumeUnstarted/-ResumeRejected waren eng begrenzte einmalige Reparaturen für Trial01;
jetzt NICHT erneut verwenden oder Marker löschen. Haupt-/Pilot-Daten getrennt.
DynamicUser,LoadCredential,keine Shell/Payment-Tools im Trial. workspace_shared=False
setzt700/600 ohne setgid (RestrictSUIDSGID verhinderte2770). IP-Sperren numerisch;
127.0.0.53 nur DNS-Ausnahme. Ctrl+C stoppt Dienst vor Quellenbereinigung. Reststatus
bei Netzabbruch stets prüfen, keine Wiederholung unklarer Modellaktionen.

## Tests / Grenzen
Letzter gesamter lokaler Lauf historisch115 Tests+107 Subtests,3 skips; spätere
Änderungen nur gezielt geprüft, zuletzt17 Tests+11 Subtests (Pilotprofiles).
AP0 soll aktuellen Gesamtlauf liefern. Nicht historische Zahl als aktuellen
Gesamtstand ausgeben. Linux-Isolation/Langzeittest/Restore-Abnahme noch zusammenführen.
Kein unkontrollierter neuer paid trial, keine neue Plugininstallation nötig.

## Plan und Zeitschätzung
AP0–6:27–44 aktive Stunden plus24h Offline-Lauf und Kundenwartezeit; StufeA grob
2–3 Wochen bei4–6 produktiven Stunden/Tag und zeitnahen Rückmeldungen.
AP7–9 zusätzlich16–28h; gesamt43–72h, grob3–5 Wochen bei geklärten externen Fragen.
Keine Kalenderzusage für autonome Nachladung: Backend/Gutschrift ungeklärt.
Arbeitsplan enthält Ergebnisse, Abnahmen, Abhängigkeiten und Entscheidungen.

## Zurückgestelltes Payment
Wallet eingerichtet/Backup vorhanden, Signing deaktiviert. Offline Signaturtests und
Vergleich mit x4022.17.0(v1.0)/2.25.0(v1.1) bestanden. Coinbase-Checkout nennt alten
Collector ohne Escrow; Backend-Version/Gutschrift ungeklärt. Keine Zahlung.
Supportentwurf NICHT versandt. Nicht als aktuellen Blocker für AP0–7 behandeln.
Details nur bei Bedarf docs/payment-relay-status.md und historische Übergabe
reports/handoff-history-2026-09-16.md. Alte Root-Dokumente enthalten überholte Aussagen;
aktueller Plan/kompakte Übergabe haben Vorrang als Statusquelle.




## Ubuntu-Fixture bestätigt und Tunnelkorrektur (16.09.2026)

Nutzer meldet OfflineCheck completed: drei simulierte Anfragen vom 16.09.2026 11:34:43 bis 11:35:28 UTC, real_model_calls=0; Runtime idle/turn_completed, vier abgeschlossene Toolcalls, alle vier erwarteten Dateien vorhanden. Nachfolgender Stop meldet stopped_or_not_running. Damit sind regulärer Ubuntu-Fixture-Abschluss und Statusinspektion belegt, nicht der Stop während laufender Arbeit. Marker erhalten; OfflineCheck nicht zurücksetzen.

Watch-Agent.ps1 kehrte laut Nutzer sofort zum Prompt zurück. Ursache nicht unabhängig festgestellt (Hintergrund-/Multiplexing-Konfiguration ist eine mögliche Erklärung). Lokal korrigiert: ssh.exe explizit als Anwendung, ForkAfterAuthentication=no, ControlMaster=no, ControlPath=none, ControlPersist=no; Warnung bei auch erfolgreichem SSH-Ende. PowerShell-Parser und offline gemockter Aufruf einschließlich Loopback-Ziel und Endewarnung bestanden. Kein erneutes Ubuntu-Deployment dafür nötig, nur lokales Skript erneut ausführen. Monitoranzeige und aktiver Stopnachweis bleiben offen.
