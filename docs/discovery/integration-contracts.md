# Integrationsverträge und Datenverantwortung — Phase 0

Stand: 2026-10-26. Recherche und Architekturvorschlag; keine laufenden Integrationen, keine Prüfung gegen die private Homelab-Installation. Die LubeLogger-Prüfung steht in [lubelogger.md](lubelogger.md). Verbindliche Auswahl und offene Alternativen werden in den [ADRs](../adr/README.md) geführt.

> **Einzelnutzer-Fortschreibung 2026-10-27:** Alle durch Cloudflare Access zugelassenen Webnutzer sind Admin und dürfen alle Fahrzeuge/Dokumente sehen. Die folgenden früheren Überlegungen zu unterschiedlichen Web-Objektberechtigungen sind keine zusätzliche Produktanforderung. Die Prüfung des tatsächlichen Access-/Origin- und Paperless-Dienstzugangs bleibt erforderlich: [ADR-0008](../adr/0008-single-user-access.md).

## Bestandsaufnahme und Vorgehen

README, AGENTS.md und alle drei ursprünglichen Dokumente unter `docs/` gelesen. Das Repository enthält bisher ausschließlich Planung. Annahmen: ein autorisierter Besitzer, bestehendes Paperless mit unbekannter Version, keine vorhandenen Zugangsdaten oder bestätigte Kalender-ID. Vorgehen: offizielle Schnittstellen prüfen, Verantwortungsgrenzen festhalten, Konflikt- und Ausfallverhalten entwerfen; Verträge später gegen isolierte Testinstanzen validieren.

## Nachgewiesene externe Fähigkeiten

### Paperless-ngx

