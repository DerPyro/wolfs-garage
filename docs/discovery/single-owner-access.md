# Ein Cloudflare-Login und Adminzugriff — technische Einordnung

Stand: 2026-10-27. Der Nutzer möchte Cloudflare Access als interaktive Anmeldung; alle zugelassenen Webnutzer haben volle Administratorrechte. Eine Fahrzeug- oder Dokumentrollentrennung zwischen angemeldeten Webnutzern ist kein Produktziel. [ADR-0008](../adr/0008-single-user-access.md) hält diese Produktvorgabe fest. Technische Umsetzung und Betreiber-/Cloudflare-Daten sind noch offen.

## Kleiner isolierter Nachweis

Mit der gepinnten LubeLogger-Testbaseline v1.7.4 wurde eine neue Instanz **ohne native Authentifizierung** ausschließlich auf internem Docker-Netz gestartet. Es gab keine Cloudflare-Verbindung oder produktive Daten. [Neun Checks](evidence/single-owner.json) wurden bestanden; der Container ist gestoppt. Reproduktion: `python3 tests/wp02/single_owner.py`, neuer zufälliger Projektname, gleiche isolierte [Compose-Testdatei](../../tests/lubelogger/compose.sandbox.yaml).

| Beobachtung | Bedeutung für den gewünschten Betrieb |
| --- | --- |
| Startseite antwortet ohne native Login-Weiterleitung. | Kein zusätzliches LubeLogger-Login in diesem getesteten Modus. |
| `/api/whoami` ordnet einem unberechtigten internen Aufruf den Root-/Admin-Principal zu. | Alle Anfragen, die den Origin erreichen, erhalten in diesem Modus die höchsten nativen Rechte. |
| Fahrzeuganlage, Dokument-Upload/-Abruf und Root-Backup funktionieren ohne Zugangsdaten. | Der gewünschte Vollzugriff funktioniert; die Zugangskontrolle muss vor dem Origin zuverlässig greifen. |
| Auch ein ungültiger API-Key verhindert den API-Zugriff nicht. | Native API-Key-Rollen schützen in diesem Modus interne Aufrufer nicht; Zugänge für Bot/Services müssen durch Netz- und Dienstgrenzen kontrolliert werden. |
| Der lokale Testhost erreicht den Origin direkt. | Das ist die gewollte Testtopologie; sie beweist gerade **keine** Isolation vor anderen Netzen oder Containern. |

Diese Tests zeigen das Verhalten der LubeLogger-Basiskonfiguration, **keinen** erfolgreichen Cloudflare-Login, keine echte Access-Policy und keinen negativen LAN-/Internet-/Container-Bypasstest. Es wurde keine Instanz mit echten Daten veröffentlicht. API-/Datei-/Backupzugriff ist für zugelassene Admins ausdrücklich Teil des Produktmodells; unbekannte Aufrufer dürfen den Browser-Login bzw. die vorgesehenen Dienstgrenzen später nicht umgehen.

## Zielweg und technische Optionen

Browser → Cloudflare Access → Tunnel → isolierter LubeLogger-Origin. Die Policy soll die Betreiberidentität zulassen; konkrete Identität und IdP sind noch nicht bekannt. Cloudflare empfiehlt für selbst gehostete Apps die Validierung des Access-Application-Tokens und nennt **Protect with Access** am Tunnel als eine Option. Diese Prüfung gilt für den Verkehr über den Connector; ein alternativer direkter Originweg muss unabhängig verhindert bzw. geprüft werden. [Cloudflare: Self-hosted-Apps und Tokenvalidierung](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/).

Zwei mögliche technische Umsetzungen unter derselben Vorgabe eines interaktiven Logins:

1. **Einfacher Ausgangspunkt:** Native LubeLogger-Authentifizierung aus, Cloudflare Access für den Browser, isolierter Origin, ausschließlich vorgesehene interne Dienstverbindungen. Der obige Test zeigt, dass jeder erfolgreiche interne Zugriff dann Admin ist. Vor Produktivbetrieb muss man diese Vertrauensgrenze und den Wiederherstellungsweg tatsächlich nachweisen.
2. **Transparentes SSO:** Native LubeLogger-Authentifizierung verwenden, sofern der ausgewählte Identity-Provider und OIDC-Flow mit Cloudflare und LubeLogger in einer Sandbox ohne zusätzliches manuelles Login zusammenspielen. Cloudflare dokumentiert [generisches OIDC für Anwendungen](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/saas-apps/generic-oidc-saas/); das beweist noch nicht die Kombination mit konkreter LubeLogger-Installation, Selbsthosting/Tunnel, Sessionverwaltung oder Betreiber-IdP.

Die Wahl zwischen beiden Wegen ist eine technische Entscheidung nach reproduzierbarer Konfiguration und Tests, kein Anlass für eine zweite nutzerseitige Rollenverwaltung. Zum jetzigen Zeitpunkt ist Weg 1 der einfachere Vorschlag, keine getestete Produktionskonfiguration und keine Freigabe zur Cloudflare-Änderung. Der Telegram-Bot benötigt trotz globaler Web-Adminrolle eine eigene User-ID-Allowlist, Bestätigung und Audit seiner Aktionen.

## Was weiterhin zu prüfen ist

- Access-Policy lässt die beabsichtigte Identität durch und verweigert anonyme/andere nicht zugelassene Identitäten. Alle App-, API-, Upload-, Temp- und Dokumentpfade hängen hinter demselben Zugang.
- Origin ist aus nicht vorgesehenen LAN-/Containersegmenten und aus dem Internet nicht direkt erreichbar; dem Connector zugeordnete Tokenprüfung und Fehlerfälle sind praktisch nachzuweisen.
- Welche internen Dienste Adminzugriff benötigen, wie ihre Verbindungen eingeschränkt werden und wie bei Ausfall/Verlust der Access-Anmeldung die Wiederherstellung erfolgt.
- Browser-/CSRF-Verhalten bei der konkreten Auth- und Origin-Topologie; ein früherer HTTP-Test mit injiziertem Cookie ist kein vollständiger Browsernachweis.
- Native Änderungshistorie gemäß REQ-043, Problemhistorie REQ-020, Tagesgrenzen, Teile-/Kosten- und Backupfälle bleiben fachlich unabhängig von der Web-Rollenentscheidung.

Quellen und aktuelle Aussagen oben abgerufen 2026-10-27. Der isolierte Test griff auf kein Cloudflare-Konto zu. Danach erfolgte eine getrennte [lesende Cloudflare-Bestandsaufnahme](cloudflare-readonly-inventory.md); keine Ressourcenänderung, kein produktiver Dienst, keine Migration/Löschung. Vertrauliche Testartefakte bleiben unter `.sandbox/` ignoriert; das versionierte Ergebnis enthält keine Geheimnisse.

Bei deaktivierter nativer Authentifizierung erzeugt die [geprüfte Middleware](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Middleware/Authen.cs) für direkte Anfragen denselben internen Namen `admin`. Ein späteres Änderungsjournal darf deshalb aus dem LubeLogger-Actor allein keine Unterscheidung verschiedener Kanäle oder eine kryptografisch nachgewiesene Cloudflare-Nutzeridentität ableiten. Für dieses Ein-Nutzer-Modell genügt die einheitliche Rolle, die fachliche Protokollabdeckung bleibt separat zu prüfen.
