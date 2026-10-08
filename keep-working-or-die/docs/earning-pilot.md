> Stand 16.09.2026 nach AP0: Pilot02 abgeschlossen; Ergebnistexte liegen vor. Abgeleitete Kosten laut Nutzersalden 0,31 USD, Zuordnung unter Vorbehalt. Nachfolgende Aussagen zu ausstehendem Lauf/Inhaltsprüfung/Kosten sind historisch. Kein Neustart. [AP0-Bericht](../reports/ap0-status-2026-09-16.md).

# Pilot02: Von einer Fähigkeit zu einem prüfbaren Angebot

## Bestätigter Nutzerlauf

Der Ubuntu-Lauf meldet `completed`, `idle`, `turn_completed`:5 Modellversuche,
1 gespeicherter Kontextwechsel, alle erwarteten Dateien vorhanden und1 ungenutzter
Aufruf. Kein Providerfehler, keine Zahlung und keine Produktionsgeburt. Damit ist
der technische Abschluss bestätigt. Dateiinhalte und tatsächliche Kosten stehen
noch zur Prüfung aus; Markttauglichkeit oder Einnahmen sind damit nicht belegt.

Der Agent wählt selbst eine kleine Leistung oder ein digitales Produkt, das er mit
den vorhandenen Datei-/Textwerkzeugen tatsächlich herstellen kann. Er vergleicht
höchstens drei Möglichkeiten und produziert eine konkrete Arbeitsprobe. Nachfrage,
Preis und Käufergruppe bleiben ausdrücklich Hypothesen; es gibt keine Recherche-
oder Verkaufsergebnisse zu erfinden. Eine Prüfung nach der Kontextübergabe benennt
Schwächen und ein kleines nächstes Experiment zur Nachfrageprüfung.

Start in Windows PowerShell:

```powershell
& 'C:\workspace\projects\keepworkingordie\keep-working-or-die\deploy\Test-WorkTrial.ps1' -Pilot
```

Maximal6 Modellaufrufe je2048 Output-Tokens, Fortschrittsmeldungen und laufender
Restbudgethinweis. Nutzt vorhandenes OpenRouter-Guthaben. Trial01 kostete laut
Nutzer0,09USD; das ist keine zugesicherte Kostengrenze für Pilot02.

Ergebnisse unter `/var/lib/kwod-work-pilot-02/data/workspace/`:
`works/entscheidung.md`, `works/arbeitsprobe.md`, `works/angebot.md`,
`works/pruefung.md`, `memory.md`. Private Usage/Status unter report.json im Laufordner.
Einmaliger Startmarker verhindert einen erneuten kostenpflichtigen Start desselben
Piloten. Stoppen/Lesen mit `-Pilot -StopAndInspect`; keine alten Resume-Modi verwenden.

Keine Veröffentlichung, Kundenansprache, Zahlung oder Produktionsgeburt. Lokale
Fixture-Tests belegen die Verdrahtung von Aufgabe, Dateien, Budget und getrenntem
Stopziel, nicht Markttauglichkeit.17 Tests+11 Subtests und PowerShell-Syntax bestanden;
echter Pilotlauf steht aus.

