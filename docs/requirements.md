# Anforderungen — Wolfs Garage

Status: Produktanforderungen mit entschiedener eigenständiger Entwicklung unter MIT. Der erste Alpha-Kern ist implementiert; weitere fachliche und betriebliche Details bleiben zu validieren.

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
- REQ-042: Cloudflare Access ist das einzige gewünschte interaktive Web-Login. Alle dort zugelassenen Webnutzer erhalten Administratorrechte auf sämtliche Fahrzeuge und Dokumente. Den Schutz der internen Anwendung vor direktem, nicht durch Access geprüftem Zugriff sowie passende Dienstzugänge prüfen; eine zweite interaktive Anmeldung ist nicht das Ziel.
- REQ-043: Änderungsprotokoll für Wartungs- und Logbucheinträge.
- REQ-044: KI-Ergebnisse von Fakten trennen; Nutzer bestätigt Änderungen.
- REQ-045: Zeitstempel und Fälligkeiten in Europe/Berlin korrekt verarbeiten.
- REQ-046: Ausfall externer APIs darf bestehende Datenverwaltung nicht blockieren.
- REQ-047: Maschinenlesbare Schnittstellen und Integrationsverträge dokumentieren.
- REQ-048: Integrationstests für Terminberechnung, Berechtigungen und Bot-Dialoge.
- REQ-049: Wartungsintervalle, Erinnerungsgrenzen und Schweregrade konfigurierbar.

## Eigenständige Open-Source-Anwendung — Nutzerentscheidung 2026-10-28

