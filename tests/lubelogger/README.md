# Lokale LubeLogger-Vertragsprüfung (B01/B02)

Ausschließlich synthetische Erprobung, keine Garage-Anwendung und keine Produktivkonfiguration. Ziel ist [v1.7.4 mit festem Digest](target.lock.json), Plattform `linux/amd64`. Die Zielwahl ist nur eine Testbaseline. Die [unabhängige Matrix](acceptance-matrix.md) enthält den breiteren Prüfplan; tatsächliche Ergebnisse und verbleibende Grenzen stehen im [Laufzeitbericht](../../docs/discovery/lubelogger-runtime-verification.md).

## Ausführen

Voraussetzungen: Linux, Python ≥3.9 mit System-Zeitzonendaten, Docker Engine und Compose sowie lokaler Zugriff auf Docker-Brückenadressen. Getestet mit Python 3.13, Docker 29.9.2 und Compose v5.6.1. Keine Python-Pakete erforderlich. Docker-Zugriff wird vorausgesetzt; der Treiber ändert keine Hostinstallation oder Daemonkonfiguration. Docker Desktop/rootless und andere Plattformen sind nicht abgenommen.

Aus dem Repository:

```bash
python3 tests/lubelogger/run.py
```

Compose lädt bei Bedarf ausschließlich das gepinnte Image. Externe Registry-Erreichbarkeit wird nur zum Herunterladen benötigt. Pro Lauf erzeugt der Treiber einen zufälligen `wolfs-b02-*`-Projektnamen und neue Volumes. Es gibt keine Option für produktive URLs, bestehende Projekte, Zugangsdaten oder reale Fixtures. Root, Nicht-Root-Owner und Outsider sowie API-Schlüssel werden zufällig bzw. synthetisch provisioniert und nur im Speicher benutzt. API-Key-Rechtetests nutzen getrennte Clients ohne Cookie/Basic-Authentifizierung.

Die Container haben keine veröffentlichten Ports, keinen Standard-IPv4-Route und ausschließlich ein internes Docker-Netz. Hostzugriff erfolgt auf die Container-Brückenadresse. Ein lokaler Webhook-Recorder bindet ausschließlich an die Docker-Brückenadresse; ein Antwortverlust-Proxy ausschließlich an Loopback. Keine Tunnel-, Telegram-, Google-, Paperless- oder KI-Verbindung. Die zweite Instanz dient ausschließlich Restore mit eigenen Daten-/Schlüsselvolumes.

MVC-Routen bedienen Setup, Reminder und Teileverwendung in der Testinstanz per HTTP. Das ist keine visuelle Browserprüfung und kein empfohlener Garage-Integrationsvertrag. Der Testsatz verändert nur selbst erzeugte synthetische Testdaten. Jahresberichte, Herstellerregeln und Bedienbarkeit werden damit nicht abgenommen.

## Ergebnisse und Ressourcen

Ergebnis je Lauf: `.sandbox/<projekt>/results.json`. Der Treiber schreibt keine Cookies, Passwörter, Einladungs- oder API-Schlüssel in dieses Ergebnis; Fehlerausgaben der Operationen enthalten nur Pfad und Status. Backup-ZIP mit synthetischen Daten und Credential-Hashes verbleibt ausschließlich im ignorierten, mit Modus 0700 angelegten Laufverzeichnis. Ergebnisse vor Aufnahme in Git zusätzlich prüfen.

- `pass`: der benannte Vertrag wurde beobachtet; keine pauschale Anforderungserfüllung.
- `gap`: eine konkret benannte Upstream-Grenze wurde reproduziert. Sie gilt weiterhin als Produkt-/Integrationslücke.
- `fail`: unerwartetes Verhalten oder Fehler im Treiber; Abbruch, Exitcode 1.

Exitcode 0 bedeutet **keine unerwartete Abweichung im Testsatz**, nicht „produktionsreif“. Auch bei einem erfolgreichen Lauf können `gap`-Befunde bestehen. Der Treiber stoppt die Sandbox-Container im `finally`-Block. Images, gestoppte Container, Netze, synthetische Volumes und ignorierte Laufartefakte werden behalten; es gibt keine automatische Löschung. Bei fehlgeschlagenem Stopp bleibt `containersStopped=false` sichtbar und der Exitcode ist ungleich null. SIGKILL/Hostausfall kann `finally` verhindern; aktive Ressourcen dann anhand des ausgegebenen Projektnamens prüfen.

Das versionierte [Beispielergebnis](../../docs/discovery/evidence/lubelogger-b02.json) enthält die geprüfte Harness-/Compose-Prüfsumme. Änderungen am Treiber erfordern einen neuen Lauf, bevor dieses Ergebnis als Evidenz für den neuen Stand gilt.

## Upstream-Dateien

`upstream/api.v1.7.4.json` ist unverändert aus dem geprüften Release übernommen und bytegleich aus dem laufenden Image abgerufen. Es ist ein eigenes API-Dokumentationsformat, **kein OpenAPI-Schema**. `upstream/LICENSE` bewahrt die MIT-Hinweise. Hashes, Quelle und Release stehen in `target.lock.json`; direkte NuGet-Lizenzen und die noch ausstehende vollständige Containerinventur im [Quellenbericht](../../docs/discovery/lubelogger-source-verification.md).
