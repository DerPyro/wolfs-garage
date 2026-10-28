# LubeLogger gegen eine eigene Lösung — technische Challenge

Nachtrag 2026-10-28: Der Nutzer hat nach dieser Gegenprüfung die eigenständige Entwicklung als Open-Source-Projekt gewählt; siehe [ADR-0009](../adr/0009-backend-ownership-challenge.md). Die folgende Bewertung hält die Entscheidungsgrundlage und ihre damaligen offenen Punkte fest. Eine produktive Übernahme ist damit nicht erfolgt.

Stand der Gegenprüfung: 2026-10-28. Auftrag: beide Optionen kritisch gegen Anforderungen und vorhandenen Code prüfen. Drei unabhängige Gegenprüfungen betrachteten den Nutzen von LubeLogger, einen eigenen Kern und Betriebs-/Datenrisiken. Diese Bewertung verwendet bestehende Testnachweise und erneut gelesene offizielle Quellen; sie enthält keine neuen Laufzeittests, Produktivzugriffe oder Migrationen.

## Ergebnis und Empfehlung

Die frühere pauschale Empfehlung „eigene SQLite-Lösung ist einfacher“ war zu weitgehend. Unsere eigene Oberfläche ist kein vollständiges Fahrzeugbackend. Für die gesamte ursprüngliche Anforderungsliste hat LubeLogger heute den größeren belegten Funktionsumfang. Für einen bewusst kleinen eigenen Kern ist ein Ersatz dagegen plausibel.

**Bedingte Architekturpräferenz: eigene Datenhoheit prüfen, wenn die eigene Oberfläche sämtliche wesentlichen Problem-/Wartungsabläufe führen soll; währenddessen trägt LubeLogger die laufende Verwaltung weiter.** Der entscheidende mögliche Mehrwert ist ein gemeinsamer Ablauf für Probleme, Wartungen, Fahrbereitschaft und Historie. Diese Präferenz ist noch kein Ergebnis eines ausgeführten Vergleichs. Der Ersatz ist erst begründet, wenn ein begrenzter eigener Durchstich diesen Nutzen einschließlich Wiederherstellung belegt. Bis dahin ist weder eine Ablösung beschlossen noch der ursprüngliche Umfang reduziert.

Ein dauerhafter Ausbau, bei dem Garage sämtliche fachlichen Abläufe selbst besitzt und LubeLogger nur noch eine zweite, synchron zu haltende Belegablage ist, soll vermieden werden. Bleiben seine vorhandenen Verwaltungsabläufe wesentlich, ist die schlanke Integration die bessere Option.

## Bewertungsgrundlage

- Die [Anforderungen](../requirements.md) enthalten weiterhin Kilometer, wiederkehrende Wartung, Kosten/Teile, Dokumente, technisches Logbuch, Telegram und Kalender. Eine einfachere Oberfläche hat diese Funktionen nicht abbestellt. Der Erstumfang einer möglichen Ablösung ist daher eine ausdrücklich offene Produktentscheidung.
- Das [Ein-Admin-Modell](../adr/0008-single-user-access.md) steht fest. Frühere Mehrnutzer- und Fahrzeugrollenbefunde begründen keinen Ersatz. Beide Lösungen müssen den Zugang über Cloudflare und die Origin-Abschirmung erhalten.
- Aussagen über LubeLogger-Laufzeitgrenzen beziehen sich auf die [geprüfte Version v1.7.4](../../tests/lubelogger/target.lock.json), nicht pauschal auf alle späteren Releases. Die aktuelle offizielle Dokumentation belegt Funktionen, aber keine nachträgliche Schließung der in dieser Version gemessenen API-Lücken.
- Die im Gespräch bestätigten fünf Fahrzeuge sind kein Nachweis einer kleinen Migration. Der aktuelle Umfang ihrer Belege, Kilometerstände, Zusatzfelder und Anhänge wurde für diese Bewertung nicht produktiv inventarisiert.
- Die Status-/INOP-Funktion und ihr SQLite-Speicher sind lokal vorbereitet. Der letzte Rollout wurde auf Nutzerwunsch gestoppt; die Bewertung behandelt diese Funktion nicht als bereits produktiv eingeführt.

