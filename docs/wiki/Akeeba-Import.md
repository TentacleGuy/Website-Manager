# Akeeba-Backup importieren

Der Import übernimmt eine vorhandene Joomla- oder WordPress-Website samt Datenbank in ein lokales Projekt. Hauptarchiv und sämtliche Teilarchive müssen zusammen vorliegen.

## Import durchführen

1. **Backups → Backup importieren** öffnen.
2. Hauptarchiv und alle Teile gemeinsam hochladen: JPA, JPS oder ZIP sowie zugehörige J01… beziehungsweise Z01… . Pro Datei sind höchstens 4 GB zulässig.
3. Bei der gespeicherten Backupgruppe **Projekt erstellen** wählen.
4. Einen freien Projektnamen vergeben. CMS und Version werden aus den entpackten Dateien erkannt.
5. PHP und Datenbank automatisch auswählen lassen oder passende Werte vorgeben.
6. Bei einem verschlüsselten JPS-Archiv das Passwort eingeben. Es wird nicht in Projektmetadaten oder im Job gespeichert.
7. Kickstart automatisch wählen oder eine passende Version vorgeben und das Projekt anlegen.

Der Manager lädt Kickstart bei Bedarf von Akeeba. Unter **System → Akeeba Kickstart** lassen sich Versionen abrufen; eine eigene offizielle `kickstart.php` ist ebenfalls möglich.

## Was beim Import passiert

Kickstart entpackt die Dateien. Danach verwendet der Manager den mitgesicherten Akeeba-Installer, um die Datenbank einzuspielen und lokale Zugänge sowie URLs zu setzen. Unterstützt werden ältere ANGIE-Installer und die neuere Akeeba Backup Restoration Script CLI. Nach erfolgreichem Abschluss wird das Installationsverzeichnis entfernt.

Produktionsdateien `.htaccess`, `.user.ini` und `php.ini` bleiben als `.vmm-original` erhalten. Die lokale Laufzeit verwendet angepasste Einstellungen. Beim späteren Sichern werden die ursprünglichen Dateinamen im Archiv wiederhergestellt.

## Grenzen und erneuter Versuch

Die Website und ihr Akeeba-Installer müssen zur gewählten PHP-Version passen. Auch Kickstart selbst hat PHP-Anforderungen. Backups mit mehreren Datenbanken, externen Verzeichnissen oder einem nicht unterstützten CMS werden angehalten.

Ist die Extraktion abgeschlossen und nur die Datenbankwiederherstellung fehlgeschlagen, kann die Wiederherstellung im bestehenden Projekt fortgesetzt werden. Dieselbe Backupgruppe verwenden; vorhandene Website-Dateien werden nicht erneut entpackt. Bei einem Extraktionsfehler für einen neuen Versuch ein neues leeres Projekt verwenden und die Fehlermeldung prüfen.

Weiter: [Backups erstellen](Backups-und-Wiederherstellung.md), [PHP auswählen](Laufzeiten-und-Datenbanken.md).
