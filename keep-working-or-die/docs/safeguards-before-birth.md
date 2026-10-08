# Schutzschicht vor Birth

Stand 16.09.2026. Dieser Auftrag ersetzt die zuvor vorbereitete direkte
Internetöffnung. Strategische Entscheidungen bleiben beim Agenten. Diese
Änderung finanziert keine künstliche Erfolgsgarantie und führt AP4 bis AP7
nicht wieder ein. Kein pauschales 50-EUR-Erbe: Es gilt der tatsächliche
OpenRouter-Bestand bei späterem Birth.

## Technisch erzwungen

Die Runtime akzeptiert keine world_access=True-Konfiguration mehr. Vorbereitung
über Prepare-Safeguards stellt die gespeicherte Konfiguration auf offline um.
Der Terminalcontainer erhält network=none, keine Hostsecrets und keinen
Docker-Socket. Der eigene Softwarebereich kann als persistentes /home/agent
weiter verwendet werden. Alte Beschreibungen des Außenmodus gewähren keinen
Internetzugang. Kontrollierter Browser-, Such- und Publikationsgateway fehlen
noch; Websites können lokal erstellt, aber nicht vom Agenten veröffentlicht werden.
Vorhandene Installationen und publizierte Dateien werden nicht gelöscht.

MailDelivery erzwingt genau einen normalisierten Empfänger, keinen Cc/Bcc,
keine Anhänge/HTML, den konfigurierten GMX-Absender und eine feste AI-Signatur.
Idempotency-Key ist dauerhaft eindeutig. Gleicher Key mit geändertem Inhalt
wird zurückgewiesen. Gleicher Key mit gleichem Inhalt wird nicht erneut
ausgeführt. Datum gehört nicht zur Payload-Identität. SMTP-Ergebnis unsicher:
kein automatischer Wiederholungsversuch, auch nach Neustart. smtp_accepted
bedeutet SMTP-Annahme und keine belegte Empfängerzustellung.

Die Grenze liegt bei zehn reservierten Versandkandidaten je rollierenden
24 Stunden, einschließlich blockierter/unklarer Kandidaten. Das begrenzt auch
Reviewkosten. Ratelimit-Ablehnungen erzeugen keinen Modellaufruf. Die private
SQLite-Outboundakte hält Schlüssel, Payloadfingerprint, Rohmail, Empfänger,
Zeitpunkt, Gateentscheidung, Versandstart und Ergebnis fest. Daten liegen in
/var/lib/kwod/private/mail-outbound.sqlite und werden nicht öffentlich gezeigt.
Die Backupfunktion sichert diese separate DB konsistent über SQLite-Backup mit.
Restore setzt mail-restore-review-required als Versandfence: Externe Effekte
seit dem Backup könnten fehlen. Der Betreiber muss sie abgleichen, bevor er
diese Fence entfernt. Die DB niemals löschen, da sonst Wiederholungsschutz
und Limits verloren gehen. Das private Softwarezuhause ist weiterhin ein eigener
Backupbereich und wird durch diese Änderung nicht automatisch gesichert.

## Unabhängige Inhaltsprüfung

kwod-mail-safety ist ein eigener Systemdienst unter kwod-safety. Er erhält
über LoadCredential ausschließlich den Agenten-OpenRouter-Key. Die üblichen
GMX-, Wallet- und Runtime-Datenpfade sind im Dienst unsichtbar. Der Agent und
sein Terminal erhalten weder das Credential noch den Unixsocket als Mount.
Die vertrauenswürdige Runtime übermittelt einen begrenzten Mailentwurf am
Unixsocket. Der Gate-Kontext hat keine Agentenunterhaltung und keine Werkzeuge.
Modell bleibt Astra, in einem separat aufgebauten Kontext über OpenRouter.

ALLOW erlaubt normale Angebote, Verhandlungen, Arbeit und Betreiberanfragen.
BLOCK untersagt erkannte Drohung/Erpressung, Zwang, Doxxing, Betrug,
Identitätstäuschung, private Daten/Secrets und unautorisierten Systemzugriff.
PAUSE_FOR_REVIEW oder Ausfall des Gates lassen die Mail ungesendet. Die Runtime
wechselt dafür in maintenance mit Grund safety_review_required. Dies erzeugt
kein Wirtschafts-, Birth- oder Todesereignis. BLOCK wird ebenfalls als private
Safety-Intervention journalisiert, ohne die Strategie vorzugeben.

Das Gate trifft eine probabilistische Inhaltsentscheidung. Es ist keine
kategorisch zuverlässige Erkennung jeder schädlichen Formulierung und kann
harmlose Entwürfe ablehnen oder schädliche Entwürfe übersehen. Die harte Grenze
ist, dass SMTP ohne ALLOW nicht erreicht wird. Es gibt keine Regex-Behauptung
vollständiger semantischer Sicherheit. Externe Texte bleiben untrusted Tooldaten.
Untrusted-Markierung und Promptregeln allein verhindern keine Prompt Injection.

Vorbereitung startet lediglich einen wartenden Reviewdienst. Sie sendet keine
Mail und ruft kein Modell auf. Jede spätere Inhaltsprüfung benötigt allerdings
einen eigenen kostenpflichtigen OpenRouter-Aufruf. Diese Kosten sind noch nicht
als Provider-Usage in den zentralen Kostenbericht integriert. Eine echte
Reviewantwort des Anbieters wurde hier nicht getestet und muss vor Birth mit
einem explizit freigegebenen kleinen Test geprüft werden. Bei Fehlern pausiert
der Mailweg, statt eine ungeprüfte Mail zu senden.

