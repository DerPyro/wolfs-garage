# Produktabläufe und Web-Abnahme — Planungsentwurf

Stand: 2026-10-26. **Vorschlag, nicht angenommen; ausschließlich Dokumentation.** Keine neue Webanwendung, Layoutbibliothek oder produktive Integration wird hiermit beschlossen. Voraussetzungen: [Anforderungen](../requirements.md), [Architektur](../architecture.md), [ADRs](../adr/README.md), [B01/B02-Laufzeitbericht](../discovery/lubelogger-runtime-verification.md).

> **Einzelnutzer-Fortschreibung 2026-10-27:** Ein Cloudflare-Login, danach volle Adminrechte auf alle Fahrzeuge und Dokumente; keine interne Trennung zwischen angemeldeten Webnutzern. Die bestehenden Produktflüsse gelten unter diesem globalen Adminmodell. [ADR-0008](../adr/0008-single-user-access.md).

## Ausgangspunkt und Entwurfsgrenzen

LubeLogger bleibt der bevorzugte Ort für Fahrzeugstammdaten, Kilometer, Wartung/Reparatur und Kosten. B07 prüft zuerst seine vorhandenen Seiten anhand der nachstehenden Aufgaben auf Desktop und Mobilgerät. Nur eine belegte Lücke rechtfertigt eine schmale Garage-Ergänzung; deren Daten kommen aus derselben Quelle. Die folgenden Wireframes beschreiben gewünschte Informationen und Abläufe, nicht bereits vorhandene LubeLogger-Seiten oder einen Auftrag für eine Komplett-UI. B03 Audit, B16 Dokumentrechte und B17 Tages-/Schwellenberechnung sind vor Freigabe relevant.

Vorschlagskonventionen: eigene stabile `vehicleId`; `ReadSnapshot` mit `source`, `readAt`, `staleAfter`; `DueTask` mit `taskId`, `dueRevision`, `dueDate`; `CommandDraft`, Command-Zustände und `operationStatus` aus [Assistentenspezifikation](assistant-ai-spec.md). Namen sind interne Verträge, keine neuen Provider-Endpunkte. Datums-/Regelhoheit folgt der noch offenen Entscheidung aus ADR-0001/0004.

## Informationsarchitektur und Phasen

| Bereich | Zweck / Hauptaktionen | Oberfläche / Gate |
| --- | --- | --- |
| Garage | Mindestens fünf Fahrzeuge, nächster Handlungsbedarf, kritische Probleme, Datenalter | Zuerst native Übersicht prüfen; zusätzliche Ampelprojektion nur bei belegter Lücke, B07/B17 |
| Anstehend | Fahrzeugübergreifende priorisierte Aufgaben, Filter überfällig/bald/unbekannt | Native Liste prüfen; gleiche fachliche Definition wie Bot/Scheduler |
| Fahrzeugdetail | Stammdaten, Kilometer, Aufgaben, Historie, Kosten, berechtigte Dokumentreferenzen | Native Details bevorzugen; logische Sektionen statt verpflichtender neuer Navigationsstruktur |
| Technisches Logbuch | Problem, Status, Schweregrad, Ereignisse, wiederkehrender Fall | v1.1; gezielte Garage-Ergänzung gemäß ADR-0002/0005 |
| Vorgang erfassen | Wartung/Reparatur, Arbeit/Dauer, verwendete Teile, Kosten, Belegreferenz | Native Form zuerst; Bot später nur nachgewiesene API-Fähigkeiten anbieten |
| Integrationsstatus | Ausstehende/unklare Aufträge, letzter Abgleich, Kalender-/Dokumentausfall | v1.1; verständliche Statusmeldungen und gezielte erneute Prüfung |
| Regeln und Quellen | Zeit-/km-Intervalle, Nutzerintervall vs. Herstellerquelle, Erinnerungsgrenzen | Exakt ein Regel-Owner; keine parallele UI-Regelpflege |

Keine Tankprotokoll-Pflicht, Videoanalyse oder Live-OBD-Navigation. Für ein Fahrzeug ohne Historie keine erfundene Jahresfahrleistung anzeigen. Motorisierung muss erfassbar sein; die Sandbox bestätigt ein Zusatzfeld, noch nicht dessen mobile Bedienbarkeit.

## Ampel, Priorität und Datenqualität

Die Ampel ist **keine technische Fahrfreigabe** und keine Diagnose. Bekannte Probleme und fällige Aufgaben bleiben voneinander unterscheidbar. Vorschlag für eine fachliche Anzeige, dessen Schwellen erst mit B04/B17 beschlossen werden:

