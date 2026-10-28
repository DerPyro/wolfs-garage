# LubeLogger B01/B02 — tatsächliche Sandbox-Ergebnisse

Stand: 2026-10-26. Getesteter Lauf: `wolfs-b02-5a27f0cb20`. [Maschinenlesbare Evidenz](evidence/lubelogger-b02.json), [Testtreiber und Reproduktion](../../tests/lubelogger/README.md), [unabhängige Quellprüfung/Lizenzmanifest](lubelogger-source-verification.md), [erweiterte Prüfmatrix](../../tests/lubelogger/acceptance-matrix.md).

## Ergebnis und Einordnung

**62 Checks ausgeführt: 51 Verträge bestätigt, 11 bekannte bzw. neu entdeckte Grenzen reproduziert, keine unerwarteten Fehler im abschließenden Lauf.** Das ist eine Charakterisierung der Zielversion, keine Produktivfreigabe. Zwei unabhängige Sub-Agents prüften Quellverträge/Lizenzen und Testfälle; der Quality-Agent prüfte zusätzlich den Treiber auf Isolation und Aussagekraft. Die Hinweise zur Fehlerredaktion, zu Objektberechtigungen, zur Restore-Abnahme und zum echten Antwortverlust wurden aufgenommen.

B01 hat eine reproduzierbare Testbaseline mit Image-Digest, Quellrevision, API-Katalog und MIT-Text. Direkte NuGet-Lizenzen sind inventarisiert; transitive/OS/Runtime/Frontend-Notices bleiben vor eigener Distribution zu vervollständigen. B02 liefert einen ersten breiten Laufzeitnachweis. Die gesamte erweiterte Matrix und die v1.0-Abnahme sind damit noch nicht abgeschlossen.

## Ziel und Isolation

- Release `v1.7.4`, Commit `63fa5cd267497ba01c29f4888c65efbbdd4b94bf`.
- Image `ghcr.io/hargata/lubelogger@sha256:483a9d7582c4e6258615fd822b3de4193b4fcc4230d0a92432c6d407faf75af2`, **linux/amd64**. OCI-Labels passen zu Release/SHA; damit ist keine zusätzliche Signatur-/Buildattestierungsprüfung behauptet.
- Docker 29.9.2, Compose v5.6.1; tatsächliches App-Locale über `/api/info`: `de-DE`, Prozesszeitzone `Europe/Berlin`.
- Zufälliger neuer Projektname, getrennte leere Volumes, internes Docker-Netz, keine veröffentlichten Ports, kein Standard-IPv4-Route. Hostprozess spricht interne Containeradressen an; kein fremdes System ist Testziel.
- Fünf synthetische Fahrzeuge, synthetisches Teil und Textdokument; Root ausschließlich für Setup/Backup. Separate Nicht-Root-/Outsider-Sessions und cookie-freie API-Key-Clients.
- Restore in einer zweiten Instanz desselben Images mit separaten Daten- und DataProtection-Key-Volumes. Beide Container am Ende gestoppt; synthetische Volumes/Backups bleiben lokal, nicht in Git.

## Nachgewiesene Verträge

