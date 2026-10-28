# Bereitstellung auf Proxmox und Cloudflare

> Anonymisierte historische Dokumentation für das öffentliche Repository. Betriebsdomain, Host-/Speicherkennungen und private Pfade sind Beispiele; konkrete Betreiberzuordnungen sind verallgemeinert. Kein direkt ausführbares Runbook. Die unveränderten Originale liegen ausschließlich lokal unter dem ignorierten Verzeichnis `.sandbox/private-ops/`. Prüfresultate betreffen die damals untersuchte Instanz, nicht die hier eingesetzten Beispielwerte.

## Überarbeitete Fahrzeugicons am 2026-10-28

Nach Betreiberfeedback wurden die ersten Fahrzeugzeichnungen durch überarbeitete Icons aus Health Icons und Material Design Icons ersetzt; Herkunft und Lizenzen stehen in `frontend/vehicle-icons-LICENSE.md`. Ein eigenes Icon für Schrägheck wurde ergänzt. Die Typbezeichnung bleibt für Screenreader verfügbar, ist aber auf der Karte nicht als Text sichtbar.

Der Betreiber bestätigte weitere Fahrzeugtypen. Für einen Hochdachkombi wurde neben einer bestehenden Modellbezeichnung eine ausdrücklich bestätigte Modellvariante ergänzt; ein weiteres Fahrzeug erhielt den Typ Schrägheck. Die konkreten Hersteller-/Modellpaare verbleiben in der privaten Betriebsdokumentation. Die neuen Vorbelegungen befinden sich in `/etc/garage-example/vehicle-types-v4.json`; die ältere Datei bleibt erhalten. Die vorhandenen LubeLogger-Fahrzeugdaten wurden nicht geändert.

Der Gateway wurde gezielt neu gebaut und neu gestartet. Router, Tunnel, LubeLogger und Datenvolumes blieben in Betrieb. Die aktive Version liegt unter `/srv/garage-example/dashboard-release-v4` und verwendet die v4-Compose-Ergänzungen und Parameterdatei mit Projektname `wolfs-garage`. Der vorherige Image-Stand `wolfs-garage-garage_gateway:pre-icon-refresh` und das v3-Release sind als Rückweg vorhanden; die nachfolgenden Angaben zu v2/v3 sind historisch.

Die vorhandenen Fahrzeugtyp-Zuordnungen wurden intern geprüft, ohne Fahrzeugdaten auszugeben. Startseite, CSS/JS, Markenlogos und native Verwaltung antworteten; die öffentliche Adresse und API leiten ohne Anmeldung zu Cloudflare Access. Die synthetischen Browser- und DOM-Tests umfassten die fünf Fahrzeugarten und vier Bildschirmbreiten. Die persönliche Sichtprüfung des Betreibers steht noch aus.

## Fahrzeugart-Symbole am 2026-10-28

Die Typbezeichnung ist auf der Fahrzeugkarte nicht mehr als Text sichtbar; stattdessen zeigen größere Symbole Limousine, Cross-Motorrad, Hochdachkombi und Naked Bike. Für Screenreader bleibt der ausdrücklich gesetzte Typ im Kartennamen vorhanden. Markenlogos und schwarz-weiße Kennzeichen bleiben erhalten; Opel- und Suzuki-Logos wurden ergänzt.

Der Betreiber hat weitere private Vorbelegungen für einen Hochdachkombi und ein Naked Bike genannt. Die Werte ergänzen die bestehenden Zuordnungen in `/etc/garage-example/vehicle-types-v3.json`. Bei der Einrichtung waren die beiden neuen Fahrzeuge in LubeLogger noch nicht angelegt. Die Datei wird vom Adapter gelesen; die LubeLogger-Fahrzeugdaten wurden nicht verändert. Ein explizites Fahrzeug-Zusatzfeld `Fahrzeugtyp` hat weiterhin Vorrang.

Der Gateway wurde gezielt neu gebaut und neu gestartet; Router, Tunnel, LubeLogger und Datenvolumes blieben bestehen. Die aktive Version liegt unter `/srv/garage-example/dashboard-release-v3`; für Compose-Verwaltung sind Basisdatei, beide v3-Ergänzungen, die v3-Parameterdatei und Projektname `wolfs-garage` zu verwenden. Das Image `wolfs-garage-garage_gateway:pre-vehicle-icons` und das v2-Release sind als Rückweg erhalten. Die folgenden Angaben zu v2 sind historisch.

