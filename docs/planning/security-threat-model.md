# Sicherheits-Threatmodell und prüfbare Abwehrmaßnahmen

Stand: 2026-10-26. **Vorgeschlagene Schutzplanung, keine eingerichteten Kontrollen und keine neuen Laufzeittests.** Grundlage: [Requirements](../requirements.md), [Architektur](../architecture.md), [vorgeschlagene ADRs](../adr/README.md), [B01/B02-Laufzeitbericht](../discovery/lubelogger-runtime-verification.md), [Quellverifikation](../discovery/lubelogger-source-verification.md) und [Runbooks](operations-runbooks.md).

> **Produktklarstellung 2026-10-27:** [ADR-0008](../adr/0008-single-user-access.md) sieht einen Cloudflare-Login und globale Adminrechte für alle zugelassenen Webnutzer vor. Das frühere Schutzmodell unterschiedlicher angemeldeter Fahrzeug-/Dokumentrollen ist kein Produktziel und entsprechende T01/T02-Read-only-Gates unten sind historisch. Nicht zugelassene Identitäten, Origin-Bypass, Telegram-Zugang, Datenintegrität und Backup bleiben relevante Grenzen.

## Bestandsaufnahme, Annahmen und Prüfplan

Der Betrieb richtet sich an eine Person, erlaubt aber technisch mehrere Identitäten: Root, Betreiber, API-Identität, Telegram-Actor und mögliche fehlberechtigte eingeloggte Nutzer. Ein Einpersonenprodukt darf Objektberechtigung nicht durch die Annahme „niemand anders meldet sich an“ ersetzen. Externe Dokumente, Providerantworten und KI-Texte sind untrusted. Domäne/IdP/Netz, Paperless-Version, konkrete Reverse-Proxy-Konfiguration und produktive Credentials fehlen. Geplante Reihenfolge: Angriffswege inventarisieren → bereits reproduzierte Findings priorisieren → Schutzoption entscheiden → getrennte Positiv-/Negativtests → erst später konkret implementieren.

Schutzgüter: Fahrzeug-/Identitätsdaten, Kennzeichen und persönliche Dokumente, unverfälschte Kilometer-/Wartungs-/Fristdaten, Herstellerbelege, API-/Session-/Recovery-Schlüssel, unveränderlicher Änderungsnachweis, Wiederherstellbarkeit und kontrollierte externe Aktionen. Fahrzeugdaten werden weder an KI noch an beliebige Rechercheziele pauschal freigegeben.

## Vertrauensgrenzen und Angreifer

| Grenze | Angreifer / Fehlerquelle | Schutzanforderung |
| --- | --- | --- |
| Internet → Access → Origin | anonymer Besucher, falsche Access-Identität, Origin-Bypass | Native Auth, geprüfte Identität und keine alternative offene Originroute |
| angemeldeter Nutzer → Fahrzeug/Dokument | Outsider ohne Fahrzeugrecht, entzogenes Recht, gestohlene Session | Autorisierung bei jedem Objektabruf, auch Dateien/Temp/Preview |
| Browser → native LL-Schreibwege | CSRF, manipulierte Form, direkter Write außerhalb Garage | Keine Zustandsänderung durch fremden Ursprung; vollständiger Auditpfad |
| Garage → Provider | fehlerhafter Adapter, überprivilegierter Key, unklare POST-Antwort | Minimalrechte, Inhaltsprüfung, keine blinden Doppelwrites |
| Telegram → Parser/Bestätigung | fremde ID, Gruppenchat, gefälschter/replayter Callback | Allowlist vor Daten-/KI-Zugriff, private Chatbindung, einmalige Bestätigung |
| Dokument/Web/KI → Tools | Prompt Injection, SSRF, bösartige Datei/URL | Keine abgeleitete Autorität; feste Adapteroperationen und erlaubte Ziele |
| Gast → Proxmox/Backup | Containerescape, Hostverlust, Backupdiebstahl | Isolierter Gast, kein Socket/privilegierter Container, verschlüsselter Recoverystore |
| Restore → Außenwelt | altes Journal, gültiger alter Token, fehlender Key | Egress aus, Auth vor Zugriff, Zustandsabgleich vor Wiederanlauf |

## Priorisierte Risiken und Abnahme

P0 bedeutet Blocker des betroffenen Echtbetriebs-/Funktionsumfangs; P1 vor zugehöriger Integration umsetzen, P2 vor KI-Freischaltung. Es ist keine numerische CVSS-Einstufung und kein behaupteter Exploit außerhalb der lokalen Testbaseline.

