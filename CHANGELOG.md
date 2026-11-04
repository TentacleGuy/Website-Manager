# Änderungsprotokoll

Alle wesentlichen Änderungen am Website Manager werden hier dokumentiert. Neue Änderungen werden zunächst unter **Unveröffentlicht** ergänzt und bei einer Veröffentlichung mit Versionsnummer und Datum versehen. Die veröffentlichten Einträge wurden anhand der Git-Historie rekonstruiert; **Unveröffentlicht** beschreibt den aktuellen Entwicklungsstand und ist noch kein verfügbares GitHub-Update.

## [Unveröffentlicht]

Noch keine Änderungen.

## [2.0.4] - 2026-11-04

### Verbessert

- Die Backup-Übersicht trennt hochgeladene Importvorlagen für neue Projekte, aus Projekten erstellte Akeeba-Backups für die Livesite und lokale Manager-Projektsicherungen. Projektansicht und Erstellungsdialog benennen den jeweiligen Verwendungszweck.

- Startvideo jederzeit per Kreuz oder Escape schließbar. Die Wiedergabe startet ohne zusätzlichen Klick; blockiert der Browser Autoplay mit Ton, läuft das Video automatisch stumm. Unter dem Video bleibt nur die Checkbox „Beim nächsten Start abspielen“.

### Behoben

- WordPress-Importe behalten die ursprünglichen Datenbank-URLs und Inhalte; lokale URLs werden zur Laufzeit angewendet. Ursprüngliche WordPress-Konfigurationen und vorhandene Dateien an den Manager-Pluginpfaden werden für den Export erhalten. Neue lokale Lizenz- und Updateanbindungen speichern ihre Manager-Einstellungen außerhalb der Website statt in den exportierten WordPress-Optionen.

- Vor dem Import werden ursprüngliche CMS-Konfigurationen und betroffene Serverdateien mit Prüfsummen gesichert. Nach der Akeeba-Installation werden ursprüngliche Einstellungen vor den lokalen DB- und Pfadanpassungen wieder übernommen. Projektbackups kombinieren aktuelle Inhalte und Datenbank mit diesen Originaldateien, einschließlich Sitename, Mailversand, SMTP- und ursprünglichen Datenbankzugängen; lokale Managerdateien bleiben draußen. Fehlende oder veränderte Originale verhindern einen unbemerkten Export lokaler Einstellungen. Die lokale Website bleibt beim Backup unverändert.
- Abgeschlossene Akeeba-ZIP-Backups und ihre Archivteile werden beim Abgleich anhand ihres tatsächlichen Formats einschließlich des Akeeba-ZIP-Vorspanns „PK00“ erkannt, statt als ungültige JPA-Sicherung abgelehnt zu werden.

## [2.0.3] - 2026-11-03

### Behoben

- Vorhandene, vom Manager gestartete Akeeba-Backups lassen sich mit dem CMS-Backend abgleichen und aus dem Projektordner übernehmen, ohne die Originalarchive zu verschieben. Alle gemeldeten Archivteile und der JPA-Dateikopf im ersten Teil werden geprüft. Downloads funktionieren auch bei fehlendem Nachweis ursprünglicher Serverdateien; diese Archive werden ausdrücklich als ungeprüft statt als defekt gekennzeichnet und nicht als geprüfte Wiederherstellungsquelle angeboten.

## [2.0.2] - 2026-11-03

### Verbessert

- Konfiguration und neue Installationen verwenden `TENTACLE_*` statt `VMM_*`. Bestehende Einstellungen bleiben kompatibel; bei beiden Namen hat der Tentacle-Wert Vorrang.

- Neue Docker-Laufzeiten und Manager-/PHP-Images verwenden Tentacle-Namen. Bestehende gemeinsame Laufzeiten werden bei ihrer nächsten Verwendung auf `tentacle-runtime` umgestellt; vorhandene Datenbank-Volumes und individuell konfigurierte Projektnamen bleiben erhalten.

### Behoben

- Backup-Einstellungen werden einzeln an Akeebas Joomla-CLI übergeben, damit Ausgabeordner, Dateiname und die Sicherung der ursprünglichen Serverdateien gemeinsam wirksam werden.
- Akeeba-Archiv-Anbindung meldet das absichtliche Weglassen lokaler Serverdateien als erfolgreich und bestätigt Originaldateien nur nach erfolgreicher Übernahme. Fehlgeschlagene Versuche werden in der Backup-Übersicht klar gekennzeichnet; die Fehlerursache bleibt im Projekt sichtbar. Die Prüfung meldet fehlende Serverdateien konkret und prüft zuerst Akeebas Abschlussstatus.

- Neue Updatehelfer heißen `tentacle-update-…` und werden nach ihrem Ende automatisch entfernt. Zurückgebliebene beendete Updatehelfer der eigenen Installation werden bereinigt; Updateprotokolle bleiben im Datenordner erhalten.

