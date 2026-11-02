# Website Manager

Der Website Manager verwaltet lokale Joomla- und WordPress-Websites: Projekte erstellen, Akeeba-Backups importieren, Erweiterungen installieren und Websites mit passenden PHP- und Datenbankversionen betreiben.

## Aktuelle Version

Diese Anleitungen gelten für die veröffentlichte Version **1.2.3**. Grundlage ist der zugehörige [Release-Tag v1.2.3](https://github.com/TentacleGuy/Website-Manager/tree/v1.2.3). Das Wiki wird mit einer neuen Veröffentlichung auf deren Stand gebracht.

Geplante Weiterentwicklungen stehen ausschließlich in der [Roadmap](Roadmap.md). Sie sind kein Bestandteil der hier beschriebenen Version.

## Erste Schritte

1. [Voraussetzungen prüfen](Voraussetzungen.md).
2. Die Anleitung für [Windows](Installation-Windows.md), [macOS](Installation-macOS.md) oder [Linux](Installation-Linux.md) verwenden.
3. [Ein Projekt erstellen](Projekte.md) oder [ein Akeeba-Backup importieren](Akeeba-Import.md).

Die Installationspakete stehen im [Release v1.2.3](https://github.com/TentacleGuy/Website-Manager/releases/tag/v1.2.3). Das Dashboard öffnet sich unter **http://localhost:8090/** auf dem Installationsrechner.

## Anleitungen

| Aufgabe | Anleitung |
| --- | --- |
| Projekt erstellen, öffnen oder löschen | [Projekte](Projekte.md) |
| Vorhandene Website aus Akeeba übernehmen | [Akeeba-Import](Akeeba-Import.md) |
| PHP und Datenbank auswählen | [Laufzeiten und Datenbanken](Laufzeiten-und-Datenbanken.md) |
| Erweiterungen installieren und aktualisieren | [Erweiterungen und Lizenzen](Erweiterungen-und-Lizenzen.md) |
| CMS-Benutzer und gespeicherte Zugänge verwalten | [Benutzer und Zugangsdaten](Benutzer-und-Zugangsdaten.md) |
| Website sichern | [Backups](Backups-und-Wiederherstellung.md) |
| Gespeicherte Archive herunterladen oder entfernen | [Gespeicherte Dateien](Gespeicherte-Dateien.md) |
| Dateien auf einen anderen Datenträger verschieben | [Speicherorte und Umzug](Speicherorte-und-Umzug.md) |
| Ergebnisse und Fehlermeldungen nachlesen | [Aktivitäten](Aktivitaeten.md) |
| Infrastruktur, lokale Domains und Ordnerzugriff prüfen | [System und Fehlerbehebung](System-und-Fehlerbehebung.md) |
| Den Manager aktualisieren | [Manager-Updates](Manager-Updates.md) |
| Den veröffentlichten Quellcode ausführen und prüfen | [Entwicklung](Entwicklung.md) |

## Daten und Zugriff

Der Manager hat keine eigene Anmeldung. Die Standardinstallation bindet den Manager an den lokalen Rechner. Netzwerkzugriff muss bewusst eingerichtet werden; siehe [Voraussetzungen](Voraussetzungen.md).

Website-Dateien und Datenbanken werden getrennt gespeichert. Für einen vollständigen Umzug genügt es nicht, nur den Programmordner oder `data/` zu kopieren. Nutze [vollständige Sicherungen](Speicherorte-und-Umzug.md).
