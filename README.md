# Wolfs Garage

Self-hosted Fahrzeugverwaltung für fünf Fahrzeuge mit Wartungsplanung, technischem Logbuch, Dokumenten, Telegram-Assistent und später KI-Diagnose.

## Projektstatus
Planungsphase. Siehe [Requirements](docs/requirements.md), [Roadmap](docs/roadmap.md) und [Architektur](docs/architecture.md).

## Prinzipien
- Web-Dashboard als Hauptoberfläche; Telegram als ergänzende Schnittstelle
- LubeLogger als bevorzugte Bestandslösung, Integration vor Implementierung prüfen
- Docker auf Proxmox; externer Zugriff via Cloudflare Tunnel + Access
- Nur ein autorisierter Telegram-Nutzer
- Wartungsempfehlungen nur mit überprüfbarer Herstellerquelle; keine erfundenen Intervalle
- Kritische Aktionen und KI-generierte Änderungen erst nach Bestätigung

## Start mit Codex
Lies zuerst AGENTS.md und docs/. Implementiere ausschließlich die jeweils beauftragte Phase.
