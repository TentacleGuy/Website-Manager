# Tentacle Productions · Website Manager

Lokaler Projektmanager für Joomla und WordPress mit gemeinsamen Docker-Laufzeiten, Akeeba-Import, Erweiterungsverwaltung und Manager-Updates über GitHub-Releases.

## Installation

Unter [Releases](https://github.com/TentacleGuy/Website-Manager/releases) das Setup für macOS, Windows oder Linux laden und entpacken:

- macOS: `Installieren.command` starten. Für eine unterbrochene Einrichtung `Einrichtung fortsetzen.command` verwenden; anschließend startet `Starten.command` den Manager.
- Windows: `Installieren.cmd` starten. Danach kann `Starten.ps1` den Manager öffnen.
- Linux: Mit vorhandenem Docker Engine und Compose `bash Installieren.sh` ausführen. Der optionale DNS-/Zertifikatshelfer unterstützt systemd-resolved sowie Debian-/Fedora-Zertifikatsspeicher; andere Resolver bleiben unverändert.

Die Einrichtung installiert bzw. prüft die benötigten Werkzeuge, erzeugt lokale Zertifikate und richtet die lokale Namensauflösung ein. Ein lokaler Docker-Dienst mit Linux-Containern muss gestartet sein. Die Installationshinweise im jeweiligen Paket erläutern die Systemschritte.

### Aus dem Quellcode starten

Voraussetzungen: Docker Engine ab 24 mit Compose ab 2.20, Linux-Container auf AMD64 oder ARM64, Python 3.12 und die Pakete aus `requirements.txt`. Docker Desktop ist eine Möglichkeit; vorhandene lokale Docker-/Rootless-Installationen werden berücksichtigt. Entfernte Docker-Kontexte werden wegen der lokalen Dateieinbindungen gezielt abgewiesen.

```sh
python3 -m pip install -r requirements.txt
python3 app/environment_service.py --root .
python3 scripts/setup.py --lan-ip 127.0.0.1
python3 scripts/setup.py --certificates
docker network create vmm-gateway
docker compose -f infra/compose.gateway.yaml up -d
docker compose up -d --build
```

`--certificates` benötigt mkcert. `setup.py` erzeugt `.env`, Gateway, DNS und Portregeln. Für `*.vmm.test` muss der lokale DNS-Dienst verwendet werden. Das Dashboard öffnet sich unter **http://localhost:8090/**, phpMyAdmin unter **http://localhost:8091/**.

Das Dashboard läuft ohne Anmeldung und bindet standardmäßig nur an den lokalen Rechner. `VMM_BIND=0.0.0.0` in `.env` ermöglicht den bewusst eingerichteten LAN-Zugriff. Für LAN-DNS die Adresse des Docker-Rechners statt `127.0.0.1` angeben und auf weiteren Geräten das öffentliche lokale Stammzertifikat als vertrauenswürdig installieren. Die private Zertifikatdatei wird nicht weitergegeben.

## Umgebungsabhängige Einrichtung

Das Setup prüft Docker-Dienst, Linux-Container, Prozessorarchitektur und Compose-Version. Der ausgewählte lokale Docker-Kontext wird beibehalten. Ein zur Docker-Servergeneration passendes Docker-CLI-Image wird für den Manager gewählt; Rootless-Sockets werden unter Linux weitergereicht. Auf macOS verwenden Docker Desktop, Colima und OrbStack den Socket innerhalb ihrer Linux-VM. Ein abweichender Socket kann explizit über `VMM_DOCKER_SOCKET` vorgegeben werden.

Vorhandene `.env`-Zusatzwerte, LAN-Einstellungen, Gateway-Ports und Zertifikate bleiben bei einer erneuten Einrichtung erhalten. Die Prüfung steht in `data/setup-report.json` und unter **System → Infrastruktur → Umgebung prüfen**. Fehler werden mit dem konkreten Schritt ausgegeben. Ein nicht verfügbares Image oder eine nicht unterstützte Architektur führt nicht zu einem stillen Rückfall auf eine ältere Datenbank.

Ein kompatibles Docker muss auf dem jeweiligen Betriebssystem laufen können. Hardware-Virtualisierung, Firmenrichtlinien, belegte Ports oder ein nicht unterstützter DNS-/Zertifikatsspeicher können weiterhin einen manuellen Schritt erfordern. Die Installation behauptet in diesen Fällen keinen erfolgreichen Abschluss.

### PHP und Datenbank nach Projektanforderungen

Neue Projekte bieten **Automatisch nach CMS und Erweiterungen** sowie eine explizite Auswahl. Unterstützte Datenbankprofile sind MariaDB 10.11, 11.4 und 11.8 sowie MySQL 8.0 und 8.4. Die Automatik bevorzugt MariaDB 11.4 und berücksichtigt deklarierte strengere Anforderungen und eine vorgegebene Datenbankfamilie. Ein MySQL-Projekt erhält MySQL und wird nicht still auf MariaDB umgestellt. Jede Datenbankserie verwendet einen eigenen Dienst und ein eigenes Volume. Eine Datenbank wird erst bereitgestellt, wenn ein Projekt sie benötigt.

Vorhandene Projekte werden auf **Bestehende Datenbank** festgelegt. Das vorhandene Image aus `data/shared/compose.json` wird einmalig in `data/shared/backend.json` festgehalten. Der Dienst `db` und das Volume `database` bleiben erhalten. Auch eine individuell konfigurierte versionierte MySQL-/MariaDB-Installation wird nicht durch MariaDB 10.11 ersetzt. Bei unbekannten oder unversionierten bestehenden Images stoppt die Umstellung zur Prüfung. Es findet kein automatisches Upgrade oder Downgrade vorhandener Datenbankvolumes statt.

Erkannt werden CMS-Mindestanforderungen, WordPress-Plugin-/Theme-Header `Requires PHP`, deklarierte Composer-PHP-/Modulanforderungen und entsprechende Joomla-Manifestangaben. Bereits archivierte ausgewählte Erweiterungen werden vor der ersten Datenbankbereitstellung berücksichtigt. Beim Backup-Import wird die im Backup dokumentierte PHP-Serie bevorzugt, sofern die Projektanforderungen dazu passen. Tatsächliche PHP-/Datenbank-Patchversionen und benötigte PHP-Module werden vor der Installation bzw. Wiederherstellung geprüft.

Nicht jede Erweiterung veröffentlicht vollständige Systemanforderungen. Fehlende Angaben können nicht zuverlässig aus beliebigem Programmcode abgeleitet werden. Für zusätzliche bekannte Herstelleranforderungen kann im Projekt- oder Erweiterungsordner eine `.tentacle-requirements.json` liegen:

```json
{
  "php": ">=8.3 <8.5",
  "php_extensions": ["soap", "intl"],
  "database": {"mysql": ">=8.4", "mariadb": ">=11.4"}
}
```

Nur genannte Datenbankfamilien sind dann zulässig. Die Erweiterungsquellen-API akzeptiert dieselben Angaben unter `requirements`. Widersprüchliche Anforderungen halten den Vorgang mit einer Fehlermeldung an. Später heruntergeladene Erweiterungen werden vor der Ausführung ihres Installers geprüft; nicht deklarierte SQL-/CMS-Inkompatibilitäten bleiben Gegenstand von Herstellerhinweisen und Praxistests.

## Projekte

### Neue CMS-Installation

Im CMS-Archiv ein offizielles Paket herunterladen oder hochladen. Anschließend ein Projekt mit CMS, Paket und PHP-Version anlegen. WordPress und Joomla ab 4.3 können mit Administratorkonto automatisch eingerichtet werden. Für ältere Joomla-Versionen steht der ursprüngliche CMS-Assistent zur Verfügung.

### Aus einem Akeeba-Backup

1. Hauptarchiv und alle Teilarchive gemeinsam unter **Backups** hochladen: JPA/JPS/ZIP, dazu J01… oder Z01… . Maximal 4 GB pro Datei.
2. **Projekt erstellen** wählen, Projektnamen angeben; PHP und Datenbank können automatisch gewählt werden. Das CMS muss nicht ausgewählt werden.
3. Optional eine bestimmte Kickstart-Version wählen. Bei **Automatisch** lädt der Manager die neueste Kickstart-Core-Version direkt von Akeeba. Unter **System → Akeeba Kickstart → Alle Versionen abrufen** steht das offizielle Versionsarchiv bereit. Jede Version wird separat gespeichert. Eine eigene `kickstart.php` kann weiterhin verwendet werden.
4. Für verschlüsselte JPS-Archive das Archivpasswort eingeben. Es wird weder in den Projektmetadaten noch im Job gespeichert.
5. Der Manager entpackt das Archiv, erkennt Joomla oder WordPress samt Version und stellt die Datenbank über den im Backup enthaltenen Akeeba-Installer wieder her. Die lokalen Datenbankzugänge und URLs werden automatisch übernommen. Anschließend wird das Installationsverzeichnis entfernt und das Projekt freigegeben.

Unterstützt werden ältere ANGIE-Installer und die neuere Akeeba Backup Restoration Script CLI. WordPress-URL-Ersetzungen verwenden die Datenbankwerkzeuge von Akeeba bzw. WP-CLI, einschließlich serialisierter Inhalte. Lokale Joomla-Pfade, SSL-Einstellungen und die Mailkonfiguration werden angepasst. Vorhandene CMS-Benutzer bleiben erhalten.

Backups mit mehreren Datenbanken, externen Verzeichnissen oder nicht unterstützten CMS werden mit einer konkreten Fehlermeldung angehalten. Sie werden nicht als erfolgreich wiederhergestellt markiert. PHP muss zur gesicherten Website und zum enthaltenen Installer passen. Eine alte Kickstart-Version kann selbst keine aktuelle PHP-Version unterstützen.

Nach erfolgreichem Entpacken kann eine fehlgeschlagene Datenbankwiederherstellung unter **Wiederherstellung fortsetzen** erneut gestartet werden. Die Wiederaufnahme verwendet dieselbe Backup-Gruppe; bereits vorhandene Website-Dateien werden nicht neu entpackt. Bei einem Fehler während der Extraktion bleiben die Dateien zur Diagnose erhalten; dafür ein neues leeres Projekt verwenden. Produktionsdateien `.htaccess`, `.user.ini` und `php.ini` bleiben beim Import als `.vmm-original` erhalten.

### Projekte löschen

**Projekt → Projekt löschen** öffnet die Bestätigung mit dem Projektnamen. Der Manager startet bei Bedarf die gemeinsame Datenbank, prüft, ob die Projektdatenbank existiert, und sichert sie vor dem Entfernen. Auch noch nicht eingerichtete Projekte ohne Datenbank können gelöscht werden. Bei einem fehlgeschlagenen Datenbankexport bleiben Projekt und Dateien erhalten.

Dateien, SQL-Export und Metadaten liegen danach unter `data/trash/`. Die Projektdatenbank bleibt erhalten; Laufzeiten und Datenbanken anderer Projekte werden nicht gelöscht. Eine automatische Wiederherstellung aus dem Papierkorb ist derzeit nicht in der Oberfläche enthalten. Für die manuelle Wiederherstellung sind Originalname, Dateien und Metadaten reserviert.

## PHP und Protokolle

| PHP | HTTP | HTTPS |
| --- | --- | --- |
| 7.4 | 8074 | 8174 |
| 8.0 | 8080 | 8180 |
| 8.1 | 8081 | 8181 |
| 8.2 | 8082 | 8182 |
| 8.3 | 8083 | 8183 |
| 8.4 | 8084 | 8184 |
| 8.5 | 8085 | 8185 |

Projektadressen folgen dem Muster `projekt.vmm.test`. Ein Aufruf mit `http://` auf einem HTTPS-Port wird auf `https://` an demselben Port umgeleitet. Ein Aufruf mit `https://` auf einem HTTP-Port wird auf `http://` korrigiert. Pfad und Abfrageparameter bleiben erhalten. Für HTTPS muss das lokale Zertifikat vertraut sein; die TLS-Verbindung wird vor einer Weiterleitung aufgebaut.

Die Regeln stehen in `infra/dynamic/protocols.yaml` und werden von `scripts/setup.py` erzeugt. Traefik liest Änderungen automatisch ein. Eine PHP-Laufzeit bedient alle Projekte der jeweiligen Version. Der erste Start kann wegen des Image-Baus mehrere Minuten dauern.

## Erweiterungen und Zugangsdaten

Der Katalog unterstützt WordPress.org, Hersteller-Update-XML, direkte ZIP-Downloads und eigene Pakete. Lizenzen können als Hauptlizenz mit projektspezifischen Seitenschlüsseln hinterlegt werden. CMS-Benutzer und gespeicherte Zugänge werden pro Projekt verwaltet. Herstellerfunktionen hängen von den jeweiligen Erweiterungen ab.

Vor Erweiterungsinstallationen und Sammelupdates erzeugt der Manager Datei-/SQL-Sicherungen. Gemeinsame PHP-Container werden dafür kurz pausiert und anschließend fortgesetzt. Unter **Backups → Projektsicherungen** stehen die Exporte zum Download. Diese Manager-Exporte sind keine Akeeba-Archive; ihr automatischer Rückimport ist nicht enthalten.

## Manager-Updates

Die feste Updatequelle ist [TentacleGuy/Website-Manager](https://github.com/TentacleGuy/Website-Manager/releases). Unter **System → Manager-Updates** werden installierte Version, letzte Prüfung und verfügbare Aktualisierungen angezeigt. Der Manager prüft beim Start und alle sechs Stunden auf neue stabile Releases. Ein Hinweis erscheint auch außerhalb der Systemansicht.

**Jetzt nach Updates suchen** prüft manuell. **Update installieren** lädt das Release-Paket samt SHA-256-Prüfsumme, prüft Version und enthaltene Pfade und startet einen separaten Docker-Helfer. Laufende Projektvorgänge müssen zuvor abgeschlossen sein. Der Helfer sichert Programmdateien und SQLite-Metadaten, ersetzt ausschließlich freigegebene Programmdateien, baut den Manager und startet ihn neu. Website-Container, `.env`, Backups, Zugangsdaten, Zertifikate und Datenbankvolumes werden beibehalten. Die Oberfläche verbindet sich wieder. Bei Fehlern werden die vorherigen Programmdateien wiederhergestellt; der Status und das Protokoll stehen unter `data/updates/`.

Der Helfer benötigt eine reguläre Compose-Installation mit `data` als Unterverzeichnis der Installation und den im Standard-Setup eingebundenen Docker-Socket. Downloadprüfung und Installation benötigen Zugriff auf GitHub. Solange noch kein öffentliches Release mit Updatepaket existiert, zeigt der Manager dies an.

### Ein Release veröffentlichen

1. `app/release.json` auf die neue Version setzen.
2. Änderungen testen und nach `main` übertragen.
3. Ein passendes Tag wie `v1.0.1` erstellen und pushen.

Der GitHub-Workflow führt Tests und Syntaxprüfungen aus und erstellt anschließend ein Release mit `manager-update.zip`, Prüfsumme und den Setup-Paketen für Windows, macOS und Linux. Tag und eingetragene Version müssen übereinstimmen. Für einen lokalen Paketbau:

```sh
python3 scripts/build_release.py --tag v1.1.0
```

Die Paketbauer verwenden eine explizite Dateiliste. Lokale Projekte, `.env`, Datenbanken, Backups, Exporte, Zertifikate und Zugangsdaten sind ausgeschlossen. Kickstart wird zur Laufzeit von Akeeba geladen und nicht mitveröffentlicht.

## Entwicklung und Datenhaltung

```sh
python3 -m unittest discover -s tests -v
node --check app/static/app.js
php -l app/tools/restore-backup.php
```

Python-Standardbibliothek mit HTTP-API und SQLite; Browseroberfläche in JavaScript und CSS. Gemeinsam genutzte MariaDB sowie PHP-/Apache-Laufzeiten werden über Compose gesteuert. PHP-Unterstützung und Erweiterungen sind in `infra/runtime/Dockerfile` definiert.

`data/` enthält Manager-Metadaten, Projektdateien, Paketarchive und Schlüssel. Die Datenbankinhalte liegen im Docker-Volume `vmm-runtime_database`. Ein Kopieren des Quellcodes oder von `data/` allein überträgt dieses Volume nicht. Für einen Umzug sind zusätzlich SQL-Exporte bzw. vollständige Backups nötig. `docker compose down -v` entfernt Datenbankvolumes und gehört nicht zum normalen Aktualisieren.