## [2.0.1] - 2026-11-02

### Neu

- Startvideo mit Ton in einem abgedunkelten Modal mit gerundeten Ecken. Schließen per Kreuz oder Escape nach Ende des Videos; die standardmäßig aktive Wiedergabe beim nächsten Start lässt sich direkt darunter oder unter System → Startvideo für den jeweiligen Browser einstellen. Blockiert der Browser Autoplay mit Ton, startet ein Klick die Wiedergabe. Bei einem Ladefehler bleibt der Manager zugänglich.

### Behoben

- Projektlöschung wieder direkt in der Projektliste über ein Papierkorb-Icon erreichbar. Die Bestätigung mit Projektnamen und der Schutz bei laufenden Vorgängen bleiben erhalten.

## [2.0.0] - 2026-11-02

### Neu

- Papierkorb für gelöschte Pakete und Archive mit Wiederherstellung und endgültigem Löschen; unter System zwischen direkter Löschung und Papierkorb wählen und die Aufbewahrung in Tagen festlegen. Abgelaufene Einträge werden bei laufendem Manager automatisch bereinigt und im Activity Log protokolliert. Vorhandene Projektpapierkörbe erhalten bei der Übernahme eine neue Aufbewahrungsfrist.
- Dateimanager für gespeicherte CMS- und Erweiterungspakete, Akeeba-Backups, Projektsicherungen, Kickstart, ältere Manager-Downloads und Projektpapierkorb; einzelne Dateien herunterladen und gespeicherte Archive gezielt entfernen.
- Wiederkehrende Aufgaben für tägliche oder wöchentliche Update-/Erreichbarkeitsprüfungen und Projektsicherungen, mit Projektauswahl, Uhrzeit, Zeitzone, Fortschritt und Abbruch zwischen Projektschritten.
- Unter **System → Dienste & Rechte** den Zustand der eigenen Dienste sowie Docker-, Netzwerk-, Speicher- und PHP-Zugriffsrechte prüfen; Dienste starten, neu starten und beenden. Laufende Arbeiten verhindern Dienststopps.
- Lokalen Ordnerdialog testen, eine Ordnerfreigabe erneut anfragen und die vorhandene Ordneranbindung erneut einrichten; Hinweise für abgelehnte Browser- und Betriebssystemfreigaben.
- Projektsicherungen als neues Projekt im Manager wiederherstellen, mit eigener Datenbank und unverändertem Ursprungsprojekt.
- Projektbenutzer mit Standardbenutzer für den Manager, direktem Backend-Login, benutzerbezogenem Login und Löschfunktion verwalten.
- Native Ordnerauswahl für Speicherorte über die lokale Desktop-Anbindung; manuelle Pfadeingabe weiterhin möglich.
- Dieses Änderungsprotokoll mit Prüfung im Entwicklungs-/Releaseablauf und Versionshinweisen aus demselben Dokument.

### Verbessert

- Deutsches Wiki mit Installations-, Projekt-, Sicherungs- und Fehlerbehebungsanleitungen für die aktuell veröffentlichte Version ergänzt und gegen deren Release-Tag geprüft. Geplante Weiterentwicklungen stehen separat in einer Roadmap; die Anleitungen werden erst mit einer neuen Veröffentlichung angehoben. Die README kennzeichnet ihren abweichenden Entwicklungsstand.
- Animierter Sonne-/Mond-Schalter ohne sichtbare Beschriftung unten links in der Sidebar, mit Tastaturbedienung, gespeicherter Auswahl und Berücksichtigung reduzierter Bewegung.
- Dateimanager mit den Reitern Alle Dateien und Papierkorb, einer gemeinsamen Suche über alle Spalten, sortierbaren Spalten und nebeneinanderstehenden Dateiaktionen; Typ-Dropdown und einzelne Spaltenfilter entfernt.
- Projektübersicht als filter- und sortierbare Tabelle mit getrennten Status- und Updateanzeigen und Aktionen in einer Zeile.
- Einheitlichere Abstände, Tabellen und lokale Bootstrap-Icons mit Beschriftungen beim Darüberfahren sowie zugänglichen Namen.
- Projektansicht mit eigenem Datenbankreiter, direkt sichtbaren Updates und nebeneinanderstehenden Akeeba-Aktionen. Benutzer bearbeiten, ohne andere Benutzer im Dialog aufzuführen.
- Erweiterungsinstallation in einem Dialog: Katalogauswahl oder ZIP-Upload, automatisch aktualisierte Felder, Lizenzwahl und neue Lizenz. Uploads werden auch in der Bibliothek gespeichert.
- Projekterweiterungen nach Updatebedarf und Typ gruppieren bzw. filtern; CMS-Updates zusätzlich anzeigen. Originalpakete und unterstützte Updatequellen direkt aus dem Projekt in die Bibliothek übernehmen.
- Erweiterungsbibliothek mit Download bereits gespeicherter Pakete; separate globale Übernahmeansicht entfällt.
- CMS-Archiv je CMS mit Upload direkt über der gemeinsamen Versionsliste und Kennzeichnung bereits heruntergeladener Versionen. CMS und Paketversion beim Upload erkennen.
- Benutzer- und Erweiterungslisten zeigen den letzten bekannten Stand; erneutes Auslesen auf Anforderung bzw. beim Projektscan.
- Akeeba-Profile mit ihren Namen anzeigen; Anbindung älterer Joomla-/Akeeba-Installationen erweitert.