| Bereich | Beobachtung |
| --- | --- |
| Identität/API-Katalog | OCI-Version/SHA stimmen. Das vom Image ausgelieferte `/defaults/api.json` ist bytegleich zum gepinnten Release, SHA256 `118df316583d3d173d48229c18e79b8264a967537682f906c62ab317696c6082`; authentifiziertes `/api` rendert. Eigener Katalog, kein OpenAPI-Vertrag. |
| Anmeldung/Rollen | Nach Root-Setup API ohne/gültigkeitslosem Key gesperrt. Viewer liest, kann keine Fahrzeuge/Kilometer anlegen oder Kilometer ändern. Editor legt an/ändert, kann weder Fahrzeug noch Kilometerbeleg löschen. Outsider sieht keine Fahrzeuge und kann fremde Belege weder lesen noch ändern. Abgewiesene Schreibwege verändern keine Testdaten. |
| Fahrzeuge/Kilometer | Fünf Fahrzeuge, Motorisierung als Zusatzfeld, Erfassung mit Datum, korrigierter Stand und rückdatierter Beleg bleiben lesbar. Invariante Ausgabe liefert Zahlen und ISO-Daten; ohne Header deutsche Datumstrings. |
| Kosten/Zusatzfelder | JSON-Zahl 123.45 und deutscher String `123,45` werden korrekt gelesen; ISO-Datum und deutsches Datum bestätigt. Wartungs-/Reparaturfelder für Arbeitsart/Dauer bleiben erhalten. Auto-Odometer-Insert kann ein-/ausgeschaltet werden. |
| Fälligkeiten | Both wird bei überschrittener Datums- oder Streckengrenze überfällig. API-Update bewahrt bestehende Wiederholung; die native HTTP-Aktion kann sie weiterschieben. Feste Intervalle, flexible Basis nach bestätigtem Wartungsdatum/-stand, Monatsende/Schaltjahr und Tagesintervalle über beide Berlin-Zeitwechsel bestätigt. Keine Hostuhr verändert. |
| Teile/Dokument | Native Requisition reduziert Menge 2→1 und Restkosten 20→10. Wartung erhält den ausdrücklich übergebenen Gesamtbetrag 15 (5 Arbeit + 10 verwendetes Teil); keine behauptete automatische Addition. Synthetisches Dokument ist am Vorgang referenziert und mit gleicher Bytefolge abrufbar. |
| Fehler/Konsistenz | Reminder-Validierung kann HTTP 200 plus `success=false` liefern. Ein lokaler Proxy lässt den POST upstream speichern und schließt anschließend ohne Antwortheader: Client sieht Transportfehler, GET findet genau einen Beleg; kein Retry erfolgt. Direkter nativer HTTP-Schreibweg wird durch frisches API-Lesen erkannt. |
| Webhooks | Lokaler Recorder erhält nach zwei HTTP-500-Antworten einen dritten Versuch; API-/UI-Eventtypen unterscheidbar. Es werden keine externen Webhookziele verwendet. |
| Restore | Anwendungsexport in zweite isolierte Instanz eingespielt: Fahrzeug-/Beleg-IDs, Beträge, Zusatzfelder, Dokumentreferenz und alle getesteten Datenlisten identisch. Root kann sich neu anmelden; API-Key und dessen Rechte bleiben erhalten; anonymer API-/Dokumentzugriff sowie fremder Fahrzeugzugriff bleiben gesperrt. Anhang bytegleich. |

## Reproduzierte Grenzen — nicht als erfüllt werten

1. **Kalendertage:** D+30 liefert bei laufender Tageszeit `DueDays=29`, D+7 liefert 6; D um 00:00 gilt bereits als `PastDue`. Der spätere Scheduler muss LocalDate/Europe-Berlin selbst verarbeiten, statt Provider-DueDays blind als Kalendertage zu verwenden.
2. **Reminder-Export:** Wiederholungsfelder fehlen im öffentlichen GET.
3. **Reminder-Eingabe:** Über API mitgesendetes `IsRecurring` wird ignoriert; anschließendes natives Pushback lehnt mangels tatsächlicher Wiederholung ab.
4. **API-Wartungsanlage:** Mitgesendete Reminder-Auswahl bewirkt keine Fortschreibung.
5. **Automatisches Refresh:** Bei eingeschalteter Einstellung verändert ein nativer GET die überfällige Fälligkeit ohne bestätigte Durchführung. Für Wolfs Garage deaktiviert lassen.
6. **Custom Thresholds:** Ein nach dem benutzerdefinierten Reminder angelegter Standard-Reminder erhält eine andere Dringlichkeit als der gleich datierte Standard-Reminder davor. Reihenfolgeabhängigkeit tatsächlich reproduziert; benutzerdefinierte Provider-Schwellen vorläufig nicht freigeben.
7. **Teileverwendung per API:** `Supplies` wird ignoriert, Bestand bleibt unverändert. Öffentliche API-Wartung ist kein Ersatz für native Requisition.
8. **Dokumentberechtigung:** Angemeldeter Outsider ohne Fahrzeugrechte kann den bekannten Dokumentpfad lesen. Anonyme Zugriffe sind gesperrt. Das ist eine fahrzeugbezogene Autorisierungslücke des geprüften Aufbaus; Links/Dateinamen sind keine Zugriffskontrolle. Keine sensiblen Dokumente dort freigeben, bevor B09/B16 gelöst sind.
9. **POST-Idempotenz:** Zwei identische POSTs erzeugen zwei Datensätze. Lokale Command-ID und Reconciliation erforderlich; keine sichere automatische Wiederholung nach unklarem Ausgang.
10. **Webhook-Audit:** Beobachtete Payloads haben keine stabile Event-ID und keinen vollständigen Vorher-/Nachhervertrag. Ein Hinweis-/Abgleichkanal, kein vollständiges Audit.
11. **Backupumfang:** Anwendungsexport enthält keine DataProtection-Keys. Eigene verschlüsselte Schlüsselsicherung nötig; Anwendungsrestore beweist keinen vollständigen Hostrestore.

