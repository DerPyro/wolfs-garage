# Phase-0-Prüfung und spätere Abnahme

Stand: 2026-10-26. Dokumentprüfungen und Integrationsabnahme strikt unterscheiden.

## In Phase 0 geprüft

- Ursprüngliches Repository vollständig gelesen; ausschließlich Planungs-/Designartefakte ergänzt.
- Unabhängige Reviews zu LubeLogger, Betrieb/Security und Paperless/Kalender zusammengeführt; gemeinsame Dateizuständigkeiten getrennt gehalten.
- Interne Markdown-Dateilinks, ADR-Referenzen und Abdeckung aller 49 REQ-IDs im Backlog überprüft.
- Compose-Design als YAML geparst: `services == {}`, keine startbaren Dienste. Variablenvorlage enthält nur leere Werte und Europe/Berlin.
- `git diff --check`; keine Secrets, persönlichen Dokumente oder echten Fahrzeugdaten hinzugefügt.

Der ursprüngliche Discovery-Schritt führte keine Anwendungstests oder Restores aus. Inzwischen wurde die ausdrücklich beauftragte [lokale B01/B02-Erprobung](lubelogger-runtime-verification.md) ausgeführt: 62 Checks mit 51 pass/11 gap und erfolgreichem Anwendungsrestore in separater Instanz. Der Bericht ordnet genaue Teilabdeckung und offene Restfälle zu. Keine produktiven Deployments. Die folgende Matrix bleibt ein **weiterer Abnahmeplan**; sie ist nicht pauschal bestanden.

## Vor Umsetzung/Freigabe nachzuweisen

| Gate | Fälle / erwartete Evidenz | Backlog |
| --- | --- | --- |
| API/Version/Lizenz | Release, Digest, API-Schema und Fixtures; minimale Rollen und fremde Fahrzeug-ID; `Success=false` trotz 2xx | B01/B02 |
| Fachliche Basis | Fünf Fahrzeuge, km/Meilen-Schutz, Rückdatierung/Korrektur, Kosten/Teileverwendung ohne Doppelzählung, Zusatzfelder | B02/B07 |
| Regel-/Datumslogik | „was zuerst eintritt“, heute/überfällig, 30/7 Tage, Monatsende, Schaltjahr, DST Europe/Berlin, bestätigte Durchführung ohne automatische Fiktion | B04/B12 |
| Audit | Eigene und direkte LubeLogger-UI-Änderungen, Löschungen/Korrekturen und verlorene Webhooks; Lücken sichtbar, REQ-043 nicht vorzeitig abhaken | B03 |
| Sicherheit | Native Auth vor Tunnel, Origin-Bypass, Objektberechtigung, CSRF, fehlende/fremde Bot-ID, Gruppenchat, manipulierte/abgelaufene Bestätigung | B06/B11 |
| Konsistenz/Ausfall | Wiederholtes Telegram-Update, konkurrierende Bestätigung, Prozessabbruch, externer POST mit verlorener Antwort, Ausfall von Google/Paperless/KI ohne Blockade der Basisverwaltung | B02/B10/B11/B12 |
| Dokumente | Version/Aushandlung, autorisierte/unberechtigte IDs, Entzug und Löschung, keine Tokens in URLs, Restore derselben IDs | B09 |
| Kalender | stabile ID, 409/412, manuelle Änderung/Löschung, 7-Tage-Reminder, abgelehnter 30-Tage-Nativwert; beschlossene Alternative | B04/B12 |
| Restore | isolierter Gast, Daten/Anhänge/Schlüssel/IDs konsistent, Auth intakt, Outbox gesperrt, kein externer Versand; gemessene RPO/RTO | B06 |
| UI | Responsive Ansicht, priorisierte Aufgaben, Ampel, Historie und Dokumentverknüpfung mit synthetischen Daten | B07/B13 |
| KI später | Quellenlücken/erfundene Intervalle ablehnen, OCR-Fehler bestätigen, externe Instruktionen ignorieren, keine direkte Schreibberechtigung | B14/B15 |

Detaillierte Fälle stehen auch in den drei Discovery-Berichten. Testprotokolle müssen Zielversion, synthetische Fixtures, erwartetes/tatsächliches Ergebnis und offene Abweichungen enthalten. Neue Ausnahmen führen zu nachvollziehbaren ADR-Updates statt stillschweigender Anforderungsänderung.

WP01 vom 2026-10-27: [42 weitere isolierte Checks](wp01-runtime-verification.md) (28 pass/14 gap) und unabhängiges Quell-/Testreview. Gezieltes Machbarkeitsergebnis, keine vollständige Gateabnahme; Original-B01/B02-Evidenz unverändert.
