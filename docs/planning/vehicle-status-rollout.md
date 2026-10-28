# Fahrbereitschaft und offene Punkte

> Anonymisierte historische Dokumentation für das öffentliche Repository. Betriebsdomain, Host-/Speicherkennungen und private Pfade sind Beispiele; konkrete Betreiberzuordnungen sind verallgemeinert. Kein direkt ausführbares Runbook. Die unveränderten Originale liegen ausschließlich lokal unter dem ignorierten Verzeichnis `.sandbox/private-ops/`. Prüfresultate betreffen die damals untersuchte Instanz, nicht die hier eingesetzten Beispielwerte.

Stand 2026-10-28. Implementierung und synthetische Tests sind abgeschlossen; die bestehende produktive Garage wurde für diese Funktion noch nicht geändert.

## Verhalten

In der bestehenden Kopfzeile zeigt ein gelb-schwarzes, doppelt umrandetes **INOP**-Schild **nicht fahrbereit**; ein Fragezeichen kennzeichnet **nicht erfasst**. Fahrbereite Fahrzeuge bekommen kein Bereitschaftssymbol. Ein schlichtes Werkzeugsymbol ohne Zähler zeigt offene Wartungs- oder Reparaturpunkte, unabhängig von der Fahrbereitschaft. Dadurch passen alle Hinweise in die vorhandene Kartenhöhe; die Texte der offenen Punkte stehen im Detailbereich. Der Betreiber kann Fahrbereitschaft und Punkte dort getrennt bearbeiten. Ein fahrbereites Fahrzeug kann offene Arbeiten haben. Die Garage leitet keine Fahrbereitschaft aus TÜV, Erinnerungen oder anderen Daten ab und ergänzt weder Fristen noch Diagnosen.

Der Betreiber hat zu ausgewählten Fahrzeugen konkrete Zustände und offene Punkte genannt. Diese können nach Freigabe einmalig übernommen werden; die übrigen Fahrzeuge bleiben `nicht erfasst`. Einträge werden anhand expliziter Hersteller-/Modellnamen eindeutig auf vorhandene Fahrzeug-IDs aufgelöst. Mehrdeutige oder fehlende Treffer sowie bereits gesetzte Zustände blockieren die gesamte Erstübernahme, statt Informationen einem anderen Fahrzeug zuzuweisen. Die einzelnen persönlichen Angaben werden nicht in dieses Repository geschrieben.

Eine lesende Vorprüfung der laufenden Fahrzeugliste ergab für die ausgewählten Ziele jeweils genau einen Treffer und vollständige Identitätsfelder. Persönliche Fahrzeugdaten wurden nicht ausgegeben. Die Bedingungen müssen unmittelbar bei der späteren Übernahme erneut geprüft werden, da sich der Datenbestand ändern kann.

## Speicherung und Sicherheit

Die Funktion speichert ihren Zustand separat von LubeLogger in einem neuen dauerhaften SQLite-Volume. Änderungen an Status und offenen Punkten werden zusammen mit einer Historie atomar gespeichert; der Logeintrag behauptet keine nachgewiesene Cloudflare-Identität. Ein vorhandener Punkt behält seine ID und verschwindet bei Erledigung aus der offenen Liste, bleibt aber im Verlauf nachvollziehbar. Revisionen schützen vor versehentlichem Überschreiben paralleler Änderungen.

Die bestehenden Cloudflare-Access- und privaten Netzwerkgrenzen bleiben bestehen. Der neue Schreibendpunkt verlangt zusätzlich einen fest konfigurierten HTTPS-Origin und Host, JSON sowie einen eigenen Header; fremde und fehlende Origins werden abgelehnt. Das ist CSRF-Schutz und ersetzt nicht die vorgelagerte Access-Anmeldung. Kein Schreibzugriff auf LubeLogger wird durch den Adapter eingeführt.

Der Status wird der LubeLogger-ID mit einem Fingerprint aus Betreiberkonfiguration, Hersteller, Modell und Baujahr zugeordnet. Ändern sich diese Daten, blockiert die Zuordnung zur Prüfung. Eine wiederverwendete ID mit identischen Stammdaten ist damit nicht sicher erkennbar; bei Restore oder Neuanlage ist die Zuordnung manuell zu prüfen. Ein beschädigter oder fehlender Statusspeicher führt bewusst zu einem sichtbaren Fehler, nicht zu einer erfundenen Entwarnung.

## Vorgesehene produktive Einführung nach Freigabe

1. Aktuelle Gateway-Version und laufende Konfiguration als Rückweg erhalten; kein Löschen oder Überschreiben bestehender Volumes. Die bestehende LubeLogger-Instanz und ihre Daten bleiben unverändert.
2. Das neue Image und die [Compose-Ergänzung](../../deploy/compose.vehicle-status.yaml) bereitstellen. Ein neues Status-Volume einmal ausdrücklich initialisieren; eine bereits vorhandene Datenbank wird niemals erneut initialisiert. Öffentlichen Origin und stabile Providerkennung fest konfigurieren.
3. Die ausdrücklich genannten Fahrzeugzustände mit dem getesteten Erstübernahmewerkzeug in einem privaten Vorgang eindeutig zuordnen und atomar speichern. Bei uneindeutigem Treffer oder vorhandenem Status abbrechen und prüfen. Andere Fahrzeuge erhalten keinen unterstellten Zustand.
4. Eine konsistente SQLite-Sicherung des neuen Statusvolumes einschließlich Historie erstellen, auf dem vorhandenen unabhängigen Backup-Speicher ablegen und auf Integrität prüfen. Der bestehende ältere LXC-Snapshot allein enthält die neuen Daten nicht. Ein regelmäßiger Backupplan und eine isolierte Restore-Probe bleiben zusätzlich erforderlich.
5. Nur den Gateway mit dem neuen Volume starten. Intern Abruf und geschützte Speicherung prüfen, danach anonymen Access-Schutz und die persönliche Browseransicht prüfen. Bei Problemen das bisherige Gateway-Image und die bisherige Compose-Konfiguration wiederverwenden; das neue Volume bleibt zur Prüfung erhalten.

Die Änderung erfordert ein produktives Deployment. Cloudflare-Routen, die Access-Policy und LubeLogger-Daten werden dafür nicht umgestellt.

## Nachweise

- 21 synthetische Backendtests inklusive Status-Historie, konkurrierender Bearbeitung, Identitäts- und Speicherfehler, CSRF-Varianten, atomarer Erstübernahme und SQLite-Backup/Restore des synthetischen Stands.
- Frontend-Mocktests für Fahrbereitschaft mit offenen Punkten, Bearbeitung und Konflikt-/Fehlerfälle.
- Chromium-Prüfung auf vier Bildschirmbreiten, einschließlich gleicher Kartenhöhe auf Mobilgeräten; eine [kompakte mobile Vorschau](../discovery/evidence/vehicle-status-compact-preview.png) zeigt ausschließlich synthetische Fahrzeuge und Aufgaben.
- Ein echter Bearbeitungs- und Reload-Ablauf lief lokal über HTTPS und Nginx gegen den synthetischen SQLite-Speicher; eine fremde Origin erhielt 403. Der tatsächliche Cloudflare-Login und die Produktionsumgebung waren daran nicht beteiligt.
- Das finale Image baute erfolgreich. Der ausdrücklich initialisierte Statusspeicher und eine SQLite-Sicherung wurden in einem nicht privilegierten Container mit synthetischem Named Volume geprüft. Ein echtes externes Backup oder Restore wurde für diese neue Funktion noch nicht durchgeführt.
