# Wiki-Stand und Dokumentationspflege

Das Benutzerhandbuch unter `docs/wiki/` und das GitHub-Wiki beschreiben ausschließlich die veröffentlichte Version **2.0.4**. GitHub führt sie als neuestes stabiles Release. Grundlage ist der Release-Tag `v2.0.4` auf Commit `6f26630e652ffad2abb379116d18d04d996373b4`. Geprüft am 4. November 2026 nach der Veröffentlichung.

## Abgleich mit dem Release

- Menüpfade und sichtbare Funktionen: `app/static/index.html` sowie die in dieser Reihenfolge geladenen Dateien `app.js`, `workspace.js`, `refinements.js`, `icons.js`, `manager-ui.js`, `system-ui.js`, `recycle-ui.js` und `splash.js`.
- Projekte, Rückimport von Projektsicherungen und Benutzer: `app/project_service.py`, `app/project_workspace.py` und CMS-Helfer.
- Dateimanager und Papierkorb: `app/file_service.py`, `app/cleanup_service.py` und `app/recycle_service.py`.
- Zeitpläne und Systemverwaltung: `app/schedule_service.py`, `app/system_service.py` und `app/folder_picker.py`.
- Installation und Laufzeiten: Plattform-Installer, `scripts/setup.py`, `scripts/installer_config.py`, `app/environment_service.py`, `app/runtime.py`, `app/database_profiles.py` und `infra/runtime/Dockerfile`.
- Update-Erkennung: `app/update_service.py`, zusätzlich der Prüfer aus Version 1.2.3 gegen das neue Paket.

Die zuvor auf der Roadmap stehenden Themen sind bereits mit 2.0.0 veröffentlicht und in die regulären Anleitungen übernommen. Die Roadmap enthält derzeit keine weitere verbindliche Planung und keine erfundenen Termine oder Versionszusagen.

## Prüfungen zur Veröffentlichung

Der vollständige Testlauf in einer temporären Linux-Testumgebung umfasste 254 Tests und war erfolgreich; 9 Tests wurden mangels Plattformwerkzeugen übersprungen. Die PHP-gestützten Ablauf- und Dateitests wurden zusätzlich lokal ausgeführt. JavaScript-/PHP-Syntax, Paketbau, Paketversionen, ZIP-Inhalte und SHA-256-Prüfsummen wurden geprüft. Der GitHub-Release-Workflow und die Plattformprüfungen für Windows, macOS und Linux für `v2.0.4` waren erfolgreich; die veröffentlichten Update- und Installationspakete sowie ihre Prüfsummen sind vorhanden.

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

Importablauf, Originaldateien, Archiv-Zuordnung und Prüfstatus gegen `app/backup_service.py`, `project_files.py`, `akeeba_service.py` und die PHP-Helfer des Release-Tags geprüft. Backup-Übersicht, Projektaktionen und Startvideo gegen die endgültigen Renderer geprüft. Startseite, Navigation, Fußzeile und Versionsverweise wurden auf das veröffentlichte Release angeglichen. Die Roadmap enthält keine offenen Zusagen zu den veröffentlichten Änderungen. Versionshinweise bleiben ausschließlich im Changelog.
