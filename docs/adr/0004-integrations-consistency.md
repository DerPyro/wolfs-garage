# ADR-0004 — Bestätigte Änderungen und ausfallsichere Integrationen

Status: **Vorgeschlagen** · Datum: 2026-10-26 · Entscheidung: offen

## Kontext und Evidenz

Telegram-Updates können wiederholt eintreffen; externe Schreibvorgänge können nach Timeout bereits erfolgreich sein. Kalender und Dokumentverwaltung sollen lokale Verwaltung nicht blockieren. Google Calendar begrenzt native Erinnerungen auf 40320 Minuten, also 28 Tage; REQ-011 mit 30 Tagen kann nicht unverändert durch einen einzelnen nativen Reminder umgesetzt werden. Quelle: [Events.insert](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert), geprüft 2026-10-26. Weitere Belege und konkrete Verträge: [Integrationsprüfung](../discovery/integration-contracts.md).

## Empfehlung

Änderungen aus natürlicher Sprache als versionierten, befristeten Entwurf mit Fahrzeug, Datum, Einheit und Quelle anzeigen. Bestätigung ist an User, privaten Chat, Payload und einmalige ID gebunden. Rechte und Datenversion unmittelbar vor Ausführung erneut prüfen. Änderungen in bestehender Fach-UI folgen deren validierten Formularen; KI/Bot darf Bestätigungen nicht umgehen.

Lokale Zustandsänderung und Outbox atomar speichern. Externe Effekte separat mit Status pending/succeeded/failed/uncertain abarbeiten. Keine behauptete Exactly-once-Garantie für LubeLogger; nach unklarem POST-Ergebnis zunächst abgleichen oder manuell klären. Bounded Retry mit Backoff für geeignete Fehler; keine automatischen POST-Wiederholungen bei unklarem Ausgang. Audit enthält Actor, Korrelations-ID und Ergebnis, keine Tokens/Dokumentinhalte.

Paperless-Dokumente per stabiler ID/Instanz referenzieren und Berechtigung bei jedem Abruf prüfen; keine dauerhaften öffentlichen Downloadlinks und keine automatische Duplikation. Ohne Paperless bleibt lokale Basisverwaltung benutzbar; Dokumentablage-Fallback vor v1.0 klären.

Kalender: eigener beschreibbarer Kalender, stabile Event-ID/Mapping und Update statt Neuanlage bei Terminverschiebung; manuelle Konflikte sichtbar machen. Vorschlag für REQ-011: HU-Hauptereignis mit nativem 7-Tage-Reminder und separates Erinnerungsevent am Tag HU minus 30 Tage. Das verändert Kalenderdarstellung und braucht eine Produktentscheidung; alternativ Anforderung auf maximal 28 Tage ändern. Telegram-30-Tage-Erinnerung erfüllt allein REQ-011 nicht. Keine stille Anforderungsänderung.

Zeitpunkte als UTC-Instant, fachliche Fälligkeiten als LocalDate mit Europe/Berlin. Kilometerprognosen als Schätzung; Herstellerregeln benötigen Quellen. HU-Folgemonate nicht ausnahmslos automatisieren: Fahrzeugklasse/amtliches Fälligkeitsdatum und Ausnahmeprüfung bestätigen lassen. Keine Rechtsregel wird durch einen pauschalen 24-Monats-Timer ersetzt.

## Alternativen und Folgen

Synchrone Ketten ohne Outbox sind einfacher, können aber Änderungen verlieren. Webhooks können später als Hinweis dienen; Polling/Abgleich bleibt Rückfallweg. Externe APIs dürfen unabhängig ausfallen; Jobs zeigen Rückstau und alte Daten transparent an.

## Offene Entscheidung und Nachweise

Kalenderdarstellung/ID/OAuth-Scope, Dokumentberechtigungen, Wiederholungs-/Deduplizierungsregeln und Bestätigungsdauer festlegen. Negativtests für fremde Telegram-ID, Wiederholung, Timeout, konkurrierende Änderungen, Sommerzeit, Schaltjahr und Kalenderkonflikte erforderlich.

## B02-Nachtrag: Datums- und Schwellen-Hoheit

Der [Laufzeitbericht](../discovery/lubelogger-runtime-verification.md) bestätigt: `DueDays` verwendet Restzeit statt lokaler Kalendertage (D+30→29, D+7→6); heutige Mitternacht gilt bereits als überfällig. Native GET-Autorefresh kann eine Frist ohne Durchführung weiterschieben. Zusätzlich beeinflusst ein Custom-Threshold-Reminder die Dringlichkeit nachfolgender Standard-Reminder.

**Offene Entscheidung B17:** Garage berechnet fachliche Tagesgrenzen selbst aus `DueDate` als LocalDate/Europe-Berlin; Provider-DueDays/Urgency sind nur Provideranzeigen. Native Auto-Refresh-Einstellung bleibt aus. Benutzerdefinierte Provider-Schwellen vorläufig nicht als verlässliche Regelbasis freigeben, bis korrigierte Version oder eindeutige eigene Schwellen-Hoheit nachgewiesen ist. Bei weiterer Nutzung der nativen Übersicht müssen ihre Abweichungen sichtbar sein. Kalender-/Scheduler-Semantik und endgültiger Regel-Owner bleiben mit B04 zu entscheiden.

Ein lokal vermittelter POST mit anschließendem Verbindungsabbruch wurde per Lesen eindeutig gefunden; ein zweiter identischer POST erzeugt dagegen ein Duplikat. Das bestätigt die vorgeschlagene Unknown/Abgleich-Behandlung, implementiert aber noch keinen produktiven Garage-Adapter. Webhooks mit zwei 500-Antworten wiederholten; fehlende Event-ID/Vorher-Nachherdaten bestätigen den Auditvorbehalt. ADR bleibt **Vorgeschlagen**.