### Behoben

- Automatisierte Tests wieder zur Versionierung freigeben, damit die GitHub-Prüfungen auch mit einem frischen Checkout vollständig verfügbar sind. PNG-Bilder nur im Hauptordner als lokale Screenshots ausschließen, damit Anwendungs-, Dokumentations- und Testbilder in Unterordnern erfasst werden können.
- CMS-Versionen aus der vorhandenen Installation aktualisieren und CMS-/Erweiterungsupdates konsistenter zählen und darstellen.
- Unnötigen Neuaufbau von Ansichten bei Hintergrundaktualisierungen reduzieren.
- Speicherorte sofort anzeigen; umfangreiche Größenberechnungen im Hintergrund ausführen.
- Nicht gestartete oder noch nicht eingerichtete Projekte bei geplanten Aufgaben als übersprungen protokollieren.
- Löschvorgänge schützen verwendete Archive und laufende Arbeiten; Pfadprüfungen verhindern Zugriffe außerhalb der verwalteten Dateien.

## [1.2.3] - 2026-10-30

### Behoben

- Originale Dateinamen von `.htaccess`, `.user.ini` und `php.ini` beim Erstellen von Akeeba- und ZIP-Sicherungen innerhalb des Archivs wiederherstellen, ohne die laufende lokale Website umzubenennen.
- Beim Akeeba-Import die lokale `htaccess.txt` als `.htaccess` aktivieren, wenn eine ursprüngliche `.htaccess` nachgewiesen ist; Produktionskonfiguration und lokale Vorlage für spätere Sicherungen erhalten.

## [1.2.2] - 2026-10-30

### Neu

- Projektordner über **Dateipfad öffnen** in Windows Explorer, macOS Finder oder dem Linux-Dateimanager anzeigen.
- Desktop-Anbindung beim lokalen Start für den aktuellen Benutzer registrieren; konfigurierte Speicherorte und kopierbare Pfade berücksichtigen.

## [1.2.1] - 2026-10-30

### Behoben

- Windows-/Docker-Hostpfade für den Updatehelfer korrigieren und benötigte Helferdateien vor dem Start prüfen.
- Fortschritt, Updatephasen, Docker-Ausgaben und Zustand des Updatehelfers anzeigen; abgebrochene Helfer erkennen und beaufsichtigte Updatevorgänge über den Manager-Neustart erhalten.
- Bei erneuter Windows-Einrichtung das Manager-Image neu bauen, um ältere Installationen reparieren zu können.

## [1.2.0] - 2026-10-30

### Neu

- Erweiterungsbibliotheken für Joomla und WordPress, ZIP-Erkennung, unterstützte Updatequellen und globale bzw. projektbezogene Lizenzschlüssel.
- Konfigurierbare Speicherorte mit geprüfter Datenkopie und unveränderten Datenbankvolumes.
- Native Akeeba-Backups erstellen und einschließlich mehrteiliger Archive herunterladen.
- Activity Log nach Zeitraum filtern und ältere abgeschlossene Einträge gezielt löschen.

### Verbessert

- Stabilere Ansichten und Aktionsmeldungen mit zeitgesteuertem Ausblenden.
- Vorhandene Host-Speicherpfade bei der Aktualisierung bestehender Installationen beibehalten.

## [1.1.0] - 2026-10-29

### Neu

- Lokale Docker-Umgebung und kompatible CLI-Version erkennen; vorhandene Installationen berücksichtigen.
- PHP-/Datenbankauswahl nach CMS- und Erweiterungsanforderungen mit getrennten MySQL-/MariaDB-Profilen.

## [1.0.0] - 2026-10-28

### Neu

- Erste versionierte Ausgabe des lokalen Joomla-/WordPress-Projektmanagers mit Docker-Laufzeiten und Installationspaketen.
- Automatische Wiederherstellung unterstützter Akeeba-Backups.
- Manager-Selbstupdates und Veröffentlichung über GitHub-Releases mit geprüften Updatepaketen.
