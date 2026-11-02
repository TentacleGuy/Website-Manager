# System und Fehlerbehebung

Unter **System** stehen in Version 1.2.3 die Bereiche **PHP-Laufzeiten**, **Infrastruktur**, **Datenbankzugänge**, **Manager-Updates**, **Akeeba Kickstart** und **Speicherorte** bereit.

## Umgebung prüfen

**System → Infrastruktur → Umgebung prüfen** prüft die Docker-Anbindung und die unterstützte Umgebung. Das Ergebnis liegt auch unter `data/setup-report.json`. Der Bereich zeigt außerdem Informationen zur Infrastruktur und den PHP-Ports.

Docker Engine beziehungsweise Docker Desktop auf dem Installationsrechner starten. Falls die Manager- oder Gateway-Umgebung fehlt oder beendet ist, die lokale **Starten**-Datei verwenden. Eine zentrale Dienste-/Rechteverwaltung mit Start-/Stoppaktionen ist nicht Bestandteil von 1.2.3.

## Häufige Probleme

| Problem | Nächster Schritt |
| --- | --- |
| Dashboard nicht erreichbar | Docker starten, lokale Startdatei öffnen, Port 8090 und Setup-Protokolle prüfen |
| `projekt.vmm.test` wird nicht gefunden | Plattform-Systemeinrichtung und lokalen DNS prüfen; VPN-/Firmeneinstellungen berücksichtigen |
| HTTPS-Zertifikat wird abgelehnt | Öffentliche lokale CA im passenden System-/Browser-Zertifikatsspeicher vertrauen; Zertifikatsgültigkeit prüfen |
| Projektordner öffnet nicht | Manager lokal über localhost öffnen, Startdatei einmal ausführen und die externe Anwendung im Browser erlauben |
| Ordnerzugriff verweigert | Betriebssystemrechte und Docker-Ordnerfreigaben prüfen |
| Erweiterungsliste soll neu geladen werden | Projekt → Erweiterungen & Updates → Liste aktualisieren beziehungsweise Updates prüfen |
| Projekt nicht bereit für Installation | Projekt starten und CMS-Einrichtung beziehungsweise Wiederherstellung abschließen |
| Backup-Import scheitert | Alle Archivteile, Passwort, Kickstart und passende PHP-Version prüfen; Activity Log lesen |

## Projektordner öffnen

**Dateipfad öffnen** verwendet die lokale Desktop-Anbindung `tentacle-project://`. Die Startdatei registriert sie für den aktuellen Benutzer. Der Browser kann beim ersten Aufruf eine Bestätigung verlangen. Bei Zugriff von einem anderen Rechner wird nur der Pfad angezeigt.

Die Anbindung öffnet vorhandene Projektordner. Sie ist in 1.2.3 kein allgemeiner nativer Ordnerauswahldialog für Speicherorte. Dort absolute Pfade manuell eintragen.

## Protokolle

- Einrichtung: `logs/` im Installationsordner.
- Umgebungsprüfung: `data/setup-report.json` und System → Infrastruktur.
- Manager-Update: `data/updates/<Kennung>/update.log`.
- Projektaktionen: **Activity Log**.

Protokolle vor einer öffentlichen Weitergabe auf Zugangsdaten und persönliche Projektangaben prüfen.
