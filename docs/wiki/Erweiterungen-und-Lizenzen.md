# Erweiterungen und Lizenzen

Die Bibliothek speichert Originalpakete für Joomla und WordPress. Ein gespeichertes Paket und eine im Projekt installierte Erweiterung sind getrennte Dinge.

## Paket hinzufügen und installieren

1. **Erweiterungen** öffnen und WordPress oder Joomla auswählen.
2. **Erweiterung hinzufügen** wählen und ein ZIP hochladen. CMS, Name und Version werden erkannt.
3. In der Bibliothek die gewünschte Version wählen und **In Projekt installieren** öffnen.
4. Projekt, Version und gegebenenfalls Lizenz auswählen und bestätigen.

Alternativ **Projekt → Erweiterungen & Updates → Erweiterung installieren** öffnen und **Aus Katalog installieren** oder **ZIP-Datei hochladen** verwenden. Das Projekt muss laufen und fertig eingerichtet sein. Themes werden nicht automatisch aktiviert.

**Gespeicherte Pakete** zeigt die archivierten ZIP-Versionen samt Download-, Installations- und Löschaktionen. Ein gelöschtes ZIP entfernt keine installierte Erweiterung aus einer Website.

## Quelle aus einer Website übernehmen

Unter **Erweiterungen → Aus Projekt übernehmen** eine laufende, fertig eingerichtete Website wählen und **Erweiterungen auslesen** ausführen. Eine unterstützte Quelle kann übernommen oder das Originalpaket archiviert werden. Die Website wird dabei nicht aktualisiert.

WordPress verwendet native Updateinformationen und bei WPML gegebenenfalls den vorhandenen OTGS Installer; Joomla verwendet registrierte Update-XML-Adressen. Projektbasierte Quellen benötigen das Herkunftsprojekt für frische Downloadlinks. Ohne unterstützten Originaldownload wird kein Herstellerpaket aus installierten Dateien nachgebaut.

## Updates installieren

Unter **Projekt → Erweiterungen & Updates** stehen **Liste aktualisieren**, **Updates prüfen** und **Erweiterungsupdates installieren** bereit. Einzelne Erweiterungen besitzen eine **Update**-Aktion. CMS-Updates werden im CMS-Backend durchgeführt.

Vor Installationen und Sammelupdates erstellt der Manager Datei-/SQL-Projektsicherungen. Gemeinsam verwendete PHP-Laufzeiten können dafür kurz pausieren. Sicherungen stehen unter **Backups → Projektsicherungen** zum Download.

## Lizenzen

Beim Bearbeiten einer Bibliothekserweiterung lässt sich ein globaler Lizenz-/API-Key speichern. Abweichende Schlüssel werden über **Projektschlüssel** beziehungsweise **Projekt → Lizenzen** verwaltet und bleiben projektgebunden. Der Installationsdialog bietet die Auswahl passender gespeicherter Lizenzen. Eine notwendige Herstelleraktivierung im CMS hängt weiterhin vom Anbieter ab.