| Anzeige | Deterministische Bedingung | Erläuterung |
| --- | --- | --- |
| Rot / „Handlung nötig“ | Bestätigtes kritisches Problem oder mindestens eine überfällige Aufgabe | Ursache als Text zeigen; kritisches Problem nicht allein aus KI-Ausgabe erzeugen |
| Gelb / „Bald prüfen“ | Mindestens eine Aufgabe innerhalb des gültigen konfigurierten Vorwarnfensters | Datum und/oder Kilometergrenze sowie auslösende Regel anzeigen |
| Grün / „Keine bekannte Fälligkeit“ | Keine obige Bedingung, auswertbare vollständige aktuelle Basis | Nicht „Fahrzeug mängelfrei“ schreiben |
| Grau / „Nicht vollständig bewertbar“ | Fehlende erforderliche Daten, ungeklärte Regel oder keine lesbare aktuelle Basis | Keine implizite grüne Einstufung; fehlende Informationen konkret nennen |

Datenqualität ist zusätzlich und unabhängig sichtbar: `aktuell`, `veraltet`, `teilweise`, `nicht verfügbar`. Bekannte rote Befunde bleiben auch bei veralteter Basis sichtbar, mit Zusatz „letzter Stand …, weitere Fälligkeiten unbekannt“. Eine fehlende Aktualisierung darf Rot nicht in Grau oder Grün auflösen. Ein veralteter unauffälliger Snapshot wird nicht als verlässlich Grün dargestellt. TTL/Vorwarnfenster/Kilometergrenze sind Betreiberparameter, keine hier festgesetzten Standardwerte.

Berechnung verwendet fachliche lokale Daten in Europe/Berlin; `DueDays`/Urgency aus LubeLogger gelten nicht als Grundlage. Heute fällige Aufgabe ist „heute fällig“, erst danach „überfällig“, sofern B04 diese Empfehlung annimmt. `Both` prüft Zeit und Kilometer unabhängig und zeigt die zuerst erreichte Grenze. Bei alter Kilometerbasis: zeitbasierte Fälligkeit trotzdem auswerten, Kilometerprognose als unbekannt oder gekennzeichnete Schätzung zeigen. Reine Vorwarnschwellenänderung erzeugt eine versionierte Policy-/Anzeigeänderung, aber keine neue bestätigte Frist oder Durchführung und keinen pauschalen neuen Versand. dueRevision steigt bei tatsächlicher bestätigter Frist-/Zyklusänderung. Native Auto-Refresh bleibt deaktiviert.

Sortierungsvorschlag: bestätigte kritische Probleme, überfällige Aufgaben, heute fällig, bald fällig, Datenprüfung erforderlich. Innerhalb einer Gruppe nach relevanter Fälligkeit und stabiler ID. Unvollständige Daten erhalten eine eigene sichtbare Gruppe; konkrete Reihenfolge dieser Gruppe ist eine Produktentscheidung. Datum und Kilometer sind nicht beliebig numerisch ineinander umrechenbar; bei gemischten Fristen die auslösende Dimension anzeigen.

## Textuelle mobile Wireframes

Alle Fahrzeuge/Werte sind synthetisch. Die Darstellungen zeigen logische Inhalte; bei nativer Abdeckung werden keine parallelen Seiten gebaut.

```text
WOLFS GARAGE                         [Aktualisieren]
Stand: heute 12:00 · LubeLogger erreichbar
[Alle 5] [Handlung nötig] [Daten prüfen]

[Rot] Testfahrzeug A
Kritisches Problem: vom Nutzer bestätigt
HU: heute fällig · Kilometerstand: 12 345 km
[Details]                           [Vorgang erfassen]

[Gelb] Testfahrzeug B
Wartung: in Vorwarnfrist · Datum: 02.11.2026
Kilometerbasis: 20.10.2026 · Prognose: Schätzung
[Details]

[Grau] Testfahrzeug C
Bewertung unvollständig: Wartungsquelle fehlt
Letzter Abruf: 25.10.2026 · Aktualisierung fehlgeschlagen
[Details]                              [Erneut lesen]
```

