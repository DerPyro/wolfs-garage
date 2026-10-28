# Entscheidungsvorlage mit empfohlenem Ziel

Stand: 2026-10-27. [ADR-0008](../adr/0008-single-user-access.md) hält die geklärte Produktvorgabe fest; die konkrete technische Ausgestaltung und die übrigen Empfehlungen bleiben vorgeschlagen. Grundlage: [B01/B02-Ergebnisse](../discovery/lubelogger-runtime-verification.md). Die Entscheidungsvorlage bündelt offene Punkte; sie ist keine erneute Sammlung von Zugangsdaten und blockiert reine Planungsarbeit nicht.

## Entscheidungen vor den jeweils abhängigen Schritten

| ID / Zeitpunkt | Empfehlung | Alternative / Konsequenz | Nachweis und betroffene ADRs |
| --- | --- | --- | --- |
| D01 / vor v1.0-Betrieb | Dedizierte Proxmox-VM als Docker-Host | Unprivilegierter LXC bei nachgewiesenem Nesting/Backup/Restore; Ressourcen und bestehendes Homelab können dafür sprechen | Hostinventar und isolierter Restore; ADR-0003 |
| D02 / vor Dokumentintegration | LubeLogger-Anhänge für den einen Admin nutzen; bestehende Paperless-Dokumente bevorzugt referenzieren, sofern vorhanden | Paperless-Integration weiterhin prüfen; es ist keine per-Fahrzeug-Rollenbarriere zwischen angemeldeten Admins nötig | B16: Cloudflare-/Originabdeckung sämtlicher Dokumentpfade; ADR-0008 |
| D03 / vor v1.0-Abnahme | Vorhandene LubeLogger-Oberfläche als Ausgangspunkt; tatsächlich verfügbares Änderungsprotokoll und Logbuchfunktion gegen REQ-043/020 prüfen | Bei belegter fachlicher Lücke gezielt ergänzen; ein Read-only-Gateway nur für verschiedene Adminrechte entfällt | B03; ADR-0006 historischer Entwurf, [ADR-0008](../adr/0008-single-user-access.md) aktuelle Produktvorgabe |
| D04 / vor Assistent/automatischer Fristfortschreibung | Garage wird alleiniger Regel-Owner; LL erhält höchstens konkrete nächste Fälligkeiten | Weiter native Regeln, dann Bot-Fristpflege bis vollständiger öffentlicher API blockiert; kein doppelt laufender Scheduler | [ADR-0007](../adr/0007-rule-ownership-transition.md), B04/B17; nachvollziehbarer Übergang, keine aktuelle Migration |
| D05 / vor Persistenzimplementierung | Ein modularer Spring-Boot-Service plus eigene PostgreSQL-Persistenz | SQLite für eine Person möglich, falls dieselben Atomizitäts-/Concurrency-/Backupverträge erfüllt; kein verteiltes Servicesystem erforderlich | ADR-0002, Transaktions-/Outbox-Prototyp; Versionen separat fixieren |
| D06 / vor Kalenderintegration | Ein HU-Haupttermin plus separates sichtbares 30-Tage-Ereignis; nativer 7-Tage-Reminder am Haupttermin | Explizite Anforderungsänderung auf ≤28 Tage. Telegram allein erfüllt REQ-011 nicht | ADR-0004; eigene Kalender-ID, Zustelltest, Zeitzone und manuelle Konflikte |
| D07 / vor Veröffentlichung | Ein interaktives Cloudflare-Access-Login, danach volle Adminrechte; Webzugang und Origin abschotten | LubeLogger-Auth deaktiviert mit isoliertem Origin oder transparentes SSO; Umsetzung und Dienstzugang sind offen | ADR-0008, Token-/Origin-/Recovery-/CSRF-Prüfung |
| D08 / vor echtem Backup | RPO 24h, RTO 4h als Ausgangsvorschlag; verschlüsselte getrennte Sicherung samt Schlüsseln | Engere/weitere Ziele nach Speicher, Budget und verfügbarer Betriebszeit; Zahlen sind keine Messung/Zusage | B05/B06, gemessener Restore, Offsite-Ziel und Schlüsselverantwortung |
| D09 / vor täglichem Botversand | Unklare Telegram-Sendezustände sichtbar halten, keinen automatischen Blind-Retry; operative Klärung/Übersicht anbieten | Erneute Zustellung bewusst erlauben und mögliche Duplikate akzeptieren; „genau einmal“ kann ohne externe Hilfe nicht garantiert werden | ADR-0004, REQ-032 und Ausfall-Szenarien |
| D10 / vor KI-Datenübermittlung | Anbieterunabhängiger Adapter, minimal freigegebener Kontext, hartes administratives Monatslimit, Quellen-/OCR-Bestätigung | Lokales Modell oder rein manuelle Recherche; tatsächliche Qualität/Kosten/Hardware erst messen | ADR-0005; Anbieter, Datenregion/Retention, Betrag und Aufbewahrung offen |
| D11 / vor B07-Jahreskostenabnahme | Vorgangskosten und echte Zahlungen getrennt modellieren; zunächst native Zahlungsfelder prüfen, bei Lücke ausdrücklich minimales führendes Zahlungsmodell entscheiden | Reine Vorgangskostenanzeige erfüllt die geforderte Zahlungshistorie nicht automatisch. Lager-Restkosten sind weder ursprünglicher Kaufbetrag noch Zahlung | B19, DS-07; Zahlungsdatum/-status/-quelle, Erstattungen und Währungspolitik festlegen |

