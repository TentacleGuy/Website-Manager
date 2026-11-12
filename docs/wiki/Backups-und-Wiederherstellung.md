# Backups und Wiederherstellung

Unter **Backups** sind drei Verwendungszwecke getrennt:

| Bereich | Inhalt und Herkunft | Verwendung |
| --- | --- | --- |
| Importvorlagen für Projekte | Hochgeladene Akeeba-Archive mit allen Teilen | Daraus ein neues lokales Projekt erstellen |
| Backups für die Livesite | Im Manager aus Projekten erstellte Akeeba-Archive | Herunterladen und mit Akeeba auf dem Zielserver wiederherstellen |
| Lokale Projektsicherungen | Manager-ZIPs mit Website-Dateien und SQL-Export | Als neues lokales Projekt wiederherstellen |

Die Herkunft wird anhand der gespeicherten Backup-Metadaten unterschieden. Ein ZIP-Dateiname allein sagt nicht aus, ob es ein Akeeba-Archiv oder eine Manager-Projektsicherung ist.

## Projektsicherung erstellen

Unter **Projekt → Backups → Projektsicherung erstellen** einen Export starten. Die Sicherung enthält Website-Dateien, `database.sql` und `project.json`. Vor Erweiterungsinstallationen und Updates werden ebenfalls Projektsicherungen angelegt. Ergebnisse erscheinen unter **Backups** und im **Dateimanager**.

Projektsicherungen lassen sich unter **Backups → Lokale Projektsicherungen** über **Herunterladen** sichern. Kopien außerhalb des Installationsrechners aufbewahren, wenn sie vor dessen Ausfall schützen sollen.

## Projektsicherung als neues Projekt einspielen

1. Unter **Backups** oder **Projekt → Backups** eine gespeicherte Projektsicherung auswählen.
2. **Wiederherstellen** wählen.
3. Einen neuen, freien Projektnamen eingeben und bestätigen.
4. Den Vorgang unter **Aufgaben** beziehungsweise **Activity Log** verfolgen.

Der Manager legt ein neues Projekt mit eigener Projektdatenbank an. Ein bestehendes Projekt wird nicht überschrieben. Dieser Weg verarbeitet bereits im Exportbereich gespeicherte Manager-ZIPs; er ist kein allgemeiner Uploaddialog für beliebige Website-ZIPs.

## Akeeba-Sicherung erstellen

Im Projekt **Livesite-Backup erstellen** wählen, ein vorhandenes Akeeba-Profil auswählen und starten. Akeeba muss bereits in der Website installiert und seine unterstützte CLI verfügbar sein. Joomla benötigt die passende Konsolenanbindung, WordPress eine unterstützte CLI von Akeeba Backup Professional.

Der Manager übersteuert die Ausgabe für diesen Lauf auf ein lokales JPA-Archiv ohne Cloud-Nachbearbeitung, Löschquoten oder Abschluss-E-Mails. Gespeicherte Profile bleiben unverändert; ihre Filter wirken weiterhin. Der Manager ermittelt bei Joomla die Optionsdefinition der tatsächlich installierten Akeeba-CLI und übergibt die Einstellungen in der passenden Form. Ist diese Definition nicht lesbar, wird die Sicherung mit einer Fehlermeldung angehalten, statt stillschweigend lokale Profileinstellungen zu verwenden. Erst nach Abschluss und Prüfung der Archivteile wird der Download freigegeben.

Von Akeeba erfolgreich abgeschlossene Archive mit vorhandenen, geprüften Archivteilen stehen zum Download bereit. Ist der Nachweis ursprünglicher Server- oder CMS-Konfigurationen unvollständig, erscheint **Serverdateien ungeprüft** mit einer Erläuterung. Das bedeutet nicht, dass Akeeba das Archiv als defekt gemeldet hat. Es ist aber keine vom Manager bestätigte Produktionssicherung und wird nicht als geprüfte Wiederherstellungsquelle angeboten.

### Vorhandenes Backend-Archiv übernehmen

Wenn Akeeba im CMS-Backend ein erfolgreiches Backup zeigt, im Manager aber noch ein fehlgeschlagener Versuch steht:

1. Das Projekt starten und **Projekt → Backups → Vorhandene Backups abgleichen** wählen.
2. Den Abschluss im **Activity Log** abwarten.
3. **Neuestes Livesite-Backup herunterladen** oder den Download beim Archiveintrag verwenden.

