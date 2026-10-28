# LubeLogger: Integrationsprüfung

Ergänzung: Die folgende Datei ist die ursprüngliche statische Discovery. Die inzwischen ausgeführte [B01/B02-Laufzeitprüfung](lubelogger-runtime-verification.md) dokumentiert tatsächliche Ergebnisse und weitere Grenzen, ohne diesen Quellenbericht rückwirkend als Testprotokoll umzudeuten.

Stand und Abrufdatum: 2026-10-26. Statische Prüfung offizieller Dokumentation und des Release-Quellcodes; keine Instanz gestartet und keine Schreiboperation gegen eine fremde Installation ausgeführt. API-Verhalten ist damit quellenbelegt, aber noch nicht durch Laufzeittests bestätigt.

## Referenz und Lizenz

Untersucht wurde **v1.7.4**, Release vom 14.10.2026, Commit `63fa5cd267497ba01c29f4888c65efbbdd4b94bf`. Dies war beim Abruf das neueste Release. `main` ist laut Installationsdokumentation experimentell; spätere Implementierung muss Release und Image-Digest separat festhalten. Die MIT-Lizenz erlaubt Nutzung und Änderungen unter Erhalt der Lizenz-/Copyright-Hinweise bei Weitergabe. Lizenzen von Containerbestandteilen bleiben gesondert zu prüfen. Quellen: [Release](https://github.com/hargata/lubelog/releases/tag/v1.7.4), [Lizenz](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/LICENSE), [Installation](https://docs.lubelogger.com/Installation/Getting%20Started/).

## Authentifizierung und Transport

Die offizielle API unterstützt Basic Auth sowie API-Schlüssel im Header `x-api-key`. Schlüsselrollen sind Viewer (lesen), Editor (zusätzlich anlegen/ändern) und Manager (zusätzlich löschen); Schlüssel handeln mit den Fahrzeugrechten ihres Nutzers. SSO-Nutzer sollen API-Schlüssel verwenden. Vorschlag: eigener Nicht-Root-Integrationsnutzer mit Zugriff nur auf die fünf freigegebenen Fahrzeuge; Viewer für Discovery, später Editor nur für freigegebene Schreibfälle. Keine Schlüssel in URLs oder Logs. Authentifizierung muss in LubeLogger aktiv sein; Cloudflare Access ersetzt diese nicht.

JSON, Form-Data und URL-encoded Bodies sind unterstützt. Antworten sind standardmäßig sprachabhängig und häufig Strings; `LUBELOGGER_INVARIANT_API=true` oder der Request-Header `culture-invariant` aktiviert typisierte, kulturunabhängige Ausgabe. Eingaben dennoch mit deutschem und invariantem Locale testen: Controller parsen intern Datum und Kosten. Keine Verwechslung von Meilen, Kilometern und Betriebsstunden zulassen. Quelle: [API-Dokumentation](https://docs.lubelogger.com/Advanced/API/), [Berechtigungen](https://docs.lubelogger.com/Installation/Authentication/), [API-Key-Filter](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Filter/APIKeyFilter.cs).

## Verifizierte API-Oberfläche

Pfade sind im Release-Quellcode vorhanden, keine angenommenen REST-Konventionen. `vehicleId` wird bei fahrzeugbezogenen GETs und JSON-Anlage im Query übergeben; Aktualisieren verwendet die Datensatz-`Id` im Body. Löschen ist hier nur zur Vollständigkeit aufgeführt und kein geplanter Bot-Anwendungsfall.

| Operation | Methode und Pfad | Wesentliche Angaben / Grenzen |
|---|---|---|
| Fahrzeuge lesen | `GET /api/vehicles` | Auf Nutzerrechte gefiltert |
| Fahrzeugstatistiken | `GET /api/vehicle/info?vehicleId=…` | Statistiken; kein Ersatz für vollständige Stammdaten |
| Fahrzeug anlegen/ändern | `POST /api/vehicles/add`, `PUT /api/vehicles/update` | `VehicleImportModel`, bei Update `Id` |
| Kilometerhistorie | `GET /api/vehicle/odometerrecords?vehicleId=…` | Liste mit `Id`, Datum, Start-/Endstand |
| Kilometerstand anlegen | `POST /api/vehicle/odometerrecords/add?vehicleId=…` | JSON: `Date`, `Odometer`, optional `InitialOdometer`, `Notes`, `Tags` |
| Kilometerstand ändern | `PUT /api/vehicle/odometerrecords/update` | `Id`, vollständigen geprüften Schreibvertrag verwenden |
| Wartungen / Reparaturen | `GET /api/vehicle/servicerecords`, `GET /api/vehicle/repairrecords` | Jeweils `vehicleId` |
| Wartung / Reparatur anlegen | `POST /api/vehicle/servicerecords/add`, `POST /api/vehicle/repairrecords/add` | `vehicleId` im Query; `Date`, `Odometer`, `Description`, `Cost`; optional Notizen, Tags, Zusatzfelder, Anhänge |
| Wartung / Reparatur ändern | `PUT /api/vehicle/servicerecords/update`, `PUT /api/vehicle/repairrecords/update` | `Id` im Body |
| Fälligkeiten | `GET /api/vehicle/reminders?vehicleId=…` | U. a. `Metric`, `UserMetric`, `DueDate`, `DueOdometer`, `DueDays`, `DueDistance`, `Urgency` |
| Fälligkeit anlegen/ändern | `POST /api/vehicle/reminders/add?vehicleId=…`, `PUT /api/vehicle/reminders/update` | `Description`, `Metric` = `Date`/`Odometer`/`Both`, entsprechende Fälligkeitswerte; Update zusätzlich `Id` |
| Aufgaben | `GET /api/vehicle/planrecords?vehicleId=…`, `POST /api/vehicle/planrecords/add?vehicleId=…`, `PUT /api/vehicle/planrecords/update` | Planner-Modell, kein technisches Problem-/Auditmodell |
| Teile und Steuern | `GET /api/vehicle/supplyrecords?vehicleId=…`, `GET /api/vehicle/taxrecords?vehicleId=…` | Auch `/add` mit POST und `/update` mit PUT vorhanden |
| Anhänge hochladen | `POST /api/documents/upload` | Multipart; Zuordnung zum Vorgang gesondert prüfen |
| Kalenderexport | `GET /api/calendar` | iCalendar-Datei; keine Google-Calendar-Synchronisierung |

Primärquellen: [Basiscontroller](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/APIController.cs), [Odometer](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/API/OdometerController.cs), [Service](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/API/ServiceController.cs), [Repair](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/API/RepairController.cs), [Reminder](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/API/ReminderController.cs), [Plan](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/API/PlanController.cs), [Supply](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/API/SupplyController.cs), [Tax](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/API/TaxController.cs).

Antwortvertrag: Schreiboperationen liefern `OperationResponse` mit `Success`, `Message`, gegebenenfalls `AdditionalData.recordId`. Ein HTTP-2xx allein reicht nicht als Erfolgskriterium: einzelne Validierungszweige liefern Fehlerobjekte ohne Fehlerstatus. Property-Casing durch Fixture festhalten. Quelle: [OperationResponse](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/Shared/OperationResponse.cs).

## Abdeckung der Wolfs-Garage-Anforderungen

„Vorhanden“ bedeutet quellenbelegt und noch nicht betrieblich abgenommen.

| Anforderungen | Ergebnis | Konsequenz |
|---|---|---|
| REQ-001–003 | Fahrzeuge und Kilometerhistorie vorhanden | Telegram-Erfassung braucht Adapter, Motorisierung als validiertes Zusatzfeld |
| REQ-004–005 | Eigene Prognosen und belegte Herstellerrecherche nicht nachgewiesen | Garage-Erweiterung; Herstellerquelle inklusive Gültigkeit erfassen |
| REQ-006–008, 012 | Datum, Strecke, frühere Grenze und wiederkehrende Erinnerungen in UI vorhanden | Wichtige API-Lücke siehe unten; HU als Aufgabe/Fälligkeit, keine unterstellte deutsche Rechtslogik |
| REQ-009–011 | Telegram- und Google-Sync nicht belegt | Eigene Integration; iCalendar allein erfüllt REQ-010/011 nicht |
| REQ-013 | Kosten und Notizen vorhanden | Eigenarbeit/Werkstatt/Dauer/Werkstattname als Zusatzfelder prüfen |
| REQ-014–015 | Teileverwaltung, Verwendung und Kostenauswertung in UI vorhanden | API-Verwendung von Teilen und Vermeidung doppelter Kosten prüfen |
| REQ-017–022 | Notes/Planner vorhanden, gefordertes Problem-/Ereignismodell nicht nachgewiesen | Eigenes Modell für Schweregrad, Statushistorie, Wiederholung und Warnungen |
| REQ-023–025 | Bestehende Fahrzeug-/Wartungsoberflächen nutzbar | Ampel über technische Probleme erst nach UI-Abnahme; eigene Ergänzungsansicht nur bei belegter Lücke |
| REQ-026–027 | Anhänge vorhanden | Paperless-Referenzen bevorzugen, keine unbestätigte native Integration annehmen |
| REQ-029–037 | Keine ausreichende native Abdeckung nachgewiesen | Spring-Boot-Assistent, Scheduler, KI später gemäß Roadmap |
| REQ-040, 043 | Backupfunktion vorhanden; vollständiger unveränderlicher Änderungsnachweis nicht belegt | Restore praktisch prüfen; eigenes Audit deckt zunächst nur Garage-Schreibwege ab |
| REQ-045–049 | Technische Basis vorhanden, Ende-zu-Ende-Verhalten offen | Berlin-Zeit, Ausfälle, Rechte und Verträge in Sandbox nachweisen |

Belege zur UI: [Reminders](https://docs.lubelogger.com/Records/Reminders/), [Odometer](https://docs.lubelogger.com/Records/Odometer/), [Supplies](https://docs.lubelogger.com/Records/Supplies/). Die Reminder-UI unterstützt Wiederholung, feste gegenüber durch Erledigung verschobenen Intervallen und manuelles Erledigen. Automatisches Fortschreiben überfälliger Erinnerungen existiert ebenfalls; dieses darf für Wolfs Garage nicht als Durchführung einer Wartung gelten. Kilometer-Dringlichkeit berücksichtigt den höchsten Stand über mehrere Belegarten; alte oder falsche Eingaben beeinflussen daher die Anzeige.

### Kritische Lücke: wiederkehrende Regeln im API-Vertrag

Das interne `ReminderRecord` kennt `IsRecurring`, `FixedIntervals`, eigene Monats-/Streckenintervalle und Schwellwerte. Der API-DTO `ReminderExportModel` und die geprüften öffentlichen Reminder-Schreibmethoden bilden diese Felder nicht ab; die GET-Ausgabe exportiert sie ebenfalls nicht. Ein öffentlicher API-Refresh-Vertrag wurde in v1.7.4 nicht gefunden. Dies ist eine konkrete Abdeckungslücke trotz funktionsreicher UI. Keine privaten MVC-UI-Routen oder direkten Datenbankänderungen als Integrationsvertrag verwenden.

Offene Entscheidung: In v1.0 wiederkehrende Regeln in LubeLogger-UI pflegen und Durchführung dort bestätigen; für v1.1 entweder upstream eine belastbare API-Erweiterung nutzen oder Regeln im Garage-Modell als alleiniger Eigentümer führen und nur konkrete nächste Termine spiegeln. Zwei unabhängig fortschreibende Scheduler sind zu vermeiden. Quellen: [internes Reminder-Modell](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/Reminder/ReminderRecord.cs), [öffentliche DTOs](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/Shared/ImportModel.cs), Reminder-Controller oben.

## Daten- und Zuverlässigkeitsgrenzen

Vorschlag: LubeLogger besitzt Stammdaten, Kilometerbelege, Wartungen/Reparaturen, Kosten und zunächst native Erinnerungen. Garage besitzt technische Probleme samt Ereignissen, Herstellerquellen, bestätigte Befehle, Audit und Integrationszustand. Externe IDs durch eine lokale stabile Fahrzeug-ID zuordnen; nicht Kennzeichen als Primärschlüssel verwenden. Zusatzfelder für Motorisierung und Arbeitsart vor Nutzung über UI und API gemeinsam prüfen.

Webhooks und SignalR sind vorhanden. API-Schreibvorgänge lösen ebenfalls Ereignisse aus. Ein Webhook wird zentral für alle Fahrzeuge gesendet. Im untersuchten Sender sind bis zu fünf HTTP-Versuche vorhanden; ein persistenter Event-Store oder eine Signatur ist dort nicht belegt. Der Payload enthält Typ, UTC-Zeit und Daten, aber keine belastbare eindeutige Event-ID, vollständige Vorher-/Nachherwerte oder durchgängige Datensatz-ID. Daraus folgt: Ereignisse höchstens als Hinweis zum autorisierten Nachlesen nutzen; periodische vollständige Reconciliation bleibt erforderlich. Quelle: [Webhook-Doku](https://docs.lubelogger.com/Advanced/Webhook/), [Sender](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Logic/Event/EventLogic.cs), [Payload](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/Shared/WebHookPayload.cs).

Eigene Befehls-ID und Outbox verhindern lokale Wiederholung. Für POST ist keine serverseitige Idempotenzgarantie belegt: nach Timeout zunächst unbekannten Ausgang markieren und abgleichen, nicht blind erneut senden. UI-Änderungen in LubeLogger können das Garage-Audit umgehen; Webhooks allein machen dieses nicht vollständig. Diese Einschränkung vor Abnahme von REQ-043 klären.

## Offene Sandbox-Abnahme vor Implementierungsfreigabe

1. Release-Image und Digest festhalten; `/api`-Dokumentation des gestarteten Zielstands sichern und mit diesen Routen vergleichen.
2. Viewer darf lesen, Editor anlegen/ändern, beide dürfen nicht löschen; fehlender/falscher Schlüssel und fremde Fahrzeug-ID müssen serverseitig scheitern. Kein Root-Schlüssel im Assistenten.
3. Synthetischen Kilometerbeleg anlegen und wieder auslesen: Datum, Einheit, IDs, Response-Casing, deutsches Locale, Zahlen/Dezimalwerte und kulturspezifische Fehler prüfen.
4. Rückdatierte Stände, Kilometerkorrekturen, automatisches Einfügen bei Wartungsbelegen und daraus berechnete Dringlichkeit testen; doppelte Historienpunkte für Prognosen erkennen.
5. Wiederkehrende Reminder einschließlich `Both`, „heute“, exakt 30/7 Tage, Ende des Monats, Schaltjahr und Berlin-Zeitwechsel testen. API-Update einer bestehenden wiederkehrenden Erinnerung darf nicht unbemerkt Regeln zerstören.
6. Wartung plus Teilverwendung und Dokumentlink im Web abnehmen; Kosten nicht zugleich als Teilekauf und Reparatur doppelt aggregieren. Zusatzfelder müssen API-Roundtrip überstehen.
7. Erfolgreichen POST mit verlorener Antwort simulieren; keine automatische Doppelanlage. `Success=false` trotz HTTP 200 sowie 401/403/5xx/Timeout kontrolliert behandeln.
8. LubeLogger direkt im Web ändern und löschen; Reconciliation, fehlende Event-ID und Audit-Lücke nachweisen. Backup auf separater Testinstanz wiederherstellen und referenzierte IDs/Anhänge kontrollieren.

Diese Punkte sind geplante Prüfungen, keine bestandenen Tests. Sie begrenzen die Empfehlung, LubeLogger als bevorzugte Basis weiterzuverfolgen.
