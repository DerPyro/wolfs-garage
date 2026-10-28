# WP02 — Funktionsprüfung LubeLogger für einen Administrator

Stand 2026-10-27. **Ergebnis einer isolierten Testinstanz, keine Produktivfreigabe.** Der Nutzer hat den Einpersonenbetrieb mit einem Cloudflare-Login und Administratorrechten für zugelassene Nutzer vorgegeben. Diese Prüfung bewertet deshalb funktionale Fähigkeiten, nicht die inzwischen nachrangige Trennung mehrerer Fahrzeugrollen.

## Umfang und Reproduktion

Untersuchte Ausgangslage: native LubeLogger-Oberfläche als bevorzugter Ausgangspunkt für v1.0, getestete Version **v1.7.4**, Commit `63fa5cd267497ba01c29f4888c65efbbdd4b94bf`, `linux/amd64`, gepinntes Image `ghcr.io/hargata/lubelogger@sha256:483a9d7582c4e6258615fd822b3de4193b4fcc4230d0a92432c6d407faf75af2`. Getesteter Lauf `wolfs-wp02-7ee1239894`: **19 Checks, 14 pass / 5 gap / 0 fail**; Instanz anschließend gestoppt.

Ziel ausschließlich selbst erzeugte synthetische Daten: fünf Fahrzeuge, Wartungs-/Reparatur-/Steuerbelege, Teil und Reminder. Frisch erzeugtes internes Docker-Netz, keine veröffentlichten Hostports, eigene Testvolumes. Native LubeLogger-Authentifizierung war in dieser isolierten Testinstanz wie beim Standard-Erststart deaktiviert, sodass die Upstream-Middleware den Testclient als Root behandelt. Das ist **kein Test von Cloudflare Access, Tunnel, Origin-Abschottung, Browser-Sessions oder einer produktiven Sicherheitskonfiguration**. Keinerlei realer Account, produktive Konfiguration oder Echtdaten verwendet.

Reproduktion aus dem Projektverzeichnis:

```bash
python3 tests/wp02/functional.py
```

Erfordert Python mit System-Zeitzonendaten sowie Docker/Compose und liest den vorhandenen, unveränderten Testhelfer `tests/wp01/helpers.py` und die gepinnte Sandbox-Konfiguration `tests/lubelogger/compose.sandbox.yaml`. Siehe [bereinigte maschinenlesbare Evidenz](../../tests/wp02/evidence.json): Test-/Helper-/Compose-SHA256 sind enthalten. Laufdaten/Volumes mit ausschließlich synthetischen Informationen bleiben lokal im ignorierten `.sandbox`-/Docker-Bereich; keine Credentials oder Dokumente werden versioniert. `pass` bestätigt den konkret genannten Test, `gap` eine beobachtete Grenze oder fehlende Anforderungserfüllung; es handelt sich nicht um fünf neue Sicherheitslücken.

## Fahrzeugübersicht und Warnung

| Test | Ergebnis |
| --- | --- |
| Fünf Fahrzeuge, Marke, Modell und Motorisierung als Zusatzfeld | API liefert alle fünf und die synthetischen Motorisierungswerte zurück. |
| Garage-Übersicht | Die native HTML-Partial `/Home/Garage` enthält die fünf Fahrzeuge; individuelle `/Vehicle/Index`-Seiten geben für alle fünf HTML zurück. |
| Reminder-Glocke mit konfigurierter Standard-Dashboardmetrik und Stand > 0 | Ein überfälliger synthetischer Reminder erzeugt eine Glocke in der betreffenden Fahrzeugkachel. |
| Gleicher überfälliger Reminder, aber Kilometerstand 0 | API meldet `pastDueReminderCount=1`, die getestete Garage-Kachel enthält keine Glocke. |

