# Vorbereitung: ein Cloudflare-Login für Wolfs Garage

Stand: 2026-10-27. Planungsstand, keine ausgeführte Konfiguration. Die Produktvorgabe ist ein Cloudflare-Login und danach Administratorzugriff für alle zugelassenen Webnutzer. [ADR-0008](../adr/0008-single-user-access.md) beschreibt die technischen Alternativen; hier wird der einfache Weg mit deaktivierter nativer LubeLogger-Anmeldung vorbereitet.

## Ausgangspunkt und noch fehlende Werte

Die [lesende Bestandsaufnahme](../discovery/cloudflare-readonly-inventory.md) fand einen One-Time-PIN-Anbieter und einen als gesund gemeldeten, lokal verwalteten Tunnel. Es wurde keine Garage-Anwendung angelegt. Die vorhandene Tunnelkonfiguration und die tatsächliche Version auf dem Host sind vor einer möglichen Wiederverwendung zu prüfen; bestehende Anwendungen und Routen dürfen dadurch nicht beeinträchtigt werden. Ein eigener Tunnel bleibt eine Alternative. Der genaue Hostname und die zu erlaubende Betreiberidentität sind noch nicht festgelegt; weder die Kontoidentität noch ein vorgeschlagener Domainname werden stillschweigend übernommen.

Für die spätere Einrichtung werden benötigt: Betreiberidentität für die Access-Policy, gewünschter Hostname und passende Zone, Zielhost und Containernetz, Auswahl und tatsächlich laufende Konfiguration des Connectors sowie ein Wiederherstellungsweg. Konkrete Zugangsdaten, E-Mail-Adressen, Account-IDs und Tunnel-Credentials gehören nicht ins Repository.

## Vorgesehene Reihenfolge

1. **Zielumgebung prüfen:** Host, Netzpfade, vorhandene Tunnelrouten und DNS einschließlich Wildcards und überlappender Access-Anwendungen erfassen. LubeLogger-Daten und Backups noch nicht migrieren. Testumgebung und tatsächliche Versionen separat festhalten.
2. **Privaten Origin vorbereiten:** LubeLogger nur auf einem dafür vorgesehenen internen Netz betreiben, ohne öffentlich oder im LAN veröffentlichten App-Port. Connector und ausdrücklich vorgesehene interne Dienste erhalten die nötige Verbindung; andere Container und Netze nicht. Der Docker-Host selbst ist ein vertrauenswürdiger Administrationszugang und kann Container unter Umständen direkt erreichen; ein internes Docker-Netz allein isoliert nicht vom Host.
3. **Access vor Veröffentlichung einrichten:** Eine Self-hosted-Anwendung für den später bestätigten Hostnamen anlegen und die Policy auf die bestätigte Betreiberidentität beschränken. Den vorhandenen One-Time-PIN-Anbieter nur verwenden, wenn er für diese Identität und den gewünschten Recovery-Weg tatsächlich geeignet ist. Ohne passende Allow-Policy darf kein Zugriff möglich sein. Die Anwendung muss alle benötigten App-, API-, Upload- und Dokumentpfade abdecken.
4. **Connector und Route festlegen:** Einen geeigneten Tunnel auswählen oder separat bereitstellen und die neue Route zur privaten Anwendung konfigurieren. Für den Tunnelverkehr **Protect with Access** mit den zur Anwendung gehörenden Werten aktivieren und die konkrete Konfiguration anhand der eingesetzten Connector-Version prüfen. Bei lokal verwaltetem Tunnel ist die tatsächlich laufende lokale Konfiguration maßgeblich; bestehende Ingress-Reihenfolge und Catch-all-Regeln dürfen nicht versehentlich verändert werden. URL-Normalisierung und Pfadabdeckung für die verwendete Version prüfen.
5. **Erst nach erfolgreicher Prüfung DNS/Erreichbarkeit herstellen:** Den bestätigten Hostnamen auf den vorgesehenen Tunnel zeigen lassen und anschließend die untenstehenden Positiv- und Negativtests durchführen. Die genaue Reihenfolge und Rückfallmöglichkeit muss bei der konkreten Zielkonfiguration überprüft werden, damit eine neue Route nicht vor Access öffentlich erreichbar wird.

