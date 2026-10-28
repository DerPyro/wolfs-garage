# Qualitätsgates und Abnahmevertrag

Stand: 2026-10-27. **Geplante Tests; separat ausgewiesene isolierte Laufzeitnachweise beachten.** Ein Cloudflare-Login, globale Adminrechte für zugelassene Nutzer: [ADR-0008](../adr/0008-single-user-access.md). Ältere Tests unterschiedlicher interner Webrollen charakterisieren den Provider, sind kein eigenständiges Produktgate. Bisher tatsächlich ausgeführt: [B01/B02, 62 Checks](../discovery/lubelogger-runtime-verification.md). Lokal prüfbare neue Spezifikationsartefakte sind davon getrennt: Schema-/Beispielvalidierung ist kein Nachweis eines laufenden Servers oder einer erfüllten Produktanforderung.

## Evidenzformat

Jeder spätere Test hält Fall-ID, Requirements, genaue Version/Digest, synthetische Fixtures, Rolle/Fahrzeug, konfigurierten Zeitpunkt/Zone, Trigger, erwartete Änderung/Nichtänderung, beobachtetes Ergebnis, pass/gap/fail und bereinigte Artefaktreferenz fest. Für einen Abweisungsfall nicht nur HTTP-Status prüfen, sondern fehlende Daten und unveränderten Bestand. Für externe Writes zusätzlich fachlichen Erfolg und Reconciliation prüfen. Screens/Logs enthalten weder echte Dokumente noch Secrets.

## Gate-Matrix

| Gate / zugehörige Pakete | Mindestnachweis | Stopbedingung |
| --- | --- | --- |
| Q01 Vertrag / WP03 | Positive und negative JSON-Beispiele; eindeutige IDs/Enums, actor/chat nicht clientsetzbar, Datum-/Geld-/Ereignispflichtfelder; alle OpenAPI-Refs lokal auflösbar | Formverträge widersprechen Fachtext oder Clients können Bestätigung/Actor übernehmen |
| Q02 Domäne / WP06/WP09 | Alle deterministischen Vektoren aus [due-date-spec.md](due-date-spec.md); heute vs. überfällig, beide Grenzen, Fixed/Flexible, Monatsende, Schaltjahr, Berlin-DST, Rückdatierung und Quelle | Wartung erfunden, Frist ohne Durchführung verschoben, fehlende Quelle als Herstellerregel ausgegeben |
| Q03 Persistenz / WP06 | Einmalige Bestätigung bei zwei parallelen Requests, atomare Fachbestätigung/Audit/Outbox, optimistic conflict, Append-only-Regel-/Problemlog, Lease-Absturz | Doppeltes Ereignis/Outbox oder stiller Historienverlust |
| Q04 Provider / WP07 | Gepinnter LL-Zielstand, Invariant-Roundtrips, Unit-/Capability-Prüfung, Success=false/200, 401/403/5xx, Writeantwortverlust und unklare Operation | Nicht-idempotenter Retry ohne Abgleich; nicht unterstützte Felder still ignoriert |
| Q05 Security / WP01/WP05/WP10 | Access-Anmeldung, nicht zugelassene Identität, alternative App-/Dokumentpfade, Origin-Bypass, CSRF und Dienstzugänge | Unangemeldeter oder nicht zugelassener Zugriff auf App/Dokumente bzw. nicht geprüfter Origin-Bypass möglich |
| Q06 Bot / WP08 | Fremde/fehlende numerische ID, privater Chat, Callbackbindung/Ablauf, doppeltes Update, Restartoffset, derselbe Command bei erneutem Bestätigen, unklarer Versand | Datenzugriff vor Autorisierung; doppelte Änderung durch Update-Replay |
| Q07 Scheduler/Kalender / WP09 | D−30/D−7, tägliche Berlin-Zeit, Ausfall über mehrere Tage, Fälligkeitsrevision, 409/412/gelöschter Termin, 30-Tage-Alternative nach Entscheidung | Doppelte Hauptevents/Reminder, Feiertag/DST als Sekundenfehler, alte Revision versendet |
| Q08 Dokumente / WP10 | Admin-Originalabruf, nicht über Access zugelassener Aufruf, fehlendes Dokument, vertrauenswürdige Basis-URL, keine Tokenlinks, gleiche ID nach Restore | Unangemeldeter Dokumentzugriff oder ungeprüfte Serviceidentität umgeht Access |
| Q09 Oberfläche / WP02/WP11 | [UI-Szenarien](product-flows.md), responsive 320/768/1280px, Tastatur/Fokus, beschriftete Ampel, leere/alte/fehlerhafte Zustände | Stale wird grün als vollständig aktuell angezeigt; Status pending als gespeichert dargestellt |
| Q10 Betrieb / WP05 | Konsistentes Backup inklusive Keys, getrennt/offsite entschlüsselt, isolierter Restore, gemessene Ziele, Job-/Egresssperre, Versionsrollback mit passendem Datenstand | Restore erzeugt externe Writes, Keys fehlen oder Recovery öffnet Auth |
| Q11 KI später / WP12 | Freigabeumfang/Quellen/Unsicherheit/OCR-Rückfrage, Prompt-Injection-Corpus, keine Write-/Secretrechte, Budgethärte, Ausfall ohne Blockade | Unbestätigte Diagnose/Intervall als Fakt; unfreigegebene Historie verlässt System |