Der Abgleich sucht die vom Manager gestarteten, bisher fehlgeschlagenen Versuche anhand ihrer Kennung und ihres Profils in Akeebas Datenbank. Er übernimmt ausschließlich abgeschlossene vollständige Website-Backups aus den freigegebenen Projekt- oder Backupordnern. Alle gemeldeten Teile müssen vorhanden sein; JPA- und ZIP-Archive werden anhand ihres Formats geprüft, bei geteilten Archiven im ersten Teil. Die Übernahme kopiert die Archive mit Prüfsummenvergleich und lässt die Originale im CMS unverändert. Sie benötigt entsprechend freien Speicherplatz. Beliebige ältere, direkt im CMS gestartete Backups werden damit nicht importiert.

Der Abgleich bestätigt keinen zuvor fehlenden Nachweis ursprünglicher Server- oder CMS-Dateien. Solche übernommenen Archive bleiben entsprechend als ungeprüft gekennzeichnet. Fehlende Dateien oder ein von Akeeba nicht bestätigter Abschluss bleiben echte Fehler; Details stehen im Backup-Eintrag und im Activity Log.

**Livesite-Backup herunterladen** lädt die neueste vollständige Sicherung. Bei mehreren Teilen wird ein äußeres Download-ZIP verwendet. Dieses zuerst entpacken und beim Import Hauptarchiv und alle Teile zusammen verwenden.

## Welche Einstellungen im Backup stehen

Bei importierten Projekten verwendet der Manager die vor dem ersten lokalen Eingriff gesicherten CMS- und Serverdateien. Im Archiv heißen sie wieder `configuration.php`, `wp-config.php`, `.htaccess` und gegebenenfalls `.user.ini` beziehungsweise `php.ini`. Die lokalen Varianten werden beim Schreiben des Archivs ersetzt; die laufende Website bleibt unverändert. Bekannte Manager-Login- und WordPress-Plugins werden weggelassen oder durch vorhandene gesicherte Originaldateien ersetzt.

Das Backup kombiniert die aktuellen Website-Inhalte und die aktuelle lokale Projektdatenbank mit den ursprünglichen Dateieinstellungen. Dazu gehören Sitename, Mailversand, SMTP-Zugänge und die ursprünglichen Datenbankzugänge. Beim Installieren auf einem anderen Server kann Akeeba die Datenbankzugänge und Zielpfade erneut anpassen. Ein deaktivierter lokaler Mailversand wird dadurch nicht als neue Produktionseinstellung übernommen.

Bei neuen Importen wird außerdem festgehalten, ob `configuration.bak.php` bereits in der Vorlage vorhanden war. Nur wenn die Datei erst durch den lokalen Installer entstanden ist, bleibt sie beim Backup draußen. Bei älteren Importen ohne diese Herkunftsinformation wird sie vorsichtshalber beibehalten.

Fehlen durch Prüfsummen erfasste Originaldateien oder wurden sie verändert, bricht der Export ab. Die Originale deshalb nicht löschen oder bearbeiten. Für ältere Importe ohne gesicherte CMS-Konfiguration ist die ursprüngliche Importvorlage nötig; ein Manager-Update allein rekonstruiert diese Einstellungen nicht. Wird bei einer solchen Akeeba-Sicherung der Nachweis nicht erbracht, bleibt sie als ungeprüft gekennzeichnet.

Nach einem Update eine neue Livesite-Sicherung erzeugen und deren Status prüfen. Bereits vorhandene ungeprüfte Archive werden durch das Update nicht nachträglich umgeschrieben oder als bestätigt eingestuft.

## Wiederherstellungsprüfung

Der Code enthält einen Prüfdienst für isolierte Wiederherstellungskopien mit separaten Containern und interner Netzwerkverbindung. Im aktuellen endgültigen Backup-Renderer ist dafür kein allgemeiner manueller Prüfknopf eingebunden. Ein vorhandener Prüfdienst bedeutet daher nicht, dass jedes gespeicherte Backup bereits geprüft wurde. Verschlüsselte JPS-Archive sind für diesen Prüfdienst nicht direkt geeignet; zuerst mit Passwort importieren.

Eine erfolgreiche technische Wiederherstellung ersetzt die Prüfung wichtiger Seiten, Anmeldung, Erweiterungen und projektspezifischer Abläufe.