```text
< Garage             TESTFAHRZEUG A
Marke / Modell / Motorisierung / Baujahr
12 345 km · erfasst 26.10.2026          [Stand erfassen]
[Aufgaben] [Historie] [Logbuch] [Kosten] [Dokumente]

HU · heute fällig
Nächste Fälligkeit: 26.10.2026
Quelle: bestätigter Bescheid / Referenz
[Durchführung erfassen]

Verlauf
26.10.2026 · Kilometerstand korrigiert
Vorher / Nachher · Begründung · Akteur
[Weitere Ereignisse]

Dokumente
HU-Beleg · Zugriff wird geprüft        [In Paperless öffnen]
Versicherungsbeleg · derzeit nicht verfügbar
```

```text
< Fahrzeug           WARTUNG / REPARATUR
Fahrzeug: Testfahrzeug A
Datum [26.10.2026]    Kilometer [12345] Einheit [km]
Art [Wartung / Reparatur]   Tätigkeit [Freitext]
Arbeit [Eigenarbeit / Werkstatt]   Dauer [h:min]
Werkstatt [optional]               Notizen [optional]
Teile [Bezeichnung | Teilenummer | Menge | Preis]
Kosten [Arbeit] [Teile] [Sonstiges] [Gesamt / Währung]
Beleg [Paperless-Referenz wählen]
Erledigte Aufgaben [nur unterstützte Zuordnung]
[Prüfen]                                  [Abbrechen]

PRÜFEN
Speicherwirkung je Schritt:
Wartung: bereit · Teile: separater bestätigter Schritt
Fristfortschreibung: Regelentscheidung erforderlich
[Bestätigen]                              [Ändern]
```

Bei vorhandener nativer Erfassungsfunktion gelten deren validierte Speicherschritte; die Wireframe-Bestätigung ist insbesondere für Garage-/KI-/Bot-Wege vorgesehen. Keine zusätzliche Bestätigungsschleife für triviale Navigation. Kritische/destruktive Änderungen benötigen klaren Wirkungsumfang. Ob native Formulare vollständiges Audit ermöglichen, muss B03 lösen.

## Konkrete Abläufe

### F1 — Fahrzeug und Kilometerstand (REQ-001–004)

Nutzer wählt ein explizit identifiziertes Fahrzeug, erfasst Datum und Kilometer; Einheit wird sichtbar übernommen. Es wird nicht still zwischen Meilen, Betriebsstunden und Kilometern umgerechnet. Rückdatierte Erfassung und sinkender Wert sind unterschiedliche Fälle. Sinkender Stand verlangt Korrekturgrund und zeigt die betroffene Historie; fachliche Korrekturpolitik und Rückrechnung sind vor Implementierung zu entscheiden. Nach Speicherung wird der tatsächliche Providerstand gelesen. Transportfehler erzeugt „Speicherergebnis unklar – Abgleich läuft“ statt „nicht gespeichert, erneut versuchen“.

Historienansicht zeigt Datum und Erfassungszeit getrennt. Prognose nennt Datenzeitraum/Basis und Schätzung; bei zu wenigen, widersprüchlichen oder veralteten Ständen bleibt sie unbekannt. Die Sandbox beweist Rückdatierung und Korrektur, noch keine sichere Prognosevalidierung oder Einheitenumrechnung.

### F2 — Wartung/Reparatur, Teile und Kosten (REQ-005–015)

Nutzer erfasst Tätigkeit, Datum, Stand, Eigen-/Werkstattarbeit, Dauer, Werkstatt, Notizen, Teile und Betrag. Vorschlag: Dauer als Minuten speichern und als Stunden/Minuten anzeigen; Währung/Betrag als Dezimalwert mit expliziter Währung, keine Fließkommarechnung. Pflichtfelder und Währung müssen festgelegt werden. Herkunft der Wartungsregel ist entweder passende belegte Herstellerquelle oder als Nutzerregel markiert; fehlt die Quelle, wird keine Herstellerbehauptung angeboten.

Teileauswahl nennt Bezeichnung, Teilenummer, verfügbare Menge, Einkaufspreis und tatsächlich verwendete Menge. Preis-/Mengenänderung muss vor Speichern klar sein. Die geprüfte öffentliche API ignoriert `Supplies`; keine Bot-/Garage-Schaltfläche darf deshalb „Wartung samt Teileabgang erledigt“ versprechen. Zunächst nativen nachgewiesenen Requisition-Weg verwenden oder Funktion als nicht unterstützt kennzeichnen. Spätere Mehrschrittintegration benötigt getrennte Ergebniszustände und Abgleich bei Teilerfolg.

