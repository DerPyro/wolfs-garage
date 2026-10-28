# Telegram-Assistent und KI v2 — Planungsentwurf

Stand: 2026-10-26. **Empfehlungen, nicht angenommen; keine Botregistrierung, Anbieteranfrage oder Datenübermittlung.** [Anforderungen](../requirements.md), [Architektur](../architecture.md), [ADR-0004](../adr/0004-integrations-consistency.md), [ADR-0005](../adr/0005-ui-ai-boundaries.md), [Laufzeitgrenzen](../discovery/lubelogger-runtime-verification.md) und [Produktabläufe](product-flows.md) sind Grundlage. Strukturierte Botbefehle müssen ohne KI verfügbar sein. Ein NL-Parser kann vor v2 nur nach eigener Daten-/Anbieterentscheidung eingesetzt werden; „natürliche Sprache“ erteilt noch keine Freigabe externer KI-Verarbeitung.

## Gemeinsam verwendete Vertragsnamen

Interne Namen, keine behaupteten Provider-Endpunkte: `CommandDraft` ist der noch nicht bestätigte Zustand desselben Auftrags mit stabiler `commandId`; ein optionales `draftId` wäre nur Alias. `ConfirmedCommand` bezeichnet denselben Auftrag nach gültiger Bestätigung. `expectedVehicleRevision` schützt die Fahrzeugbasis; `expectedCommandRevision` die angezeigte Entwurfsfassung. Actor/Chat werden serverseitig abgeleitet, nicht aus frei eingesandten Fachfeldern übernommen.

Command-Zustände: `awaiting_confirmation`, `accepted`, `executing`, `succeeded`, `partially_succeeded`, `failed`, `uncertain`, `cancelled`, `expired`, `conflict`. Einzelne externe Operationen haben `operationId` und `operationStatus = pending | in_flight | succeeded | failed | uncertain | cancelled`. Ein Auftrag mit teilweise ausgeführten externen Schritten ist nicht „fehlgeschlagen, gefahrlos neu senden“. `ReadSnapshot(source, readAt, staleAfter)`, `DueTask(taskId, dueRevision, dueDate)`, `DocumentReference` und `ProblemEvent` behalten die gemeinsamen Domänenbezeichnungen. Maschinenlesbare Verträge sind mit diesen Namen konsistent zu halten.

## Strukturierte Befehle — vorgeschlagener Produktvertrag

Fahrzeugalias wird ausschließlich aus berechtigter serverseitiger Liste aufgelöst; `A` bezeichnet in allen Beispielen ein synthetisches Testfahrzeug. Beträge/Einheiten/Datumsformate werden vor Bestätigung normalisiert und sichtbar angezeigt. Slash-Befehle sind Entwürfe eines Botinterfaces, keine bereits registrierten Commands.

| Befehl | Zweck und vorgeschlagene Syntax | Wirkung / Grenze |
| --- | --- | --- |
| `/start`, `/hilfe` | Bedienung und verfügbare Fähigkeiten | Nur nach Autorisierung; keine öffentliche Nutzerregistrierung |
| `/fahrzeuge` | Berechtigte Fahrzeuge und eindeutige Aliasse | Namen/Identifier nur dem erlaubten Nutzer zeigen |
| `/status A` | Übersicht, kritische Probleme, Fälligkeiten, Datenalter | Gleiche fachliche Ampel wie Web, keine Fahrfreigabe |
| `/aufgaben A` bzw. `/aufgaben` | Fahrzeugbezogene oder eigene Gesamtliste | Überfällig/heute/bald/unbekannt getrennt |
| `/km A 12345 2026-10-26` | Kilometerstand erfassen | Erzeugt bestätigungspflichtigen Entwurf; sinkender Stand braucht Korrekturgrund |
| `/wartung A` | Geführter Dialog Tätigkeit, Datum, Kilometer, Arbeit, Dauer, Kosten | Nur nachgewiesene API-Felder; Reminder/Teile nicht als implizit erledigt melden |
| `/aufgabe A` | Einmalige Aufgabe oder belegte Regel als Entwurf | Schreibfähigkeit durch gewählten Regel-Owner begrenzt; keine API-Rekurrenz erfinden |
| `/hu A` | Durchführung/Beleg/amtliche nächste Fälligkeit geführt erfassen | Explizite Bestätigung und Quellen-/Ausnahmeprüfung; Kalenderstatus separat |
| `/problem A` | Problem, Datum, Stand, Beschreibung, Schweregrad erfassen | Entwurf; kritisch nur bestätigte Eingabe oder später validierte Fachregel |
| `/verlauf A` | Berechtigte jüngste Ereignisse | Keine unbeschränkte Übermittlung der gesamten Historie |
| `/auftrag <commandId>` | Zustand eines eigenen Auftrags abfragen | Liest denselben Auftrag; erzeugt keine neue externe Operation |
| `/abbrechen` | Aktuellen noch unbestätigten Entwurf abbrechen | Bereits gestartete externe Wirkung nicht als rückgängig gemacht behaupten |
| `/diagnose A` | v2: getrennten Beratungsdialog starten | Nur nach aktivierter KI und zweckgebundener Datenfreigabe |

