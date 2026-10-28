# WP02 — Änderungsprotokoll im Einpersonenbetrieb

Stand: 2026-10-27. Geprüft: LubeLogger v1.7.4, Commit `63fa5cd267497ba01c29f4888c65efbbdd4b94bf` und [gepinnte Testbaseline](../../tests/lubelogger/target.lock.json). Nutzerkontext: eine Person, Cloudflare Access als äußerer Login, danach alle administrativen Funktionen erlaubt. **Keine produktiven Dienste oder Provider-/Cloudflare-Änderungen.** Die Bewertung verlangt keine Mehrnutzer-Isolation und keinen ReadOnly-Write-Gateway als Selbstzweck.

## Anforderung angemessen auslegen

REQ-043 fordert ein Änderungsprotokoll für Wartungs- und Logbucheinträge. Der Wortlaut verlangt weder vollständige Vorher-/Nachher-Snapshots aller Felder noch unveränderliche Speicherung gegen einen Administrator oder eine lückenlose rechtliche Revisionssicherheit. Diese strengeren Ziele wurden im bisherigen Architekturentwurf teilweise als notwendige Freigabebedingung unterstellt; sie sind **zusätzliche Designannahmen**, keine bestätigten Produktanforderungen.

REQ-020 verlangt gesondert eine unveränderlich nachvollziehbare Statushistorie technischer Probleme. Daraus folgt ein passendes Ereignismodell für das spätere eigene Logbuch; daraus folgt kein automatischer Auftrag, sämtliche native Wartungsverwaltung durch eine eigene Anwendung zu ersetzen.

Für eine Person ist ein verständliches Protokoll „wann wurde welcher Wartungseintrag angelegt/korrigiert/entfernt, mit welchem kurzen Hinweis“ eine angemessene zu konkretisierende Mindestzielsetzung. Welche Änderungen inhaltlich rekonstruiert werden sollen, bleibt eine Scopefrage; technische Grenzen werden offen dokumentiert und nicht mit Audit-Schlagworten verdeckt.

## Was LubeLogger tatsächlich speichert/anzeigt

| Funktion | Belegter Umfang | Grenze für REQ-043 |
| --- | --- | --- |
| Fahrzeughistorie | Aggregiert aktuell gespeicherte Service-/Repair-/Upgrade-/Tax-/Kilometer-/Tankbelege nach fachlichem Datum/Kilometerstand. | Wartungshistorie, kein Verlauf früherer Versionen: Korrektur ersetzt Darstellung, Löschung entfernt Eintrag. |
| Wartung/Reparatur (`GenericRecord`) | Id, Fahrzeug, fachliches Date, Mileage, Description, Cost, Notes, Dateien, Tags, Zusatzfelder und Teileverwendung. | Kein allgemeines Created/Modified/Actor-/Versionsfeld. Das Date ist Arbeits-/Belegdatum und kann rückdatiert sein. |
| Planner | `DateCreated`, `DateModified`, aktueller Progress und Priority; native Editansicht zeigt Erstellungs-/Änderungszeit. | Nur letzter Stand, kein gespeicherter Verlauf aller Phasenwechsel. API exportiert beide Zeitfelder als Datum ohne Uhrzeit. UI-Edit übernimmt DateCreated aus Eingabe; Metadaten sind kein geschützter Beweis. |
| Teileverwendung | RequisitionHistory mit Datum, Menge, Kosten, Teilenummer und Beschreibung. | Sachliche Verwendungshistorie, keine generelle Änderungshistorie von Wartungen. Einträge bleiben normale editierbare Daten. |
| Notes | Aktueller Notizinhalt als Fahrzeugbeleg. | Kein nachgewiesenes Append-only- oder Versionierungsmodell. |
| Datenbank | LiteDB Service-DataAccess `Upsert`, `Delete`, `Checkpoint`; PostgreSQL-Variante `UPDATE`/`DELETE` der aktuellen Zeile. | Keine in diesen geprüften Pfaden angelegte separate Versions-/Audit-Tabelle. DB-Datei/WAL/Checkpoint sind kein zugesagter fachlicher Änderungslog. |
| Laufzeitlogs | Fehler-/Betriebshinweise, etwa fehlgeschlagene Zustellung und Loginversuche. | Kein geprüfter vollständiger chronologischer Nutzdaten-Änderungsbericht. Containerlogs allein erfüllen das fachliche Protokoll nicht. |

