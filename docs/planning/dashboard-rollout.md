# Eigene Wolfs-Garage-Startseite: Entwurf und Einführung

> Anonymisierte historische Dokumentation für das öffentliche Repository. Betriebsdomain, Host-/Speicherkennungen und private Pfade sind Beispiele; konkrete Betreiberzuordnungen sind verallgemeinert. Kein direkt ausführbares Runbook. Die unveränderten Originale liegen ausschließlich lokal unter dem ignorierten Verzeichnis `.sandbox/private-ops/`. Prüfresultate betreffen die damals untersuchte Instanz, nicht die hier eingesetzten Beispielwerte.

**Umgesetzt am 2026-10-28:** Die neue Startseite wurde nach ausdrücklicher Freigabe aktiviert. Aktueller Betriebs- und Prüfstand: [Bereitstellungsbericht](../discovery/deployment-2026-10-27.md#dashboard-update-am-2026-10-28). Die nachfolgende Einführungsplanung dokumentiert den vorbereiteten Stand.

Stand: 2026-10-28. Der Betreiber wünscht eine eigene, einfachere Oberfläche. Die neue Startseite und der Adapter sind lokal umgesetzt; die laufende Garage bleibt bis zur Freigabe für diese produktive Änderung unverändert. [Aktueller Betrieb](../discovery/deployment-2026-10-27.md).

## Funktionen und Grenzen

Die neue Seite zeigt Fahrzeuge, hinterlegte Erinnerungen und letzte Wartungen. Sie verwendet keine externen Schriften oder Skripte, hat Lade-, Leer- und Fehlerzustände und führt über `Verwalten` zur bestehenden LubeLogger-Oberfläche. Anlegen und Ändern von Fahrzeugen und Einträgen erfolgen in dieser ersten Ausbaustufe weiterhin dort. Einheiten, Währungen und Kilometerstände werden nicht geraten; fehlende Werte bleiben entsprechend gekennzeichnet oder verborgen.

Der [Leseadapter](../../garage_gateway/README.md) liest nur dokumentierte LubeLogger-Endpunkte. Bei deaktivierter nativer LubeLogger-Anmeldung ist seine Netzwerkverbindung privilegiert; deshalb müssen App, Adapter und Router im isolierten Origin-Netz bleiben. Die vorhandene Access-Policy und die Tokenprüfung im Cloudflare-Tunnel schützen weiterhin alle öffentlichen Wege. Der Adapter ist keine eigene Anmeldung oder Rollenverwaltung. Der Reminder-Leseweg wurde auf Quellebene geprüft; ein neuer Laufzeitnachweis, dass er keine vorhandenen Daten ändert, steht noch aus.

Ein Nginx-Router liefert die Startseite unter `/` und leitet `/garage-api/` und `/garage-assets/` an den Adapter weiter. Native Pfade wie `/Home`, Dateien und `/api/ws` gehen an LubeLogger. Unveränderte native Webfunktionen können weiterhin die in WP01/WP02 dokumentierten Upstream-Seiteneffekte haben; sie sind nicht schreibgeschützt. Die Router-Konfiguration unterstützt WebSocket-Upgrade und Uploads; diese Fälle sind im Live-Verbund noch nicht praktisch abgenommen. Der [synthetische Reminder-Laufzeittest](../discovery/dashboard-reminder-runtime.md) fand bei fünf GETs für einen Testdatensatz keine Änderung der Datenbankdateien; das ist keine Aussage über alle Datenkonstellationen.

## Konkreter Änderungsumfang nach Freigabe

1. Den momentanen Zustand des eigenen Tunnels und der Compose-Konfiguration sichern; keine Fahrzeugdaten migrieren oder löschen.
2. Die versionierten Dashboard-Dateien in den bestehenden Container `<CTID>` übertragen; Images anhand der geprüften Digests bauen und konfigurieren. Die [Compose-Ergänzung](../../deploy/compose.dashboard.yaml) fügt nur Router und Leseadapter auf dem bestehenden internen Origin-Netz hinzu. Das bestehende LubeLogger-Volume und der Connector bleiben erhalten.
3. Innerhalb des Containers Startseite, Adapter, native Oberfläche, Assets und Upload-/WebSocket-Weiterleitung prüfen. Vor dem Umschalten die funktionsfähige Router- und Zugangsprüfung dokumentieren.
4. Nur die bestehende Route `garage.example.invalid` des separaten Tunnels von `http://lubelogger:8080` auf `http://garage_router:8080` umstellen. Audience, `Protect with Access`, restliche Routen und Access-Policy bleiben bestehen. Keine Änderung am anderen Tunnel oder DNS erforderlich.
5. Anonymen Zugriff, gefälschte Identitätsheader, Anmeldung und Originalverwaltung erneut prüfen. Der Betreiber bestätigt die Darstellung und den Login. Wenn ein Test scheitert, die vorherige Route des eigenen Tunnels wiederherstellen; Daten und Volumes bleiben erhalten.

Die obigen Schritte waren der Einführungsentwurf. Vor der tatsächlichen Umschaltung wurde ein einmaliges Containerbackup erstellt und sein Archiv geprüft; ein regelmäßiges Backup und ein Restore sind weiterhin nicht nachgewiesen.

## Lokal geprüfter Stand

- Adapter: vier synthetische HTTP-Tests, darunter Fehlerfälle und begrenzte Upstream-Routen.
- Frontend: Mock-Tests für leere Garage, Fehler, Fahrzeugdaten und sichere Textdarstellung.
- Chromium: synthetischer Fahrzeug- und Wartungsdatensatz bei 320, 390, 768 und 1280 Pixeln; keine horizontale Seitenverbreiterung, ausgewählte Fahrzeugkarte und Verwaltungslink geprüft.
- Nginx: Konfigurationssyntax mit festem Image-Digest und eingeschränkten Capabilities; lokaler synthetischer Routentest für Startseite, API, native Seite, Asset-Pfad und POST an `/`. Keine Aussage über alle Upstream-Funktionen, Cloudflare, echte Daten oder WebSocket-/Upload-Verhalten.

Für den Browserlauf dienten ausschließlich lokale synthetische Daten; der Testserver und Test-Router wurden anschließend beendet. Der [mobile Vorschaustand](../discovery/evidence/dashboard-preview-mobile.png) ist ein Testbild mit erfundenem Fahrzeug.

Zur lokalen Wiederholung den synthetischen Server mit `python3 tests/dashboard_preview.py` starten und nach dem Test mit Strg+C beenden. Der Browserlauf verwendet `tests/dashboard_browser.cjs`, das gepinnte Testimage `mcr.microsoft.com/playwright:v1.55.0-noble` und Docker-Hostnetz, um den ausschließlich an `127.0.0.1:18980` gebundenen Testserver zu erreichen. Der Nginx-Routentest nutzte lokale Stub-Origins; ein End-to-End-Test mit dem tatsächlichen Tunnel und der persönlichen Access-Sitzung steht aus.