Mehrdeutige Aliasse lösen eine Auswahl aus. Leere Argumente führen in einen schrittweisen Dialog, kein Fehlertext mit internem Stacktrace. Nicht unterstützte Teile-/Wiederholungsfunktionen werden mit konkreter Handlungsalternative in der geprüften nativen Oberfläche erläutert. Keine Bot-Löschbefehle im vorgeschlagenen Erstumfang. Authentifizierter Dokumentzugriff per Web/Paperless-Link statt Versand sensibler PDFs in Telegram; die Verlinkung setzt gelöstes B16 voraus.

## NL-Dialoge und Bestätigung

Beispiel „Bei A heute 12 345 km“: Fahrzeug sicher auflösen, „heute“ in Europe/Berlin aus Eingangszeitpunkt bestimmen und im Entwurf als konkretes Datum zeigen. Keine stillschweigende Änderung des Datums, wenn eine Antwort nach Mitternacht eintrifft. Beispiel „Ölwechsel erledigt“: Fahrzeug, tatsächliches Datum, Kilometerstand und Tätigkeit nachfragen; keine passende Wartungsregel oder Herstellervorgabe erfinden. Beispiel „Was steht bald an?“ ist lesend und zeigt Regelbasis/Datenalter.

Entwurf enthält Fahrzeug/Einheit, konkrete Aktion/Felder, alte und neue Werte soweit verfügbar, Quellenkennzeichnung, Kosten/Währung sowie getrennte Wirkungen: Vorgang, Teileabgang, Fristfortschreibung und Kalenderprojektion. Nicht unterstützte Wirkungen sind ausdrücklich ausgeschlossen bzw. blockiert; der Nutzer bestätigt den tatsächlich ausführbaren Umfang. Bedienelemente: „Bestätigen“, „Ändern“, „Abbrechen“. Eine fachliche Änderung bricht den alten unbestätigten Entwurf ab und erzeugt eine neue commandId mit eigener Revision, Hash und Nonce; alte Buttons bleiben ungültig. Ein bloßer erneuter Abruf derselben unveränderten Absicht kann dagegen nach der API-Recoveryregel die Nonce unter derselben commandId drehen und commandRevision erhöhen. Eine einfache Nachricht „ja“ genügt nur als Antwort auf den eindeutig zugeordneten aktuellen Entwurf; die sichere Erstempfehlung ist ein gebundener Button.