Vorschau nennt Gesamtbetrag und dessen Bestandteile; eine bereits eingerechnete Teileposition wird nicht ein zweites Mal aufaddiert. Eigenarbeitsdauer wird ohne ausdrückliche Preisregel nicht als Geldbetrag bewertet. Sandboxbeispiel 5 Arbeit + 10 Teil = ausdrücklich übergebenes Gesamt 15 belegt keine automatische Provideraddition. Jahreskosten müssen B07 gegen synthetische Vorgänge mit Jahreswechsel, Korrektur und Teilverbrauch prüfen; Bezugsdatum (Leistungs-/Zahlungsdatum), Steuerbehandlung, Erstattungen und Währungspolitik bleiben offen. Bis dahin keinen unbelegten Zahlungsstatus oder vollständige Finanzbuchhaltung zusagen.

Wartungserfassung und Erledigung/Fortschreibung einer Aufgabe sind getrennte Wirkungen. Native UI-Funktion zuerst prüfen. Öffentliche API-Wartungsanlage allein erledigt keinen Reminder. Wenn Regel-Owner oder API-Fähigkeit fehlt: Vorgang kann gespeichert sein, aber die Aufgabe bleibt sichtbar offen mit Hinweis zur getrennten bestätigten Fortschreibung. Keine grüne Erfolgsmeldung für die Gesamtkette bei Teilerfolg.

### F3 — HU, Steuer und Versicherung (REQ-008–012)

Datum/Beleg erfassen, als einmalige oder belegte wiederkehrende Aufgabe kennzeichnen. Bei bestätigter HU-Durchführung tatsächliches Datum und amtliche nächste Fälligkeit/Quelle anzeigen. Nicht pauschal 24 Monate addieren; Ausnahmen und Regelquelle klären. Kalenderstatus lautet separat „Aktualisierung ausstehend“, „aktuell“ oder „Konflikt“. Google-Ausfall darf die erfasste Durchführung nicht zurückrollen. Bei nur bestätigtem HU-Monat wird „fällig im Monat …“ angezeigt; ein operativer Monatsletzter bleibt als Ableitung erkennbar, statt einen amtlich bestätigten genauen Tag vorzutäuschen. Der native 7-Tage-Reminder und das vorgeschlagene zusätzliche 30-Tage-Ereignis stehen unter ADR-0004; UI zeigt keine bereits erfüllte 30-Tage-Garantie.

### F4 — Technisches Problem (REQ-017–022)

Nutzer wählt Fahrzeug, Datum, Kilometerstand, Beschreibung und Schweregrad aus den konfigurierten Begriffen. Bei „kritisch“ zeigt die Vorschau die geplante Dashboardhervorhebung und Warnung. Erst nach Bestätigung werden Problemereignis und Warnauftrag erzeugt. Diagnoseversuch, Reparatur und Statuswechsel ergänzen Ereignisse; alte Einträge bleiben lesbar. Wiederkehrender Fall referenziert eine frühere Problem-ID und überschreibt sie nicht. Status „behoben“ ist eine bestätigte Eingabe, kein Schluss aus verstrichener Zeit oder KI-Text. Telegram-Zustellung hat eigenen Status und darf eine gespeicherte kritische Markierung nicht verdecken.

### F5 — Dokumente (REQ-026–027, B16)

Standardvorschlag: bestehendes Paperless-Dokument auswählen und auf Fahrzeug/Vorgang referenzieren. Zuerst den gültigen Cloudflare-Adminzugang prüfen; Paperless benötigt einen technisch funktionsfähigen eigenen Zugang. Ein Garage-Link allein erteilt keinen externen Zugriff. Eine zweite interaktive Anmeldung ist nicht das gewünschte Nutzererlebnis und die Einbindung muss noch getestet werden. Dokumenttitel/Thumbnails dürfen vor dieser Prüfung nicht erscheinen. Bei Entzug nicht aus altem Cache weiter anzeigen. Defekte Referenz erläutern und korrigieren lassen, historische Vorgänge nicht löschen.

**Native LubeLogger-Dateipfade sind in der Testbaseline für jeden angemeldeten Nutzer lesbar.** Das passt zu den jetzt gewünschten globalen Adminrechten. Vor Nutzung echter Daten muss der tatsächlich vorgesehene Cloudflare-/Originzugang verhindern, dass nicht zugelassene Personen direkt App oder Dokumente abrufen. Bestehende Paperless-Dokumente werden bevorzugt referenziert, soweit praktisch geprüft.

### F6 — Fehler, Neustart und parallele Bearbeitung (REQ-040–048)

