# Fälligkeiten, Kilometerprognose und Kosten — vorgeschlagene Fachregeln

Stand: 2026-10-26. **Planung, keine Implementierung und keine bestandenen Tests.** Die folgenden Regeln konkretisieren REQ-003–015/032/045/049 für den empfohlenen Garage-Regel-Owner ab v1.1. Diese Auswahl, v1.0-Übergang und Kalender30 bleiben nach ADR-0001/0004 offen. Intervalle in Beispielen sind ausschließlich synthetische Rechenparameter, keine Hersteller- oder Rechtsvorgaben.

Grundlage: [Domainmodell](domain-model.md), [Laufzeitbericht](../discovery/lubelogger-runtime-verification.md). Der Runtimebefund `DueDays`/`Urgency`, GET-Autorefresh und Custom-Threshold-Reihenfolge begründet eine eigene, eindeutig definierte Fachberechnung; er autorisiert keine direkte Änderung an Provider-Interna. Im jetzigen Schritt werden keine Dienste gestartet.

## Zeit-, Einheiten- und Quellenvertrag

Fachliche Eingaben sind ISO-`LocalDate`; `today = LocalDate(clockInstant, Europe/Berlin)`. UTC-Instants gelten für Erfassung, Bestätigung und Audit. Jeder Test injiziert eine feste Clock; `now()` ist keine versteckte Rechenabhängigkeit. Ein Datum ohne Uhrzeit wird nicht durch Umrechnung von UTC-Mitternacht abgeleitet. Tagesdifferenz ist `dueDate − today` in lokalen Kalendertagen; Tagesintervalle sind `plusDays`, Monate `plusMonths`, niemals 24-Stunden- bzw. 30-Tage-Näherungen.

Eine Herstellerregel braucht freigegebene Quelle, passende Fahrzeug-/Motoranwendung, Intervall und Prüfdatum. Ist eine Quelle unklar, gilt `requires_review`, nicht „KI hat ein plausibles Intervall gefunden“. Ein ausdrücklich bestätigtes Nutzerintervall ist zulässig und als `user` gekennzeichnet; es darf keine Herstellerbehauptung erhalten. Bestätigte einzelne Termine dürfen ohne erfundene Wiederholungsregel existieren. Diese Spezifikation setzt keine rechtlichen HU-Fristen fest.

Kilometer haben explizite Einheit. Negative/uneindeutige Werte, Betriebsstunden oder unbestätigte Meilenumrechnung werden abgewiesen bzw. zur Klärung vorgelegt. MVP verwendet ganze Kilometer; Anbieterwerte werden mit Raw-Wert/Einheit beobachtet und nicht aus Feldnamen allein normalisiert. Widersprüchliche oder veraltete Daten bleiben sichtbar.

## DS-01 — fachlicher Fälligkeitszustand

Für jede bestätigte Datums-/km-Grenze getrennt berechnen:

| Dimension | `overdue` | `due_now` | `future` | `unknown` |
| --- | --- | --- | --- | --- |
| Datum | `today > dueDate` | `today == dueDate` | `today < dueDate` | Grenze fehlt/Quelle strittig |
| Kilometer | `confirmedCurrentKm > dueKm` | `confirmedCurrentKm == dueKm` | `confirmedCurrentKm < dueKm` | erforderlicher Stand/Einheit ungeklärt |

Bei Both gewinnt `overdue` vor `due_now` vor `future`; mindestens eine unbekannte erforderliche Dimension verhindert eine verlässliche grüne Gesamtaussage. Eine bekannte überfällige Grenze bleibt auch bei anderer unbekannter Dimension überfällig. Ergebnis enthält immer Einzelzustände und Datenstand; `future` ist nur dann vollständig bekannt, wenn alle erforderlichen Dimensionen bewertbar sind.

„Was zuerst eintritt“ bedeutet jede Grenze ist unabhängig verbindlich; keine Umrechnung von Kilometern in Tatsachentage. Kilometerprognosen dürfen eine **geschätzte** Zeitwarnung begründen, aber weder Durchführung noch tatsächliche Überschreitung beweisen. Ampel: bestätigt kritisch/überfällig rot, fällig/heute oder innerhalb konfigurierter Vorwarnung gelb, vollständig bekannte spätere Fälligkeit grün, fehlende/strittige Grundlage ausdrücklich ungeklärt. Problem-Schweregrad wird separat angezeigt und kann die Gesamtpriorität erhöhen.