## Was heute tatsächlich vorhanden ist

| Bestandteil | Belegter Stand | Bedeutung für einen Ersatz |
| --- | --- | --- |
| Eigene Oberfläche | Fahrzeugkarten, Marken-/Typsymbole, Kennzeichen, Erinnerungs-/Serviceübersicht und lokaler Statuseditor. Die Listen zeigen im Detail derzeit höchstens fünf Einträge je Kategorie. | Ein großer Teil der Darstellung ist wiederverwendbar; vollständige Historie und Verwaltungsformulare fehlen. |
| LubeLogger-Adapter | Drei unterschiedliche Upstream-GETs: Fahrzeuge, Erinnerungen und Servicebelege. Fahrzeug-/Kilometer-/Belegverwaltung führt weiterhin über `/Home` zu LubeLogger. | Wenige gelesene Endpunkte bedeuten nicht, dass die dahinter benutzte Verwaltungsfunktion bereits selbst existiert. |
| Eigene SQLite | `meta`, `states`, `audit`; Bereitschaft, bis zu 20 offene Kurztexte und deren Revisionen. | Keine eigenen Fahrzeug-, Kilometer-, Wartungs-, Kosten- oder Dokumenttabellen. Kein vollständiges Aufgabenmodell und noch keine Anzeige der gespeicherten Änderungsstände. |
| Integration des Status | Ein Status-Write liest zuerst die LubeLogger-Fahrzeugliste. Der Fingerprint unseres Adapters verwendet Provider, Marke, Modell und Baujahr. | Der lokale Status bleibt vom Fremdsystem abhängig; Stammkorrekturen können die Zuordnung bewusst blockieren. Der Fingerprint ist eine eigene Implementierungsentscheidung: stabile lokale IDs mit expliziter Provider-Zuordnung und Abgleich wären auch beim Behalten von LubeLogger möglich. |
| LubeLogger-Verwaltung | Belege, Kilometer, Zusatzfelder, Teileverwendung und ausgewählte Kostenberichte sind in isolierten Tests belegt. Ein Anwendungsrestore inklusive eines Testanhangs wurde geprüft. | Diese vorhandenen Funktionen und Nachweise müssen bei einer Ablösung ersetzt oder ausdrücklich aus dem Erstumfang ausgeklammert werden. |

Codebelege: [Adapter](../../garage_gateway/server.py), [Statusspeicher](../../garage_gateway/status_store.py), [Frontend](../../frontend/app.js), [Verwaltungslinks](../../frontend/index.html). Bestehende Laufzeitevidenz: [B01/B02](../discovery/lubelogger-runtime-verification.md), [WP02 Funktion](../discovery/wp02-functional.md).

Das neue Werkzeugsymbol folgt aktuell den manuell gepflegten offenen Punkten. Eine automatische Verknüpfung mit den LubeLogger-Erinnerungen ist damit noch nicht implementiert. „Offene Arbeit“ und „regelbasierte Wartung fällig“ müssen fachlich zusammengeführt oder klar getrennt angezeigt werden; beide Backends brauchen dafür einen definierten Ablauf.

## Fairer Vergleich

Die relevante Alternative zum Eigenbau ist **LubeLogger mit unserer eigenen, reduzierten Bedienung**. Ein Vergleich nur mit seiner umfangreichen nativen Oberfläche würde die bestehende Integrationsoption benachteiligen.

