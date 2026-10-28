# ADR-0001 — LubeLogger als Basis über öffentliche API

Status: **Vorgeschlagen** · Datum: 2026-10-26 · Entscheidung: offen

## Kontext und Evidenz

Die Roadmap bevorzugt Bestandssoftware. Die [Discovery](../discovery/lubelogger.md) prüft LubeLogger v1.7.4 einschließlich MIT-Lizenz, API-Key-Rollen und Ressourcen. UI-Funktionalität beweist keine API-Abdeckung: insbesondere Wiederholungs-/Refresh-Felder für Reminder fehlen im geprüften API-Modell. Das ist für REQ-006/012/030 relevant.

## Empfehlung

LubeLogger übernimmt Fahrzeugstammdaten, Kilometerhistorie, Leistungen und Kosten. Nur dokumentierte und gegen die gewählte Version getestete API-Operationen verwenden. Kein direkter Datenbankzugriff, kein Fork und kein Scraping privater UI-Controller als Integrationsvertrag. Falls native LubeLogger-Auth aktiviert ist: API-Key mit nötiger Rolle und Header-Übertragung; Reader und Writer nur bei funktionalem Bedarf trennen. Bei ausgeschalteter nativer Auth schützen API-Key-Rollen nicht; interne Dienstzugänge müssen stattdessen durch den gewählten Netz-/Zugangsaufbau kontrolliert werden (ADR-0008). Invariante Datum-/Zahlendarstellung explizit anfordern und testen.

Für v1.0 Wiederholungsregeln zunächst in der LubeLogger-UI pflegen, sofern die Sandbox REQ-006/012 bestätigt. Vor v1.1 entscheiden: unterstützt eine dann geprüfte öffentliche API alle nötigen Regeln oder verwaltet Garage diese Regeln selbst? Garage darf keine unvollständige Kopie der UI-Regeln als verlässliche Quelle behandeln. Bei Garage-Hoheit ist eine einmalige nachvollziehbare Übernahme samt Deaktivierung konkurrierender Wiederholungen nötig.

## Alternativen und Folgen

- Vollständige Eigenentwicklung: hohe Kosten, derzeit kein belegter Mehrwert.
- Direkter Datenbankzugriff/Fork: Kopplung an Interna und Upgrade-Risiko; nicht empfohlen.
- Reine LubeLogger-Nutzung: günstig für v1.0, deckt Bot und technisches Logbuch nicht nachweislich ab.

LubeLogger kann unabhängig vom Assistenten bedienbar bleiben. Ein Adapter muss Versionsänderungen, unbekannte Felder und Fehler erkennen. Lizenzhinweise bei Weitergabe erhalten; konkrete Artefakte und Abhängigkeiten vor Distribution gesondert inventarisieren.

## Offene Entscheidung und Nachweise

Zielversion und Image-Digest, reale API-Schemaausgabe, Berechtigungstests, Fälligkeits-/Kosten-/Kilometerfälle und Reminder-Wiederholung in isolierter Umgebung prüfen. Erst dann Basisumfang freigeben. API-Erweiterung upstream ist eine mögliche spätere Option, keine Voraussetzung mit zugesagtem Liefertermin.

## B01/B02-Nachtrag: Laufzeitstand 2026-10-26

[Testbaseline](../../tests/lubelogger/target.lock.json) auf v1.7.4/linux-amd64 mit Registry-Digest festgelegt, API-Katalog bytegleich zum Release verifiziert. [Laufzeitbericht](../discovery/lubelogger-runtime-verification.md): Kern-CRUD, Rollen, Locale, bestehende Wiederholung nach API-Update und isolierter Restore bestätigt. Öffentliche API ignoriert neu mitgesendete Wiederholungs-/Reminder-Auswahl-/Teileverwendungsfelder; eine erfolgreiche Wartungsanlage allein schreibt weder Fristen noch Lager fort. Reminder-Grenzen und Dokumentrechte haben zusätzliche Befunde (B16/B17). Deshalb bleibt dieser ADR **Vorgeschlagen**; der Testbaseline entspricht keine Produktivfreigabe. Direkte Paketlizenzen sind inventarisiert, vollständige Container-SBOM vor eigener Distribution offen.

## WP01-Präzisierung — API-Reads und Rollen

[WP01](../discovery/wp01-runtime-verification.md) zeigt, dass auch `GET /api/vehicle/odometerrecords` unter Viewer-Key eine bedingte persistierende Altbestandskonvertierung ausführt; Viewer kann zudem `/api/documents/upload` verwenden. Ein Minimalrollen-Key ist weiterhin nötig, aber kein pauschaler Schreibschutz aller Routen. Adaptercapabilities müssen deshalb konkret verifizierte Pfade, Methoden und Nebenwirkungen beschreiben. Für Kilometer-Vorher-/Nachhermessungen wurde `/api/vehicle/odometerrecords/all` als unabhängiger nicht konvertierender Beobachter genutzt; keine pauschale Freigabe weiterer GETs ableiten.
