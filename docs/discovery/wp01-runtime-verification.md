# WP01 — Ergebnis der isolierten Audit-/Dateigrenzenprüfung

**Einordnung nach Nutzerklärung:** Die nachstehenden Messungen sind unverändert gültige historische Testevidenz. Der Nutzer möchte nur einen Cloudflare-Login und danach volle Adminrechte; eine interne Read-only-/Outsider-Trennung ist daher kein Produktziel und keine eigenständige Voraussetzung für v1.0. Die damalige Gatewayempfehlung wird durch [ADR-0008](../adr/0008-single-user-access.md) für diesen Scope ersetzt. Die Side-Effect-, Audit-, Origin- und Browser-Authentifizierungsfragen bleiben getrennt relevant.

Stand: **2026-10-27**. Abschließender Lauf `wolfs-wp01-e1a8b97817`, **42 Checks: 28 pass / 14 gap / 0 fail**. [Bereinigte Evidenz](evidence/wp01.json), [reproduzierbarer Testtreiber](../../tests/wp01/README.md), [statisches Quellinventar](wp01-route-review.md), [unabhängiger Testreview](wp01-test-review.md).

## Entscheidungsergebnis des Spikes

**Die Hypothese „Household-View/Viewer-Key macht die native LubeLogger-Ansicht zuverlässig schreibfrei“ ist für v1.7.4 widerlegt.** Repräsentative normale Writes werden zwar abgewehrt, aber Kilometer-GETs können persistieren und die View-Steuerprüfung kann neue Kostenbelege erzeugen. Die Dateiabgrenzung bleibt unabhängig davon unzureichend. Damit ist die bevorzugte native Read-only-Variante aus ADR-0006 in diesem Stand **nicht freigabefähig**.

Das ist ein konkretes Machbarkeitsergebnis von WP01, keine vollständige Runtime-Abnahme aller Aktionen. B03 (vollständiger Auditpfad) und B16 (Dokumentabsicherung) bleiben offen. Ein kontrollierter eigener API-Zugang ist als enger Teilumfang demonstriert, eine vollständige native UI hinter einem umfassenden Schutzproxy weder implementiert noch bewiesen. Es wird nicht behauptet, jede denkbare Proxy-/Upstream-Lösung sei unmöglich.

## Bestand, Plan und Isolation

Gelesen: AGENTS, README, Anforderungen, Architektur, Roadmap, ADR-0006, Lieferplan und Threatmodell. Plan: unabhängige Quell-/Bedrohungsprüfung → reale Household-View-Konfiguration → normale Writes und indirekte Seiteneffekte mit Vorher/Nachher messen → Datei-/Kodierungs-/Rechteentzug-/Restorefälle → sehr enge Test-Positivliste prüfen → Konsequenzen dokumentieren.

Ziel unverändert: LubeLogger **v1.7.4**, Source `63fa5cd267497ba01c29f4888c65efbbdd4b94bf`, Image `ghcr.io/hargata/lubelogger@sha256:483a9d7582c4e6258615fd822b3de4193b4fcc4230d0a92432c6d407faf75af2`, linux/amd64. Laufende Containerimage-ID jeweils gegen das gepinnte Image geprüft; kein ungeprüftes `latest`.

Eigenes zufälliges Dockerprojekt, zwei getrennte leere Daten-/Key-Volume-Paare, internes Netz ohne veröffentlichte Hostports und ohne externe Providerkonfiguration. Nur synthetische Fahrzeuge, Belege und Textdateien. Root nur für Einrichtung/Backup, separate Parent-/Child-/Outsider-Identitäten, reine API-Key-Clients getrennt von Cookies. Bei regulärem Ende beide Container gestoppt und Testlistener geschlossen. Keine produktive Konfiguration/Cloudflare-Änderung und keine echten Daten.

Unabhängige Agents inventarisierten Quellrouten und Test-/Bypassfälle. Ein dritter Review prüfte den Treiber; Hinweise zu unabhängigem `/all`-Observer, vollständigerem Stammdaten-Fingerprint, tatsächlicher Containerimage-Bindung und positiver Scopeprüfung der Fahrzeugliste wurden aufgenommen. Fehlgeschlagene Entwicklungsdurchläufe sind keine Erfolgsevidenz; ausschließlich der oben genannte abschließende Lauf ist versioniert.

