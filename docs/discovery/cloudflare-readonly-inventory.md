# Cloudflare-Bestandsaufnahme für den Ein-Nutzer-Zugang

> Anonymisierte historische Dokumentation für das öffentliche Repository. Betriebsdomain, Host-/Speicherkennungen und private Pfade sind Beispiele; konkrete Betreiberzuordnungen sind verallgemeinert. Kein direkt ausführbares Runbook. Die unveränderten Originale liegen ausschließlich lokal unter dem ignorierten Verzeichnis `.sandbox/private-ops/`. Prüfresultate betreffen die damals untersuchte Instanz, nicht die hier eingesetzten Beispielwerte.

Stand: 2026-10-27. **Nur lesender Kontozugriff** über das verfügbare Cloudflare-Plugin; keine Cloudflare-Ressourcen erzeugt, geändert, aktiviert oder gelöscht. Das Login-/Adminmodell wurde durch den Nutzer geklärt: ein Cloudflare-Login, danach volle Adminrechte. [ADR-0008](../adr/0008-single-user-access.md).

## Abgefragter Bestand

Gezielt und ausschließlich per GET: Kontoliste, Access-Anwendungen, Tunnel, Identity-Provider, Zonen sowie ein exakter DNS-Namenscheck. In diesem öffentlichen Repository werden bewusst keine Account-IDs, Zugangsdaten, E-Mail-Adressen, vorhandenen privaten Hostnamen, Tunnel-IDs oder anderen persönlichen Kontodetails abgelegt.

| Abfrage | Lesendes Ergebnis | Einordnung |
| --- | --- | --- |
| Konten | Ein für die Prüfung freigegebenes Konto verfügbar | Keine Kontenauswahl für diese Bestandsaufnahme erforderlich. |
| Access-Anwendungen | Bestehende Self-hosted-Anwendungen; keine bei der Namens-/Hostnamensuche mit `garage` gefunden | Bestehende Apps werden nicht verändert. Die Suche ist keine vollständige Wildcard-/Policyanalyse. |
| Cloudflare-Tunnel | Bestehende Tunnel mit unterschiedlichen Zuständen; mindestens einer wurde als `healthy` gemeldet | Für den als gesund gemeldeten Tunnel meldet die API `config_src=local` und liefert eine Konfigurationsansicht mit mehreren Ingress-Einträgen; darin wurde kein Hostname mit `garage` gefunden. Bei lokal verwalteter Konfiguration muss der tatsächlich laufende Konfigurationsstand am jeweiligen Host geprüft werden. Daraus folgt nicht, dass dieser Tunnel für Wolfs Garage geeignet ist; bestehende Routen/Verbindungen bleiben unangetastet. |
| Identity-Provider | Ein One-Time-PIN-Anbieter | Ein vorhandener Anmeldungstyp ist vorhanden; tatsächliche Betreiber-E-Mail/Policy muss später passend konfiguriert und getestet werden. |
| DNS-Zonen | Mehrere sichtbare Zonen; eine aktive Zone wurde anhand eines betreiberspezifischen Namensfilters als Kandidat identifiziert | Ein möglicher Kandidat, keine automatisch beschlossene Projektdomain. |
| DNS-Vorprüfung | In dieser einen Kandidatenzone gab es für den exakten Namen `garage.<Zone>` keinen expliziten DNS-Eintrag. | Kein Nachweis, dass Wildcards, bestehende Access-Muster oder Tunnelrouten die Adresse unbelegt machen. Keine DNS-Änderung erfolgt. |

Die konkreten GET-Endpunkte wurden vorab im Cloudflare-OpenAPI-Schema nachgeschlagen. Ergebnisse sind eine zeitpunktbezogene Bestandsaufnahme; sie können sich ändern. Ein vorhandener Tunnel oder eine vorhandene Access-Policy wird nicht ungeprüft mitbenutzt oder umkonfiguriert.

## Konsequenz für das Projekt

Die vorhandene Infrastruktur deutet darauf hin, dass eine browserbasierte Cloudflare-Access-Anmeldung grundsätzlich in das Konto integrierbar ist. Als einfacher Entwurf wird eine passende Access-Anwendung vor einem privaten LubeLogger-Origin vorbereitet; ob ein bestehender Tunnel geeignet ist oder ein eigener sinnvoller ist, hängt vom Homelab-Netz und bereits vorhandenen Routen ab. Es wird weder ein Hostname noch eine Identität ohne ausreichende Grundlage festgelegt.

Der [isolierte LubeLogger-Test](single-owner-access.md) zeigt, dass bei deaktivierter nativer Authentifizierung jeder interne Originaufruf Admin ist. Daher sind **tatsächliche Access-Policy, Tokenvalidierung, Origin-Zugangswege und getrennter Telegram-/Servicezugang** vor einer späteren Veröffentlichung zu prüfen. Die hier vorhandenen Cloudflare-Ressourcen zeigen weder eine bereits geschützte Wolfs-Garage-Anwendung noch einen durchgeführten Ende-zu-Ende-Login.

Cloudflare dokumentiert für `cloudflared` ab 2026.10.0 eine optionale URL-Normalisierung vor dem Ingress-Abgleich; sie war in 2026.10.0 standardmäßig aus. Welche Version und Einstellung auf dem vorhandenen Connector läuft, wurde nicht geprüft. Bei einer späteren Routenänderung müssen Normalisierung und Access-Abdeckung deshalb konkret anhand der Zielversion geprüft werden. Quelle: [Cloudflare Origin-Parameter](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/origin-parameters/).

Die offizielle Anleitung beschreibt [Self-hosted-Access, Tunnel und Tokenvalidierung](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/). Alle konkreten Produktiv- oder Cloudflare-Änderungen bleiben gemäß AGENTS.md explizit freigabepflichtig; diese Bestandsaufnahme ist keine solche Änderung oder Freigabe.
