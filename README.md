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

## Aktivitäten und Aktionsmeldungen

Das **Activity Log** zeigt standardmäßig die letzten sieben Tage und lädt jeweils 50 Einträge. Über **Von** und **Bis** lassen sich Datum und Uhrzeit frei wählen; Suche, Status und Seitenauswahl gelten innerhalb dieses Zeitraums. Alle Zeitangaben verwenden die lokale Zeitzone des Browsers.

Unter **Alte Logs löschen** einen Zeitpunkt wählen: Endgültig entfernt werden nur erledigte, fehlgeschlagene oder unterbrochene Vorgänge mit einem Beginn **vor** diesem Zeitpunkt. Einträge genau zum gewählten Zeitpunkt sowie laufende und wartende Vorgänge bleiben erhalten.

Aktionen erscheinen als Meldungen unten rechts. Laufende und wartende Vorgänge bleiben sichtbar; Erfolgsmeldungen verschwinden nach 8 Sekunden, Fehler und Unterbrechungen nach 20 Sekunden. Meldungen lassen sich auch vorher schließen. Die Restlaufzeit bleibt beim Neuladen desselben Browser-Tabs erhalten. Alle Vorgänge bleiben unabhängig von der Meldung im Activity Log nachlesbar.

Die Projektübersicht trennt **Erweiterungsupdates** und **CMS-Updates**. Bei Joomla enthält die Erweiterungsprüfung zusätzlich einen Hinweis auf verfügbare CMS-Updates; CMS-Updates werden im CMS-Backend installiert.

Unter **Backups** lassen sich sowohl hochgeladene Akeeba-Backupgruppen einschließlich aller Teilarchive als auch erzeugte Projektsicherungen über **Löschen** endgültig entfernen. Backups für noch offene Wiederherstellungen sind gegen Löschen geschützt. Das Löschen eines Backup-Archivs entfernt kein daraus wiederhergestelltes Projekt.

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

Unter **Erweiterungen** sind **WordPress** und **Joomla** getrennt. Jeder Reiter enthält die Bibliothek, **Gespeicherte Pakete** und **Aus Projekt übernehmen**. Zum Hinzufügen genügt ein ZIP-Paket: CMS, Name und Version werden erkannt. Joomla-Update-XML wird aus dem Manifest übernommen; WordPress.org wird nur bei einer passenden Paketidentität verwendet. Eine fremde WordPress-`Update URI` ist keine ausreichende Downloadquelle und bleibt zunächst ungeklärt.

**Gespeicherte Pakete** zeigt Version, Größe und Datum sowie Download, Installation und Löschen. Löschen entfernt das ZIP aus dem Archiv, keine installierte Website. Installationszuordnungen bleiben erhalten. Pakete werden während laufender Installationen und Downloads gegen Löschen geschützt.

Beim Bearbeiten einer Erweiterung kann ein globaler Lizenz-/API-Key hinterlegt werden. Abweichende Schlüssel werden unter **Projekt → Lizenzen** verwaltet und bleiben an dieses Projekt gebunden. Bestehende Lizenzdaten werden beibehalten; Anbieter und Pakettyp müssen in der normalen Oberfläche nicht ausgewählt werden. Eine Herstelleraktivierung im CMS ist weiterhin vom jeweiligen Hersteller abhängig.

**Aus Projekt übernehmen** liest die native Updateanbindung einer laufenden, vollständig eingerichteten Website. Eine erkannte Quelle kann übernommen oder das neueste Originalpaket direkt archiviert werden. WordPress nutzt seine eigenen Updateinformationen und bei WPML zusätzlich den vorhandenen OTGS Installer. Joomla verwendet die registrierten Update-XML-Adressen. Die Website wird dabei nicht aktualisiert. Lizenzschlüssel aus der Website bleiben projektgebunden und werden nicht zu globalen Schlüsseln gemacht.

Projektbasierte Quellen benötigen ihr Herkunftsprojekt weiterhin zum Abfragen frischer Downloadlinks. Signierte Links werden nicht dauerhaft als Updatequelle gespeichert. Fehlt eine unterstützte Quelle, ein gültiger Zugang oder ein Originaldownload, meldet der Manager dies; aus installierten Dateien wird kein vermeintliches Herstellerpaket zusammengesetzt. Die Erkennung benötigt keine Ausführung hochgeladener Pakete.

Vor Erweiterungsinstallationen und Sammelupdates erzeugt der Manager Datei-/SQL-Sicherungen. Gemeinsame PHP-Container werden dafür kurz pausiert und anschließend fortgesetzt. Unter **Backups → Projektsicherungen** stehen die Exporte zum Download. Diese Manager-Exporte sind keine Akeeba-Archive; ihr automatischer Rückimport ist nicht enthalten.

## Speicherorte

Unter **System → Speicherorte** werden die Ordner für Projekte, Erweiterungspakete, CMS-Archive, Akeeba-Backups und Projektsicherungen angezeigt, einschließlich belegtem und freiem Speicher. Die Pfade beziehen sich auf den **Docker-Rechner**, nicht auf einen entfernten Browser. Datenbanken bleiben in ihren bisherigen Docker-Volumes; Manager-Metadaten, Zertifikate und Zugangsdaten behalten den bisherigen Datenordner.

