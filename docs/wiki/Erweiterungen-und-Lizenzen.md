# Erweiterungen und Lizenzen

Die Bibliothek speichert Originalpakete für Joomla und WordPress. Ein gespeichertes Paket und eine im Projekt installierte Erweiterung sind getrennte Dinge.

## Paket hinzufügen und verwenden

1. **Erweiterungen** öffnen und das CMS auswählen.
2. **Erweiterung hinzufügen** wählen und ein ZIP hochladen. CMS, Name und Version werden erkannt.
3. Die Erweiterung auswählen und gespeicherte Versionen ansehen oder herunterladen.
4. Zum Installieren **Projekt → Erweiterungen → Erweiterung installieren** öffnen.
5. Ein Katalogpaket mit Version und Lizenz auswählen oder direkt ein ZIP hochladen. Das Projekt muss laufen und fertig eingerichtet sein.

Ein direkt hochgeladenes ZIP wird auch in der Bibliothek gespeichert. Passt es nicht zum CMS, wird es nicht im ausgewählten Projekt installiert. Themes werden nicht automatisch aktiviert.

## Updateprüfung und Übernahme aus einem Projekt

**Projekt → Erweiterungen → Updates prüfen** lädt den aktuellen CMS-Stand. Die zuvor angezeigte Liste ist ein gespeicherter Stand mit Prüfzeitpunkt. Verfügbare Updates stehen oben; Joomla-Core-Erweiterungen lassen sich gesondert filtern.

**In Bibliothek speichern** übernimmt eine unterstützte Updateanbindung und archiviert das verfügbare Originalpaket.

WordPress verwendet native Updateinformationen und bei WPML gegebenenfalls den vorhandenen OTGS Installer; Joomla verwendet registrierte Update-XML-Adressen. Projektbasierte Quellen benötigen das Herkunftsprojekt für frische Downloadlinks. Ohne unterstützten Originaldownload wird kein Herstellerpaket aus installierten Dateien nachgebaut.

## Updates installieren

Einzelne Erweiterungen über **Update installieren**, mehrere über **Alle Erweiterungen updaten** aktualisieren. Zuvor erstellt der Manager Datei-/SQL-Projektsicherungen. Gemeinsam verwendete PHP-Laufzeiten können dabei kurz pausieren. CMS-Updates werden im CMS-Backend durchgeführt.

## Lizenzen

Beim Bearbeiten einer Bibliothekserweiterung lässt sich ein globaler Lizenz-/API-Key speichern. Projektgebundene Schlüssel bleiben auf das betreffende Projekt beschränkt. Der Installationsdialog bietet die Lizenzwahl und das Anlegen einer neuen projektgebundenen Lizenz. Eine notwendige Herstelleraktivierung im CMS hängt weiterhin vom Anbieter ab.

Das Löschen eines gespeicherten ZIP entfernt keine installierte Erweiterung aus einer Website. Für die Aufbewahrung gilt die unter [Löschen und Papierkorb](Dateimanager-und-Papierkorb.md) eingestellte Regel.
