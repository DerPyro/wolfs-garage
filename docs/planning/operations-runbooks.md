# Betriebsplanung und Runbooks

Stand: 2026-10-26. **Alle folgenden Verfahren und Parameter sind vorgeschlagen; keines wurde durch diese Planung ausgeführt.** Der Auftrag umfasst keine neuen Dienste, Produktionskonfiguration, Hoständerung oder Migration. Vorbedingungen: [Architektur](../architecture.md), [ADRs](../adr/README.md), [Backlog](../backlog.md) und [Threatmodell](security-threat-model.md).

> **Produktklarstellung 2026-10-27:** Ein interaktives Cloudflare-Login, danach globale Adminrechte. [ADR-0008](../adr/0008-single-user-access.md) ersetzt frühere Anforderungen an separate native Webanmeldungen/Read-only-Rollen. Die technische Abschottung des Origins und interne Servicezugänge bleiben zu prüfen.

## Bestandsaufnahme und Arbeitsplan

Vorhanden: Dokumentationsarchitektur, nicht startbares Compose-Design sowie isolierter LubeLogger-Teststand v1.7.4 mit 62 Checks (51 bestätigte Verträge, 11 reproduzierte Grenzen). Testinstanzen wurden gestoppt. Der [Laufzeitbericht](../discovery/lubelogger-runtime-verification.md) belegt weder Proxmox-Betrieb noch Offsite-Wiederherstellung oder UI-/Audit-Abnahme. Gepinnter Teststand: [`target.lock.json`](../../tests/lubelogger/target.lock.json).

Vorgehen für spätere Aufträge: Parameter inventarisieren → Blocker entscheiden → isoliert nachweisen → konkrete Konfiguration reviewen → gegebenenfalls erforderliche Freigabe einholen → bereitstellen → Abnahme und Rückfallpunkt dokumentieren. Keine fehlende Betreiberangabe erfinden. VM ist vorgeschlagen; VM/LXC bleibt ADR-0003 offen.

## Entscheidungs- und Freigabegates

Technisches Gate bedeutet ein prüfbares Abnahmekriterium, keine zusätzliche pauschale Erlaubnisfrage. Explizite Zustimmung ist gemäß AGENTS.md Regel 6 für **produktive Deployments, Cloudflare-Änderungen, Löschungen und Migrationen** erforderlich. Normale Dokumentation und reversible lokale Prüfungen brauchen daraus keine neue Freigabe; der aktuelle Auftrag beschränkt sich unabhängig davon auf Planung.

| Gate | Vorbedingung / Evidenz | Ergebnis bei Nichterfüllung |
| --- | --- | --- |
| G0 Parameter | Gast, Netz, Identität, Speicher, Secretverwahrung, Wiederherstellungsziele erfasst | Nur davon unabhängige Planung fortsetzen |
| G1 Produktumfang | B03 Audit, B04/B17 Regel-/Datums-Hoheit, B07 UI und B16 Dokumentrechte entschieden | Kein produktiver v1.0-Umfang als erfüllt behaupten |
| G2 Sandbox | Getestetes Image/Architektur/Digest, negative Rechte- und CSRF-Tests, UI-Abnahme, sichere Dokumentlösung | Findings mit Test-ID beheben oder Produktumfang ausdrücklich neu entscheiden |
| G3 Betrieb | Verschlüsselte Sicherung plus separater Key-Recovery, vollständiger Restore, Origin-Bypass, Messung von RPO/RTO | Kein produktiver Betrieb |
| G4 konkreter Änderungsplan | Zielressourcen, Versionen, Maßnahmen, Abnahme, Rückfallpunkt und bekannte Risiken reviewbar | Änderung konkretisieren; vor Produktivdeployment/Cloudflare-Änderung/Migration/Löschung explizite Freigabe |
| G5 Aktivierung | Gewählter Access-/Originweg geprüft, Monitoring und Recovery-Verantwortung vorhanden | Veröffentlichung nicht aktivieren |
| G6 nach Änderung | Funktion, Rechte, Audit, Fristen, Backup und externe Zustände geprüft | Rückfallverfahren wählen; keine blinden externen Wiederholungen |

