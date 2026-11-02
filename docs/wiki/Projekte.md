# Projekte erstellen und verwalten

Ein Projekt verbindet Website-Dateien, CMS, PHP-Laufzeit und eine eigene Projektdatenbank. Mehrere Projekte können dieselben Laufzeit- und Datenbankdienste verwenden.

## Neue Website erstellen

1. **CMS-Archiv** öffnen. Unter **Versionen entdecken** das CMS wählen, Versionen abrufen und ein Paket herunterladen. Alternativ unter **Paket hochladen** CMS, Version und ZIP angeben. **Mein Archiv** zeigt gespeicherte Pakete.
2. Unter **Projekte** ein neues Projekt anlegen.
3. Einen Namen vergeben: kleiner Buchstabe am Anfang, danach kleine Buchstaben, Ziffern und Bindestriche; maximal 40 Zeichen.
4. Das archivierte CMS-Paket wählen. PHP und Datenbank automatisch oder ausdrücklich auswählen.
5. Für die automatische Einrichtung die Administratordaten eintragen. Das Passwort muss mindestens zwölf Zeichen haben.
6. Optional Erweiterungen zur Mitinstallation auswählen und das Projekt anlegen.

Die automatische CMS-Einrichtung unterstützt WordPress und Joomla ab 4.3. Für ältere Joomla-Versionen den CMS-Assistenten verwenden. Laufende Schritte und Fehler erscheinen im [Activity Log](Aktivitaeten.md).

## Website öffnen

Die Projektübersicht bietet eine Suche sowie Links für Frontend, Backend, phpMyAdmin und **Details →**. **Dateipfad öffnen** öffnet den Website-Ordner auf dem Installationsrechner.

Die Detailansicht enthält **Übersicht**, **Erweiterungen & Updates**, **Benutzer** und **Lizenzen**. In der Übersicht stehen PHP-Auswahl, Akeeba-Backups, **Jetzt sichern**, Datenbankzugänge und **Projekt löschen**.

Eine vorhandene Website lässt sich über den [Akeeba-Import](Akeeba-Import.md) übernehmen.

## Projekt löschen

In der Projektübersicht der Detailansicht **Projekt löschen** wählen und den Projektnamen bestätigen. Vor dem Entfernen sichert der Manager eine vorhandene Projektdatenbank. Schlägt der Export fehl, bleibt das Projekt bestehen. Andere Projekte und ihre Laufzeiten werden nicht gelöscht.

Die Dateien, Metadaten und gegebenenfalls der SQL-Export liegen danach unter `data/trash/`. Die Projektdatenbank bleibt erhalten. Version 1.2.3 bietet dafür keine Wiederherstellungsschaltfläche. Die aufbewahrten Daten nicht löschen, wenn eine spätere manuelle Wiederherstellung benötigt wird.
