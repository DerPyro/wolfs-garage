# ADR-0003 — Isolierter Betrieb mit eigener Autorisierung und Restore

Status: **Vorgeschlagen** · Datum: 2026-10-26 · Entscheidung: offen

> **Scope-Fortschreibung 2026-10-27:** Ein interaktives Cloudflare-Login, danach globaler Adminzugriff: [ADR-0008](0008-single-user-access.md). Native Zugangsdaten/mehrere Objektrollen sind keine eigenständige Produktanforderung; Authentifizierungsweg, Origin-/Dienstgrenzen und Recovery bleiben zu prüfen. Die nachfolgende ursprüngliche Bedrohungs- und Testhistorie bleibt als Kontext erhalten.

## Kontext

Docker auf Proxmox und externer Webzugriff über Cloudflare Tunnel/Access sind Produktvorgaben. Hostinventar, Identitätsanbieter, Backupziele und Wiederanlaufziele fehlen. Access ersetzt weder native Anwendungsauthentifizierung noch serverseitige Fahrzeugrechte.

## Empfehlung

Dedizierten Docker-Host bevorzugt als VM betreiben; unprivilegiertes LXC nur nach belegter Unterstützung von Docker/Nesting, UID-Mapping, Ressourcen und Wiederherstellung. Kein privilegiertes LXC als Bequemlichkeitslösung. Dienste nur intern verbinden; keine Router-Portfreigabe und keine öffentlichen DB-/API-Ports. `cloudflared` erhält ausschließlich benötigte Origin-Ziele, Datenbanknetz bleibt getrennt. Vor Veröffentlichung die gewählte Access-/Origin-Variante, tokenvalidierte Webpfade und mögliche Bypässe prüfen; native LubeLogger-Authentifizierung ist optional, wenn die einfache Variante mit abgeschottetem Origin gewählt wird.

Garage-Web/API prüft die über Access zugelassene Identität an einer vertrauenswürdigen Servergrenze und gewährt ihr globalen Zugriff; es braucht keine unterschiedlichen Fahrzeugrollen. Für Cookie-Sessions ist CSRF-Schutz zu prüfen. Ein Access-Header allein gilt nicht als Identitätsnachweis; JWT-Prüfung mit Issuer/Audience/Signatur oder unabhängig authentifizierte Session ist erforderlich. API-Adapter nutzen einen kontrollierten Dienstzugang; native API-Key-Rollen wirken nur bei eingeschalteter LubeLogger-Authentifizierung. Telegram startet vorzugsweise per Long Polling, mit numerischer User-ID-Allowlist und privatem Chat. Jobs und Direktzugriffe verwenden dieselben Domänenberechtigungen.

Secrets außerhalb von Git, restriktive Dateirechte, Rotation und Log-Redaktion. Umgebungsvariablen sind keine automatische Verschlüsselung. Compose-Vorlage beschreibt nur Grenzen; keine Produktivkonfiguration.

Konsistente Sicherungen umfassen LubeLogger-Daten und Anhänge/Konfiguration, Garage-Datenbank samt Audit/Outbox, Paperless-Referenzen und separat geschützte benötigte Schlüssel. Vor Restore ausgehende Jobs pausieren und Telegram-Offset, Outbox und Kalenderabgleich kontrollieren, um Wiederholungen zu vermeiden. Restore isoliert nachweisen.

## Alternativen und Folgen

Ein Cloudflare-Login ohne geprüfte Origin-Abgrenzung und privilegiertes LXC sind nicht empfohlen. VM und verschlüsselte Backups bedeuten zusätzlichen Betrieb; ein zweites interaktives Login ist keine Produktvorgabe. Konkrete Verfahren und Quellen: [Betrieb/Security](../discovery/operations-security.md).

## Offene Entscheidung und Nachweise

VM/LXC, Hostarchitektur, Identität/Recovery-Zugang, Secretablage, Retention, RPO/RTO und externes Backupziel festlegen. Beispielsweise RPO 24 h/RTO 4 h sind nur Diskussionswerte. Restore und Origin-/Autorisierungs-Negativtests sind vor produktiver Freigabe erforderlich. Keine Cloudflare- oder Infrastrukturänderung durch diesen ADR autorisiert.

## B02-Nachtrag: Dokumentberechtigung vor Freigabe entscheiden

Die [Sandbox](../discovery/lubelogger-runtime-verification.md) belegt: Anonymer Dokumentzugriff wird abgewiesen, ein angemeldeter Outsider ohne Fahrzeugrechte kann einen bekannten nativen Dokumentpfad dennoch lesen. Unter der früher angenommenen Mehrbenutzertrennung verletzt dies eine solche Abgrenzung; nach der geklärten Ein-Admin-Vorgabe ist eine Trennung zwischen zugelassenen Webnutzern nicht erforderlich. Die Grenze gegen nicht zugelassene Aufrufe muss über den tatsächlich abgesicherten Access-/Originweg erfüllt werden; ein schwer erratbarer Dateiname ist kein Login. Normale Fahrzeug-/Beleg-APIs respektierten die geprüften Objektberechtigungen.

**Offene Entscheidung B16:** Paperless als alleinige sensible Dokumentablage mit aktuellen Objektberechtigungen und nachgewiesener Sperre nativer Dokumentpfade/Uploads vorsehen, oder eine belegte Upstream-/Proxy-Lösung wählen, die auch native Browser-, API-, Temp- und Wiederherstellungswege abdeckt. Nur Garage-Proxy-Prüfungen schützen den direkten LubeLogger-Dateipfad nicht. Keine fremde DB manipulieren oder Schutzwirkung eines bloßen versteckten Links annehmen. Vor Nutzung echter Dokumente muss der gewählte Access-/Originweg funktionieren; nach Restore nicht angemeldeten Zugriff und Umgehung der Login-Grenze testen.

Anwendungsexport/Restore wurde erfolgreich in zweiter isolierter Instanz erprobt; DataProtection-Keys fehlen im Export und sind separat zu sichern. Kein Proxmox-/Offsite-/RPO-/RTO-Nachweis daraus ableiten. ADR bleibt **Vorgeschlagen**.

## WP01-Präzisierung — Dateiscope und Origin

Der [WP01-Lauf](../discovery/wp01-runtime-verification.md) reproduziert den Outsider-Dateizugriff auch nach Household-Rechteentzug und Restore, dazu Viewer-API-Upload und Temp-Schreiben per GET. Ausgewählte kodierte/normalisierte Pfadvarianten liefern ebenfalls die synthetischen Bytes. Preview/HEAD wurden getrennt bewertet. Ein enger lokaler Testproxy verweigert ausgewählte Wege, aber der Host kann den Origin absichtlich direkt erreichen; **Netzisolation und produktive Authentifizierung sind dadurch nicht bewiesen**.

Ein nativer Formrequest mit manuell injiziertem Ownercookie, fremdem Origin/Referer und ohne Antiforgery-Token erzeugte einen Beleg. Das bestätigt für diesen Request keine wirksame Serververweigerung, ist ohne Browser-/SameSite-/Accessprüfung kein vollständiger Browser-CSRF-Nachweis. B03/B06/B16 bleiben offen; nicht aus einer 403-Matrix allein Produktionssicherheit ableiten.
