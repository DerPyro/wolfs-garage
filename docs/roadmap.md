# Roadmap

## Phase 0 — Discovery und Architektur
LubeLogger und Paperless-API prüfen; Datenmodell, Deployment-Grenzen, Backups, Authentifizierung und Integrationsvertrag festlegen. Ergebnis: ADRs, Compose-Entwurf, priorisierter Backlog.

## Version 1.0 — Basisverwaltung
LubeLogger auf Proxmox via Docker; Cloudflare Tunnel/Access; Fahrzeugstammdaten; Kilometerstände; Wartungsintervalle; Reparaturen; Kosten; Web-Listenübersicht; HU/Steuer/Versicherung; Backups. Eigene UI nur wenn die Bestandslösung Anforderungen nicht ausreichend abdeckt.

## Version 1.1 — Assistent und Integrationen
Spring-Boot-Telegram-Bot; ID-Allowlist; natürlichsprachliche Erfassung mit Bestätigung; 30-Tage-Erinnerungen; prognostizierte Kilometerfälligkeiten; Google-Kalender-HU-Synchronisierung; Paperless-Verknüpfung; technisches Logbuch und Schweregrade.

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