Vorwarnschwellen `warningDays`, `warningKm` sind nichtnegative konfigurierbare Werte pro Regel oder explizitem globalen Default. Vergleich inklusiv: `0 ≤ remainingDays ≤ warningDays` bzw. `0 ≤ remainingKm ≤ warningKm`. Keine veränderliche Threshold-Variable von einer Aufgabe zur nächsten übernehmen. Bei Quellenkonflikt kommt ein sichtbarer Reviewhinweis hinzu; eine unbekannte Zukunft darf nicht als „alles erledigt“ erscheinen.

## DS-02 — Fortschreibung ausschließlich nach bestätigtem Ereignis

`one_off`: Nach bestätigter Durchführung abgeschlossen, kein Folgetermin. Erfassung einer neuen Wartung erledigt nur die ausdrücklich ausgewählten `taskId`s. Beschreibungsgleichheit oder ein allgemeiner LubeLogger-Servicebeleg ist keine automatische Zuordnung. Jede bestätigte Durchführung erhält `completionId`, Datum, Quelle/Actor und bei Kilometerintervall den tatsächlich bestätigten Stand; bereits bekannte Erfassung wird nicht erneut durchgeführt. Bei Annahme werden lokale bestätigte Durchführung, Audit, fachlich vollständig berechenbare neue DueState und Outbox atomar gespeichert. Der LubeLogger-Kosten-/Wartungsbeleg folgt asynchron. Anzeige und Command-Ergebnis unterscheiden „Durchführung lokal bestätigt“ von „LubeLogger-Beleg pending/failed/uncertain“. Ein unklarer externer Ausgang nimmt die bestätigte tatsächliche Durchführung nicht still zurück und löst keine zweite lokale Erledigung aus.

`after_completion`: nächste Datumsgrenze = tatsächlich bestätigtes `performedOn + interval`, nächste Kilometergrenze = `performedKm + intervalKm`. Fehlen erforderliche Werte, keine erfundene Basis; fehlende Dimension `requires_review`, keine vollständige Fristprojektion. Frühere/verspätete Durchführung verschiebt die Basis bewusst.

`fixed_anchor`: Aufgabe besitzt ursprünglichen bestätigten Anker und eine ganzzahlige `occurrenceIndex`. Datumsgrenze für Index n wird **direkt** aus `anchorDate + n × interval` berechnet, Kilometergrenze aus `anchorKm + n × intervalKm`. Keine Verkettung bereits geklemmter Monatsdaten. Nach einer Durchführung Index um genau einen erhöhen; keine Schleife, die mehrere verpasste Zyklen als erledigt überspringt. Ein danach weiterhin vergangener Termin bleibt überfällig. Gewünschtes Überspringen/Neuverankern braucht eigenen angezeigten, bestätigten Regeländerungsauftrag.

Monatsregel: Tage, die der Zielmonat nicht hat, auf dessen letzten Tag klemmen. Bei festem Anker bleibt der ursprüngliche Tag über Folgezyklen erhalten: 31. Januar → Februarende → 31. März. Bei `after_completion` ist dagegen das neue tatsächliche Durchführungsdatum der Anker. „Immer Monatsletzter“ ist ein eigener gegebenenfalls später freizugebender Modus, keine implizite Folge jedes 30./31.-Datums.

Regeländerung erzeugt neue immutable `ruleRevision`; bestätigte neue Fälligkeit erzeugt neue `dueRevision`. Countdown, Prognose-Refresh und reines Lesen erzeugen keine bestätigte Friständerung. LubeLogger-GET-Autorefresh bleibt im vorgeschlagenen Aufbau aus. Provider-Reminder spiegeln höchstens konkrete Werte, nicht eine zweite fortschreibende Wahrheit.

## DS-03 — Rückdatierung und Korrektur

Kilometerbeleg führt Erfassungszeit (`recordedAt`) und fachliches Datum (`recordedOn`). Rückdatierung ist zulässig, sofern zeitlich benachbarte gültige Stände in derselben Distanz-Epoche monoton bleiben. Sinkende Stände erfordern eine angezeigte Korrektur oder einen bestätigten Tachowechsel/Epochenwechsel; kein stilles Zurücksetzen der Lebenslaufdistanz. Originalbeobachtung und Begründung bleiben nachvollziehbar. Ein falscher hoher alter Stand darf nach bestätigter Korrektur nicht weiter jede Garage-Prognose dominieren; Provider-Maximalstand-/UI-Abweichung wird als Konflikt angezeigt.