- REQ-050: Der neue Anwendungskern verwaltet seine Daten eigenständig; LubeLogger ist keine erforderliche Laufzeitabhängigkeit. Eine bestehende LubeLogger-Instanz wird erst durch einen gesonderten, kontrollierten Übernahmeauftrag ersetzt.
- REQ-051: Eigener Projektcode wird unter MIT bereitgestellt. Lizenzen und Hinweise zu Drittkomponenten und Markenabbildungen bleiben erhalten.
- REQ-052: Andere Betreiber können die Anwendung mit generischer Konfiguration und eigener Datenhaltung selbst installieren. Persönliche Fahrzeugdaten, Hostkonfiguration und Geheimnisse gehören nicht in die öffentliche Quelle oder Beispieldaten.
- REQ-053: Der Kern funktioniert ohne verpflichtende Cloud-APIs. Cloudflare Access bleibt der gewünschte Eingang der Referenzinstallation; andere Betreiber können einen passenden authentifizierenden Reverse-Proxy einsetzen. Ein eigenes Mehrrollen- oder Mandantensystem wird dadurch nicht beauftragt.
- REQ-054: Einen vom Betreiber eingegebenen HU-Fälligkeitsmonat als `YYYY-MM` speichern und daraus einen Europe/Berlin-Status sowie eine getrennte Readiness-Projektion ableiten. Ein unbekannter Monat bleibt unbekannt; die gespeicherte manuelle Fahrbereitschaft wird nicht verändert. Die Frist- und Blockierungsregel ist eine explizite Betreiberregel, keine Aussage über gesetzliche Fristen.
- REQ-055: Die Karten-HU-Leiste bleibt als visuelle Statusanzeige erhalten: Für kommende Monate nutzt sie die visuelle 24-Monats-Skala, voll grün bei mindestens 24 Monaten und dann rechts verankert mit graduellem Farbwechsel zu Rot. Unbekannt bleibt ein voller violetter Balken mit zentriertem `?`; `due` im aktuellen Monat ein voller gelber Balken ohne Ablaufmarker; `overdue` und `blocking` ein voller roter Balken mit zentriertem `!`; eine ungültige Projektion neutral grau mit `!`. In der Fahrzeugdetailansicht ersetzt eine kompakte Textzeile das große HU-Panel und jeden Detailmeter: bekannter Termin mit ungefährer Restzeit, klare Texte für aktuell fällig, überfällig/blockierend, unbekannt und nicht verfügbar. Kein doppeltes Standdatum der Projektion. Die Detailzeile verändert die Bereitschaftsregeln nicht. Die 24-Monats-Skala ist ausschließlich visuell; sie setzt keine Frist, leitet keine Intervalle ab und ändert weder Backend-/API-Felder noch die Betreiberregel. Die Kartenhöhe bleibt unverändert.
- REQ-056 (Nutzeranforderung, 2026-10-29): Aktive offene Punkte in der Fahrzeugdetailansicht einzeln bearbeiten oder über **Erledigt** in ein Arbeitsprotokoll überführen können. Bearbeiten öffnet den bestehenden Statuseditor mit Fokus auf dem ausgewählten Punkt. Erledigt startet das vorhandene Arbeitsformular mit vorausgefüllter Beschreibung und heutigem Datum; Kilometerstand und Kosten bleiben optional. Erst eine ausdrückliche Speicherung legt den Arbeitsdatensatz an und schließt genau den ausgewählten Punkt atomar. Andere Punkte samt Fälligkeitsdatum, Schweregrad und Lebenszyklus sowie die manuell gespeicherte Fahrbereitschaft bleiben unverändert. Abbrechen verwirft den Entwurf ohne Schreibvorgang. Es werden keine neuen Notiz- oder Prioritätsfelder eingeführt.
- REQ-057: Einen vollständigen, konsistenten SQLite-Datenbankstand über die geschützte Oberfläche/API sichern und getrennt vom portablen JSON-Export wiederherstellen können. Wiederherstellung validiert Inhalt und unterstütztes Schema, schreibt ausschließlich in eine neue Datenbankdatei, überschreibt nie die konfigurierte Live-Datenbank und führt keine Schema-Migration aus. Die Recovery-Probe erfolgt isoliert; Offhost-Sicherung bleibt Betreiberaufgabe.
- REQ-058: Garage, Sicherungen und Einstellungen als getrennte, per Hash navigierbare Ansichten bereitstellen. Die mobile Navigation ist per Taste bedienbar; Escape schließt sie mit Fokus-Rückgabe, Außenklick schließt sie ohne Fokusdiebstahl. Browser-Zurück stellt die Garage-Ansicht einschließlich ausgewähltem Fahrzeug und ungespeichertem Editorentwurf wieder her; der Ansichtswechsel schreibt oder verwirft keinen Formularinhalt. Fahrzeuge hinzufügen bleibt in Garage, JSON-/SQLite-Downloads und Offline-Wiederherstellungshinweis liegen unter Sicherungen, Version und Bewegungspräferenz unter Einstellungen. `system` respektiert `prefers-reduced-motion`; `reduce` und `system` werden lokal gespeichert und beeinflussen die sanfte Kartennavigation.
- REQ-059: Belegdatum und Kilometerwert sicher korrigieren können. Record und zugehöriger Messwert müssen explizit und dauerhaft verknüpft sein; unbekannte Legacy-Beziehungen bleiben unverknüpft, bis der Eigentümer sie ausdrücklich bestätigt. Verknüpfte Änderungen erfordern beide erwarteten Revisionen, eine Begründung und eine idempotente Befehls-ID und aktualisieren Record, Messung und Audit atomar. Manuelle Messungen und Datumsänderungen an Belegen ohne Messung haben getrennte, begrenzte Operationen. Einheit, Fahrzeug, Arbeitsart/-kosten, Bereitschaft und Issue-Abschluss bleiben unverändert; höchstens drei Nachkommastellen, auch `0`, bleiben exakt als Dezimaltext erhalten. Änderungen warnen, wenn sie die nach Datum und Messungs-ID bestimmte aktuelle Anzeige verändern.
- REQ-060: Optional eine exakte Jahresnutzung je Fahrzeug speichern (`annualUsage`, `null` oder Dezimalstring 0–1.000.000.000 mit höchstens drei Nachkommastellen; `0` ist gültig). Eine read-only-Projektion schätzt aus dem neuesten tatsächlichen Messwert nach Datum absteigend und bei Gleichstand nach Messungs-ID, beschriftet Schätzung, Ankerdatum, `asOf` und Einheit und schreibt niemals eine geschätzte Messung. Ein Garage-Hinweis fragt standardmäßig 30 Tage nach dem letzten tatsächlichen Stand nach einem neuen abgelesenen Stand; Intervall 1–3650 Tage ist konfigurierbar, `null` deaktiviert den Hinweis. Ein fehlender Stand zeigt den Bedarf einer Erfassung; ein zukünftiger oder einheitsinkonsistenter Anker blockiert die Projektion und verlangt eine Prüfung; eine rechnerisch außerhalb des Wertebereichs liegende Schätzung bleibt ohne Schätzwert. Ein fälliger oder fehlender Stand öffnet ein leeres tatsächliches Messwertformular, ein Prüfhinweis öffnet die Historie. Nur explizites Speichern erzeugt einen Stand. Keine Telegram-Nachricht oder externe Erinnerungsintegration in diesem Schritt.

