# Anforderungen — Wolfs Garage

Status: abgestimmene Produktanforderungen; technische Details sind noch zu validieren.

## Fahrzeugstammdaten
- REQ-001: Mindestens fünf Autos/Motorräder verwalten, beliebig erweiterbar.
- REQ-002: Marke, Modell, Baujahr, Motorisierung, Kennzeichen, Kilometerstand und fahrzeugspezifische Daten.
- REQ-003: Kilometerstände manuell per Web und Telegram mit Datum erfassen.
- REQ-004: Fahrleistung aus historischen Ständen schätzen und Prognosen als Schätzung kennzeichnen.

## Wartung, Termine, Kosten
- REQ-005: Herstellervorgaben fahrzeugspezifisch recherchieren und mit Quellen nachweisen.
- REQ-006: Zeit- und kilometerbasierte Intervalle, inklusive Regel 'was zuerst eintritt'.
- REQ-007: Individuelle Intervalle und einmalige Aufgaben.
- REQ-008: TÜV/HU, Steuer und Versicherung mit Fälligkeit erfassen.
- REQ-009: 30 Tage vor Fälligkeit per Telegram erinnern; weitere Erinnerungsregeln konfigurierbar.
- REQ-010: Für HU nach bestätigter Durchführung nächste Fälligkeit bestimmen und Google-Kalender-Eintrag automatisch aktualisieren; Regelfall 24 Monate, Ausnahmen prüfen.
- REQ-011: Google-Kalender-Erinnerungen 30 und 7 Tage vorher.
- REQ-012: Wartungen und Reparaturen als erledigt erfassen; nächste Fälligkeit neu berechnen.
- REQ-013: Eigenarbeit vs. Werkstattarbeit unterscheiden; Dauer, Werkstatt, Notizen und Kosten.
- REQ-014: Ersatzteile mit Bezeichnung, Teilenummer, Kaufpreis und Verwendung erfassen.
- REQ-015: Fahrzeugbezogene Zahlungs- und Reparaturhistorie sowie Jahreskosten anzeigen.
- REQ-016: Tankvorgänge sind kein MVP-Ziel.

## Technisches Logbuch
- REQ-017: Probleme mit Datum, Kilometerstand, Beschreibung und Schweregrad erfassen.
- REQ-018: Schweregrade: Auffälligkeit, reparaturbedürftig, kritisch.
- REQ-019: Ereignisse und Diagnose-/Reparaturversuche einem Problem zuordnen.
- REQ-020: Status: offen, beobachtet, behoben; Historie unveränderlich nachvollziehbar.
- REQ-021: Wiederkehrende Probleme mit früheren Fällen verknüpfen.
- REQ-022: Kritische Probleme im Dashboard hervorheben und Telegram-Warnung senden; sicherheitskritische Hinweise nicht allein durch KI klassifizieren.

## Oberfläche und Dokumente
- REQ-023: Responsives Web-Dashboard mit Ampelübersicht aller Fahrzeuge.
- REQ-024: Priorisierte Listenansicht anstehender und überfälliger Aufgaben.
- REQ-025: Fahrzeugdetailseite mit Historie und Logbuch.
- REQ-026: Dokumente zu Fahrzeugen und Vorgängen zuordnen (Fahrzeugschein, HU, Rechnung, Versicherung).
- REQ-027: Paperless-ngx-Integration prüfen; bestehende Dokumente möglichst referenzieren statt duplizieren.
- REQ-028: Sichere Cloudflare-Tunnel-/Access-Veröffentlichung ohne Router-Portfreigabe.

## Telegram und KI
- REQ-029: Telegram-Bot nur für explizit autorisierte Telegram-ID.
- REQ-030: Bot kann Kilometerstände, Aufgaben, Fälligkeiten und Probleme abfragen und erfassen.
- REQ-031: Natürliche Sprache für Erfassung und Abfragen; strukturierte Änderungen vor Speicherung bestätigen.
- REQ-032: Automatische tägliche Prüfung anstehender Fristen und Benachrichtigung ohne Duplikate.
- REQ-033: Fahrzeugbezogene KI-Diagnose mit Zugriff auf freigegebene Historie, Modell und Motorisierung.
- REQ-034: Diagnoseassistent kann gezielte Rückfragen stellen und alternative Ursachen samt Unsicherheit erklären.
- REQ-035: Recherche im Internet zu bekannten Problemen, Reparaturinformationen und Ersatzteilen mit Quellen.
- REQ-036: Screenshots von OBD-Fehlercodes auswerten; Code, Zeitpunkt, Fahrzeug und Status hinterlegen.
- REQ-037: Fehlercode-Status aktiv, gelöscht oder erneut aufgetreten verwalten; kein automatischer OBD-Zugriff.
- REQ-038: Keine Videoanalyse als Ziel; normale Problemfotos sind kein Muss.

## Qualität und Sicherheit
- REQ-039: Self-hosted, Docker-basiert, auf bestehendem Proxmox-Homelab.
- REQ-040: Backups und dokumentierte Wiederherstellung.
- REQ-041: Geheimnisse über Environment/Secret-Management, niemals im Repository.
- REQ-042: Web-Authentifizierung und Autorisierung zusätzlich zur Cloudflare-Schutzschicht prüfen.
- REQ-043: Änderungsprotokoll für Wartungs- und Logbucheinträge.
- REQ-044: KI-Ergebnisse von Fakten trennen; Nutzer bestätigt Änderungen.
- REQ-045: Zeitstempel und Fälligkeiten in Europe/Berlin korrekt verarbeiten.
- REQ-046: Ausfall externer APIs darf bestehende Datenverwaltung nicht blockieren.
- REQ-047: Maschinenlesbare Schnittstellen und Integrationsverträge dokumentieren.
- REQ-048: Integrationstests für Terminberechnung, Berechtigungen und Bot-Dialoge.
- REQ-049: Wartungsintervalle, Erinnerungsgrenzen und Schweregrade konfigurierbar.

## Offene Entscheidungen
- Genaue LubeLogger-API-/Datenmodellabdeckung und Alternative bei Lücken.
- Kalender: eigene Kalender-ID, Ereignisidentität, Duplikatvermeidung und Ausnahmen bei HU-Fälligkeiten.
- KI-Anbieter, Kostenbudget und Datenschutz bei Dokument-/Historienübermittlung.
- Speicherung technischer Logbucheinträge und Anhänge.