ADRs bleiben bis zur dokumentierten Entscheidung **Vorgeschlagen**. Eine Scope-Änderung von REQ-043 ist eine fachliche Entscheidung und darf keinen fehlenden Auditnachweis verdecken.

## Parametermatrix ohne Geheimnisse

Keine echten Hostnamen, IDs oder Tokenwerte eintragen. Umsetzungswerte später im privaten Betriebsinventar halten. `.env.example` beschreibt nur den künftigen Vertrag; keine automatische Upstream-Unterstützung ableiten.

| Parametergruppe | Zu erfassen | Vorschlag / Zustand | Validierung |
| --- | --- | --- | --- |
| Host | Proxmox-Version, amd64/arm64, Gasttyp, OS, Docker/Compose, verfügbare Ressourcen | VM bevorzugt; unprivilegierter LXC offen | Zielarchitektur und Nesting/UIDs/Backups auf eigenem Gast prüfen |
| Kapazität | vCPU, RAM, persistenter Speicher, freier Platz, I/O, Anhänge/Jahr | Siehe Startannahmen unten, ungemessen | Leerlauf, Lastspitze, Backup-/Restorebedarf messen |
| LL-Version | Release, Source-SHA, Registry-Digest, Plattform, API-Kataloghash | Testbaseline v1.7.4, kein automatischer Produktivpin | Gegen gewählten Betriebskandidaten erneut vergleichen |
| Netz | Gastadresse, Managementnetz, DNS/NTP, Originziele, erlaubter Egress | Keine Routerfreigabe/DB-Publikation | Positiv-/Negativmatrix aus Management-, LAN- und Originzone |
| Webidentität | Domain, IdP, berechtigter Nutzer, Access-Audience, Session/Recovery | Offen; native LL-Auth verpflichtend | Fremder Nutzer, falsche Audience, Direktzugriff, abgelaufene Session |
| Dienste | LL-interner Dienstzugang, Paperless-Instanz/Version, eigenes DB-Schema | Adminmodell für Web; interner Zugriff muss zum gewählten Authmodus passen | Access-Grenze und Verhalten interner Dienste prüfen |
| Telegram ab 1.1 | numerische User-ID, privater Chat, Polling, Bestätigungsdauer | Long Polling; Werte offen | Fehlende Config verweigert; Fremd-/Replaytest |
| Kalender ab 1.1 | eigene Kalender-ID, Credentialtyp/Scope, Eventidentität | 30-Tage-Alternative offen | Kein Schreiben in fremde Kalender; Konflikt-/Ausfalltest |
| Zeit | fachliche Zone, UTC-Audit, NTP, Zeitabweichungsalarm | Europe/Berlin / UTC | DST/Monatsende; DueDays nicht als LocalDate verwenden |
| Secretverwaltung | Ablagepfade, Rechte, Owner, Rotation, Recovery-Verfahren | Dateien/Tresor außerhalb Git | Prozesszugriff, Logredaktion, Keyverlustübung |
| Backup | Ziel, Verschlüsselung, separater Schlüsselort, Retention, Owner, Messprotokoll | RPO/RTO/Retention vorgeschlagen, unbestätigt | Restore vom tatsächlich externen Ziel statt lokaler Kopie |
| Betrieb | Betreiber/Vertretung, Wartungsfenster, Alarmkanal, Datenaufbewahrung | Offen | Probealarm und Erreichbarkeit |

### Kleine Startannahmen, ausdrücklich ungemessen