| ID / Prio | Bedrohung und Evidenz | Vorgeschlagene Mitigation | Prüffähiger Nachweis / Zuordnung |
| --- | --- | --- | --- |
| T01 / P0 | **Reproduziert:** angemeldeter Outsider ohne Fahrzeugrechte liest bekannten nativen Dokumentpfad; anonym gesperrt | Paperless als einzige sensible Ablage plus belegte Sperre nativer LL-Datei-/Uploadwege, oder belegte Upstream-Objektautorisierung | Berechtigter Leser erfolgreich; Outsider/Entzug/anonym scheitern an allen relevanten Pfaden, auch nach Restore; B09/B16 |
| T02 / P0 | **Belegte Grenze:** Garage-Audit erfasst native UI/API-Writes nicht lückenlos; Webhook ohne stabile Event-ID und Vorher/Nachher | Vollständigen Auditpfad über sämtliche tatsächlich erlaubte Writes beweisen, ggf. Schreibwege begrenzen; explizite Produktentscheidung bei Scope-Änderung | Native Anlegen/Ändern/Löschen, Korrektur, Import, Wartungsfortschreibung und Rechteänderung zu Actor/Objekt/Zeit/Änderung korrelierbar; B03 |
| T03 / P0 | Offener LAN-/Hostport oder zusätzliche Tunnelroute umgeht Access | Kein veröffentlichter Origin-/DB-Port; Managementzugang separat und nativ authentifiziert; Access-JWT am Prüfpunkt validieren | Direkter Zugriff aus LAN/anderen Containern, Hostheader/Token-Manipulation und falsche Audience scheitern; B05/B06 |
| T04 / P0 | LL-Auth default aus; Credentialmix kann Tests mit Root-Cookie scheinbar bestehen lassen | Isolierter Erststart, native Auth vor Routing; Root nur Recovery; separate cookie-freie API-Clients | Auth aus darf nicht publiziert werden; ohne/ungültigen Key gesperrt; Viewer/Editor/Objektrechte getrennt; B02/B06 |
| T05 / P0 | Cookie-authentifizierte native Writes oder GET mit Seiteneffekt durch CSRF/Linkaufruf; Schutz nicht vollständig untersucht | Native CSRF-Abnahme; eigene Cookie-API mit Antiforgery und Originprüfung; seiteneffektbehaftete GETs nicht als sichere Reads erlauben | Cross-origin Form, simple POST, Fetch, GET-Navigation, alte/fehlende Tokens dürfen keine Änderung auslösen; B03/B06/B17 |
| T06 / P0 | **Reproduziert:** GET-Autorefresh verschiebt Fälligkeit; DueDays-/Threshold-Abweichung verfälscht Erinnerung | Auto-Refresh aus, LocalDate/Europe-Berlin und ein Regel-Owner; Providerdringlichkeit nicht ungeprüft übernehmen | Wiederholte Reads ohne Durchführung unveränderlich; D+30/D+7/D, DST/Monatsende und Reihenfolgefälle; B04/B17 |
| T07 / P1 | Fremde Telegram-ID oder Callback löst Fahrzeugabfrage/Write aus | Numerische from.id-Allowlist, private Chat-ID, Actor/Chat/Payload/Ablauf/Nonce und erneute Objektprüfung | Fremde/fehlende ID, Gruppe, anderer Chat, Replay, Ablauf und geänderte Revision: weder Daten noch Providerwrite; B11 |
| T08 / P1 | **Reproduziert:** identischer POST erzeugt Duplikate; Antwortverlust macht Ausgang unklar | Persistente Command-ID/Inbox, `uncertain`, Reconciliation vor Retry, unique Zustellschlüssel | Speichererfolg + Antwortverlust führt nicht zu zweitem POST; Adapter prüft `success=false` trotz HTTP 200; B10/B12 |
| T09 / P1 | SSRF/Tokenabfluss über freie URLs, Redirects, manipulierte Providerlinks | Feste Providerbase-URLs; Ziele, Redirects, DNS/IP und Protokolle validieren; Credentials nur für gebundenen Origin | Loopback/private/link-local/Metadatenziel, DNS-Rebinding, Cross-origin-Redirect und URL-Userinfo ablehnen; freigegebener interner Provider nur explizit |
| T10 / P1 | Große/aktive Datei erschöpft Speicher oder exfiltriert über Browserpreview | Sensible Dokumente Paperless, begrenzte Typen/Größen/Quoten, sichere Anzeige/Download, isolierte Verarbeitung | Übergröße/Typ-Mismatch/polyglotte und aktive Testdatei kontrolliert abweisen; keine unbeabsichtigte Vorschau im Origin |
| T11 / P0 | **Reproduziert:** Anwendungsexport ohne DataProtection-Keys; Hostverlust oder Schlüsselverlust gefährdet Recovery | Daten+Keys+Konfigmanifest getrennt verschlüsselt sichern; externen Restore nachweisen | Entschlüsseln ohne verlorenen Originalgast möglich; Auth/Rechte/Dokumente geprüft; fehlender Key kein anonymer Fallback; B06 |
| T12 / P1 | Backupdiebstahl/zu breite Logs verraten Keys, Dokumente oder Telegraminhalt | Separate Verschlüsselungskeys, restriktive Dateirechte, Logredaktion, keine Query-API-Keys, minimierte Evidenz | Repo-/Log-/Artefaktprüfung mit Testmarkern, restorebare Offsite-Kopie und nachgewiesener Zugriffsschutz |
| T13 / P1 | Restore spielt alte Commands/Benachrichtigungen erneut ab oder reaktiviert kompromittierte Session | Outbox/Scheduler/Egress vor Restore aus, Journale/Provider abgleichen, alte Bestätigungen verwerfen und Credentials nach Incident rotieren | Kein externer Request während Restore; absichtlich alter Command nicht erneut geschrieben; alter Key nach Rotation gesperrt |
| T14 / P1 | Imagewechsel / überprivilegierter Container kompromittiert Host oder verschlechtert Schutz | Gepinnter Digest/Plattform, kein Docker-Socket/Hostnetz/privilegierter Betrieb, Rechte/Schreibpfade messen | Image-/Configvergleich, isolierter Upgrade-Restore, B16/CSRF/Rollen erneut prüfen; VM/LXC gemäß ADR-0003 |
| T15 / P2 | KI-Dokument/Rechercheanweisung veranlasst Write, Herstellerfakt oder Datenausleitung | KI ohne Schreib-/Secretrechte, minimierte explizit freigegebene Daten, Quellen/Unsicherheit, deterministisches Bestätigungsmodell | Eingebettete „ignoriere Regeln“-Instruktion kann weder Tools umwidmen noch Fahrzeug-/Dokumentumfang erweitern; B14/B15 |
| T16 / P1 | Wartungs-/HU-Quelle oder OCR-Wert falsch bestätigt | Passende Hersteller-/amtliche Quelle, Einheit/Datum/Fahrzeug und Unsicherheit sichtbar; OCR als Entwurf | Verwechslung Modell/Einheit, unmöglicher Tacho, unbestätigte HU-Ausnahme und unsicherer OBD-Code blockieren Automatismus |

