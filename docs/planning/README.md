# Umsetzungsplanung — Wolfs Garage

Stand: 2026-10-26. **Vorgeschlagener Zielentwurf, keine Implementierung oder Betriebsfreigabe.** Auftrag: die vorhandene Discovery so weit konkretisieren, dass nach wenigen gezielten Entscheidungen kleine, prüfbare Arbeitspakete gestartet werden können. Anforderungen bleiben unverändert; weder echte Fahrzeugdaten noch externe Zugangsdaten werden benötigt.

## Bestand und Planungsannahmen

Gelesen wurden AGENTS.md, README, Anforderungen, Architektur, Roadmap, Backlog, ADRs sowie Quellen- und Laufzeitberichte. Vorhanden sind Planungsdokumente und der isolierte LubeLogger-Testsatz. Dessen **62 Checks / 51 pass / 11 gap** bleiben die bisherige Laufzeitevidenz; diese Planungsrunde führt keine neuen Laufzeitprüfungen aus.

Drei unabhängige Bereiche bearbeiten Domäne/Fälligkeiten, Infrastruktur/Security und Produkt/Bot/KI. API-Verträge, Entscheidungen und Lieferplan werden zentral abgestimmt. Die Datenhoheit wird als Zielentwurf konkretisiert, aber nicht als Nutzerentscheidung ausgegeben. Annahmen: eine Person, fünf erweiterbare Fahrzeuge, zunächst km/EUR, Docker/Proxmox, bestehendes oder separat bereitzustellendes Paperless; sämtliche Betreiberparameter bleiben offen. Spätere WP01-/WP02-Läufe und ihre Grenzen stehen in den unten verlinkten Berichten; die obige Zahl bezeichnet nur den ursprünglichen B01/B02-Stand.

## Lesepfad

| Zweck | Dokument |
| --- | --- |
| Kritischer Vergleich des heutigen LubeLogger-Kerns mit einer eigenen Lösung | [Backend-Challenge](lubelogger-vs-own.md), [vorgeschlagene ADR-0009](../adr/0009-backend-ownership-challenge.md) |
| Wenige Entscheidungen mit Empfehlung und Auswirkung | [Entscheidungsvorlage](decision-brief.md) |
| Nächste umsetzbare Schritte, Abhängigkeiten und Abnahme | [Lieferplan](delivery-plan.md) |
| Relationen, Identitäten, Revisionen und Transaktionen | [Datenmodell](domain-model.md) |
| Fälligkeiten, Historie, Prognosen und synthetische Beispiele | [Fälligkeits-Spezifikation](due-date-spec.md) |
| Offline-Rechenprüfung ausgewählter Beispiele | [Rechenprüfung](due-date-math-check.md) |
| Vorgeschlagene HTTP-/JSON-Verträge | [API- und Konsistenzvertrag](api-contracts.md), [OpenAPI-Entwurf](contracts/garage.openapi.yaml) |
| Native und ergänzende Webabläufe | [Produktabläufe](product-flows.md) |
| Bot-Dialoge und spätere KI-Grenzen | [Assistent/KI](assistant-ai-spec.md) |
| Bereitstellung, Backup, Restore, Upgrade und Störungen | [Betriebs-Runbooks](operations-runbooks.md) |
| Ein Cloudflare-Login und späterer Einrichtungsablauf | [Access-Rolloutvorbereitung](cloudflare-access-rollout.md) |
| Reproduzierbarer Bereitstellungsentwurf für den gewählten Host | [Compose-Vorlage](production-compose.md) |
| Konkrete Angriffe, Abgrenzungen und Nachweise | [Threatmodell](security-threat-model.md) |
| Übergreifende Qualitätsgates | [Qualitäts- und Abnahmeplan](quality-gates.md) |

[Prüfstand der Planungsartefakte](validation-report.md): positive/negative Payloadprüfung und lokale Referenzprüfung; keine neuen Dienste gestartet.

## Verbindlichkeit und Ausführungsgrenze

Die Produktvorgabe [ADR-0008](../adr/0008-single-user-access.md) ist durch den Nutzer geklärt; ihre technische Ausgestaltung und die übrigen ADRs bleiben vorgeschlagen. Ältere Hinweise auf separate native Logins, Web-Read-only-Nutzer und einen aus Rollenbedenken nötigen Gateway sind für das Ein-Admin-Modell überholt. Tabellen und Schemas sind Spezifikationen, keine gestarteten Services, Migrationen oder produktiven Konfigurationen. Die Garage-Routen im OpenAPI-Entwurf sind neu vorgeschlagene eigene Endpunkte und existieren noch nicht; sie sind keine behaupteten LubeLogger-/Paperless-Endpunkte.

Sichere, reversible Implementierungsarbeit kann später innerhalb ihres Auftrags erfolgen. Explizite Freigabe bleibt gemäß AGENTS.md für produktive Deployments, Cloudflare-Änderungen, Löschungen und Migrationen erforderlich. Nicht jede technische Routineentscheidung braucht eine zusätzliche Freigaberunde. Fehlende Hersteller-/HU-Quellen oder die noch ungelösten Audit-/Dokumentgates werden durch diese Planung nicht umgangen.

Praktische Fortschreibung: [WP01-Runtimebericht vom 2026-10-27](../discovery/wp01-runtime-verification.md) widerlegt die einfache native Nur-Lesen-Hypothese und konkretisiert die nächsten Optionen. Die Offline-Spezifikationsprüfungen bleiben davon getrennt.

Einzelnutzer-Fortschreibung: [ADR-0008](../adr/0008-single-user-access.md) und die aktualisierte [Entscheidungsvorlage](decision-brief.md) ersetzen ältere Rollen- und Doppelloginannahmen. LubeLogger bleibt der bevorzugte Ausgangspunkt; fremde Inhalte/Telegram bleiben unabhängig vom Weblogin zu behandeln.

Ergänzend: [WP02-Funktionsbefunde](../discovery/wp02-functional.md), [Auditumfang](../discovery/wp02-audit-assessment.md), [Access-Only-Sandbox](../discovery/single-owner-access.md), [Cloudflare-Bestand](../discovery/cloudflare-readonly-inventory.md) und [SSO-Feasibility](../discovery/access-sso-feasibility.md). Diese Befunde ändern keine bestehenden Kontorouten und sind keine Produktivfreigabe.

Ein isolierter [Browserlauf](../discovery/wp02-ui.md) prüft die native Oberfläche mit synthetischen Daten auf drei Bildschirmbreiten. Die [Offline-Rechenprüfung](due-date-math-check.md) umfasst ausgewählte Rechenschritte und belegt weder die implementierte Fälligkeitslogik noch Zustandsübergänge.
