# Windows 11 → SSH → Ubuntu 24.04.4 LTS

Ziel laut Betreiber: SSH-Alias `s340`. Stand 15.09.2026: Der Betreiber hat das Deployment von Windows aus ausgeführt und den öffentlichen Lesedienst sowie die Browseranzeige über den SSH-Tunnel bestätigt. Ein Gruppenrechtefehler an der öffentlichen Datenbank wurde auf Ubuntu manuell repariert; die lokale Installationsvorlage enthält die Korrektur und eine zusätzliche Leseprüfung unter `kwod-public`. Diese lokale Änderung wurde noch nicht erneut auf Ubuntu ausgerollt. Die Codex-Arbeitsumgebung selbst hat keinen bestätigten SSH-Zugang zum Ziel.

## Vom eigenen Windows-Terminal aus

Im Projektverzeichnis ausführen. Der Alias liefert Benutzer, Port und Schlüsselauswahl aus deiner vorhandenen SSH-Konfiguration. Es werden keine Schlüsseldateien mit dem Projekt kopiert. Den Server-Hostschlüssel vor dem ersten Einsatz anhand des Ubuntu-Geräts verifizieren; die Skripte schalten diese Prüfung nicht aus.

```powershell
ssh s340
```

Die eigentliche Vorbereitung erfolgt anschließend aus Windows:

```powershell
.\deploy\Deploy-Ubuntu.ps1 -SshTarget s340 -Action Check
.\deploy\Deploy-Ubuntu.ps1 -SshTarget s340 -Action Install -InstallPrerequisites
```

`Check` erzeugt und überträgt ein reines Quellpaket, kontrolliert dessen SHA-256, entpackt es in ein neues Verzeichnis im SSH-Benutzer-Home und prüft Ubuntu, Python und systemd. Es verändert keine Systemdienste. `Install` benötigt sudo und installiert unter `/opt/kwod/releases/<release>`. Mit `-InstallPrerequisites` werden Ubuntu-Pakete für Python-venv und Docker installiert. Auf dem Host werden keine Firewall- oder SSH-Regeln automatisch verändert.

Die Installation legt getrennte Runtime-/Public-Benutzer und einen gemeinsamen Workspace-GID 65532 an. Vorhandene widersprechende Identitäten führen zum Abbruch. Der vertrauenswürdige Runtime-Benutzer erhält Docker-Verwaltungsrechte; der Agent-Executor erhält weder diese Rechte noch den Socket. Dieses Vertrauen gilt ausschließlich für die vom Betreiber installierte Runtime.

Danach werden Paketabhängigkeiten installiert, Offline-Tests ausgeführt, das Executor-Image gebaut und die beiden Linux-Isolationstests unter der tatsächlichen Runtime-Identität ausgeführt. Erst nach bestandenen Prüfungen wird die Instanz initialisiert und der öffentliche Lesedienst gestartet. **Der Modell-Worker wird nicht gestartet oder automatisch aktiviert.** Es findet keine Geburt statt, und kein API-Key wird erstellt oder hochgeladen.

Die vorhandenen Dienstvorlagen verwenden `/opt/kwod/current`. Dieses Symlink wird erst nach den Prüfungen auf das neue Release umgestellt. Bei einem Update muss `kwod-runtime` zuvor beendet sein; das Skript unterbricht keine laufenden Agentenaktionen. Vor einer Migration vorhandener Daten wird ein Backup mit dem alten Release angelegt. Bestehende Instanzkonfiguration und Executor-Auswahl bleiben erhalten; Imagewechsel sind ein eigener dokumentierter Eingriff. Alte Releases und Backups werden nicht automatisch gelöscht. Ein Abbruch kann ein unaktiviertes Release oder bereits installierte Systempakete hinterlassen; es wird kein vollständiger Rollback behauptet.

## Vom Hauptcomputer zusehen

```powershell
.\deploy\Watch-Agent.ps1 -SshTarget s340
```

Danach im Browser öffnen: **http://127.0.0.1:8765**. Das Terminal bleibt offen; Strg+C schließt den Tunnel. Die Verbindung ist ein lokales Forwarding von Windows zum ausschließlich auf Ubuntu-Loopback erreichbaren Lesedienst. Kein Reverse-Tunnel, keine SSH-Agent-Weiterleitung, keine X11-Weiterleitung. Vorkonfigurierte Portweiterleitungen im Alias werden vom Beobachtungsskript abgewiesen.

