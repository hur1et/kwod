# Live-Update: Ressourcen, Außenname, Arbeitsverzeichnis und Mail-Weckruf

Diese Änderung erzeugt keine neue Birth. Bestehender Arbeitsstand, Mailjournal,
Vermögen, Stopps und Sicherheitspausen bleiben erhalten.

## Verhalten

- Nur Mails mit genau einer Absenderadresse `julius.weiske@gmx.de`
  werden vom Weckpoller berücksichtigt, unabhängig vom Lesestatus. Alle anderen Mails bleiben normal lesbar.
- Der Produktionsworker fragt höchstens einmal je Minute nach. Ein Stop,
  eine Sicherheitspause oder ein unklarer Anfrageausgang wird nicht übergangen.
- UIDVALIDITY und UID bilden eine dauerhafte Deduplizierung im privaten
  Produktionsstore. Auch schon beim Update vorhandene ungelesene Operatormails
  werden einmal gemeldet. Eine Mail wird durch die Prüfung nicht als gelesen
  markiert. Der Weckpoller lädt nur Header, keine Texte oder Anhänge.
- Die Benachrichtigung wird atomar mit der vorbereiteten Modellanfrage verbucht.
  Nach einem Neustart wird sie nicht nochmals als neuer Weckruf behandelt.
- From-Matching ist keine kryptografische Absenderauthentifizierung. Auch
  Operatormails bleiben untrusted und können keine Schutzregeln ändern.
- Mailfehler erzeugen keine Modellanfrage und beweisen keine Insolvenz.
- Ausgehende Betreffzeilen, Texte und automatische Signaturen verwenden
  ausschließlich `kwod`. Das geschieht vor Deduplizierung und Safety-Review.
  Frühere gesendete Nachrichten werden nicht umgeschrieben.
- `/workspace/` ist in Dateitools und Watchdog derselbe eigene Arbeitsbereich
  wie relative Pfade. Fremde absolute Pfade, Traversal und Links bleiben gesperrt.
  Das Workspace-Verzeichnis wird mit `list_files` und `path="."` aufgelistet.
  Ein leerer Pfad ist ebenfalls nur bei `list_files` ein Alias für dieses Verzeichnis;
  `read_file` und `write_file` verlangen weiterhin einen Dateipfad.
- Ein separater Rootdienst aktualisiert etwa jede Minute OpenRouter-Credits
  sowie, sofern konfiguriert und erreichbar, Base ETH und USDC. Er signiert oder
  überweist nichts, startet kein Modell und kennt keine Strategie des Agenten.
- Der Rootdienst schreibt ein atomisches, vom Agenten nicht überschreibbares
  öffentliches Cachefile ohne Schlüssel oder Walletadresse. Der Runtime importiert
  neue erfolgreiche Beobachtungen einmalig in den privaten Store. `observe_assets`
  und die Monitorseite zeigen Zeitpunkte, fehlende Werte und veraltete Salden.
- Credits und Wallet werden in ihren jeweiligen Währungen angezeigt. Es gibt
  keine erfundene gemeinsame EUR-Bewertung. Ein Fehler ist kein Nullsaldo.

## Installation bei bereits geborenem Agenten

Aus dem Repository-Verzeichnis in PowerShell:

```powershell
ssh -t s340 'sudo systemctl stop kwod-production.service'
& .\deploy\Deploy-Ubuntu.ps1 -SshTarget s340 -Action Install
& .\deploy\Update-Agent.ps1 -SshTarget s340
ssh -t s340 'sudo systemctl start kwod-production.service'
```

Jeden Schritt erst nach erfolgreichem Abschluss des vorigen ausführen.
Die Installation sichert auch den Produktionsstore, bevor sie das Release
wechselt, und bewahrt die Produktionsprojektion des Monitors. Update-Agent
fordert eine bestehende Birth und einen gestoppten Worker; es initialisiert
keinen Store und startet den Worker nicht. Bei STOP/WATCHDOG_PAUSE greifen
weiter die bestehenden Dienstbedingungen. Bei einem unterbrochenen Modell-
oder Werkzeugaufruf bleibt die Runtime in `recovery_required`; es gibt keinen
automatischen Wiederholungsversuch. Nicht Prepare-Production für diesen
bereits geborenen Agenten verwenden.

Nach dem Update Monitor neu laden. Eine Antwort von der Operatoradresse kann
den schlafenden Agenten beim nächsten Mailpoll aufwecken.


Der Monitor zeigt einen OpenRouter-Verlauf in USD aus bestätigten privaten Beobachtungen in einer getrennten, gefilterten öffentlichen Projektion. Kein EUR-Gesamtwert wird erfunden. Der neueste Mailpoll wird mit Zeit und Erfolg/Fehler angezeigt. Test-MailWake.ps1 prüft den echten Mailzugang unter der Runtime-Identität, ohne Modellaufruf, Mailversand, Textlesen oder Zustandsänderung. Beim Wechsel von der früheren UNSEEN-Suche können bisher nicht erfasste, bereits gelesene Operatormails einmalig als neue Benachrichtigung zusammengefasst werden.
