# Prüfstand der Planungsartefakte

Stand: 2026-10-27. Nach der Ein-Admin-Klarstellung wurde die OpenAPI-Sessionbeschreibung auf ein automatisch aus Cloudflare abgeleitetes Login aktualisiert und offline erneut geprüft. **Ausschließlich Offline-Spezifikationsprüfung, keine neuen Laufzeit-/Server-/Autorisierungstests.**

Bestandsaufnahme und Review: Alle ursprünglichen Requirements/Architektur-/Roadmapdokumente, ADRs und B01/B02-Berichte wurden berücksichtigt. Drei unabhängige Planungsbereiche lieferten Domäne/Fachregeln, Produkt/Bot/KI und Betrieb/Security. Anschließende Read-only-Reviews identifizierten und bereinigten Vertragswidersprüche.

## Tatsächlich geprüft

- `python3 tests/planning/validate_contracts.py`: JSON Schema Draft 2020-12 strukturell gültig; **34 positive/negative Payloadprüfungen**, **56 lokale Referenzen**, fünf eindeutige OpenAPI-Operationen.
- Beispiele enthalten keine tatsächlichen Nutzer-/Fahrzeugdaten, Passwörter oder Tokens. Die Bestätigungsnonce im Beispiel ist ausdrücklich eine synthetische Zeichenfolge ohne Servergültigkeit.
- Interne Markdown-Dateilinks, ADR-/Backlogreferenzen und unveränderte B01/B02-Evidenz-Prüfsummen überprüft; `git diff --check`.
- Keine Dienste gestartet, keine produktiven Ressourcen angelegt, keine Datenmigration/Löschung, kein Cloudflare-/Provider-Accountzugriff.

Eine vollständige OpenAPI-Konformitätsprüfung mit spezialisierter Toolchain ist noch offen. Die lokalen Checks ersetzen keine Semantik-, Berechtigungs-, Datenbank-/Provider-/UI-Tests. **27 Fachvektoren sind spezifiziert, nicht als Domänencode ausgeführt.** Die vorherigen 62 B01/B02-Laufzeitchecks bleiben die bisherige Laufzeitevidenz.

## Im Review bereinigte Punkte

1. Physische Durchführung lokal bestätigt versus Providerbeleg pending/uncertain: getrennte Zustände, kein stiller Rollback und kein doppeltes Erledigen.
2. Idempotenz-Lookup über Actor/Methode/Pfad/Key, Bodyhash nur als Vergleich; abweichende Nutzlast führt zum Konflikt.
3. Recovery einer verlorenen Entwurfsantwort: neue Nonce plus höhere Commandrevision, alte Nonce ungültig; nur Nonce-Prüfwert gespeichert.
4. Erwartete Aggregatrevisionen serverseitig binden, nicht nur Fahrzeug-Snapshotrevision.
5. Bestätigte Frist getrennt von Forecast samt Messreferenzen/Projektionsrevision; Monatsprecision bewahren.
6. Cancel nur für awaiting_confirmation; keine zugesagte Rücknahme akzeptierter externer Effekte.
7. Web-Session/CSRF gegenüber Telegram-Allowlist/Chatbindung transportabhängig, gemeinsame Domänenautorisierung.

## Reproduktion und Prüfsummen

Voraussetzungen des Offline-Prüfers: Python mit PyYAML und jsonschema; im geprüften System verfügbar. Keine Dienste, Netzabfragen oder Schreibvorgänge durch den Prüfer. Getestete Paketversionen: PyYAML 6.0.2, jsonschema 4.19.2.

```bash
python3 tests/planning/validate_contracts.py
```

| Datei | SHA256 des geprüften Stands |
| --- | --- |
| [command.schema.json](contracts/command.schema.json) | `6aa69dab944842c5ffc4f88072bdd78d60907e263a7b3f63ae2a56ebbf9ce7e7` |
| [garage.openapi.yaml](contracts/garage.openapi.yaml) | `6b57438898036448a19e410f2491413ba8393d52e210410096a6a625390e932f` |
| [validate_contracts.py](../../tests/planning/validate_contracts.py) | `001cc32c09f0ebb4785f44de11edf97f5ebe3309e66b3fbc8b96a5dbf048f336` |
| [command-uncertain.json](contracts/examples/command-uncertain.json) | `b6f1c9ba9237dd11f4ac04663acd65d4bab9d22ceba76dc6b3d3f1e9dac87015` |
| [confirm.json](contracts/examples/confirm.json) | `5906aa151725bb4cff317eeaf15660dfa9105db5d05ec63f0a6e650bf34e54b0` |
| [draft-hu-month.json](contracts/examples/draft-hu-month.json) | `47af3313dddd9aa22a075e5edc959c18fec5a0b2fef3dc2fb08ea3754cdfcdfa` |
| [draft-maintenance.json](contracts/examples/draft-maintenance.json) | `bb026d161a47d124448d8696ae2c8d635fe2b51f0f225c77cc6830575415b3b3` |
| [draft-odometer.json](contracts/examples/draft-odometer.json) | `75c52c323aac66b192b4339aeb2d2d49f89dbee6416584391bc7990ff909811f` |
| [draft-problem.json](contracts/examples/draft-problem.json) | `9d1df6cfe33b8d8f16a9a97d7153e8883339b1e66d5954aaf02745eefab4b4f1` |
| [tasks-forecast.json](contracts/examples/tasks-forecast.json) | `ba5e70f71b4a402df1550e77a4a10ad2ccb940e3cddee186bd1d90605d6b4623` |
| [tasks.json](contracts/examples/tasks.json) | `5c38bd592416b6ecda80419d6be164480806becf5e41701a1b3c68ddde54013e` |
