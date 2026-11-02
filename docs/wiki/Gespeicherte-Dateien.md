# Gespeicherte Dateien verwalten

In Version 1.2.3 liegen gespeicherte Dateien in den jeweiligen Fachbereichen. Eine zentrale Dateimanageransicht mit wiederherstellbarem Papierkorb gehört noch nicht zur veröffentlichten Version.

## Dateien finden und herunterladen

| Dateiart | Bereich |
| --- | --- |
| CMS-Pakete | CMS-Archiv → Mein Archiv |
| Erweiterungs-ZIPs | Erweiterungen → Gespeicherte Pakete |
| Hochgeladene Akeeba-Archive | Backups → Backup importieren |
| Vom Manager erstellte Akeeba-Sicherungen | Projekt → Übersicht → Akeeba-Backups |
| Datei-/SQL-Projektsicherungen | Backups → Projektsicherungen |
| Kickstart-Versionen | System → Akeeba Kickstart |

Bei Erweiterungspaketen und Projektsicherungen stehen Downloadlinks zur Verfügung; bei erstellten Akeeba-Sicherungen einzelne Archivteile und gegebenenfalls ein Downloadpaket.

## Archive löschen

In der Backupansicht entfernt **Löschen** die gewählte Akeeba-Gruppe einschließlich ihrer Teile beziehungsweise die Projektsicherung endgültig. Vor dem Bestätigen eine benötigte externe Kopie anlegen. Backups für offene Wiederherstellungen und Pakete in laufender Verwendung werden geschützt.

Das Löschen eines gespeicherten Pakets oder Backup-Archivs entfernt keine daraus installierte Website. Die [Projektlöschung](Projekte.md) ist ein eigener Vorgang: Dabei legt der Manager Dateien und Metadaten unter `data/trash/` ab. Eine allgemeine Wiederherstellungsoberfläche oder einstellbare Aufbewahrungsfrist gibt es in 1.2.3 nicht.
