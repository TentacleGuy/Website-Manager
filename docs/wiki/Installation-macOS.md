# Installation unter macOS

Das macOS-Setup unterstützt Intel und Apple Silicon. Es verwendet vorhandenes lokales Docker oder installiert bei Bedarf Docker Desktop vom Hersteller.

## Einrichten

1. Das macOS-ZIP aus den [Releases](https://github.com/TentacleGuy/Website-Manager/releases) vollständig entpacken.
2. `Installieren.command` als normaler Benutzer öffnen.
3. Falls Docker fehlt, den Download und die angezeigte Installation abschließen. Der Installer prüft Herstellersignatur und macOS-Kompatibilität.
4. Die Administratorabfragen für Docker sowie lokale Projektadressen und Zertifikatsvertrauen bestätigen, wenn diese Einrichtung gewünscht ist.
5. Warten, bis DNS und HTTPS geprüft wurden und die Einrichtung ihren Abschluss meldet.

Der Standardordner lautet `~/Library/Application Support/Tentacle/WebsiteManager`. Die Einrichtung erstellt Startdateien auf dem Desktop und unter `~/Applications/`.

## Später starten

**Tentacle Projektmanager.command** öffnen. Alternativ `Starten.command` im Installationsordner verwenden. Dashboard: **http://localhost:8090/**.

Bei einer unterbrochenen Einrichtung **Tentacle Einrichtung fortsetzen.command** auf dem Desktop oder `Einrichtung fortsetzen.command` im Installationsordner starten. Protokolle liegen unter `logs/` im Installationsordner.

## Lokale Domains und Ordner

Die Paketinstallation verwendet für ihren lokalen DNS-Dienst Port 1053 und richtet die Auflösung für `vmm.test` ein. Der öffentliche lokale CA-Nachweis wird im Zertifikatsspeicher vertraut gemacht. VPN- oder Firmen-DNS kann die Prüfung verhindern; dann meldet das Setup keinen erfolgreichen Abschluss.

Für das Öffnen von Projektordnern im Finder den Manager mindestens einmal über seine Startdatei öffnen. Bei verweigerten Dateizugriffen die macOS-Einstellungen unter **Datenschutz & Sicherheit → Dateien & Ordner** prüfen.

Weiter: [Projekt erstellen](Projekte.md) oder [System prüfen](System-und-Fehlerbehebung.md).
