# Benutzer und Zugangsdaten

CMS-Benutzer, gespeicherte Zugangsdaten und Erweiterungslizenzen haben unterschiedliche Aufgaben.

## CMS-Benutzer verwalten

Unter **Projekt → Benutzer** steht der zuletzt gespeicherte Benutzerbestand. **Benutzerliste aktualisieren** liest ihn erneut aus dem CMS.

- **Neuen Benutzer anlegen** erstellt einen tatsächlichen CMS-Benutzer.
- **Passwort zurücksetzen** öffnet das Formular für den gewählten Benutzer.
- **Als Standard wählen** merkt den Benutzer für die Backend-Aktion dieses Projekts vor.
- **Login →** öffnet das Backend als dieser Benutzer.
- **Löschen** entfernt den Benutzer nach Bestätigung aus dem CMS.

Der Standardbenutzer ist eine Manager-Einstellung. **Backend** nutzt ihn, sofern er gewählt ist; ohne Auswahl wird die normale Backend-Adresse geöffnet. Der direkte Login verwendet einen 60 Sekunden gültigen Einmal-Link und ändert kein CMS-Passwort. Pop-ups für den Manager müssen erlaubt sein. Gesperrte Benutzer können nicht als Standard oder für diesen Login verwendet werden.

Der letzte Administrator und der ausgewählte Standardbenutzer sind vor versehentlicher Löschung geschützt. Bei WordPress werden Inhalte einem verbleibenden Benutzer zugeordnet.

## Zugangsdaten ablegen

Die Zugangsdatenfunktion speichert Bezeichnung, Benutzername, Passwort, URL und Notizen. Ein dort eingetragener Zugang erstellt keinen CMS-Benutzer und ändert kein CMS-Passwort.

Daten und Schlüssel im Manager-Datenordner gehören zusammen gesichert. Den Ordner nicht öffentlich bereitstellen oder in Git aufnehmen. Der Manager selbst hat keine Anmeldung; Zugriff auf den Manager ermöglicht auch Zugriff auf seine Verwaltungsfunktionen.

Lizenz-/API-Keys für Downloads werden unter [Erweiterungen und Lizenzen](Erweiterungen-und-Lizenzen.md) beschrieben.