## Testaufbau und Werkzeugwahl vor Umsetzung

Reine Fachberechnung mit injiziertem Clock/LocalDate und kleinen Tabellenvectoren prüfen. Persistenz atomar gegen die gewählte echte Engine testen; ein In-Memory-Ersatz beweist PostgreSQL-/SQLite-Locks nicht. Providerverträge gegen gepinnte reale Sandbox plus kontrollierten Fehler-/Antwortverlustproxy prüfen; ein Mock allein beweist keinen externen Vertrag. Bot per aufgezeichneten synthetischen Updateformen und Testtransport testen, produktiver Token nicht erforderlich. UI-Tests gegen Testserver und rolegebundene Fixtures, visuelle Abnahme separat.

Konkrete aktuelle Library-/Buildversionen sind noch nicht gewählt und vor Implementation offiziell zu prüfen. Keine breite Testinfrastruktur vor dem ersten relevanten Modul bauen. Jeder Testsatz muss einen tatsächlichen Fehler-/Vertragspunkt abdecken; triviale Strukturduplikate ohne Aussagekraft vermeiden.

## Geplante Ausfall-/Konkurrenzszenarien

| Fall | Prüferwartung |
| --- | --- |
| Zwei Bestätigungen gleichzeitig | Genau ein lokaler akzeptierter Command/Facheffekt; zweiter Request zeigt denselben Zustand oder klaren Konflikt |
| Crash vor/innerhalb lokaler Transaktion | Entweder vollständiger Commit oder keine Fachänderung; kein allein übrig gebliebenes „erledigt“ ohne Audit |
| Crash nach lokalem Commit, vor Provideraufruf | Pending-Operation wird wiedergefunden, nicht ein zweiter Command erzeugt |
| Crash während LL-POST | Operation unklar; erst eindeutiger Abgleich, keine pauschale Lease-Retry-Doppelanlage |
| LL-Beleg unklar, tatsächliche Durchführung bereits bestätigt | Bestätigte Durchführung bleibt wahr; Frist-/Syncstatus sichtbar getrennt; kein zweites Erledigen als Fehlerbehandlung |
| Telegram-Sendeantwort verloren | Versand unklar anzeigen; beschlossene D09-Strategie, kein verstecktes Exactly-once-Versprechen |
| Kalender nach fachlichem Erfolg offline | Lokale Bestätigung bleibt bestehen, Projektion pending; gleiche Event-ID nach Wiederkehr |
| Rechteentzug zwischen Vorschau und Klick | Bestätigung abweisen, kein zusätzlicher Provider-/Dokumentzugriff |
| Provider direkt geändert/gelöscht | Drift/missing sichtbar; keine automatische stille Übernahme in Garage-Regelhoheit |
| Restore hinter bereits extern gesendeten Effekt | Journale gesperrt, externe Mappings abgleichen; keine neue ID oder Wiederholung aus altem Snapshot |
| Herstellerquelle entzogen/ungeeignet | Bestehende Historie erhalten, neue automatische Regelverwendung requires_review |

## Aktuelle Spezifikationsprüfung

Ausführbarer Dokumentationsprüfer: [validate_contracts.py](../../tests/planning/validate_contracts.py). Er prüft Schemas, Beispiele, gezielte unzulässige Payloads und lokale OpenAPI-Referenzen/Operation-IDs. Er greift auf keine Dienste zu. Eine vollständige OpenAPI-Toolchain-/Server-Conformanceprüfung wird nicht behauptet.

Zur späteren Definition of Done gehören neben passenden Tests: reproduzierbare Konfiguration, dokumentierte Sicherheitsannahmen, bedienbarer Pfad, aktualisierte Roadmap und bekannte Restgates. „Plan detailliert“ und „Test grün“ sind keine alleinige Freigabe zum Veröffentlichen.
