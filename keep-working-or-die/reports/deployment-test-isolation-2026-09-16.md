# Installationsprüfung von Live Safeguards getrennt

Die Betreiber-Ausgabe meldet 19 fehlgeschlagene Tests, deren temporäre Runtimes
in maintenance statt ihrer erwarteten Arbeitszustände landen. Der aktive
hostseitige WATCHDOG_REQUIRED-Marker erzwingt auch für diese Testdaten den
Live-Wächter. Die Root-Testprozesse sind keine autorisierten Gateway-Clients;
der sichere Ablehnungsweg verhindert dann Werkzeugarbeit. Das wurde lokal
mit erzwungenem Marker und nicht erreichbarem Socket reproduziert.

Keine Ausnahme oder Abschaltvariable wurde der Agentenruntime hinzugefügt.
Die breite Installationsprüfung läuft jetzt über test_release_isolated.py:
unshare erzeugt private Mount- und Netzwerk-Namespaces; deren Identitäten
müssen sich von beiden Eltern-Namespaces unterscheiden. Vor temporären
Bind-Mounts wird die Mount-Propagation auf private gestellt. Live-Schutzmarker,
Geheimnisse, Runtime-Daten und Dienst-/Docker-Sockets werden nur in diesem
Testbereich mit leeren read-only Ansichten verdeckt. Netzwerkzugriff ist
ausgeschlossen. Auch CLI-Unterprozesse erben diese Isolation. API-Key-
Umgebungsvariablen werden nicht an die Testprozesse weitergegeben.

Namespace- oder Mount-Fehler brechen die Prüfung ab; es gibt keinen unsicheren
Fallback und kein Überspringen der Tests. Live-Marker und Dienste bleiben
unverändert. Die gesonderten Docker-Ausführungsgrenztests unter der tatsächlichen
Runtime-Identität folgen weiterhin separat und verändern diesen Testaufbau nicht.

Lokale Abnahme: 199 Tests bestanden, 3 übersprungen, 153 Subtests bestanden.
Nachweis: deployment-isolation-tests-2026-09-16.xml. Namespace- und Mount-Aufrufe
werden hier unter Windows gemockt; die tatsächliche Ubuntu-Ausführung steht aus.
Source-Bundle enthält den neuen Runner. Kein SSH, kein Agenten-Modellaufruf,
keine Mail, Zahlung oder Birth wurde durch die lokale Korrektur ausgelöst.

Der gemeldete Installationsabbruch lag vor der current-Umschaltung und vor
Runtime-Backup/Migration. Zum erneuten Versuch das vorhandene Deploy-Ubuntu
mit -Action Install ausführen und danach Prepare-BrowserAccess.
