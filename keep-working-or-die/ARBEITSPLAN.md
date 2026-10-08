# KEEP WORKING OR DIE — überprüfbarer Arbeitsplan

Stand: 16.09.2026. Dieser Plan ersetzt die bisherigen Prioritäten, nicht die
historischen Nachweise. **AP0 am 16.09.2026 lokal abgenommen**; aktuelle Abnahmestände
stehen in `reports/arbeitspakete.md`. AP1 lokal implementiert und geprüft;
Ubuntu-Abnahme noch offen (Anleitung: `docs/work-monitor.md`). Vorhandene
Komponenten werden wiederverwendet; die Zeiten beziehen sich auf Restarbeit.

## Ziel und zwei Abnahmestufen

**Stufe A: begleiteter echter Auftrag.** Ein echter Bedarf wird aufgenommen, der
Agent erstellt eine Lieferung, verarbeitet Rückmeldung und dokumentiert Aufwand
und gegebenenfalls einen tatsächlich belegten Zahlungseingang. Der Betreiber
entscheidet über externe Kommunikation und übernimmt zunächst nötige Abwicklung.

**Stufe B: selbstständig wirtschaftender Agent.** Innerhalb ausdrücklich freigegebener
Kanäle findet und bearbeitet er Arbeit, erhält Geld und kann daraus Compute nachkaufen.
Die einmalige Produktionsgeburt erfolgt erst nach belegter Finanzierung und Abnahme.
Ein guter Text, ein Interessenbekunden oder eine lokale Buchung ist kein Umsatz.

## Gesicherte Ausgangslage

- Ubuntu s340, persistenter Runtimekern, Dateiwerkzeuge, privates Journal,
  Kontextübergabe, Budgethinweise, Backup/Restore und öffentliche Leseansicht vorhanden.
- Zwei echte OpenRouter-Läufe: Trial01 teilweise abgeschlossen; Pilot02 mit
  fünf Aufrufen, einer Übergabe und allen vorgesehenen Dateien abgeschlossen.
- Agent wählte ein FAQ-Paket für Fahrradwerkstätten, produzierte Muster/Angebot
  und erkannte konkrete Schwächen. Nachfrage und 89-Euro-Preis sind ungetestet.
- Nutzerangaben: Trial01 0,09 USD; Pilot02 39,91 minus 39,60 = 0,31 USD;
  zusammen 0,40 USD. Zuordnung setzt keinen weiteren Verbrauch im Zeitraum voraus.
  Letzter gemeldeter Kontostand 39,60 USD, kein aktueller API-Abgleich.
- Kein Kunde, Auftrag oder Umsatz; kein Produktionsstart. Monitor zeigt Piloten
  noch nicht. Automatischer Compute-Nachkauf ist ungelöst und vorerst zurückgestellt.

## Arbeitspakete

| Paket | Konkretes Ergebnis | Überprüfbare Abnahme | Restaufwand | Abhängigkeit |
|---|---|---|---|---|
| AP0 — Stand sichern | Ein aktueller Statusbericht; Pilotnachweise, Versionsstand und Kostenbeobachtungen zusammengeführt | Jeder Status hat Datei/Test/Nutzernachweis; Originale unverändert; ein lokaler Gesamttest protokolliert; unbekannte Werte ausdrücklich benannt | 2–3 h | keine |
| AP1 — Beobachten und steuern | Piloten/Arbeitsläufe im Monitor mit Phase, Restbudget, Abschluss und Ergebnisverweisen; ein Start-/Status-/Stopweg | Ein Testlauf ist ohne Terminalraten verfolgbar; Stop beendet den Prozess; Neustart wiederholt keine Aktion; private Texte/Schlüssel erscheinen nicht im öffentlichen Monitor | 4–6 h | AP0 |
| AP2 — Kosten nachvollziehen | Kostenbericht pro Lauf und getrennte Kontostandsbeobachtungen | 0,09/0,31/39,60 USD als Nutzerangaben erfasst; verfügbare Provider-Usage je Versuch zugeordnet; fehlende Kosten bleiben unbekannt; kein doppelter Abzug; Quellen und Differenzen sichtbar | 3–5 h | AP0 |
| AP3 — Auftrag vollständig bearbeiten | Dauerhafter Ablauf Briefing → Rückfrage → Entwurf → Prüfung → Korrektur → Lieferung | Ein vorab festgelegter Musterauftrag mit einer fehlenden Angabe und einer Änderungsrunde läuft durch; fehlende Fakten werden erfragt; Abnahmekriterien erfüllt; Neustart an einer Zwischenstufe ohne Doppelarbeit | 6–10 h | AP0, AP2 |
| AP8 — Compute und weitere Mittel aus Einnahmen beschaffen | Verifizierter Zahlungs-/Beschaffungsablauf für Compute, Fortbildung, Skills oder Werkzeuge einschließlich Wiederholungsschutz | Der Agent begründet die Mittelverwendung selbst; ein separat autorisierter realer Kauf wird genau einmal abgewickelt und der erhaltene Gegenwert belegt; Netzwerkabbruch produziert keine Doppelzahlung | 6–12 h nach Schnittstellenklärung + unbestimmte Anbieterwartezeit | AP2; optional nach dem Start |
| AP9 — Produktionsgeburt | Fixiertes Release, OpenRouter-Finanzierungsbeleg, einmaliger Birth-Vorgang und Betriebsanleitung | OpenRouter-Bestand und Währung zum Birth belegt; Entwicklungsverbrauch gesondert behandelt; technische AP0–3 abgeschlossen; expliziter Produktionsstart und einmaliger Birth-Eintrag | 2–4 h | Mailkanal, Betreiberentscheidung |

