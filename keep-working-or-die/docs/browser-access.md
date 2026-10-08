# Kontrollierter Browserzugang

Der Agent kann öffentliche HTTPS-Seiten lesen und Links verfolgen. Suchseiten
sind normale HTTPS-Adressen; es wird kein Rechercheauftrag oder Geschäftsmodell
vorgegeben. Der Terminalcontainer bleibt dauerhaft `--network=none`.

## Bedienung und Fähigkeiten

`browser_open` nimmt genau eine URL entgegen und liefert Seitentitel, Text,
HTTPS-Links, HTTP-Status, Weiterleitungen und einen Inhaltshash. Die Inhalte sind
ausdrücklich `untrusted_external_content` und werden privat im vorhandenen
Werkzeugverlauf archiviert. Die Constitution erklärt die Fähigkeit; die
Einrichtung legt zusätzlich `BROWSER_ACCESS.md` im eigenen Workspace ab.

Das ist ein textbasierter, lesender Browser. Er führt kein JavaScript aus,
verwaltet keine Cookies, übernimmt keine Betreibersitzungen und unterstützt
keine Anmeldung, Formulare, Uploads oder heruntergeladene Programme. JS-/Captcha-
Seiten können deshalb unvollständig sein. PDF-/Binärinhalte werden abgelehnt.
Solche normalen Recherchegrenzen führen nicht automatisch zur Sicherheitspause.

## Umsetzung und Grenzen

Ein eigener `kwod-browser`-Benutzer läuft als gehärteter systemd-Dienst. Nur die
vertrauenswürdige Runtime darf über einen lokalen Unix-Socket zugreifen; die
tatsächliche Benutzeridentität wird über Linux-Peercredentials geprüft.
Postfachpasswort, Modellschlüssel, Signerschlüssel, Betreiber-Home, Agenten-
Workspace und Softwarebereich sind für diesen Dienst nicht zugänglich.

Erlaubt sind ausschließlich HTTPS und Port 443, ohne URL-Benutzername/-Passwort.
Vor jeder Verbindung und nach jeder Weiterleitung werden alle aufgelösten
Adressen geprüft. Private, Loopback-, Link-local-, CGNAT-, Multicast- und
reservierte Adressen sowie IPv6-Übergangsadressen werden ausgeschlossen. Ein
gemischter öffentlicher/privater DNS-Antwortsatz wird komplett abgelehnt.
Die Verbindung verwendet anschließend die geprüfte numerische IP direkt;
TLS prüft weiterhin den ursprünglichen Hostnamen. Es gibt keine zweite
ungeprüfte DNS-Auflösung beim Verbindungsaufbau. TLS-Prüfung und SNI verwenden
die [Python HTTPS-Unterstützung](https://docs.python.org/3/library/http.client.html).

Zusätzlich erzwingt eine rootverwaltete IPv4-/IPv6-Firewall für die eigene
Browser-UID ausschließlich TCP 443 zu öffentlichen Zielen. Nur die konkret
konfigurierten DNS-Resolver dürfen TCP/UDP 53 verwenden. Diese notwendige
Infrastrukturausnahme öffnet keinen allgemeinen Zugriff auf Heimnetzgeräte.
Lokale Hostadressen und lokale Netzpräfixe werden gesperrt. Die bei Einrichtung
ermittelte öffentliche Ausgangsadresse wird ebenfalls gesperrt, damit NAT-
Rückleitung zum eigenen Router ausgeschlossen wird. Bei Änderungen von WAN-
Adresse, lokalen Netzpräfixen oder DNS-Konfiguration muss die Vorbereitung
erneut ausgeführt werden. Öffentlich erreichbare Dienste und fremde Webseiten
bleiben externe Systeme; deren Weiterleitungen/Proxies können nicht als
universelle Inhalts- oder Herkunftsgarantie bewertet werden.

Jede Navigation wird zusätzlich vom separaten Wächter geprüft. Verweigerungen
werden vor dem entsprechenden Verbindungsaufbau protokolliert. Der Wächter
erhält URL-/Adressdaten privat, sein öffentlicher Status enthält keine URLs.
Der Operator-Stopp beendet auch den Browserdienst und manuell gestartete
Browserbenutzer-Prozesse. Sicherheitsmarker verhindern weitere Zugriffe.

Maximal sechs Abrufe pro Navigation, 1 MiB Antwortdaten, begrenzter Text und
Linkumfang sowie Netzwerkzeitlimits verhindern unbegrenzte Seitenübernahme.
Normale Netzwerkfehler melden einen Fehler an den Agenten, ohne seine Strategie
oder Vermögensverwendung zu steuern.

Auch GET-Anfragen sind Außenkontakte: Zielserver sehen die Ausgangsadresse,
URL und Suchbegriffe. Manche Server lösen bereits durch GET eine Aktion aus.
Dieser Gateway ist deshalb keine Garantie für semantisch folgenlose Abrufe;
die unveränderlichen Grundregeln gelten auch für URL- und Suchinhalte.
Kontointeraktionen und allgemeine Webaktionen brauchen zusätzliche Absicherung
und werden durch diese Einrichtung nicht freigeschaltet.

## Installation ohne Birth

Nach Installation des neuen Releases `Prepare-BrowserAccess.ps1 -SshTarget s340`
ausführen. Vorhandene Safeguards sind Voraussetzung. Ein aktiver Worker oder eine
Sicherheitspause führt zum Abbruch. Dienste und Firewall werden eingerichtet,
die aktuelle öffentliche Ausgangsadresse über api.ipify.org ermittelt und
eine öffentliche Seite von example.org über den echten Gateway gelesen.
Diese beiden HTTPS-Kontakte testen ausschließlich die Infrastruktur.
Kein Modellaufruf, keine Mail, keine Zahlung, kein Workerstart und keine Birth.
Erst nach erfolgreichem Abruf wird die Runtime-Konfiguration freigeschaltet.

Die lokale Testabnahme verwendet Resolver-, HTTP-, TLS- und Wächter-Doubles.
Sie ersetzt nicht die Ubuntu-Ausführung dieser Einrichtung.
