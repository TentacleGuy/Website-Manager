# Backups und Wiederherstellung

Version 1.2.3 unterscheidet native Akeeba-Archive und eigene ZIP-Projektsicherungen. Beide können Dateien und Datenbank enthalten, verwenden aber unterschiedliche Formate.

| Sicherung | Erstellen | Wiederherstellen |
| --- | --- | --- |
| Akeeba-Archiv | Native Akeeba-CLI im Projekt | [Akeeba-Import](Akeeba-Import.md) mit Hauptarchiv und allen Teilen |
| Manager-Projektsicherung | Datei-/SQL-Export des Managers | In Version 1.2.3 kein automatischer Rückimport im Manager |

## Projektsicherung erstellen

Unter **Projekt → Übersicht → Jetzt sichern** einen Export starten. Die Sicherung enthält Website-Dateien, `database.sql` und `project.json`. Vor Erweiterungsinstallationen und Updates werden ebenfalls Projektsicherungen angelegt.

Unter **Backups → Projektsicherungen** die ZIP-Datei herunterladen. Die Sicherungen können zur manuellen Wiederherstellung und zur externen Aufbewahrung verwendet werden. Der Manager bietet in 1.2.3 keine Schaltfläche zum Rückimport dieser ZIPs als neues Projekt.

## Akeeba-Sicherung erstellen

1. **Projekt → Übersicht → Akeeba-Backups** öffnen.
2. Eine vorhandene Akeeba-Profilnummer eintragen.
3. **Akeeba-Backup erstellen** wählen und das Ergebnis abwarten.
4. Die fertigen Archivteile herunterladen.

Akeeba muss bereits in der Website installiert und seine unterstützte CLI verfügbar sein. Joomla benötigt die passende Konsolenanbindung, WordPress eine unterstützte CLI von Akeeba Backup Professional. Der Manager installiert Akeeba nicht automatisch.

Der Manager übersteuert die Ausgabe für diesen Lauf auf ein lokales JPA-Archiv ohne Cloud-Nachbearbeitung, Löschquoten oder Abschluss-E-Mails. Gespeicherte Profile bleiben unverändert; ihre Filter wirken weiterhin. Erst nach Abschluss und Prüfung der Archivteile wird der Download freigegeben.

Bei mehreren Teilen steht **Alle Teile als Downloadpaket (.zip)** bereit. Dieses äußere ZIP zuerst entpacken und beim Import Hauptarchiv und alle Teile zusammen verwenden.

## Originale Serverkonfiguration

Beim Import gesicherte `.vmm-original`-Dateien werden im Archiv wieder als `.htaccess`, `.user.ini` beziehungsweise `php.ini` abgelegt. Die laufende lokale Website bleibt dabei unverändert. Auch ZIP-Projektsicherungen erhalten die ursprünglichen Dateinamen.

Eine erstellte Sicherung sollte außerhalb des Installationsrechners aufbewahrt und ihre Wiederherstellung vor einem Ernstfall geprüft werden. Eine vollständige automatische Wiederherstellungsprobe wird in dieser Version nicht als Oberflächenfunktion angeboten.