## Reihenfolge und Entscheidungsstellen

1. **Jetzt AP0, dann AP1 und AP2.** Keine weiteren frei erfundenen Schreibpiloten.
2. AP3 und den Mailkanal fertigstellen.
3. AP4–AP7 sind für dieses Experiment gestrichen; der Agent soll Nachfrage,
   Kommunikation, Arbeit und Wiederholung selbst in seinem Lauf entwickeln.
4. AP9 ist danach die eigenständige Freigabe für den ersten produktiven Lauf.
5. AP8 wird erst aufgenommen, wenn der Agent selbst einen konkreten Bedarf für
   Compute, Fortbildung, Skills oder Werkzeuge begründet.

Der konkrete Restweg vom Mailkanal bis zur Produktionsfreigabe steht in
`docs/arbeitsplan-aussenkanal-bis-start.md`. Die früher geplanten Pakete AP4–AP7
bleiben als historische Planung nachvollziehbar, sind aber keine Voraussetzungen
mehr für den Start.

## Zeitschätzung

- **Stufe A einschließlich Betriebsabnahme (AP0–6): 27–44 aktive Arbeitsstunden**,
  dazu 24 Stunden Offline-Test und Rückmeldungen von außen.
- Bei 4–6 produktiven Arbeitsstunden pro Tag: grob **2–3 Kalenderwochen**, wenn
  Rückmeldungen innerhalb der angenommenen 3–10 Werktage eintreffen. Ohne Interessenten
  bleibt die technische Abnahme möglich, der echte Auftrag jedoch offen.
- **Zusätzlich für Produktionsstart und spätere Mittelbeschaffung (AP8–9): 10–16 aktive Stunden**
  nach geklärten Schnittstellen und Freigaben. Insgesamt **37–60 aktive Stunden**, grob **3–5 Wochen**
  bei zügigen externen Entscheidungen. Für AP8 gibt es derzeit keinen belastbaren
  Kalendertermin; Anbieterwartezeit kann diese Spanne deutlich überschreiten.
- Planungsgrößen für Entwicklung, Prüfung und Betreuung, keine Zusage autonomer
  Modelllaufzeit. Die bisherigen 0,40 USD erlauben keine seriöse Gesamtkostenprognose.
- Nach AP0 und AP3 Schätzung anhand tatsächlicher Restarbeit aktualisieren. Neue
  Anforderungen oder unzugängliche Kanäle separat ausweisen, nicht still einrechnen.

## Definition von „fertig“ für jedes Paket

Ein Paket wird erst geschlossen, wenn Ergebnisdatei, ausgeführte Prüfung, Datum,
beobachtetes Resultat und verbleibende Einschränkung in `reports/arbeitspakete.md`
stehen. Tests nur vorbereitet zählt nicht als bestanden; lokale Prüfung zählt
nicht als Linux-Abnahme. Menschliche Überarbeitung wird als Intervention markiert.

## Zuständigkeit und Grenzen

Der Entwicklungsassistent implementiert, prüft lokal und liefert fertige Ubuntu-
Befehle. Der Nutzer führt nötige SSH/sudo-Schritte aus und entscheidet über konkrete
externe Kontakte, Konto-/Geschäftsangaben und Produktionsstart. Kein Zugriff auf
Schlüsselinhalt, keine Zahlung, keine Nachricht und kein Dauerbetrieb allein aus
diesem Plan ableiten. Reversible Entwicklungsarbeit innerhalb der Pakete läuft
ohne wiederholte allgemeine Bestätigungsfragen weiter.
