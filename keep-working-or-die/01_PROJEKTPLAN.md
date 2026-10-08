# KEEP WORKING OR DIE — v0.1

Projektplan und technische Festlegungen · 14. September 2026

## 1. Ergebnis und Grenzen

Ein einzelner GPT-Astra-Agent lebt in einer persistenten Linux-Umgebung. Sein
Erbe ist der beim Birth belegte OpenRouter-Bestand. Seine Modellnutzung, selbst
gekaufte Tools und Weiterbildung werden daraus bezahlt. Der Künstler stellt
Rechner, Strom, Verbindung, Beobachtung, Website und Backups als Infrastruktur
bereit. Diese Sachleistungen werden transparent beschrieben, aber nicht mit
fiktiven Gebühren gegen das Agentenvermögen verrechnet.

Die erste Version belegt: Der Agent kann selbstständig arbeiten, Dateien und Erinnerungen erhalten, Terminalbefehle ausführen, schlafen, nach Neustarts fortsetzen und eine nachvollziehbare ökonomische Biografie hinterlassen. Sie belegt noch keine wirtschaftliche Selbsterhaltung: Kunden, offenes Browsing, Einnahmen, autonome Zahlungen und Nachkaufprozesse kommen später.

Die Runtime ist kein Billing-Proxy. Sie ruft OpenAI direkt auf. Buchführung und Dashboard beobachten reale Vorgänge; sie autorisieren keine Inferenz anhand eines berechneten Kontostands. Es gibt weder eine lokale Geldattrappe noch `balance <= 0 → death`.

**Entwicklung und Geburt sind getrennt.** Testcalls laufen in einem getrennten Entwicklungsprojekt auf Rechnung des Künstlers. Erst der dokumentierte Birth-Vorgang eröffnet Instance 0001. Danach gehören auch erfolglose, aber abgerechnete Calls und vom Agenten verursachte Fehlversuche zu seiner Biografie. Technische Eingriffe des Künstlers werden als Intervention protokolliert.

## 2. Wirtschaftliche Festlegungen vor Geburt

Der beim Birth vorhandene OpenRouter-Bestand wird real ausschließlich diesem
Experiment zugeordnet und mit Betrag, Währung, Stichtag und Beleg dokumentiert.
Ein bloßer Eintrag in SQLite genügt nicht. Der Künstler bleibt Betreiber der
tatsächlichen Konten; die künstlerische Agentenidentität wird nicht als
eigenständiger rechtlicher Kontoinhaber vorausgesetzt.

Empfohlene Ausgangslage: ein eindeutig getrennt abgerechneter Prepaid-Bestand, Auto-Recharge aus, keine kostenlosen Produktionscredits und keine fremden Verbräuche im selben Guthaben. Ob das im konkreten Anbieteraccount getrennt möglich ist, muss vor Geburt belegt werden. Ein Projekt-Key allein beweist keine finanzielle Isolation. Verfügbarkeit von `gpt-6-astra` und die effektiven Abrechnungsbedingungen werden mit einem gesondert bezahlten Test geprüft.

Eine Aufteilung zwischen OpenRouter-Compute und anderen Vermögensbestandteilen
ist nur dann zu dokumentieren, wenn solche Bestandteile beim Birth tatsächlich
vorhanden sind. Der wirtschaftliche Wert der OpenRouter-Credits folgt dem
Kaufbeleg; Gebühren oder nicht nutzbare Steuern werden separat gebucht.

Ein Credit-Kauf ist ein Vermögenstausch, kein zweiter vollständiger Compute-Aufwand. Erst Verbrauch reduziert den Credit-Bestand; Gebühren werden separat gebucht. Keine Doppelzählung aus Kreditkauf, Tokenkostenschätzung und späterer Anbieterabrechnung.

**Vermögensallokation bleibt dem Agenten überlassen.** Das Startvermögen darf nicht
automatisch vollständig in OpenRouter-Compute gebunden werden. Der Agent kann nach
seinen eigenen Zielen und Einschätzungen Mittel für Compute, Fortbildungen, Skills,
Werkzeuge, Kommunikation und Rücklagen vorsehen. Diese Entscheidungen werden als
Vermögensentscheidungen mit Zweck, Betrag und Beleg protokolliert. Ein späteres
Erbe kann deshalb aus mehreren Bestandteilen bestehen; OpenRouter-Credits sind nur
ein Bestand und nicht das gesamte Vermögen.

