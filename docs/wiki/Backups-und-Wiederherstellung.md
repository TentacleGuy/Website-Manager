# Backups und Wiederherstellung

Der Manager unterscheidet native Akeeba-Archive und eigene ZIP-Projektsicherungen. Beide können Dateien und Datenbank enthalten, verwenden aber unterschiedliche Wiederherstellungswege.

| Sicherung | Erstellen | Wiederherstellen |
| --- | --- | --- |
| Akeeba-Archiv | Native Akeeba-CLI im Projekt | [Akeeba-Import](Akeeba-Import.md) mit Hauptarchiv und allen Teilen |
| Manager-Projektsicherung | Datei-/SQL-Export des Managers | Gespeicherte Sicherung als neues Projekt einspielen |

## Projektsicherung erstellen

Unter **Projekt → Backups → Projektsicherung erstellen** einen Export starten. Die Sicherung enthält Website-Dateien, `database.sql` und `project.json`. Vor Erweiterungsinstallationen und Updates werden ebenfalls Projektsicherungen angelegt. Ergebnisse erscheinen unter **Backups** und im **Dateimanager**.

Dateien lassen sich über **Dateimanager → Dateien anzeigen → Herunterladen** sichern. Kopien außerhalb des Installationsrechners aufbewahren, wenn sie vor dessen Ausfall schützen sollen.

## Projektsicherung als neues Projekt einspielen

1. Unter **Backups** oder **Projekt → Backups** eine gespeicherte Projektsicherung auswählen.
2. **Wiederherstellen** wählen.
3. Einen neuen, freien Projektnamen eingeben und bestätigen.
4. Den Vorgang unter **Aufgaben** beziehungsweise **Activity Log** verfolgen.

Der Manager legt ein neues Projekt mit eigener Projektdatenbank an. Ein bestehendes Projekt wird nicht überschrieben. Dieser Weg verarbeitet bereits im Exportbereich gespeicherte Manager-ZIPs; er ist kein allgemeiner Uploaddialog für beliebige Website-ZIPs.

## Akeeba-Sicherung erstellen

Im Projekt **Akeeba Backup erstellen** wählen, ein vorhandenes Akeeba-Profil auswählen und starten. Akeeba muss bereits in der Website installiert und seine unterstützte CLI verfügbar sein. Joomla benötigt die passende Konsolenanbindung, WordPress eine unterstützte CLI von Akeeba Backup Professional.

Der Manager übersteuert die Ausgabe für diesen Lauf auf ein lokales JPA-Archiv ohne Cloud-Nachbearbeitung, Löschquoten oder Abschluss-E-Mails. Gespeicherte Profile bleiben unverändert; ihre Filter wirken weiterhin. Erst nach Abschluss und Prüfung der Archivteile wird der Download freigegeben.

**Akeeba Backup herunterladen** lädt die neueste vollständige Sicherung. Bei mehreren Teilen wird ein äußeres Download-ZIP verwendet. Dieses zuerst entpacken und beim Import Hauptarchiv und alle Teile zusammen verwenden.

## Wiederherstellungsprüfung

Der Code enthält einen Prüfdienst für isolierte Wiederherstellungskopien mit separaten Containern und interner Netzwerkverbindung. Im aktuellen endgültigen Backup-Renderer ist dafür kein allgemeiner manueller Prüfknopf eingebunden. Ein vorhandener Prüfdienst bedeutet daher nicht, dass jedes gespeicherte Backup bereits geprüft wurde. Verschlüsselte JPS-Archive sind für diesen Prüfdienst nicht direkt geeignet; zuerst mit Passwort importieren.

Eine erfolgreiche technische Wiederherstellung ersetzt die Prüfung wichtiger Seiten, Anmeldung, Erweiterungen und projektspezifischer Abläufe.
