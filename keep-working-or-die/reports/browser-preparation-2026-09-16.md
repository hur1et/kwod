# Kontrollierter Browser vorbereitet

Implementiert ist browser_open als textbasierter HTTPS-Lesezugang über einen
eigenen systemd-Benutzer und authentifizierten Unix-Socket. Das Terminal bleibt
network=none. Private/gemischte DNS-Ziele, lokale Netzpräfixe, lokale Hostadressen,
IPv6-Übergang und die bei Einrichtung ermittelte öffentliche Ausgangsadresse
werden vor der Verbindung gesperrt. Numerisches IP-Pinning mit Hostnamenprüfung
für TLS verhindert ungeprüfte zweite DNS-Auflösung. Jede Weiterleitung wird
neu bewertet; der unabhängige Wächter prüft jede Navigation.

Zusätzlich begrenzt eine persistente, rootverwaltete IPv4-/IPv6-OUTPUT-Firewall
den Browserbenutzer auf TCP 443 und konkret konfigurierte DNS-Resolver auf
TCP/UDP 53. Operator-Stopp umfasst Browserdienst und Browserbenutzer-Prozesse.
Die Gateway-Ausgabe ist externes, unvertrauenswürdiges Material im privaten
Werkzeugverlauf. Kein JavaScript, Cookieprofil, Betreiberlogin, Formular,
Upload, beliebiger Download oder öffentlicher Hostingzugang wird aktiviert.

Lokale Gesamtprüfung: 195 Tests bestanden, 3 übersprungen, 153 Subtests bestanden.
Nach Ergänzung der unveränderlichen Browser-Verhaltensregeln bestanden auch die
28 relevanten Browser-, Firewall-, Wächter- und Konfigurationsprüfungen erneut.
JUnit: browser-tests-2026-09-16.xml. Bestehende Starlette-DeprecationWarning.
Die Firewall-Tests bewerten die erzeugten Regeln mit repräsentativen Paketen;
sie führen keine echten Linux-Netfilter-Änderungen durch.

Die Ubuntu-Ausführung steht aus. Prepare-BrowserAccess prüft dort Dienste und
Firewall, ermittelt die öffentliche Ausgangsadresse über api.ipify.org und
liest example.org durch den tatsächlichen Gateway, bevor Config freigeschaltet
wird. Dies erzeugt zwei öffentliche HTTPS-Kontakte, aber keine Modellaufrufe,
Mails, Zahlungen, Workerstarts oder Birth. Sourceumsetzung und lokale Tests
haben keine SSH-Verbindung oder echte Agenten-Modellaufrufe ausgelöst.

Das bisherige DOCX wurde in einer separaten erweiterten Ausgabe erhalten und
um Browser, Safeguards, Betrieb und Grenzen ergänzt. Veraltete Angaben zu Mail-
Wiederholungsschutz und Größenbegrenzung wurden korrigiert. OOXML-Lesbarkeit
und Inhalte wurden geprüft. Ein gebündelter Word-/LibreOffice-Renderer ist in
diesem Windows-Runtimepaket nicht vorhanden; vollständige visuelle Seitenprüfung
konnte deshalb nicht erfolgen.

Grenzen: GET kann serverseitig Folgen haben und übermittelt URL/Suchbegriffe
an externe Systeme. Inhaltliche Verbote gelten hostseitig als unveränderliche
Grundregeln, sind für Browser-URLs kein generativer Inhaltsfilter. WAN-, Netz-
oder DNS-Wechsel verlangen erneute Vorbereitung. JS-/Captcha-Seiten können
unbrauchbar sein. Allgemeine Webaktionen und Zahlungsgateway bleiben offen.