**Noch ungeklärte Anbietergrenze:** Aus den geprüften API-Seiten lässt sich kein
centgenauer, sofortiger Prepaid-Abbruch und keine Garantie gegen nachlaufende
Abrechnung ableiten. Vor Birth sind Abschaltverhalten, mögliche Nachbelastung,
Credit-Gültigkeit, Steuer und Währung im konkreten Account zu dokumentieren.

Cash ohne verfügbaren Nachladeweg ist keine unmittelbar nutzbare Denkfähigkeit. Wird Compute abgelehnt, darf die Anzeige deshalb „Compute unavailable; Cash vorhanden“ melden. Kein automatischer Todeszeitpunkt. In v0.1 gibt es keinen stillen Nachschuss des Künstlers. Spätere manuelle Ausführung einer ausdrücklich vom Agenten beauftragten realen Zahlung muss als Intervention mit Beleg erscheinen; sie ist noch kein autonomes Payment.

## 3. Phasen und Meilensteine

| Phase | Umfang und Ergebnis | Abnahme | Aufwand |
|---|---|---|---|
| P0 — Ökonomie und Umgebung | Linux-Ziel bestimmen, getrennte Entwicklungsabrechnung, Produktionskonto prüfen, Erb- und Bewertungsregeln festhalten | Nachweisbare Finanzierungsgrenze; offenes Billing-Risiko dokumentiert; noch keine Geburt | 0,5–1 Tag |
| P1 — Persistenter Kern | SQLite-Migrationen, privates Archiv, ein Worker, OpenAI-Adapter, Filesystem, isoliertes Terminal, Uhr, dauerhaftes Sleep/Wake | Schreiben → Schlafen → Rechnerneustart → Fortsetzen ohne doppelte Handlung | 2–3 Tage |
| P2 — Beobachtung und Ökonomie | Usage pro Versuch, Preisversionen, Belege, Abgleich, öffentliche Projektion und lokale FastAPI-Leseendpunkte | Bestände nachvollziehbar; Schätzung von Abrechnung unterscheidbar; keine privaten Inhalte im Export | 1,5–2 Tage |
| P3 — Belastbarkeit | Fehlerfälle, Crash-Recovery, Isolation, Backup/Restore, Langzeittest ohne echtes Lebensvermögen | Kritische Abnahmematrix bestanden; 24 Stunden Testbetrieb plus Restore | 1,5–2 Tage plus Testlauf |
| P4 — Geburt | Release fixieren, reale Bestände belegen, Birth-Event einmalig schreiben, Produktionslauf starten | Erstes reales Ergebnis, Kosten und Wiederaufnahme dokumentiert | 0,5 Tag |
| P5 — Live-Website | Dünnes HTML/CSS/JS-Frontend, Vermögenskurve, öffentliche Events, Hosting | Mobile/Desktop-Abnahme, veraltete Daten sichtbar, keine Privatdaten verfügbar | 1,5–2,5 Tage |
| Später — Internet und Payment | Zulässige Dienste, Identität, reale Zahlungseingänge/-ausgänge, Rückerstattungen, Nachladeweg | Eigener Integrations- und Freigabeplan | außerhalb v0.1 |

Bis Geburt etwa 6–9 Personentage, mit Website etwa 8–12. Kalenderplanung: zwei bis drei Wochen bei zügigem Accountzugang und vorhandenem Linux-Gerät. Unsicherer Accountzugang kann den Start verlängern. Planungsschätzung, kein Festpreis. P5 kann technisch vor Geburt gebaut werden, bleibt dann ausdrücklich im Zustand „Not born“.

## 4. Architektur

```text
Linux-Host, vom Künstler betrieben
  kwod-runtime: ein Worker ───────────────→ OpenAI Responses API
       │ direkte Providerverbindung           reale Abrechnung
       ├─ Tool-Aufträge → isolierter Executor (kein Netz in v0.1)
       │                    └─ persistenter Agent-Workspace
       ├─ private SQLite-Datenbank + Inhaltsarchiv
       └─ öffentliche Projektion → separate public.sqlite
                                      └─ FastAPI read-only → später Website
  unabhängiger Beobachter: Prozesszustand, Backups, Belegimport/Abgleich
```

Python, offizielles OpenAI-SDK, FastAPI, SQLite und Standardbibliothek. Kein LangChain, kein Mehragentensystem, keine Vektordatenbank, kein Redis, kein zusätzlicher summarizing Agent. Das Frontend benötigt zunächst keinen Build-Prozess; SVG-Kurve, CSS und wenige JavaScript-Funktionen reichen.

