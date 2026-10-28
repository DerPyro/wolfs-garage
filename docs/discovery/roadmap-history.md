# Historical roadmap and implementation log

Archived on 2026-10-28 when the standalone alpha source was prepared for publication. This is historical evidence of the earlier discovery and LubeLogger integration, not the current release plan. Statements marked open or proposed below retain their original context and may be superseded by [ADR-0009](../adr/0009-backend-ownership-challenge.md) and [ADR-0010](../adr/0010-open-source-mit.md). The current plan is [docs/roadmap.md](../roadmap.md).

# Roadmap

## Eigenständige Open-Source-Anwendung — 2026-10-28

Nutzerentscheidung: eigener Datenkern und MIT-Lizenz. Die folgenden älteren Phase-0-/LubeLogger-Einträge bleiben historische Evidenz; der neue Kern hat keine LubeLogger-Laufzeitabhängigkeit. Historische Betriebsangaben sind anonymisiert.

- [x] Entscheidung zu eigener Datenhoheit und MIT dokumentiert: [ADR-0009](../adr/0009-backend-ownership-challenge.md), [ADR-0010](../adr/0010-open-source-mit.md).
- [x] Erster isolierter Kern mit Fahrzeuganlage/-korrektur, unabhängiger Fahrbereitschaft/offenen Punkten, Kilometerständen, Wartungs-/Reparaturbelegen, explizitem atomarem Punktabschluss und lesbarem Verlauf.
- [x] Eigene SQLite, Revisionen, wiederholbare Record-/Kilometerbefehle, konsistentes Backup und synthetischer isolierter Restore. [Nachweis des ersten Kerns](../discovery/standalone-core.md): 24 Backendprüfungen, Frontend-Mocks, Browserablauf und isolierter Containerstart.
- [x] Eigenständige Oberfläche und generischer Docker-/Compose-Einstieg ohne feste Betreiber-Domain; Anleitung, MIT-Lizenz, Drittanbieterhinweise und Beitragsregeln vorbereitet.
- [ ] Vor öffentlicher Veröffentlichung den tatsächlich freizugebenden Quellstand samt Historie abschließend prüfen und veröffentlichen.
- [ ] Nutzbare nächste Ausbaustufe: Belegkorrekturen, vollständige Verlauf-/Kilometerbedienung, Aufgaben mit Fälligkeiten und geprüfte wiederkehrende Regeln.
- [ ] Dokumente/Uploads bzw. Paperless-Referenzen und Teile-/Kostenauswertungen gemäß Anforderungen ausbauen.
- [ ] Datenbank-Upgrades und zukünftige Versionswechsel nachweisen; aktuelle Schema-1-Initialisierung ist kein Upgradepfad.
- [ ] Vor produktiver Übernahme kompletten Altbestand inventarisieren, Sicherung und isolierten Import vergleichen, Schreibumschaltung und Rückweg festlegen.


## Phase 0 — Discovery und Architektur
LubeLogger und Paperless-API prüfen; Datenmodell, Deployment-Grenzen, Backups, Authentifizierung und Integrationsvertrag festlegen. Ergebnis: ADRs, Compose-Entwurf, priorisierter Backlog.

### Stand 2026-10-26

Phase 0 ist gestartet; die Dokumentationsartefakte liegen zur Prüfung vor:

- [x] [Bestandsaufnahme und Annahmen](../discovery/phase-0.md), unabhängige Quellen-/Integrationsprüfungen.
- [x] [Architekturvorschlag](../architecture.md), [vorgeschlagene ADRs](../adr/README.md), [Compose-Design](../../deploy/compose.design.yaml), [priorisierter Backlog](../backlog.md).
- [ ] Betreiberentscheidungen und ADR-Annahme; keine Entscheidungen stillschweigend als akzeptiert markieren.
- [ ] Isolierte API-, Rechte-, Regel-, UI- und Restore-Nachweise gemäß [Abnahmeplan](../discovery/validation.md).
- [ ] Blocker klären: API-Rekurrenz, vollständiges Audit auch bei LubeLogger-UI-Änderungen, 30-Tage-Kalendererinnerung, Host/Backup-Ziele.

