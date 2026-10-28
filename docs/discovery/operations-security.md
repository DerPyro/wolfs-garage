# Phase 0: Betrieb, Sicherheitsgrenzen und Wiederherstellung

Stand: 2026-10-26. **Architekturvorschlag, nicht eingerichtet oder praktisch getestet.** Grundlage: README, AGENTS und sämtliche vorhandenen Anforderungs-, Architektur- und Roadmap-Dokumente. Keine Zugangsdaten, produktiven Systeme oder Cloudflare-Ressourcen wurden angelegt oder verändert.

> **Produktklarstellung 2026-10-27:** Das ursprüngliche Dokument nimmt native Web-Anmeldung und unterschiedliche Objektrollen an. Der Nutzer möchte ein einziges Cloudflare-Login und Adminrechte für alle zugelassenen Webnutzer. [ADR-0008](../adr/0008-single-user-access.md) ersetzt diese Annahmen; Origin-/Dienstzugang und Recoverynachweis bleiben offen. Der Rest dokumentiert die ältere Discovery.

## Bestandsaufnahme, Annahmen und Vorgehen

Das Repository enthält bisher ausschließlich Planung. Proxmox-Version, Gastressourcen, bestehende Docker-/Backup-Struktur, DNS-Domain, IdP, Paperless-Version und tatsächliche Netzwerkregeln sind unbekannt. Angenommen werden ein Betreiber, mindestens fünf Fahrzeuge und ein vorhandenes Paperless-ngx. Zunächst Isolation und Auth-Grenzen festlegen, danach Secret-/Datenbesitz und Restore definieren; die spätere Sandbox prüft die Annahmen vor Freigabe. Die Compose-Datei dokumentiert nur diese Grenzen.

## Gast und Vertrauenszonen