Der letzte Fall ist **eine belegte Lücke für eine zuverlässige Fahrzeug-Gesamtwarnung**, auch bei nur einem Administrator. Im Quellcode wird die Glocke im Zweig für die Standardmetrik und einen nicht-null letzten Stand angezeigt. Die native UI kann weitere Listen/Ansichten besitzen; dieser Test beweist weder, dass alle Hinweise insgesamt fehlen, noch dass die gesamte mobile UI/Ampel nicht existiert. Keine vollständige Browser-, JavaScript-, responsive oder Accessibility-Abnahme ausgeführt: HTTP lieferte serverseitiges HTML, JavaScript wurde nicht ausgeführt.

Quellen: [Garage-Controller, v1.7.4](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/HomeController.cs), [Garage-Partial](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Views/Home/_GarageDisplay.cshtml), [Dashboard-Auswertung](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Logic/VehicleLogic.cs).

## Teile, Vorgangskosten und Zahlungen

Synthetisches Testfahrzeug 1: Wartung 2025 = 100, Wartung 2026 = 30, Reparatur 2026 = 40, Steuer 2026 = 20. Ein Vorratsteil mit Menge 2/Gesamtwert 20 wird in einer nativen Wartungsaktion einmal verwendet; Restmenge 1, Restwert 10. Der Test übergibt ausdrücklich einen vollständigen Wartungsbetrag von 15 (synthetisch 5 Arbeit + 10 Teil). Eine Wartung über 9999 gehört zu Fahrzeug 2.

Der native Jahreskostenreport für Fahrzeug 1 und die explizit ausgewählten Kategorien Wartung/Reparatur/Steuer zeigt **2025 = 100, 2026 = 105**. Die 9999 des anderen Fahrzeugs und der verbleibende Lagerwert werden in dieser Testauswahl nicht hinzugerechnet. Wird der 2025-Wartungsbeleg von 100 auf 110 korrigiert, meldet der Report 2025 = 110 und 2026 weiterhin 105. Dies belegt den getesteten Gruppierungs- und Korrekturfall; das Testformular übergibt den Gesamtbetrag ausdrücklich und beweist keine automatische Addition des verwendeten Teilpreises durch die native Oberfläche.

Der Report wertet in der geprüften Implementierung ausgewählte Wartungs-, Reparatur-, Upgrade-, Tank-, Steuer- und Kilometerbelege aus. Ein explizit als `SupplyRecord` ausgewählter Bestandskauf erscheint in diesem spezifischen Report nicht als eigene Cash-Zahlung. **Vorgangskostenbericht und vollständige Zahlungshistorie sind daher noch nicht gleichgesetzt.** Die Anforderungen zu Kaufpreis, tatsächlichem Zahlungsdatum/-status, Erstattungen und separaten Rechnungen müssen anhand der konkreten native Möglichkeiten weiter abgeglichen werden; diese Stichprobe beweist nicht, dass keinerlei alternative Zahlungserfassung existiert.