## 1. Was Household-View tatsächlich schützt

Parent ist direkter Collaborator der zwei Zielautos. Child erhält nur Household-View, keine direkte Parentfahrzeug-Kollaboration, keine Edit-/Delete-Permissions. Folgende native HTTP-Seiten sind lesbar: Fahrzeugdetail, Servicebelege und Reminder. Das belegt gerendertes HTML, **keine** vollständige visuelle/JavaScript-/Mobil-Abnahme.

Sechs repräsentative Writes werden mit Child-Cookie abgewiesen und lassen Fahrzeugstammdaten sowie Belege unverändert: Serviceanlage, Kilometeranlage, bestehendes Fahrzeug ändern, Service löschen, Service duplizieren und Bulk-Edit. Ein Outsider sieht keine Parentfahrzeuge/-belege. Normale Nicht-Root-Backups sind gesperrt; Root-Dateilöschung wird beim Child mit 302 auf `/Error/403` abgewiesen, und die synthetische Tempdatei bleibt erhalten. HTTP-Redirect und Fehlerobjekt wurden nicht mit erfolgreicher Änderung verwechselt.

**Grenze:** Household-Rechte sind objektbezogene Parentrechte, keine globale native Nutzerrolle. Der Child kann ein eigenes neues Fahrzeug anlegen und dort direkt Servicebelege schreiben. Das ist nicht der Nachweis einer Edit-Rechteausweitung auf Parentfahrzeuge; es widerlegt aber die weitergehende Annahme einer vollständig schreibfreien Browsersitzung. Ein späterer Zugang müsste auch Neuanlage-/Direktkollaborationswege kontrollieren.

## 2. Persistierende Reads und View-Prüfung

| Aufruf / Identität | Unabhängig beobachteter Effekt | Konsequenz |
| --- | --- | --- |
| `GET /Vehicle/GetOdometerRecordsByVehicleId?vehicleId=…`, Child-View-Cookie | Zwei Altbelege mit initialOdometer 0/0 werden dauerhaft auf 10000/10000 geändert | Native View-Seite kann schreiben; gewöhnlicher Read ist kein sicherer Audit-Bypass-freier Weg |
| `GET /api/vehicle/odometerrecords?vehicleId=…`, Viewer-API-Key des Child | Nach erneut separat hergestellter Null-Fixture dieselbe persistierende Konvertierung | Auch öffentlicher GET mit Viewer-Key ist nicht automatisch schreibfrei; aus enger Positivliste ausgeschlossen |
| `POST /Vehicle/CheckRecurringTaxRecords?vehicleId=…`, Child-View-Cookie | Vorher ein wiederkehrender synthetischer Kostenbeleg, nachher drei | Fachliche Belegfortschreibung trotz reiner View-Grundlage; nur POST-Sperre löst den Kilometer-GET nicht |
| `GET /Files/UploadCoordinates?coordinates=…`, Child | Neue Tempdatei, Marker als Bytes anschließend durch Outsider lesbar | GET-Methode und kein Editrecht verhindern allgemeine Dateischreibwirkung nicht |

Bei Kilometerständen wurde **nicht** der mutierende per-vehicle-GET als Kontrollabruf verwendet. Beobachter: `/api/vehicle/odometerrecords/all` mit zusätzlichem Zielfahrzeugfilter; beide mutierenden Einstiegspunkte erhielten getrennte wiederhergestellte Fixtures. Für die Tax-Fixture wurde eine künftig wiederkehrende Steuer über die native Parentfunktion erstellt und das Datum anschließend über das öffentliche API-Update rückdatiert. Keine Provider-DB manipuliert und keine Hostuhr verstellt.

Diese Effekte können Upstream-Migrations-/Komfortlogik sein; der Bericht erklärt sie nicht pauschal zu CVEs. Für das geforderte strikte Audit-Schreibmodell sind sie dennoch relevante nicht kontrollierte Writes.

