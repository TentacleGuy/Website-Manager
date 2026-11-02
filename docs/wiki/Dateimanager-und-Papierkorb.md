# Dateimanager und Papierkorb

Der **Dateimanager** bündelt CMS- und Erweiterungspakete, Akeeba-Archive, Projektsicherungen, Kickstart-Dateien, Manager-Downloads und weitere verwaltete Dateien.

## Dateien finden

1. **Dateimanager → Alle Dateien** öffnen.
2. Die gemeinsame Suche verwenden; sie berücksichtigt die angezeigten Spalten.
3. Über Spaltenüberschriften sortieren.
4. **Dateien anzeigen** für Dateidetails und einzelne Downloads wählen.

Ein zusätzlicher Typ-Dropdown oder einzelne Spaltenfilter sind im Dateimanager von Version 2.0.1 nicht vorhanden. Die Projektübersicht hat dagegen eigene Spaltenfilter.

## Löschverhalten einstellen

Unter **System → Löschen & Papierkorb** zwischen Papierkorb und direkter endgültiger Löschung wählen. Die Standardwerte sind **Papierkorb** und **30 Tage** Aufbewahrung. Zulässig sind 1 bis 3650 Tage.

Die Frist gilt für künftige Löschungen. Bereits gespeicherte Ablaufdaten werden durch eine Änderung nicht angepasst. Abgelaufene Einträge werden bei laufendem Manager automatisch endgültig entfernt und protokolliert.

Löschdialoge in Bibliothek und Backupansicht verwenden dieselbe Regel. Laufende Installationen, Übertragungen, Wiederherstellungen und Prüfungen können die benötigten Dateien schützen. Bei mehrteiligen Akeeba-Backups wird die gesamte Gruppe behandelt. Das Löschen eines Pakets oder Backup-Archivs entfernt keine bereits daraus installierte Website.

## Wiederherstellen

1. **Dateimanager → Papierkorb** öffnen.
2. Name, Löschdatum und geplante endgültige Löschung prüfen.
3. **Wiederherstellen** wählen und bestätigen.

Dateien und zugehörige Bibliotheksdaten werden zurückgeholt. Vorhandene Zieldateien werden nicht überschrieben. Konflikte oder fehlende Dateien müssen zuerst geprüft werden. Für gelöschte Projekte gelten die zusätzlichen Regeln unter [Projekte](Projekte.md).

**Endgültig löschen** entfernt einen Papierkorbeintrag ohne weitere Wiederherstellungsmöglichkeit im Manager. Der Papierkorb ersetzt keine externe Sicherung.
