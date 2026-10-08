# Birth vom Monitor aus

Die öffentliche Beobachtung bleibt ohne schreibende API. Ihr Link „Birth-Steuerung öffnen“ führt auf eine separate passwortgeschützte Ansicht unter http://127.0.0.1:8766. Watch-Agent leitet diese lokale Adresse durch SSH an den ausschließlich auf Ubuntu-Loopback gebundenen Operatordienst auf Port 8001. Zugang benötigt sowohl den SSH-Tunnel als auch das eigene Operatorpasswort. Benutzername ist operator. Kein Port am Router muss geöffnet werden.

## Einrichtung ohne Birth

```powershell
& .\deploy\Deploy-Ubuntu.ps1 -SshTarget s340 -Action Install
& .\deploy\Prepare-Production.ps1 -SshTarget s340
& .\deploy\Prepare-BirthControl.ps1 -SshTarget s340
& .\deploy\Watch-Agent.ps1 -SshTarget s340
```

Prepare-BirthControl fragt ein neues Passwort zweimal verdeckt ab. Gespeichert wird ein gesalzener PBKDF2-SHA256-Hash mit 600000 Iterationen, root-only. Ein vorhandenes Passwort wird beibehalten. Die Vorbereitung aktiviert nur den Operatordienst, nicht den Agentenworker. Sie erzeugt keinen BORN-Marker, keine Birth, keine Modellanfrage und keine Zahlung. Der Installer stoppt einen bisherigen Operatorprozess, damit ein neuer Code nicht durch einen alten Startprozess ausgelöst werden kann. Anschließend ist erneute Vorbereitung nötig. Linux-Dienste müssen auf Ubuntu geprüft werden.

## Start ohne finanziertes Wallet und Ablauf

Der Betreiber hat am 17 September 2026 ausdrücklich entschieden, ohne finanziertes Wallet und ohne vorherigen Wallet–OpenRouter-Zahlungstest zu starten. Der Operatordienst prüft weiterhin den installierten Produktionschecker. Der Zahlungstest ist keine Startsperre mehr. Die Ansicht zeigt stattdessen den Hinweis zum unfinanzierten Wallet und ungeprüften Nachladeweg.

Der Kontostandsnachweis bleibt erforderlich: Das tatsächliche OpenRouter-Guthaben ist das Erbe. Die Birth-Evidence enthält wallet_test=null. Es wird kein Zahlungsnachweis angelegt und keine Gutschrift fingiert. BIRTH_RESOURCES.json und der initiale Modellkontext erhalten wallet_funding=unfunded_as_reported_by_operator sowie wallet_openrouter_test=not_performed. Dies ist die Betreiberangabe, keine Abfrage oder bestätigte Nullbewertung der Blockchain. EUR-Bewertung und on-chain Walletsaldo bleiben unbekannt. Der Agent erfährt ausdrücklich, dass bei Birth kein funktionierender Nachladeweg eingerichtet ist.

Ein alter wallet-openrouter-verified.json-Nachweis wird für diesen Start weder vorausgesetzt noch automatisch als aktuelle Prüfung übernommen. Ein späterer echter Zahlungstest kann weiterhin separat dokumentiert werden. Safety-STOP, Watchdog-Pause und alle technischen Readiness-Prüfungen bleiben verbindlich.

Bei erfüllten Voraussetzungen liest „Erbe prüfen und Birth vorbereiten“ den echten Accountbestand bei OpenRouter. Die Vorschau gilt 60 Sekunden. Ein zweiter bewusster Klick mit angekreuzter Zustimmung löst Birth aus. Vor dem Speichern werden technische Voraussetzungen und Guthaben erneut geprüft. Bei Änderungen muss die Vorschau neu erstellt werden. Kein automatischer Wiederholungsversuch ist vorgesehen.

OpenRouter dokumentiert für GET /api/v1/credits einen Management-Key. Falls der Modell-Key keinen Zugriff hat, kann Connect-CreditReader.ps1 einen separaten Management-Key verdeckt auf Ubuntu unter /etc/kwod-openrouter/credits.key speichern. Dieser Schlüssel wird niemals als systemd-Credential an den Worker weitergegeben. Der Kontostand ist total_credits minus total_usage; gespeichert werden USD-Providercredits, keine fiktiven Euro und keine Walletbewertung. Quelle: https://openrouter.ai/docs/api/api-reference/credits/get-credits