## 3. Datei-, Upload- und Rechteentzuggrenzen

- Native Dokumentbytes: Parent und Household-Child dürfen lesen; **auch der angemeldete Outsider ohne Fahrzeugrechte erhält identische synthetische Bytes**. Anonymer Zugriff bleibt gesperrt.
- Ein Viewer-API-Key ohne Edit-Recht kann `/api/documents/upload` verwenden; neu gespeicherte synthetische Bytes sind anschließend abrufbar. Die API-Key-Rolle ist kein pauschaler Writefilter aller Aktionen.
- Ein Outsider kann die native Temp-Uploadfunktion benutzen; ein anderer angemeldeter Nutzer kann den bekannten Temp-Pfad lesen. Keine persönliche Datei wurde benutzt.
- Nach Entfernen des Household-Zugriffs scheitert der Parentbeleg-API-Zugriff, der bekannte native Dokumentpfad bleibt mit derselben alten Child-Sitzung lesbar. Das ist nicht nur ein Problem veralteter Listenansicht.
- Restore in zweiter isolierter Instanz erhält Dokumentbytes, Rootlogin, Household-View und **dieselbe Outsider-Dateilücke**. Anonym weiterhin gesperrt. Eine Wiederherstellung ist keine Sicherheitskorrektur.

Zehn rohe Pfadvarianten wurden charakterisiert: normaler Dokumentpfad, kodierter Buchstabe im Präfix, kodiertes `.`-Segment und aufgelöstes `../` lieferten bei Outsider Dokumentbytes. Die hier getesteten Großschreibungs-, doppelten Slash-, doppelt kodierten Dot- und konventionellen `/Files/GetStaticFile`-Kandidaten lieferten 404. Das ist zielversionsbezogene Routingbeobachtung, keine pauschale Aussage über alle Kodierungen/Proxys.

Preview liefert HTML mit dem bereits übergebenen Dokumentpfad, nicht selbst Dokumentbytes; HEAD liefert 200 mit bekannter Inhaltslänge, aber keinen Body. Diese Beobachtungen werden **nicht** als zusätzliche Byteexfiltration gezählt. Eine vorgeschaltete Sperre müsste Pfadnormalisierung, Methoden, Datei-/Temp-/Preview-/Upload-/Export-/Restorewege und direkte Originzugänge konsistent abdecken; ein einzelnes Präfix oder versteckter Button genügt nicht als Beweis.

## 4. Cross-origin-Serverprüfung — begrenzter Nachweis

Ein nativer Parent-Service-POST ohne Antiforgery-Token wurde mit absichtlich fremdem `Origin`/`Referer` und manuell injiziertem gültigem Parent-Cookie angenommen; ein zusätzlicher synthetischer Beleg ist nachgewiesen. Damit war für diesen Serverpfad keine wirksame Origin-/Antiforgery-Verweigerung zu beobachten.

**Kein vollständiger Browser-CSRF-Exploitnachweis:** Der HTTP-Client injiziert Cookies; reale Browserentscheidung über SameSite/Scheme/Navigation, Access-Schicht und Cookieattribute wurde nicht getestet. Weder „CSRF vollständig sicher“ noch „jeder Browser kann dies ausnutzen“ wird behauptet. Browser-/Sessiontests bleiben vor nativer Veröffentlichung offen.

## 5. Was die enge API-Positivliste zeigt

Temporärer Loopback-Testserver mit zufälligem Testmarker, fester serverseitiger Household-Viewer-Identität und zwei erlaubten Operationen:

1. `GET /api/vehicles`, Antwort zusätzlich auf die beiden expliziten Zielfahrzeuge gefiltert; das Child-eigene Neufahrzeug wird nachweislich ausgeschlossen.
2. `GET /api/vehicle/servicerecords?vehicleId=<explizit erlaubte ID>`, nur exakt kanonischer Parametervertrag.