Für eine Person und fünf Fahrzeuge als **Messstartpunkt**, ohne KI-Modell: dedizierter Gast mit 2 vCPU, 4 GiB RAM und 32 GiB Systemdisk; zusätzlich zunächst 20 GiB persistenter Nutzdatenplatz. Anhänge/Backups werden separat kalkuliert. Das sind weder Mindestanforderungen des Herstellers noch eine zugesagte Kapazität. v1.1 mit Garage/PostgreSQL benötigt eine erneute Messung; lokales KI-Modell ist nicht enthalten.

In isolierter Umgebung 24 Stunden Leerlauf plus synthetische Spitzen (gleichzeitige Webnutzung, API, Backup/Restore) messen: RSS/Peak-RAM, CPU, I/O, Antwortzeiten, Daten-/Anhangswachstum und freier Platz. Mindestens Platz für Nutzdaten, konsistente Sicherungsstagingkopie, Restore-Zweitinstanz und Sicherheitsreserve kalkulieren. Gast-Übercommit und Proxmox-Storageausfall getrennt bewerten. Vorschlag für erste Beobachtungsgrenzen: Speicherbelegung 75 % Warnung/90 % kritisch, letzter erfolgreicher Backup älter als 26 Stunden kritisch; nach Messung begründen und anpassen. Nicht als bereits eingerichtete Alarme verstehen.

## Runbook A: isolierte Vorbereitung und spätere Bereitstellung

1. **Eingang:** G0/G1 geklärt, Auftrag für den jeweils konkreten nächsten Schritt; keine Wiederverwendung der alten Testvolumes als Echtdatenbasis. Zuständigkeit und zulässige Ziele im privaten Änderungsprotokoll festhalten.
2. Gasttyp nach ADR wählen. Bei LXC Nesting, UID-Mapping und Backup der Mountpunkte nachweisen; keine privilegierte Ausweichlösung. Managementzugang und OS-Patching planen; Docker nicht direkt auf Proxmox-Host installieren.
3. Neue isolierte Umgebung mit getrennten Daten- und DataProtection-Key-Volumes vorsehen. Keine öffentlichen Ports, kein Produktions-Paperless/Telegram/Kalender, keine produktiven Credentials. Images anhand Plattform und Digest prüfen; Bestandteile/Lizenzen inventarisieren, falls eigene Distribution vorgesehen.
4. Secret-Mapping je Image aus verifizierter Dokumentation prüfen. `_FILE`-Konvention nicht pauschal annehmen. Keine Secrets in CLI-Historie, Git, Diagnoseausgaben oder Compose-rendered Logs.
5. Gewählte Ein-Login-Variante isoliert testen: Cloudflare Access mit geschützt isoliertem Origin oder nachgewiesenes transparentes SSO. Bei ausgeschalteter nativer Auth ist jeder interne Originaufruf Admin; keine API-Key-Rollenwirkung behaupten. Anonyme Sperre am tatsächlichen Access-Eingang und erlaubte interne Dienstzugänge nachweisen. Registrierung/Einladung nur nach festgelegter Policy.
6. B16-Access-/Originabdeckung und B03-Änderungsprotokoll anhand des Ein-Admin-Modells prüfen. Bis zur konkreten Bereitstellung ausschließlich synthetische Anhänge. Trennung zwischen zugelassenen Admins ist kein Ziel.
7. GET-Autorefresh aus lassen; Zeit-/Schwellenregel-Owner dokumentieren. Kalender, E-Mail und sonstige Nebenwirkungen bis zur jeweiligen Integrationsabnahme deaktiviert halten.
8. Messungen, Restore und UI-Abnahme durchführen. Reale Compose-Konfiguration erst im späteren Umsetzungsauftrag erstellen; die vorhandene Datei bleibt Designmetadaten.
9. **Vor produktivem Deployment bzw. Cloudflare-Änderung:** konkrete Ressourcen und Rückfallplan vorlegen, explizite Freigabe gemäß AGENTS abwarten. Der Auftrag zur Planung autorisiert keine Aktivierung.
10. **Ausgang:** nach autorisierter späterer Änderung erlaubter Browserzugang funktioniert; anonyme/fremde Nutzer und direkte LAN-/Originpfade sind gesperrt, keine DB-Publikation. Schreibtest mit synthetischem Datensatz, Audit, Datum und Backup erfolgreich. Erst dann private Echtdatenübernahme planen; Migration erfordert eigene explizite Freigabe.

