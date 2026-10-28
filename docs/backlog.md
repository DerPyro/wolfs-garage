# Priorisierter Backlog nach Phase-0-Discovery

Stand: 2026-10-27. Der Nutzer hat Einzelnutzerbetrieb mit einem Cloudflare-Login und Adminrechten für alle zugelassenen Webnutzer festgelegt. B01/B02 haben nun eine Testbaseline und dokumentierte Laufzeitevidenz; die offenen Restabnahmen sind unten und im Prüfbericht ausgewiesen. Alle produktiven Umsetzungspakete bleiben **offen**. P0 blockiert die jeweils abhängige Implementierung/Freigabe; spätere Pakete sind keine aktuelle Implementierungsbeauftragung. D = Entscheidung, S = isolierter Nachweis, I = spätere Implementierung. Zuordnung entspricht AGENTS/Roadmap und erteilt keine Deploymentfreigabe.

| ID / Priorität / Typ | Paket und Verantwortungsbereich | Abhängigkeit / Abnahmekriterium |
| --- | --- | --- |
| B01 / P0 / D | Integration: Testbaseline festgelegt | v1.7.4/linux-amd64 mit Digest, API-Katalog und MIT-Text in [target.lock.json](../tests/lubelogger/target.lock.json); direkte Paketlizenzen inventarisiert, vollständige Distributions-SBOM offen |
| B02 / P0 / S | Integration/Quality: Laufzeitprüfung ausgeführt, Restabnahmen offen | [62 Checks: 51 pass / 11 gap](discovery/lubelogger-runtime-verification.md); erweiterte Matrix-Reste insbesondere Einheiten/visuelle UI/Webhook-Prozessabbruch bleiben offen; kein Produktiv-Gate bestanden |
| B03 / P0 / S | Quality/Domain: Änderungsprotokoll prüfen | [WP02-Audit](discovery/wp02-audit-assessment.md): aktuelle Fahrzeughistorie ersetzt alte/gelöschte Belegstände; Webhook enthält Aktivität, aber kein dauerhaftes vollständiges Journal. Ein kleines optionales Aktivitätsjournal prüfen; REQ-043 und Problemhistorie REQ-020 bleiben offen |
| B04 / P0 / D+S | Domain: Regeln und Kalendergrenzen | REQ-006/010/011/012, ADR-0001/0004; ein Regel-Owner, bestätigte HU-Quelle/Ausnahmen, 30-Tage-Alternative entscheiden |
| B05 / P0 / D | Infrastruktur: Host, Access, Secret-/Backupkonzept | ADR-0008: genau ein interaktives Cloudflare-Login, danach Admin; VM/LXC, Origin-/Dienstzugang, Ressourcen, RPO/RTO/Retention/Offsite und Restore-Verantwortung festlegen |
| B06 / P0 / S | Infrastruktur/Quality: isolierte Auth-/Restore-Abnahme | B01/B05; Negativtests, Daten/Anhänge/Schlüssel/IDs wiederherstellen, keine externen Seiteneffekte |
| B07 / P0 / S | UI/Domain: Basisverwaltung und Kosten abnehmen | [WP02 Funktion](discovery/wp02-functional.md): fünf Autos, Teileentnahme und ausgewählter Jahreskostenreport geprüft; überfällige Fahrzeugglocke bei 0 km fehlt. Responsive Browser-/Priorisierungsprüfung und echte Zahlungshistorie bleiben separat |
| B16 / P0 / S | Zugang zu App und Dokumenten über Cloudflare absichern | Trennung zwischen angemeldeten Admins ist kein Produktziel. Nicht zugelassene oder nicht angemeldete Aufrufe dürfen Web, API und Dokumente nicht über Cloudflare oder direkte Originwege umgehen; JWT-/Origin-/Dienstzugang und Recovery testen |
| B17 / P0 / D+S | Domain: Provider-Datums-/Schwellwertgrenzen | B02 zeigt DueDays-Off-by-one, GET-Autorefresh und Threshold-Leak; eigene LocalDate-Berechnung, Autorefresh aus und Schwellen-Hoheit festlegen; B04/ADR-0004 |
| B19 / P0 / D+S | Domain/UI: Vorgangskosten und Zahlungen abgrenzen | WP02 bestätigt getestete Jahresgruppierung/Korrektur, aber Lagerkauf wird im gewählten Report nicht als Cash-Zahlung erfasst. Zahlungsdatum/-status, alternative native Erfassung und REQ-015 weiterhin prüfen |
| B18 / P1 / D+S | Implementierungsverträge vorbereitet, Umsetzung offen | [Planungsindex](planning/README.md), Domainmodell und eigene OpenAPI-/JSON-Schemas; 34 lokale Payloadprüfungen/56 Referenzen geprüft, keine Server-Conformance oder akzeptierte ADRs |
| B08 / P1 / I | Infrastruktur: v1.0-Basis später umsetzen | B01–B07/B16/B17/B19; reproduzierbare Konfiguration, gepinnte Images, Auth, Backup; Deployment nur mit expliziter Freigabe |
| B09 / P1 / D+S | Integration: Paperless-Installation und Rechte | Installationsversion/API-Aushandlung, eingeschränktes Konto, Dokument-IDs, Link-/Entzugstests; keine Duplikate |
| B10 / P1 / D+I | Backend/Domain: v1.1 Garage-Modell | ADR-0002 und B04; Datenbank/ER/Retention, Problem-/Ereignisverknüpfung, Severity/Status, Audit und Outbox |
| B11 / P1 / I | Bot: Telegram und Dialoge | B10; ID-Allowlist, Inbox, Vorschau/Bestätigung, Wiederholung/Ablauf, unbekannte Updatearten, Rechte und unklare Zustellung testen |
| B12 / P1 / I | Domain/Integration: Fristen, Prognose, Kalender | B04/B10/B11; tägliche Berlin-Prüfung, konfigurierte Regeln, Deduplizierung, Quellennachweis, Kalender-ID/OAuth/ETags und Ausfallnachholung |
| B13 / P1 / I | UI: belegte Lücken und Logbuch ergänzen | B07/B10; keine doppelte Stammdatenverwaltung, kritische Probleme sichtbar; REQ-022 Warnung mit geprüften Regeln |
| B14 / P2 / D | KI: Anbieter/Datenschutz/Budget/Quellen | ADR-0005; freigegebene Daten, Region/Retention, Kostenlimit, Modelloptionen und Sicherheitsgrenzen entscheiden |
| B15 / P2 / I | KI: v2.0 Diagnose/OBD/Recherche | B10/B14; Fakten/Vorschläge trennen, alternative Ursachen, Rückfragen, OCR-Bestätigung, Fehlercodeverlauf und Prompt-Injection-Tests |