Die neue monochrome Ansicht zeigt den Entwicklungszustand, letzte Activity, Wake-Zeit und öffentliche Ereignisse. Vor Geburt bleiben Vermögen und Kurve leer. Ein veralteter Worker-Stand und ein unterbrochener Beobachtungstunnel sind unterschiedliche Zustände. Das Browserfenster steuert den Agenten nicht und erhält keine privaten Modellantworten, Terminalbefehle oder Dateiinhalte. Es ist eine erste Beobachtungsansicht; finanzielle Live-Daten und historisches Replay sind noch nicht angebunden.

## Grenze zum Hauptcomputer und zum Netzwerk

Die Betreiberanforderung lautet: keine unbefugten Zugriffe vom Agenten auf Windows, andere LAN-Geräte oder fremde Systeme. Der neue Server ist kein Freibrief zum Ausbruch. Die derzeitige technische Grenze ist ein netzloser Container mit ausschließlich seinem Workspace als Mount. Er erhält keine Windows-Freigaben, SSH-Schlüssel, Agent-Sockets, Host-Home-Verzeichnisse, private Datenbank oder API-/Zahlungsschlüssel. Keine dieser Grenzen wird durch die Beobachtungsansicht gelockert.

Für den später wirtschaftlich aktiven Agenten ist freigegebener Internetzugang notwendig. Vor seiner Aktivierung muss ein eigener Netzpfad folgende Zugriffe unabhängig vom Modell verhindern: LAN/private und lokale Adressen, Host-/Managementdienste, Metadatenendpunkte sowie alternative IPv6-/DNS-/Redirect-Wege. Ein getrenntes Netz/VLAN für den Server kann die Grenze zusätzlich absichern. Das ist ein noch zu implementierender und auf Ubuntu zu testender Teil; derzeit bleibt `--network=none` unverändert. Ein bloßes Promptverbot wäre keine Isolation.

Der Betreiber bleibt für SSH-Updates, Host-Patches und die Trennung der Verwaltungsrechte verantwortlich. Eine absolute Garantie gegen sämtliche Betriebssystem-/Containerfehler wird nicht behauptet. Nachgewiesene Isolation ist eine Startvoraussetzung.

## Wallet-Laufzeit vorbereiten

