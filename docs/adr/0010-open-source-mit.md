# ADR-0010 — Wiederverwendbare Open-Source-Anwendung unter MIT

- Status: **Entschieden**
- Datum: 2026-10-28
- Entscheider: Betreiber/Nutzer, ausdrückliche Wahl von MIT

## Entscheidung

Wolfs Garage wird als eigenständige Anwendung entwickelt, die auch andere Betreiber selbst installieren können. Der eigene Projektcode wird unter MIT lizenziert; die [Root-Lizenz](../../LICENSE) enthält den Lizenztext. Fremdkomponenten und Markenabbildungen bleiben gesondert in [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md) ausgewiesen.

Jede Installation besitzt eigene Konfiguration und Fahrzeugdaten. Das Repository enthält generische Beispiele und synthetische Nachweise. Die Veröffentlichung umfasst keine persönlichen Fahrzeugdaten, Originaldokumente, Geheimnisse oder privaten Betriebsdaten. Historische Betriebsberichte werden anonymisiert, private Originale bleiben außerhalb der versionierten Quelle.

Der neue Kern benötigt weder LubeLogger noch eine verpflichtende Cloud-API. Das vorhandene Cloudflare-Referenzdeployment bleibt ein möglicher Authentifizierungsweg. Andere Betreiber können einen anderen authentifizierenden Reverse-Proxy einsetzen. Der erste Dienst bietet selbst kein Login und veröffentlicht seinen Port im Compose-Entwurf nur auf Loopback; öffentlich erreichbarer Betrieb braucht die vorgelagerte Anmeldung.

## Konsequenzen

- Installation, Alpha-Grenzen, Konfiguration, Datenbankinitialisierung, Sicherung und isolierter Restore müssen verständlich dokumentiert sein.
- Bibliotheken, Artefakte und Beispiele dürfen keine Betreiberidentität fest einbauen. Schemaänderungen brauchen einen geprüften Übergang; inkompatible Datenbanken dürfen nicht automatisch zurückgesetzt werden.
- Der Quellstand muss vor Veröffentlichung einschließlich seiner Historie geprüft werden. Ignore-Regeln allein bereinigen bereits veröffentlichte oder getrackte Daten nicht.
- Diese Entscheidung ist keine Aussage, dass bereits eine öffentliche Alpha veröffentlicht oder der produktive Bestand migriert wurde.

Siehe [eigenständiger Betrieb](../standalone.md), [Veröffentlichungsvorbereitung](../open-source-release.md) und [ADR-0009](0009-backend-ownership-challenge.md).