| Kriterium | LubeLogger hinter eigener Oberfläche | Eigener kleiner Backendkern |
| --- | --- | --- |
| Gestaltung und wenige Optionen | Vollständig durch unsere Oberfläche bestimmbar; unbenutzte native Optionen müssen dort nicht erscheinen. | Ebenfalls frei bestimmbar. Die Kartenoptik entscheidet den Backendvergleich nicht. |
| Fahrzeuge, Kilometer und Belege | Bereits vorhanden; eigene Eingabeformulare müssen aber noch an geprüfte Schreiboperationen angebunden werden. | Datenmodell, Formulare und sämtliche Schreibpfade neu; vorhandene Statusvalidierung ist nur ein Teil davon. |
| Problem → Durchführung → Historie | Eigene Probleme und fremde Belege erzeugen mehrere Schreibvorgänge mit möglichen Teilerfolgen. | Lokale Durchführung, Problemabschluss und Historie können gemeinsam in einer DB-Transaktion gespeichert werden. |
| Wiederkehrende Wartung | Native UI besitzt Datum/Kilometer, frühere Grenze und feste/flexible Wiederholung. Im geprüften öffentlichen API-Vertrag fehlen Wiederholungs-/Refresh-Felder. | Regeln frei formulierbar, aber Berechnung und Randfälle sind eigene Verantwortung. Nur benötigte Fälle zuerst umsetzen. |
| Historie | Vorhandene Wartungshistorie zeigt aktuelle Belege; Korrekturen und Löschungen sind kein durchgängiger Versionsverlauf. | Änderungsstände können direkt beim Schreiben protokolliert werden. Die lokale Statushistorie deckt bisher nur ihren eigenen kleinen Umfang ab. |
| Teile, Kosten, Anhänge | Nutzbare vorhandene Funktionen. Die ausgewerteten Vorgangskosten sind nicht automatisch eine vollständige Zahlungshistorie. | Neue Arbeit für Geldbeträge/Währung, Teileverbrauch, Verknüpfungen und Dateilebenszyklus oder eine explizite Paperless-Referenzlösung. |
| Telegram/Kalender/KI | Eigene Integrationen und Bestätigungsabläufe bleiben nötig; API-Grenzen und unklare externe Schreibausgänge kommen hinzu. | Gemeinsame lokale Datenhoheit hilft; externe Ausfälle, doppelte Zustellung und Kalenderregeln bleiben trotzdem zu lösen. |
| Betrieb und Pflege | Upstream pflegt die Fachanwendung; wir pflegen Oberfläche, Adapter und Erweiterungen. Mehrere Speicher brauchen abgestimmten Restore. | Ein eigener Dienst kann die Datenhaltung vereinfachen; Schemaänderungen, Validierung, Dateiverwaltung und Updates liegen vollständig bei uns. |
| Migration und Rückweg | Bestehender Datenbestand und native Verwaltung bleiben unmittelbar nutzbar. | Vollständige Übernahme samt Prüfung nötig; nach ersten neuen Zielschreibvorgängen ist ein Rückfall mehr als das Starten des alten Containers. |