Der erste eigenständige Entwicklungsstand umfasst Fahrzeuge, unabhängige Fahrbereitschaft/offene Punkte, Kilometer, Service-/Reparaturbelege, Verlauf und Backup. Die abgeschlossenen Vorgänge und Kilometerstände lassen sich inzwischen vollständig, gefiltert und seitenweise browsen. Implementiert sind begrenzte Belegkorrekturen an Beschreibung, Art, Kosten, Währung und Dokumentreferenz sowie begründete, revisionsgeschützte Datums-/Kilometerkorrekturen mit Audit-Verlauf und bestätigter Messwert-Provenienz. Bestehende offene Punkte können ein optionales Fälligkeitsdatum, einen vom Nutzer gesetzten Schweregrad (`observation`, `repair`, `critical`; `null` bedeutet nicht eingestuft) sowie `open`/`observed` als aktive Lebenszyklen erhalten. Ein lesendes Dashboard zeigt überfällige, heute fällige, kommende und undatierte Punkte mit Europe/Berlin-Tagesgrenzen. Ein gespeicherter HU-Monat erzeugt zusätzlich einen abgeleiteten Status und kann nach der dokumentierten Betreiberregel die Readiness-Projektion auf `not_ready` setzen; die manuelle Fahrbereitschaft und offene Punkte bleiben unverändert. Das ist keine Rechtsauskunft oder Bewertung einer gesetzlichen Frist. Das Dashboard für offene Arbeit ist ein begrenzter Arbeitsstatus für vorhandene Punkte, noch kein vollständiges technisches Logbuch: Diagnoseereignisse, Schweregrad-Historie, Wiederholungsfälle, wiederkehrende Intervalle und Erinnerungen bleiben offen. Anhänge, Teile, Telegram, Kalender und KI bleiben weitere Arbeitspakete. Die bestehenden Anforderungen werden dadurch nicht gestrichen.

## Klarstellung zum Betriebsmodell vom 2026-10-27

Der Nutzer betreibt die Anwendung für sich. Cloudflare Access ist der gewünschte Eingang; nach erfolgreicher Anmeldung erhalten zugelassene Nutzer volle Adminrechte. Eine rollen-, fahrzeug- oder dokumentbezogene Trennung **zwischen** angemeldeten Webnutzern ist kein Produktziel. Das erlaubt es nicht, die Anwendung für nicht angemeldete Personen über einen direkten Originweg zu öffnen. Telegram bleibt ein separater Zugang mit eigener ID-Allowlist und Bestätigungen. REQ-020/043 zu Historie und Änderungsprotokoll bleiben bestehen; deren genaue native Abdeckung wird geprüft, ohne zusätzliche Details als bereits beauftragt zu unterstellen.

## Offene Entscheidungen
- Vollständigkeit des späteren LubeLogger-Imports und konkreter Schreibwechsel; der eigenständige Kern ist als Ziel entschieden.
- Kalender: eigene Kalender-ID, Ereignisidentität, Duplikatvermeidung und Ausnahmen bei HU-Fälligkeiten.
- KI-Anbieter, Kostenbudget und Datenschutz bei Dokument-/Historienübermittlung.
- Speicherung technischer Logbucheinträge und Anhänge.