Automatisch aus Wartung entstandene Kilometerbelege und manuelle Belege mit gleichem Datum/gleichem Stand werden für Prognosen zusammengefasst, bleiben aber als unterschiedliche Quellen referenziert. Unterschiedliche Stände desselben Datums benötigen verlässliche Messreihenfolge oder Nutzerauflösung; nicht nach Belieben den höchsten Wert als „letzte Messung“ auswählen.

Rückdatierte Durchführung wird nicht nach Eingabereihenfolge zur neuesten Wartung. Effektive Basen nach fachlichem Datum und bestätigter Zuordnung zum Zyklus bestimmen. Zwei konkurrierende Durchführungen desselben Zyklus sind ein Konflikt. Korrektur referenziert `supersedesCompletionId`; Regel und nachfolgende Durchführungen werden in der Vorschau neu bewertet. Korrektur eines älteren Zyklus verschiebt nicht still bereits bestätigte spätere Basen. Ein noch nicht eindeutig auflösbarer Zyklus bleibt `requires_review`.

## DS-04 — HU und Kalender als bestätigte Projektion

HU-Durchführung, amtliche/anderweitig bestätigte nächste Fälligkeit und zugrunde gelegte Quelle getrennt speichern. Fehlt eine belastbare Regel oder liegt eine Ausnahme vor, fragt der Assistent die nächste bestätigte Fälligkeit ab; er setzt nicht pauschal „Durchführung + 24 Monate“. Ein künftig freigegebenes fahrzeugspezifisches Regelprofil darf einen **Vorschlag** erzeugen, der nächste Fälligkeit vor Änderung bestätigen lässt. Ein im Anforderungstext genannter Regelfall ersetzt diese Quellen-/Ausnahmeprüfung nicht.

Liegt nur ein bestätigter Fälligkeitsmonat vor, `precision=month` bewahren. Für interne Sortierung/Erinnerung den letzten Tag dieses Monats als operativen Vergleichstag vorschlagen und als solchen kennzeichnen; daraus folgt keine neue rechtliche Tagesbehauptung. Monat und abgeleiteter Vergleichstag dürfen nicht verwechselt werden. Ein vorgegebener genauer Tag behält `precision=day`.

Nach bestätigter Fälligkeitsänderung Mapping des HU-Tasks aktualisieren, keine starre 24-Monats-Wiederholungsserie erzeugen. Haupttermin ganztägig: `start.date=dueDate`, `end.date=dueDate+1 Tag`, Beschreibung zeigt gegebenenfalls Monatsprecision. `taskId` und `eventId` bleiben über die nächste HU gleich; `dueRevision` steigt. Ein fehlgeschlagener Kalendersync ist sichtbar und blockiert keine bereits bestätigte lokale Durchführung. Manuelle Kalenderabweichung erzeugt Konflikt, keine stille neue Fachfrist.

**Kalender30 bleibt offen:** Der nachgewiesene native Kalender-Reminder erreicht keine 30 Tage. Ein separates `notice30`-Ereignis am `dueDate−30 Tage` mit eigener stabiler ID ist nur der Vorschlag aus ADR-0004; kein automatischer Ersatz und keine stillschweigende Kürzung auf 28 Tage. Telegram-30-Tage-Versand ist eine andere Anforderung.

## DS-05 — tägliche Erinnerungen und Ausfallnachholung

Tägliche Prüfung nach vorgeschlagener konfigurierbarer Ortszeit, beispielsweise 09:00 Europe/Berlin. Das ist eine Produktkonfiguration, kein in dieser Phase gestarteter Job. Tageslauf-ID ist lokales Datum; zwei Prozessstarts am selben Tag erzeugen keinen zweiten fachlichen Versand. Für DST-unmögliche Laufzeit ersten gültigen Zeitpunkt danach nehmen, bei doppelter Uhrzeit erste Ausprägung; Unique-Tageslauf verhindert Doppelverarbeitung.

Eligibility für Offset N: `today ≥ dueDate−N Kalendertage`, Task nicht erledigt, Quelle gültig, aktuelle `dueRevision`, keine bereits erfolgreiche oder unklare Zustellung dieses Schlüssels. Nach Ausfall innerhalb mehrerer Offsets keine veraltete Nachrichtenserie versenden: pro Task/Kanal nur den aktuell dringlichsten noch relevanten Hinweis auswählen und übersprungene Offsets nachvollziehbar als überholt markieren. Eine Tagesprüfung erzeugt keine tägliche Wiederholungsserie, sofern diese nicht ausdrücklich konfiguriert wurde.