## T01: Dokument-Outsider-Lücke konkret eingrenzen

Die Runtime-Evidenz belegt **keinen anonymen öffentlichen Leak** und keine pauschale Umgehung aller Fahrzeug-APIs. Sie belegt den vertraulichkeitskritischen Unterschied: normales fremdes Fahrzeug/Record wird verweigert, derselbe angemeldete Outsider kann bekannte Dokumentbytes lesen. Access erlaubt eine äußere Identität; es weiß nicht automatisch, welchem Fahrzeug eine Datei gehört. Zufällige Dateinamen und versteckte UI-Links sind keine Mitigation.

Quellprüfung dieser Planung gegen bereits lokal vorliegenden offiziellen Release `63fa5cd267497ba01c29f4888c65efbbdd4b94bf`: [FilesController](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/FilesController.cs) hat klassenweites `[Authorize]`, aber `GetStaticFile` löst die Datei aus dem Requestpfad ohne Fahrzeugprüfung. Genau dieses Muster passt zum reproduzierten Befund. Der Bericht behauptet keine zusätzliche neue Ausnutzung.

### Verifizierte native Pfade und Aktionen als Inventar, kein Integrationsvertrag

| Quelle / Route | Methode / Funktion | Schutzplanung |
| --- | --- | --- |
| `FilesController.GetStaticFile`: `/documents/{fileName}`, `/temp/{fileName}`, `/images/{fileName}`, `/translations/{fileName}` | Attributrouten, Dateiausgabe | Dokument/Temp definitiv berücksichtigen; Bilder/Übersetzungen getrennt auf erlaubte Inhalte und notwendige UI-Funktion prüfen, nicht alle als sensible Fahrzeugdateien gleichsetzen |
| `FilesController.HandleFileUpload`, `HandleMultipleFileUpload` | POST, temporärer Upload; konventionelle Controlleraktionen | Native Uploadwege im eingeschränkten Produktmodus nicht erlauben; Rollback-/Restore-Maintenance getrennt absichern |
| `FilesController.UploadCoordinates` | konventionelle Aktion, kein eigener HttpPost-Attributzwang im geprüften Code | Seiteneffekt trotz nicht festgelegter Methode inventarisieren; nicht anhand GET pauschal freigeben |
| `FilesController.PreviewFile` | konventionelle Previewaktion | Eingebettete Pfade/Links und Berechtigungsumgehung prüfen |
| `FilesController.RestoreBackup` | POST, Root-only | Nur kontrollierte isolierte Recovery; Backup kann gesperrte Dateiinhalte erneut einbringen |
| `/api/documents/upload` | POST, `APIController.UploadDocument` | Auch öffentliche API-Uploadroute berücksichtigen |
| `/api/makebackup` | GET, Root-only Export, optionale direkte ZIP-Ausgabe | Sensibler administrativer Export, kein gewöhnlicher Readpfad |
| `/api/tempfiles`, `/api/cleanup`, `/api/demo/restore` | GET, Root-only Inventar/Cleanup/Demo-Restore | Seiteneffekte und mögliche alternative Dateizugänge bei erlaubten Adminwegen berücksichtigen |