Quellen: [GenericRecord](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/Shared/GenericRecord.cs), [VehicleHistory](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/Vehicle/ReportController.cs#L517), [PlanRecord](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/PlanRecord/PlanRecord.cs), [native Planner-Schreiblogik](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/Vehicle/PlanController.cs#L18), [Planner-API](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/API/PlanController.cs), [Planner-UI](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Views/Vehicle/Plan/_PlanRecordModal.cshtml#L54), [SupplyUsageHistory](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/Supply/SupplyUsageHistory.cs), [LiteDB-Servicezugriff](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/External/Implementations/Litedb/ServiceRecordDataAccess.cs), [PostgreSQL-Servicezugriff](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/External/Implementations/Postgres/ServiceRecordDataAccess.cs). Offizielle [Planner-Dokumentation](https://docs.lubelogger.com/Records/Planner/) beschreibt die aktuellen Phasen und die Umwandlung bei Done; sie verspricht kein unveränderliches Phasenarchiv.

## Events und Webhook als kleine Ergänzung

Die offizielle [Webhook-Dokumentation](https://docs.lubelogger.com/Advanced/Webhook/) bestätigt Ereignisse für native Fahrzeug-/Recordänderungen einschließlich API-Schreibvorgängen. Ein zentraler Webhook und SignalR informieren Empfänger über Änderungen. Im gepinnten Code liefert ein generisches Wartungsereignis Typ, Username, VehicleId, menschenlesbare Action sowie Kurzfelder wie Beschreibung, Kilometer und Kosten. **Das genügt als Grundlage eines Aktivitätsjournals**, etwa „Service korrigiert, Zeitpunkt, Fahrzeug, Kurzbeschreibung“; hierfür sind vollständige Snapshots keine Voraussetzung.

Die Grenzen sind konkret:

- GenericRecord-Events enthalten keine stabile Wartungs-Record-ID. Zwei ähnlich benannte Wartungen können nicht immer eindeutig zugeordnet werden. Ein optionaler eigener synthetischer Referenzcode in der Beschreibung wäre ein nutzerfreundlicher Konventionsweg, kein vollautomatischer ID-Ersatz.
- Notizen/Korrekturgrund, fachliches Wartungsdatum und vollständige alte Werte werden im generischen Payload nicht übertragen. Nach Löschung ist ein Nachlesen des ursprünglichen Datensatzes nicht mehr möglich.
- `Timestamp` ist ein berechneter Getter mit `UtcNow` bei Serialisierung, kein dauerhaft gespeicherter Transaktionszeitpunkt. Wiederholte Zustellversuche können verschiedene Zeitwerte erzeugen. Ein Collector sollte zusätzlich seine Empfangszeit speichern und nicht die Sendezeit als unveränderliche Event-ID verwenden.
- `PublishEvent` arbeitet `async void`, ohne in diesem Pfad gefundene persistente Queue. Bis zu fünf Versuche bei HTTP-Antwortfehlern, kein belegter Replay-/Nachliefervertrag nach Collector-/Prozessausfall. Ein Empfänger kann doppelte oder fehlende Events erleben.
- Nicht jede indirekte Änderung veröffentlicht einen eigenen fachlichen Event, etwa die gezeigte automatische Reminderfortschreibung. Ein normaler HTTP-Erfolgsstatus ist zudem nicht immer fachlicher Erfolg.
- SignalR benutzt dieselben Payloads als Livekanal, keine nachgewiesene historische Event-Abfrage. Ein permanenter SignalR-Abonnent wäre zusätzlicher Betriebsaufwand, kein automatischer Persistenzgewinn.

Quellen: [Payloads](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/Shared/WebHookPayload.cs), [Sender](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Logic/Event/EventLogic.cs), [Native Wartung](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/Vehicle/ServiceController.cs), [Reminder-Helper](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/Vehicle/ReminderController.cs). Diese Bewertung betrifft den persönlichen Überblick; sie verlangt nicht, dass sich ein Administrator technisch selbst nicht mehr ändern könnte.

## Neue isolierte Laufzeitprüfung

Reproduzierbar: `python3 tests/wp02/audit_run.py`. Der Harness erzeugt ein frisches zufälliges Docker-Testprojekt, prüft das gepinnte Image, benutzt ausschließlich das interne Docker-Netz ohne Hostport und einen lokalen Webhook am eigenen Bridgegateway. Credentials werden nur im Speicher gehalten. Kein Cloudflare-Zugriff, keine reale E-Mail/Telegram-/Kalenderverbindung. `finally` stoppt den eigenen Container; synthetische Volumes bleiben erhalten. [Sanitizierte Evidenz](../../tests/wp02/audit-results.json), [Testcode](../../tests/wp02/audit_run.py).

**12/12 Checks erfolgreich**:

- Service-API zeigt fachliches Datum, keine Created-/Modified-Metadaten.
- API-Korrektur ersetzt aktuellen Text/Kosten; native Fahrzeughistorie enthält korrigierten Text, keine vorherige Beschreibung.
- Nach Löschen fehlt Service sowohl in aktueller API-Liste als auch im Fahrzeughistorienbericht.
- Lokaler Recorder empfängt API- und native MVC-Serviceaktionen add/update/delete jeweils als drei Events; Actor/Fahrzeug/UTC-Zeit/Kurzfelder vorhanden, Record-ID und Notiz-/Korrekturgrund fehlen.
- Planner-API liefert Created/Modified als Tageswerte. Native Planner-Editansicht zeigt bei Korrektur eine neue Last-Modified-Uhrzeit und unverändertes DateCreated; API zeigt nur aktuellen Progress.

Ein anfänglicher lokaler Recorder-Fehler bei Chunked-HTTP wurde im Harness korrigiert; das war kein Produktfehler. Danach erfolgreicher Durchlauf; zusätzliche Image-/Netzassertions ebenfalls geprüft. Keine Simulation manipulationssicherer Speicherung, kein neuer Nachweis vollständiger Eventzustellung nach Ausfall, keine Vollprüfung aller UI-Screens. Frühere [B01/B02-Evidenz](lubelogger-runtime-verification.md) bestätigt bereits lokale Webhook-Retries nach zwei 500-Antworten; das ist keine dauerhafte Queuegarantie. Alle von diesem Audit-Harness erstellten Container sind nach Abschluss gestoppt.

## Kleine, konkrete Alternativen

| Option | Aufwand / Verhalten | Ehrlicher Umfang |
| --- | --- | --- |
| A — native Historie plus bewusste Korrektureinträge | Sofortige Arbeitsweise: echte Durchführung als Beleg, spätere sachliche Korrekturen mit datierter Notiz „korrigiert am …, Grund …“; versehentlich erfasste Belege vor Löschen kurz dokumentieren. Regelmäßiges Backup. | Persönlich brauchbarer Verlauf bei konsequenter Pflege; keine automatische Beobachtung jeder beliebigen Bearbeitung. Nicht als schon vollständig automatisches REQ-043 abhaken. |
| B — kleines lokales Webhook-Aktivitätsjournal | Vorhandenen Logging-/Webhookempfänger weiterverwenden, falls vorhanden; andernfalls später kleiner lokaler Collector mit JSONL/SQLite, Empfangszeit, Typ, Fahrzeug, Actor, Kurztext und Rohpayload. Schnelle Persistierung vor 2xx, Rotation/Backup, Zustellwarnung; kein neuer Browser-Schreibpfad. | Automatischer Überblick über empfangene native/API-Änderungen. Dokumentierte Lücken bei Ausfall, Ambiguität und nicht publizierten Nebenwirkungen; doppelte Events kennzeichnen. Kein versprochenes Vollversionsarchiv. |
| C — tägliche Snapshots/Exporte zusätzlich | Bereits geplante Backups/Exporte als Rückfall für versehentliche Änderungen verwenden. | Wiederherstellbare Stände, kein Ersatz für Ereignisprotokoll zwischen Sicherungen. Kein eigenes Dienstsystem nötig. |
| D — vollständiger kontrollierter Schreibweg/Upstream-Erweiterung | Erst bei konkretem Bedarf an nachweislich jeder Feldänderung, eindeutigen Record-IDs oder verlustfreier Nachlieferung prüfen. | Höherer Entwicklungs-/Betriebsaufwand; nach heutiger Nutzerklärung keine angemessene zwingende Voraussetzung für den Start. Keine ungefragte Upstream-Anfrage. |

**Empfehlung:** LubeLogger als native Administrationsoberfläche beibehalten. Für die persönliche Nutzung A plus C als einfache dokumentierte Arbeitsweise vorsehen; bei Umsetzung des automatischen Änderungsprotokolls B ergänzen und dessen tatsächlichen Funktionsumfang sichtbar benennen. Die vorgeschlagenen Anforderungen an den späteren Collector können ohne Write-Gateway erreicht werden. Kein Collector oder produktiver Logger wurde hier eingerichtet.

Das spätere technische Logbuch speichert eigene Problem-/Statusereignisse nachvollziehbar gemäß REQ-020 und REQ-043; dafür wird keine zweite vollständige Wartungsverwaltung benötigt. Die bestehende strenge ADR-0006-Gatewayempfehlung sollte mit dieser Scopeklärung überarbeitet oder als verworfene strengere Option dokumentiert werden. Diese Assessmentdatei ändert selbst keine ADRs, Produktanforderungen oder gemeinsamen Planungsdateien.
