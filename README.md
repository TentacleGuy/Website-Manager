# Tentacle Productions · Website Manager

Lokaler Projektmanager für Joomla und WordPress mit gemeinsamen Docker-Laufzeiten, Akeeba-Import, Erweiterungsverwaltung und Manager-Updates über GitHub-Releases.

## Dokumentation

Das [GitHub-Wiki](https://github.com/TentacleGuy/Website-Manager/wiki) enthält nach Aufgaben geordnete Anleitungen. Die gepflegten Quellen liegen unter [docs/wiki/Home.md](docs/wiki/Home.md). Das Wiki dokumentiert ausschließlich die aktuell veröffentlichte Version **2.0.0**, geprüft gegen den Release-Tag `v2.0.0`. Geplante Themen stehen separat in der [Roadmap](docs/wiki/Roadmap.md). Diese README beschreibt dagegen den Entwicklungszweig und kann bereits unveröffentlichte Funktionen enthalten. Der [Dokumentationsabgleich](docs/WIKI-PRUEFUNG.md) erläutert diese Abgrenzung.

## Änderungsprotokoll

Alle veröffentlichten Versionen und die noch unveröffentlichten Änderungen stehen in [CHANGELOG.md](CHANGELOG.md). Das Protokoll wird bei relevanten Änderungen mitgepflegt; GitHub-Versionshinweise werden bei der Veröffentlichung daraus erzeugt.

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

Vorhandene `.env`-Zusatzwerte, LAN-Einstellungen, Gateway-Ports und Zertifikate bleiben bei einer erneuten Einrichtung erhalten. Die Prüfung steht in `data/setup-report.json` und unter **System → Dienste & Rechte → Weitere Informationen zur Umgebung**. Fehler werden mit dem konkreten Schritt ausgegeben. Ein nicht verfügbares Image oder eine nicht unterstützte Architektur führt nicht zu einem stillen Rückfall auf eine ältere Datenbank.

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

Die Projektübersicht zeigt einen gespeicherten Erweiterungsupdate-Status. Im Projekt führt **Erweiterungen → Updates prüfen** eine neue Prüfung aus; dort werden auch erkannte CMS-Updates angezeigt. CMS-Updates werden im CMS-Backend installiert.

Unter **Backups** lassen sich Akeeba-Backupgruppen einschließlich aller Teilarchive sowie Projektsicherungen entfernen. Je nach Einstellung unter **System → Löschen & Papierkorb** werden gespeicherte Archive in den Papierkorb verschoben oder endgültig gelöscht. Backups für offene Wiederherstellungen bleiben geschützt. Das Löschen eines Archivs entfernt kein daraus wiederhergestelltes Projekt.

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

Dateien, SQL-Export und Metadaten liegen danach unter `data/trash/`. Die Projektdatenbank bleibt erhalten; Laufzeiten und Datenbanken anderer Projekte werden nicht gelöscht. Unter **Dateimanager → Papierkorb** können geeignete Projekte mit ihrem ursprünglichen Namen wiederhergestellt werden; sie erscheinen anschließend gestoppt. Belegte Namen und problematische Dateiverknüpfungen verhindern die automatische Übernahme. Fehlt die aufbewahrte Projektdatenbank, wird der gesicherte SQL-Export verwendet.

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

Unter **Erweiterungen** sind **WordPress** und **Joomla** getrennt. Die Bibliothek und **Gespeicherte Pakete** zeigen die archivierten Erweiterungen. Originalpakete aus bestehenden Websites werden direkt unter **Projekt → Erweiterungen → In Bibliothek speichern** übernommen; die separate globale Übernahmeansicht entfällt. Zum Hinzufügen genügt ein ZIP-Paket: CMS, Name und Version werden erkannt. Joomla-Update-XML wird aus dem Manifest übernommen; WordPress.org wird nur bei einer passenden Paketidentität verwendet. Eine fremde WordPress-`Update URI` ist keine ausreichende Downloadquelle und bleibt zunächst ungeklärt.

**Gespeicherte Pakete** zeigt Version, Größe und Datum sowie Download, Installation und Löschen. Löschen entfernt das ZIP aus dem Archiv, keine installierte Website. Installationszuordnungen bleiben erhalten. Pakete werden während laufender Installationen und Downloads gegen Löschen geschützt.

Beim Bearbeiten einer Erweiterung kann ein globaler Lizenz-/API-Key hinterlegt werden. Abweichende Schlüssel werden unter **Projekt → Lizenzen** verwaltet und bleiben an dieses Projekt gebunden. Bestehende Lizenzdaten werden beibehalten; Anbieter und Pakettyp müssen in der normalen Oberfläche nicht ausgewählt werden. Eine Herstelleraktivierung im CMS ist weiterhin vom jeweiligen Hersteller abhängig.

**In Bibliothek speichern** unter **Projekt → Erweiterungen** liest die native Updateanbindung einer laufenden, vollständig eingerichteten Website und übernimmt die unterstützte Quelle samt herunterladbarem Originalpaket. WordPress nutzt seine eigenen Updateinformationen und bei WPML zusätzlich den vorhandenen OTGS Installer. Joomla verwendet die registrierten Update-XML-Adressen. Die Website wird dabei nicht aktualisiert. Lizenzschlüssel aus der Website bleiben projektgebunden und werden nicht zu globalen Schlüsseln gemacht.

Projektbasierte Quellen benötigen ihr Herkunftsprojekt weiterhin zum Abfragen frischer Downloadlinks. Signierte Links werden nicht dauerhaft als Updatequelle gespeichert. Fehlt eine unterstützte Quelle, ein gültiger Zugang oder ein Originaldownload, meldet der Manager dies; aus installierten Dateien wird kein vermeintliches Herstellerpaket zusammengesetzt. Die Erkennung benötigt keine Ausführung hochgeladener Pakete.

Vor Erweiterungsinstallationen und Sammelupdates erzeugt der Manager Datei-/SQL-Sicherungen. Gemeinsame PHP-Container werden dafür kurz pausiert und anschließend fortgesetzt. Unter **Backups** stehen die Projektsicherungen mit **Wiederherstellen** zur Verfügung. Dateien lassen sich im **Dateimanager** über **Dateien anzeigen** herunterladen. Manager-Exporte sind keine Akeeba-Archive; eine gespeicherte Projektsicherung kann als neues Projekt mit eigener Datenbank eingespielt werden. Vorhandene Projekte werden nicht überschrieben.

## Speicherorte

Unter **System → Speicherorte** werden die Ordner für Projekte, Erweiterungspakete, CMS-Archive, Akeeba-Backups und Projektsicherungen angezeigt, einschließlich belegtem und freiem Speicher. Die Pfade beziehen sich auf den **Docker-Rechner**, nicht auf einen entfernten Browser. Datenbanken bleiben in ihren bisherigen Docker-Volumes; Manager-Metadaten, Zertifikate und Zugangsdaten behalten den bisherigen Datenordner.

Neue absolute Pfade eintragen, **Speicherorte prüfen** wählen und anschließend **Daten kopieren und Speicherorte übernehmen**. Zielordner werden bei Bedarf angelegt und müssen leer, beschreibbar und ausreichend groß sein. Laufende Jobs und Uploads müssen beendet sein. Bei der Umstellung startet der Manager neu und betroffene PHP-Laufzeiten werden kurz angehalten. Dateien werden kopiert und über SHA-256 verglichen, bevor die neuen Einbindungen aktiviert werden. Bisherige Ordner werden nicht automatisch gelöscht. Eine fehlgeschlagene Umstellung setzt die bisherigen Einstellungen zurück; eventuell entstandene Zielkopien bleiben zur Prüfung erhalten.

Die Konfiguration liegt unter `data/storage/settings.json`, wird in `.env` für reguläre Starts und in `data/storage/compose.storage.json` für den Helfer übernommen. Änderungen an diesen Dateien nicht während einer Umstellung vornehmen. Externe Laufwerke müssen beim Start verfügbar sein. Die internen `/data/...`-Pfade bleiben stabil. PHP-Laufzeiten werden vor dem Anhalten anhand ihrer tatsächlichen Projekte-Einbindung auf Zugehörigkeit zu dieser Installation geprüft.

## Akeeba-Backups erstellen

Im Projekt **Akeeba Backup erstellen** wählen, ein vorhandenes Profil mit Namen und Nummer auswählen und bestätigen. Die Aktion ist unter anderem in den Zeilenaktionen und unter **Projekt → Backups** erreichbar. Die Funktion nutzt die installierte native Akeeba-CLI; Akeeba wird nicht automatisch installiert. Für Joomla wird eine unterstützte Akeeba-Installation mit aktiviertem Konsolenplugin benötigt, für WordPress die unterstützte CLI von Akeeba Backup Professional.

Der Manager erzeugt ein echtes vollständiges JPA-Archiv im eingestellten Backup-Ordner. Die gewählte Profilkonfiguration wird für diesen Lauf übersteuert: lokaler Ausgabeordner, JPA-Format, keine Cloud-Nachbearbeitung, keine Löschquoten und keine Akeeba-Abschluss-E-Mails. Gespeicherte Akeeba-Profile werden dabei nicht geändert. Die Profilfilter bleiben wirksam. Erst nach Akeebas Abschlussbestätigung und Prüfung aller Archivteile wird der Download freigegeben.

Die Dateien können einzeln heruntergeladen werden. Bei mehrteiligen Sicherungen steht zusätzlich **Alle Teile als Downloadpaket (.zip)** bereit. Dieses äußere ZIP vor einer Wiederherstellung entpacken; danach JPA und Teilarchive gemeinsam verwenden. Unvollständige Sicherungen werden als Fehler angezeigt und nicht als wiederherstellbares Backup angeboten. Datei-/SQL-Projektsicherungen bleiben eine separate Funktion.

## Manager-Updates

Die feste Updatequelle ist [TentacleGuy/Website-Manager](https://github.com/TentacleGuy/Website-Manager/releases). Unter **System → Manager-Updates** werden installierte Version, letzte Prüfung und verfügbare Aktualisierungen angezeigt. Der Manager prüft beim Start und alle sechs Stunden auf neue stabile Releases. Ein Hinweis erscheint auch außerhalb der Systemansicht.

**Jetzt nach Updates suchen** prüft manuell. Während der Installation zeigt **System → Manager-Updates** den aktuellen Schritt, die letzte Rückmeldung und das fortlaufende Docker-Protokoll. **Updatehelfer prüfen** liefert den Containerzustand, Exit-Code und dessen letzte Ausgaben. Während des Image-Baus bleibt die Oberfläche erreichbar; beim eigentlichen Neustart verbindet sie sich automatisch wieder. Das vollständige Protokoll liegt zusätzlich unter `data/updates/<Kennung>/update.log`. **Update installieren** lädt das Release-Paket samt SHA-256-Prüfsumme, prüft Version und enthaltene Pfade und startet einen separaten Docker-Helfer. Laufende Projektvorgänge müssen zuvor abgeschlossen sein. Der Helfer sichert Programmdateien und SQLite-Metadaten, ersetzt ausschließlich freigegebene Programmdateien, baut den Manager und startet ihn neu. Website-Container, `.env`, Backups, Zugangsdaten, Zertifikate und Datenbankvolumes werden beibehalten. Die Oberfläche verbindet sich wieder. Bei Fehlern werden die vorherigen Programmdateien wiederhergestellt; der Status und das Protokoll stehen unter `data/updates/`.

Der Helfer benötigt eine reguläre Compose-Installation mit `data` als Unterverzeichnis der Installation und den im Standard-Setup eingebundenen Docker-Socket. Downloadprüfung und Installation benötigen Zugriff auf GitHub. Solange noch kein öffentliches Release mit Updatepaket existiert, zeigt der Manager dies an.

Falls unter Windows ein älterer Updatehelfer mit `apply.py: No such file or directory` abbricht, das aktuelle Windows-Setup erneut entpacken und `Installieren.cmd` starten. Bei der Standardinstallation übernimmt es die Programmdateien in den bestehenden, markierten Installationsordner und baut das Manager-Image neu. `data` und `.env` sind nicht im Paket enthalten und bleiben erhalten. Bei einem individuellen Installationsordner denselben `VMM_INSTALL_DIR` wie zuvor verwenden.

### Ein Release veröffentlichen

1. Änderungen im selben Arbeitsschritt unter **Unveröffentlicht** in `CHANGELOG.md` dokumentieren.
2. Für das Release diese Einträge in einen neuen Abschnitt mit Version und Datum übernehmen; unter **Unveröffentlicht** anschließend `Noch keine Änderungen.` eintragen und `app/release.json` angleichen.
3. `python3 scripts/changelog.py --tag vX.Y.Z` und die Tests ausführen; Änderungen nach `main` übertragen.
4. Das passende Tag `vX.Y.Z` erstellen und pushen.

Der GitHub-Workflow führt Tests und Syntaxprüfungen aus und erstellt anschließend ein Release mit `manager-update.zip`, Prüfsumme und den Setup-Paketen für Windows, macOS und Linux. Tag, eingetragene Version und Changelog müssen übereinstimmen. Fehlende Einträge oder noch nicht versionierte Änderungen verhindern die Veröffentlichung. Programmänderungen ohne Änderung an der Changelog werden in der GitHub-Prüfung beanstandet. Die Versionshinweise werden als `dist/release-notes.md` aus dem passenden Eintrag erzeugt und für das GitHub-Release verwendet. Die vollständige `CHANGELOG.md` wird ebenfalls als Release-Datei beigefügt. Für einen lokalen Paketbau:

```sh
python3 scripts/build_release.py --tag vX.Y.Z
```

Die Paketbauer verwenden eine explizite Dateiliste. Lokale Projekte, `.env`, Datenbanken, Backups, Exporte, Zertifikate und Zugangsdaten sind ausgeschlossen. Kickstart wird zur Laufzeit von Akeeba geladen und nicht mitveröffentlicht.

## Entwicklung und Datenhaltung

```sh
python3 -m unittest discover -s tests -v
node --check app/static/app.js
php -l app/tools/restore-backup.php
```

Python-Standardbibliothek mit HTTP-API und SQLite; Browseroberfläche in JavaScript und CSS. Gemeinsam genutzte MariaDB sowie PHP-/Apache-Laufzeiten werden über Compose gesteuert. PHP-Unterstützung und Erweiterungen sind in `infra/runtime/Dockerfile` definiert.

`data/` enthält Manager-Metadaten, Projektdateien, Paketarchive und Schlüssel. Die Datenbankinhalte liegen je Datenbankprofil in getrennten Docker-Volumes; das frühere Standardvolume heißt `vmm-runtime_database`. Ein Kopieren des Quellcodes oder von `data/` allein überträgt diese Volumes nicht. Für einen Umzug sind zusätzlich SQL-Exporte bzw. vollständige Backups nötig. `docker compose down -v` entfernt Datenbankvolumes und gehört nicht zum normalen Aktualisieren.

## Projektordner im Dateimanager öffnen

**Dateipfad öffnen** steht in der Projektliste und der Projektübersicht. Es öffnet den Website-Ordner (`site`) im Explorer, Finder beziehungsweise Linux-Dateimanager und berücksichtigt die konfigurierten Speicherorte. Der Pfad kann zusätzlich kopiert werden.

Die lokale Startdatei des Managers richtet dafür beim nächsten Start die Desktop-Anbindung `tentacle-project://` für den aktuellen Benutzer ein. Bei einer bestehenden Installation nach Übernahme der neuen Programmdateien einmal `Starten.ps1` (Windows), `Starten.command` (macOS) oder `Starten.sh` (Linux) ausführen. Linux benötigt eine Desktop-Sitzung mit `curl` und den XDG-Werkzeugen. Beim reinen Docker-/Quellcodebetrieb kann unter macOS/Linux `bash app/installer_assets/register-folders.sh "$PWD"` ausgeführt werden; unter Windows die Funktion `Register-ProjectFolders` aus `Gemeinsam.ps1` verwenden.

Der Browser kann beim ersten Öffnen nach einer Bestätigung fragen. Die Anbindung nimmt ausschließlich Projektnamen entgegen und ermittelt den vorhandenen Ordner über den lokalen Manager; sie akzeptiert keine beliebigen Pfade oder Befehle. Bei Zugriff von einem anderen Rechner wird nur der Pfad angezeigt. Ältere Projekte in Docker-Volumes müssen zuvor auf gemeinsame Laufzeiten umgestellt werden.

### Lokale und ursprüngliche Server-Konfiguration

Beim Akeeba-Import erhält der Manager vorhandene `.htaccess`, `.user.ini` und `php.ini` als `.vmm-original`. War eine `.htaccess` vorhanden, wird die mitgelieferte `htaccess.txt` (alternativ `.htaccess.txt`) zur lokalen `.htaccess` umbenannt. Ohne vorherige `.htaccess` wird keine Vorlage aktiviert. Fehlt die Vorlage, bleibt das Original gesichert und wird nicht ungeprüft lokal aktiviert.

Akeeba-Backups über den Manager ordnen diese Originaldateien direkt beim Schreiben des JPA-Archivs wieder den ursprünglichen Namen zu. Die lokale `.htaccess` erhält dabei ihren Vorlagennamen zurück; `.vmm-original`-Doppeldateien landen nicht im Archiv. Die laufende Website wird während des Backups nicht umbenannt oder auf Produktionsregeln umgestellt. Das gilt auch für vorhandene `.vmm-original`-Dateien aus älteren Importen. Unterordner bleiben unverändert. Ein Backup wird nur als vollständig angeboten, wenn Akeeba die erwarteten Serverdateien nachweislich aufgenommen hat; ausschließende Profilfilter führen zu einer verständlichen Fehlermeldung. Auch ZIP-Projektsicherungen verwenden diese ursprünglichen Dateinamen und erhalten die lokale htaccess-Vorlage unter ihrem Vorlagennamen.

## Arbeitsbereiche und gespeicherte Dateien

Projekte stehen in einer spaltenweise filter- und sortierbaren Tabelle. Erweiterungen verwenden eine Auswahlliste mit Detailbereich. In Projekten sind Sicherungen, Zugänge und Laufzeiteinstellungen getrennte Bereiche. Die regelmäßige Aktualisierung lädt nur Daten der geöffneten Ansicht; im Hintergrund pausiert sie. Abgeschlossene Updatefehler stehen im Updateverlauf getrennt von der installierten Manager-Version.

Erweiterungen lassen sich vollständig aus der Bibliothek entfernen oder einzelne gespeicherte ZIP-Versionen löschen. Das CMS-Archiv bietet dieselbe Möglichkeit für Installationspakete. Unter **Backups** können Akeeba-Archive einschließlich aller Teilarchive, ZIP-Projektsicherungen sowie unter **Weitere Downloads** Kickstart-Dateien, ältere Manager-Downloads, Projektpapierkörbe und verbliebene Löschdateien entfernt werden. Vor der endgültigen Löschung zeigt der Dialog Umfang und Zuordnungen. Aktive Einrichtungen, Wiederherstellungen, Prüfungen und Downloads schützen benötigte Dateien. Bereits installierte Websites bleiben beim Löschen ihrer Bibliothekspakete erhalten.

### Projektprüfungen und Wiederherstellung

Die gespeicherten wiederkehrenden Aufgaben prüfen laufende, fertig eingerichtete Projekte auf Erreichbarkeit und Updates. Vorbelegt ist eine tägliche Prüfung um 09:00 Uhr in Europe/Berlin; verpasste Termine werden beim nächsten Start einmal nachgeholt. Der Aufgabenbereich zeigt Startzeit, Fortschritt und die laufenden Schritte. Die Projektprüfung kann nach dem aktuellen Schritt beendet werden. Schreibende Sicherungs- und Installationsvorgänge werden vollständig abgeschlossen.

Die Erweiterungsliste zeigt den zuletzt gespeicherten Stand; „Updates prüfen“ lädt ihn gezielt neu. Updates stehen zuerst, Joomla-Core-Erweiterungen können getrennt gefiltert werden. Die Projektübersicht zeigt die erkannte CMS-Version und den bekannten Updatezustand.

Unter Backups stehen Projektsicherungen und Akeeba-Archive nebeneinander. „Wiederherstellen“ spielt ein ZIP mit Website und Datenbank in einen neuen Projektnamen ein; vorhandene Projekte werden nicht überschrieben. Der SQL-Import verwendet das eingeschränkte Konto dieses neuen Projekts. Technische Downloads und der Projektpapierkorb sind im **Dateimanager** erreichbar. Gespeicherte Erweiterungspakete bleiben in der Erweiterungsbibliothek.

Ein Standardbenutzer wird nur im Manager gespeichert. „Backend“ verwendet diesen Benutzer, „Login →“ den gewählten Benutzer. Dazu wird ein 60 Sekunden gültiger Einmal-Link erstellt; vorhandene CMS-Passwörter werden nicht verändert. Der letzte Administrator und der gewählte Standardbenutzer sind vor versehentlicher Löschung geschützt. Bei WordPress werden Inhalte beim Löschen einem verbleibenden Benutzer zugeordnet.

### Plattformprüfungen

`python scripts/platform_smoke.py` baut Installations- und Updatepakete in einem temporären Verzeichnis, prüft Prüfsummen sowie Pfade mit Leerzeichen und den Erhalt privater Daten beim Entpacken eines Updates. Der Workflow `platform-smoke.yml` führt dies unter Windows, Linux und macOS aus; hinzu kommen Updatehelfer-Tests, JavaScript-Prüfungen und die Windows-PowerShell-Syntaxprüfung. Die vollständige lokale Testsuite startet mit `python -m unittest discover -s tests`.

## Dateimanager und Zeitpläne

Der Dateimanager bündelt gespeicherte CMS- und Erweiterungspakete, Akeeba-Archive, ZIP-Projektsicherungen, Kickstart-Dateien, Manager-Downloads und Projektpapierkörbe. Eine gemeinsame Suche über die angezeigten Spalten, sortierbare Spalten und Dateidetails helfen beim Verwalten. Ein Typ-Dropdown und einzelne Spaltenfilter sind im aktuellen Dateimanager entfernt. Löschungen verwenden dieselben Schutzprüfungen und die Papierkorbeinstellung wie die Bibliothek. Bei mehrteiligen Backups wird die gesamte Sicherungsgruppe entfernt.

Unter Aufgaben lassen sich tägliche und wöchentliche Projektprüfungen und Projektsicherungen mit Uhrzeit, Zeitzone und Projektauswahl anlegen, bearbeiten, pausieren und manuell starten. Die tägliche Projektprüfung ist vorbelegt. Der Manager muss zur Ausführung laufen; ein verpasster Termin wird beim nächsten Start einmal nachgeholt. Während eines laufenden Projektschritts beendet ein Abbruch zunächst diesen Schritt, damit keine unvollständigen Sicherungen entstehen.

Speicherorte werden beim Öffnen des Reiters geladen; ihre Größenberechnung läuft im Hintergrund. Ein Klick auf ein Pfadfeld verwendet die registrierte lokale Desktop-Anbindung für den normalen Ordnerdialog. macOS verwendet den Systemdialog, Windows den FolderBrowserDialog, Linux zenity oder kdialog. Gegebenenfalls den Manager einmal über seine lokale Starten-Datei starten. Der ausgewählte Pfad ändert nur das Formular. Erst Prüfen und Anwenden führen eine Speicherumstellung aus. Eine manuelle Pfadeingabe bleibt verfügbar.


### Dienste und Berechtigungen

Unter **System → Dienste & Rechte** prüft der Manager seine Docker-Anbindung, das interne Netzwerk, den Zustand der eigenen Dienste und den Zugriff auf alle Speicherbereiche. Für jeden Speicherbereich wird eine kleine temporäre Datei geschrieben, gelesen und entfernt. Bei laufenden PHP-Diensten werden zusätzlich die Dateirechte des PHP-Benutzers für die aktiven Projektordner geprüft. Das ist keine vollständige Prüfung jeder Datei einer Website.

Die eigenen Dienste können gestartet, neu gestartet und beendet werden. Laufende Aufgaben und Dateiübertragungen verhindern das Beenden benötigter Dienste. Ein bewusst gestopptes PHP startet bei einem erneuten Website-Aufruf wieder bei Bedarf. Fehlende Gateway-/DNS-Container richtet die lokale **Starten**-Datei ein. Ein Manager-Neustart unterbricht kurz die Oberfläche; nach dem Beenden muss der Manager über die lokale **Starten**-Datei gestartet werden. Docker Engine bzw. Docker Desktop selbst lassen sich aus einem beendeten Manager nicht steuern.

**Ordnerfreigabe anfragen** testet die lokale Ordneranbindung und öffnet den nativen Auswahldialog. Der Test verändert keine Speicherorte. **Ordneranbindung erneut einrichten** erneuert die vorhandene Registrierung für den aktuellen Benutzer und öffnet denselben Dialog. Fehlt die Registrierung vollständig, muss zuerst die lokale **Starten**-Datei ausgeführt werden. Die Anbindung läuft nur bei Bedarf; sie ist kein Hintergrunddienst. Finder/Explorer lassen sich aus einer gewöhnlichen Website nicht auf allen Betriebssystemen allein mit einem Link öffnen. Abgelehnte Browser- oder Betriebssystemfreigaben können nicht aus der Website zwangsweise zurückgesetzt werden; Hinweise stehen direkt in der Oberfläche.


### Dateimanager und Papierkorb

Der **Dateimanager** zeigt alle gespeicherten Pakete und Archive in einer Liste. Die Suche über der Liste berücksichtigt alle angezeigten Spalten; über die Spaltenüberschriften kann sortiert werden. Im Reiter **Papierkorb** lassen sich Dateien wiederherstellen oder nach Bestätigung endgültig entfernen. Wiederherstellen überschreibt keine inzwischen vorhandenen Dateien und stellt die gespeicherten Bibliotheksdaten wieder her. Bereits gelöschte Projekte können unter ihrem ursprünglichen Namen wiederhergestellt werden und erscheinen anschließend gestoppt im Manager. Die aufbewahrte Projektdatenbank wird wiederverwendet; falls sie fehlt, wird der gesicherte SQL-Export eingespielt. Projekte mit verknüpften Dateien werden zur manuellen Prüfung angehalten.

Unter **System → Löschen & Papierkorb** kann zwischen direkter endgültiger Löschung und vorherigem Verschieben in den Papierkorb gewählt werden. Voreinstellung für gespeicherte Pakete und Archive ist **Papierkorb mit 30 Tagen Aufbewahrung**. Die Aufbewahrung kann auf 1–3650 Tage gesetzt werden. Sie gilt für künftige Löschungen; bereits vorhandene Einträge behalten ihr angezeigtes Ablaufdatum. Abgelaufene Einträge werden bei laufendem Manager ungefähr minütlich geprüft und im Hintergrund endgültig entfernt. Die Bereinigung wartet laufende Aufgaben ab und wird im Activity Log protokolliert. Bei beendetem Manager erfolgt sie nach dem nächsten Start.

Pakete und Archive bleiben im Papierkorb als versteckte Dateien im jeweiligen Speicherbereich, damit auch getrennte Laufwerke ohne umfangreiche Kopie unterstützt werden. Die zugehörigen Metadaten liegen in der Manager-Datenbank. Beim Umstellen von Speicherorten werden diese Dateien ebenfalls mitkopiert. Der normale Projektlöschvorgang legt weiterhin zuerst eine Projektsicherung im Projektpapierkorb an. Vorhandene Projektpapierkörbe werden beim Einführen dieser Funktion mit einer neuen vollen Aufbewahrungsfrist übernommen und deshalb nicht rückwirkend sofort gelöscht.