Die Rohbeobachtungen verwenden nur synthetische Daten. Keine Zugangsdaten oder Original-Backups sind in die versionierte Evidenz aufgenommen.

## Abdeckung der unabhängigen 28-Fälle-Matrix

Die Fallnummern der Matrix sind detaillierter als die ursprünglichen acht Discovery-Gruppen. Einzelchecks im JSON tragen beschreibende Namen; diese Zuordnung verhindert eine pauschale Abnahme noch offener Teile.

| Matrixfälle | Laufzeitabdeckung / Rest |
| --- | --- |
| B02-01–06 | Kernfälle Rollen/Objektrechte, Add/Update/Delete-Verweigerung, `/all`, Locale und Historie geprüft. Zusätzlich fremdes tatsächliches Fahrzeug auf Owner-Seite sowie rückläufige Tachostände/Prognosevalidierung noch offen. |
| B02-07 | Auto-Odometer-Insert ein/aus geprüft; globale Maximalstandwirkung durch Both-Kilometerfall abgedeckt. |
| B02-08 | Gesonderte Meilen-/Betriebsstunden- und Umrechnungserprobung offen; bisher ausschließlich Kilometerkonfiguration. |
| B02-09–15 | Locale, Zeit-/km-Grenzen, Wiederholungs-Lücke, API-Erhalt und native feste/flexible Fortschreibung geprüft. Edit-HTML-Feldvergleich nicht separat automatisiert; funktionaler Erhalt durch Pushback bestätigt. |
| B02-16–18 | Auto-Refresh-GET, Custom-Threshold-Reihenfolge, Monatsende/Schaltjahr sowie historische DST-Tagesintervalle geprüft. Kein über Tage laufender Scheduler getestet. |
| B02-19–21 | Teileabgang, API-Lücke und ausgewählte Zusatzfelder geprüft. Jahreskostenreport, konfigurierte Pflichtfelder und visuelle UI-Feldbedienung noch offen (B07). |
| B02-22–24 | Synthetische Dokumentzuordnung, erlaubter/anonymer/fremder Browserzugriff und tatsächlicher Transportantwortverlust geprüft. API-2xx-Fehlerobjekt bestätigt; vollständiger 4xx/5xx-Vertrag eines noch nicht implementierten Garage-Adapters offen. |
| B02-25–26 | API-/UI-Webhooks und zwei 500→200-Wiederholungen geprüft. Vollständige Fünf-Versuch-Erschöpfung/Prozessabbruch und Replayverhalten noch offen; keine dauerhafte Queue behauptet. |
| B02-27–28 | Root-Export, Nicht-Root-Verweigerung, ZIP-Prüfung und isolierter Restore samt Objekt-/Rollen-Negativtests bestanden. Proxmox-/Offsite-/RPO-/RTO-Abnahme bleibt B06; abweichender Dokumentzugriff nach Restore muss bei künftiger Schutzlösung erneut geprüft werden. |

## Konsequenz für die nächste Phase

Die Bestandslösung bleibt ein plausibler Kern für Stammdaten, Kilometer und Kosten. Eine Produktivfreigabe folgt daraus nicht. [ADR-0001](../adr/0001-lubelogger-integration.md), [ADR-0003](../adr/0003-deployment-security.md) und [ADR-0004](../adr/0004-integrations-consistency.md) sowie [Backlog B16/B17](../backlog.md) halten die neuen Sicherheits-/Datumsentscheidungen fest. B03 (vollständiges Audit), B04 (Regelhoheit/Kalender), B05/B06 (Betrieb/Restore) und B07 (UI) bleiben offen. Es wurden keine produktiven Dienste, Cloudflare-Ressourcen oder echten Daten verändert.