## Vollständige Anforderungszuordnung

Jede ID hat ein Folgepaket; Zuordnung bedeutet keine Erfüllung. Basisfunktionen bleiben bis B02/B07 unter Laufzeitvorbehalt.

| Anforderungen | Paket(e) / Phase |
| --- | --- |
| REQ-001–003 | B02/B07/B08 Basis, Telegram-Erfassung B11 |
| REQ-004–005 | B04/B12 v1.1; Herstellerintervalle für v1.0 bereits B07 quellenbasiert manuell |
| REQ-006–008 | B02/B04/B07/B08 v1.0 |
| REQ-009–011 | B04/B12 v1.1, Kalender-30-Tage-Konflikt offen |
| REQ-012–015 | B02/B04/B07/B08/B19; Bot-/Fristfortschreibung B12; tatsächliche Zahlungen separat abnehmen |
| REQ-016 | B07: Tankvorgänge bleiben außerhalb des MVP-Abnahmekatalogs |
| REQ-017–022 | B10/B11/B13 v1.1 |
| REQ-023–025 | B07/B08 v1.0; belegte Erweiterung B13 |
| REQ-026–027 | B07 Dokument-Fallback v1.0, B09/B16 sichere Referenzintegration |
| REQ-028 | B05/B06/B08; Cloudflare-Änderung benötigt gesonderte explizite Freigabe |
| REQ-029–032 | B10/B11/B12 v1.1 |
| REQ-033–037 | B14/B15 v2.0 |
| REQ-038 | B15: Videoanalyse ausgeschlossen, normale Fotos kein Muss |
| REQ-039–042 | B05/B06/B08/B16; Cloudflare-Login und Adminzugriff mit kontrolliertem Origin-/Dienstzugang |
| REQ-043 | B03/B10; gefordertes Änderungsprotokoll prüfen, keine weitergehende Auditgarantie unterstellen |
| REQ-044 | B11/B14/B15 |
| REQ-045–046 | B02/B06/B10/B12/B17; Zeitzone und isolierte Ausfälle |
| REQ-047 | B01/B02/B09/B10/B18; Vertragsentwurf in Discovery, ausführbares Schema vor Integration festhalten |
| REQ-048 | B02/B06/B11/B12/B18; B02-Teile ausgeführt, Bot-/Fach-/Persistenztests geplant; Offline-Schemas sind keine Integrationstests |
| REQ-049 | B04/B10/B12/B13/B17; konfigurierbare Regeln/Schwellwerte/Schweregrade |