Quellen: [Kostenreport, v1.7.4](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/Vehicle/ReportController.cs), [Jahres- und Monatsgruppierung](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Helper/ReportHelper.cs), [native Teileentnahme](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/Vehicle/SupplyController.cs), [offizielle Supplies-Dokumentation](https://docs.lubelogger.com/Records/Supplies/).

## Kilometer, Meilen und Betriebsstunden

Die Testkonfiguration akzeptiert `UseHours` pro Fahrzeug. Beim selben synthetischen Zahlenpaar 100 → 500 meldet die Tabellenansicht für ein reguläres Fahrzeug **400 km**, für das als Betriebsstunden-Fahrzeug konfigurierte Fahrzeug **400 h**.

Nach Änderung der globalen Nutzereinstellung `UseMPG` zeigt der Report für dasselbe reguläre Fahrzeug **400 mi.**; die zuvor gespeicherten Zahlen 100 und 500 bleiben in den geprüften API-Daten unverändert. In diesem konkreten Test erfolgte also keine automatische Umrechnung der Bestandswerte, während die Einheit wechselte. Vor späterer Automatisierung müssen Einheit und etwaige Umrechnung explizit geklärt werden; aus einem nackten API-Zahlenwert lässt sich die gewünschte Einheit nicht zuverlässig ableiten. Der Test trifft keine pauschale Aussage über weitere manuelle Umrechnungs-/Fahrzeuganpassungsfunktionen.

Quellen: [Vehicle-Modell](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/Vehicle/Vehicle.cs), [Benutzereinstellung](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/Settings/UserConfig.cs), [Reportcontroller](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/Vehicle/ReportController.cs).

## Automatische Dateneffekte und Änderungsprotokoll

Bei einer synthetischen wiederkehrenden Steuer wird ein rückdatierter Altbeleg angelegt. Der bloße HTTP-Abruf der Fahrzeugseite verändert ohne Ausführung von JavaScript noch nichts; die Seite enthält den Aufruf `checkRecurringTaxes()`. Beim im Test separat ausgeführten nativen Prüfrequest wächst die Anzahl von einem auf drei Kostenbelege, ohne getrennte Zahlungsbestätigung. Dies ist die getestete upstream Fortschreibungslogik, keine Aussage darüber, dass eine reale Zahlung stattgefunden hat. Die normale Browserausführung der JavaScript-Kette wurde hier nicht automatisiert getestet.

Ein per öffentlicher API geänderter Wartungsbeleg erscheint anschließend in der aktuellen API-Liste nur mit dem neuen Wert; der alte Wert ist in **dieser Liste** nicht mehr enthalten. Das allein beweist weder ein vollständiges Änderungsprotokoll noch, dass an anderer Stelle überhaupt keine Historie existiert. Das bisherige Webhook-Ergebnis aus [B01/B02](lubelogger-runtime-verification.md) zeigt ebenfalls keine vollständigen Vorher-/Nachherdaten.

Der Nutzerwunsch „ein Administrator“ hebt REQ-043 (Änderungsprotokoll) und REQ-020 (nachvollziehbare Problemhistorie) nicht auf. Vor Ausweisung als erfüllt muss geklärt werden, welche tatsächlich verfügbare native Historie das gewünschte Änderungsprotokoll abdeckt und ob eine ergänzende Umsetzung nötig ist. Die gesondert vorgeschlagene Forderung nach lückenlosen Vorher-/Nachherdaten für alle nativen Wege ist als Architekturvorschlag zu behandeln, nicht stillschweigend als vom Nutzer zusätzlich zugesagte Produktanforderung.

Quellen: [Fahrzeugansicht und Tax-JavaScript](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Views/Vehicle/Index.cshtml), [Tax-Clientaktion](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/wwwroot/js/taxrecord.js), [Tax-Fortschreibung](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Logic/VehicleLogic.cs), [Wartungs-API](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/API/ServiceController.cs).

## Konsequenz für den nächsten Schritt

Die native Oberfläche bleibt ein sinnvoller v1.0-Ausgangspunkt: fünf Fahrzeuge, Belege, Teileverwendung und ein einfacher Kostenreport sind im geprüften Umfang vorhanden. Eine eigene vollständige Oberfläche ist aus den früheren Mehrbenutzer-Rechtebefunden allein nicht begründet. Die **konkret belegte fehlende Glocke bei Stand 0**, die weiterhin zu prüfenden Prioritäts-/Logbuchanforderungen sowie fachliche Datums- und Zahlungsgrenzen können gezielte Ergänzungen rechtfertigen.

Offen bleiben insbesondere native UI-Abnahme inklusive Mobilansicht/Barrierefreiheit und Priorisierung, echte Zahlungshistorie, nachvollziehbares Änderungsprotokoll, sichere Cloudflare-Login-/Origin-Grenze, Restore der gesamten benötigten Daten samt DataProtection-Keys, Tagesgrenzen und die bekannten API-Lücken für wiederkehrende Regeln und Teileverwendung. Google-Kalender 30 Tage und Telegram-Workflows gehören zur späteren Integrationsphase. Keine dieser Lücken wird durch die alleinige Einbenutzerentscheidung automatisch als gelöst oder aufgehoben markiert.
