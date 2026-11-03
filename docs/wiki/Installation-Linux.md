# Installation unter Linux

Unter Linux müssen Docker Engine und das Compose-Plugin bereits installiert und für den eigenen Benutzer erreichbar sein. Der Installer installiert Docker nicht selbst.

## Einrichten

1. Das Linux-ZIP aus den [Releases](https://github.com/TentacleGuy/Website-Manager/releases) vollständig entpacken.
2. Im entpackten Setup-Ordner ausführen:

   ```sh
   bash Installieren.sh
   ```

3. Warten, bis der Manager unter **http://localhost:8090/** erreichbar ist.
4. Für lokale Projektdomains und HTTPS im **Installationsordner** ausführen:

   ```sh
   sudo bash Systemeinrichtung.sh
   ```

Der Standardordner lautet `${XDG_DATA_HOME:-$HOME/.local/share}/Tentacle/WebsiteManager`. Ein individuelles Ziel lässt sich über `TENTACLE_INSTALL_DIR` vorgeben.

## DNS und Zertifikate

Der Systemhelfer erwartet aktives `systemd-resolved` und richtet `vmm.test` über `127.0.0.1:1053` ein. Für den Zertifikatsspeicher verwendet er `update-ca-certificates` oder `update-ca-trust`. Bei einem anderen Resolver oder nicht unterstützten Zertifikatsspeicher hält er mit einer Meldung an; diese Umgebung benötigt eine manuelle Einrichtung.

Browser mit eigenem Zertifikatsspeicher können zusätzlich das öffentliche `data/certs/rootCA.pem` benötigen. Private Schlüssel nicht weitergeben.

## Später starten

Im Installationsordner ausführen:

```sh
bash Starten.sh
```

Für die lokale Ordneranbindung ist eine Desktop-Sitzung mit `curl` und XDG-Werkzeugen nötig. Die native Ordnerauswahl verwendet `zenity` oder `kdialog`; alternativ einen Pfad manuell eintragen.

Weiter: [Projekt erstellen](Projekte.md) oder [Fehler beheben](System-und-Fehlerbehebung.md).