Unique-Zustellschlüssel `(taskId,dueRevision,channel,offsetDays)`. Vor Versand nochmals aktuelle Revision/Erledigung prüfen. Alte ausstehende Revisionen verwerfen; gesendete Historie behalten. Eine geänderte bestätigte Frist kann einen neuen Hinweis rechtfertigen, muss dann als **Friständerung** erkennbar sein; nicht bloß erneut dieselbe Nachricht senden. `uncertain` bleibt sichtbar und wird nicht blind wiederholt: lokale Eindeutigkeit garantiert keine externe Exactly-once-Zustellung. Bei Kilometerprognose im Text ausdrücklich „geschätzt“, Datenstand und bestätigtes Kilometerziel nennen.

## DS-06 — deterministische Kilometerprognose

Vorschlag für einen einfachen überprüfbaren Startalgorithmus statt behaupteter Genauigkeit: konfigurierbares Fenster 90 lokale Tage, mindestens 14 Tage Messabstand, mindestens zwei unterschiedliche Messtage, letzte bestätigte Messung höchstens 30 Tage alt. Dies sind zu bestätigende Produktparameter, keine Fahrzeugwartungsintervalle. Nur nach DS-03 bereinigte monotone Messungen gleicher bestätigter Einheit/Epoche, kein zukünftiges Messdatum; fehlen Bedingungen, `forecast=unavailable` mit Grund.

Aus ältester und jüngster Messung im Fenster `rate=(lastKm−firstKm)/calendarDays(firstOn,lastOn)` als exakter Dezimal-/Bruchwert bilden; erst Anzeige runden. Rate ≤ 0 ergibt keine zeitliche Prognose. Keine lineare Prognose über ungeklärten Tachowechsel hinweg. Ändernde mittlere Fahrleistung und Datenlücken sind Unsicherheit, kein statistisch belegtes Konfidenzintervall.

Für Kilometerziel größer als letzter bestätigter Stand: `estimatedDueOn = lastOn + ceil((dueKm−lastKm)/rate) Tage`. **Anker ist letztes Messdatum, nicht Abfragetag**; sonst verschiebt sich die Prognose beim bloßen Warten ständig nach hinten. Ziel am/unter letztem Stand ist bereits fachlich fällig/überfällig, keine Zukunftsschätzung. Vergangenes Schätzdatum bei noch nicht bestätigter Überschreitung heißt „geschätzte Fälligkeit erreicht, neuen Stand erfassen“, nicht erwiesene Überschreitung. Bei Both ist prognostische Warnzeit die frühere bekannte Datumsfrist bzw. geschätzte Kilometerzeit, wobei Tatsachenfrist und Schätzung getrennt bleiben.

Prognose enthält Algorithmus-/Parameterrevision, beide Referenzmessungen, Stichtag, bereinigten Datenhash, Rate, Ergebnisdatum und Datenalter. Neue Messung/Korrektur aktualisiert `projectionRevision`, nicht automatisch die bestätigte `dueRevision` oder Wartungshistorie.

## DS-07 — Kosten und Zahlungen ohne Doppelzählung

LubeLogger bleibt Quelle der vorhandenen Vorgangskosten. Beträge mit Währung und Originalpräzision lesen; kein Float und keine stille Änderung beim Import. Manuell eingegebene EUR-Vorgangsbeträge höchstens zwei Dezimalstellen, zusätzliche Stellen vor Bestätigung klären. Intern Rechenschritte mit ausreichender Dezimalpräzision; Schlussrundung für Darstellung erst am Ende nach festgelegtem `HALF_UP`. Verschiedene Währungen nicht ohne expliziten Kurs-/Stichtagsvertrag summieren.