## Änderungsprotokoll ohne Mehrnutzer-Gateway

Die Rechteklärung macht einen Gateway zur Unterscheidung von Admins und Read-only-Nutzern entbehrlich. **REQ-043 verlangt weiterhin ein Änderungsprotokoll für Wartung und Logbuch** und REQ-020 eine nachvollziehbare Problemhistorie. Welche nativen LubeLogger-Daten dazu tatsächlich genügen, wird unabhängig mit synthetischen Daten und Quellcode geprüft.

Ein lückenloser Vorher-/Nachher-Nachweis aller nativen UI-Aktionen wurde früher als technische Option angesetzt; der Nutzer hat ihn nicht zusätzlich zur bestehenden Anforderung verlangt. Die geprüfte Lösung darf ihre tatsächliche Abdeckung trotzdem nicht übertreiben. Eine eigene Ergänzung kommt bei belegter funktionaler Lücke in Betracht, nicht allein zur Durchsetzung verschiedener Web-Rollen.

## Betreiberinformationen erst dann erheben, wenn sie gebraucht werden

Keine Geheimnisse in Antworten oder Git eintragen. Später reichen zunächst: Proxmox-Gastwahl und Architektur, grob freie CPU/RAM/Disk, vorhandene Domain/Identität, Paperless-Version, Backupziel/Retention und Betriebsverantwortung. Telegram-User-ID und Kalender-ID werden zur Integration benötigt, Tokens ausschließlich über die festgelegte lokale Secretablage. Für fachliche Einrichtung kommen pseudonymisierte Fahrzeugprofile und die passenden Herstellerunterlagen hinzu; FIN und private Dokumente müssen nicht im Repository landen.

## Was ohne diese Antworten weitergehen kann

Spezifikation, synthetische Domänen-/Vertragstests und isolierte Spikes für Rechte, Audit und Einheiten benötigen keine Homelab-Secrets. Produktive Datenübernahme, Tunnel, Anbieterzugriffe und Veröffentlichungen benötigen dagegen vorher aufgelöste zugehörige Fragen und die in AGENTS.md genannten ausdrücklichen Freigaben.

WP01-Fortschreibung 2026-10-27: [42 isolierte Checks](../discovery/wp01-runtime-verification.md) gelten technisch weiter. Der Nutzer benötigt jedoch keine Native-Read-only-Rollen oder Rechteunterschiede zwischen zugelassenen Admins; die damalige zwingende Gatewayempfehlung entfällt. Side-Effect-Reads und Schutz vor unauthentifizierten externen bzw. direkten Originzugriffen bleiben eigene Prüfpunkte.
