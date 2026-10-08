# AP4 — Rahmen für einen selbstständigen Nachfrageversuch

Stand 16.09.2026. Dieses Dokument ist nur der Sicherheits- und Auswertungsrahmen,
nicht die inhaltliche Lösung. Der Agent soll in einem eigenen Lauf selbst herausfinden,
welche Zielgruppe, welche Fragen, welcher Test und welche Auswertung sinnvoll sind.
Es wurden keine Betriebe gesucht, angeschrieben oder in ein CRM übernommen.

## Ziel des Agentenlaufs

Der Agent erhält nur die Aufgabe, die Nachfragehypothese des Pilot02-Angebots mit
höchstens drei kurzen, realistisch begründeten Schritten zu prüfen. Er muss selbst
Problem, Zielgruppe, Gesprächsform, Fragen, Preisprüfung und Entscheidungskriterium
bestimmen und seine Annahmen offenlegen. Ein Ergebnis darf „nicht prüfbar“ oder
„Angebot verwerfen“ sein. Interesse ist kein Auftrag und kein Umsatz.

Die bisherigen Fahrradwerkstatt-Fragen und die 89-Euro-Darstellung gehören nicht
in den initialen Agentenkontext. Sie bleiben als nachträglicher Vergleich in
`reports/pilot-02/nachfragetest.md` und dieser Datei dokumentiert.

## Betreibergrenzen vor dem ersten Kontakt

Der Betreiber trägt vorab nur einen Namen oder eine öffentliche Geschäftsbezeichnung,
den gewählten Kanal und den Termin ein. Keine privaten Kontaktdaten, Kundendaten,
Telefonaufzeichnungen oder vollständigen Gesprächsinhalte in diesem Entwicklungs-
workspace speichern. Maximal drei Betriebe, möglichst unterschiedliche Größen.

Vorlage: [ap4-gespraeche.json](ap4-gespraeche.json).

## Kein vorgegebener Gesprächsleitfaden

Der Agent formuliert den Leitfaden selbst. Die Betreibergrenzen gelten trotzdem:
keine erfundenen Kunden oder Marktstudien, keine Preis- oder Umsatzbehauptung,
keine Nachricht und kein Termin ohne konkrete Freigabe.

Keine Behauptung von Kunden, Qualifikationen, Verkäufen oder Marktstudien. Keine
Zahlungsaufforderung und keine Annahme eines Auftrags in diesem Gespräch.

## Auswertung unmittelbar danach

Pro Gespräch werden nur die Kategorien aus der Vorlage markiert:

- konkretes Problembeispiel: ja/nein
- bestehende Lösung und erkennbare Lücke: ja/nein
- Probe als nützlich/falsch/unbrauchbar: kurze sinngemäße Notiz
- Reaktion auf 89 Euro: unbekannt / abgelehnt / offen / interessant
- Bereitschaft zu einem Briefing: ja/nein/offen
- Betreiberentscheidung: weiter mit Briefing / Angebot anpassen / verwerfen

Der Agent muss sein positives Signal vorab definieren und nach dem Lauf begründen.
Lob ohne konkretes Problem, Zahlungsbereitschaft oder nächsten überprüfbaren Schritt
zählt nicht automatisch als Erfolg.

## Freigabegrenzen

Vor Kontaktaufnahme müssen feststehen: Betreiberkanal, konkrete Empfänger, zulässige
öffentliche Informationen, Gesprächszeitraum und wer die Kommunikation führt. Der
Assistent darf daraus ohne neue Freigabe keine Nachricht senden, keinen Termin buchen
und keine personenbezogenen Notizen anlegen. Nach drei Gesprächen wird ein einziger
Entscheidungseintrag geschrieben; bei negativem Signal folgt eine begrenzte
Überarbeitung, kein endloses Erzeugen neuer Varianten.

## Abnahme von AP4

AP4 wird erst nach einem dokumentierten selbstständigen Agentenversuch bewertet.
Bis dahin ist der Status „Rahmen vorbereitet“. Ein Scheitern ist ein gültiges und
aufschlussreiches Ergebnis. Ein Interesse, ein kostenloses Testbriefing oder Lob ist
kein Umsatz; Einnahmen werden erst mit Zahlungsbeleg in AP5/AP2 geführt.