| Übergang | Guard / Verarbeitung | Nutzertext |
| --- | --- | --- |
| Eingabe → `awaiting_confirmation` | Schema/Fahrzeugrechte/Providerfähigkeit prüfen; fehlt Information: weiter klären | „Entwurf – noch nicht gespeichert“ |
| Bestätigung → `accepted` | Actor/Chat, Nonce, Inhaltshash, Ablaufzeit und beide Revisionen atomar prüfen | „Durchführung lokal bestätigt; LubeLogger-Synchronisierung ausstehend“ bei tatsächlicher Durchführung, sonst „Auftrag angenommen“ |
| Veralteter Entwurf → `conflict` | Providerbasis geändert oder fremde neuere Bestätigung; kein Schreiben | „Daten geändert – bitte neuen Entwurf prüfen“ |
| Ablauf → `expired` | Zeitlimit überschritten, Nonce ungültig | „Entwurf abgelaufen – neu prüfen“ |
| Ausführung → `executing` | Lokaler Auftrag/Audit/Outbox dauerhaft; Operationen einzeln abarbeiten | „Wird gespeichert“ |
| Alle erforderlichen Operationen erfolgreich → `succeeded` | Providerinhalt und `OperationResponse.Success` geprüft | „Gespeichert“ mit Ergebnis, Kalender bei separatem Auftrag separat ausweisen |
| Eindeutiger Teilerfolg → `partially_succeeded` | Mindestens ein erforderlicher fachlicher Effekt erfolgreich, anderer eindeutig fehlgeschlagen; pending optionale Projektion separat | „Wartung gespeichert; weiterer Schritt offen“ |
| Möglicher externer Erfolg → `uncertain` | Antwortverlust/Abbruch nach möglichem Commit; keine blinde POST-Wiederholung | „Ergebnis unklar – derselbe Auftrag wird abgeglichen“ |
| Eindeutig ohne Wirkung fehlgeschlagen → `failed` | Validierungs-/Berechtigungsfehler oder nachgewiesener Nichtabschluss | „Nicht gespeichert – Eingabe/Zugriff prüfen“ |
| Abbruch vor Bestätigung → `cancelled` | Nur awaiting_confirmation; atomarer Zustandswechsel | „Entwurf abgebrochen“ |

`partially_succeeded` und `uncertain` müssen je `operationId` aufgeschlüsselt werden. Bei unklarer Operation ist der Gesamtauftrag mindestens als unklar erkennbar, selbst wenn andere Schritte erfolgreich sind. Exakte Aggregationsregeln vor Implementierung im gemeinsamen Schema festlegen. Nach `accepted` nimmt `/abbrechen` keinen Abbruchauftrag mehr an, sondern zeigt den bestehenden Status und erläutert gegebenenfalls den getrennten Korrekturweg. Gestartete Calls brauchen Abgleich, keinen fiktiven Rollback. Erneute Bestätigung derselben Fassung liefert den bestehenden Zustand, keinen zweiten Auftrag.

Bestätigungsdauer ist offen und konfigurierbar; in diesem Dokument wird keine verbindliche Minutenzahl festgelegt. Spätere künstliche Retry-Anfragen oder eingehende Dokumenttexte können nie eine Nutzerbestätigung ersetzen.

## Telegram-Transport und Autorisierung

