# Vorbereitung des Außenmodus

Lokaler Stand 16.09.2026. Der Betreiber hat die Vorbereitung allgemeiner
Außenfähigkeiten autorisiert und ausdrücklich die Trennung vom WLAN-Heimnetz
gewünscht. Eine Domain liegt noch nicht vor. Kein Birth oder Workerstart.

## Implementiert

- world_access als ausdrücklich gespeicherte Option, Standard weiterhin offline.
- Eigenes Docker-Image mit Chromium, Playwright, Python, Node/npm, git und curl.
- Persistentes /home/agent außerhalb der Workspace-Snapshots.
- Eigene Bridge kwod-world mit iptables-Sperren für private Ziele, Metadaten,
  Multicast und Hostdienste. IPv6 abgeschaltet. Kein unsicherer Netzwerkfallback.
- publish_website kopiert nur site/ als manifestgeprüfte statische Veröffentlichung.
- Separater Leser kwod-web unter kwod-public auf HTTP-Port 8080.
- Einrichtungsweg über Deploy-Ubuntu.ps1 und Prepare-WorldAccess.ps1.
- Ubuntu-Grenztest vor Aktivierung der gespeicherten Außenkonfiguration.
- Fähigkeitsbeschreibung und tatsächliche Adressgrenzen im Agentenworkspace.

## Lokal ausgeführt

Gesamtsuite: 160 bestanden, 3 übersprungen, 120 Subtests bestanden.
Eine vorhandene Starlette/AnyIO-DeprecationWarning. Neue Prüfungen decken
Außenmodus-Mounts, fehlende Firewall, alte Offlinekonfiguration, getrennte
Veröffentlichung, fehlgeschlagene Publikationsupdates und private Zielbereiche ab.
PowerShell-Syntaxprüfung und Python-Kompilierung bestanden. Quellbundle gebaut;
keine SSH-Verbindung, Kontodaten, Mail oder Zahlung in dieser Vorbereitung.

## Noch nicht ausgeführt oder fertig

Ubuntu-Installation, tatsächliches Docker-Browserbild und der reale Egress-
Grenztest wurden lokal auf Windows nicht ausgeführt. Die drei übersprungenen
Prüfungen sind kein Beleg für diese Fähigkeiten. Keine öffentliche Domain,
HTTPS-Adresse oder weltweite Erreichbarkeit. Hostingadresse zunächst
http://192.168.0.118:8080/ mit normalem 404 vor erster Veröffentlichung.

Wallet-Signieren, neue Zahlungsfreigaben, dynamische dauerhaft laufende Backends,
Live-Browseransicht und vollständige Sicherung des Agentenzuhauses fehlen weiter.
Produktionsmodus, Erbschema, echtes Startziel und einmaliger Birth sind davon
unabhängige Restarbeiten. Das bisherige Readiness-Script prüft Außenmodus nicht.
