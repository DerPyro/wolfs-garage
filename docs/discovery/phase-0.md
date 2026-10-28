# Phase 0 — Bestandsaufnahme und Prüfplan

Stand: 2026-10-26. Ausgangspunkt: `3135c0f8c59fcd81cd62b99bf13f93f4a0cc5177` (`main`).

## Bestand und Umfang

Gelesen: `AGENTS.md`, `README.md` und sämtliche ursprünglichen Dateien unter `docs/`: `requirements.md`, `architecture.md`, `roadmap.md`. Das Repository enthält nur diese Planungsunterlagen; Anwendung, Laufzeitkonfiguration, Tests und Homelab-Inventur fehlen. Die Produktanforderungen bleiben unverändert.

Phase 0 liefert Empfehlungen, einen nicht betriebsfähigen Compose-Entwurf, vorgeschlagene ADRs und einen priorisierten Backlog. Keine Container, Datenbanken, produktiven Integrationen, Cloudflare-Konfigurationen, Migrationen oder Veröffentlichungen werden angelegt.

## Arbeitsplan

1. Bestand, Anforderungen und Phasengrenzen erfassen.
2. Unabhängige Prüfung von LubeLogger, Infrastruktur/Security sowie Paperless/Integrationsverträgen; gemeinsame Architekturdateien bleiben beim koordinierenden Agenten.
3. Funktionsabdeckung, Datenhoheit und Sicherheitsgrenzen zusammenführen; Alternativen und offene Entscheidungen als ADRs dokumentieren.
4. Dokumentation, Quellen, Entwurf und Anforderungsabdeckung prüfen; ausstehende Laufzeitnachweise als Kriterien für die Folgephase festhalten.

## Annahmen — zu bestätigen

- Fünf Fahrzeuge, eine autorisierte Person, metrische Kilometerstände und EUR; ausschließlich synthetische Daten für spätere Erprobungen.
- Docker auf Proxmox; VM/LXC, CPU-Architektur, Ressourcen und Backupziel unbekannt.
- Paperless-ngx möglicherweise vorhanden; URL, Version und Dokumentrechte unbekannt. Fehlen/Ausfall darf Basisverwaltung nicht blockieren.
- Kalender-ID und Telegram-ID noch nicht benannt; Zugangsdaten und Anbieterressourcen werden jetzt nicht benötigt.
- Spring Boot stammt aus der Roadmap. Datenbank und eigene Weboberfläche bleiben Vorschläge.
- RPO/RTO, Speicherbedarf, Betriebsbudget und KI-Datenschutzfreigabe offen.

## Ergebnisse und Evidenzgrenzen

- [LubeLogger](lubelogger.md): API, Lizenz, Modellabdeckung, Lücken.
- [Integrationsverträge](integration-contracts.md): Paperless, Kalender, systemübergreifende Abläufe.
- [Betrieb und Sicherheit](operations-security.md): Deployment, Identitäten, Backup/Restore.
- [Architektur](../architecture.md), [ADRs](../adr/README.md), [Backlog](../backlog.md), [Abnahmeplan](validation.md).
- [Compose-Design](../../deploy/compose.design.yaml), [Variablenvorlage](../../deploy/.env.example).

Quellen- und Quellcodeprüfung beweisen keine erfolgreiche Integration einer konkreten Installation. Keine privaten APIs, Test-Schreibvorgänge oder Wiederherstellungen wurden ausgeführt. Versionen/Images sind vor Implementierung festzulegen und Verträge isoliert zu prüfen. Alle ADRs sind **Vorgeschlagen**; Nutzerentscheidungen werden nicht vorweggenommen.

## Fortschreibung B01/B02

Der Absatz zur fehlenden Laufzeitevidenz beschreibt den ursprünglichen Discovery-Schritt. Die nachfolgend beauftragte [isolierte Erprobung](lubelogger-runtime-verification.md) ist jetzt ausgeführt (62 Checks, 51 pass/11 gap). Zwei synthetische Testinstanzen wurden gestartet und wieder gestoppt; kein produktiver Dienst implementiert. Ziel-/Digestdatei, API-Katalog und reproduzierbarer Testtreiber liegen unter `tests/lubelogger/`. Betreiberentscheidungen, Produktivabnahme und die im Bericht ausgewiesenen Restfälle bleiben offen.
