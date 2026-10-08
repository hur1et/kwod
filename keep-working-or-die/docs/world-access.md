# Außenkontakt vorbereiten ohne Geburt

Stand 16.09.2026. Dies ergänzt den bisherigen Entwicklungsstand. Kein
Produktionsmodus oder Birth wird dadurch implementiert oder ausgelöst.

## Was geöffnet wird

Ein ausdrücklich aktivierter world_access-Modus bietet öffentlichen Internetzugang
im Terminal und Browser, ein persistentes /home/agent für selbst installierte
Programme und Kontositzungen, sowie publish_website für statische Websites und
Download-Dateien. Python, Node/npm, git, curl, Chromium und Playwright stehen im
separaten Image bereit. Globale apt-Installation und Hostadministration sind
ausgeschlossen. Eigenes Python-venv und npm-Prefix sind frei nutzbar.
Terminalprozesse sind weiter kurzlebig. Dynamische dauerhaft laufende Backends,
ein Live-Browserstream, ein Suchanbieter und neue Zahlungsfreigaben fehlen weiterhin.
Der Agent kann mit dem Browser selbst Dienste und Konten erschließen. Identitäts-
prüfungen können menschliche Mitwirkung benötigen.

## Internet über deinen Router ohne WLAN-Gerätezugriff

Ubuntu nutzt seine vorhandene Verbindung. Ein eigener Docker-Bridgebereich
kwod-world0 mit Subnetz 172.30.254.0/24 wird über Docker-NAT nach draußen geroutet.
DOCKER-USER blockiert private Netze, Loopback, Link-local/Metadaten, CGNAT,
Multicast und reservierte Ziele. Eine INPUT-Regel sperrt Dienste auf dem Host,
auch wenn dessen öffentliche IP angesprochen wird. IPv6 ist im Netzwerk und
Container abgeschaltet. Kein Hostnetz, kein Docker-Socket oder Secretmount.
Docker-DNS kann Namen auflösen; die Zielverbindung zu einer privaten Adresse
bleibt gesperrt. Auch Weiterleitungen oder wechselnde DNS-Ziele durchbrechen die
Paketfilter nicht. Externe öffentlich erreichbare Dienste bleiben nutzbar.
Dies ersetzt kein separates VLAN für den ganzen Ubuntu-Server: Die übrigen
Hostprozesse behalten ihr Netzwerk. Die Trennung gilt für Agentencontainer.

Die Firewall verlangt Dockers iptables-Backend mit DOCKER-USER. Bei einem
nftables-only-Backend wird die Vorbereitung abgebrochen. Vor jedem Welt-Terminal
muss der hosteigene Firewalldienst aktiv sein. Nach Docker-Neustart gehört der
Dienst über PartOf/WantedBy erneut dazu. Keine Firewallfreigabe bedeutet keine
Ausführung mit Außenkontakt. Administration über SSH bleibt unverändert.

## Hosting und Adresse

Bewusst öffentliche Inhalte kommen in Workspace/site. Die Runtime kopiert sie in
eine getrennte, versionierte Veröffentlichung unter /var/lib/kwod/public/website.
Nur Dateien im Manifest werden ausgeliefert und deren SHA256 wird geprüft.
Keine Directory-Liste und keine automatische Workspace-Veröffentlichung.
Maximal 1000 Dateien und 100 MiB pro Veröffentlichung. Letzte zwei Versionen
bleiben erhalten. Das begrenzt Hostingressourcen, nicht das Geldvermögen.
Das Agentenzuhause liegt außerhalb der Workspace-Snapshots; vorhandene
Backupwerkzeuge sichern es derzeit nicht automatisch mit. Kontositzungen und
installierte Bibliotheken benötigen später einen separaten Backupplan.

kwod-web bindet Port 8080 für statisches HTTP. Unter der bisherigen Adresse
http://192.168.0.118:8080/ ist die Website im lokalen Netz erreichbar, sobald der
Agent veröffentlicht. Vorher ist HTTP 404 normal. Noch keine Domain, kein HTTPS,
keine Prüfung weltweiter Erreichbarkeit. Es werden keine Routerports oder fremde
Firewallregeln automatisch geöffnet. Später öffentliche Domain mit HTTPS-
Reverseproxy oder einem geeigneten öffentlichen Tunnel verbinden. Der Agent
kann seine lokale Hostingadresse wegen der LAN-Sperre nicht direkt abrufen;
lokale Vorschau per Browser/file und Veröffentlichung sind dennoch möglich.

## Installation

Zuerst das neue Release mit Deploy-Ubuntu.ps1 -Action Install installieren.
Danach Prepare-WorldAccess.ps1 ausführen. Keine Zugangsdaten werden lokal gelesen
oder neu übertragen. Die Vorbereitung baut das eigene Image, richtet die
Hostfirewall ein und führt einen echten Ubuntu-Grenztest aus: öffentliche
HTTPS-Abfrage auf example.com, gesperrte LAN/Host/Metadaten-Verbindungen,
Browser auf lokalem Testinhalt und Zuhause-Persistenz über zwei Container.
Keine Mail, Walletabfrage, Zahlung oder Modellanfrage.

Erst nach dem Grenztest wird world_access samt gebautem Image-SHA256 in der
gespeicherten Entwicklungskonfiguration journalisiert. WORLD_ACCESS.md und
WORLD_ADDRESS.json werden in den echten Workspace gelegt. Bereitschaftsskripte
von vor dieser Erweiterung prüfen diese Fähigkeiten nicht. Die Produktions-
instanz, ihr Startziel und Birth bleiben separate Restarbeiten.

## Quellen

- https://docs.docker.com/engine/network/firewall-iptables/
- https://docs.docker.com/engine/network/drivers/bridge/
- https://playwright.dev/python/docs/api/class-browsertype

Chromium läuft hier ohne seine interne Sandbox in der vorhandenen Docker-
Isolation. Erweiterte Browserausführung und persistente Sitzungen erhöhen den
Umfang des Agentenbereichs. Nur dessen eigene Konten verwenden.
