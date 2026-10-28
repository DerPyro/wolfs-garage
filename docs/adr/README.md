# Architecture Decision Records

Stand: 2026-10-28. ADR-0001–0007 sind historische **Vorschläge**; deren LubeLogger-Zielannahmen sind für den neuen Kern durch ADR-0009 ersetzt. ADR-0009/0010 halten die entschiedene eigenständige Entwicklung und MIT fest. ADR-0008 hält die ausdrücklich geklärte Produktvorgabe fest; seine technische Umsetzung bleibt getrennt zu prüfen. Nach Entscheidung Status, Datum, Entscheider und Begründung ergänzen; verworfene Optionen nachvollziehbar erhalten. Keine Betriebsfreigabe wird vorausgesetzt.

| ADR | Thema | Offener Punkt |
| --- | --- | --- |
| [0001](0001-lubelogger-integration.md) | LubeLogger als Basis | Version, API-Abdeckung und Wiederholungsregeln |
| [0002](0002-domain-persistence.md) | Datenhoheit/eigene Persistenz | Ergänzungsmodell und Datenbank |
| [0003](0003-deployment-security.md) | Betrieb/Auth/Restore | VM/LXC, Identität und RPO/RTO |
| [0004](0004-integrations-consistency.md) | Integrationen/Konsistenz | Kalender, Dokumentrechte, Bestätigungen |
| [0005](0005-ui-ai-boundaries.md) | UI/KI | UI-Lücken, Datenschutz und Anbieter |
| [0006](0006-audit-write-boundary.md) | Kontrollierter Audit-Schreibweg | Machbarkeit nativer Read-only-Grenze, v1.0/v1.1-Umfang |
| [0007](0007-rule-ownership-transition.md) | Ein Rule-Owner und geordneter Übergang | Garage-Regelhoheit als Ziel, Cutover und Rückfall |
| [0008](0008-single-user-access.md) | Ein Cloudflare-Login, alle Zugelassenen Admin | Produktvorgabe geklärt, Origin/Dienstzugang und Umsetzung offen |
| [0009](0009-backend-ownership-challenge.md) | Eigener Garage-Kern | Entwicklung entschieden; produktive Übernahme separat |
| [0010](0010-open-source-mit.md) | Eigenständiges Open Source unter MIT | Lizenz entschieden; veröffentlichbaren Quellstand und Installation prüfen |

[Entscheidungsvorlage D01–D11](../planning/decision-brief.md) bündelt Empfehlungen und Konsequenzen. ADR-0008 hält die geklärte Produktvorgabe fest; seine technische Ausgestaltung und die übrigen ADRs bleiben Vorschläge.

Vor Umsetzung Nachweise im [Backlog](../backlog.md) abarbeiten. Betreiberparameter dürfen offen bleiben, müssen vor dem davon abhängigen Schritt entschieden sein.