Lesefehler: letzten zulässigen Stand mit Alter und partieller Auswertung anzeigen; keine Daten als gelöscht deuten. Schreibfehler: `failed` nur bei eindeutigem Fehlschlag, `uncertain` bei möglichem externem Erfolg. „Erneut prüfen“ liest denselben Auftrag; es legt keinen neuen an. Bei veränderter Revision zeigt die Oberfläche Vorher/Nachher und fordert einen neuen Entwurf. Nach Wiederherstellung bleiben externe Jobs pausiert, bis Betreiber Zuordnungen/Outbox freigibt; Nutzer sieht „Synchronisierung pausiert“, keine fingierte Aktualität.

## Visuelle und funktionale Abnahmeszenarien — geplant, nicht ausgeführt

| ID | Szenario | Erwartetes Ergebnis |
| --- | --- | --- |
| UI-01 | Fünf synthetische Fahrzeuge auf schmalem Mobilviewport und Desktop | Alle erreichbar, Hauptaufgaben ohne horizontales Tabellenzwangscrollen; Farben zusätzlich durch Text/Icons, sichtbarer Tastaturfokus, verständliche Feldfehler |
| UI-02 | Kritisches Problem, heute fällig, morgen fällig und überfällig gemischt | Fachliche Priorität und lokale Datumstexte korrekt; keine Provider-DueDays-Abweichung übernommen |
| UI-03 | Früher roter Befund, aktueller Provider nicht erreichbar | Rot mit Datenalter bleibt sichtbar; keine verlässliche grüne Bewertung |
| UI-04 | Kilometerbasis fehlt oder ist veraltet | Datum weiter auswertbar; Kilometerprognose unbekannt/Schätzung mit Basis, keine erfundene Fahrleistung |
| UI-05 | Rückdatierte Lesung und begründete Kilometerkorrektur | Unterschied erkennbar; tatsächlicher Providerstand, Auditverknüpfung und Prognose-Neubewertung geprüft |
| UI-06 | Werkstatt-/Eigenarbeit mit Dauer, synthetischem Teil und Kosten | Werte bleiben nach erneutem Lesen erhalten; Teilmenge und Gesamtkosten nicht doppelt gezählt; API-Teilelücke sichtbar |
| UI-07 | Wartung gespeichert, Reminderfortschreibung nicht unterstützt | Wartung erfolgreich, Aufgabe weiterhin offen; kein pauschales „alles erledigt“ |
| UI-08 | Jahreswechsel, Korrektur, Teilabgang | Jahresreport stimmt mit beschlossenem Bezugsdatum und Einmalzählung überein; offene Finanzregeln blockieren falsche Summenbehauptung |
| UI-09 | Nicht über Access zugelassener Aufruf und bekannter nativer Dateipfad | Zugang zur App und Dokumentbytes gesperrt; B16 besteht Browser-/API-/Temp-/Restore- und Origin-Negativtests |
| UI-10 | HU bestätigt, Google nicht erreichbar oder fremd editiert | Lokaler Verlauf korrekt; Projektionsstatus ausstehend/Konflikt, keine Doppeltermine oder ungeprüfte 24-Monatsregel |
| UI-11 | Zwei Bestätigungen, Antwortverlust, Neustart | Ein lokaler Auftrag; mögliches externes Duplikat durch Abgleich behandelt, `uncertain` sichtbar |
| UI-12 | Problem beobachtet → behoben → erneut aufgetreten | Historie nachvollziehbar, alter Fall bleibt bestehen, kritische Einstufung nachvollziehbar bestätigt |

B07 protokolliert je Szenario `native erfüllt`, `Konfiguration nötig`, `Ergänzung nötig` oder `blockiert`, inklusive Version, reproduzierbarer Schritte und synthetischer Screenshots ohne Secrets. Erst dann Umfang einer UI-Ergänzung entscheiden. Planungsabnahme ist kein bestandener visueller Test.

Für den vorgeschlagenen Garage-Regel-Owner gilt präzise: Bei atomarer Command-Annahme wird die ausdrücklich bestätigte tatsächliche Durchführung samt fachlich berechenbarer Frist lokal erfasst. LubeLogger-Beleg und Kostenprojektion können noch pending/uncertain sein und werden getrennt angezeigt. Das ist kein Anlass für eine zweite Durchführung; fehlende/ungeklärte Regelhoheit ist ein anderer Fall und blockiert ihre automatische Fortschreibung.