Geprüft wurden die bestehenden Fahrzeugtyp-Zuordnungen, die private Zuordnungsdatei unter der nicht privilegierten Gateway-UID, Auslieferung von Startseite, Assets, Opel-/Suzuki-Logos und `/Home`, sowie externe Weiterleitung zur Cloudflare-Anmeldung. Die synthetischen Browserprüfungen umfassten alle vier Symbole auf vier Bildschirmbreiten und den Screenreader-Namen. Der persönliche Browsercheck bleibt dem Betreiber überlassen.

## Fahrzeugkarten-Update am 2026-10-28

Nach der Bestätigung der Vorschau wurden Fahrzeugtypen, groß angeschnittene Markenlogos und die schwarz-weiße Kennzeichenansicht aktiviert. Der Adapter wurde im bestehenden LXC `<CTID>` gezielt neu gebaut und neu gestartet; Router, LubeLogger, Tunnel und Datenvolumes blieben in Betrieb. Ein eigenes Image-Tag `wolfs-garage-garage_gateway:pre-vehicle-types` und die bisherige Dashboard-Konfiguration bleiben als Rückweg erhalten.

Die ausdrücklich vom Betreiber genannten Zuordnungen liegen als private Datei `/etc/garage-example/vehicle-types.json` im rootgeschützten Verzeichnis und werden nur lesend in den Adapter eingebunden. Die Datei selbst ist für den nicht privilegierten Container-User lesbar; der Hostverzeichnispfad ist auf root beschränkt. An LubeLogger-Fahrzeugdatensätzen wurde nichts geändert. Ein fahrzeugbezogenes LubeLogger-Zusatzfeld `Fahrzeugtyp` hat Vorrang; die Vorbelegung gilt ansonsten für das exakte Hersteller-/Modellpaar und wird beim Adapterstart geladen.

Interne Prüfungen bestätigten die gewünschten Fahrzeugtypen, die Startseite, Logos, CSS/JS und `/Home`; persönliche Fahrzeugdaten wurden bei der Prüfung nicht ausgegeben. Ohne Anmeldung leiteten `/`, `/garage-api/vehicles`, eine Logodatei und `/Home` zu Cloudflare Access. Die lokale Vorschau wurde auf vier Bildschirmbreiten einschließlich Kennzeichen getestet. Ein erneuter persönlicher Browsercheck nach dem Update steht noch aus.

Die aktive Ergänzung liegt im Gast unter `/srv/garage-example/dashboard-release-v2` und umfasst die private Compose-Ergänzung für Fahrzeugtypen zusätzlich zu der bisherigen Basis. Für spätere Compose-Verwaltung sind die Basisdatei und beide Ergänzungen mit der Parameterdatei des v2-Releases und Projektname `wolfs-garage` zu verwenden. Die ursprüngliche Version und das frühere Image wurden nicht gelöscht. Die einmalige Sicherung und die offene Wiederherstellungsprüfung stehen im folgenden Dashboard-Abschnitt.

## Dashboard-Update am 2026-10-28

Auf ausdrückliche Freigabe wurde die eigene Wolfs-Garage-Startseite aktiviert. Im bestehenden Container `<CTID>` laufen ergänzend der Leseadapter und ein Nginx-Router auf dem privaten Origin-Netz. Der eigene Cloudflare-Tunnel leitet `garage.example.invalid` auf den Router; Access-Policy, Audience, `Protect with Access`, DNS und übrige Tunnelrouten blieben unverändert. LubeLogger, cloudflared und die vorhandenen Daten-/Key-Volumes wurden nicht neu erstellt oder angehalten. Die native Oberfläche ist unter `/Home` erreichbar und weiterhin für das Anlegen und Bearbeiten zuständig.

Vor der Umschaltung wurde ein Proxmox-Snapshotbackup des laufenden LXC auf dem vorhandenen Speicher `<BACKUP_STORAGE>` erstellt. Der konkrete Archivname und seine Größe verbleiben in der privaten Betriebsdokumentation. `zstd -t` bestand. Ein Archivtest ist kein vollständiger Restore-Test; ein regelmäßiger Backupplan und eine getestete Wiederherstellung bleiben offen. Das Backup kann persönliche Daten und das Tunnel-Token enthalten und muss geschützt bleiben.