## Runbook B: konsistente tägliche Sicherung

Vorgeschlagene Ziele: RPO ≤24 Stunden, RTO ≤4 Stunden, 7 tägliche/4 wöchentliche/12 monatliche Stände, separate/offline Kopie. Noch zu entscheiden und vom echten Sicherungsziel wiederherzustellen; kein vorhandener Nachweis dieser Werte.

1. **Eingang:** Backupziel erreichbar, genügend Platz, Verschlüsselung und separat recoverbarer Schlüssel verfügbar; letzte Sicherung nicht überschreiben. Lauf-ID, Version/Digest und Startzeit erfassen, keine Geheimnisse.
2. Ab v1.1 schreibende Worker, Scheduler und Bestätigungsannahme kontrolliert pausieren; laufende externe Writes abschließen oder als `uncertain` markieren. Native UI-Schreibwege ebenfalls sperren/pausieren. Ein pausierter Garage-Worker allein schafft keine Konsistenz.
3. Gemeinsamen Wiederherstellungspunkt herstellen: LL-Datenbank/-Dateien bei angehaltenen Schreibern sichern, Garage-DB transaktional sichern, Referenzinventar und Zeitpunkt erfassen. Nicht unkoordiniert laufende DB-Dateien kopieren. Native LL-Exportfunktion kann zusätzlichen Portabilitätspunkt liefern, ersetzt aber nicht vollständige Datenträger-/Schlüsselsicherung.
4. Einschließen: `/App/data`, Anhänge/Konfiguration, `/root/.aspnet/DataProtection-Keys`, Garage-DB inklusive Audit, Inbox/Outbox, Kalender-Mappings und Providerinstanz-IDs; Manifest mit Versionen und Hashes. Paperless separat abgestimmt sichern, stabile Dokument-IDs prüfen. Zugangsdaten und Recovery-Keys getrennt verschlüsselt verwahren.
5. Checksummen und Lesbarkeit prüfen, verschlüsselt außerhalb des Gasts übertragen und bestätigten Eingang protokollieren. Same-host-Kopie schützt nicht vor Hostverlust. LXC-Host-Bindmounts brauchen gesonderte Sicherung; `vzdump` erfasst deren Inhalt nicht automatisch.
6. Schreibbetrieb nach erfolgreichem lokalen Konsistenzpunkt wieder freigeben; externer Transfer darf keinen unbegrenzten Wartungsstopp auslösen. Ausfall sichtbar alarmieren, letzte gute Sicherung erhalten. Löschung alter Stände nur durch später ausdrücklich freigegebene Retention-Aktion/Policy gemäß AGENTS; nicht aus diesem Plan ableiten.
7. **Ausgang:** Recoverypunkt, Umfang, Prüfergebnis, Offsite-Ankunft und Alter letzter erfolgreicher Sicherung sichtbar. Monatliche Restore-Stichprobe und nach Upgrade vollständige Übung vorgeschlagen.

## Runbook C: isolierter Restore und Wiederanlauf