Offizielle Funktionsquellen: [API](https://docs.lubelogger.com/Advanced/API/), [Service-/Reparaturbelege](https://docs.lubelogger.com/Records/Service%20Records/), [Reminders](https://docs.lubelogger.com/Records/Reminders/), [Supplies](https://docs.lubelogger.com/Records/Supplies/). Quellen zu den versionsgebundenen Grenzen: [Integrationsprüfung](../discovery/lubelogger.md), [API-/Laufzeitnachweis](../discovery/lubelogger-runtime-verification.md), [Auditbewertung](../discovery/wp02-audit-assessment.md).

Die [MIT-Lizenz der geprüften LubeLogger-Version](https://github.com/hargata/lubelog/blob/v1.7.4/LICENSE) liefert keinen Produktgrund für eine Ablösung. Es gibt außerdem keine Messung, die einen entscheidenden Ressourcen- oder Geschwindigkeitsvorteil des Eigenbaus belegt. Ein eingesparter Container allein trägt die Entscheidung nicht.

## Die stärksten Gegenargumente

**Gegen Eigenbau:** Die Oberfläche ist der heute auffällige Teil, aber sie spart keine Umsetzung von Belegkorrekturen, Kilometerhistorie, Beträgen, Anhängen, Wiederholungsregeln und Wiederherstellung. Fünf Fahrzeuge begrenzen weder Datumsrandfälle noch Datenverlustrisiken. SQLite löst Persistenztechnik, nicht das fachliche Modell. Der bestehende Python-HTTP-Adapter ist ebenfalls kein Nachweis eines bereits vollständigen, migrationsfähigen Anwendungsbackends.

**Gegen dauerhaftes LubeLogger:** Wenn Garage ohnehin Probleme, Wartungsregeln, Bestätigungen, Historie und die gesamte Bedienung besitzt, bleiben von LubeLogger vor allem ausgelagerte CRUD-Operationen. Dann bezahlen wir mit Provider-Zuordnungen, API-Anpassungen, Ausfallkopplung und mehrstufigen Schreibabläufen. Private UI-Routen oder direkte Fremd-DB-Eingriffe wären kein belastbarer Ausweg aus einer fehlenden öffentlichen Operation.

**Gegen eine pauschale Zwei-Datenbanken-Kritik:** Getrennte, klar führende Fachbereiche sind zunächst keine doppelte Datenhaltung. Die problematische Zusatzarbeit entsteht dort, wo ein fachlicher Vorgang beide Bereiche zuverlässig ändern muss. Auch eine eigene Lösung benötigt weiterhin Backups, Konfiguration und gegebenenfalls Dokumentdateien außerhalb ihrer DB.

**Gegen unnötige Architektur:** Der persönliche Gebrauch verlangt keine neue Rollenplattform, Microservices oder manipulationssichere Audit-Infrastruktur gegen den eigenen Administrator. Ein verständliches Änderungsjournal und angemessene Wiederherstellung sind der Ausgangspunkt. Die [Auditbewertung](../discovery/wp02-audit-assessment.md) trennt diese Ziele bereits ausdrücklich.

## Welcher konkrete Ablauf entscheidet?

Ein isolierter Durchstich soll mit denselben synthetischen Daten und Erwartungen gegen beide Varianten bewertet werden:

1. Fahrzeug mit Typ und Einheit anlegen, später Stammdaten korrigieren; zugehörige Probleme und Belege bleiben richtig zugeordnet.
2. Ein fahrbereites Fahrzeug erhält eine offene Wartungsaufgabe. Die Karte zeigt Wartung, ohne daraus INOP abzuleiten.
3. Eine Reparatur mit fachlichem Datum, Kilometerstand und Kosten dokumentieren und den zugehörigen offenen Punkt ausdrücklich abschließen. Weitere offene Punkte bleiben bestehen; Fahrbereitschaft wird separat gepflegt. Für einen tatsächlich benötigten wiederkehrenden Fall die nächste Fälligkeit nachvollziehbar bestimmen.
4. Einen Beleg korrigieren und den Verlauf anzeigen. Wiederholtes Absenden, veraltete Revision und ein Abbruch zwischen Schreibschritten dürfen keine unbemerkten Doppelbelege oder verlorenen Änderungen erzeugen.
5. Daten samt einer Dokumentreferenz oder einem Testanhang exportieren, in einen leeren isolierten Bestand wiederherstellen und Identitäten, Verlauf, Beträge, Daten/Einheiten und gegebenenfalls Dateibytes vergleichen.

Für LubeLogger ist konkret zu zeigen, welche Schritte über seine öffentliche API funktionieren und wo eine manuelle native Aktion oder eigene Fachlogik bleibt. Für Eigenbau müssen alle Schritte ohne LubeLogger funktionieren. Vorhandene Tests dürfen wiederverwendet werden; aus ihrer Anzahl entsteht keine prozentuale Produktabdeckung.

### Wann LubeLogger gewinnt

- Die täglichen Abläufe sind mit wenigen geprüften API-Schreiboperationen abbildbar und die native Beleg-/Teile-/Dokumentverwaltung bleibt nützlich.
- Die benötigten Automatismen verursachen keine dauerhaften doppelten Regeln oder unklaren Fachtransaktionen.
- Der Eigenkern müsste kurzfristig viele vorhandene Verwaltungs- und Importfunktionen nachbauen oder ein Bestandsimport verliert relevante Informationen.

### Wann der eigene Kern gewinnt

- Die eigene Bedienung und der zusammenhängende Problem-/Wartungsablauf sind der bestätigte Schwerpunkt; der erste Ersatzumfang ist explizit begrenzt, ohne spätere Anforderungen stillschweigend zu streichen.
- Fahrzeug, Aufgabe, Durchführung und Historie können gemeinsam geführt werden; LubeLogger würde überwiegend eine zusätzliche synchronisierte Ablage bleiben.
- Der eigene Durchstich einschließlich Korrektur, Export und Restore besteht. Ein trockener Import kann den benötigten Bestand vollständig erhalten.

## Möglicher Eigenkern und kontrollierter Übergang

Als zu prüfender Entwurf genügt ein einzelner modularer Backenddienst mit eigener stabiler Fahrzeug-ID und SQLite. Die vorhandene Oberfläche, Karten und Teile des Statuseditors bleiben nutzbar. Neue Kernbestandteile sind Fahrzeuge, Kilometerbelege, Aufgaben/Probleme, Durchführungen mit Kosten, Dokumentzuordnung, Änderungsjournal sowie Schema-Migrationen und Export. Ein gepflegtes Webframework und explizite DB-Migrationen sind vor einer Ausweitung des heutigen HTTP-Adapters zu bewerten. Spring Boot/PostgreSQL aus dem alten Zielentwurf sind für einen kleinen Ein-Admin-Kern keine Voraussetzung.

Telegram und Kalender können später denselben Anwendungsdienst verwenden. Externe Versand- und API-Aktionen folgen erst nach einer lokalen bestätigten Speicherung und benötigen weiter einen nachvollziehbaren Fehler-/Wiederholungsablauf. Dokumente können lokal oder als Paperless-Referenzen geführt werden; welche Variante den Bedarf erfüllt, bleibt zu entscheiden. Keine neue allgemeine Dokumentplattform als Nebenprojekt.

Vor einer realen Ablösung sind eine lesende Bestandsinventur, ein vollständiges gesichertes Original inklusive Anhängen, LubeLogger-/Betriebskonfiguration und ASP.NET-DataProtection-Schlüsseln sowie ein isolierter Import nötig. Das getestete Anwendungsexport-ZIP allein enthält diese Schlüssel nicht und ist kein vollständiger Betriebsrückweg. Objektzahlen allein reichen nicht: Referenzen, Datumswerte, Einheiten, Beträge und Anhang-Hashes vergleichen; nicht übernehmbare Felder benennen. Fahrzeugtypen aus der privaten Zuordnung und gegebenenfalls bis dahin vorhandene Statushistorien gehören ebenfalls zum Übernahmeplan.

Ein späterer Wechsel bekommt einen eindeutigen führenden Schreibpfad. Kein paralleles Dual-Write. Der alte Datenstand kann als Rückweg erhalten bleiben; neue Zieländerungen müssen bei einem späteren Rückfall gesondert gesichert und abgeglichen werden. Diese Schritte sind Voraussetzungen eines späteren Auftrags, keine in dieser Challenge ausgeführte Migration.

## Offene Entscheidungen und Evidenzgrenzen

1. Welche Teile der weiterhin gültigen Anforderungen müssen vor einer Ablösung vorhanden sein, welche kommen danach? Besonders Teilelager, Kostenauswertung, wiederkehrende Regeln und Dokumente verändern den Aufwand.
2. Kann die gewollte eigene Bedienung die vorhandene LubeLogger-Verwaltung weitgehend ersetzen, oder soll diese dauerhaft benutzt werden?
3. Welche Dokumentvariante und welche Darstellung der Änderungshistorie werden tatsächlich benötigt?
4. Wie groß ist der heutige vollständige Datenbestand und welche nicht übernehmbaren Felder gibt es?

Es liegen weder belastbare Entwicklungsstunden noch ein vergleichbarer Performancebenchmark oder ein vollständiger Produktiv-Restore vor. Diese Bewertung nennt daher keine erfundenen Zeitersparnisse oder Komplettabdeckungsquoten. Die laufende Anwendung wurde für den Vergleich nicht geändert. [ADR-0009](../adr/0009-backend-ownership-challenge.md) hält die vorgeschlagene Entscheidungsgrenze fest.