[APIController](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/APIController.cs) belegt API-Pfade. [Program.cs](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Program.cs) belegt konventionelles `{controller=Home}/{action=Index}/{id?}`-Routing und statische Dateien. Beispiel `/Files/HandleFileUpload` ergibt sich aus der geprüften konventionellen Aktion; Attributrouten dürfen nicht automatisch als zusätzlich konventionell erreichbar behandelt werden. Ein vermeintlicher `/Files/GetStaticFile`-Alias ist daher **nur ein negativer Testkandidat**, keine hier behauptete erreichbare Route.

### Vorgeschlagene Lösungsoption und Positivallowlist

Option A zur Entscheidung: sensible Originale ausschließlich in Paperless, Garage speichert autorisierte Referenzen. Im LL-Produktmodus keine nativen sensiblen Anhänge hochladen/anzeigen; alte LL-Dokumente nur durch getrennt freigegebene Migration behandeln. Zusätzlich eine **methoden- und routenspezifische Positivallowlist** für tatsächlich benötigte Web-/API-Funktionen prüfen: Default deny, freigegebene Assets/Seiten/Operationen aus vollständigem gepinntem Routeinventar und Browserabnahme ableiten. Upload, Temp, Preview, Export, Restore, Import und administrative Wege bleiben gesonderte Wartungsfunktionen. Pfadsperren sind keine vollständige Dokumentautorisierung; diese Option reduziert erlaubte Funktionen und kann REQ-026/Benutzbarkeit verändern. Vollständigen UI-Abnahmetest vor Entscheidung ausführen.

Option B: verifizierte Upstream-Korrektur mit objektbezogener Dateiautorisierung in einer erneut geprüften Version. Option C: dokumentierte anwendungsbewusste Vermittlung mit eindeutigem Fahrzeug-/Dateibesitz, die **alle** direkten nativen Zugänge technisch ausschließt. Ein Garage-Downloadproxy neben weiterhin erreichbarem LL-Dokumentpfad genügt nicht.

Bypass-Tests für jede Option: Groß-/Kleinschreibung, normalisierte/doppelte Slashes, URL-Encoding und doppelte Kodierung, Dot-Segmente, Query-/Pathparameter, HEAD/alternative Verben, Method-Override soweit unterstützt, Range-/Cacheabruf, Redirects, Preview, API/Browser/Temp/Import/Restore, bekannte alte Links, Rechteentzug und parallele/alte Sessions. Proxy und Origin müssen dieselbe normalisierte Route bewerten; nicht erreichbare Testkandidaten dokumentieren. Autorisierter Abruf muss weiterhin funktionieren. Direkter Container-/LAN-Origin darf den Vermittler nicht umgehen. Keine Nginx-Konfiguration oder reale Routingänderung wird hier geliefert.

## T02/T05: native Writes, Audit und CSRF gemeinsam prüfen

Ein vorgeschaltetes Write-Audit muss mehr als HTTP-Status speichern: Manche LL-Operationen liefern HTTP 200 mit fachlichem Fehler. Es braucht tatsächlichen Actor, Fahrzeug/Objekt, bestätigten Inhalt, Zeitpunkt und Erfolg/Vorher-Nachher bzw. belastbares Änderungsdelta. Webhook-Retry oder spätes Snapshotdiff beweist nicht, wer dazwischen welchen Wert änderte. API-Keys, Cookies und Basic-Auth können unterschiedliche Identitäten priorisieren; getrennte Testclients verhindern falsch positive Rollentests. [Authen.cs](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Middleware/Authen.cs)