Intern antworteten die Dashboard-Startseite, CSS/JS, Fahrzeug-API und native `/Home`- und Asset-Pfade mit HTTP 200. Die API lieferte eine gültige Fahrzeugliste und für ein vorhandenes Fahrzeug eine strukturell gültige Erinnerungs- und Wartungsübersicht; persönliche Daten wurden dabei nicht ausgegeben. Der externe Aufruf ohne Anmeldung und mit gefälschten Identitätsheadern wurde für `/`, `/garage-api/vehicles`, `/garage-assets/app.js` und `/Home` jeweils zur Cloudflare-Anmeldung weitergeleitet. Cloudflare meldete den Tunnel anschließend als gesund; ein Konfigurationsvergleich bestätigte, dass ausschließlich das Origin-Ziel geändert wurde. Der erfolgreiche angemeldete Zugriff auf die neue Seite und alle nativen Funktionen muss im Browser des Betreibers bestätigt werden; Uploads und WebSockets sind noch nicht Ende-zu-Ende abgenommen.

Die Dashboard-Version liegt im Gast unter `/srv/garage-example/dashboard-release-v1`; die ergänzende Compose-Datei und nicht versionierte lokale Parameterdatei befinden sich dort. Für Verwaltung der vier Services muss die ursprüngliche Compose-Datei zusammen mit dieser Ergänzung und deren Parameterdatei verwendet werden, jeweils mit Projektname `wolfs-garage`. Die ursprüngliche Tunnel-Originadresse war `http://lubelogger:8080`; ein Rückfall darf nur die Route des eigenen Tunnels zurückstellen und muss die bestehende Access-Prüfung erhalten. Keine Datenvolumes löschen.

Stand: 2026-10-27. Der Betreiber hat den eigenen Proxmox-Container und die Veröffentlichung unter `garage.example.invalid` beauftragt. Es wurde eine neue, zunächst leere LubeLogger-Instanz eingerichtet; keine bestehenden Fahrzeugdaten wurden migriert.

## Laufender Stand

- Proxmox `PVE-BEISPIEL`, eigener unprivilegierter Debian-12-LXC `<CTID>` mit betreiberspezifisch gewählten CPU-/RAM-/Speicherressourcen auf `<ROOT_STORAGE>`. Im geprüften Aufbau waren `nesting=1` und `onboot=1` gesetzt. DHCP lieferte eine Adresse; der separate Tunnel baut seine Verbindung ausgehend auf und benötigt keine feste LAN-Adresse.
- Docker Engine 29.9.2, Compose 5.6.1; Storage-Treiber `overlayfs`, cgroup v2. Die Konfiguration liegt im Gast unter `/srv/garage-example/compose.yaml` mit separater lokaler Parameterdatei. Ihre Grundlage ist die versionierte [Compose-Datei](../../deploy/compose.production.yaml).
- LubeLogger v1.7.4 mit dem in `tests/lubelogger/target.lock.json` geprüften Image-Digest, ohne native Anmeldung. Data und DataProtection-Keys liegen in getrennten Docker-Volumes. Die App veröffentlicht keinen Port auf dem Gast; ihr internes Netzwerk wird mit dem Connector geteilt.
- Eigenständiger remote verwalteter Cloudflare-Tunnel `<GARAGE_TUNNEL>` mit `cloudflared` 2026.10.5; Image-Digest `sha256:1b1d34d0a9c0bfca9de72db8460d328db3f19edd2b96169114e3e893a97bbe53`. Das Tunnel-Token liegt ausschließlich in einer geschützten Datei im Gast, nicht im Repository oder in Prozessargumenten. Der Connector hat zusätzlich ein ausgehendes Docker-Netz.
- Access-Anwendung `<GARAGE_ACCESS_APP>` mit One-Time-PIN und Allow-Policy für die ausdrücklich freigegebene Betreiberidentität; die konkreten Identitätsdaten bleiben privat. Tunnel-Origin-Option **Protect with Access** verlangt ein für die Garage-Anwendung ausgestelltes Token; nicht zutreffende Tunnelrouten enden mit 404. Der proxied CNAME `garage.example.invalid` zeigt auf den eigenen Tunnel. Bestehende Tunnel und Anwendungen wurden nicht verändert.