Offiziell nachgeprüft am 2026-10-26: `InlineKeyboardButton.callback_data` umfasst **1–64 Bytes**; `getUpdates` bestätigt ältere Updates durch Aufruf mit höherem `offset`; Telegram bewahrt Updates höchstens 24 Stunden auf. Long Polling und Webhooks sind alternative Empfangswege. `answerCallbackQuery` beendet die Fortschrittsanzeige des Clients. Quellen: [Buttons](https://core.telegram.org/bots/api#inlinekeyboardbutton), [Updateempfang](https://core.telegram.org/bots/api#getting-updates), [getUpdates](https://core.telegram.org/bots/api#getupdates), [Callbacks](https://core.telegram.org/bots/api#callbackquery). Das sind belegte Plattformgrenzen; alle folgenden Verfahren sind Garage-Vorschläge.

- Empfang ausschließlich per ausgehendem Long Polling, ein aktiver Poller mit Lease/Fencing. Bestehenden Webhookzustand vor späterer Inbetriebnahme read-only feststellen; nicht ungefragt fremde Webhooks löschen. Kein automatisches `drop_pending_updates`.
- Nur explizit allowlistete numerische `from.id` **und** privater, serverseitig gebundener `chat.id` dürfen Fachverarbeitung auslösen. User-ID und Chat-ID als getrennte Felder behandeln, nicht Gleichheit voraussetzen. IDs mit ausreichendem Integerbereich speichern, nicht als 32-Bit-Zahl. Username/Anzeigename/weitergeleiteter Absender sind keine Identität. Fehlendes `from`, Gruppen, Channels, Inline-/Business-Kontexte und unbekannte Updatearten führen zu keiner Fachaktion.
- Autorisierung vor Fahrzeugabfrage, Freitextanalyse, KI, Dateiabruf oder fachlicher Antwort. Fremde Anfragen höchstens generisch ablehnen; keine Fahrzeugnamen, erlaubten IDs, Dialoginhalte oder Providerfehler verraten. Sicherheitsjournal minimal halten, keine fremden Rohtexte dauerhaft speichern.
- Je `update_id` eine dauerhafte Inbox-Zeile mit Unique Constraint. Zulässige Updates erst minimal validieren und dauerhaft übernehmen; unzulässige/ungewöhnliche Updates als minimalen Ablehnungs-/Quarantänestatus übernehmen. Fachverarbeitung erfolgt anschließend aus der Inbox. Dauerhaftes Ingest und Verarbeitungsstatus sind getrennt.
- Den nächsten Poll-Offset erst nach dauerhaftem Ingest des gesamten zurückgegebenen Batches auf dessen höchste ID plus eins setzen. Ein Crash davor führt zu erneutem Empfang und Unique-Constraint-Deduplizierung; ein Crash danach verliert keine bereits übernommene Fachaktion. Keine Annahme lückenlos aufeinanderfolgender IDs, keine Bestätigung nur aufgrund eines noch nicht persistierten In-Memory-Erfolgs. Ein kaputtes Update darf nicht durch endloses Wiederholen den Bot blockieren.
- Längere Ausfälle können Telegram-Updates verlieren; der lokale Bestand bleibt führend. Nach Wiederanlauf Ausfallfenster anzeigen und offenen Dialogstatus abfragen lassen. Telegram-Queue ist kein dauerhaftes Audit/Backup.

### Callback-Vertrag

Vorschlag: Callback enthält nur ASCII-Aktionspräfix und zufälliges opakes Token, zum Beispiel `c:<opaque-token>`. Mindestens 128 Bit Zufall, als Base64url ohne Padding etwa 22 Zeichen; mit kurzem Präfix weit unter 64 **UTF-8-Bytes**. Keine JSON-Payload, Fahrzeug-ID, Kosten, Herstellerquelle oder Credentials in `callback_data`. Vor Ausgabe Bytelänge prüfen; Zeichenanzahl allein reicht nicht.

Server mappt Token auf `commandId`, `expectedCommandRevision`, `payloadHash`, `confirmationNonce`, Actor, privaten Chat, `message_id`, Aktion und Ablauf. Token besitzt keine selbstständige Fachberechtigung. Bei jedem Callback erneut `callback_query.from.id`, tatsächlichen Nachrichtenchat, Nachrichtenidentität und Fahrzeugrechte prüfen; fremde/fehlende/unzugängliche Nachricht ablehnen. `data` als untrusted behandeln. Ein einmaliger atomarer Compare-and-Set konsumiert Nonce und bestätigt den Auftrag. Replay liefert vorhandenen Auftragsstatus.

Callback zeitnah quittieren, damit der Client nicht hängen bleibt; Quittung ist kein Speichernachweis. Langsame Provider-/KI-Arbeit läuft danach. Ein Fehler beim Entfernen alter Buttons entwertet die Nonce nicht rückwirkend. Alte Buttons bleiben serverseitig ungültig, auch wenn Telegram das visuelle Update nicht erhält. Ausgaben mit sicherem Text/escapten Formatierungen; keine ungeprüften HTML-/Markdown-Fragmente aus Dokumenten oder Recherche.

### Versand und Erinnerungen

Inbox-Deduplizierung und fachliche Deduplizierung lösen nicht automatisch die Versandunsicherheit. Pro Erinnerung Schlüssel `(taskId, dueRevision, channel, offsetDays)`; dazu `deliveryId`, Versuche, Versandstatus, bekannte Telegram-`message_id` und letzter Fehler. Ein erfolgreich beantworteter `sendMessage` wird dokumentiert; ein Timeout nach möglichem Versand erzeugt `uncertain`.

Entscheidungsvorschlag für den ersten Umfang: unklaren Versand nicht blind automatisch wiederholen, sondern im Web/bei nächster Botinteraktion als unklar anzeigen und explizit „erneut senden“ anbieten. Das vermeidet automatische Duplikate, garantiert aber keine Zustellung; bei kritischen Warnungen ist ein bewusst anderes Wiederholungs-/Eskalationsverfahren separat zu beschließen. REQ-032 „ohne Duplikate“ bleibt deshalb eine Abnahmeentscheidung, keine behauptete Exactly-once-Garantie. Bekannter eindeutiger temporärer Fehlschlag darf begrenzt wiederholt werden; Anbieter-Retryvorgaben beachten, Budget und Backoff begrenzen.

Nach Restore Poller, Scheduler und Outbox zunächst pausieren; Inbox/Offset/Fälligkeitsrevision und Kalenderzuordnungen abgleichen. Ein alter Snapshot darf keine neue Serie doppelter Erinnerungen starten. Botblockierung als Zustellproblem zeigen, nicht Fahrzeugdaten ändern.

## KI v2: providerneutrale Beratung

KI hat keine Provider-/Datenbank-Schreibtools, keine direkte Bestätigungsfunktion und keine eigenständige Entscheidung über kritischen Status. Ein serverseitiger Adapter begrenzt zulässige Funktionen auf Analyse freigegebener Eingaben und Recherche; jeder Vorschlag wird strukturiert validiert. Strukturierte Bot-/Webfunktionen bleiben bei KI-Ausfall verfügbar. Keine Anbieterwahl, aktuelle Preise oder Datenschutzgarantien werden hier angenommen.

### Freigabe und minimale Daten

Vor jeder erstmaligen Übermittlung pro Zweck zeigt die Anwendung Datenkategorien, Zielanbieter/Region, mögliche Aufbewahrung und Kostenrahmen an. Fehlen diese Angaben oder die Zustimmung, wird kein externer Aufruf ausgeführt. Freigabe eines Fahrzeugs ist keine unbefristete Freigabe seiner vollständigen Dokumente.

| Datenkategorie | Ausgangsregel des Vorschlags | Nur bei explizit nachgewiesenem Bedarf |
| --- | --- | --- |
| Modell/Baujahr/Motorisierung | Freigegebener technischer Kontext | Unklare Motorisierung nachfragen, nicht aus Modellname raten |
| Symptome/ausgewählte Ereignisse | Nutzer wählt relevante Zeitspanne/Fälle | Erweiterung der Historie nach transparentem Hinweis |
| FIN/Kennzeichen/Nutzer-/Telegram-ID | Nicht an KI senden | Abweichender Bedarf gesondert begründen und entscheiden |
| Dokumente/Rechnungen | Nicht pauschal senden | Zugriffsprüfung, Ausschnitt, Redaktionsvorschau, zweckgebundene Zustimmung |
| OBD-Screenshot | Vorverarbeitung nur nach aktivierter Funktion | Kennzeichen/Name/Ort redigieren; Nutzer prüft den tatsächlichen Ausschnitt |
| Tokens, Passwörter, interne URLs | Nie als Modellkontext | Kein Ausnahmeweg über Prompt oder Dokument |

Lokaler Kontextaufbau prüft pro Zugriff Berechtigung, Quelle und Datenalter. Ein Retrievalfilter muss fremde Dokumente vor dem Modellaufruf ausschließen; der Prompt ist keine Autorisierung. Modell-, Anfrage- und Quellenmetadaten dürfen im Audit landen, sensible Rohinhalte nur mit beschlossener Retention und Zugriffspolitik. Zweckwiderruf stoppt neue Übermittlung; bereits beim Anbieter vorhandene Daten erfordern dessen geprüften Lösch-/Retentionprozess und dürfen nicht als automatisch gelöscht dargestellt werden.

### Ausgabe und Quellenqualität

Ein `AiSuggestion` enthält Fahrzeugreferenz, Fragestellung, freigegebenen Kontextumfang/Lesestand, Modell-/Promptversion, Rückfragen, alternative Hypothesen, Unsicherheiten und Quellenliste. Aussagen unterscheiden Nutzeraussage, bestätigte Historie, belegten Quelleninhalt und Modellhypothese. Keine erfundene numerische Diagnosewahrscheinlichkeit; qualitative Unsicherheit mit Begründung. Fehlende Belege werden ausdrücklich als fehlend markiert.

`SourceEvidence` enthält URL, Herausgeber, Titel, Abrufzeit, relevante Fundstelle, Fahrzeug-/Motor-/Baujahrpassung und Evidenzart. Suchtreffer allein gelten nicht als geprüfte Quelle. Herstellerintervalle dürfen nur aus passender nachvollziehbarer Herstellerquelle als solche übernommen werden; Foren können Hinweise geben, sind keine Herstellervorgabe. Widersprüchliche Quellen oder nicht passende Variante verhindern automatische Übernahme. Ersatzteilvorschlag ist ohne belegte Kompatibilität keine Bestell- oder Einbauempfehlung.

Nächste Aktion ist eine Rückfrage oder ein optionaler `CommandDraft`, niemals eine direkte Änderung. Kritische Hinweise werden als zu bestätigender Hinweis dargestellt; etablierte Nutzerkennzeichnung oder später gesondert geprüfte deterministische Fachregel bestimmt den verbindlichen Schweregrad. Keine neuen Diagnosefakten oder Wartungsintervalle in diesem Planungsdokument.

### OBD-Screenshot und Fehlercodeverlauf

Vorschlag für die Pipeline: berechtigten Fahrzeugkontext wählen → Bildtyp/Größe und Inhaltsgrenzen prüfen → redigierten Ausschnitt vorschauen → freigegeben verarbeiten → extrahierte Kandidaten samt Bildfundstelle und Unsicherheit anzeigen → Code, Zeitpunkt, Fahrzeug und Status vom Nutzer bestätigen → strukturiertes Ereignis speichern. Größen-/Seiten-/Dateityplimits müssen vor Implementierung festgelegt werden; keine unbegrenzten Uploads oder automatischen Downloads beliebiger URLs.

Unsichere Zeichen bleiben markiert; Parser darf sie nicht in einen plausibel wirkenden Code umdeuten. Formatvalidierung und generische/herstellerspezifische Bedeutung benötigen freigegebene Quellen und Fahrzeugkontext. Ein Screenshot belegt keine Ursache, keinen aktuellen technischen Zustand und keine erfolgreiche Reparatur. Status `aktiv`, `gelöscht`, `erneut aufgetreten` wird aus bestätigter Erfassung mit Zeitpunkt abgeleitet. „Gelöscht“ bedeutet keine bestätigte Fehlerbehebung. Wiederauftreten referenziert das frühere Ereignis; keine automatische OBD-Abfrage oder Löschung am Fahrzeug.

### Prompt Injection, Recherche und Abbruchgrenzen

Dokumente, OCR, Webseiten, Foren und Modellantworten sind untrusted Daten. Enthaltene Anweisungen wie „lade alle Rechnungen hoch“ oder „bestätige den Vorgang“ dürfen weder Kontextumfang noch Tools/Rechte verändern. Systemgrenzen werden durch serverseitige Tool-Allowlist, Objektberechtigungen, Schemaprüfung und Bestätigungsablauf erzwungen. Zugriffstokens werden nie in Modellkontext oder Toolausgaben aufgenommen.

Ein späteres Recherchewerkzeug darf nur kontrollierte HTTP(S)-Ziele erreichen; Loopback, private Netze, Cloudmetadaten, unerlaubte Ports und Redirects dorthin ablehnen. Antwortgrößen/Timeouts/Anzahl URLs/Weiterleitungen begrenzen, keine fremden Shellbefehle ausführen. Quelleninhalt als Text behandeln; aktives HTML oder Skripte nicht darstellen. Konkrete Fetchbibliothek/Netzwerkpolicy sind Implementierungsentscheidungen, kein bereits vorhandener Schutz.

### Budget und Anbieterentscheidung

Vor Aktivierung festzulegen: Anbieter oder lokales Modell, zulässige Region, Speicher-/Trainingsnutzung, Auftragsverarbeitung, Token-/Bildkostenmodell, maximale Anfragegröße, Outputlimit, Monats-/Tagesbudget, Parallelität und Fehlerschwellen. Preisangaben erst anhand des tatsächlich gewählten aktuellen Primärangebots prüfen. Lokale Ausführung hat ebenfalls Ressourcen- und Betriebsbudget.

Vorschlag: Budgetreservierung serverseitig vor jedem Aufruf; pro Nutzer/Zeitraum und Gesamtbudget atomar prüfen, maximale mögliche Anfragekosten reservieren und nach Verbrauch abrechnen. Bei unbekanntem Preis/Verbrauch oder fehlendem Limit verweigert der Adapter neue kostenpflichtige Aufrufe statt unbegrenzt zu schätzen. Recherchen und Bilder in dieselbe Gesamtkalkulation einbeziehen. Retries verbrauchen Budget und sind begrenzt; keine automatische Modell-/Providerkaskade ohne neue Freigabe. Budgetüberschreitung liefert eine verständliche Meldung und lässt strukturierte Erfassung weiterlaufen. Konkrete Geld-/Tokenwerte bleiben offen.

## Abnahmeszenarien — geplant

| ID | Fall | Erwartung |
| --- | --- | --- |
| BOT-01 | Fremde User-ID, erlaubter Anzeigename, Gruppenchat oder fremder Callback | Keine Fahrzeugabfrage, Datei-/KI-Verarbeitung oder Änderung; minimale generische Ablehnung |
| BOT-02 | Derselbe Updatebatch nach Crash vor/nach Ingest erneut empfangen | Ein Inbox-Eintrag je ID, kein verlorener Auftrag und kein zweiter bestätigter Befehl |
| BOT-03 | Mehrdeutiger Alias, „heute“ über Mitternacht, fehlende Einheit | Explizite Rückfrage bzw. konstantes konkret angezeigtes Bezugsdatum |
| BOT-04 | Callback >64 UTF-8-Bytes, manipuliert, abgelaufen, weitergeleitet oder Replay | Vor Ausgabe Längenprüfung; vor Wirkung Bindungen/Nonce prüfen; Replay liest vorhandenen Zustand |
| BOT-05 | Nutzdaten oder Fahrzeugrevision nach Vorschau geändert | Alter Button bestätigt keine neuen Daten; `conflict`/neuer Entwurf |
| BOT-06 | Wartungs-POST gespeichert, Antwort verloren; zweite Bestätigung | Derselbe Auftrag wird abgeglichen; kein blinder POST, unklarer Zustand sichtbar |
| BOT-07 | Wartung gespeichert, Teile-/Reminderwirkung nicht unterstützt | Begrenzter bestätigter Umfang oder deutlicher Teilerfolg; keine behauptete vollständige Fortschreibung |
| BOT-08 | Telegram-Send-Timeout, Bot blockiert, Ausfall >24 Stunden, Restore | Zustellstatus getrennt; keine Exactly-once-/vollständige-Queue-Behauptung; kontrollierter Wiederanlauf |
| AI-01 | Keine Freigabe, Budget fehlt/ausgeschöpft, Anbieter offline | Kein externer Aufruf, strukturierte Fahrzeugverwaltung bleibt möglich |
| AI-02 | Fremdes Dokument mit passendem Suchbegriff | Vor Retrieval ausgeschlossen; keine Metadaten/Bytes an Modell oder Chat |
| AI-03 | Herstellerintervall ohne Quelle oder für falsche Motorvariante | Nicht als Herstellerfakt übernehmen; Rückfrage/Unsicherheit statt erfundener Regel |
| AI-04 | OCR unleserlich, Code falsch erkannt, „gelöscht“ ohne Reparatur | Kandidat bleibt unbestätigt; keine Ursache/Behebung erfinden; Ereignis erst nach Bestätigung |
| AI-05 | Webseite/PDF fordert Exfiltration, Toolaufruf oder automatische Bestätigung | Keine Rechte-/Toolausweitung und keine Änderung; Ausgabe sicher gerendert |
| AI-06 | Modell behauptet sichere Diagnose oder kritischen Status ohne Evidenz | Quellen-/Schemagate greift; Status nicht automatisch ändern; Rückfragen/Unsicherheit sichtbar |
| AI-07 | Parallele Anfragen am Budgetlimit, Retry nach Timeout | Reservierung verhindert Überschreitung im definierten Kostenmodell; unbekannter Verbrauch sperrt weitere kostenpflichtige Arbeit bis Klärung |

Nicht ausgeführte Tests als geplant kennzeichnen. Freigabegates bleiben B03/B04/B09/B10–B17 und ADR-0005; weder dieses Dokument noch vorgeschlagene Fachbegriffe akzeptieren ADRs oder autorisieren ein Deployment.

Die gemeinsame API-Spezifikation ist für Cancel-/Recovery-/Revisionsregeln maßgeblich. Lokale bestätigte TaskCompletion und Fristfortschreibung bleiben bei ausstehendem/unklarem LL-Beleg erhalten; Kosten werden erst mit nachgewiesenem LL-Beleg in dessen Kostenprojektion gezählt. Keine erneute Durchführung zur Sync-Fehlerbehandlung.