Phase 0 ist damit noch nicht als technische Implementierungsfreigabe abgeschlossen. Im ursprünglichen Discovery-Schritt wurden keine Dienste gestartet.

### B01/B02 — lokale Erprobung 2026-10-26

- [x] Ziel v1.7.4/linux-amd64 mit [Image-Digest/API-Katalog/Lizenztext](../../tests/lubelogger/target.lock.json) fixiert; direkte Paketlizenzen inventarisiert.
- [x] [Reproduzierbarer Testsatz](../../tests/lubelogger/README.md) ausgeführt: [62 Checks, 51 pass / 11 gap](../discovery/lubelogger-runtime-verification.md), inklusive Restore in zweiter isolierter Instanz; beide Instanzen gestoppt.
- [ ] B02-Restfälle laut Prüfbericht, vollständiges Distributionsinventar und visuelle B07-Abnahme.
- [ ] Neue Blocker B16/B17: Dokument-Objektberechtigung und Datums-/Schwellwertsemantik entscheiden/nachweisen; ADRs weiterhin vorgeschlagen.

Keine produktiven Ressourcen oder Cloudflare-Einstellungen verändert. Die Erprobung gibt v1.0 nicht automatisch frei.

### Vertiefte Umsetzungsplanung

[Planungsindex](../planning/README.md), [Entscheidungsvorlage D01–D11](../planning/decision-brief.md) und [Lieferplan WP01–WP12](../planning/delivery-plan.md) konkretisieren Datenmodell, Fachregeln, Web/Bot, Verträge und Betrieb. 27 deterministische Fachvektoren sind spezifiziert; eigene JSON-/OpenAPI-Entwürfe mit 34 positiven/negativen Payloadprüfungen und 56 lokalen Referenzen offline geprüft. Das sind keine neuen Anwendungstests.

ADR-0006/0007 bleiben vorgeschlagen. Vollständiges Audit kann einen früheren kleinen Garage-Schreibpfad erfordern; dieser Roadmap-Scope ist noch zu entscheiden. Ebenso offen bleiben dokumentbezogene Autorisierung, Übergang der Regelhoheit, Kalender30 und die Abgrenzung echter Zahlungen von Vorgangskosten. Keine Dienste in dieser Planungsrunde gestartet.

### WP01 — Machbarkeitsprüfung 2026-10-27

- [x] [42 isolierte Checks](../discovery/wp01-runtime-verification.md), 28 pass / 14 gap, anschließend beide Instanzen gestoppt; keine Produktivänderung.
- [x] Quellinventar mit 329 Action-Deklarationen erstellt; nicht als vollständig geprüfte Runtimeallowlist ausgegeben.
- [x] Native Read-only-Hypothese anhand persistierender View-GETs/Taxfortschreibung widerlegt; Datei-Lücke nach Entzug/Restore bestätigt.
- [x] Sehr enge Positivliste mit zwei API-Leseoperationen und 31 abgewiesenen Varianten demonstriert.
- [ ] Vollständiger Auditpfad, schützende Origin-/Dateiabgrenzung und Browser-/UI-Abnahme weiterhin offen. Testproxy ist keine produktive Lösung.
- [ ] Empfehlung eines früheren schmalen Garage-Zugangs versus Upstream-/Scopealternative entscheiden; ADRs bleiben vorgeschlagen.

### Geklärter Einzelnutzerbetrieb — 2026-10-27

[ADR-0008](../adr/0008-single-user-access.md): Cloudflare Access als einziges gewünschtes interaktives Login; alle zugelassenen Webnutzer erhalten Adminrechte. LubeLogger mit vorhandener Oberfläche ist wieder bevorzugter v1.0-Ausgangspunkt. Eine zusätzliche eigene Oberfläche oder ein Gateway ausschließlich für Rollen-/Fahrzeugtrennung ist nicht erforderlich. Die WP01-Testdaten bleiben gültig, ihre frühere rollenbezogene Priorisierung ist für diesen Produktscope überholt.

