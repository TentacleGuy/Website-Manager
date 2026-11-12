# Wiki-Stand und Dokumentationspflege

Das Benutzerhandbuch unter `docs/wiki/` und das GitHub-Wiki beziehen sich auf die [veröffentlichte Version 2.0.8](https://github.com/TentacleGuy/Website-Manager/releases/tag/v2.0.8). Grundlage für den Abgleich ist der Release-Tag `v2.0.8` auf Commit `4cc05015d0c954200743ec2aeeeac7bbac5fd837`. Geprüft am 12. November 2026 nach der Veröffentlichung.

## Abgleich mit dem Release

- Menüpfade und sichtbare Funktionen: `app/static/index.html` sowie die in dieser Reihenfolge geladenen Dateien `app.js`, `workspace.js`, `refinements.js`, `icons.js`, `manager-ui.js`, `system-ui.js`, `recycle-ui.js` und `splash.js`.
- Projekte, Rückimport von Projektsicherungen und Benutzer: `app/project_service.py`, `app/project_workspace.py` und CMS-Helfer.
- Dateimanager und Papierkorb: `app/file_service.py`, `app/cleanup_service.py` und `app/recycle_service.py`.
- Zeitpläne, Systemverwaltung und lokale Desktop-Anbindung anhand der Dienste, der zugehörigen API und der macOS-Startskripte.
- Installation und Laufzeiten: Plattform-Installer, `scripts/setup.py`, `scripts/installer_config.py`, `app/environment_service.py`, `app/runtime.py`, `app/database_profiles.py` und `infra/runtime/Dockerfile`.
- Update-Erkennung und Paketprüfung anhand von `app/update_service.py` und den veröffentlichten Dateien.

Die zuvor auf der Roadmap stehenden Themen sind bereits mit 2.0.0 veröffentlicht und in die regulären Anleitungen übernommen. Die Roadmap enthält derzeit keine weitere verbindliche Planung und keine erfundenen Termine oder Versionszusagen.

## Prüfungen zur Veröffentlichung

Die 260 lokalen Tests und der lokale Plattformtest waren erfolgreich. Auf GitHub wurden der [Release-Workflow](https://github.com/TentacleGuy/Website-Manager/actions/runs/43168922088) und die [Plattformprüfungen](https://github.com/TentacleGuy/Website-Manager/actions/runs/43168921934) für `v2.0.8` erfolgreich abgeschlossen. Das veröffentlichte Update-ZIP und die drei Installations-ZIPs wurden heruntergeladen. Geprüft wurden die SHA-256-Prüfsummen, die ZIP-Inhalte und die enthaltene Programmversion.

Eine echte Wiederherstellung auf einem externen Zielserver und eine Aktualisierung auf einem anderen Rechner sind damit nicht bestätigt.

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

## Umfang des aktuellen Abgleichs

Startseite, Seitennavigation, Fußzeile und Versionslinks wurden auf den veröffentlichten Tag abgestimmt. Die Anleitungen für Projekte, Dateien, Speicherpfade, Aktualisierungen und Systembereiche folgen der Reihenfolge der geladenen Oberflächenskripte. Die Roadmap enthält keine offenen Zusagen zu veröffentlichten Änderungen. Versionshinweise stehen im Changelog.
