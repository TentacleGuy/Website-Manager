# Wiki-Stand und Dokumentationspflege

Das Benutzerhandbuch unter `docs/wiki/` und das GitHub-Wiki beschreiben ausschließlich die veröffentlichte Version **2.0.0**. GitHub führt sie als neuestes stabiles Release. Grundlage ist der Release-Tag `v2.0.0` auf Commit `bb558f54af0cb5079abe2160ca2cfec35190fcc7`. Geprüft am 2. November 2026 nach der Veröffentlichung.

## Abgleich mit dem Release

- Menüpfade und sichtbare Funktionen: `app/static/index.html` sowie die in dieser Reihenfolge geladenen Dateien `app.js`, `workspace.js`, `refinements.js`, `icons.js`, `manager-ui.js`, `system-ui.js` und `recycle-ui.js`.
- Projekte, Rückimport von Projektsicherungen und Benutzer: `app/project_service.py`, `app/project_workspace.py` und CMS-Helfer.
- Dateimanager und Papierkorb: `app/file_service.py`, `app/cleanup_service.py` und `app/recycle_service.py`.
- Zeitpläne und Systemverwaltung: `app/schedule_service.py`, `app/system_service.py` und `app/folder_picker.py`.
- Installation und Laufzeiten: Plattform-Installer, `scripts/setup.py`, `scripts/installer_config.py`, `app/environment_service.py`, `app/runtime.py`, `app/database_profiles.py` und `infra/runtime/Dockerfile`.
- Update-Erkennung: `app/update_service.py`, zusätzlich der Prüfer aus Version 1.2.3 gegen das neue Paket.

Die vorher auf der Roadmap stehenden Themen sind mit 2.0.0 veröffentlicht und in die regulären Anleitungen übernommen. Die Roadmap enthält derzeit keine weitere verbindliche Planung und keine erfundenen Termine oder Versionszusagen.

## Prüfungen zur Veröffentlichung

227 lokale Unit-Tests, JavaScript-/PHP-Syntaxprüfungen, Paketbau, Prüfsummen und der lokale Installations-/Updatepaket-Test waren erfolgreich. Die GitHub-Workflows für Release und Plattformprüfungen liefen für das Veröffentlichungstag erfolgreich. Eine echte Aktualisierung auf dem Rechner einer Kollegin ist damit nicht bestätigt.

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