Neue absolute Pfade eintragen, **Speicherorte prüfen** wählen und anschließend **Daten kopieren und Speicherorte übernehmen**. Zielordner werden bei Bedarf angelegt und müssen leer, beschreibbar und ausreichend groß sein. Laufende Jobs und Uploads müssen beendet sein. Bei der Umstellung startet der Manager neu und betroffene PHP-Laufzeiten werden kurz angehalten. Dateien werden kopiert und über SHA-256 verglichen, bevor die neuen Einbindungen aktiviert werden. Bisherige Ordner werden nicht automatisch gelöscht. Eine fehlgeschlagene Umstellung setzt die bisherigen Einstellungen zurück; eventuell entstandene Zielkopien bleiben zur Prüfung erhalten.

Die Konfiguration liegt unter `data/storage/settings.json`, wird in `.env` für reguläre Starts und in `data/storage/compose.storage.json` für den Helfer übernommen. Änderungen an diesen Dateien nicht während einer Umstellung vornehmen. Externe Laufwerke müssen beim Start verfügbar sein. Die internen `/data/...`-Pfade bleiben stabil. PHP-Laufzeiten werden vor dem Anhalten anhand ihrer tatsächlichen Projekte-Einbindung auf Zugehörigkeit zu dieser Installation geprüft.

## Akeeba-Backups erstellen

Unter **Projekt → Übersicht → Akeeba-Backups** eine Profilnummer wählen und **Akeeba-Backup erstellen** anklicken. Die Funktion nutzt die installierte native Akeeba-CLI; Akeeba wird nicht automatisch installiert. Für Joomla wird eine unterstützte Akeeba-Installation mit aktiviertem Konsolenplugin benötigt, für WordPress die unterstützte CLI von Akeeba Backup Professional.

Der Manager erzeugt ein echtes vollständiges JPA-Archiv im eingestellten Backup-Ordner. Die gewählte Profilkonfiguration wird für diesen Lauf übersteuert: lokaler Ausgabeordner, JPA-Format, keine Cloud-Nachbearbeitung, keine Löschquoten und keine Akeeba-Abschluss-E-Mails. Gespeicherte Akeeba-Profile werden dabei nicht geändert. Die Profilfilter bleiben wirksam. Erst nach Akeebas Abschlussbestätigung und Prüfung aller Archivteile wird der Download freigegeben.

Die Dateien können einzeln heruntergeladen werden. Bei mehrteiligen Sicherungen steht zusätzlich **Alle Teile als Downloadpaket (.zip)** bereit. Dieses äußere ZIP vor einer Wiederherstellung entpacken; danach JPA und Teilarchive gemeinsam verwenden. Unvollständige Sicherungen werden als Fehler angezeigt und nicht als wiederherstellbares Backup angeboten. Datei-/SQL-Projektsicherungen bleiben eine separate Funktion.

## Manager-Updates

Die feste Updatequelle ist [TentacleGuy/Website-Manager](https://github.com/TentacleGuy/Website-Manager/releases). Unter **System → Manager-Updates** werden installierte Version, letzte Prüfung und verfügbare Aktualisierungen angezeigt. Der Manager prüft beim Start und alle sechs Stunden auf neue stabile Releases. Ein Hinweis erscheint auch außerhalb der Systemansicht.

**Jetzt nach Updates suchen** prüft manuell. Während der Installation zeigt **System → Manager-Updates** den aktuellen Schritt, die letzte Rückmeldung und das fortlaufende Docker-Protokoll. **Updatehelfer prüfen** liefert den Containerzustand, Exit-Code und dessen letzte Ausgaben. Während des Image-Baus bleibt die Oberfläche erreichbar; beim eigentlichen Neustart verbindet sie sich automatisch wieder. Das vollständige Protokoll liegt zusätzlich unter `data/updates/<Kennung>/update.log`. **Update installieren** lädt das Release-Paket samt SHA-256-Prüfsumme, prüft Version und enthaltene Pfade und startet einen separaten Docker-Helfer. Laufende Projektvorgänge müssen zuvor abgeschlossen sein. Der Helfer sichert Programmdateien und SQLite-Metadaten, ersetzt ausschließlich freigegebene Programmdateien, baut den Manager und startet ihn neu. Website-Container, `.env`, Backups, Zugangsdaten, Zertifikate und Datenbankvolumes werden beibehalten. Die Oberfläche verbindet sich wieder. Bei Fehlern werden die vorherigen Programmdateien wiederhergestellt; der Status und das Protokoll stehen unter `data/updates/`.

Der Helfer benötigt eine reguläre Compose-Installation mit `data` als Unterverzeichnis der Installation und den im Standard-Setup eingebundenen Docker-Socket. Downloadprüfung und Installation benötigen Zugriff auf GitHub. Solange noch kein öffentliches Release mit Updatepaket existiert, zeigt der Manager dies an.

Falls unter Windows ein älterer Updatehelfer mit `apply.py: No such file or directory` abbricht, das aktuelle Windows-Setup erneut entpacken und `Installieren.cmd` starten. Bei der Standardinstallation übernimmt es die Programmdateien in den bestehenden, markierten Installationsordner und baut das Manager-Image neu. `data` und `.env` sind nicht im Paket enthalten und bleiben erhalten. Bei einem individuellen Installationsordner denselben `VMM_INSTALL_DIR` wie zuvor verwenden.

### Ein Release veröffentlichen

1. `app/release.json` auf die neue Version setzen.
2. Änderungen testen und nach `main` übertragen.
3. Ein passendes Tag wie `v1.0.1` erstellen und pushen.

Der GitHub-Workflow führt Tests und Syntaxprüfungen aus und erstellt anschließend ein Release mit `manager-update.zip`, Prüfsumme und den Setup-Paketen für Windows, macOS und Linux. Tag und eingetragene Version müssen übereinstimmen. Für einen lokalen Paketbau:

```sh
python3 scripts/build_release.py --tag v1.2.0
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