## Nächster sinnvoller Auftrag

Nach Klärung des Ein-Admin-Modells: LubeLogger-Basisoberfläche, Einheiten, Teile/Jahreskosten und bestehendes Änderungsprotokoll isoliert prüfen; Datumslogik und Cloudflare-/Originweg separat ausarbeiten. B05/B06 benötigen weiterhin Betreiberparameter und Host-/Restore-Nachweise. Produktive Dienste erst nach den zugehörigen Nachweisen; Veröffentlichung, Cloudflare-Änderungen, Migrationen und Löschungen weiter nur nach expliziter Freigabe gemäß AGENTS.md.

## Weiterführende Umsetzungsplanung

[Entscheidungsvorlage](planning/decision-brief.md), [Lieferplan WP01–WP12](planning/delivery-plan.md), [Qualitätsgates](planning/quality-gates.md) und [Offline-Prüfstand](planning/validation-report.md) konkretisieren die Pakete. Empfehlungen bleiben vorgeschlagen; sie ändern weder Produktanforderungen noch Freigabegrenzen.

## WP01-Machbarkeit — 2026-10-27

[Runtimebericht](discovery/wp01-runtime-verification.md): 42 Checks (28 pass / 14 gap), beide Testinstanzen gestoppt. [Statisches Inventar](../tests/wp01/route-inventory.json): 329 Deklarationen/35 Dateien, keine vollständig geprüfte Routingallowlist. WP01 liefert das Machbarkeitsergebnis; es schließt B03/B16 nicht als Sicherheitsabnahme ab. Nach der Klarstellung des Nutzers ist eine eigene Oberfläche zur Erzwingung von Read-only-Rollen nicht erforderlich. WP02 prüft die vorhandene Basisoberfläche und fachlichen Restfälle; eine eigene Erweiterung bleibt auf belegte funktionale Lücken beschränkt.

## Ein-Admin-Fortschritt — 2026-10-27

Der Nutzer bestätigte ein Cloudflare-Login und Adminrechte für zugelassene Webnutzer. [ADR-0008](adr/0008-single-user-access.md) hält die Vorgabe fest. [Lokaler Auth-off-Test](discovery/single-owner-access.md): neun Checks bestanden, ohne Cloudflare; jeder interne Originzugriff ist dabei Root. [Funktion](discovery/wp02-functional.md): 19 Checks, 14 pass/5 gap. [Audit](discovery/wp02-audit-assessment.md): 12 Checks bestanden, Grenzen der verfügbaren Historie dokumentiert. Die [Cloudflare-Bestandsaufnahme](discovery/cloudflare-readonly-inventory.md) war ausschließlich lesend. Keine dieser Prüfungen ist ein produktiver Access-/Origin-/Browserabnahmetest oder setzt die verbleibenden fachlichen Anforderungen außer Kraft.