Fachliche Nachweise für Daten, Teile, Kosten, Änderungsprotokoll, Fälligkeiten und Wiederherstellung laufen weiter. Origin-/Access-Absicherung und der separate Telegram-Zugang bleiben zu prüfen. Bestehende frühere Hinweise auf eine verpflichtende zusätzliche interaktive Anmeldung oder auf eine native Read-only-Rolle werden durch diese Klarstellung ersetzt. Keine Cloudflare-Änderung oder produktives Deployment aus dieser Klarstellung ableiten.

### Ein-Admin-Fortschritt mit synthetischen Daten

- [x] [Auth-off-Sandbox](../discovery/single-owner-access.md): neun Checks; LubeLogger ohne zweite Anmeldung möglich, intern jeder Zugriff Root. Keine Cloudflare-Konfiguration getestet.
- [x] [Basisfunktionen](../discovery/wp02-functional.md): 19 Checks, 14 pass / fünf bekannte Grenzen; fünf Fahrzeuge, Teileentnahme und ausgewählter Jahreskostenbericht nachgewiesen.
- [x] [Änderungshistorie](../discovery/wp02-audit-assessment.md): 12 lokale Checks; native Historie enthält aktuelle Belege, Webhooks bieten Ereignisse mit Zustell-/ID-Grenzen. REQ-043/020 nicht als erledigt markiert.
- [x] [Cloudflare-Bestand](../discovery/cloudflare-readonly-inventory.md) nur lesend geprüft; bestehende Apps/Tunnel/Zonen nicht verändert.
- [x] [Native Browseroberfläche](../discovery/wp02-ui.md) mit fünf Testfahrzeugen auf drei Bildschirmbreiten geprüft; Tastaturfokus und eine abgeschnittene Datumszelle bleiben offen.
- [x] [Fälligkeitsbeispiele](../planning/due-date-math-check.md) teilweise offline nachgerechnet: 34 Vergleiche bestanden, keine Anwendungs- oder Zustandsprüfung.
- [x] [Access-Rollout](../planning/cloudflare-access-rollout.md) mit Reihenfolge und Abnahmetests vorbereitet; keine Einrichtung ausgeführt.
- [ ] Tatsächlicher Access-Login, vollständige Origin-Abschirmung und Dienstzugänge abnehmen; zwischenzeitlich eingerichtete Ressourcen siehe Bereitstellungsstand unten.
- [ ] Einheitenumrechnung, Fahrzeugwarnung bei unbekanntem/0-km-Stand, Zahlungshistorie, gewünschtes Änderungsprotokoll und gesamter Wiederherstellungsweg abnehmen.

### Bereitstellung auf Nutzerauftrag

- [x] Eigenen dedizierten Proxmox-LXC gestartet, Docker, LubeLogger und einen separaten Cloudflare-Tunnel eingerichtet; `garage.example.invalid` leitet ohne Anmeldung zu Cloudflare Access. Details und Prüfgrenzen im [Bereitstellungsbericht](../discovery/deployment-2026-10-27.md).
- [ ] Erfolgreichen persönlichen OTP-Login und Bedienung nach Anmeldung vom Betreiber bestätigen lassen.
- [ ] Regelmäßiges Backup und Wiederherstellung nachweisen; die bestehenden fachlichen und Sicherheitsprüfungen bleiben offen.

### Eigene Oberfläche

