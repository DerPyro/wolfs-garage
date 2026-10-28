# ADR-0009 — LubeLogger oder eigener Garage-Kern

- Status: **Entschieden — eigenständige Entwicklung, produktive Übernahme separat**
- Datum: 2026-10-28
- Anlass: Nutzerauftrag, LubeLogger kritisch gegen eine eigene Lösung zu prüfen.

## Kontext

Eine eigene reduzierte Oberfläche ist entstanden; LubeLogger trägt weiterhin Fahrzeug-, Kilometer-, Beleg- und Erinnerungsverwaltung. Fahrbereitschaft und offene Punkte sind als eigener lokaler SQLite-Ausbau vorbereitet. Der Nutzer hat den entsprechenden Rollout gestoppt. Eine Zustimmung zur Optik ist keine hier dokumentierte neue Migrationsentscheidung.

Die ursprünglichen Anforderungen umfassen mehr als die Fahrzeugkarten und wurden nicht durch einen kleineren Funktionsumfang ersetzt. LubeLogger besitzt dafür nachgewiesene Verwaltungsfunktionen. Seine öffentliche API der geprüften Version v1.7.4 bildet jedoch Wiederholungsregeln und einige native Folgeaktionen nicht vollständig ab. Ein gemeinsamer Problem-/Reparatur-/Historienablauf würde mit eigener Zusatzdatenbank mehrere Schreibgrenzen berühren.

Die [vollständige Challenge](../planning/lubelogger-vs-own.md) unterscheidet Codebestand, bestehende Laufzeitevidenz, offizielle Dokumentation, Vorschläge und unbekannten Produktivdatenumfang.

## Entscheidung nach Nutzerklärung

Der Nutzer hat sich ausdrücklich für die eigenständige Entwicklung von Wolfs Garage als Open-Source-Projekt entschieden. Anschließend wurde MIT als Lizenz gewählt. Damit ist die Datenhoheit für die neue Anwendung geklärt: Fahrzeuge, Kilometer, offene Arbeiten, Durchführungen und Historie werden im eigenen Kern geführt. LubeLogger ist keine Laufzeitabhängigkeit des neuen Kerns.

Der erste isolierte Entwicklungsumfang enthält einen modularen Flask-/SQLite-Dienst, die vorhandene Oberfläche, unabhängige Fahrbereitschaft/offene Punkte, Kilometer, Service-/Reparaturbelege, eine explizite atomare Punkt-Erledigung, Verlauf und Backup/Restore-Nachweise. Die ursprünglichen weiteren Anforderungen bleiben auf der Roadmap. Dieser erste Umfang ist keine Behauptung vollständiger LubeLogger-Parität.

LubeLogger bleibt für den bereits laufenden Bestand bis zu einer gesonderten Übernahme führend. Die Entscheidung erlaubt lokale eigenständige Entwicklung, aber keine unangekündigte Migration, Datenlöschung oder produktive Umschaltung. Ein dauerhafter Dual-Write wird nicht eingeführt.

## Konsequenzen und offene Entscheidungen

- Die bestehende Oberfläche kann bei beiden Varianten weiterverwendet werden. UI-Unzufriedenheit allein entscheidet die Datenhoheit nicht.
- Vor einem Ersatz ist der erste vollständige Nutzungsumfang ausdrücklich festzulegen. Keine Anforderungen stillschweigend streichen und keine vollständige LubeLogger-Parität unterstellen.
- Eigene stabile IDs, Schemaänderungen, Kilometer-/Geld-/Datumsregeln, Dokumente, Änderungsjournal sowie Backup/Restore wären eigene Verantwortung.
- Ein späterer Übernahmeauftrag benötigt vollständige Inventur, gesicherten Originalbestand einschließlich Anhängen, Betriebs-/LubeLogger-Konfiguration und ASP.NET-DataProtection-Schlüsseln, trockenen Import und Vergleich sowie einen eindeutigen Schreibwechsel mit Rückweg. Ein Anwendungsexport allein deckt diesen Betriebsrückweg nicht ab. Parallele Dual-Writes sind kein vorgeschlagener Übergang.
- Für den neuen eigenständigen Kern ersetzt diese Entscheidung die vorgeschlagene LubeLogger-Datenhoheit aus ADR-0001/0002 und die Übergangsannahmen aus ADR-0007. Diese alten Entwürfe bleiben für historische Integrationsarbeit lesbar. ADR-0008 gilt weiterhin für das Referenzdeployment; andere Installationen können einen anderen authentifizierenden Reverse-Proxy verwenden.
- Eigenständige lokale Implementierung ist beauftragt. Produktive Übernahme und Stilllegung von LubeLogger sind nicht erfolgt.

## Evidenz

- [Anforderungen](../requirements.md), [Challenge mit Quellen und Gegenargumenten](../planning/lubelogger-vs-own.md)
- [LubeLogger B01/B02](../discovery/lubelogger-runtime-verification.md), [Funktionen](../discovery/wp02-functional.md), [Auditumfang](../discovery/wp02-audit-assessment.md)
- [Aktueller Adapter](../../garage_gateway/server.py), [lokaler Statusspeicher](../../garage_gateway/status_store.py)
