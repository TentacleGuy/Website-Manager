# Entwicklung und Quellcodebetrieb

Der Manager besteht aus einer Python-HTTP-API mit SQLite, einer Browseroberfläche in JavaScript/CSS und gemeinsam verwendeten Docker-Diensten. PHP-/Apache-Profile stehen unter `infra/runtime/`.

## Aus dem Quellcode starten

Für den dokumentierten Stand zuerst den Release-Tag `v1.2.3` auschecken. Mit lokalem Docker, Compose, Python 3.12 und mkcert für den folgenden Zertifikatsweg ausführen:

```sh
git clone --branch v1.2.3 --depth 1 https://github.com/TentacleGuy/Website-Manager.git Website-Manager-1.2.3
cd Website-Manager-1.2.3
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 app/environment_service.py --root .
python3 scripts/setup.py --lan-ip 127.0.0.1
python3 scripts/setup.py --certificates
docker network inspect vmm-gateway || docker network create vmm-gateway
docker compose -f infra/compose.gateway.yaml up -d
docker compose up -d --build
```

Unter Windows die Umgebung über `.venv\Scripts\Activate.ps1` aktivieren und einen verfügbaren Python-3.12-Aufruf verwenden. Für den normalen Windows-Betrieb ist das [Setup-Paket](Installation-Windows.md) der einfachere Weg.

`setup.py` erzeugt lokale Gateway-/DNS-Dateien und benötigt für `--certificates` mkcert auf dem Host. Das unterscheidet sich von den Setup-Paketen, die Zertifikate mit `installer_config.py` erzeugen. Beim manuellen Weg muss das Betriebssystem `*.vmm.test` an den eingerichteten DNS-Dienst auflösen. Der manuelle Generator veröffentlicht DNS standardmäßig an Port 53; macOS-/Linux-Setup-Pakete verwenden Port 1053. Gateway-Portbindungen des manuellen Generators sind gesondert auf den gewünschten lokalen Zugriff zu prüfen.

Dashboard: `http://localhost:8090/`. Die Ordneranbindung wird im Quellcodebetrieb separat eingerichtet, etwa unter macOS/Linux mit `bash app/installer_assets/register-folders.sh "$PWD"`.

## Projektstruktur

| Pfad | Inhalt |
| --- | --- |
| `app/` | API, Dienste, Laufzeitlogik und Oberfläche |
| `app/tools/` | Helfer für CMS, Installation, Updates und Wiederherstellung |
| `installer/` | Plattform-Installationsdateien |
| `app/installer_assets/` | Mitgelieferte Installations- und Desktophelfer, auch für Updates |
| `scripts/` | Einrichtung, Paketbau und Prüfungen |
| `tests/` | Automatisierte Tests und Windows-Prüfung |
| `data/` | Lokale Laufzeitdaten; nicht versionieren |

## Prüfen

```sh
python3 -m unittest discover -s tests -v
node --check app/static/app.js
php -l app/tools/restore-backup.php
```

Die verfügbaren Prüfungen ergeben sich aus dem Workflow des Release-Tags. Ein grüner Unit-Testlauf allein bestätigt keine vollständige Installation mit realen Docker-Diensten.

## Dokumentation und neue Releases

Diese Anleitungen bleiben auf Version 1.2.3, bis eine neue Version veröffentlicht wird. Die [Roadmap](Roadmap.md) beschreibt den Ausblick. Änderungen am Entwicklungszweig können deshalb vom Handbuch abweichen.

Für die Arbeit am aktuellen Entwicklungszweig gelten dessen `AGENTS.md`, `CHANGELOG.md`, Workflows und Prüfskripte. Sie sind nicht automatisch Teil des alten Release-Tags. Die Wiki-Quellen werden im Entwicklungszweig unter `docs/wiki/` gepflegt und erst nach einem Release auf dessen Funktionsstand angehoben.

In Git gehören Quellcode, Tests, Beispiele ohne Geheimnisse, Dokumentation und Build-/Workflow-Dateien. Nicht hinein gehören `.env`, lokale Projekte, Schlüssel, Datenbanken, Backups, virtuelle Umgebungen und erzeugte Pakete.
