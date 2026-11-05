# Website Manager

Der Website Manager verwaltet lokale Joomla- und WordPress-Websites: Projekte erstellen, Akeeba-Backups importieren, Erweiterungen installieren und Websites mit passenden PHP- und Datenbankversionen betreiben.

## Aktuelle Version

Diese Anleitungen gelten für die veröffentlichte Version **2.0.5**. Grundlage ist der [Release-Tag v2.0.5](https://github.com/TentacleGuy/Website-Manager/tree/v2.0.5). Das Wiki wird mit einer neuen Veröffentlichung auf deren Stand gebracht. Geplante Weiterentwicklungen stehen separat in der [Roadmap](Roadmap.md).

## Erste Schritte

1. [Voraussetzungen prüfen](Voraussetzungen.md).
2. Die Anleitung für [Windows](Installation-Windows.md), [macOS](Installation-macOS.md) oder [Linux](Installation-Linux.md) verwenden.
3. [Ein Projekt erstellen](Projekte.md) oder [ein Akeeba-Backup importieren](Akeeba-Import.md).

Die Installationspakete stehen im [Release v2.0.5](https://github.com/TentacleGuy/Website-Manager/releases/tag/v2.0.5). Das Dashboard öffnet sich unter **http://localhost:8090/** auf dem Installationsrechner.

## Anleitungen

| Aufgabe | Anleitung |
| --- | --- |
| Projekt erstellen, öffnen oder löschen | [Projekte](Projekte.md) |
| Vorhandene Website aus Akeeba übernehmen | [Akeeba-Import](Akeeba-Import.md) |
| PHP und Datenbank auswählen | [Laufzeiten und Datenbanken](Laufzeiten-und-Datenbanken.md) |
| Plugins, Themes und Joomla-Erweiterungen verwalten | [Erweiterungen und Lizenzen](Erweiterungen-und-Lizenzen.md) |
| CMS-Benutzer und Backend-Login verwalten | [Benutzer und Zugangsdaten](Benutzer-und-Zugangsdaten.md) |
| Importvorlagen, Livesite-Backups und lokale Sicherungen verwalten | [Backups und Wiederherstellung](Backups-und-Wiederherstellung.md) |
| Pakete aufräumen oder aus dem Papierkorb zurückholen | [Dateimanager und Papierkorb](Dateimanager-und-Papierkorb.md) |
| Dateien auf einen anderen Datenträger verschieben | [Speicherorte und Umzug](Speicherorte-und-Umzug.md) |
| Prüfungen und Sicherungen planen | [Aufgaben und Aktivitäten](Aufgaben-und-Aktivitaeten.md) |
| Dienste, lokale Domains und Ordnerzugriff prüfen | [System und Fehlerbehebung](System-und-Fehlerbehebung.md) |
| Startvideo ein- oder ausschalten | [Startvideo](Startvideo.md) |
| Den Manager aktualisieren | [Manager-Updates](Manager-Updates.md) |
| Aus Quellcode starten, testen oder veröffentlichen | [Entwicklung](Entwicklung.md) |

## Daten und Zugriff

Der Manager hat keine eigene Anmeldung. Die Standardinstallation bindet den Manager an den lokalen Rechner. Netzwerkzugriff muss bewusst eingerichtet werden; siehe [Voraussetzungen](Voraussetzungen.md).

Website-Dateien und Datenbanken werden getrennt gespeichert. Für einen vollständigen Umzug genügt es nicht, nur den Programmordner oder `data/` zu kopieren. Nutze [vollständige Sicherungen](Speicherorte-und-Umzug.md).