## Einmalige Speicherung und Fehler

Ein Prozesslock serialisiert die Operatoraktionen, ein Workerlock schützt den Store, und die Datenbank erzwingt genau ein Birth-Event und eine Erbbuchung. Startcontext bleibt erhalten und wird um die bestätigten Ressourcen ergänzt. BIRTH_RESOURCES.json steht im eigenen Workspace. Birth-Zeitpunkt, Evidence, Assetbeobachtung und Erbbuchung werden in einer SQLite-Transaktion gespeichert. Erst danach wird der rootgeschützte BORN-Marker erzeugt und kwod-production.service mit enable --now aktiviert.

Bei einem Fehler nach dem Datenbankcommit wird Birth nicht zurückgenommen und nicht wiederholt. Der Operatorstatus liest den tatsächlichen privaten born_at-Wert unabhängig von einer möglicherweise noch alten öffentlichen Projektion. Ein fehlender Marker oder Workerstart benötigt eine gezielte manuelle Wiederaufnahme durch den Betreiber; die UI bietet keinen automatischen zweiten Birth-Versuch an. Bei unbekanntem HTTP-Ausgang ebenfalls den gespeicherten Status prüfen.

## Berechtigungsgrenze

Der Operatorprozess läuft mit Rootrechten, weil er den getrennten Birth-Marker erzeugt, geschützte Kontostandszugänge liest und systemd steuert. Schreibbare Pfade sind auf Produktionskontrolle und Produktionsdaten eingeschränkt. Er öffnet nur feste Dienste und feste URLs; keine frei übermittelten Shellbefehle, Pfade oder Zieladressen. SQLite und Workspace werden durch einen festen Helper unter kwod-runtime geschrieben, damit Eigentümerrechte stimmen.

Basic-Auth wird nur über den lokalen SSH-Tunnel verwendet. Hostprüfung, gleichursprüngliche Origin-Prüfung, ein zufälliger CSRF-Header, frame-ancestors none und no-store schützen die Startaktion zusätzlich. Fünf fehlerhafte Anmeldungen pro Minute sperren weitere Anmeldungen vorübergehend. Der Agent besitzt weder das Passwort noch den Management-Key; Terminalnetz bleibt aus und sein Browser blockiert Loopback. Diese Grenze setzt weiterhin vertrauenswürdige Hostprogramme und einen intakten Ubuntu-Administratorzugang voraus.

Der sichere Operator-Stopp beendet jetzt auch den Startzugang. Bereits laufende externe Wirkungen können weiterhin einen unbekannten Ausgang haben. Eine Safety-Pause oder STOP wird durch die Startansicht nicht entfernt.

## Readiness im Operatordienst

AF_NETLINK ist ausschließlich im Operatordienst zugelassen, damit iptables und ip6tables die tatsächlich eingebundenen Firewall-Hooks lesen können. Die Dateisystemdiagnose mit nsenter allein bildet diese Adressfamilienbeschränkung nicht nach. Test-BirthReader führt deshalb zusätzlich eine vorübergehende Diagnose mit den tatsächlichen systemd-Beschränkungen aus. Repair-BirthMonitor ergänzt bei der alten Operatorunit genau diese Adressfamilie und startet nur den Operatordienst neu. Passwort, Produktionsworker, Birth-Zustand, Zahlungsnachweise und Agentenfirewall werden nicht geändert.

Der Operatordienst erhält außerdem AmbientCapabilities CAP_SETUID und CAP_SETGID, damit seine festen Helpers unter kwod-runtime laufen können. NoNewPrivileges bleibt aktiv; die Runtime- und Containerunits erhalten diese Fähigkeiten nicht. Das Dienstprotokoll vom 17 September zeigte, dass runuser innerhalb des tatsächlichen Webdienstes mit „Benutzerkennung konnte nicht festgelegt werden“ scheiterte. Eine vorübergehende Diagnose muss deshalb auch AmbientCapabilities und CapabilityBoundingSet nachbilden. Die aktualisierte Repair-BirthMonitor-Reparatur ergänzt die beiden Fähigkeiten in der vorhandenen Operatorunit, prüft deren Laden und startet ausschließlich den Operatorzugang neu. Der tatsächliche erfolgreiche Zustandszugriff muss anschließend im Monitor bestätigt werden.
