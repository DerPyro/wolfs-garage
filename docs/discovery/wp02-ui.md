# WP02: LubeLogger-Oberfläche im isolierten Browser

Stand: 2026-10-27. Ein Browserlauf mit ausschließlich synthetischen Daten prüft ausgewählte Grundabläufe der nativen Oberfläche. Er ist keine vollständige Abnahme, kein Cloudflare-Login-Test und kein produktiver Betrieb.

## Aufbau und Ergebnis

Der Lauf `wolfs-wp02ui-ddc857706d` verwendete das im [Test-Lock](../../tests/lubelogger/target.lock.json) festgelegte LubeLogger-Image und Chromium 140.0.7339.16 aus dem per Digest fixierten Playwright-Testimage. LubeLogger und Browser liefen ohne veröffentlichte Host-Ports in einem internen Docker-Testnetz; die native Anmeldung war für diesen lokalen Funktionstest ausgeschaltet. Die fünf Fahrzeuge, Kennzeichen, Wartungen, Ersatzteile und Erinnerungen sind erfunden. Beide Testcontainer wurden anschließend gestoppt; Testvolumes und Netzwerke blieben erhalten.

Alle fünf übergeordneten Prüfschritte des Laufs bestanden. Bei **320 × 800, 768 × 1024 und 1280 × 800 Pixeln** gelangen jeweils:

- Darstellung aller fünf Fahrzeugkarten und Öffnen des ersten Fahrzeugs per Maus;
- Anzeige eines Wartungseintrags mit Kosten sowie Öffnen des Eingabeformulars;
- Eingabe und Speichern eines neuen synthetischen Wartungseintrags über die Oberfläche; die drei Einträge wurden zusätzlich über die lokale API überprüft;
- Anzeige je einer synthetischen Erinnerung und eines Ersatzteils.

Die fünf Fahrzeugkarten waren in diesem Lauf ohne horizontale Verbreiterung des Dokuments sichtbar; bei 320 Pixeln standen sie untereinander. Im aufgezeichneten Browserlauf wurden weder JavaScript-Ausnahmen noch Antworten mit HTTP-Status ab 400 oder externe HTTP-Anfragen beobachtet. Dies beweist keine vollständige Fehlerfreiheit oder Barrierefreiheit.

## Beobachtete Einschränkungen

- Die Fahrzeugkarten waren `div`-Elemente ohne Rolle mit `tabIndex = -1`; der direkte Fokusversuch mit `focus()` scheiterte bei allen drei Größen. Die getestete Öffnung erfolgte per Maus. Ein vollständiger Tastatur- oder Screenreader-Test wurde nicht durchgeführt.
- In der Wartungstabelle bei 1280 Pixeln maß die Datumszelle 91 Pixel bei 102 Pixel Inhalt und verwendete `text-overflow: ellipsis`; im DOM stand das vollständige Datum, aber kein `title`-Attribut. Bei 320 und 768 Pixeln wurde an der geprüften Zelle kein solcher Überlauf gemessen.
- Erinnerung und Ersatzteil wurden angezeigt; Erinnerungslogik, tatsächliche Benachrichtigung, Dokument-Uploads, Offline-Verhalten und sämtliche Formulare sind damit nicht vollständig geprüft. Die Unterschiede zwischen überfälligen Erinnerungen und Garage-Kachel sind gesondert im [Funktionsbericht](wp02-functional.md) dokumentiert.

Das Ergebnis stützt LubeLogger als Ausgangspunkt für den Ein-Nutzer-Betrieb. Es begründet für sich weder eine eigene Oberfläche noch einen Verzicht auf weitergehende Zugänglichkeitsprüfungen.

## Nachvollziehbarkeit

Die [kompakte synthetische Evidenz](../../tests/wp02/ui-evidence.json) enthält Schritte, Messungen, Image-Identität und SHA-256-Prüfsummen der [Screenshots](../../tests/wp02/ui-shots/). Die dort angegebenen Skript-Prüfsummen beschreiben den aktuellen Dateistand; sie wurden nach dem Lauf ermittelt und sind kein zur Laufzeit erzeugter Integritätsnachweis.

Der isolierte Test kann mit `python3 tests/wp02/ui_run.py` erneut gestartet werden. Docker, das im Lock festgelegte LubeLogger-Image und das im Skript festgelegte Browserimage müssen lokal verfügbar sein; der Test lädt selbst kein Image herunter. Auf dem untersuchten Host waren Dockers automatische Netz-Subnetze durch zurückbehaltene Testnetze erschöpft. Der erfolgreiche Lauf nutzte deshalb ein leeres internes Netzwerk eines vorherigen **eigenen** UI-Testlaufs wieder. Auf einem frischen Host wird ein neues internes Testnetz angelegt; auf diesem Host ist für Wiederholungen ein geeignetes freies internes Testnetz erforderlich. Es wurden keine fremden Ressourcen oder Testartefakte gelöscht.
