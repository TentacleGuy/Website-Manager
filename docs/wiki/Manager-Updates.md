# Manager aktualisieren

Der Manager verwendet stabile Releases von [TentacleGuy/Website-Manager](https://github.com/TentacleGuy/Website-Manager/releases). Er prüft beim Start und danach alle sechs Stunden auf Aktualisierungen.

## Update durchführen

1. Laufende Projektarbeiten abschließen lassen.
2. **System → Manager-Updates** öffnen.
3. **Jetzt nach Updates suchen** wählen und die angebotene Version prüfen.
4. **Update installieren** starten.
5. Fortschritt beobachten. Beim Neustart verbindet sich die Oberfläche erneut. Das technische Protokoll steht im **Activity Log** in den Details des Updatevorgangs.

Das Updatepaket wird mit SHA-256-Prüfsumme und Pfadkontrollen geprüft. Ein separater Helfer sichert Programmdateien und SQLite-Metadaten, ersetzt freigegebene Programmdateien, baut den Manager und startet ihn neu. `.env`, Projektdateien, Zugangsdaten, Zertifikate und Datenbankvolumes werden beibehalten. Bei Fehlern werden die vorherigen Programmdateien wiederhergestellt.

Der Reiter zeigt auch das Änderungsprotokoll der installierten Version.

Der Ablauf setzt eine reguläre Compose-Installation mit `data/` als Unterverzeichnis, passender lokaler Docker-Anbindung und Zugriff auf GitHub voraus. Ein Manager-Update ersetzt keine externe Sicherung der Websites.

Neue Updatehelfer heißen `tentacle-update-…` und werden nach ihrem Ende automatisch entfernt. Beendete Helfer früherer Updates der eigenen Installation werden bereinigt. Die Protokolle im Datenordner bleiben erhalten.

## Updatefehler untersuchen

Im **Activity Log** öffnet **Meldung anzeigen** die Update-Meldung mit technischen Details. Das vollständige Protokoll liegt unter `data/updates/<Kennung>/update.log`. Frühere Fehler sind vom aktuell installierten Versionsstand zu unterscheiden.

Bei dem älteren Windows-Fehler `apply.py: No such file or directory` das aktuelle Windows-Setup vollständig entpacken und `Installieren.cmd` erneut starten. Denselben Installationsordner verwenden; individuelle `TENTACLE_INSTALL_DIR`-Werte beibehalten.

Die Versionshinweise stehen im [Changelog](https://github.com/TentacleGuy/Website-Manager/blob/v2.0.8/CHANGELOG.md). Dieses Handbuch gilt für Version 2.0.8. Geplante Themen stehen in der [Roadmap](Roadmap.md).