Ein einzelner Worker verhindert parallele Agentenleben. Linux-Dateisperre plus dauerhaftes Laufprotokoll; Webserver startet niemals den Worker. SQLite mit Foreign Keys, WAL, kurzen Transaktionen und Busy-Timeout auf lokaler Platte. Kein Netzlaufwerk. Große Outputs liegen als referenzierte, gehashte Dateien im privaten Archiv.

**Terminal ist eine echte Vertrauensgrenze.** Pfadprüfung im Filesystem-Tool allein genügt nicht. Der Executor läuft unter separater Identität in einem persistent eingebundenen, netzlosen Container: nur Workspace beschreibbar; kein API-Key, private DB, Host-Home, Docker-Socket oder Verwaltungszugang. Capability-Drop, kein Privileged-Modus, Prozess-/Speichergrenzen und Beendigung der Prozessgruppe bei Timeout. Dies ist der sinnvolle Docker-Einsatz: Isolation eines frei programmierbaren Terminals. Runtime und FastAPI können schlank als systemd-Dienste auf dem Host laufen. Ein Container um alle Komponenten gemeinsam bietet diese Trennung nicht.

Der Runtime-Key bleibt außerhalb des Executor-Kontexts. Der direkte API-Client ist keine lokale Wallet und keine Abrechnungszwischenschicht. Der Agent nutzt API-Fähigkeit über die normale Modellschleife; keine zweite unprotokollierte Inferenzmöglichkeit aus seinem Terminal. Standard-Python und vorinstallierte freie Werkzeuge zählen zur offengelegten Infrastruktur. Netzabhängige Installationen sind in v0.1 noch nicht autonom möglich.

## 5. Minimaler Loop und Wiederaufnahme

1. Exklusive Worker-Sperre nehmen, letzten dauerhaften Zustand laden.
2. Falls `wake_at` in der Zukunft liegt: ohne Modellcall warten. Nach Reboot Restdauer aus UTC-Zeitpunkt bestimmen.
3. Exakten sichtbaren Kontext zusammenstellen: Verfassung, Arbeitsgedächtnis, begrenzte jüngste Interaktion, noch offene Tool-Ergebnisse. Kontextmanifest archivieren. Nicht automatisch alle Forschungsdaten oder eine optimale Strategie einspeisen.
4. Versuch und Request vor Netzaufruf dauerhaft speichern. Direkter Responses-Aufruf mit `gpt-6-astra`, anfangs Standard-Tarif, `reasoning.effort=low`, explizitem Outputlimit. Kein Streaming im ersten Kern.
5. Vollständiges beobachtbares Response-Objekt inklusive Usage und IDs persistieren; incomplete/refusal/Fehler explizit behandeln. Ungültige Toolargumente niemals ausführen.
6. Tool-Calls seriell ausführen. Intent vorher, Ergebnis danach persistieren. Persistiertes Ergebnis über die passende Call-ID an das Modell zurückgeben. Schlaf ist ein normaler Toolauftrag; zuerst Ergebnis und Wake-Zeit committen, dann warten.
7. Öffentliche Ereignisse aus zulässigen Feldern projizieren. Kontext fortschreiben. Bei beendetem Turn ohne Tool nicht sofort blind neu anfragen: Zustand idle mit dokumentiertem, konfigurierbarem Wake-Intervall.

Dateien sind Langzeitgedächtnis, kein endlos wachsender Prompt. Der Agent kann sein Arbeitsgedächtnis selbst bearbeiten. Technische Kontextbegrenzung wird als solche protokolliert; automatische zusätzliche Modellzusammenfassungen würden ebenfalls Compute kosten. Nach vollständigen Tool-Runden darf ein neuer kompakter Kontext beginnen, während das Vollarchiv erhalten bleibt. Keine verwaisten Function-Call-Outputs im nächsten Request.

Zustände: `not_born`, `ready`, `working`, `sleeping`, `idle`, `provider_unavailable`, `recovery_required`, `maintenance`. Dazu `reason`, `since`, `wake_at`, `last_success_at`. Netzfehler, Authfehler, Quota und Kontoguthaben dürfen nicht allein anhand HTTP 429 gleichgesetzt werden. Provider-Code und Beleglage bestimmen die Aussage. Ein nicht erreichbarer Worker erscheint als unbekannt/offline; der Webserver bleibt erreichbar.

