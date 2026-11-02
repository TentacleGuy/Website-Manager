# Wiki-Stand und Dokumentationspflege

Das Benutzerhandbuch unter `docs/wiki/` und das GitHub-Wiki beschreiben ausschließlich die veröffentlichte Version **2.0.1**. GitHub führt sie als neuestes stabiles Release. Grundlage ist der Release-Tag `v2.0.1` auf Commit `fe969a40384c74cef097929e77e26c8a71e62c04`. Geprüft am 2. November 2026 nach der Veröffentlichung.

## Abgleich mit dem Release

- Menüpfade und sichtbare Funktionen: `app/static/index.html` sowie die in dieser Reihenfolge geladenen Dateien `app.js`, `workspace.js`, `refinements.js`, `icons.js`, `manager-ui.js`, `system-ui.js`, `recycle-ui.js` und `splash.js`.
- Projekte, Rückimport von Projektsicherungen und Benutzer: `app/project_service.py`, `app/project_workspace.py` und CMS-Helfer.
- Dateimanager und Papierkorb: `app/file_service.py`, `app/cleanup_service.py` und `app/recycle_service.py`.
- Zeitpläne und Systemverwaltung: `app/schedule_service.py`, `app/system_service.py` und `app/folder_picker.py`.
- Installation und Laufzeiten: Plattform-Installer, `scripts/setup.py`, `scripts/installer_config.py`, `app/environment_service.py`, `app/runtime.py`, `app/database_profiles.py` und `infra/runtime/Dockerfile`.
- Update-Erkennung: `app/update_service.py`, zusätzlich der Prüfer aus Version 1.2.3 gegen das neue Paket.

Die zuvor auf der Roadmap stehenden Themen sind bereits mit 2.0.0 veröffentlicht und in die regulären Anleitungen übernommen. Die Roadmap enthält derzeit keine weitere verbindliche Planung und keine erfundenen Termine oder Versionszusagen.

## Prüfungen zur Veröffentlichung

230 lokale Unit-Tests, JavaScript-/PHP-Syntaxprüfungen, Paketbau, Prüfsummen und der lokale Installations-/Updatepaket-Test waren erfolgreich. Die GitHub-Workflows für Release und Plattformprüfungen liefen für das Veröffentlichungstag erfolgreich. Eine echte Aktualisierung auf dem Rechner einer Kollegin ist damit nicht bestätigt.

## Pflege bei weiteren Releases

1. Tatsächlich veröffentlichtes stabiles Release und dessen Tag feststellen.
2. Betroffene Anleitungen gegen diesen Tag prüfen und erst dann aktualisieren.
3. Startseite, Seitennavigation und Fußzeile auf denselben Versionsstand bringen.
4. Erledigte Roadmap-Themen entfernen oder neu einordnen.
5. Links, Formatierung und Changelog prüfen und die Darstellung auf GitHub kontrollieren.

Die Regeln sind zusätzlich in `AGENTS.md` festgehalten. Versionshinweise werden ausschließlich aus `CHANGELOG.md` gepflegt.

## Übertragung ins Wiki

Die Quellen beginnen bei [wiki/Home.md](wiki/Home.md). `_Sidebar.md` und `_Footer.md` enthalten Navigation und Versionsstand. Relative lokale Seitenlinks tragen im Quellrepository `.md`; bei der Übertragung in das separate Wiki-Repository werden nur diese Endungen entfernt. Externe Links bleiben unverändert.

Wiki-Repository: `https://github.com/TentacleGuy/Website-Manager.wiki.git`. Inhaltliche Änderungen ausschließlich aus den gepflegten Quellen übertragen.

## Ergänzungen in 2.0.1

Startvideo und Systemeinstellung gegen `app/static/splash.js` und `splash.css` geprüft. Die Medienauslieferung einschließlich Byte-Range-Anfragen ist durch Tests abgedeckt. Das Papierkorb-Icon in der Projektliste verwendet die bestehende Bestätigung; in einer getrennten Vorschau wurden der Dialog und die Sperre bei laufenden Vorgängen geprüft. Die öffentlichen Updatepakete werden mit den Updateprüfern aus 1.2.3 und 2.0.0 geprüft.
