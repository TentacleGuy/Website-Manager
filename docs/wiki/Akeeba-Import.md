# Akeeba-Backup importieren

Der Import übernimmt eine vorhandene Joomla- oder WordPress-Website samt Datenbank in ein lokales Projekt. Hauptarchiv und sämtliche Teilarchive müssen zusammen vorliegen.

## Import durchführen

1. **Backups → Importvorlagen für Projekte → Importvorlage hochladen** öffnen.
2. Hauptarchiv und alle Teile gemeinsam hochladen: JPA, JPS oder ZIP sowie zugehörige J01… beziehungsweise Z01… . Pro Datei sind höchstens 4 GB zulässig.
3. Bei der gespeicherten Backupgruppe **Projekt erstellen** wählen.
4. Einen freien Projektnamen vergeben. CMS und Version werden aus den entpackten Dateien erkannt.
5. PHP und Datenbank automatisch auswählen lassen oder passende Werte vorgeben.
6. Bei einem verschlüsselten JPS-Archiv das Passwort eingeben. Es wird nicht in Projektmetadaten oder im Job gespeichert.
7. Kickstart automatisch wählen oder eine passende Version vorgeben und das Projekt anlegen.

Der Manager lädt Kickstart bei Bedarf von Akeeba. Unter **System → Akeeba Kickstart** lassen sich Versionen abrufen; eine eigene offizielle `kickstart.php` ist ebenfalls möglich.

## Was beim Import passiert

Kickstart entpackt die Dateien. Danach verwendet der Manager den mitgesicherten Akeeba-Installer, um die Datenbank einzuspielen und lokale Zugänge sowie URLs zu setzen. Unterstützt werden ältere ANGIE-Installer und die neuere Akeeba Backup Restoration Script CLI. Nach erfolgreichem Abschluss wird das Installationsverzeichnis entfernt.

Vor dem ersten Eingriff sichert der Manager die ursprüngliche `configuration.php` beziehungsweise `wp-config.php` sowie betroffene Serverdateien. Vorhandene `.htaccess`, `.user.ini` und `php.ini` bleiben als `.vmm-original` erhalten. Die CMS-Konfiguration wird als `.vmm-original.php` gesichert. Ein Manifest außerhalb der Website erfasst die Originaldateien mit Prüfsummen.

Nach der Akeeba-Installation übernimmt der Manager wieder die gesicherte CMS-Konfiguration und setzt die für das lokale Projekt nötigen Datenbank-, Pfad- und Routingwerte. Sitename und SMTP-Einstellungen werden dabei nicht durch Installer-Standardwerte ersetzt. Lokal kann der Mailversand deaktiviert sein; im späteren Backup steht die ursprüngliche Einstellung. WordPress verwendet lokale URL-Überlagerungen; die ursprünglichen URL-Werte in der Datenbank bleiben erhalten.

Bei späteren Projektbackups werden die gesicherten Originaldateien unter ihren regulären Namen ins Archiv geschrieben. Aktuelle Website-Inhalte und die aktuelle Projektdatenbank werden übernommen. Details und Grenzen stehen unter [Backups und Wiederherstellung](Backups-und-Wiederherstellung.md).

## Grenzen und erneuter Versuch

Die Website und ihr Akeeba-Installer müssen zur gewählten PHP-Version passen. Auch Kickstart selbst hat PHP-Anforderungen. Backups mit mehreren Datenbanken, externen Verzeichnissen oder einem nicht unterstützten CMS werden angehalten.

Ist die Extraktion abgeschlossen und nur die Datenbankwiederherstellung fehlgeschlagen, kann die Wiederherstellung im bestehenden Projekt fortgesetzt werden. Dieselbe Backupgruppe verwenden; vorhandene Website-Dateien werden nicht erneut entpackt. Bei einem Extraktionsfehler für einen neuen Versuch ein neues leeres Projekt verwenden und die Fehlermeldung prüfen.

Bei älteren Importen ohne gesicherte ursprüngliche CMS-Konfiguration kann das Update die verlorenen Werte nicht rekonstruieren. Dafür die ursprüngliche Importvorlage erneut in ein neues Projekt übernehmen.

Weiter: [Backups erstellen](Backups-und-Wiederherstellung.md), [PHP auswählen](Laufzeiten-und-Datenbanken.md).
