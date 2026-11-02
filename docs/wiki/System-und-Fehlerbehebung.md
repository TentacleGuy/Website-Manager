# System und Fehlerbehebung

Unter **System → Dienste & Rechte** den Zustand der Managerdienste und ihre Zugriffsrechte prüfen. Dieser Reiter hieß in älteren Beschreibungen **Infrastruktur**.

## Dienste prüfen

**Dienste und Rechte prüfen** untersucht Docker, interne Netzwerke, Dienste und die Speicherbereiche. Der Speichertest schreibt, liest und entfernt eine kleine Prüfdatei. Bei aktiven PHP-Laufzeiten werden zusätzlich deren Rechte an den Projektordnern geprüft. Das ist keine vollständige Kontrolle sämtlicher Website-Dateien.

Eigene Dienste können je Zustand gestartet, neu gestartet oder beendet werden. Laufende Arbeiten schützen benötigte Dienste vor dem Beenden. Mehrere Projekte können dieselbe PHP-Laufzeit nutzen; ein Neustart betrifft dann mehrere Websites. PHP kann beim nächsten Website-Aufruf wieder bei Bedarf starten.

Nach dem Beenden des Managers die lokale **Starten**-Datei verwenden. Ein beendeter Manager kann Docker Desktop oder Docker Engine nicht selbst wieder starten. Fehlende Gateway-/DNS-Container werden durch die lokale Startdatei eingerichtet.

## Häufige Probleme

| Problem | Nächster Schritt |
| --- | --- |
| Dashboard nicht erreichbar | Docker starten, lokale Startdatei öffnen, Port 8090 und Setup-Protokolle prüfen |
| `projekt.vmm.test` wird nicht gefunden | Plattform-Systemeinrichtung und lokalen DNS prüfen; VPN-/Firmeneinstellungen berücksichtigen |
| HTTPS-Zertifikat wird abgelehnt | Öffentliche lokale CA im passenden System-/Browser-Zertifikatsspeicher vertrauen; Zertifikatsgültigkeit prüfen |
| Ordnerdialog erscheint nicht | Manager lokal über localhost öffnen, Startdatei einmal ausführen, externe Anwendung im Browser erlauben |
| Ordnerzugriff verweigert | Betriebssystemrechte und Docker-Ordnerfreigaben prüfen |
| Erweiterungen oder Benutzer wirken veraltet | Im Projekt gezielt **Updates prüfen** oder **Benutzerliste aktualisieren** ausführen |
| Projekt nicht bereit für Installation | Projekt starten und CMS-Einrichtung beziehungsweise Wiederherstellung abschließen |
| Backup-Import scheitert | Alle Archivteile, Passwort, Kickstart und passende PHP-Version prüfen; Activity Log lesen |
| Datei lässt sich nicht löschen | Benötigter Download, Import, Installation oder Prüfung läuft möglicherweise noch |

## Ordneranbindung

**Ordnerfreigabe anfragen** testet den nativen Dialog, ohne Speicherorte zu ändern. **Ordneranbindung erneut einrichten** erneuert eine vorhandene Registrierung. Fehlt diese vollständig, zuerst die lokale Startdatei ausführen.

macOS verwendet den Systemdialog, Windows den FolderBrowserDialog und Linux `zenity` oder `kdialog`. Eine dauerhaft abgelehnte Browser- oder Betriebssystemfreigabe muss dort wieder erlaubt werden. Die Website kann sie nicht erzwingen.

## Protokolle

- Einrichtung: `logs/` im Installationsordner.
- Umgebungsprüfung: `data/setup-report.json` und die weiteren Umgebungsinformationen im Systemreiter.
- Manager-Update: `data/updates/<Kennung>/update.log`.
- Projektaktionen: **Activity Log**.

Protokolle vor einer öffentlichen Weitergabe auf Zugangsdaten und persönliche Projektangaben prüfen.

## Startvideo einstellen

Unter **System → Startvideo** die Wiedergabe beim Öffnen des Managers ein- oder ausschalten. **Startvideo ansehen** öffnet eine Vorschau. Die Auswahl gilt für den jeweiligen Browser. Weitere Hinweise unter [Startvideo](Startvideo.md).
