# Änderungsprotokoll pflegen

- Bei jeder Änderung an Verhalten, Oberfläche, Installation, Fehlerbehebung oder Sicherheit im selben Arbeitsschritt `CHANGELOG.md` aktualisieren. Nur relevante Auswirkungen für Benutzer beschreiben; keine Zugangsdaten, persönlichen Projektangaben oder internen Testdaten aufnehmen.
- Noch nicht veröffentlichte Änderungen unter `## [Unveröffentlicht]` ergänzen, nach `Neu`, `Verbessert` und `Behoben` ordnen. Bestehende passende Einträge präzisieren, statt denselben Punkt mehrfach aufzulisten. Keine Veröffentlichung oder Versionsnummer erfinden.
- Vor einer Veröffentlichung die betreffenden Einträge in einen neuen Abschnitt `## [X.Y.Z] - YYYY-MM-DD` übernehmen und `app/release.json` angleichen. Veröffentlichte Historie nur zur sachlichen Korrektur ändern. Unter `Unveröffentlicht` ohne offene Änderungen den Satz `Noch keine Änderungen.` verwenden.
- `python3 scripts/changelog.py` vor Abschluss prüfen. Releases zusätzlich mit `python3 scripts/changelog.py --tag vX.Y.Z` prüfen. GitHub-Versionshinweise werden daraus erzeugt; keine unabhängige zweite Liste pflegen.

# Wiki auf dem veröffentlichten Stand halten

- Reguläre Anleitungen unter `docs/wiki/` und im GitHub-Wiki beschreiben ausschließlich die aktuell veröffentlichte Version. Dafür das tatsächliche GitHub-Release und den zugehörigen Release-Tag prüfen; nicht allein `main`, Commit-Betreff oder `app/release.json` verwenden.
- Unveröffentlichte Funktionen nicht vorzeitig in Benutzeranleitungen aufnehmen. Geplante Themen ausschließlich auf der klar getrennten Seite `Roadmap.md` ohne erfundene Termine oder Versionszusagen beschreiben.
- Erst mit einer neuen Veröffentlichung die betroffenen Anleitungen, Startseite, Seitennavigation und Fußzeile gegen den neuen Release-Tag aktualisieren. Erledigte Roadmap-Themen entfernen oder neu einordnen. Versionshinweise weiterhin allein aus `CHANGELOG.md` beziehen.
- Die README des Entwicklungszweigs darf dessen aktuellen Stand beschreiben, muss diesen Unterschied zum Wiki aber klar nennen.