**Vorgangskostenansicht:** je bestätigtem Wartungs-/Reparatur-/Steuer-/Versicherungsvorgang genau dessen vollständigen Betrag einmal zählen. Eigenarbeit braucht keinen erfundenen Stundenlohn; dokumentierte Dauer bleibt getrennt. Teileverwendung zeigt Herkunft/Menge/Kostenanteil, wird aber nicht nochmals auf einen bereits vollständigen Rechnungsbetrag addiert. Die Sandbox belegt nur ausdrücklich übergebenen Gesamtbetrag, keine automatische korrekte Summierung. Jahreszuordnung nach fachlichem Vorgangsdatum, nicht Erfassungszeit. Korrekturen ersetzen die aktive Projektion, bleiben im Audit nachvollziehbar; negative Beträge nur als ausdrücklich verknüpfte Gutschrift nach gesonderter Vertragsprüfung.

**Zahlungshistorie:** Kaufdatum, Zahlungsdatum und Verwendungsdatum sind unterschiedliche Fakten. Ein veränderlicher Restlagerwert beweist weder ursprünglichen Kaufpreis noch Zahlung. Für echten Cash-Jahresbericht jeden belegten Zahlungsvorgang genau einmal am bestätigten Zahlungsdatum zählen; Rechnungsbetrag und seine Teileanteile sind keine weiteren Zahlungen. Quelle/Owner eines gegebenenfalls zusätzlich nötigen Zahlungsmodells ist vor B07 ausdrücklich zu entscheiden. Bis dahin Ansicht „Vorgangskosten“ benennen und REQ-015-Zahlungshistorie nicht als vollständig gelöst markieren.

## Deterministische Testvektoren — später auszuführen

Alle Beispiele sind synthetisch. Erwartete Werte sind Soll-Spezifikation, keine bereits bestandenen Tests. Sofern nicht anders angegeben sind Quellen als bestätigte Nutzerintervalle angelegt, aktuelle Messungen gültig und Clock/Zeitzone wie angegeben.

