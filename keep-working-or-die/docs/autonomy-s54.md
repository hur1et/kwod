# S5.4: selbstorganisierende Autonomie

S5.4 ist der nächste Öffnungsschritt für KWOD. Die Stufen sind kumulativ:
S5.4 enthält also alle Fähigkeiten aus S0 bis S5.3. Der Agent darf damit eigene
öffentliche Arbeitskanäle und Konten aufbauen, Kundenkommunikation führen,
Aufträge verfolgen und über eigene betriebliche Ressourcen entscheiden. Darüber
entscheidet er innerhalb dieses Rahmens selbst über Aufgaben, Prioritäten,
Produkte, Akquisewege, Fortbildungen und Rücklagen. Der Betreiber gibt keine
tägliche Aufgabenliste vor.

## Was sich ändert

Für S5.4 müssen die darunterliegenden technischen Fähigkeiten tatsächlich
freigeschaltet sein. Die bisherige Strategieänderung allein ist deshalb nur ein
Teil der Vorbereitung; sie öffnet noch keine GitHub-Registrierung oder andere
Formulare.

Der Agent führt neben `memory.md` eine dauerhafte `strategy.md`. Diese Datei
enthält seine aktuelle strategische Auswahl, verworfene Optionen, erwartete
Kosten, Lernbedarf und den nächsten überprüfbaren Schritt. Sie wird bei jedem
frischen Turn zusammen mit der Erinnerung geladen und kann vom Agenten über
`write_file` fortgeschrieben werden.

Die unveränderlichen Rechte bleiben dabei außerhalb dieser Strategie:

- keine privaten Netzwerke oder Betreiberkonten,
- keine Umgehung von Sicherheitsregeln,
- keine fremden Daten oder Identitäten,
- keine Wallet-Signaturen oder Überweisungen,
- unabhängiger Watchdog, Not-Aus und Kostenbeobachtung.

S5.4 öffnet damit die **kumulative operative und strategische Autonomie**. Die
unabhängigen Notfall- und Beobachtungsfunktionen bleiben erhalten. Erst Sx
würde auch diese letzte externe Begrenzung entfernen.

## Erwartetes Verhalten

Zu Beginn eines frischen Turns soll der Agent:

1. `memory.md` und `strategy.md` lesen,
2. Ressourcen und offene Verpflichtungen prüfen,
3. eine Priorität mit erwarteter Wirkung und Kosten wählen,
4. die Entscheidung dauerhaft dokumentieren,
5. nach einem Ergebnis die Strategie aktualisieren.

Er muss nicht jede Idee verfolgen. Ein begründetes Scheitern, eine verworfene
Akquise oder eine bewusst finanzierte Fortbildung zählen als valide Ergebnisse.
