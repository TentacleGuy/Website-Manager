# Installation unter Windows

Verwende das Windows-Setup aus den [Releases](https://github.com/TentacleGuy/Website-Manager/releases). Die folgenden Schritte beschreiben den Installer der Version 2.0.0.

## Einrichten

1. Das ZIP vollständig entpacken.
2. `Installieren.cmd` starten.
3. Falls noch kein lokaler Docker-Dienst vorhanden ist, die angezeigten Schritte für Windows-Voraussetzungen und Docker Desktop durchführen. Eine neue Docker-Desktop-Installation verwendet WSL 2.
4. Wird ein Neustart verlangt, zuerst die eigene Arbeit speichern und Windows neu starten. Danach die Desktop-Verknüpfung **Tentacle Einrichtung fortsetzen** öffnen.
5. Die Einrichtung lokaler Projektadressen und des Zertifikats abschließen.
6. Warten, bis der Installer den erfolgreichen Abschluss meldet und den Browser öffnet.

Der Standardordner lautet `%LOCALAPPDATA%\Tentacle\WebsiteManager`. Ein abweichendes `VMM_INSTALL_DIR` muss bei einer erneuten Einrichtung wieder auf denselben Ordner zeigen. Ein bereits belegter, nicht als Manager-Installation markierter Zielordner wird abgewiesen.

## Später starten

Die Verknüpfung **Tentacle Projektmanager** auf dem Desktop oder im Startmenü verwenden. Alternativ `Starten.ps1` im Installationsordner ausführen. Diese Startdatei richtet auch die lokale Ordneranbindung ein.

Dashboard: **http://localhost:8090/**.

## Wenn die Einrichtung abbricht

Die konkrete Fehlermeldung und die Protokolle unter `logs/` im Installationsordner prüfen. Nach Behebung den Installer erneut starten. Bestehende `data/`-Inhalte und `.env` sind nicht Bestandteil des Setup-Pakets und werden bei der erneuten Standardinstallation beibehalten.

Für eine neue Docker-Desktop-Installation prüft der Code unter anderem Windows-Build, Architektur und Arbeitsspeicher. Firmenrichtlinien, Virtualisierung oder DNS/VPN können zusätzliche Schritte erfordern. Die tatsächlich installierte Docker-Version muss die Plattform unterstützen.

Weiter: [Projekt erstellen](Projekte.md) oder [Fehler beheben](System-und-Fehlerbehebung.md).