## Prüfungen und Grenzen

- Der zuvor unklare Anlageauftrag wurde über den eingerichteten gepinnten SSH-Zugang auf `PVE-BEISPIEL` anhand der Auftrags-ID in der Containerbeschreibung und des abgeschlossenen Proxmox-Tasks `vzcreate` mit Status `OK` abgeglichen. Es wurde keine zweite Anlage ausgelöst. Das Homelab-Plugin kann seinen ursprünglichen Auftragsstatus dennoch weiterhin als `uncertain` anzeigen.
- Beide Docker-Container laufen; der Tunnel meldet `healthy` und vier aktive Verbindungen. Ein interner Aufruf des LubeLogger-Origins antwortete mit HTTP 200. Ein Test vom Entwicklungsrechner zur Gastadresse auf Port 8080 konnte keine Verbindung herstellen; Docker meldet keine veröffentlichte Portzuordnung.
- Externe Anfragen ohne Anmeldung an `/`, `/api/whoami` sowie beispielhafte Upload- und Dokumentpfade erhielten eine Weiterleitung zur Cloudflare-Access-Anmeldung. Dasselbe gilt für gefälschte Identitäts- und JWT-Header. Die Anmeldeseite selbst antwortete mit HTTP 200. Das ist kein vollständiger Test aller möglichen Pfade oder ein Nachweis eines erfolgreichen Logins.
- Ein erfolgreicher persönlicher OTP-Login und die Bedienung nach dem Login müssen vom Betreiber bestätigt werden. Eine andere Identität, abgelaufene Tokens, Wiederherstellung, Browser-CSRF und vollständige Abschirmung aller nicht vorgesehenen Netzwerksegmente wurden noch nicht Ende-zu-Ende geprüft.
- Nachtrag 2026-10-28: Der Betreiber zeigte einen Screenshot der LubeLogger-Einstellungen unter der Garage-Adresse. Das belegt den Zugriff auf die Oberfläche nach dem Einrichten; die übrigen genannten Negativ- und Wiederherstellungstests bleiben offen.
- Es gibt noch **keinen nachgewiesenen regelmäßigen Backup- und Restore-Lauf**. Die Docker-Volumes sind persistent, ersetzen aber keine unabhängige Sicherung. Vor Ablage wichtiger Fahrzeugdaten Backup-Ziel und Restore prüfen. Fachliche Einschränkungen zu Erinnerungen, Einheiten und Änderungshistorie bleiben bestehen; siehe [Roadmap](../roadmap.md).

## Bedienung und Fehlerdiagnose

Adresse: https://garage.example.invalid. Die Anmeldung erfolgt per Cloudflare-Einmal-PIN; anschließend hat der zugelassene Nutzer volle LubeLogger-Adminrechte.

Auf dem Proxmox-Host über den vorhandenen administrativen Zugang: `pct status <CTID>`. Im Gast zeigt `cd /srv/garage-example && docker compose ps` den Zustand; `docker compose logs --tail 100` unterstützt die Diagnose. Logausgaben können sensible Anwendungsdaten enthalten und gehören nicht ungeprüft ins Repository. Bei Ausfall zuerst Container-, DNS-, Access- und Tunnelstatus getrennt prüfen. Eine Änderung, ein Neustart oder eine Löschung bestehender anderer Dienste ist nicht Teil dieser Einrichtung.

Die lokale Parameterdatei und das geschützte Token sind für eine Wiederherstellung erforderlich. Die tatsächlichen Origin-/Egress-Netze wurden gegen die zum Einrichtungszeitpunkt sichtbaren Gast- und Hostrouten geprüft; unbekannte Reservierungen waren dadurch nicht ausgeschlossen. `GARAGE_ORIGIN_SUBNET=192.0.2.0/28` und `GARAGE_EGRESS_SUBNET=198.51.100.0/28` sind hier ausschließlich Dokumentationsbeispiele aus reservierten Beispielnetzen und keine geprüften Betriebswerte.
