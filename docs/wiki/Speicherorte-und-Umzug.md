# Speicherorte und Umzug

Unter **System → Speicherorte** lassen sich die Bereiche für Projekte, Erweiterungen, CMS-Pakete, Akeeba-Backups und Projektsicherungen verwalten. Die Pfade beziehen sich auf den Docker-Rechner.

## Speicherbereich umstellen

1. Laufende Jobs und Uploads abschließen lassen.
2. Den gewünschten absoluten Zielpfad auswählen oder **Pfad manuell eingeben** verwenden.
3. **Speicherorte prüfen** wählen.
4. Erst nach erfolgreicher Prüfung **Daten kopieren und Speicherorte übernehmen** ausführen.
5. Den Neustart abwarten und die neuen Speicherorte prüfen.

Die Ordnerauswahl ändert zunächst nur das Formular. Zielordner müssen leer, beschreibbar und ausreichend groß sein. Dateien werden kopiert und mit SHA-256 verglichen, bevor neue Einbindungen aktiviert werden. Betroffene PHP-Laufzeiten werden kurz angehalten. Alte Ordner werden nicht automatisch gelöscht. Bei einem Fehlschlag werden Einstellungen zurückgesetzt; angelegte Zielkopien können zur Prüfung liegen bleiben.

Der native Dialog ist auf dem Installationsrechner über localhost verfügbar. Bei einem entfernten Browser Pfade manuell eingeben. Externe Laufwerke müssen bei späteren Starts verfügbar sein.

## Was dadurch nicht umzieht

Datenbanken bleiben in ihren Docker-Volumes. Manager-Metadaten, Zertifikate und Schlüssel behalten den bisherigen Datenordner. Die Speicherumstellung ist deshalb kein vollständiger Umzug auf einen anderen Rechner.

## Vollständigen Umzug vorbereiten

- Für jede Website vollständige Akeeba- oder Datei-/SQL-Projektsicherungen erstellen und extern sichern.
- Manager-Metadaten und zugehörige Schlüssel sowie individuelle Einstellungen gesondert sichern, wenn sie übernommen werden sollen.
- Auf dem Zielrechner eine passende Manager-Umgebung einrichten und Websites wiederherstellen. Akeeba besitzt dafür einen Upload- und Importablauf; Manager-ZIPs werden aus dem gespeicherten Exportbereich wiederhergestellt.
- Anschließend Domains, PHP, Datenbank, Backend und wichtige Website-Funktionen prüfen.

Die Datenbanken liegen je Profil in getrennten Volumes; das frühere Standardvolume heißt `vmm-runtime_database`. Nicht von einem einzigen Volume für alle aktuellen Profile ausgehen. `docker compose down -v` entfernt Volumes und ist kein normaler Update- oder Umzugsschritt.
