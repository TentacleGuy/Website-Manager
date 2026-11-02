# Wiki-Stand und Dokumentationspflege

Das Benutzerhandbuch unter `docs/wiki/` und das GitHub-Wiki gelten ausschließlich für die veröffentlichte Version **1.2.3**. GitHub zeigt v1.2.3 als neuestes Release; der zugehörige lokale Release-Tag zeigt auf Commit `4cb6d54`. Geprüft am 2. November 2026.

## Quellen und Abgrenzung

- Funktionsumfang und Menüpfade: Code unter `v1.2.3`, insbesondere `app/static/app.js`, `app/static/index.html` und die zugehörigen Python-Dienste.
- Installation: Plattform-Installer und Einrichtungsskripte unter demselben Tag.
- Laufzeiten: `app/runtime.py`, `app/database_profiles.py`, `scripts/setup.py` und `infra/runtime/Dockerfile` unter demselben Tag.
- Veröffentlichung: [Release v1.2.3](https://github.com/TentacleGuy/Website-Manager/releases/tag/v1.2.3).

Die README im Entwicklungszweig beschreibt dessen aktuellen Code und kann Funktionen enthalten, die noch nicht veröffentlicht wurden. Solche Abweichungen machen eine Anleitung für das alte Release nicht automatisch falsch. Das öffentliche Benutzerhandbuch darf deshalb nicht ungeprüft aus der Entwicklungs-README übernommen werden.

## Bewusst getrennte Themen

| Handbuch für 1.2.3 | Separater Ausblick |
| --- | --- |
| Archive in ihren Fachbereichen verwalten, endgültige Löschung von Backups | Zentraler Dateimanager und wiederherstellbarer Papierkorb |
| Manager-Projektsicherungen erstellen und herunterladen | Manager-ZIPs als neues Projekt zurückspielen |
| Activity Log und manuelle Updateprüfung | Wiederkehrende Aufgaben und Zeitpläne |
| System → Infrastruktur, Umgebung prüfen | Dienste & Rechte und erweiterte Ordnerdialoge |
| CMS-Benutzer anlegen und Passwort zurücksetzen | Standardbenutzer, Einmal-Login und erweiterte Benutzerverwaltung |
| Erweiterungen → Aus Projekt übernehmen | Direkte Übernahme in der neuen Projektansicht |

Der Ausblick steht ausschließlich auf [Roadmap](wiki/Roadmap.md). Er ist keine zweite Liste von Versionshinweisen und enthält weder zugesagte Release-Version noch Termin.

## Aktualisierung bei einer Veröffentlichung

1. Die tatsächlich veröffentlichte Version und den zugehörigen Tag feststellen.
2. Geänderte Abläufe und sichtbare Menüpfade anhand dieses Tags prüfen.
3. Nur veröffentlichte Funktionen in die betroffenen Handbuchseiten übernehmen.
4. Versionsangabe auf Startseite, Navigation und Fußzeile gemeinsam aktualisieren.
5. Erledigte Roadmap-Themen entfernen oder neu einordnen.
6. Lokale Links, Formatierung und Changelog prüfen, dann das Wiki übertragen und auf GitHub kontrollieren.

Die Pflegevorgaben stehen zusätzlich in `AGENTS.md`. Vollständige Neuinstallationen unter allen drei Betriebssystemen und reale Docker-/CMS-Wiederherstellungen sind durch einen Dokumentationsabgleich nicht bestätigt.

## Wiki-Quellen und Veröffentlichung

Die Inhalte beginnen bei [wiki/Home.md](wiki/Home.md). `_Sidebar.md` und `_Footer.md` enthalten Navigation und Versionsstand. Die lokalen Dateien verwenden relative Markdown-Links mit `.md`; beim Übertragen in das separate Wiki-Git-Repository werden diese Endungen nur bei lokalen Seitenlinks entfernt. Externe Links bleiben unverändert.

Wiki-Repository: `https://github.com/TentacleGuy/Website-Manager.wiki.git`. Inhalte ausschließlich aus den gepflegten Quellen übertragen und keine getrennte zweite Textfassung pflegen. Versionshinweise bleiben in `CHANGELOG.md`.