| ID | Eingabe | Erwartung |
| --- | --- | --- |
| DV-01 | Clock `2026-10-25T23:30:00Z`, Europe/Berlin; Frist `2026-10-26` | `today=2026-10-26`, `remainingDays=0`, `due_now`, nicht überfällig. |
| DV-02 | Heute `2026-10-26`; Fristen `2026-10-25`, `2026-11-02`, `2026-11-25` | `remainingDays=−1/7/30`; `overdue/future/future` vor Warnschwellen. Keine Übernahme der Providerwerte −1/6/29. |
| DV-03 | Heute `2026-10-26`; Both Frist `2026-12-01`/20000 km; Stand 19999/20000/20001 | `future/due_now/overdue` aus km-Grenze; Datum bleibt Zukunft. |
| DV-04 | Both Frist gestern und unbekannter Stand; Both Frist morgen und unbekannter Stand | Erster Fall `overdue` mit unbekannter km-Dimension; zweiter `requires_review`/unvollständig, keine verlässliche grüne Gesamtanzeige. |
| DV-05 | Warnung Tage=7, Strecke=100; heute D, Frist D+7/aktueller Stand+100 | Exakte Grenzwerte inklusive; Warnung gelb. D+8/+101 ohne andere Fälligkeit außerhalb der Warnung. |
| DV-06 | Monatsanker `2028-01-31`, fixed, 1 Monat, n=1/2/3 | `2028-02-29`, `2028-03-31`, `2028-04-30`; kein März-29-Drift aus verketteter Zwischenfrist. |
| DV-07 | Anker `2028-02-29`, Intervall 12 Monate | Nächste synthetische Frist `2029-02-28`; keine Rechts-/Herstellerbehauptung. |
| DV-08 | Tagesbasis `2026-03-28` bzw. `2026-10-24`, Intervall 2 Tage | `2026-03-30` bzw. `2026-10-26`; lokale Kalendertage trotz 47/49 Stunden zwischen lokalen Mitternachten. |
| DV-09 | after_completion: bestätigt `2026-10-10`, 10500 km; synthetisch 2 Monate/1000 km | Nächste Frist `2026-12-10`/11500 km; Erfassung am 20.10. ändert Basis nicht. |
| DV-10 | fixed: Anker `2026-01-31`, Monatsintervall, aktueller Zyklus n=1; eine bestätigte Durchführung am 10.05. | Nächster Index n=2 → `2026-03-31`, weiterhin überfällig. Keine fiktiven Durchführungen zum Überspringen. |
| DV-11 | One-off am 10.10. bestätigt; derselbe Command zweimal bestätigt | Ein `completionId`, Task abgeschlossen, kein neuer Reminder/Folgetermin/zweiter externer Auftrag. |
| DV-12 | Bestehende Bestätigung Zyklus Oktober, nachträglich Septemberbeleg ohne explizite Zykluszuordnung | Vorschau/Klärung; keine automatische Ersetzung der Oktoberbasis nach Erfassungsreihenfolge. |
| DV-13 | Messungen 01.10.=10000, 20.10.=11000; Nachtrag 10.10.=10500 bzw. 11500 | 10500 passt; 11500 ist nichtmonoton und braucht Korrektur/Epochklärung. Keine negative Rate aus stiller Annahme. |
| DV-14 | Manueller und automatisch erzeugter Beleg am 01.10. beide 10000 | Für Prognose ein Messpunkt mit zwei Provenienzen. Zwei verschiedene Werte ohne Zeitreihenfolge sind Konflikt statt willkürlicher Auswahl. |
| DV-15 | Regelquelle unbestätigt; ähnlich klingende Intervallangabe aus KI | `requires_review`; kein Fristfortschreiben, Kalenderauftrag oder Herstellerfakt daraus. |
| DV-16 | HU-Durchführung 10.10.2026, bestätigter nächster Monat `2028-10` | Precision month, operativer Vergleichstag `2028-10-31` ausdrücklich abgeleitet; nicht pauschal `2028-10-10`. Haupttermin-Enddatum `2028-11-01`. |
| DV-17 | HU-Durchführung ohne verifizierte Folgeregel und ohne bestätigte nächste Fälligkeit | Nachfragen/Review; weder 24-Monats-Automatik noch erfundener Kalendertermin. |
| DV-18 | Frist `2026-04-28`; Offset30 | Eligibility ab `2026-03-29` als LocalDate; DST ändert nicht den Tag. Kalender-`notice30` bleibt bis Entscheidung deaktiviert. |
| DV-19 | Ausfall bis 5 Tage vor Frist, Offsets30/7 beide nie gesendet | Ein aktueller 7-Tage-Hinweis als verspätete Nachholung; kein unmittelbarer 30-Tage-und-7-Tage-Nachrichtenstapel. |
| DV-20 | Versandstatus `uncertain`, derselbe Task/Revision/Kanal/Offset erneut fällig | Keine blinde Wiederholung; sichtbare Klärung, keine fälschlich behauptete Deduplizierung bei Telegram. |
| DV-21 | Prognose: heute 31.01.2026; 01.01.=10000, 31.01.=10600; Ziel12000 | Rate20 km/Tag; Rest1400→70 Tage ab 31.01. → `2026-04-11`, ausdrücklich geschätzt. |
| DV-22 | Dieselben Messungen, heute 05.02.2026 | Prognose weiterhin `2026-04-11`, nicht 70 Tage ab 05.02.; letzter Datenstand 31.01., Alter5 Tage sichtbar. |
| DV-23 | Nur eine Messung, zwei Messungen am selben Tag, Differenz0, Messabstand13 Tage oder letzter Stand31 Tage alt | Jeweils keine Prognose mit nachvollziehbarem Grund; kein unendliches Datum oder Division durch0. |
| DV-24 | Prognose rate3 km/Tag, letzter Stand10000 am 01.01.2026, Ziel10010 | `ceil(10/3)=4` → geschätzt `2026-01-05`; keine Abrundung auf den 04.01. |
| DV-25 | Parts Einkauf2 Stück/20 EUR; Verwendung1 Stück/10 EUR in bestätigtem Gesamtvorgang15 EUR | Restlager1/10; Vorgangskosten15 einmal, nicht25 oder35. Cashbericht kann Zahlung20 separat zeigen, zählt Teileanteil10 nicht nochmals als Zahlung. |
| DV-26 | Vorgang 31.12.2026, Zahlung02.01.2027, erfasst03.01.2027 | Vorgangskosten2026; belegte Cashzahlung2027; Erfassungsdatum verschiebt keine Fachjahre. |
| DV-27 | Ein Vorgang10 EUR und ein Vorgang12 USD ohne Kursvertrag | Getrennte Währungssummen, keine fiktive Gesamtsumme22 EUR. |

Vor Implementierung diese IDs in automatisierte Fachtests übertragen; Clock, Policyrevision, Quell-/Ownerstatus und Eingabedaten vollständig in Fixtures angeben. Bestehende B02-Charakterisierung bleibt davon getrennt: Ein bewusst von LubeLogger abweichender Sollwert ist kein nachträglich als bestanden deklarierter Upstream-Test.
