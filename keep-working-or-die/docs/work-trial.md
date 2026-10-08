> Stand 16.09.2026 nach AP0: Trial01 ist beendet; fünf erfolgreiche Versuche nach einem 404, Review fehlt. Kein Neustart. Nachfolgende Aussagen zu ausstehenden Läufen/Resume sind historisch. Aktuell: [AP0-Bericht](../reports/ap0-status-2026-09-16.md).

# Erster begrenzter Arbeitslauf — 16.09.2026

## Ergebnis und nächste lokale Verbesserung

Kostenbeobachtung: Nutzer meldet am16.09.2026 **0,09USD** für diesen Trial.
Als Nutzerangabe gespeichert, nicht unabhängig mit Anbieterabrechnung abgeglichen:
`work-trial-cost-observation.json`. Bei fünf erfolgreichen Aufrufen sind das
rechnerisch0,018USD pro erfolgreichem Aufruf; keine belegte Einzelaufrufabrechnung
und keine belastbare Hochrechnung auf andersartige Aufgaben. Keine EUR-Umrechnung,
kein abgeleiteter Kontosaldo und keine zusätzliche Ledgerbelastung erzeugt.

Nach einem404 wurden fünf Modellanfragen erfolgreich abgeschlossen (insgesamt
etwa33 Sekunden). Entwurf „Restlaufzeit“, Werkbeschreibung und Gedächtnisdatei
wurden gespeichert, Review fehlt. Dienst inzwischen gestoppt. Budget ausgeschöpft;
keine erneute Ausführung dieses Trials. Die Gedichtaufgabe war ein vom Entwickler
gewählter Funktionstest, kein Beleg für selbstständige Auftragsakquise oder Einnahmen.

Neu, bisher nur lokal: Jede Trialanfrage enthält die tatsächliche Versuchsnummer
und das verbleibende Budget, einschließlich fehlgeschlagener Versuche. Der letzte
Aufruf verlangt einen ehrlichen Abschluss; Kontextübergaben setzen das Budget nicht
zurück. Gefilterte Tools und Budgethinweis werden mit der effektiven Trialanfrage
privat archiviert. Report nennt fehlende Dateien und trial_call_limit als separaten
Abbruchgrund.22 Tests+13 Subtests bestanden. Die Wirkung auf die Planung des echten
Modells ist noch nicht geprüft. Keine zusätzlichen Modellkosten in diesem Schritt.

Aktueller Nachtrag: Der erste Start scheiterte an systemd-IP-Aliaslisten, inzwischen
korrigiert. Der zweite scheiterte vor Initialisierung an chmod2770 (setgid) im
DynamicUser-Sandboxprozess. Diagnose: keine Modellversuche gespeichert. Der Trial
nutzt jetzt private700/600-Rechte ohne setgid. `Test-WorkTrial.ps1 -ResumeUnstarted`
setzt ausschließlich den nachweislich noch nicht initialisierten Lauf fort: Marker
und DB müssen existieren, Instanz-/Versuchs-/Tool-/Ereignistabellen sowie Workspace
müssen leer sein. Ein zusätzlicher exklusiver Marker verhindert doppelte Fortsetzung.
Keine bestehenden Marker werden gelöscht.47 Tests und18 Subtests plus PS-Syntax
bestanden; korrigierter Ubuntu-Lauf noch ausstehend.

Der Nutzer hat einen echten Entwicklungsprobelauf über das vorhandene OpenRouter-
Guthaben autorisiert. Dies ist keine Produktionsgeburt. Automatischer Nachkauf und
Supportversand bleiben zurückgestellt.

Start in Windows PowerShell:

```powershell
& 'C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\Test-WorkTrial.ps1'
```

Aufgabe: deutscher Textentwurf (max.180 Wörter), Werkbeschreibung, dauerhafte
Arbeitsübergabe und eine anschließende kritische Review mit frischem Kontext.
Maximal sechs Modellaufrufe mit jeweils2048 Output-Tokens, keine automatischen
Provider-Retries. Das begrenzt den Lauf, ist keine zugesagte Euro-Kostengrenze.
Antworten und Usage bleiben im privaten Journal. Der Bericht zeigt Erfolg erst,
wenn alle vier Dateien nicht leer sind, eine Übergabe vorliegt und der Lauf idle
erreicht; das ist keine Bewertung der künstlerischen Qualität.

Dateiwerkzeuge, checkpoint und record_decision stehen bereit. Andere Toolcalls
werden abgewiesen. Kein Terminal, keine Zahlung, keine Veröffentlichung.
Ein vorab exklusiv gespeicherter Marker verhindert weitere Aufrufe bei Wiederholung.
Auch nach einem Crash darf dieser Marker nicht einfach für einen Retry gelöscht
werden. Zuerst den tatsächlichen Stand prüfen.

Der Launcher prüft den Bundle-Hash, kopiert ausschließlich Python-/Migrationsquellen
in einen rootgeschützten temporären Bereich und nutzt vorhandene Runtime-Pakete.
Ein transienter systemd-Dienst läuft als DynamicUser mit eigenem StateDirectory,
ohne Docker-Socket oder Haupt-Instanzdaten. Das vorhandene Credential wird durch
systemd separat bereitgestellt. Private/Link-local-Netzadressen sind blockiert;
127.0.0.53 bleibt für Ubuntus lokalen DNS-Stub zugelassen. Kein Modellwerkzeug
kann beliebige Netzaufrufe ausführen. Runtime-Limit900 Sekunden,512MiB RAM.

Private Ergebnisse auf Ubuntu:

- `/var/lib/kwod-work-trial-01/report.json`: Status, Dateihashes und beobachtete Usage pro Versuch.
- `/var/lib/kwod-work-trial-01/data/workspace/works/`: Entwurf, Beschreibung, Review.
- `/var/lib/kwod-work-trial-01/data/workspace/memory.md`: Arbeitsübergabe.
- `/var/lib/kwod-work-trial-01/data/private/`: vollständiges Journal.

Lokal bestanden:20 Tests und15 Subtests (Trial, Kontextübergabe, OpenRouter-Adapter),
PowerShell-/Python-Syntax und Quellenpaket. Das beweist noch keinen echten
Modellzugang und keine Linux-Dienstabnahme. Die Ausgabe des Nutzerlaufs steht aus.

Responses-API-Vertrag geprüft anhand:
https://openrouter.ai/docs/api_reference/responses/overview

