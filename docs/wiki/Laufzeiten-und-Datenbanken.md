# PHP-Laufzeiten und Datenbanken

Die passende Kombination richtet sich nach CMS, Erweiterungen und gegebenenfalls dem enthaltenen Wiederherstellungsprogramm. Eine hohe Versionsnummer allein bedeutet nicht, dass eine ältere Website kompatibel ist.

## PHP und Projektadressen

| PHP-Serie | HTTP-Port | HTTPS-Port |
| --- | --- | --- |
| 7.4 | 8074 | 8174 |
| 8.0 | 8080 | 8180 |
| 8.1 | 8081 | 8181 |
| 8.2 | 8082 | 8182 |
| 8.3 | 8083 | 8183 |
| 8.4 | 8084 | 8184 |
| 8.5 | 8085 | 8185 |

Beispiel für PHP 8.4: `http://meine-website.vmm.test:8084/` beziehungsweise `https://meine-website.vmm.test:8184/`. Die angebotenen Serien sind die Profile des Projekts, keine Aussage über ihren aktuellen Hersteller-Support.

Eine PHP-Laufzeit bedient mehrere Projekte derselben Serie. Beim ersten Start muss gegebenenfalls ein Image gebaut werden. Eine falsche Kombination aus HTTP/HTTPS und Port wird korrigiert; für eine HTTPS-Verbindung muss das Zertifikat bereits vertraut sein.

## Datenbank auswählen

Für neue Projekte stehen MariaDB **10.11, 11.4 und 11.8** sowie MySQL **8.0 und 8.4** bereit. **Automatisch** bevorzugt MariaDB 11.4, soweit deklarierte Projektanforderungen das erlauben. Jede Serie erhält einen eigenen Dienst und ein eigenes Volume; sie wird bei Bedarf bereitgestellt.

Vorhandene Projekte behalten das Profil **Bestehende Datenbank**. Die tatsächliche bisherige Datenbankversion wird festgehalten. Unbekannte oder unversionierte Images müssen vor einer Umstellung geprüft werden. Es gibt kein automatisches Upgrade oder Downgrade vorhandener Datenbankvolumes.

## Anforderungen ergänzen

Der Manager berücksichtigt deklarierte CMS-, Composer-, WordPress- und Joomla-Anforderungen sowie PHP-Module. Unvollständige Herstellerangaben ersetzen keinen Praxistest.

Zusätzliche Vorgaben können im Projekt- oder Erweiterungsordner in `.tentacle-requirements.json` stehen:

```json
{
  "php": ">=8.3 <8.5",
  "php_extensions": ["soap", "intl"],
  "database": {"mysql": ">=8.4", "mariadb": ">=11.4"}
}
```

Sind Datenbankfamilien angegeben, sind nur diese zulässig. Widersprüchliche Anforderungen stoppen die Einrichtung. Beim Backup-Import wird eine dokumentierte PHP-Serie bevorzugt, wenn sie die Anforderungen erfüllt.