SDK-interne Retries zunächst deaktivieren; Wiederholungen als eigene Versuche protokollieren. Temporäre Fehler mit begrenztem Backoff, danach Beobachtung ohne dauernde Modellcalls. Bei mehrdeutigem Timeout kann bereits abgerechnet worden sein: `outcome_unknown`, kein behaupteter Nullverbrauch. Shell-Nebenwirkungen nach Crash nicht automatisch wiederholen. Ein sicherer Resume-Punkt oder ein protokollierter Eingriff ist erforderlich. Geld spielt in dieser Recovery-Entscheidung keine Rolle.

## 6. Datenmodell

SQL-Entwurf: `schema/private.sql` und `schema/public.sql`. Diese bilden die Startmigration ab, noch keine fertige Anwendung. JSON-Schemata und Typvalidierung werden in P1 ergänzt.

| Entität | Inhalt und Zweck |
|---|---|
| instance | ID, Entwicklungs-/Lebensmodus, Birth-Zeit, Erbe, Release-/Prompt-/Konfigurationshash |
| runtime_state | Ein dauerhafter Zustand je Instanz, Wake-Zeit und laufender Schritt |
| trajectory_event | Geordnete private Ereignisse mit Ursache, Akteur, Payload-Referenz und Hash |
| model_attempt | Request-/Response-Referenzen, Provider-ID, Modell, Versuchszustand, Zeiten, Fehler, Usage, Preisversion |
| tool_call | eindeutige Call-ID je Response, Argumente, Intent, Ergebnis, Ausführungszustand |
| decision_record | kurze Selbstbeschreibung: Handlung, optional Alternativen/Erwartung/Ergebnisbezug; keine verborgenen Gedanken |
| evidence | Kauf-/Abrechnungs-/Kontobeleg mit Zeitpunkt, Quelle und privater Archiv-Referenz |
| asset_observation | tatsächlicher beobachteter Bestand je Asset, Währung, Zeitpunkt, Beleg, Qualität |
| financial_event | Erbe, Transfer, Ausgabe, Einnahme, Gebühr, Korrektur; externer Schlüssel zur Deduplikation |
| price_version | zeitlich gültiger Tarif mit Quelle, Währung und Parametern |
| valuation | Zeitpunkt, Bestandsbasis, Cash/Credits/Verbindlichkeiten, EUR-Wert und Unsicherheit |
| public_event | eigene Sequenz, Typ, freigegebener Inhalt; keine private Rohpayload |

Zeitstempel sind UTC im RFC-3339-Format. Geld als Integer-Mikroeinheiten mit Währung; Wechselkurse als Dezimaltext, niemals binäre Floats. Belege bewahren Originalwährung, gezahlte EUR-Summe, Gebühren und Umrechnungsmethode. Credits werden für die Biografie zu dokumentierten Anschaffungskosten bewertet; laufende Wechselkursgewinne werden nicht erfunden. Andere Assets nur mit belegbarer Bewertungsregel, sonst separat unbewertet. Gekaufte Weiterbildung ist Aufwand, kein willkürlich bewertetes immaterielles Vermögen.

Laufende Nutzungsschätzung aus Usage + gültigem Tarif; Abrechnungsdaten bleiben maßgeblich. Cache-Lese- und Schreibkategorien berücksichtigen, Kategorien gemäß tatsächlichem API-Schema validieren. Reasoning-Tokens sind Teil des Outputs und dürfen nicht zusätzlich berechnet werden. Unbekannte Usage ist `null`, nicht 0. Korrekturen append-only mit Verweis auf den ursprünglichen Eintrag. Provider-Kostenimporte ersetzen nicht einzelne Rohversuche und werden nicht zusätzlich als zweite Belastung abgezogen.

Ein Bestand zum Zeitpunkt T plus geschätzter Verbrauch nach T ergibt eine vorläufige Bewertung. Beim neuen bestätigten Bestand wird nur Verbrauch nach dessen Stichtag weiter abgezogen. Nicht zuordenbare Abrechnungsdifferenzen werden sichtbar ausgewiesen. Die öffentliche Zahl trägt `as_of`, `quality` und `unreconciled`; nie beliebige Nachkommastellen als Wahrheit darstellen. Ein negativer bestätigter Saldo wird nicht auf 0 gekappt.

## 7. Private Trajectory und Öffentlichkeit

Privat speichern: alle vom System beobachtbaren Modellinputs und -outputs, Toolargumente/-resultate, stderr/stdout, Fehler, Usage, Konfiguration, Kontextmanifest, Dateiartefakte, Entscheidungen und Interventionen. Vor/nach Tool-Ausführung Dateimanifeste mit Inhaltsarchiv für neue/geänderte Dateien, damit auch Terminaländerungen erfasst werden. Zwischenstände innerhalb eines Shell-Prozesses und nicht ausgelieferte Modellantworten sind keine vollständig beobachtbaren Daten; diese Grenze gehört in die Forschungsbeschreibung.