Mögliche Entscheidung: alle fachlichen Writes durch vollständig auditierbare Domänenoperationen führen und native Writes technisch ausschließen. Das hat Aufwand und Auswirkungen auf das Bestands-UI-Prinzip; nicht durch „read-only“ im Frontend oder pauschales Blockieren aller POSTs gelöst, da Lesen/Anmelden ebenfalls POSTs verwenden können und GETs Nebenwirkungen haben. Alternative: belegter nativer/upstream Auditvertrag. Bis zur Entscheidung B03 offen halten.

Die punktuelle Quellprüfung fand in `Program.cs`, `Controllers/` und `Filter/` keine expliziten Treffer für `ValidateAntiForgery`/`Antiforgery`; daraus folgt **kein alleiniger vollständiger CSRF-Nachweis**. Browser-Cookieattribute, SameSite-Kontext, Origin-/Referer-Prüfungen und tatsächliche Form-/Ajaxwege brauchen Tests. Access und SameSite allein sind keine bewiesene Absicherung sämtlicher nativer Wege. Eigene Garage-API soll Cookie-Session plus CSRF-Token/Originprüfung oder getrennte nicht automatisch versendete API-Credentials nutzen; CORS ist keine Autorisierung.

## Restore und Incident als Sicherheitsgrenze

Ein bekannt guter Restore bewahrt möglicherweise gültige API-Keys und entschlüsselbare alte Sessions. Nach Kompromittierung müssen Berechtigungen/Secrets nach getrenntem Rotationsplan neu geprüft werden; vollständiges Kopieren der Keys darf nicht mit Sessionentzug verwechselt werden. Fehlende Keys dürfen weder `EnableAuth=false` noch offene Erstregistrierung als Recovery-Abkürzung auslösen. Neue Instanz bleibt bis zur Auth-Abnahme isoliert.

Nach Restore B16 mit Outsider wiederholen, weil Backup/Import Dateien und Zugänge zurückbringen kann. Die bisherigen Tests belegen Daten-/Anhangswiederherstellung und ausgewählte Rechte, keine durchgängige Host-/Offsite-/Key-Recovery. Runbooks halten Worker/Egress bis zum externen Zustandsabgleich gesperrt; Wiederherstellung einer DB darf nicht automatisch Telegram-/Kalenderaktionen wiederholen.

## Evidenzanforderung und Restrisiken

Für jeden Test später festhalten: Version/Digest, synthetische Actor-/Objektrolle, Requestmethode/normalisierter Pfad ohne Geheimnisse, erwartetes Verhalten, tatsächlicher HTTP- und Fachstatus, Datenänderung/Bytezugriff, Ergebnis nach Entzug/Restore und sanitizierte Referenz. Kein reales Dokument als Probe. Bestehende Findings dürfen im Regressionstest nicht als behoben gelten, nur weil der Test ausschließlich 401 für anonyme Nutzer prüft.

Nicht gelöst durch dieses Modell: Betriebssystem-/Hypervisorhärtung auf unbekanntem Host, vollständige Supply-Chain-Prüfung, Browser-/Provider-Sicherheitsstand, beweisfeste Unveränderlichkeit gegenüber einem vollprivilegierten DB-/Hostadministrator und absolute Exactly-once-Zustellung externer APIs. Diese Grenzen explizit in Abnahme/Scope aufnehmen; technische Maßnahmen nach Priorität und tatsächlicher Phase planen. Alle Schutzoptionen bleiben vorgeschlagen. Die ausdrücklich freigabepflichtigen produktiven Aktionen ergeben sich ausschließlich aus AGENTS.md Regel 6 und dem konkreten späteren Auftrag.

## WP01-Runtimefortschreibung — 2026-10-27

[42 gezielte Checks](../discovery/wp01-runtime-verification.md) ergänzen dieses bisherige Planungsmodell: Household-View und API-Viewer sind keine globale Schreibbarriere; native und öffentliche Kilometer-GETs konvertieren persistent, Tax-Viewprüfung erzeugt Kostenbelege, Viewer-Upload ist möglich. Dokumentbytes bleiben trotz entzogenem Householdzugriff und Restore sichtbar. Ein fremder Origin mit manuell gesetztem gültigem Cookie wird für einen nativen Formwrite serverseitig akzeptiert; Browser-/SameSite-Ausnutzbarkeit weiterhin offen. Eine enge lokale Positivliste blockiert 31 ausgewählte Varianten ohne Upstreamkontakt, aber keine vollständige Origin-/Native-UI-/Auditgrenze ist nachgewiesen. T01/T02/T05 bleiben Freigabegates, keine als behoben ausgegebenen Findings.
