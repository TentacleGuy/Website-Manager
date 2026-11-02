# Speicherorte und Umzug

Unter **System → Speicherorte** lassen sich die Bereiche für Projekte, Erweiterungen, CMS-Pakete, Akeeba-Backups und Projektsicherungen verwalten. Die Pfade beziehen sich auf den Docker-Rechner.

## Speicherbereich umstellen

1. Laufende Jobs und Uploads abschließen lassen.
2. Den gewünschten absoluten Zielpfad manuell eintragen.
3. **Speicherorte prüfen** wählen.
4. Erst nach erfolgreicher Prüfung **Daten kopieren und Speicherorte übernehmen** ausführen.
5. Den Neustart abwarten und die neuen Speicherorte prüfen.

Ein eingetragener Pfad ändert zunächst nur das Formular. Zielordner müssen leer, beschreibbar und ausreichend groß sein. Dateien werden kopiert und mit SHA-256 verglichen, bevor neue Einbindungen aktiviert werden. Betroffene PHP-Laufzeiten werden kurz angehalten. Alte Ordner werden nicht automatisch gelöscht. Bei einem Fehlschlag werden Einstellungen zurückgesetzt; angelegte Zielkopien können zur Prüfung liegen bleiben.

Die Pfade werden manuell eingetragen und beziehen sich auf den Installationsrechner. Externe Laufwerke müssen bei späteren Starts verfügbar sein.

## Was dadurch nicht umzieht

Datenbanken bleiben in ihren Docker-Volumes. Manager-Metadaten, Zertifikate und Schlüssel behalten den bisherigen Datenordner. Die Speicherumstellung ist deshalb kein vollständiger Umzug auf einen anderen Rechner.

## Vollständigen Umzug vorbereiten

- Für jede Website vollständige Akeeba- oder Datei-/SQL-Projektsicherungen erstellen und extern sichern.
- Manager-Metadaten und zugehörige Schlüssel sowie individuelle Einstellungen gesondert sichern, wenn sie übernommen werden sollen.
- Auf dem Zielrechner eine passende Manager-Umgebung einrichten und Websites wiederherstellen. Akeeba besitzt dafür einen Upload- und Importablauf. Der Rückimport eines Manager-ZIPs muss in 1.2.3 manuell erfolgen; ein automatischer Rückimport ist nicht enthalten.
- Anschließend Domains, PHP, Datenbank, Backend und wichtige Website-Funktionen prüfen.

Die Datenbanken liegen je Profil in getrennten Volumes; das frühere Standardvolume heißt `vmm-runtime_database`. Nicht von einem einzigen Volume für alle aktuellen Profile ausgehen. `docker compose down -v` entfernt Volumes und ist kein normaler Update- oder Umzugsschritt.