- [x] Eine reduzierte, responsive Fahrzeugübersicht und einen Leseadapter mit synthetischen Tests vorbereitet; Einzelheiten und Grenzen im [Dashboard-Einführungsplan](../planning/dashboard-rollout.md).
- [x] Produktive Einführung nach ausdrücklicher Freigabe: bestehende Access-Policy erhalten, eigener Tunnel auf den Router umgestellt, vorhandene Datenvolumes belassen. [Prüfstand](../discovery/deployment-2026-10-27.md#dashboard-update-am-2026-10-28).
- [ ] Persönlichen Zugriff auf die neue Startseite, native Verwaltung und Datenänderungen im Browser bestätigen; Fahrzeuge und Einträge werden vorerst weiterhin in LubeLogger verwaltet.
- [x] [Fahrzeugtypen, Markenlogos und Kennzeichen](../planning/vehicle-types-rollout.md) umgesetzt, mit synthetischen Daten geprüft und nach Freigabe eingeführt.
- [x] [Fahrbereitschaft und offene Punkte](../planning/vehicle-status-rollout.md) lokal implementiert und mit synthetischen Daten geprüft.
- [ ] Nach Freigabe produktiv einführen, die ausdrücklich genannten Zustände übernehmen und Statusspeicher sowie Wiederherstellung absichern.

### Backend-Challenge — 2026-10-28

- [x] [LubeLogger gegen eigenen Kern](../planning/lubelogger-vs-own.md) anhand des aktuellen Codes, bestehender Testnachweise, offizieller Quellen und dreier unabhängiger Gegenprüfungen bewertet. Keine neue Laufzeit- oder Produktivprüfung.
- [x] [ADR-0009](../adr/0009-backend-ownership-challenge.md) als Vorschlag dokumentiert: eigener Kern als zu prüfende Zielrichtung bei vollständiger eigener Bedienung; LubeLogger bleibt für die laufende Verwaltung führend.
- [ ] Erstumfang und Datenhoheit entscheiden; vorgeschlagenen isolierten Ablauf samt Export/Restore gegen die Integrationsvariante nachweisen. Originalanforderungen bleiben bis zur ausdrücklichen Scopeentscheidung bestehen.
- [ ] Vor einer etwaigen Ablösung vollständigen Bestand inventarisieren, Import isoliert prüfen und späteren Schreibwechsel/Rückweg planen. Der Nutzerauftrag zur Challenge ist keine Migrations- oder Ablösefreigabe.

## Version 1.0 — Basisverwaltung
Eigene selbst betreibbare Anwendung unter MIT mit Fahrzeugstammdaten, Kilometerständen, Aufgaben/Fälligkeiten, Wartungen/Reparaturen, Kosten, technischer Historie, Dokumentzuordnung und geprüftem Backup/Restore. Docker als generischer Einstieg; Cloudflare Access im Referenzdeployment. Kontrollierte Übernahme bestehender Daten gesondert vorbereiten.

## Version 1.1 — Assistent und Integrationen
Telegram-Adapter des eigenen modularen Dienstes; ID-Allowlist; natürlichsprachliche Erfassung mit Bestätigung; 30-Tage-Erinnerungen; prognostizierte Kilometerfälligkeiten; Google-Kalender-HU-Synchronisierung; Paperless-Verknüpfung; technisches Logbuch und Schweregrade.

## Version 2.0 — KI-Diagnose
Fahrzeughistorienbasierte interaktive Diagnose; Recherche mit Quellen; Screenshot-Erkennung für Fehlercodes; Verknüpfung wiederkehrender Probleme; Statusverfolgung und Sicherheitswarnungen.

## Später / Nicht-Ziele
OBD-Live-Anbindung, automatische Telemetrie, Tankprotokoll als Pflichtfeature, Mehrbenutzerbetrieb, Videoanalyse.

## Codex-Arbeitspakete
1. Architektur-/Integrationsprüfung (zuerst, blockiert Implementierung).
2. Infrastructure Agent: Compose, Cloudflare-Konzept, Secrets, Backup.
3. Domain Agent: Datenmodell, Wartungs- und Fälligkeitslogik.
4. Integration Agent: LubeLogger, Paperless, Google Calendar.
5. Bot Agent: Telegram, Dialoge, Authentifizierung.
6. Quality Agent: Tests, Security-Review, Dokumentation.

Parallelisierung erst nach geklärten Schnittstellen; jeder Agent arbeitet in abgegrenztem Bereich.
