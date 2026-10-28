# WP01 — isolierter Routen-/Rechte-Spike

Zweck: Machbarkeit der Hypothese „native LubeLogger-Ansicht read-only, alle fachlichen Änderungen kontrolliert“ und native Dateigrenzen prüfen. **Kein produktiver Gateway, keine Schutzkonfiguration und keine Sicherheitsfreigabe.** Der [Ergebnisbericht](../../docs/discovery/wp01-runtime-verification.md) enthält den tatsächlichen Befund.

## Ausführen

```bash
python3 tests/wp01/run.py
```

Voraussetzungen wie beim [B01/B02-Testsatz](../lubelogger/README.md): Linux mit erreichbarer Docker-Brücke, Python-Standardbibliothek inklusive Zeitzonen, Docker Engine und Compose. Kein pip-Paket nötig. Verwendet dieselbe unveränderte, gepinnte [Sandbox-Compose-Datei](../lubelogger/compose.sandbox.yaml), aber einen eigenen zufälligen `wolfs-wp01-*`-Projektnamen und neue leere Volumes. Kein Ziel-URL-/Projekt-/Credentialparameter für fremde Systeme. Plattform linux/amd64; keine Hostports, internes Netz, CapDrop und Ressourcenlimits. Der laufende Image-ID wird gegen das gepinnte Image verglichen, auch bei Restore.

`helpers.py` enthält ausgewählte, mit Herkunfts-SHA belegte Kopien der B01/B02-Testhelfer, damit der bisherige Treiber und seine Evidenz unverändert bleiben. Anders als ein Import von dessen `run.py` erzeugt die Hilfsdatei keine Sandbox beim Import. Cookies/Passwörter/Keys bleiben im Prozess; Antwortkörper von Login/API-Keyerzeugung werden nicht als Testevidenz gespeichert.

## Rollen und unabhängige Beobachtung

Setup: Root für Einrichtung/Backup; Nicht-Root-Parent als direkter Collaborator zweier synthetischer Fahrzeuge; Household-Child mit explizit leeren Edit/Delete-Permissions; Outsider ohne Parentfahrzeugrechte. Kein direkter Collaboratorzugriff für den Child auf Parentfahrzeuge. Cookie-Sessions und reine API-Key-Clients bleiben getrennt.

Die Kilometer-Fixture wird über offizielle API-Anlage plus explizites API-Update auf einen Altzustand mit ausschließlich null Startständen gesetzt. **Vorher/Nachher niemals mit dem per-vehicle Kilometer-GET beobachten:** Dieser GET konvertiert den Bestand selbst. Beobachter ist `/api/vehicle/odometerrecords/all`, danach Zielfahrzeugfilter. Für nativen und öffentlichen mutierenden GET wird der Altzustand getrennt hergestellt. Fingerprints umfassen Fahrzeugstammdaten und relevante Belege.

Native MVC-Aufrufe dienen ausschließlich der synthetischen Prüfung, nicht einem späteren produktiven Garage-Integrationsvertrag. Der Helper folgt Redirects nicht automatisch: Native Root-Verweigerung kann 302 nach `/Error/403` sein; diese wird zusammen mit unverändertem Bestand geprüft. API-Verweigerungen und `success=false` werden separat bewertet.

Dateivarianten werden mit `http.client` als rohe Requesttargets gesendet, damit nicht schon der HTTP-Client Pfade normalisiert. HEAD liefert absichtlich keinen Body; Status/Länge sind kein Beweis einer Byteexfiltration. Preview-HTML, das einen bereits bekannten Pfad enthält, ist ebenfalls kein zusätzlicher Dokumentbyte-Nachweis.

## Enger Testproxy und seine Grenzen

Ein temporärer Python-HTTP-Server bindet ausschließlich an Loopback. Er akzeptiert einen zufälligen Testmarker, verwendet serverseitig den Household-Viewer-Key und erlaubt exakt:

- `GET /api/vehicles`: Antwort auf die zwei Test-Zielfahrzeuge gefiltert; Child-eigenes Neufahrzeug ausgeschlossen.
- `GET /api/vehicle/servicerecords?vehicleId=<explizite Test-ID>`: kanonisches vollständiges Requesttarget mit genau diesem Parameter.

Alles andere aus der getesteten Matrix wird vor Upstreamzugriff abgewiesen. Insbesondere Kilometer-per-vehicle-GET, native UI, Dateien/Temp/Preview, Upload, Admin, alternative Methoden/Pfadvarianten und doppelte/fremde Query-IDs sind **nicht erlaubt**. Der Proxy prüft das rohe Requesttarget vor Normalisierung durch den Pythonhandler. Die Evidenz enthält die weitergeleiteten Requests und bestätigt unveränderte Daten nach abgewiesenen Requests.

Der Marker ist **keine produktive Webauthentifizierung**, die zwei Routen sind keine vollständige native UI, es gibt keinen Audit-Write-Service und keine bewiesene Netzabschottung des Origins. Der Host kann absichtlich direkt auf die Container-IP zugreifen; die Outsider-Datei bleibt dort lesbar. Ein künftiger Origin muss aus untrusted Zonen vollständig unerreichbar sein, bevor eine solche Vermittlung schützen kann. Den Testserver nicht als Deploymentvorlage verwenden.

## Ergebnis und Lebenszyklus

`.sandbox/<projekt>/results.json` enthält bereinigte Checks und Beobachtungen. `backup.zip` mit synthetischen Daten/Credential-Hashes bleibt ausschließlich im ignorierten 0700-Laufverzeichnis. `pass` bestätigt den benannten Vertrag, `gap` reproduziert eine Grenze oder bewusst nicht gelöste Testtopologie, `fail` bricht bei unerwartetem Ergebnis ab. Gaps sind keine Anzahl unabhängiger Sicherheitslücken.

Bei regulärem Ende und Fehler stoppt `finally` beide Container und schließt die lokalen Listener. Images, gestoppte Container, Netze und synthetische Volumes werden nicht automatisch gelöscht. SIGKILL/Hostausfall kann den Abschluss verhindern; dann Projektnamen prüfen. Keine produktiven Systeme, Cloudflare-Ressourcen oder echten Fahrzeugdaten werden verwendet.

[route-inventory.json](route-inventory.json) ist ein statisches, quellengebundenes Rohinventar (329 Deklarationen), **keine vollständig getestete/deploybare Routingallowlist**. Der [unabhängige Quellbericht](../../docs/discovery/wp01-route-review.md) erläutert Parsing-/Reachabilitygrenzen. Versionierte [Runtime-Evidenz](../../docs/discovery/evidence/wp01.json) enthält Hashes von Treiber, Helfern, Inventar und unveränderter Basiskonfiguration.
