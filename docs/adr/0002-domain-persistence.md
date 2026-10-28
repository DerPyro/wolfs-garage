# ADR-0002 — Eigene Metadaten mit eindeutiger Datenhoheit

Status: **Vorgeschlagen** · Datum: 2026-10-26 · Entscheidung: offen

## Kontext

Technisches Logbuch mit unveränderlicher Ereignishistorie, Bestätigungen, Audit, Dokumentreferenzen und zuverlässige Integrationszustände sind als vollständiger LubeLogger-Vertrag nicht nachgewiesen. Sie dürfen nicht als Freitext-Konvention ohne Integrität modelliert werden.

## Empfehlung

Für v1.1 ein modularer Spring-Boot-Garage-Service mit eigener relationaler Persistenz; PostgreSQL ist der Vorschlag für Transaktionen, Constraints, Outbox und Job-Koordination. Keine Microservices pro Adapter. v1.0 benötigt diesen Service noch nicht.

Datenhoheit:

| Daten | Führendes System |
| --- | --- |
| Fahrzeuge, Kilometerstände, Reparaturen, Kosten | LubeLogger |
| Originaldokumente und deren Zugriffsrechte | Paperless-ngx, sofern verfügbar |
| Probleme, Severity/Status, Ereignisse, Fallverknüpfungen | Garage |
| Bestätigungsentwürfe, Audit, Outbox, API-Operationsstatus | Garage |
| Kalender-Sync-Zuordnung, Reminder-Versandjournal | Garage |
| Wartungs-/HU-Regeln, Quellen und nächste Fälligkeit | Vor Implementierung nach ADR-0001 eindeutig festzulegen |
| Kalenderereignis | Abgeleitete Projektion der bestätigten Fälligkeit |

Garage benutzt eigene stabile UUIDs plus Provider-ID-Zuordnungen. Keine dauerhaft zweite editierbare Fahrzeug-/Kostenkopie. Caches erhalten Quelle, Lesestand und Ablaufzeit; veraltete Werte werden gekennzeichnet. Problemlog ergänzt Ereignisse; Korrekturen referenzieren Vorgänger, anstatt Historie still zu überschreiben. Aufbewahrung und administrative Löschung sind separat festzulegen, bevor personenbezogene Daten gespeichert werden.

## Alternativen und Folgen

SQLite wäre für eine Person einfacher und bleibt möglich, muss aber identische Transaktions-/Parallelitätsanforderungen erfüllen. Alles in LubeLogger-Zusatzfeldern würde Dialogzustände und unveränderliche Historie nicht ausreichend absichern. PostgreSQL bedeutet zusätzliche Backup- und Betriebsverantwortung; keine vorgezogene Bereitstellung.

## Offene Entscheidung und Nachweise

REQ-043 fordert weiterhin ein Änderungsprotokoll für Wartung und Logbuch; das Garage-Audit erfasst nur eigene Schreibwege. Die vorhandene native Funktionalität und ihre Grenzen sind zu prüfen (B03). Ein lückenloses Vorher-/Nachher-Audit sämtlicher LubeLogger-Webänderungen ist eine frühere technische Interpretation, keine zusätzlich bestätigte Nutzeranforderung. Webhooks/Snapshots dürfen dennoch nicht als vollständiges Audit ausgegeben werden.

Datenbank, Aufbewahrung, endgültiges ER-Modell, Regeln zur Kilometerkorrektur und Reminder-Hoheit festlegen. Transaktionsgrenzen, Lösch-/Verwaisungsfälle, Restore von Provider-Zuordnungen und parallele Bestätigungen mit synthetischen Daten nachweisen. Details: [Integrationsverträge](../discovery/integration-contracts.md).