Die offizielle Dokumentation beschreibt `GET /api/documents/`, `GET /api/documents/{id}/` und Download unter `/api/documents/{id}/download/`. Token-Authentifizierung nutzt `Authorization: Token <token>`. `/api/schema/view/` stellt die API-Dokumentation bereit. API-Versionen werden per `Accept` ausgehandelt; der geprüfte Dokumentationsstand nennt Versionen 9/10 und `Accept: application/json; version=10`. Die Header `X-Api-Version` und `X-Version` dienen der Kompatibilitätsprüfung. Das ist keine Aussage über die installierte Homelab-Version. [Offizielle API-Dokumentation](https://docs.paperless-ngx.com/api/), abgeglichen mit [docs/api.md, Commit 7d8147c21d4f3984c8b5195b719ed7e0a35f65a1](https://github.com/paperless-ngx/paperless-ngx/blob/7d8147c21d4f3984c8b5195b719ed7e0a35f65a1/docs/api.md), Abruf 2026-10-26.

Globale und objektbezogene Rechte wirken gemeinsam. Eine Berechtigung auf einem Tag gewährt keine Berechtigung auf die damit markierten Dokumente. Superuser umgehen diese Abgrenzung und eignen sich deshalb nicht als Integrationskonto. [Paperless: Berechtigungen](https://docs.paperless-ngx.com/usage/#permissions), Abruf 2026-10-26.

### Google Calendar

Kalenderereignisse unterstützen eigene IDs: 5–1024 Zeichen aus `0–9` und `a–v`, eindeutig innerhalb des Kalenders. `id` und `iCalUID` sind unterschiedliche Identitäten. Ganztagstermine verwenden `start.date` und ein exklusives `end.date`. **Native Reminder erlauben maximal 40320 Minuten, also 28 Tage.** 30 Tage entsprechen 43200 Minuten und sind deshalb für REQ-011 nicht als nativer Reminder am HU-Termin darstellbar. Sieben Tage (10080 Minuten) sind zulässig. [Events: insert, Felder `id`, `end.date`, `reminders.overrides[].minutes`](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert), Abruf 2026-10-26.

Updates können fremde Änderungen mit ETags erkennen. [Events-Ressource und Update-Semantik](https://developers.google.com/workspace/calendar/api/v3/reference/events), Abruf 2026-10-26. Die Fehlerdokumentation benennt unter anderem `409 duplicate`, `412 conditionNotMet`, Authentifizierungsfehler und temporäre Ratenbegrenzung. [Calendar: Fehlerbehandlung](https://developers.google.com/workspace/calendar/api/guides/errors), Abruf 2026-10-26.

## Datenverantwortung — Vorschlag

| Information | Vorgeschlagene führende Speicherung | Abgrenzung / offene Entscheidung |
| --- | --- | --- |
| Fahrzeuge, Kilometerhistorie, Wartungs-/Reparaturkosten | LubeLogger | Adapter liest/schreibt nur geprüfte API-Felder; keine direkte Datenbankintegration. |
| Wartungsregeln und berechnete Fälligkeiten | Auswahl offen | Regel-Owner einmalig festlegen; LubeLogger-UI und Garage dürfen keine konkurrierenden Regeln pflegen. Quellenpflicht, `was zuerst eintritt` und API-Lücken entscheiden die Auswahl. |
| Technische Probleme, Schweregrade, verknüpfte Diagnoseversuche | Künftige Garage-Persistenz | Problem-ID mit Append-only-Ereignissen; Änderungen ergänzen die Historie, statt sie still zu überschreiben. |
| Telegram-Dialoge, Bestätigungen, Audit, Zustellstatus, Integrationszuordnungen | Künftige Garage-Persistenz | Keine Replikation aller Fahrzeugdaten; externe IDs und minimale Projektionen mit Lesedatum. |
| Dokumentdateien und OCR | Bestehendes Paperless | Garage hält Referenz, Kategorie und berechtigte Zuordnung zum Fahrzeug/Vorgang. |
| Kalendertermine | Google als Projektion | Führende Fälligkeit liegt beim noch auszuwählenden Regel-Owner; Kalenderänderungen dürfen keine Wartung als erledigt markieren. |
| KI-Vorschläge | Separat markierte Garage-Datensätze, später | Keine Wartungsregel oder Reparaturhistorie wird allein durch Modellausgabe zum Fakt. |

Eine stabile lokale `vehicleId` wird auf `(lubeInstanceId, externalVehicleId)` abgebildet. Externe IDs gelten nur im Kontext ihrer Instanz; nach Restore/Neuimport sind Zuordnungen zu prüfen. Eine Garage-ID erteilt keine Berechtigung. Vor jedem Lese-/Schreibzugriff muss der Server Besitzer und Fahrzeugzuordnung prüfen.

## Adaptervertrag — Vorschlag für spätere Implementierung

Dies sind interne Operationsnamen, keine behaupteten HTTP-Endpunkte von LubeLogger:

| Adapteroperation | Eingabe / Ergebnis | Fehler- und Konsistenzvertrag |
| --- | --- | --- |
| `getVehicleSnapshot` | Fahrzeugreferenz → Daten, Herkunft, `readAt`, Fähigkeiten | Nicht verfügbare Felder explizit `unsupported`; Ausfall liefert markierten letzten Lesestand oder `unavailable`. |
| `recordOdometerReading` | Fahrzeug, Kilometer, Erfassungsdatum, bestätigter Befehl | Ganze Kilometer, Datum plausibel; sinkende Stände benötigen begründete Korrektur. Datum-/Rückdatierungsfähigkeit erst nach LubeLogger-Vertragsprüfung zusagen. |
| `recordMaintenance` | Fahrzeug, Typ, Datum, Kilometer, Kosten, bestätigter Befehl | Keine automatische Fristneuberechnung ohne festgelegten Regel-Owner und gültige Quelle. |
| `resolveDocumentReference` | Instanz, Dokument-ID → zulässige Metadaten / Link | Erst Garage-Berechtigung, dann Paperless-Prüfung; fehlende/entzogene Rechte zeigen keine gecachten Inhalte. |
| `projectHuDueDate` | bestätigte HU-Fälligkeit, Version, Kalenderzuordnung | Asynchrone Projektion; Google-Ausfall blockiert lokale Durchführungserfassung nicht. |

Ein späteres Maschinenformat muss dieselben Felder mindestens in folgender Form abbilden (Beispiel nur mit synthetischen Werten, kein fertiges API-Schema):

```json
{
  "contractVersion": 1,
  "commandId": "synthetic-command-001",
  "vehicleId": "synthetic-vehicle-001",
  "actorId": "synthetic-authorized-owner",
  "operation": "recordOdometerReading",
  "confirmedAt": "2026-10-26T12:00:00Z",
  "expectedRevision": 3,
  "payload": { "kilometers": 12345, "recordedOn": "2026-10-26" }
}
```

`actorId` und Bestätigung dürfen nicht aus ungeprüften Clientfeldern übernommen werden. Die obige Darstellung beschreibt den intern bereits authentifizierten Befehl. Server erzeugt `commandId`, bindet Bestätigung an Nutzer, Fahrzeug, Inhaltshash, Ablaufzeit und Revision. `expectedRevision` ist Garage-Optimistic-Locking, keine zugesagte LubeLogger-Fähigkeit.

## Idempotenz, Konflikte und Ausfälle — Vorschlag

- Bestätigte Garage-Änderung, Audit und Outbox-Eintrag werden in einer lokalen Transaktion gespeichert. Arbeit wird mindestens einmal zugestellt; exakt einmal über mehrere Systeme wird nicht behauptet.
- Adapter führen pro `commandId` ein Ergebnisjournal. Vor externem Aufruf Status `in_flight`, danach externe Referenz und Ergebnis. Bei Timeout nach möglichem Schreibabschluss Status `uncertain`; keine blinde Wiederholung nicht-idempotenter Schreibzugriffe. Erneut lesen/abgleichen oder manuelle Klärung, falls externe API keine sichere Identität bietet.
- Rückmeldungen unterscheiden `pending`, `succeeded`, `failed`, `uncertain`. Ein Telegram-Dialog bestätigt nicht schon den externen Erfolg. Wiederholtes Bestätigen desselben Befehls erzeugt keinen neuen Auftrag.
- Temporäre Netz-/Serverfehler werden begrenzt mit exponentiellem Backoff und Zufallsanteil wiederholt. Auth-/Validierungsfehler brauchen Korrektur; keine Endlosschleife. Fehlerdetails und Tokens nicht an Telegram weitergeben.
- Nativer LubeLogger-Zugriff bleibt bei Google-/Paperless-/KI-Ausfall verfügbar. Garage-Aufträge mit fehlendem LubeLogger bleiben ausstehend; neue Snapshots werden nicht erfunden. Regelmäßiger Leseabgleich erkennt native UI-Änderungen. Fehlt externes Versions-Locking, parallele Änderungen als Restrisiko dokumentieren und vor Schreiben erneut lesen.
- Erinnerungsjournal mit eindeutigem Schlüssel `(taskId, dueRevision, channel, offsetDays)`; Scheduler prüft täglich in `Europe/Berlin` und holt fällige, nicht zugestellte Einträge nach. Nach Friständerung alte ausstehende Revisionen verwerfen. Telegram sendet bei unklarem Timeout möglicherweise bereits; ohne nachgewiesene externe Deduplizierung nicht „keine Duplikate garantiert“ behaupten. Unklare Zustellung markieren und festgelegte Wiederholungsstrategie anwenden.

## Paperless-Referenzen — Vorschlag

`DocumentReference` enthält `paperlessInstanceId`, numerische `documentId`, optionale `versionId` nur bei nachgewiesener Serverunterstützung, `vehicleId`, optional `problemId`/Wartungsreferenz und Kategorie. Kein API-Token, OCR-Text oder Dateiduplikat in URLs/Audit/Telegram. Bei Referenzierung erst Metadatenzugriff mit dem vorgesehenen eingeschränkten Dienstkonto prüfen. Browserlinks ausschließlich aus konfigurierter vertrauenswürdiger Basisadresse und ID erzeugen; die konkrete UI-Route gegen die installierte Version validieren.

Browser muss Paperless selbst authentifizieren. Garage-Dienstkonto berechtigt nicht automatisch Browser oder Telegram. Falls später ein Download-Proxy erforderlich wird, prüft er bei jedem Aufruf Garage-Rechte und aktuellen Paperless-Zugriff; kein öffentliches Storage und keine dauerhaft gültigen Download-URLs. MVP-Verknüpfungen benötigen nur Leserechte; keine Dokumentänderungen, Uploads oder Berechtigungsänderungen durch Garage. Löschung/Unzugänglichkeit erzeugt eine defekte Referenz mit Reparaturhinweis, keine automatische Neuanlage oder Löschung der Garage-Historie.

## HU-/Kalendervertrag — Vorschlag, Entscheidung offen

HU-Durchführung erfasst tatsächliches Datum, Belegreferenz, bestätigte nächste Fälligkeit und Regelquelle. Die Anforderung nennt einen Regelfall von 24 Monaten; hier wird keine rechtliche Intervallregel validiert. Erstzulassung, Fahrzeugart und abweichende Bescheide können relevant sein und müssen vor Automatisierung mit aktuellen zuständigen Quellen geklärt werden. Bei fehlender Quelle oder Ausnahme bleibt die nächste Fälligkeit manuell bestätigungspflichtig. Keine starre zweijährliche Google-Wiederholungsserie.

Pro Fahrzeug/HU-Aufgabe ein stabiler Haupttermin für die nächste bestätigte Fälligkeit. Identität aus dauerhaft gespeicherter zufälliger UUID in zulässiger Hex-Darstellung ohne Bindestriche; Mapping `(calendarId, taskId, role) → eventId, etag, desiredRevision`. Bei neuer HU dieselbe Ereignis-ID aktualisieren. `409 duplicate` löst Lesen und Identitätsprüfung aus, nicht Anlegen unter neuer ID. Bei `412` erneut lesen und Konflikt sichtbar bearbeiten. Manuell gelöschte/verschobene Termine nicht ungefragt mit neuer ID duplizieren; Wiederherstellung nach definierter Konfliktregel.

REQ-011 bleibt offen: empfohlen wird zusätzlich ein eigenes Kalenderereignis `role=notice30`, datiert auf Fälligkeit minus 30 Kalendertage, mit einer eigenen stabilen Identität. Der Haupttermin erhält den nativen 7-Tage-Reminder. Das 30-Tage-Ereignis wäre ein sichtbarer Ersatz mit eigenem Reminder zum Ereigniszeitpunkt; es ist kein nativer 30-Tage-Reminder am Haupttermin. Nutzerentscheidung und Test der tatsächlichen Benachrichtigungszustellung erforderlich. Nicht still auf 28 Tage verkürzen; Telegram-30-Tage-Erinnerung aus REQ-009 bleibt unabhängig davon.

Datumsregeln: Fälligkeiten als `LocalDate`, HU-Haupttermin ganztägig mit `end.date = start.date + 1 Tag`; Ereigniszeitpunkte/Audit in UTC, Tageswechsel und Reminderberechnung in `Europe/Berlin`. Kalenderzeitzone explizit prüfen. „30 Tage vorher“ bedeutet lokale Kalendertage, nicht `30 × 24 Stunden`; Monatsintervalle brauchen eine dokumentierte Monatsende-Regel. Kalenderbeschreibungen enthalten minimale Daten und keinen Fahrzeugschein, keine echte FIN oder Dokumentinhalte.

## Noch nachzuweisen: Sandbox-Prüfungen

| Prüfung | Erwartetes Ergebnis / spätere Abnahme |
| --- | --- |
| Paperless-Version/API-Aushandlung | Installierte Version und Schema dokumentiert; unterstützter `Accept`-Header fest gepinnt, unbekannte Version führt zu verständlichem Kompatibilitätsfehler. |
| Paperless-Dienstkonto | Zulässiges Dokument abrufbar; fremdes, nicht freigegebenes Dokument weder via Liste noch direkter ID lesbar; Entzug wirkt sofort. |
| Dokument-Link | Browser wird authentifiziert; kein Token in URL; entfernte Dokumente bleiben nachvollziehbare defekte Referenzen. |
| Externer Schreib-Timeout | Keine blinde doppelte Wartung/Kilometererfassung; Auftrag sichtbar unklar, Abgleich durchführbar. |
| Kalender-ID/Reminder | Wiederholung und Prozessabbruch erzeugen keinen zweiten Haupttermin; 7 Tage akzeptiert, 43200 Minuten gezielt abgelehnt; 30-Tage-Alternative erst nach Entscheidung prüfen. |
| Datum / Scheduler | Sommer-/Winterzeit, Monatsende, Schaltjahr, rückdatierte Erfassung, veränderte Fristen und Neustart nach Fälligkeit nachvollziehbar behandelt. |
| Zugriff / Bestätigung | Fremde Telegram-ID und Fahrzeugreferenz abgelehnt; abgelaufene/veränderte Bestätigung verworfen; erneute gültige Bestätigung bleibt derselbe Befehl. |

Diese Prüfungen sind geplante Abnahmekriterien, keine bereits ausgeführten Integrationstests. Ohne Zielinstanzen, freigegebene Zugangsdaten und aufgelöste ADRs ist kein produktiver Integrationsnachweis möglich.
