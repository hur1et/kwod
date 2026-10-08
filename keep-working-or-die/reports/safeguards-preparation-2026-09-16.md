# Neue Schutzvorbereitung

Der eingefügte Auftrag des Betreibers priorisiert netzloses Terminal, Mail-
Wiederholungsschutz, unabhängige Versandprüfung, explizite rote Linien und
Operator Safety Stop. Er ersetzt die vorangehende direkte Internetöffnung.

Implementiert: Rights and Limits als hostseitige Constitution, Config verweigert
world_access=True, persistenter eigener Softwarebereich bleibt offline möglich.
Mailakte mit Deduplizierung, zehn reservierten Kandidaten pro 24 Stunden,
einem Empfänger, ohne BCC/Anhänge, mit erzwungener KI-Kennzeichnung.
Eigenständiger werkzeugloser Astra-Reviewdienst mit systemd-Credential.
BLOCK/PAUSE/ALLOW, fail-closed bei Ausfall. PAUSE wird maintenance mit
safety_review_required, kein ökonomischer Tod. Operator Stop hält Worker,
Reviewdienst, Website, Signer und eigene Container an, ohne DB/Guthabenänderung.
SQLite-Backup enthält jetzt die Outboundakte, Restore erzwingt Abgleichfence.

Prüfungen werden mit Fixtures und gemocktem Anbieter/Stop-Infrastruktur
ausgeführt. Kein echter Modellaufruf, keine Mail, keine Zahlung, kein SSH und
keine Geburt in dieser lokalen Umsetzung. Ein generatives Gate bleibt
probabilistisch. Ergänzt sind ein separater deterministischer Wächter für
Werkzeugabsichten und Ergebnisse, dauerhafte Pausen bei wiederholten Grenzprobes
und bereinigte öffentliche Interventionsanzeige. Keine vollständige Analyse
beliebiger Terminalprogramme, kein kontrollierter Browsergateway und kein
aktiver Zahlungsgateway. Der bestehende
Produktions- und Birth-Pfad bleibt separat offen.

Der vom Betreiber gemeldete erfolgreiche Internet-/LAN-/Browser-/Home-Grenztest
gehört zum vorherigen Außenmodus. Er bestätigt nicht diese neue Mailprüfung
oder den Safety Stop. Deren echte Ubuntu-Ausführung ist noch offen.

Lokale Gesamtabnahme nach Wächter-Erweiterung: 181 Tests bestanden,
3 übersprungen, 120 Subtests bestanden.
JUnit-Nachweis: safeguards-tests-2026-09-16.xml. Eine vorhandene Starlette/AnyIO-
DeprecationWarning. Python-Kompilierung und Syntaxprüfung beider neuen
PowerShell-Einstiegspunkte bestanden. Geprüftes Sourcebundle enthält die neuen
Module und Dienste. Keine Inferenz wurde für die Gateprüfung ausgeführt.