Das ist eine Vorbereitung für eine spätere, gesondert freigegebene Änderung. Es wurde hier weder ein Tunnel noch eine Access-App, Policy, DNS-Route oder ein produktiver Dienst erstellt oder geändert. Cloudflare-Änderungen und produktive Deployments benötigen nach AGENTS.md explizite Freigabe; produktive Migrationen und Löschungen ebenfalls.

## Abnahmetests für die tatsächliche Umgebung

| Fall | Erwartung |
| --- | --- |
| Browser ohne Access-Sitzung | Anmeldung erforderlich; keine App-, API- oder Dokumentdaten sichtbar. |
| Zugelassene Identität | Ein Cloudflare-Login; danach native LubeLogger-Weboberfläche mit Adminfunktionen ohne weiteres interaktives Login. |
| Andere Identität | Access verweigert den Zugriff. |
| Fehlendes, manipuliertes, abgelaufenes oder für eine andere Anwendung ausgestelltes Token am Connector | Zugriff wird verweigert; ein selbst gesetzter Identitätsheader ersetzt keine Tokenprüfung. |
| Direkter Zugriff aus Internet, LAN und nicht vorgesehenem Containernetz | Origin, API, Uploads, Dokumente und Backups sind nicht erreichbar; gesondert dokumentierter Zugriff vom vertrauenswürdigen Administrationshost ist hiervon zu unterscheiden. |
| Interner Bot-/Dienstzugriff | Nur ausdrücklich vorgesehene Dienstverbindungen; Telegram-User-ID-Allowlist, Bestätigung und Aktionsprotokoll werden unabhängig vom Browserlogin geprüft. |
| Cross-Site-Anfrage im tatsächlichen Browser | Cookie-/CSRF-Verhalten der konkreten Access- und App-Konfiguration prüfen; der frühere HTTP-Test mit künstlich injiziertem Cookie beweist keine Browserausnutzbarkeit. |
| Ausfall von Access, Connector oder OTP und Wiederherstellung | Erwartetes Fehlerverhalten und ein getesteter administrativer Wiederherstellungsweg sind dokumentiert, ohne den Origin allgemein freizugeben. |

Bei deaktivierter nativer Authentifizierung behandelt LubeLogger jeden erfolgreichen Originaufruf als Admin; ein API-Key begrenzt diese Aufrufer in diesem Modus nicht. Das wurde [isoliert mit synthetischen Daten getestet](../discovery/single-owner-access.md). Eine Access-Tokenprüfung am Connector schützt nur Verkehr, der diesen Connector tatsächlich durchläuft. Die Ende-zu-Ende-Fälle oben sind bislang nicht ausgeführt.

## Weitere Grenzen

Die Ein-Admin-Vorgabe löst weder die fachlichen Anforderungen an Änderungsprotokoll und Problemhistorie noch Backup/Restore und Reminder-Berechnung. Native Webhook-Ereignisse sind eine mögliche Grundlage für ein späteres Aktivitätsjournal, aber kein nachgewiesenes vollständiges Audit; siehe [Auditprüfung](../discovery/wp02-audit-assessment.md). Bei Auth-off setzt LubeLogger für Originaufrufe denselben internen Admin-Actor; daraus lässt sich keine validierte Cloudflare-Identität oder Kanalzuordnung ableiten.

Offizielle Grundlagen: [Cloudflare Self-hosted Access](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/), [Tunnel-Origin-Parameter und Protect with Access](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/origin-parameters/). Diese Planung ist keine Aussage, dass die konkrete Kontokonfiguration bereits funktioniert.
