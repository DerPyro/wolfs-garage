# Fahrzeugtypen und Markenlogos

> Anonymisierte historische Dokumentation für das öffentliche Repository. Betriebsdomain, Host-/Speicherkennungen und private Pfade sind Beispiele; konkrete Betreiberzuordnungen sind verallgemeinert. Kein direkt ausführbares Runbook. Die unveränderten Originale liegen ausschließlich lokal unter dem ignorierten Verzeichnis `.sandbox/private-ops/`. Prüfresultate betreffen die damals untersuchte Instanz, nicht die hier eingesetzten Beispielwerte.

Stand: 2026-10-28. Fahrzeugtypen, Logos und Kennzeichenansicht wurden nach Freigabe aktiviert. Der aktuelle Prüfstand steht im [Bereitstellungsbericht](../discovery/deployment-2026-10-27.md#fahrzeugkarten-update-am-2026-10-28); die nachfolgende Einführungsplanung dokumentiert die Vorbereitung.

Die Fahrzeugkarte zeigt den ausdrücklich gepflegten Typ als Symbol ohne sichtbare Typplakette. Es gibt unterscheidbare Symbole für Limousine, Cross-Motorrad, Hochdachkombi, Naked Bike und Schrägheck; für Screenreader bleibt der Typ im Kartennamen verfügbar. Die Fahrzeugicons wurden nach Nutzerfeedback durch Icons aus Health Icons und Material Design Icons ersetzt; Quellen und Lizenzen stehen in [frontend/vehicle-icons-LICENSE.md](../../frontend/vehicle-icons-LICENSE.md). Peugeot, Yamaha Motor, Opel und Suzuki erhalten lokal bereitgestellte Logos, die groß, rechts angeschnitten und dezent ausgeblendet erscheinen. Für andere Marken erscheint der Herstellername. Unbekannte Typen bleiben unklassifiziert und erhalten ein neutrales Symbol. Herkunft und Hinweise zu den Markenabbildungen stehen in [frontend/brands/README.md](../../frontend/brands/README.md).

Auf Wunsch des Betreibers erscheinen vorhandene Kennzeichen zusätzlich als schwarz-weiße Schilder mit neutralem Seitenstreifen. Eine Länderkennung wird ohne entsprechende Angabe nicht angenommen. Fehlende Kennzeichen erzeugen keinen Platzhalter; auch lange und sonderzeichenhaltige Werte werden als Text behandelt.

Die im ursprünglichen Betreiberauftrag ausdrücklich bestätigten Hersteller-/Modellpaare sind nur in einer privaten Konfigurationsdatei auf dem Garage-Host hinterlegt. Die öffentliche Dokumentation enthält keine konkrete Flottenzuordnung. Der Abgleich nutzt das vollständige Paar aus Marke und Modell, ohne andere Fahrzeuge anhand ihrer Marke zu erraten. Fahrzeuge mit gleicher Marke und gleichem Modell teilen sich diese Vorbelegung.

Im Verlauf wurden ausdrücklich bestätigte Zuordnungen für weitere Fahrzeugarten und eine abweichende Modellvariante ergänzt. Eine Zuordnung wird nicht allein aus einem ähnlichen Modellnamen abgeleitet.

Für einzelne Fahrzeuge kann später in LubeLogger ein Zusatzfeld `Fahrzeugtyp` gepflegt werden; es hat Vorrang vor der privaten Vorbelegung. [Offizielle LubeLogger-Dokumentation](https://docs.lubelogger.com/Advanced/Additional%20Fields/). Der [isolierte Laufzeitnachweis](../discovery/vehicle-types-runtime.md) bestätigt den Leseweg für zwei synthetische Fahrzeug-Zusatzfelder; die Pflege über die native Oberfläche wurde damit nicht geprüft. Die private Datei wird beim Start gelesen; ihre Änderung erfordert derzeit einen Neustart des Adapters. Eine eigene Bearbeitungsoberfläche ist noch nicht implementiert.

## Einführung nach Freigabe

1. Aktuelle Konfiguration und Image des Dashboard-Adapters als Rückweg erhalten. Die privaten Typzuordnungen außerhalb des Repository in einem vom Administrator geschützten Verzeichnis ablegen; der Dateimount muss für die nicht privilegierte Adapter-UID lesbar sein.
2. Die neue Oberfläche, den Adapter und die [optionale Compose-Ergänzung](../../deploy/compose.vehicle-types.yaml) auf den bestehenden Garage-Container übertragen. Den Adapter gezielt neu bauen und neu starten; Router, LubeLogger, Cloudflare-Tunnel und Datenvolumes bleiben bestehen. Während des Adapterwechsels kann die Übersicht kurz nicht erreichbar sein.
3. Intern prüfen, ob die ausdrücklich zugeordneten Fahrzeuge die gewünschten Typen und Logos erhalten, ohne Fahrzeugdaten auszugeben oder zu verändern. Fehlende/ungeklärte Typen müssen neutral bleiben. Danach Cloudflare-Anmeldeschutz und Benutzeransicht prüfen.
4. Bei Fehlern den vorigen Adapterstand mit seiner vorherigen Compose-Konfiguration wiederherstellen; die LubeLogger-Datenbank wurde für die Zuordnungen nicht geändert.

Vor der Einführung geprüft: sieben synthetische Adaptertests, DOM-Tests für beide Typen, Logos, Kennzeichen und Fallback, Chromium auf 320/390/768/1280 Pixeln, Containerstart mit nicht privilegierter UID und privat gemounteter Beispielkonfiguration sowie ein isolierter LubeLogger-Lauf. Eine [mobile Vorschau](../discovery/evidence/vehicle-types-preview.png) zeigt synthetische Fahrzeuge.