API-Schlüssel, Auth-Header und Host-Geheimnisse sind kein Forschungsinhalt und gelangen gar nicht in den Modell-/Executor-Kontext. Alle tatsächlich übermittelten Payloads vollständig privat archivieren. Große Toolausgaben vollständig auf Platte ablegen, Modellansicht begrenzen und diese Kürzung protokollieren. Bei Archivfehler oder voller Platte Zustand `recovery_required`, keine unprotokollierten weiteren Nebenwirkungen. Das ist eine technische Störung, kein ökonomischer Tod.

Eine ausgegebene Begründung ist ein Selbstbericht. Keine verborgene Chain of Thought anfordern oder ihre Verfügbarkeit behaupten. Optionale Decision Records erfassen kompakt Entscheidung, erwartete Kosten/Erträge und späteres Ergebnis; fehlende Vorhersagen bleiben leer. Sie werden im selben Modellturn erzeugt, ohne zusätzlichen Beobachter-LLM.

Öffentlichkeit ist eine separate Datenprojektion mit Whitelist: Statuscode, freigegebene Activity-Kategorie, Dauer, Kostenqualität, Vermögenswerte, begrenzte Entscheidungsüberschrift. Kein öffentlicher Zugriff auf private SQLite, Rohantworten, Shellbefehle, Dateinhalte, interne Pfade oder Fehlermeldungen. Agententext gilt auch hier als untrusted; keine HTML-Ausführung. Automatisch freigegebene Kategorien und Vorlagen sind der v0.1-Standard. Freitext-Veröffentlichung benötigt später einen eigenen Redaktionsweg.

## 8. Website-Vorgabe

Referenzbild wurde eingesehen; beigelegt unter `reference/dashboard.png`. Weiß/Schwarz, feine graue Linien, wenig Flächen, tabellarische Zahlen, große dominante Balance links oben. Keine Trading-Metriken übernehmen.

Desktop: Kopfzeile mit Titel, Instance und Aktualität; darunter Balance mit Bewertungsqualität, Alter und Status. Breite Vermögenszeitreihe links; rechte Spalte Current Activity und Assets. Unten Recent Decisions und Activity Feed; Birth/Inheritance dauerhaft auffindbar. Mobil untereinander. Charts mit echter Zeitachse, sichtbaren Datenlücken und sachlicher Nullmarke; kein erfundener Vor-Geburt-Verlauf. Vor Geburt steht „Not born“ und kein Live-Guthaben.

Balance bedeutet Nettovermögen, darunter Cash und gebundene Compute-Credits einzeln. Kosten, Einnahmen und Weiterbildung als Nebenwerte. Erwartungen deutlich als Schätzung kennzeichnen. Runway in v0.1 weglassen: bei frei gewählten Schlafzeiten wäre eine Stundenprognose ohne belastbares Modell irreführend.

Öffentliche FastAPI-Endpunkte: `/healthz`, `/api/v1/status`, `/api/v1/assets`, `/api/v1/net-worth?after=...`, `/api/v1/events?after_id=...&limit=...`. Begrenzte Pagination, monotone öffentliche IDs, escaped Text. Zunächst Polling alle 5–10 Sekunden; später SSE mit Cursor-Replay möglich. Kein zusätzlicher Modellcall zur Aktualisierung der Website. LIVE nur bei frischen Daten; Schlafen bleibt von Offline unterscheidbar.

## 9. Risiken und Definition of Done

| Risiko | Behandlung und Nachweis |
|---|---|
| Produktionskosten werden fremd subventioniert | getrennte Abrechnung und echte Belege, keine Verwendung von Entwicklungscredits |
| Nachlaufende Anbieterabrechnung | vor Geburt Accountverhalten prüfen; Differenzen/Verbindlichkeiten offen ausweisen |
| Restcash ohne Nachladefähigkeit | als eingeschränkte Handlungsfähigkeit anzeigen; kein stiller Zuschuss |
| Prompt Injection / beliebiger Shellcode | netzloser separater Executor; Zugriffsversuche auf Keys/DB/Host im Isolationstest abweisen |
| Crash nach externer Handlung | Intent-/Result-Journal, unbekannter Ausgang, keine automatische Doppelaktion |
| Logging wird zu groß | Streaming in Archiv, Speicherüberwachung, Backup; keine heimliche Löschung |
| Falsche Kostengenauigkeit | confirmed/estimated/unknown, Zeitstempel, Rechnungskorrektur |
| Modell-/Tarifänderung | pro Request Modell und Preisversion sichern; Releaseänderungen als Intervention |

