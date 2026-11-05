# Entwicklung und Quellcodebetrieb

Der Manager besteht aus einer Python-HTTP-API mit SQLite, einer Browseroberfläche in JavaScript/CSS und gemeinsam verwendeten Docker-Diensten. PHP-/Apache-Profile stehen unter `infra/runtime/`.

## Aus dem Quellcode starten

Für den dokumentierten Release-Stand mit lokalem Docker, Compose, Python 3.12 und mkcert ausführen:

```sh
git clone --branch v2.0.5 --depth 1 https://github.com/TentacleGuy/Website-Manager.git Website-Manager-2.0.5
cd Website-Manager-2.0.5
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
| `docs/wiki/` | Gepflegte Wiki-Quellen |
| `data/` | Lokale Laufzeitdaten; nicht versionieren |

## Prüfen

```sh
python3 -m unittest discover -s tests -v
python3 scripts/changelog.py
node --check app/static/app.js
node --check app/static/workspace.js
node --check app/static/refinements.js
node --check app/static/manager-ui.js
node --check app/static/system-ui.js
node --check app/static/recycle-ui.js
node --check app/static/icons.js
node --check app/static/splash.js
php -l app/tools/restore-backup.php
python3 scripts/platform_smoke.py
```

Die GitHub-Workflows prüfen plattformübergreifend. Ein grüner Unit-Testlauf allein bestätigt keine vollständige Installation mit realen Docker-Diensten.

## Release erstellen

1. Benutzerrelevante Änderungen unter **Unveröffentlicht** in `CHANGELOG.md` pflegen.
2. Für eine tatsächliche Veröffentlichung Einträge in einen Abschnitt mit Version und Datum übernehmen und `app/release.json` angleichen.
3. Unter **Unveröffentlicht** anschließend `Noch keine Änderungen.` setzen.
4. `python3 scripts/changelog.py --tag vX.Y.Z` und die erforderlichen Tests ausführen.
5. Die Änderungen veröffentlichen und das passende Tag pushen. Der Workflow erzeugt Installationspakete und Versionshinweise aus dem Changelog.

Lokaler Paketbau: `python3 scripts/build_release.py --tag vX.Y.Z`. Der Paketbau synchronisiert Plattformdateien aus `installer/` nach `app/installer_assets/`; beide Bereiche bei Änderungen prüfen. Der Paketbau schreibt Dateien und ist keine reine Leseprüfung.

In Git gehören Quellcode, Tests, Beispiele ohne Geheimnisse, Dokumentation und Build-/Workflow-Dateien. Nicht hinein gehören `.env`, lokale Projekte, Schlüssel, Datenbanken, Backups, virtuelle Umgebungen und erzeugte Pakete. Kein zweites unabhängiges Versionsprotokoll im Wiki führen.