1. **Eingang:** Wiederherstellungsgrund, akzeptierter Recoverypunkt, betroffene Systeme und extern bereits ausgeführte Effekte festhalten. Für produktive Datenersetzung/Migration/Löschung und Wiederbereitstellung explizite Freigabe einholen; isolierte Planung/Prüfung allein erteilt sie nicht.
2. Separate isolierte Zielumgebung ohne Telegram-/Kalender-/KI-/Mail-Egress und ohne öffentliches Routing bereitstellen, wenn beauftragt. Scheduler und Outbox bereits vor erstem Start deaktivieren. Altes System zunächst unverändert erhalten.
3. Manifest, Hashes, Entschlüsselbarkeit, Imagearchitektur/-Digest und Schema-/Anwendungsversion prüfen. Nicht automatisch mit neuerem Image öffnen. Bei fehlendem Key-Store oder Authkonfiguration abbrechen statt offen starten.
4. LL-Daten, DataProtection-Keys und Konfiguration zusammen wiederherstellen; eigene DB samt Provider-Mappings/Journal passend einspielen. API-Keys können durch Export erhalten bleiben und müssen deshalb wie aktive Credentials behandelt werden. Auth vor Originzugang prüfen.
5. Datenabnahme: fünf bzw. erwartete Fahrzeug-IDs, Kilometerdaten, Beträge, Regeln, Anhänge mit Bytehash, DocumentReference-IDs, Auditfolgen und Backupzeitpunkt vergleichen. Fehlende Paperless-Referenzen sichtbar machen, Originale nicht automatisch erneut importieren.
6. Security-Abnahme: nicht angemeldete/nicht über Access zugelassene Nutzer, bekannte native Dokumentpfade, Originumgehung und Sessionverhalten erneut prüfen. Interne Viewer-/Fahrzeugrollentrennung ist kein Ein-Admin-Produktziel. Erfolgreiche Datenwiederherstellung allein beweist B16 nicht.
7. **Vor Egress:** alte Bestätigungen verwerfen, Telegram-Offset/Inbox und unklare Requests abgleichen; externe Kalender-IDs/ETags lesen, Terminprojektionen vergleichen. Outbox nicht blind abspielen. Schlüsselverlust/Incident verlangt Credential-/Sessionrotation; Erhalt alter DataProtection-Keys kann alte Cookies weiterhin entschlüsselbar machen.
8. Fachlichen Verlust und externen Vorsprung transparent dokumentieren; kontrolliert nur eindeutig ausstehende Operationen wieder freigeben. Telegram-Zustellungen ohne eindeutigen Nachweis bleiben unklar; keine Exactly-once-Zusage.
9. **Ausgang:** gemessene RPO/RTO, negative Rechte-/Dokumenttests, externe Abgleichliste und Verantwortlicher dokumentiert. Produktive Umschaltung nur entsprechend freigegebenem Plan. Alte Instanz/Volumes nicht automatisch löschen.

## Runbook D: Upgrade und Rückfall

1. **Eingang:** konkrete Zielversion/Plattform/Digest, Release-Notes, API-Katalog-/Schemaänderung, Lizenzinventar und bekannte Findings gegenüber Testbaseline prüfen. Keine unbeaufsichtigten `latest`-Updates.
2. Frischen konsistenten Wiederherstellungspunkt anlegen und isoliert mit alter Version restoreprüfen. Produktivupgrade ist ein Deployment; mögliche Datenmigrationen zusätzlich im explizit freizugebenden Änderungsplan aufführen.
3. Restore-Kopie mit Zielversion prüfen: unveränderte IDs/Beträge/Regeln, native Dokumentrechte und Uploadwege, Auth-/CSRF, direkte Writes/Audit, Autorefresh/Schwellen, API-2xx-Fehlerobjekte, eigene Adaptertests und UI. Native Routeninventar/Positivallowlist bei Versionswechsel erneut prüfen.
4. Ressourcen und Restorezeit vergleichen. Geplante Ausfallzeit und Abbruchkriterien festhalten: Auth-Bypass, fehlende Daten, Dokumentleck, unkontrollierte Friständerung oder Auditverlust → keine Aktivierung.
5. Nach entsprechender Freigabe im Wartungsfenster Schreibbetrieb pausieren, Backup abschließen, genau den getesteten Stand bereitstellen, Abnahmen wiederholen. Ausgehende Worker zuletzt aktivieren.
6. Rückfall bei ungeklärtem Fehler: neue Writes stoppen, Zustand sichern, externen Effektenstatus erfassen. Alte Anwendung nicht auf möglicherweise migrierter DB starten. Vorherige Version **mit ihrem passenden Recoverypunkt** isoliert wiederherstellen; seitdem entstandene Writes manuell nachvollziehen. Produktionsersetzung/-migration nur gemäß freigegebenem Rückfallplan.
7. **Ausgang:** Version/Digest, Zeitpunkt, Tests, Restfindings und Backup-/Monitoringstatus aktualisiert. Staging-/Altbestände nur nach späterer autorisierter Löschung entfernen.