Beide Positivpfade funktionieren. Fehlender Testmarker scheitert. **31** geprüfte Datei-/Temp-/Preview-/Upload-/Admin-/native Write-/Kodierungs-/Methoden-/Queryvarianten werden mit 403 abgewehrt, bevor sie den Origin erreichen. Weiterleitungszähler und Vorher-/Nachherfingerprint bleiben bei diesen abgewiesenen Requests unverändert. Das rohe Requesttarget wird vor Pythonhandler-Normalisierung geprüft; keine bloße „GET erlaubt“-Regel.

Das demonstriert eine schmale Vermittlung, nicht mehr: kein produktives Login/JWT/CSRF, keine native vollständige UI, kein Audit-Write-Service, keine Prüfung aller möglichen Requestformen, keine Origin-Netzisolation. Im Test kann der Host absichtlich direkt auf die Container-IP zugreifen und dort die Outsider-Datei lesen. **Dieser direkte Weg müsste im späteren echten Aufbau ausgeschlossen sein**, sonst schützt auch ein korrekt verweigernder Proxy nicht. Der Testproxy ist keine ausrollbare Sicherheitslösung.

## 6. Konsequenzen und konkrete Optionen

| Option | WP01-Bewertung | Weiterer Aufwand / Entscheidung |
| --- | --- | --- |
| Native Oberfläche nur durch Household-View/Viewer-Key absichern | **Für strikte Schreibfreiheit verworfen**, konkrete Gegenbeispiele | Nicht durch Umbenennung in „read-only“ oder Methodensperre freigeben |
| Native vollständige Oberfläche hinter umfassender Methoden-/Routenvermittlung | **Nicht nachgewiesen** | Vollständiges kompiliertes Routeninventar, Browserfunktion und alle Nebenwirkungen/Dateipfade/Netzgrenzen prüfen; beträchtliche Kopplung an Zielversion |
| Schmaler eigener Garage-Zugang, LL nur intern über geprüfte Operationen | **Bevorzugter weiterer Entwurf**, zwei reine API-Leseoperationen demonstriert | Audit-/Commandschreibkern und Originisolation separat implementieren/nachweisen; fehlende Teile-/Recurrence-Verträge nicht erfinden; ggf. früherer Garage-Umfang erforderlich |
| Belegte Upstream-Verbesserung | Offen | Neue Version oder konkret geprüfte Erweiterung erneut testen; kein Fork/PR oder Liefertermin beauftragt |
| Kleinerer v1.0-Audit-/Funktionsumfang | Nur nach expliziter Produktentscheidung | REQ-043/026/014 nicht still als erfüllt abhaken |

Empfehlung für den nächsten Auftrag: den kleinen Garage-Zugang und seine minimalen tatsächlich ausführbaren Schreibfälle konkretisieren, parallel die verbliebenen UI-/Einheiten-/Kostenfälle aus WP02 prüfen. Vor der ersten produktiven Freigabe müssen B03/B16/Origin-/Sessionnachweise vorliegen. Es ist keine Entscheidung des Nutzers über vorgezogene v1.1-Funktionen getroffen; alle ADRs bleiben vorgeschlagen.

## Nachweisgrenzen und Aktualisierung

Statisches Inventar: **329 Action-Deklarationen aus 35 Controllerdateien**, kein vollständig kompilierter Endpunktkatalog. Runtime nur die ausdrücklich benannten Fälle, keine vollständige Prüfung aller 329 Deklarationen oder sämtlicher Files-/Import-/Backup-/Bulkwege. 14 `gap`-Checks enthalten sich überschneidende Effekte, bereits bekannte Grenzen und bewusst ungelöste Testtopologie; es sind **nicht 14 unabhängig neu entdeckte Sicherheitslücken**.

Bisherige B01/B02-Evidenz und ihre 62 Checks bleiben unverändert. Testtreiber-/Helfer-/Inventar-/Compose-/Lock-Hashes stehen in [wp01.json](evidence/wp01.json). Der neue Spike behebt keine Upstream-Funktion. Keine produktiven Dienste oder Cloudflare-Konfiguration angelegt, keine echte Datenmigration/Löschung. Lokale synthetische Laufvolumes/Backups bleiben ignoriert erhalten; keine Passwörter, Keys, Cookies oder Originalbackups in Git.
