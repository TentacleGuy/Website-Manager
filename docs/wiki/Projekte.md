# Projekte erstellen und verwalten

Ein Projekt verbindet Website-Dateien, CMS, PHP-Laufzeit und eine eigene Projektdatenbank. Mehrere Projekte können dieselben Laufzeit- und Datenbankdienste verwenden.

## Neue Website erstellen

1. **CMS-Archiv** öffnen und WordPress oder Joomla auswählen.
2. Versionen abrufen und ein Paket herunterladen oder ein CMS-ZIP hochladen. Beim Upload werden CMS und Version erkannt.
3. Unter **Projekte** ein neues Projekt anlegen.
4. Einen Namen vergeben: kleiner Buchstabe am Anfang, danach kleine Buchstaben, Ziffern und Bindestriche; maximal 40 Zeichen.
5. Das archivierte CMS-Paket wählen. PHP und Datenbank automatisch oder ausdrücklich auswählen.
6. Für die automatische Einrichtung die Administratordaten eintragen. Das Passwort muss mindestens zwölf Zeichen haben.
7. Optional Erweiterungen zur Mitinstallation auswählen und das Projekt anlegen.

Die automatische CMS-Einrichtung unterstützt WordPress und Joomla ab 4.3. Für ältere Joomla-Versionen den CMS-Assistenten verwenden. Laufende Schritte und Fehler erscheinen unter [Aufgaben und Aktivitäten](Aufgaben-und-Aktivitaeten.md).

## Website öffnen

Die Projektübersicht ist eine Tabelle mit Suche, Spaltenfiltern und Sortierung. **Frontend**, **Backend**, **Projektdetails**, Akeeba-Aktionen und der Projektordner sind über die Zeilenaktionen erreichbar. Symbole zeigen ihre Beschriftung beim Darüberfahren.

Die Detailansicht enthält **Übersicht**, **Erweiterungen**, **Backups**, **Benutzer**, **Lizenzen**, **Datenbank** und **Einstellungen**. Unter **Datenbank** stehen Projektzugänge und der Link zu phpMyAdmin.

Eine vorhandene Website kann über [Akeeba-Import](Akeeba-Import.md) oder eine [gespeicherte Projektsicherung](Backups-und-Wiederherstellung.md) übernommen werden.

## Projekt löschen und zurückholen

In der Projektliste das **Papierkorb-Icon** in der Zeile des Projekts wählen. Alternativ unter den Projekteinstellungen **Projekt löschen** öffnen. Der Dialog zeigt den Projektnamen; dieser muss zur Bestätigung eingegeben werden. Während eines laufenden Projektvorgangs ist die Löschaktion deaktiviert. Vor dem Entfernen sichert der Manager eine vorhandene Projektdatenbank. Schlägt der Export fehl, bleibt das Projekt bestehen. Andere Projekte und ihre Laufzeiten werden nicht gelöscht.

Die Projektlöschung legt Dateien, Metadaten und gegebenenfalls SQL unter `data/trash/` ab; die Projektdatenbank bleibt zunächst erhalten. Das ist ein eigener Ablauf gegenüber der einstellbaren direkten Löschung gespeicherter Pakete.

In Version 2.0.3 lässt sich das Projekt unter **Dateimanager → Papierkorb → Wiederherstellen** zurückholen. Es erscheint gestoppt unter seinem ursprünglichen Namen. Ein belegter Name oder problematische Dateiverknüpfungen verhindern die automatische Wiederherstellung. Verfügbare Datenbanken werden wiederverwendet; andernfalls wird der gesicherte SQL-Export eingespielt. Die angezeigte Aufbewahrungsfrist beachten.
