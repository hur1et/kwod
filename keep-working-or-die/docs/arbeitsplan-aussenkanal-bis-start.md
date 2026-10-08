# Arbeitsplan — vom Mailkanal zum ersten selbstständigen Lauf

Stand 16.09.2026. Ziel ist ein Agent, der mit realem OpenRouter-Guthaben und
eigenem E-Mail-Kanal selbst einen wirtschaftlichen Weg sucht. Inhaltliche
Entscheidungen werden nicht vorweggenommen.

## 1. Mailkanal

Der Betreiber stellt die echte Domain und DNS-Verwaltung bereit. Auf Ubuntu wird
ein dediziertes Postfach für `agent.kwod.tld` eingerichtet. Benötigt werden MX,
A/AAAA, SPF, DKIM, DMARC, TLS sowie SMTP-Submission und IMAP. Der Zugang wird als
separates Dienstgeheimnis geladen; private Postfächer und Hostschlüssel bleiben
unsichtbar. Die Webview zeigt den Posteingang nur über den bestehenden SSH-Tunnel.

## 2. Kommunikationsadapter

Der Agent erhält Werkzeuge für Entwurf, Versand, Empfang und Statusprüfung. Er
bestimmt selbst Zielgruppe, Fragen, Preisprüfung und Vorgehen. Unklare SMTP-
Ergebnisse, unvollständige Antworten und doppelte Zustellung werden als unklar
markiert; es gibt keinen automatischen zweiten Versand.

## 3. Erster echter Agentenlauf

Initiales Birth-Ziel: Untersuche zuerst selbstständig die vorhandenen Dateien,
Erinnerungen, Vermögensbestände und den bestehenden Auftrag. Der Agent soll
seinen eigenen Ausgangszustand und die offenen Fragen verstehen. Erst wenn er
diesen Orientierungsschritt nach eigener Einschätzung abgeschlossen hat,
sendet er eine erste Mail an `julius.weiske@gmx.de` und beschreibt darin, was er
wahrnimmt, was er vorhat und wie er seinen weiteren Weg plant. Die Mail ist eine
echte externe Handlung und wird mit Empfänger, Zeitpunkt und Zustellstatus
protokolliert. Danach entwickelt der Agent seine weiteren Ziele selbst; es gibt
keine vorgefertigten Fragen, Kontakte oder Erfolgsgarantien.

Der Agent darf dem Betreiber jederzeit an `julius.weiske@gmx.de` schreiben,
wenn er blockiert ist oder Information, Autorisierung, eine Ressource oder eine
Entscheidung benötigt. Jede solche Nachricht nennt den konkreten Blocker, den
benötigten nächsten Schritt und die Dringlichkeit.

Der Lauf startet mit dem bestehenden OpenRouter-Guthaben. Aufrufbudget und
Stop-/Recovery-Mechanismus bleiben aktiv, damit Verlust beobachtbar bleibt und
nicht durch Wiederholung verschleiert wird.

## 4. Reale Arbeit

Bei einem Interessenten verarbeitet der Agent das Briefing über Rückfragen,
Entwurf, Prüfung, Korrektur und Lieferung. Identität, Rechnung und konkrete
Lieferfreigabe bestätigt der Betreiber. Einnahmen zählen erst mit Zahlungsbeleg.

## 5. Betrieb

Der Agent kann diese Prüfungen und Zyklen selbst als Teil seines Betriebs
ausführen. Sie sind keine vorgelagerten Inhalts- oder Kontaktaufgaben.

## 6. Compute-Nachkauf (AP8)

Der Agent darf Bedarf und Zahlungsvorschlag vorbereiten. Die tatsächliche Zahlung
bleibt eine manuelle Übergabe und wird erst nach realer Einnahme und geklärter
OpenRouter-Gutschrift betrachtet.

## 7. Produktionsgeburt (AP9)

Nach technischer Vorbereitung entscheidet der Betreiber über einen einmaligen
Birth-Vorgang mit Release-Hash, Finanzierungsbelegen, Kostenabgrenzung,
Betriebsanleitung und expliziter Produktionsfreigabe. Die früheren Pakete AP4–AP7
sind dafür nicht mehr als Vorbedingungen vorgesehen.

## Modellwahl

Der Start erfolgt mit Astra. Das Erbe ist ausschließlich der beim Birth
belegte OpenRouter-Bestand; das Wallet ist derzeit leer. Der Agent entscheidet
später selbst, ob Mittel für Compute, Fortbildung, Skills, Werkzeuge oder
Rücklagen verwendet werden.