## Runbook E: Störung und Sicherheitsvorfall

| Ereignis | Unmittelbar vorgeschlagene Maßnahme | Diagnose / Wiederanlauf |
| --- | --- | --- |
| Provider API down / 429 | Bounded Retry nur für geeignete sichere Reads; unklare Writes pausieren | Retry-After/Fehlerbudget beachten, Rückstau sichtbar; Basisverwaltung unabhängig halten |
| POST-Timeout | Operation `uncertain`, kein automatischer zweiter POST | Nach Nutzlast/Providerzustand abgleichen; unentscheidbare Fälle manuell klären |
| Dokumentleck / Origin-Bypass | Sensiblen Zugriff nach autorisiertem Incidentplan unterbinden, Beweise minimiert sichern | Native/Proxy/Restorepfade untersuchen; Auth-Lösung nicht durch versteckte Links ersetzen |
| Token-/Sessionverlust | Betroffene Integration isolieren, Credentials/Session-Schlüssel nach Plan rotieren | Audit, Logs und externe Aktionen prüfen; neue Secrets außerhalb Git, alte Zugänge negativ testen |
| Daten-/Fristabweichung | Betroffene Scheduler/Writes pausieren, letzten sicheren Lesestand anzeigen | B17/Zeitzone/Autorefresh/Regelhoheit prüfen; keine automatische erneute Fristfortschreibung |
| Speicher voll / Backupfehler | Schreiblast begrenzen, Alarm; keine ungeplante Datenlöschung | Wachstum/Logs/Staging prüfen; alte Sicherung behalten; Kapazität gemäß Auftrag erweitern |
| Hostverlust | Recoverypunkt auswählen, isoliertes Runbook C | Keine freie Originveröffentlichung als schnelle Umgehung; externen Zustandsvorsprung abgleichen |

Bei produktiven Maßnahmen gilt weiterhin AGENTS Regel 6: Änderungen an Cloudflare, produktive Bereitstellungen, Migrationen und Löschungen brauchen explizite Freigabe oder einen bereits ausdrücklich freigegebenen konkreten Incidentplan. Diagnose und dokumentierbare reversible Schritte im vorhandenen Auftrag weiterführen; keine pauschale neue Approvalpflicht erfinden.

Incidentprotokoll: UTC-Zeitlinie, betroffene Objekte/Versionen, Erkennungsweg, Auswirkung, Beweisreferenzen ohne Geheimnisse, autorisierte Maßnahmen, Datenverlust-/Doppelwirkungsrisiko und Wiederanlaufentscheidung. Nutzerkommunikation über einen erreichbaren separaten Kanal einplanen; ein gestörter Telegram-Bot ist kein verlässlicher alleiniger Alarmweg. Abschluss erst nach negativem Regressionstest, neuem Backup und dokumentierter Ursache.

## Nachweisgrenzen und Quellen

Dieses Dokument plant Prozesse; Tests wurden hier weder ausgeführt noch neu behauptet. Maßgeblich bleiben [Laufzeitbericht](../discovery/lubelogger-runtime-verification.md), [Betriebsdiscovery mit offiziellen Quellen](../discovery/operations-security.md), [Abnahmeplan](../discovery/validation.md) und [Threatmodell](security-threat-model.md). Kein Proxmox-/Cloudflare-Account wurde inspiziert. Der frühere isolierte Anwendungsexport beweist nur den beschriebenen Umfang und enthält **keine DataProtection-Keys**.
