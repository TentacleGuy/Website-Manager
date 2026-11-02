# Voraussetzungen

Der Manager benötigt einen lokalen Docker-Dienst mit Linux-Containern. Die Websites laufen auf diesem Rechner; ein Browser auf einem anderen Gerät ändert den Speicherort der Daten nicht.

## Unterstützte Umgebung

| Bestandteil | Anforderung des Projektcodes |
| --- | --- |
| Prozessor | AMD64 oder ARM64 |
| Docker Engine | Ab Version 24 |
| Docker Compose | Ab Version 2.20, als Compose-Plugin |
| Container | Linux-Container |
| Quellcodebetrieb und Entwicklung | Python 3.12 als Referenzumgebung, Pakete aus `requirements.txt` |
| Automatische Tests | Zusätzlich Node.js und PHP für die entsprechenden Syntaxprüfungen |

Die Setup-Pakete führen die Python-Konfiguration in Docker aus. Eine eigene Python-Installation auf dem Host ist für diesen Weg nicht erforderlich.

Docker Desktop ist eine Möglichkeit. Der Code berücksichtigt auch vorhandene lokale Docker-Umgebungen, auf macOS etwa Colima und OrbStack sowie unter Linux Rootless-Sockets. Ein entfernter Docker-Kontext wird wegen der lokalen Dateieinbindungen abgewiesen.

## Speicher und Rechte

Die Neuinstallation unter Windows und macOS prüft beim Kopieren mindestens 20 GB freien Speicher. Zusätzlich wächst der Platzbedarf mit Websites, Docker-Images, Datenbanken und Backups. Der Windows-Installer verlangt für eine neue Docker-Desktop-Installation mindestens 8 GB RAM; der macOS-Installer prüft mindestens 4 GB und empfiehlt 8 GB oder mehr. Das sind Prüfungen des Installers, keine Zusage für beliebig viele Projekte.

Administratorrechte können für Docker, DNS und das Vertrauen in das lokale Zertifikat erforderlich sein. Den normalen Manager unter dem eigenen Benutzer starten.

## Lokaler Zugriff und Netzwerk

Der Manager öffnet sich auf `http://localhost:8090/`, phpMyAdmin auf `http://localhost:8091/`. Projektadressen haben die Form `projektname.vmm.test` mit einem PHP-abhängigen Port.

Der Manager besitzt keine Anmeldung und steuert Docker sowie gespeicherte Zugangsdaten. `VMM_BIND=0.0.0.0` in `.env` öffnet allein die Manager-Bindung für Netzwerkzugriffe. Für einen tatsächlichen LAN-Betrieb sind zusätzlich Firewall, Gateway-Bindungen, DNS und Zertifikatsvertrauen zu berücksichtigen. Die Setup-Pakete konfigurieren die Gateway-Ports zunächst lokal. Keine Router-Portfreigabe ins Internet einrichten.

Weiter: [Windows](Installation-Windows.md), [macOS](Installation-macOS.md), [Linux](Installation-Linux.md) oder [Quellcodebetrieb](Entwicklung.md).
