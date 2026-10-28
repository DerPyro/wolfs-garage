# ADR-0007 — Garage als alleiniger Regel-Owner und geordneter Übergang

Status: **Vorgeschlagen** · Datum: 2026-10-26 · Entscheidung: offen

## Kontext und Evidenz

LubeLogger v1.7.4 bietet Recurrence in der nativen UI, exportiert/verwaltet sie aber nicht vollständig über die öffentliche API. Wartungsanlage via API erledigt keinen Reminder; DueDays ist kein verlässlicher lokaler Kalendertagabstand, und Custom-Thresholds sind reihenfolgeabhängig. Quellen/Laufzeitfälle: [B01/B02](../discovery/lubelogger-runtime-verification.md).

## Empfehlung

Ab der zugehörigen Garage-Erweiterung besitzt Garage Regeln, bestätigte Durchführungen, quellenbelegte Baselines, daraus abgeleitete Fälligkeiten und Versandrevisionen. LubeLogger bleibt führend für seine Fahrzeug-/Kilometer-/Kostenbelege und kann konkrete nicht wiederkehrende Fälligkeiten als **abgeleitete Anzeige** erhalten. Kalender und Telegram sind weitere Projektionen. Kein zweiter editierbarer Regelbestand; keine automatische Rückübernahme von Provider-Drift.

Die Empfehlung ist von B04 und einer expliziten Übernahmeentscheidung abhängig. v1.0 kann vorher native Regeln verwenden, wenn die jeweiligen Gate-Nachweise vorliegen; der Zeitpunkt des Ownerswechsels bleibt offen. Die [Fälligkeits-Spezifikation](../planning/due-date-spec.md) legt den Zielentwurf fest, ohne echte Herstellerintervalle einzusetzen.

## Geplanter Übergang — derzeit keine Migration

1. Synthetische Fälle, danach bestätigte Inventur aller Regeln: Beschreibung, Originalquelle, Datum-/km-Grenzen, Einheit, feste/flexible Baseline, Intervalle und tatsächliche letzte Durchführung.
2. Nicht exportierte Recurrence-Felder über nachvollziehbare manuelle UI-Inventur erfassen; keine privaten Routen oder direkten DB-Manipulationen als laufende Integration.
3. Dry-run in Garage berechnen; jede Abweichung erklären, keine Ausgabe als Durchführung werten. Doppelte/unsichere Quellen getrennt klären.
4. Vor einem später ausdrücklich freigegebenen Cutover: Schreibstopp, konsistentes Backup und Manifest; Nutzer bestätigt Regelübernahme. Native automatische Fortschreibung und konkurrierende Regeln kontrolliert deaktivieren. Das geht in der geprüften API nicht vollständig: ein überprüfter manueller Administrationsschritt ist erforderlich.
5. Erst danach Garage-Jobs und gewünschte konkrete Projektionen aktivieren; gemeinsame Revision/Zuordnungen prüfen. Kein massenhaftes Nachsenden alter Erinnerungen.
6. Rollback nur bei pausierten Schreibern/Jobs und nach Klassifikation bereits extern ausgeführter Effekte. Nach Cutover eingegangene Durchführungen nicht durch Rückspielen eines alten Backups verlieren.

## Alternativen und Folgen

Native Regelhoheit belassen: kleinerer eigener Umfang, Bot-Fortschreibung bleibt bis belastbarer API-Erweiterung eingeschränkt. Upstream-Erweiterung abwarten: mögliche spätere Vereinfachung, keine zugesicherte Verfügbarkeit. Doppelte Scheduler sind ausgeschlossen, weil sie unterschiedliche nächste Fristen und Duplikate erzeugen können.

Garage-Regelhoheit bedeutet eigene fachliche Verantwortung für LocalDate, Monatsende, Quellen, Schätzungen und Korrekturen. Deshalb vor Umsetzung deterministische Testvektoren und nachher Scheduler-/Cutover-/Restore-Tests erforderlich. Dieser ADR autorisiert weder eine produktive Migration noch Löschung oder Deployment.