Der Betreiber hat Node v22.23.2 und npm 10.9.8 auf Ubuntu gemeldet. Die aktuelle
[Coinbase-Anleitung](https://docs.cdp.coinbase.com/agentic-wallet/cli/quickstart)
verlangt Node 24+. `deploy/Install-WalletRuntime.ps1 -SshTarget s340` installiert
eine getrennte Node-24-LTS-Laufzeit unter `/opt/kwod-wallet/node` aus dem offiziellen
Node-Downloadarchiv. Die SHA-256 wird mit der über HTTPS abgerufenen offiziellen
Prüfsummenliste verglichen. Die bisherige Node-Installation wird nicht ersetzt.
Der eigene Benutzer `kwod-wallet` erhält keine zusätzlichen Gruppen, eine
gesperrte Login-Shell und `/var/lib/kwod-wallet` als Home mit Modus 0700.

Lokal geprüft: Versionsauswahl, Prüfsummenauswertung, Bundle und PowerShell-Syntax.
Der Betreiber hat die erfolgreiche Ubuntu-Ausführung bestätigt: separate Node
v24.21.0, npm 11.19.0, `wallet_runtime=ready`, Home-Modus 0700.
Das Skript installiert noch kein `awal`,
erstellt kein Wallet, versendet keinen E-Mail-Code und startet keine Zahlungen
oder Modell-Worker. CLI-Version, Linux-Betrieb und Zahlungsfreigabe sind separat
zu prüfen. Die Benutzertrennung allein ist keine vollständige Netzwerkisolation.

Betreiberangabe: 40 EUR bereits für OpenRouter-Compute bezahlt; keine
Zahlungsmethode hinterlegt. Tatsächliche USD-Credits und Gebühren müssen noch
abgeglichen werden. Es wurde kein Buchungseintrag oder Birth-Event daraus
abgeleitet. Ziel ist Coinbase Agentic Wallet mit USDC auf Base. Das Wallet ist
noch nicht eingerichtet; automatischer OpenRouter-Nachkauf ist nicht implementiert.
Diese Coinbase-Wallet-Auswahl wurde inzwischen durch die nachfolgende Entscheidung
für ein eigenes Wallet ersetzt.

### Wallet-Startfehler auf Ubuntu (Betreiberausgabe)

`awal@2.12.1 status` und die Anmeldung scheitern bereits beim lokalen Serverstart.
Der nachgeladene Server unter `/var/lib/kwod-wallet/.local/share/awal-nodejs/server`
enthält Electron 37.10.3; dessen Programmdatei ist vorhanden. Der direkte Start
bricht mit einer SUID-Sandbox-Konfigurationsmeldung ab. Die SSH-Sitzung hat
zusätzlich kein DISPLAY. Das übersprungene Installationsskript ist daher nicht
als alleinige Ursache bestätigt.

`npm audit --omit=dev` meldet Electron und extract-zip als betroffene Pakete
mit hoher Schwere. Die konkrete Ausnutzbarkeit im Coinbase-Server ist nicht
nachgewiesen. Keine Freigabe zur Finanzierung aus diesem Prüfstand ableiten.
Nächster Schritt: aktuelle Coinbase-CLI- und installierte Server-Metadaten
prüfen, dann eine kompatible gepflegte Version ermitteln. Keine pauschale
Sandbox-Abschaltung, kein `npm audit fix --force` und kein SUID-Helfer im
benutzerbeschreibbaren Paketbaum als automatische Reparatur.

### Ergebnis der Versionsprüfung

Der Betreiber hat `npm view awal@latest` ausgeführt: aktuell 2.12.1. Der lokal
nachgeladene Server heißt `@coinbase/payments-mcp`, ebenfalls Version 2.12.1,
und deklariert Electron `^37.2.1`. Ein Update der CLI auf latest bietet nach
diesem Stand keinen belegten Lösungsweg. Die frühere Empfehlung dieser
CLI-Version war hinsichtlich Linux-Betrieb und abhängiger Komponenten unzureichend.

Die [CDP API-Key-Wallet](https://docs.cdp.coinbase.com/wallets/quickstart/api-key-auth)
ist eine Alternative ohne Electron. Ihre
[Preisregelung](https://docs.cdp.coinbase.com/wallets/pricing) sieht jedoch nach
5.000 kostenlosen Wallet-Operationen pro Monat 0,005 USD je Operation und
monatliche nachträgliche Rechnungen vor (Recherche 15.09.2026). Dies ist keine
belegte Begrenzung auf das Agenten-Wallet-Vermögen; daher nicht automatisch als
Ersatz aktivieren. Eine lokal verwaltete Signierkomponente für ein separates
Base-Wallet wäre eine andere Architektur und ist noch nicht implementiert.

## Eigenes Wallet: Ersteinrichtung und Sicherung

Der Betreiber hat ein eigenes Wallet auf Ubuntu ausgewählt. Die Arbeitskopie
des Schlüssels bleibt dort; eine verschlüsselte Sicherung soll auf den anderen
Laptop. Der Betreiber hat die erfolgreiche Ubuntu-Ausführung und den geprüften
Download nach Windows bestätigt:

- Empfangsadresse: `0x939DB49B1EAbB40C8afE5c6a12fB1694a242C5b6`.
- `wallet=ready`, `backup_verified=true`, `payments_enabled=false`, `worker_started=false`.
- Backup-SHA256: `1ccc375842fcc7d653cc5694b2d75412ef037d64b6c80e6a99d9a9cb26d09d42`.
- Verschlüsselte Windows-Datei: `C:\Users\minew\KWOD-Wallet-Backup\wallet-93200b9f89ff49999ed6475080c79ab9.json`.

Damit sind auch die im erfolgreichen Skriptlauf vorgeschalteten Kryptografie-
und Lesesperrenprüfungen auf Ubuntu durchlaufen. Der Betreiber hat klargestellt,
dass der Windows-Laptop das zweite Gerät ist: Die Sicherung liegt damit bereits
auf Server und separatem Gerät. Eine Wiederherstellung auf Windows wurde nicht
ausgeführt. Aus dieser Ausgabe
wird weder ein Guthaben noch eine Buchung oder Agentengeburt abgeleitet.

In **Windows PowerShell**, nicht innerhalb der Ubuntu-Shell:

```powershell
& "C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\New-LocalWallet.ps1" -SshTarget s340
```

Das Skript fragt zuerst nach dem Ubuntu-sudo-Passwort und anschließend nach
einem neuen Backup-Passwort (mindestens 16 Zeichen; lang und zufällig wählen).
Das Backup-Passwort wird verdeckt direkt auf Ubuntu eingegeben. Es wird weder
als Argument übergeben noch gespeichert. Sicher und getrennt vom Backup behalten.

Die Einrichtung legt `kwod-signer` ohne Zusatzgruppen und Login-Shell an.
`/var/lib/kwod-signer` hat Modus 0700. Dies ist absichtlich ein neuer Benutzer,
getrennt vom bisherigen npm/Electron-Verzeichnis unter `kwod-wallet`.
Der Arbeits-Schlüssel steht in `identity.json` mit Modus 0600. Diese Arbeitskopie
ist nicht passwortverschlüsselt, damit ein späterer isolierter Zahlungsdienst
automatisch arbeiten kann. Linux-root und der vertrauenswürdige Administrator
können weiterhin darauf zugreifen. Modell und Executor erhalten keinen Zugriff.

Die root-kontrollierte Python-Umgebung unter `/opt/kwod-signer` installiert
`eth-account==0.14.0` ausschließlich aus Wheels über PyPI, prüft die
Abhängigkeitskonsistenz und ersetzt keine vorhandene Node-Installation.
Die Version ist festgelegt; transitive Abhängigkeiten sind noch nicht vollständig
mit Hashes gesperrt. Dies ist kein vollständiges Sicherheits-Audit der Lieferkette.
Quellen: [Paketversion](https://pypi.org/project/eth-account/0.14.0/),
[Account und Keystore-Funktionen](https://eth-account.readthedocs.io/en/stable/eth_account.html).

Die eigentliche Erzeugung läuft als `kwod-signer` in einer temporären
systemd-Einheit mit privatem Netzwerk, gesperrter Rechteausweitung,
schreibgeschütztem System und deaktivierten Core-Dumps. Nur das Wallet-Verzeichnis
ist als persistentes Schreibziel freigegeben. Vor der Erzeugung werden ein
öffentlicher Adress-Testvektor, Verschlüsselung/Entschlüsselung und die Ablehnung
eines falschen Passworts geprüft. Es wird kein eigener Kryptografiealgorithmus
implementiert und keine experimentelle Seed-Phrase-Funktion benutzt.

`backup.json` enthält einen mit scrypt geschützten Ethereum-V3-Keystore.
Die Wiederherstellung wird aus den tatsächlich geschriebenen Bytes geprüft.
Ein bestehendes Wallet wird beim Wiederholen wiederverwendet; widersprüchliche,
verlinkte oder unsicher berechtigte Dateien führen zum Abbruch. Ein Abbruch nach
Schlüsselerzeugung kann bereits ein Wallet hinterlassen: nichts löschen, sondern
denselben Aufruf wiederholen oder den Fehler prüfen.

Erst nach erfolgreicher Prüfung wird ausschließlich die verschlüsselte Sicherung
unter `/var/lib/kwod-wallet-export/<SSH-UID>/backup.json` für den SSH-Administrator
bereitgestellt. Windows lädt sie nach `%USERPROFILE%\KWOD-Wallet-Backup` und
vergleicht SHA-256. Diese Datei auf den anderen Laptop kopieren; dort die Prüfsumme
gegen die heruntergeladene Datei vergleichen. Eine Wiederherstellung auf dem
zweiten Laptop wurde damit noch nicht ausgeführt. Passwort und Schlüssel niemals
in den Chat senden. Die Serverkopie wird nicht automatisch gelöscht.

Lokal bestanden: 8 Deployment-/Dateisicherheitstests und 3 Subtests;
PowerShell-Syntaxprüfung. Der Kryptografie-Paketdownload ist in der Codex-Umgebung
blockiert, daher laufen die echten Kryptografieprüfungen zwingend auf Ubuntu
vor der Schlüsselerzeugung. Die systemd-/Benutzergrenzen sind lokal unter Windows
nicht ausführbar; das Skript prüft auf Ubuntu die Lesesperre für `kwod-runtime`,
`kwod-public` und den bisherigen `kwod-wallet`-Benutzer.

Noch keine Einzahlung oder Agentengeburt auslösen. Ein dauerhafter Zahlungsdienst,
RPC-Anbindung, Gebührenabgleich und Modellwerkzeuge sind noch nicht implementiert.
Die Adresse ist eine EVM-Adresse; das geplante Zahlungsnetz ist Base. Netzwerk und
Asset müssen vor Finanzierung konkret geprüft werden.

## Isolierter Signierdienst: Vorbereitung

Der Betreiber hat die erfolgreiche Installation auf Ubuntu bestätigt:
`signer_selftest=passed`, `network_used=false`, `signer_installed=true`,
`isolation_checks=passed`. Der laufende Dienst meldet die bestehende Adresse
`0x939DB49B1EAbB40C8afE5c6a12fB1694a242C5b6`, Chain-ID 8453,
`signed_transactions=0`, `signing_enabled=false`, `broadcast_enabled=false`.
Der Modell-Worker wurde nicht gestartet. Verwendeter Windows-Aufruf:

```powershell
& "C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\Install-Signer.ps1" -SshTarget s340
```

Die Installation nutzt die vorhandene Wallet-Python-Umgebung und erzeugt keinen
neuen Schlüssel. Sie installiert `kwod-signer.service` und startet ihn im
Prüfmodus (`signing_enabled=false`). Die Dienstkonfiguration liegt root-kontrolliert
unter `/etc/kwod-signer.json`. Der Dienst bindet ausschließlich einen Unix-Socket
unter `/run/kwod-signer/payment.sock`. Die Runtime bekommt die Gruppe
`kwod-payments`; unabhängig von der Gruppe prüft der Dienst die tatsächliche
Linux-Benutzerkennung jedes Aufrufers. Nur root und die konfigurierte Runtime-UID
werden akzeptiert. Der Agent-Container erhält keinen Socket-Mount.

Der Dienst läuft als `kwod-signer`, ohne IP-Netzwerk oder IP-Socket-Familien,
ohne zusätzliche Capabilities und mit schreibgeschützter Schlüsseldatei.
Beim Start prüft er, dass IPv4-/IPv6-Sockets tatsächlich nicht erzeugt werden
können. Die verschlüsselte Backup-Datei ist im Dienst ausgeblendet. Der Installer
prüft erlaubten Runtime-Zugriff, verweigerten Public-/Alt-Wallet-Zugriff sowie
die gesonderte Peer-UID-Prüfung am Socket und die fehlenden Schlüsselleserechte.
Diese Prüfungen ersetzen keinen vollständigen Penetrationstest.

Die API bietet Status, Transaktionsvorschau und einen standardmäßig gesperrten
Signierpfad für ETH-/USDC-Transfers auf Base (Chain-ID 8453). Der Aufrufer kann
keinen RPC-Endpunkt, fremde Chain-ID oder beliebige Vertragsdaten einschleusen.
USDC-Transfers verwenden den von Circle dokumentierten Vertrag
`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`. Beträge werden in ganzzahligen
Basiseinheiten übergeben; es gibt keine Gleitkommaumrechnung.
Quellen: [Base-Netzwerk](https://docs.base.org/get-started/connect-to-base),
[Circle-Verträge](https://developers.circle.com/stablecoins/usdc-contract-addresses).

Signierte Transaktionen werden vor der Rückgabe im privaten SQLite-Journal
`/var/lib/kwod-signer/payments.sqlite` dauerhaft gespeichert. Wiederholungen
derselben Auftrags-ID liefern dieselben Bytes, auch nach Neustart. Abweichende
Inhalte zur selben ID oder ein anderer Auftrag mit bereits verwendeter Nonce
werden abgewiesen. Das verhindert doppelte Signierung bei Wiederholung eines
bekannten Auftrags; eine zukünftige Laufzeit muss dieselbe Auftrags-ID erhalten
und darf bei unklarem Ausgang nicht einfach eine neue Zahlung anlegen.

Noch kein vollständiger Zahlungsweg: Der Dienst sendet keine Transaktionen ins
Netz und prüft weder aktuellen Bestand noch Nonce oder vollständige Base-Gebühren.
RPC-Relay, Empfangsbelege/Finalität, Wiederanlauf nach unklarem Broadcast,
Gebührenersatz für festhängende Transaktionen und die Agentenwerkzeuge fehlen.
Signieren bleibt bis zu dieser Integration ausgeschaltet. Die Abschaltung ist
eine Entwicklungsstufe, keine spätere Einzelzahlungsfreigabe durch den Betreiber.

Lokal: 13 Signierkern-/Deploymenttests und 25 Subtests bestanden;
PowerShell-Syntax und Python-Kompilierung geprüft. Die Signierkern-Unit-Tests
verwenden einen ausdrücklich simulierten Signierer. Der Installer führt zusätzlich
echte Kryptografie mit einem öffentlichen Testschlüssel, Signatur-Recovery und
Journal-Wiederanlauf auf Ubuntu in einer netzlosen temporären Einheit aus. Dabei
wird weder der echte Wallet-Schlüssel zum Signieren verwendet noch eine Zahlung
übermittelt. Der Betreiber hat diese Ubuntu-Prüfungen inzwischen erfolgreich
bestätigt. Die folgenden Netzwerk-/Broadcast- und Produktionsprüfungen bleiben offen.

## API-Key und wirtschaftlicher Kreislauf

Der Entwicklungs-Key gehört ausschließlich in die geschützte Hostdatei `/etc/kwod/development.env`, Variable `KWOD_DEV_OPENAI_API_KEY`. Sie bleibt außerhalb des Quellpakets und des Executor-Mounts. Die Vorlage startet ohne diese Datei nicht. Entwicklungsabrechnung und späteres Lebensvermögen bleiben getrennt.

Wirtschaftliches Ziel: einmalig 50 € bereitstellen; der Agent entscheidet selbst, wie er arbeitet, Einnahmen erzielt und Compute finanziert. Ausgewählt sind OpenRouter für Compute und inzwischen ein eigenes Wallet. Laut Betreiber wurden 40 EUR bei OpenRouter eingezahlt. Die produktive Anbindung ist noch nicht implementiert.

Technisch müssen Zahlungseingang, wirklich verfügbarer Bestand, Gebühren/Rückerstattungen und Compute-Nachkauf zusammenpassen. Beispielhaft wurden Stripe-Zahlungsbestätigungen und Bankauszahlungen geprüft: Ein Zahlungsereignis kann automatisiert verarbeitet werden, doch Auszahlung und Verfügbarkeit des Geldes sind gesonderte Vorgänge. Das ist keine Festlegung auf Stripe oder ein bestimmtes Geschäftsmodell. Quellen: [Checkout-Fulfillment](https://docs.stripe.com/checkout/fulfillment), [Auszahlungen](https://docs.stripe.com/payouts).

Zusätzlich zum direkten OpenAI-Adapter ist nun ein OpenRouter-Responses-Adapter
lokal implementiert und offline geprüft. Er ist noch nicht auf Ubuntu ausgerollt
oder mit einem echten Modellaufruf getestet. Der OpenRouter-Key darf nicht einfach
in den bisherigen Entwicklungs-Key-Slot eingesetzt werden. OpenRouter hat den alten automatischen
Coinbase-Kaufendpunkt entfernt und verweist auf den Web-Checkout. Der autonome
Nachkauf ist deshalb weiterhin offen, auch mit einem funktionierenden eigenen
Wallet. Quelle: [OpenRouter Crypto API](https://openrouter.ai/docs/cookbook/administration/crypto-api).

### OpenRouter-Key sicher hinterlegen und ohne Inferenz prüfen

Der Betreiber hat die erfolgreiche Ubuntu-Ausführung bestätigt:
`openrouter_key=verified`, `management_key=false`, `key_usage_usd="0"`,
`key_stored=true`, `inference_tested=false`, `worker_started=false`.
Key-Limit und verbleibendes Key-Limit wurden als `null` gemeldet; es ist damit
kein numerisches Key-Limit ausgewiesen. Das Kontoguthaben bleibt über diesen
normalen Key unbekannt. Die gemeldete Nutzung null gilt für diesen Key und ist
kein Beleg für den gesamten Kontoverbrauch oder für die Höhe der USD-Credits.

Im separat finanzierten OpenRouter-Projektkonto einen normalen Inferenz-Key
anlegen: [API-Keys](https://openrouter.ai/settings/keys). Keinen Management- oder
Provisioning-Key verwenden. Danach in Windows PowerShell:

```powershell
& "C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\Connect-OpenRouter.ps1" -SshTarget s340
```

Der Key wird verdeckt direkt auf Ubuntu eingegeben und nach erfolgreicher Prüfung
in `/etc/kwod-openrouter/api.key` abgelegt (root:root, 0600, Verzeichnis 0700).
Die Runtime erhält vorerst keinen Lesezugriff. Ein bestehender Key wird bei
wiederholtem Aufruf wiederverwendet und nicht automatisch ersetzt.
Der Prüfer ruft ausschließlich `GET https://openrouter.ai/api/v1/key` auf;
Umgebungs-Proxies und Redirects sind deaktiviert. Er fragt keinen Modellendpunkt
ab, kauft kein Guthaben und startet keinen Worker. Key, Label und Kontokennung
erscheinen nicht in seiner Ausgabe. Fehlertexte des Anbieters werden nicht ausgegeben.

Die Ausgabe unterscheidet Key-Nutzung/-Limit von echtem Kontoguthaben.
`account_credit_balance_usd=null` bedeutet unbekannt, nicht null Dollar.
Die [Key-Metadaten](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key)
liefern das Key-Limit; die Abfrage des gesamten Kontoguthabens erfordert laut
[Credits-Dokumentation](https://openrouter.ai/docs/api/api-reference/credits/get-remaining-credits)
einen Management-Key. Ein erfolgreicher Key-Check bestätigt weder verfügbares
Guthaben noch Astra-Zugang oder fehlende gespeicherte Zahlungsmittel. Der Abgleich
der eingezahlten 40 EUR mit tatsächlichen USD-Credits erfolgt separat.

### Entwicklungsadapter und verbleibende Live-Prüfung

Der neue CLI-Schalter `run --openrouter-dev` verlangt ausschließlich
`KWOD_DEV_OPENROUTER_API_KEY` aus separat finanzierter Entwicklung. Er liest
den obigen Produktions-Key nicht. Diesen Entwicklungsmodus nicht mit dem
Lebensvermögen finanzieren. Vorhandene Entwicklungsdaten bleiben fest an ihren
bisherigen Provider gebunden; ein Wechsel erfordert ein eigenes Datenverzeichnis.
Der normale Ubuntu-Worker bleibt unverändert und ausgeschaltet.

Der Adapter verwendet den festen OpenRouter-Responses-Endpunkt, übersetzt das
festgelegte Modell auf `openai/gpt-6-astra`, verlangt `store=false`, erhält
Tool-Kontext und verschlüsselte Reasoning-Elemente und fordert OpenAI ohne
Provider-Fallback an. Es gibt keinen Modellwechsel. Redirects und automatische
HTTP-Wiederholungen sind deaktiviert. Timeout/5xx/ungültige Erfolgsantworten
werden als unklarer Ausgang behandelt. HTTP 402 ist ein Providerfehler, keine
lokal ausgelöste Agententod-Entscheidung.

Anbieter-Usage wird unverändert archiviert. Bestehende OpenAI-Direkttarife werden
nicht auf OpenRouter-Verbrauch angewendet. Ein verifizierter OpenRouter-
Kostenabgleich, die produktive Credential-Zustellung und ein separat bezahlter
Live-Test für Modell, Routing, Tools und Reasoning bleiben offen.
Quellen: [Responses](https://openrouter.ai/docs/api_reference/responses/overview),
[Reasoning](https://openrouter.ai/docs/api_reference/responses/reasoning),
[Routing](https://openrouter.ai/docs/guides/routing/provider-selection).

Lokal bestanden: 46 gezielte Tests und 26 Subtests (Adapter, Konto-Prüfer,
Runtime, Accounting, bestehender Provider und Deployment). PowerShell-Syntax
und Python-Kompilierung bestanden. Alle HTTP-Tests verwenden Offline-Mocks;
lokal wurden keine echten Modellaufrufe oder Key-Abfragen ausgeführt.
Die separate reine Key-Abfrage auf Ubuntu wurde inzwischen vom Betreiber
erfolgreich bestätigt. Ein echter Modellaufruf wurde weiterhin nicht ausgeführt.

### Öffentliche Netzwerk- und Modellprüfung

Der Betreiber hat die erfolgreiche Ubuntu-Ausführung bestätigt. Beobachtung am
2026-09-15T10:39:24.834810+00:00: Wallet auf Base (8453), abgeschlossener Block
51339224, Hash `0xc25dd78b34f99f6d9d3593e0957ddba6112ecae6be5bf0bcae17bdf0576b48ab`.
ETH und USDC wurden an diesem Block mit jeweils 0 beobachtet. OpenRouter listete
drei OpenAI-Endpunkte für `openai/gpt-6-astra`, jeweils mit beworbener Tools-
und Reasoning-Unterstützung. `inference_verified=false`, `model_calls=0`,
`transactions_sent=0`, `worker_started=false`. Dies ist eine datierte
RPC-/Katalogbeobachtung, keine dauerhafte Bestands- oder Verfügbarkeitsgarantie.
Verwendeter Windows-Aufruf:

```powershell
& "C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\Check-Readiness.ps1" -SshTarget s340
```

Der Prüfer läuft als normaler SSH-Benutzer ohne sudo. Er liest ausschließlich
die öffentliche Adresse aus der root-kontrollierten Signierdienst-Konfiguration.
Er öffnet keine Wallet- oder API-Schlüsseldatei, verändert keinen Dienst und
erteilt dem Agenten keinen Netzwerkzugang.

Base: Chain-ID 8453 prüfen, abgeschlossenen Block (`finalized`) wählen,
Vertragscode und USDC-Dezimalstellen prüfen, ETH und USDC für denselben Block
abfragen und dessen Hash danach erneut vergleichen. Ein mehr als eine Stunde
alter oder deutlich zukünftiger Block führt zu einer fehlgeschlagenen Prüfung.
Netzwerk- oder Datenfehler ergeben keinen erfundenen Nullbestand. ETH-Wei und
USDC-Basiseinheiten bleiben exakte Ganzzahlen; eine EUR-Bewertung erfolgt nicht.
Es wird die Aussage eines einzelnen RPC-Anbieters beobachtet, kein eigener
Konsens-/Light-Client-Beweis erzeugt.

OpenRouter: öffentlichen Endpunktkatalog für `openai/gpt-6-astra` lesen und
von OpenAI beworbene Tools-/Reasoning-Unterstützung ausgeben. Das bestätigt
weder kontospezifischen Modellzugang noch die vollständige Responses-Kompatibilität;
`catalog_only=true` und `inference_verified=false` bleiben ausdrücklich erhalten.

Netzwerk: nur `mainnet.base.org` und der feste OpenRouter-Katalogpfad sind erlaubt.
Alle aufgelösten Adressen müssen öffentlich sein. Die Verbindung wird zur bereits
geprüften IP aufgebaut; TLS prüft weiterhin den ursprünglichen Hostnamen.
Private/lokale, Multicast-, IPv4-mapped- und Übergangsadressen werden abgewiesen.
Es gibt keinen Proxy aus der Umgebung und keine Redirect-Verfolgung.
Dies ist ein eng begrenzter Leseprüfer, noch kein allgemeiner Internet-Broker
für den Agenten oder dauerhafter Zahlungs-Relay.

Lokal bestanden: 11 Tests und 12 Subtests für Leseprüfer und Deployment,
einschließlich exakter Beträge, falscher Chain, widersprüchlicher Blöcke,
veralteter Daten, RPC-Fehlern, Netzwerkzielgrenzen und TLS-Hostbindung.
PowerShell-Syntax und Python-Kompilierung geprüft. Die Tests verwenden
simulierte Netzwerkantworten; die separate reale Ubuntu-Ausgabe wurde inzwischen
vom Betreiber erfolgreich bestätigt.

Der Betreiber hat erneut 40 EUR als angezeigtes OpenRouter-Guthaben angegeben.
Diese Angabe bleibt eine Betreiberangabe in EUR; es wurde kein USD-Wert erfunden
oder daraus eine Buchung/Agentengeburt erzeugt.

Quellen: [Base-Netzwerk](https://docs.base.org/get-started/connect-to-base),
[JSON-RPC und Blockparameter](https://ethereum.org/developers/docs/apis/json-rpc/),
[OpenRouter-Modellendpunkte](https://openrouter.ai/docs/guides/routing/model-variants/overview).

SSH-Grundlage: [offizielle Ubuntu-OpenSSH-Dokumentation](https://ubuntu.com/server/docs/how-to/security/openssh-server/).
