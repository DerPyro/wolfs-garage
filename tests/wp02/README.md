# WP02-Tests mit synthetischen Daten

Diese Tests prüfen die gepinnte LubeLogger-Testversion in isolierten Docker-Containern. Sie verwenden keine echten Fahrzeugdaten, keine Cloudflare-Verbindung und keinen produktiven Dienst. Nach jedem Lauf werden die Testcontainer gestoppt; Netzwerke und Volumes werden gemäß AGENTS.md nicht ohne ausdrückliche Freigabe gelöscht.

| Test | Befehl | Bericht |
| --- | --- | --- |
| Ein-Admin-Modus ohne native Anmeldung | `python3 tests/wp02/single_owner.py` | [Access-only-Sandbox](../../docs/discovery/single-owner-access.md) |
| Funktionen und Berichte | `python3 tests/wp02/functional.py` | [Funktionsbericht](../../docs/discovery/wp02-functional.md) |
| Änderungshistorie und Webhooks | `python3 tests/wp02/audit_run.py` | [Auditprüfung](../../docs/discovery/wp02-audit-assessment.md) |
| Browseroberfläche | `python3 tests/wp02/ui_run.py` | [Browserbericht](../../docs/discovery/wp02-ui.md) |

Die Berichte nennen Voraussetzungen, Testumfang und Grenzen. Auf dem untersuchten Host waren Dockers automatische Netz-Subnetze durch zurückbehaltene Testnetze erschöpft. Wiederholungen benötigen einen verfügbaren isolierten Netzbereich; der dokumentierte Browserlauf verwendete ein eigenes leeres internes Testnetz erneut. Andere Ressourcen wurden nicht gelöscht. Die Browser-Screenshots enthalten ausschließlich synthetische Daten.
