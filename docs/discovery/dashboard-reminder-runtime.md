# Reminder-Lesezugriff: isolierter Laufzeitnachweis

Stand: 2026-10-28. Der Dashboard-Adapter liest Erinnerungen über `GET /api/vehicle/reminders`. Dieser Test untersucht eine mögliche persistierende Nebenwirkung des Leseaufrufs mit synthetischen Daten und ergänzt die frühere Quellcodeprüfung. Er greift nicht auf die produktive Garage oder Cloudflare zu.

## Aufbau und Ergebnis

- Gepinntes LubeLogger-Image v1.7.4, Digest `sha256:483a9d7582c4e6258615fd822b3de4193b4fcc4230d0a92432c6d407faf75af2`; isoliertes internes Docker-Netz, kein veröffentlichter Port, lokaler Testhost als vertrauenswürdiger Aufrufer.
- Ein synthetisches Fahrzeug, ein Kilometerbeleg mit Ausgangsstand 12000 und Stand 12345 sowie eine kombinierte Datums-/Kilometererinnerung wurden über die API erstellt. Native Authentifizierung war im isolierten Test aus, Locale `de-DE`; ansonsten Standardeinstellungen.
- Nach zwei Sekunden Ruhezeit wurden alle regulären Dateien unter `/App/data` außer `*.log` mittels `sha256sum` erfasst und nach Pfad sortiert. Nach fünf Reminder-GETs, jeweils HTTP 200 mit einer Erinnerung, wurde nach weiteren zwei Sekunden dieselbe Dateiliste erneut gehasht und verglichen.
- Ergebnis: **zwei Daten-Dateien verglichen, Dateiliste und SHA-256-Prüfsummen unverändert**. Der erfolgreiche Lauf verwendete `wolfs-reminder-check-8001c892`; der Testcontainer wurde gestoppt und synthetische Ressourcen wurden nicht gelöscht. Ein vorausgegangener erfolgreicher Vorlauf verwendete `wolfs-reminder-check-e5e7698b`. Der erste Vorlauf `wolfs-reminder-check-64b2e6d1` scheiterte beim Anlegen des Kilometerbelegs mit HTTP 500, weil die Locale nicht explizit gesetzt war; auch dieser Container ist gestoppt.

Der unveränderte Dateistand ist eine Beobachtung zu genau diesem Datensatz und Testzeitfenster. Er beweist nicht, dass sämtliche Einstellungen, Fälle oder später verzögert persistierte Änderungen nebenwirkungsfrei sind. Insbesondere sind daraus kein Backup-/Restore-Nachweis, kein Test echter Daten und keine Aussage über abweichende LubeLogger-Versionen abzuleiten. Eine frühere WP01-Prüfung betraf andere Kilometer-GETs und bleibt davon unberührt.

## Wiederholung

Das [Prüfskript](../../tests/dashboard_reminder_runtime.py) benötigt das gepinnte Image, Docker und ein leeres internes Testnetz. Es legt einen neuen isolierten synthetischen Container an, überprüft vorab Netzwerkisolation und fehlende Portfreigabe, führt den Vergleich durch und stoppt den Container anschließend. Synthetische Ressourcen bleiben erhalten.

```sh
GARAGE_TEST_NETWORK=<leeres-internes-testnetz> python3 tests/dashboard_reminder_runtime.py
```

Im dokumentierten Lauf wurde ein leeres eigenes Testnetz `wolfs-wp02ui-2bf1ae3e16_isolated` erneut verwendet, da der automatische Docker-Subnetzpool auf dem Entwicklungsrechner belegt war. Das Netz ist nicht als fest vorhandene Voraussetzung auf anderen Rechnern anzunehmen.