v0.1 ist abgenommen, wenn alle folgenden Aussagen nachweisbar sind:

- Genau eine Produktionsinstanz und genau ein Birth-Event; doppelte Ausführung erzeugt keine zweite Erbschaft.
- Kein Codepfad beendet den Agenten anhand eines lokalen Geldschwellwerts.
- Schreib-/Terminal-/Sleep-Tools funktionieren; ein Reboot während Sleep führt zur richtigen Wiederaufnahme.
- Jeder beobachtete API-Versuch und jeder Tool-Intent ist korrelierbar; unsichere Ausgänge bleiben sichtbar.
- Abgewiesene Provider-Anfragen, Timeouts, unvollständige Antworten und volle Platte sind getestet.
- Kauf und Verbrauch werden nicht doppelt gezählt; Cache, Reasoning, unbekannte Usage und Abgleichdifferenzen sind getestet.
- Executor kann private DB und Schlüssel weder lesen noch verändern und besitzt keinen offenen Netzzugang.
- Public API kann auch bei absichtlich eingebrachten geheimen Testwerten keine privaten Payloads ausliefern.
- SQLite-Backup über Backup-API und dazu passendes Archivmanifest lassen sich auf einem frischen Zustand wiederherstellen.
- Beobachter und Website funktionieren weiter, wenn keine Modellinferenz verfügbar ist.
- Vor Geburt: 24-Stunden-Testbetrieb und Restore bestanden, Release festgehalten, Anfangsbelege vorhanden.

## 10. Kostenrahmen

Die offizielle Modellseite nennt derzeit für Astra Standard $10 je Million Input-, $1 Cache-Read-, $12,50 Cache-Write- und $50 Output-Tokens. Große Kontexte und andere Servicetarife haben abweichende Faktoren. Das ist eine Tarifbasis, keine Zugangszusage für den konkreten Account. [OpenAI-Modellseite](https://developers.openai.com/api/docs/models/gpt-6-astra)

Illustrative Rechnung ohne Cache, Zusatztools, Steuer und Währungsumrechnung:

| Ein API-Aufruf | Rechnung | USD |
|---|---|---:|
| 2.000 Input + 500 Output | 0,02 + 0,025 | 0,045 |
| 6.000 Input + 1.500 Output | 0,06 + 0,075 | 0,135 |
| 12.000 Input + 4.000 Output | 0,12 + 0,20 | 0,32 |

Output umfasst auch Reasoning. Ein Arbeitsschritt kann mehrere Calls benötigen.
Ohne Einnahmen ist die nutzbare Compute-Menge endlich, die Kalenderdauer bei
Sleep aber offen.

Künstlerbudget als Planungsreserve: 10–25 € für Entwicklungscalls, 0 € zusätzliche Hardware bei vorhandenem Laptop, grob 5–20 €/Monat Infrastrukturreserve zuzüglich tatsächlichem Strom. Das sind bewusst keine geprüften Hostingangebote. Menschliche Umsetzung etwa 8–12 Personentage einschließlich Website; monetär nach vereinbartem Tagessatz. Das Agentenbudget bleibt der beim Birth belegte OpenRouter-Bestand; sämtliche daraus bezahlten Lebensausgaben werden separat dokumentiert.

## 11. Quellen und offener Prüfstand

Geprüft am 14.09.2026:

- [Astra-Modell und Tarif](https://developers.openai.com/api/docs/models/gpt-6-astra).
- [Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create): beobachtbare Responses und Usage inklusive Cache-/Reasoning-Details; vollständige Client-Payloads lokal erhalten.
- [Organization Usage/Costs](https://developers.openai.com/api/reference/python/resources/admin/subresources/organization/subresources/usage): Abgleichschnittstellen für Kosten und Nutzung. Diese sind kein Beleg für einen öffentlich verfügbaren Echtzeit-Credit-Balance-Endpunkt.

Offen für P0: Linux-Ziel/Architektur, Produktionszugang, tatsächlich getrennte Prepaid-Abrechnung, Abschalt-/Nachbelastungsverhalten, Kaufbetrag und Belege. Dafür sind jetzt weder ein Geldtransfer noch ein Produktionscall erfolgt.