REQ-039 verlangt Docker auf Proxmox. Die bisherige Architektur bevorzugt einen isolierten LXC; das ist noch keine validierte Betriebsentscheidung. Vorschlag zur ADR-Prüfung: dedizierte QEMU-VM als stärkere Isolationsgrenze bevorzugen, falls Ressourcen reichen. Unprivilegierter LXC mit bewusst geprüftem Nesting bleibt eine Alternative; keine privilegierten Container oder Host-Docker-Socket-Mounts. Die aktuelle Proxmox-Dokumentation beschreibt geteilten Hostkernel bei LXC und empfiehlt QEMU-VM-Nesting für maximale Isolation und Live-Migration. Ihre aktuellen OCI-Application-Container gelten als Technology Preview; sie ersetzen hier keine geprüfte Docker-Umgebung. [Proxmox-Quelldokumentation](https://raw.githubusercontent.com/proxmox/pve-docs/master/pct.adoc)

Geplante Grenzen:

| Zone | Erlaubter Verkehr / Daten | Verbot / offene Prüfung |
|---|---|---|
| Browser → Cloudflare Access | Identitätsprüfung vor Webzugriff | Keine öffentliche API-Ausnahme für Telegram |
| cloudflared → Origin | Nur authentifizierte Webdienste | Kein Hostnetz, keine Router-Portfreigabe |
| Garage → LubeLogger | Dokumentierte API, eigenes minimales Integrationskonto | Kein Direktzugriff auf LL-Dateien oder LL-DB |
| Garage → eigene Persistenz | Logbuch, Audit, Outbox, Referenzen | Kein öffentlicher Datenbankport |
| Garage → Paperless | Authentifizierte interne API, geringste Rechte | Keine freie URL aus Benutzer-/KI-Text aufrufen |
| Garage → Telegram/Kalender | Explizit freigegebene Ziele, begrenzte Timeouts | Keine unbeschränkten SSRF-Requests |

Die geplanten Compose-Netzwerke sind Kommunikationsgruppen. Zielbasierte Egress-Regeln benötigen zusätzlich Gast-Firewall oder Proxy und eine geprüfte DNS-Strategie; `internal: true` allein löst ausgehenden Telegram-/Kalenderzugriff nicht.

## Web-Authentifizierung und Servicekonten

Cloudflare Tunnel baut ausgehend Verbindungen auf; die vorgeschlagene Veröffentlichung braucht keine Router-Portfreigabe. Access schützt den äußeren Weg, ersetzt aber nicht Anwendungsrechte. Der Origin muss über den Connector erreichbar sein, ohne daneben einen ungeschützten LAN-/Hostport zu öffnen. [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/)

Access-JWTs am Connector oder vorgeschalteten Origin-Gateway anhand Signatur, Aussteller, Ablauf und passender Audience validieren; bloß vorhandene Header sind kein Identitätsnachweis. Für eine künftige eigene Web-API zusätzlich serverseitige Fahrzeugberechtigung, Session-/CSRF-Schutz und Autorisierung pro Objekt. Ein späterer Wartungszugang über Managementnetz benötigt ebenfalls native Anmeldung und Audit. Keine automatische Identitätsübernahme aus frei setzbaren Proxy-Headern. [Cloudflare JWT-Validierung](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/)

LubeLogger aktiviert Authentifizierung standardmäßig **nicht**. Erstzugang deshalb ausschließlich in isolierter Umgebung, Auth aktivieren und unberechtigte Web-/API-Zugriffe negativ testen, bevor überhaupt ein Tunnel vorgeschlagen wird. Root bleibt Wiederherstellung/Administration vorbehalten; Integrationskonto auf benötigte Fahrzeuge beschränken und wirksame API-Rechte testen. Die dokumentierten Nicht-Root-Rollen dürfen APIs verwenden, besitzen aber nicht pauschal alle Fahrzeuge. Keine erfundene Auth-Environment-Konfiguration in den Compose-Entwurf aufnehmen. [LubeLogger Authentication](https://docs.lubelogger.com/Installation/Authentication/)

## Telegram: Vorschlag für Version 1.1

Long Polling vermeidet einen zusätzlichen eingehenden Webhook und eine Access-Ausnahme. Die Bot-API bietet `getUpdates`; Empfang und Webhooks sind nicht gleichzeitig zu verwenden. Offset erst nach dauerhaftem Speichern/Verarbeiten der Updates fortschreiben. [Telegram Bot API](https://core.telegram.org/bots/api#getupdates)

Vor Parser, KI, Datenabfrage oder Callback-Ausführung die numerische `from.id` mit der konfigurierten Allowlist vergleichen; private Chatart und bekannte Chat-ID zusätzlich prüfen. Fehlende/ungültige Konfiguration verweigert Zugriff. Benutzernamen sind kein stabiler Berechtigungsnachweis. Bot-Ausgaben nur an den bekannten privaten Chat senden. Unbekannte Updatearten, Gruppenposts und manipulierte Callbacks ohne Datenzugriff ablehnen.

Schreibvorschlag serverseitig speichern: Fahrzeug, Aktion, vollständige Nutzlast, Actor, Ablauf und einmalige Nonce. Bestätigung erneut autorisieren, Version seit Vorschlag prüfen und atomar nur einmal ausführen. `update_id`, fachliche Operations-ID und Bestätigungsstatus persistieren; doppelter Empfang darf keine zweite Wartung erzeugen. Externe Schreib-Timeouts als ungeklärten Zustand behandeln, vor Wiederholung abgleichen. Audit erfasst Akteur, Kanal, Zeit, Objekt, vorher/nachher bzw. Änderung, Bestätigung und Ergebnis; keine Bot-Tokens oder vollständigen privaten Nachrichten loggen.

## Secrets und Daten

[`.env.example`](../../deploy/.env.example) enthält ausschließlich leere Konfigurationsplätze und nicht geheime Zeitzone. Die Variablen sind ein Garage-Vertragsentwurf, keine behaupteten Upstream-Variablen. Reale `.env`, Secret-Dateien, Dumps und persönliche Dokumente müssen vor späterer Verwendung durch `.gitignore` ausgeschlossen werden. Secret-Store bzw. Dateien außerhalb des Repositorys mit restriktiven Rechten; getrennte Credentials je Integration, Rotation und Wiederherstellung dokumentieren.

Compose-Secrets werden als Dateien in Container eingebunden und pro Dienst freigegeben; sie sind kein verschlüsselter Tresor für den Host. Ob das jeweilige Image Dateisecrets oder bestimmte `_FILE`-Variablen unterstützt, wird ausdrücklich separat geprüft. Keine automatische Gleichsetzung von Secret-Mount und Anwendungskonfiguration. [Docker Compose Secrets](https://docs.docker.com/compose/how-tos/use-secrets/)

LubeLogger-Daten und ASP.NET-Schlüssel persistent halten. Upstream verwendet `/App/data` und `/root/.aspnet/DataProtection-Keys`; diese Pfade vor Fixierung des gewählten Release erneut prüfen. Keine gemeinsam beschreibbaren LL-Volumes für Garage. [Upstream-Compose](https://raw.githubusercontent.com/hargata/lubelog/main/docker-compose.yml)

## Backup- und Restore-Entwurf (REQ-040)

Vorgeschlagene, noch zu bestätigende Betriebsziele: RPO höchstens 24 Stunden, RTO höchstens 4 Stunden, tägliche verschlüsselte Sicherung, 7 tägliche/4 wöchentliche/12 monatliche Stände, zusätzliche getrennte/offline Kopie. Speicherbedarf, Schlüsselverwahrung und Verantwortlicher bleiben offen. Proxmox-Snapshots allein sind kein nachgewiesenes anwendungskonsistentes Backup.

| Bestandteil | Sicherung | Restore-Abnahme |
|---|---|---|
| LubeLogger | Daten, Dokumente, Einstellungen und ASP.NET-Schlüssel; releasebezogener Manifest | Fahrzeuge, Kilometerstände, Kosten, Anhänge und native Anmeldung geprüft |
| Garage ab 1.1 | Eigene DB inklusive Referenzen, Audit, Bestätigungen, Inbox/Outbox und Kalender-Mappings | Keine verlorenen Referenzen, keine erneut ausgeführten alten Kommandos |
| Paperless (bestehend) | Eigenständige abgestimmte Sicherung inkl. Dokument-IDs und Originalen | Referenzierte IDs und Zugriffsrechte geprüft |
| Konfiguration | Git-SHA, Image-Digests, Netz-/Auth-Konfiguration, Backup-Katalog | Dieselbe getestete Version reproduzierbar |
| Secrets | Separater verschlüsselter Recovery-Store | Schlüssel verfügbar; nach Kompromittierung rotierbar |

LubeLogger dokumentiert eine Root-Backup-/Restore-Funktion und empfiehlt Backups vor Updates. Die genaue Abdeckung dieses Exports gegenüber Volume-Sicherung ist noch in der Sandbox zu prüfen. Kein Produktions-Root-Token nur für einen normalen Integrationsprozess verwenden. [LubeLogger Upgrade/Backup](https://docs.lubelogger.com/Installation/Upgrade/)

Geplante konsistente Sicherung: schreibende Prozesse und Scheduler pausieren, offene externe Operationen markieren, LubeLogger und Garage auf gemeinsamen Wiederherstellungspunkt bringen, Daten bei gestoppten Schreibern kopieren bzw. DB-natives Backup nutzen, Manifest und Checksummen erzeugen, verschlüsselt außerhalb des Gasts sichern, Schreibbetrieb wieder freigeben. Zunächst kurzzeitiger vollständiger Schreibstopp statt unbewiesener Cross-Service-Snapshot-Konsistenz.

Restore-Übung vor Echtbetrieb: isolierter Gast ohne Telegram-/Kalender-/KI-Egress, passende Versionen aus Manifest, Daten und Schlüssel einspielen, Integrität und Rechte prüfen. Inbox/Outbox zunächst gesperrt lassen. Kalender-/Telegram-Zustand extern abgleichen, überholte Bestätigungen verwerfen und Erinnerungen nicht blind nachsenden. Erst nach dokumentierter Abnahme produktive Verbindung freigeben. Monatliche Restore-Stichprobe und vollständige Übung nach Versionswechsel sind vorgeschlagen; bisher nicht ausgeführt. Bei LXC beachten: Proxmox sichert Host-Bindmount-Inhalte nicht automatisch über `vzdump`. [Proxmox Mountpoints](https://raw.githubusercontent.com/proxmox/pve-docs/master/pct.adoc)

## Compose-Entwurf und Abnahmepunkte

[`compose.design.yaml`](../../deploy/compose.design.yaml) ist eine YAML-Designvorlage mit leerem `services` und erklärenden `x-design`-Metadaten: keine startbaren Dienste, keine Builds, keine Secrets, keine produktiven Images. Sie dokumentiert Netzwerke, Zuständigkeiten und LL-Persistenz; keine Healthcheck-Endpunkte erfinden. Versionen/Digests, Datenbankengine, Nutzer-UID, konkrete Secret-Einbindung, Ressourcen, Readiness und Netzregeln bleiben Freigabekriterien der späteren Sandbox.

Vor Umsetzung offen: Gastwahl (VM oder unprivilegierter LXC), vorhandene Versionen/Ressourcen/Backups, Domain/IdP und Access-Audience, native Auth- und API-Rechte, Secret-Dateisupport je Image, Backup-Abdeckung, Offsite-Ziel, Recovery-Ziele und Schlüsselverantwortung. Geeignete Negativtests: unauthentifizierter Web-/API-Zugriff, direkter Originzugang, fremde Telegram-ID, Gruppenchat, fremde Fahrzeug-ID, abgelaufene/wiederholte Bestätigung, simulierte Ausfälle und Restore ohne externe Seiteneffekte. Alle bleiben offen, bis eine getrennt beauftragte Testumgebung besteht.

Quellen: ausschließlich oben verlinkte Primärquellen, abgerufen am 2026-10-26; veränderliche `main`-/`master`-Links beschreiben den Recherchestand und sind noch keine releasegebundene Betriebsfreigabe.
