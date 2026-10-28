# Standalone-Kern — isolierter Nachweis

Stand: 2026-10-28. Geprüft wurde die neue eigenständige Alpha ausschließlich mit synthetischen Daten. Keine Verbindung zur produktiven Garage, LubeLogger, Cloudflare oder sonstigen externen Integrationen.

## Ergebnis

- 24 Python-Tests bestanden: 18 Store- und sechs HTTP-/API-Prüfungen. Erfasst sind atomare Durchführung/Punkt-Erledigung, unabhängige Fahrbereitschaft, stabile IDs bei Stammdatenkorrektur, alte Revisionen, parallele Wiederholung, unveränderte Idempotenzantwort nach Restart/Restore, falsche Eingaben, Origin-/Host-/JSON-Grenzen und fehlende/inkompatible Datenbanken.
- Frontend-Mockprüfungen bestanden: Legacy-Anzeige, eigenständige Anlage und Korrektur, Wiederholung mit stabiler Command-ID, expliziter Problemabschluss und lesbarer Verlauf.
- Chromium durchlief die echte UI gegen Gunicorn und SQLite: leere Garage → Fahrzeuganlage → INOP mit zwei offenen Punkten → Stammkorrektur → Kilometer → Reparatur mit Kosten und Belegreferenz → genau einen Punkt schließen → Verlauf → Neuladen. INOP und der andere Punkt bleiben bestehen. Die native Verwaltungsnavigation ist verborgen.
- Die Browseransicht wurde bei 320, 390, 768 und 1280 Pixeln ohne horizontale Seitenverbreiterung geprüft. [Mobile Aufnahme](evidence/standalone-preview-mobile.png) enthält ausschließlich synthetische Daten.
- Docker-Image auf dem gepinnten Python-3.12-Basisimage gebaut; vollständige Runtimeversionen sind in `requirements.lock` festgehalten. Compose-Konfiguration geprüft.
- Das Image lief mit UID/GID 65532, schreibgeschütztem Root-Dateisystem und dauerhaftem Named Volume. HTTP-Anlage, Durchführung/Punktabschluss und Verlauf funktionierten; eine SQLite-Sicherung wurde erstellt und intern geprüft. Nach Containerneustart waren der Belegbetrag und der bearbeitete Status erhalten.

Der lokale Docker-Standardadresspool war durch vorhandene Testnetze ausgeschöpft. Für den Compose-Lauf wurde daher nach Prüfung sichtbarer Routen und Netze eine ausschließlich lokale Testergänzung mit explizitem freiem Subnetz verwendet. Bestehende Netze wurden nicht entfernt. Das ist eine Umgebungsgrenze dieses Prüfhosts, kein Lauf auf einem frischen Betreiberhost. Die Testprozesse und der Testdienst wurden anschließend beendet; ihre synthetischen Datenvolumes bleiben erhalten.

## Reproduktion und Grenzen

Store/API: `.venv/bin/python -m unittest discover -s tests -p 'test_own_*.py'`. Frontend: `frontend/test-ui.cjs` im bisherigen Chromium-/Node-Testimage. Der echte Browserablauf steht in `tests/standalone_browser.cjs` und erwartet eine leere, bewusst initialisierte lokale Alpha unter `http://127.0.0.1:18981`; das öffentliche Origin muss diesem Wert entsprechen. Der Test schreibt synthetische Daten und braucht vor einer Wiederholung eine neue isolierte DB.

Die [Installationsanleitung](../standalone.md) und Compose-Datei definieren den generischen Einstieg. Die Proben ersetzen keinen Nachweis des späteren authentifizierenden Reverse-Proxys, eines echten vollständigen Datenimports oder eines produktiven Restore. Schema-Upgrades, wiederkehrende Regeln, Belegkorrekturen, Uploads, Teileverwaltung und externe Integrationen sind noch nicht Bestandteil dieser Alpha. Externe Dokumente werden nur referenziert und nicht durch das SQLite-Backup gesichert.