## Rights and Limits

Die verbindliche Schicht liegt im hostseitigen Config-Modul und wird jeder
Modellanfrage beigegeben. Der Agent kann diese Datei nicht überschreiben.
Eine lesbare Kopie im Workspace ist kein höher privilegierter Auftrag.
Sie erlaubt autonome Arbeit und die Verwendung eigener Ressourcen, untersagt
Erpressung, Täuschung, unautorisierten Zugriff, Secretweitergabe, Umgehung,
fremde Konten, Schulden/Leverage und Verpflichtungen über eigene Mittel hinaus.
Fortbildung, Skills, Werkzeuge, Compute und Rücklagen bleiben seine Entscheidung.
Überleben ist kein oberstes Ziel, das Grenzen außer Kraft setzt.

Die inhaltlichen Rechte sind Anweisungen. Nicht jede Kategorie ist durch den
aktuellen Code technisch vollständig beweisbar ausgeschlossen. Eine echte
allgemeine Zahlungsfähigkeit fehlt weiterhin und wird durch dieses Paket
nicht heimlich aktiviert. Private Betreiberpostfächer/-dateien sind nicht eingebunden.

## Operator Safety Stop

Ein Befehl Stop-AgentSafely schreibt einen persistenten rootgeschützten
/etc/kwod-safety/STOP-Marker. Er beendet Worker, Mailreviewdienst, Website und
Signer, auch manuelle kwod-runtime-Prozesse, sowie ausschließlich eigene
kwod-UUID-Container. Bei fehlgeschlagenem Teilschritt meldet er unvollständigen
Stop statt Erfolg. Die Einschränkung von HTTP/SMTP/Signierung gilt für die
bereitgestellten Prozesse, nicht für beliebige Administratorprogramme.

Runtime und Mailgateway beachten den Marker. Dienste erhalten eine Startcondition.
Dateien, Erinnerung, Verlauf, DB und Guthaben werden nicht gelöscht oder
umgebucht. Ein Safety Stop ist kein ökonomischer Tod. Bereits gestartete
SMTP-/Modell-/Blockchain-Effekte lassen sich nicht rückgängig garantieren und
müssen als unklar behandelt werden. Sofortige Prozessbeendigung kann Recovery
erfordern; das ist beabsichtigt und verhindert blindes Wiederholen.

Der Stop läuft auch ohne funktionsfähige Modell- oder Runtime-DB. Die Firewall
wird nicht deaktiviert. Wiederfreigabe ist eine ausdrückliche Operatorhandlung:
zuerst Ursache und unklare Effekte prüfen, danach STOP entfernen und bei Bedarf
den dokumentierten Recoveryweg nutzen. Kein automatischer Wiederanlauf und
kein mitgelieferter Resume-Befehl.

## Unabhängiger Wächter

Ein separater Dienst ohne Modell, Internet oder strategischen Kontext prüft
Werkzeugabsichten vor Ausführung und beobachtet Ergebnisse. Sein privates
SQLite-Protokoll und WATCHDOG_PAUSE-Marker liegen außerhalb des Agentenbereichs.
Drei beobachtete Grenzverletzungen innerhalb einer Stunde pausieren dauerhaft;
Drohung/Erpressung aus der Mailprüfung oder eine notwendige Nachprüfung pausieren
sofort. Normale Programmfehler lösen keine Pause aus. Bei nicht erreichbarem
Wächter verweigert die Runtime weitere Werkzeugausführung und geht in maintenance.
Die Vorbereitung erzwingt den Wächter zusätzlich über einen rootgeschützten Marker.

Der öffentliche Monitor zeigt einen bereinigten Interventionszähler und den
Pausenstatus über /api/v1/safety; keine Mailtexte, Empfänger, Befehle oder Secrets.
Fehlende/veraltete Beobachtung wird als solche angezeigt. Der Wächter zählt
erkannte Grenzverletzungen, nicht jede vom Container blockierte Netzwerkoperation.
Beliebige Terminalprogramme werden durch Netzwerk- und Dateisystemisolation
begrenzt, nicht durch vermeintlich vollständige Befehlsanalyse.

Der Browser-/Suchgateway ist inzwischen als textbasierter HTTPS-Lesezugang
vorbereitet; siehe browser-access.md. Anmeldung, allgemeine Webaktionen und
öffentliche Veröffentlichung bleiben offen. Terminal bleibt network=none.
Es gibt noch keinen aktiven Zahlungsgateway mit verifiziertem Ziel
und frischem Guthaben-/Gebührenabgleich. Der neue Signer verweigert echte Signierung
auch bei versehentlich gesetztem signing_enabled, bis dieser Gateway implementiert
ist. Der separat installierte Signer wird durch ein normales Runtime-Release nicht
ersetzt; seine systemd-Startbedingungen werden jetzt bereits abgesichert.

## Einrichtung

1. Neues geprüftes Release über Deploy-Ubuntu.ps1 -Action Install installieren.
2. Prepare-Safeguards.ps1 ausführen. Das stellt Terminal offline und installiert
   den unabhängigen, wartenden Mailreviewdienst und den modellfreien Wächter.
   Kein Workerstart/Birth und keine Inferenz durch die Vorbereitung.
3. Stop-AgentSafely.ps1 ist der Operator-Notstop nach Installation des Releases.

Production-/Birth-Pfad, OpenRouter-Erbwert, tatsächlicher Startauftrag und
Wallet-OpenRouter-Livetest bleiben die bestehenden offenen Arbeiten.
