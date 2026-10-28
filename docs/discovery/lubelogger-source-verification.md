# LubeLogger B01 — unabhängige Quellverifikation

Stand/Abruf: 2026-10-26. Read-only-Prüfung offizieller Dokumentation und separat nach `/tmp/wolfs-b01-source` geklontem Release-Quellcode. Keine laufende Sandbox verändert. Voraussetzung: AGENTS.md, README, Anforderungen, Architektur, Roadmap und bisherige Discovery gelesen. Die nachfolgenden Setup-Routen dienen ausschließlich der Provisionierung einer lokalen synthetischen Erprobung; sie werden **nicht** zum Produktions-Integrationsvertrag erklärt.

## Identität und Lizenz

- Zielstand bestätigt: `v1.7.4`, Commit `63fa5cd267497ba01c29f4888c65efbbdd4b94bf`; die offizielle Release-Seite bezeichnet ihn beim Abruf als Latest und nennt den 14.10.2026. Das Release hebt unter anderem eine Korrektur der API-Key-Rechte beim Anlegen von Fahrzeugen hervor. [Release](https://github.com/hargata/lubelog/releases/tag/v1.7.4).
- `LICENSE`: MIT, Copyright Hargata Softworks 2024. SHA256 der unveränderten Datei: `5745d164b9897a203a75e43b51a25c84eec6d0d16982947a0067e3e020e4caef`. Hinweise bei Weitergabe erhalten; MIT des Anwendungsrepos ist keine pauschale Lizenzbestätigung sämtlicher Containerbestandteile. [Gepinnte Lizenz](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/LICENSE).
- Releaseprojekt zielt auf `net10.0`. Direkte NuGet-Referenzen: CsvHelper 33.1.0, LiteDB 5.0.17, MailKit 4.18.1, Microsoft.IdentityModel.JsonWebTokens 8.23.0 und Npgsql 9.0.5. Das ist ein Quell-Inventar, **kein** vollständiges transitive/runtime SBOM und keine Lizenzfreigabe aller Pakete. [Projektdatei](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/CarCareTracker.csproj).
- `wwwroot/defaults/api.json` ist die vom `/api`-View gelesene maschinenlesbare Dokumentationsquelle. SHA256: `118df316583d3d173d48229c18e79b8264a967537682f906c62ab317696c6082`. Kein zugesagtes OpenAPI-Schema: das Format ist die eigene LubeLogger-Dokumentationsstruktur. [API-Dokumentationsdaten](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/wwwroot/defaults/api.json), [View-Ladevorgang](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/APIController.cs).

Der Container-Digest muss separat anhand der Registry ermittelt werden; Release-SHA und Datei-Hashes ersetzen ihn nicht. Diese Datei behauptet keinen Laufzeitnachweis.

## B01 — vorläufiges Lizenzmanifest direkter NuGet-Pakete

Abruf: 2026-10-26. Die fünf direkten Referenzen der gepinnten Projektdatei wurden gegen die jeweiligen offiziellen NuGet-`.nuspec`-Metadaten geprüft. Hashes beziehen sich auf die unverändert heruntergeladenen Metadatendateien. Paketinhalt wurde nicht ausgeführt. Die Angaben sind Inventarevidenz, keine pauschale Distributionsfreigabe.

| Direktes Paket | Version | Lizenzangabe im NuGet-Paket | Primäre Metadaten / SHA256 |
| --- | --- | --- | --- |
| CsvHelper | 33.1.0 | SPDX-Ausdruck `MS-PL OR Apache-2.0`; Lizenzwahl bei Weitergabe festhalten | [Nuspec](https://api.nuget.org/v3-flatcontainer/csvhelper/33.1.0/csvhelper.nuspec), `962a4ad52857ef1d7ca8f50bf1fb3168097153758870aaae60cf60b04a816ef2` |
| LiteDB | 5.0.17 | Dateilizenz `LICENSE`, Inhalt MIT; Copyright Mauricio David 2014–2022 | [Nuspec](https://api.nuget.org/v3-flatcontainer/litedb/5.0.17/litedb.nuspec), `c5507d740683b1e7416bb40edfd8ef6647865dafed4df53d782ac094fa4ac133` |
| MailKit | 4.18.1 | SPDX-Ausdruck `MIT` | [Nuspec](https://api.nuget.org/v3-flatcontainer/mailkit/4.18.1/mailkit.nuspec), `8f592284bd2b3e4eb8d118074839aea9c64fa901ac879b36f4c434be5872cb55` |
| Microsoft.IdentityModel.JsonWebTokens | 8.23.0 | SPDX-Ausdruck `MIT` | [Nuspec](https://api.nuget.org/v3-flatcontainer/microsoft.identitymodel.jsonwebtokens/8.23.0/microsoft.identitymodel.jsonwebtokens.nuspec), `2e80c6e4aa256492bf8dc70e7bcbd7d6b6bf31a62efd2cae34ca6e20166c74d4` |
| Npgsql | 9.0.5 | SPDX-Ausdruck `PostgreSQL` | [Nuspec](https://api.nuget.org/v3-flatcontainer/npgsql/9.0.5/npgsql.nuspec), `8d4d0c391d75952331182c6d8ce173534d85922e98078495c26bf1dd55f2e55d` |

Für LiteDB wurde zusätzlich die Datei `LICENSE` aus dem [offiziellen NuGet-Paket 5.0.17](https://api.nuget.org/v3-flatcontainer/litedb/5.0.17/litedb.5.0.17.nupkg) gelesen; SHA256 der Lizenzdatei: `0f077c548c9f6f6181d59a6dc1ddca08f35968a9b38b7f45932932b0cb082081`. Die `licenseUrl` dieser Version ist nur ein veralteter generischer NuGet-Hinweis und deshalb kein Ersatz für die mitgelieferte Datei.

### Getrennt noch zu inventarisieren

- **Transitive NuGet-Abhängigkeiten:** genaue für das Ziel-Framework und tatsächliche Publish-Artefakt aufgelöste Versionen samt Lizenz-/Notice-Dateien. Die Tabelle oben enthält ausschließlich direkte `PackageReference`-Einträge; z. B. aus Paketmetadaten abgeleitete Mindestversionen sind keine verifizierten ausgelieferten Versionen.
- **.NET-/ASP.NET-Runtime und native Bibliotheken:** tatsächlich im Image enthaltene Runtime-Version, native Abhängigkeiten und zugehörige Third-Party-Notices getrennt vom Anwendungslizenztext erfassen. `net10.0` allein identifiziert keine konkrete Runtime-Buildversion.
- **Betriebssystem-/Basisimage-Pakete:** distributionseigene Paketdatenbank und Lizenztexte anhand des gewählten Plattform-Image-Digests erfassen. Das LubeLogger-Repo-MIT gilt nicht automatisch für diese Bestandteile.
- **Ausgelieferte Frontend-Assets:** JavaScript-/CSS-/Schrift-/Bildbestandteile, gebündelte Versionen und Notices separat prüfen; sie sind nicht vollständig durch NuGet abgedeckt.

Vor eigener Weitergabe eines Images vollständige artefaktbezogene SBOM/Notices und Lizenzwahl für alternativ lizenzierte Bestandteile erstellen. Dieses vorbereitete Manifest schließt weder transitive noch Runtime-/OS-/Frontend-Lizenzprüfung ab und verändert keine laufende Instanz.

## Nachvollziehbare lokale Provisionierung

Alle folgenden Requests ausschließlich gegen den isolierten lokalen Origin einer neu angelegten Testinstanz. Zufällige Testpasswörter, Cookies, Einladungs- und API-Schlüssel nur außerhalb des Repositorys speichern; keine Werte in Testprotokolle übernehmen. Keine Provider-/SMTP-Konfiguration erforderlich.

| Schritt | Belegte Route / Bindung | Prüfpunkt |
| --- | --- | --- |
| Root aktivieren | `POST /Login/CreateLoginCreds`, Form `UserName`, `Password` | Initial setzt Auth-Middleware bei deaktivierter Auth einen Root-Principal mit ID −1; danach muss anonymes `/api/vehicles` scheitern. |
| Root anmelden | `POST /Login/Login`, Form `UserName`, `Password`, optional `IsPersistent=false` | `success` prüfen und ausgegebenes Login-Cookie für Setup behalten. |
| Einladung ohne E-Mail | Root-Cookie, `POST /Admin/GenerateNewToken`, Form `emailAddress`, `autoNotify=false` | Erfolg erzeugt Token; Antwort enthält ihn nicht direkt. |
| Einladung lesen | Root-Cookie, `GET /Admin/GetTokenPartialView` | HTML enthält Tokens für Admin-Verwaltung; nur im privaten Setup-Prozess parsen. |
| Nicht-Root registrieren | `POST /Login/Register`, Form `UserName`, `Password`, `EmailAddress`, `Token` | Token und case-sensitive E-Mail müssen zusammenpassen; Token wird bei Registrierung verbraucht. |
| Nicht-Root anmelden | `POST /Login/Login` mit dessen Zugangsdaten | Eigene Session verwenden, nicht Root-Cookie weiterverwenden. |
| Schlüssel erzeugen | Nutzer-Cookie, `POST /Home/CreateAPIKeyForUser`, Form `keyName`, wiederholbare `permissions` | `additionalData.apiKey` ist der einmal ausgegebene Klartextschlüssel; lokal geheim halten. |
| Rollen gemäß UI | Viewer: keine Permissions-Einträge; Editor: `Edit`; Manager: `Edit`, `Delete` | Enum enthält auch `View=0`, die UI sendet jedoch für Viewer eine leere Liste. |

Diese MVC-Aktionen nutzen Form-Modelbinding, kein `[FromBody]`-JSON. Die Standardroute ist `{controller=Home}/{action=Index}/{id?}`. Nach Setup sind Test-APIs mit `x-api-key` getrennt von Cookie-/Basic-Sessions zu prüfen: Die Auth-Middleware bevorzugt vorhandenes Basic-Header, dann Cookie, dann API-Key. Ein gleichzeitig vorhandenes Root-Cookie würde den API-Key-Rechtetest verfälschen.

Quellen: [Logincontroller](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/LoginController.cs), [Loginlogik](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Logic/LoginLogic.cs), [Admincontroller](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/AdminController.cs), [Homecontroller](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/HomeController.cs), [Userlogik](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Logic/UserLogic.cs), [Frontend-Rollenzuordnung](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/wwwroot/js/garage.js), [Auth-Middleware](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Middleware/Authen.cs), [Routing](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Program.cs). Offizielle Bedienanleitung: [Authentication](https://docs.lubelogger.com/Installation/Authentication/).

## DTO- und Fehlerdetails für B02

- Fahrzeuganlage erwartet `VehicleImportModel`: mindestens `Year`, `Make`, `Model`, `Identifier`, `FuelType`. Bei `Identifier=LicensePlate` ist zusätzlich `LicensePlate` nötig. Gültige FuelTypes sind `Gasoline`, `Diesel`, `Electric`; `Year` wird als Integer geparst. Optionale Felder: `UseEngineHours`, `OdometerOptional`, `Tags`, `ExtraFields`. Die Antwort liefert `additionalData.vehicleId`.
- Kilometeranlage nutzt `OdometerRecordExportModel` mit Datum/Stand, optional Startstand und Notizen/Tags; Wartung/Reparatur nutzen `GenericRecordExportModel` mit `Date`, `Odometer`, `Description`, `Cost`, optional `Notes`, `ExtraFields`, `Files`, `Tags`. Recordanlagen liefern `additionalData.recordId`.
- JSON-Eingabekonverter akzeptieren typisierte Zahlen/Datumswerte; die Controller parsen anschließend Stringwerte über Locale. Daher Fixture-Roundtrips bei `de_DE` und invariantem Ausgabeheader nachweisen, keine stabile Locale allein aus JSON-Eingabe ableiten.
- `ReminderExportModel` besitzt keine `IsRecurring`, `FixedIntervals` oder Wiederholungsintervall-Felder. Das GET-Modell `ReminderAPIExportModel` ergänzt `UserMetric`, `DueDays`, `DueDistance`, aber ebenfalls keine Wiederholungsregeln.
- Reminder-Update lädt den bestehenden Datensatz und ändert nur Datum, Kilometergrenze, Beschreibung, Metric, Notizen und Tags. Statisch bleiben vorhandene Wiederholungsfelder dadurch erhalten; das ist **keine** Fähigkeit, sie über die API anzulegen/zu ändern/auszulesen. Laufzeitprüfung bleibt erforderlich.
- Reminder `Metric=Both` ohne gültiges Datum oder Kilometergrenze liefert `success=false` mit HTTP 200. Auch ein wegen fremder Fahrzeugrechte abgewiesener POST/add kann durch `CollaboratorFilter(jsonResponse=true)` HTTP 200 plus `success=false` liefern. HTTP-Status allein ist deshalb kein Erfolgskriterium.
- Fehlender API-Schlüssel bei aktiver Auth führt auf API-Routen zu 401; fehlende Edit-/Delete-Permission im `APIKeyFilter` liefert 403. Objektzugriff und Schlüsselrolle müssen separat geprüft werden.
- Keine belegte Idempotency-Key-Verarbeitung: verlorene externe Schreibantwort darf nicht blind mit einem zweiten POST beantwortet werden. Ein Test sollte den bereits gespeicherten Datensatz nach verlorenem Antwortkanal abgleichen.

Quellen: [Import-/Exportmodelle](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/Shared/ImportModel.cs), [Fahrzeugcontroller](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/APIController.cs), [Remindercontroller](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/API/ReminderController.cs), [API-Key-Filter](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Filter/APIKeyFilter.cs), [Objektfilter](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Filter/CollaboratorFilter.cs), [OperationResponse](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/Shared/OperationResponse.cs), [API-Dokumentation](https://docs.lubelogger.com/Advanced/API/).

## Ergebnis und offene Evidenz

Die bisherige statische Discovery wird bestätigt und um präzise lokale Setup-/Fehlerverträge ergänzt. Diese Verifikation macht B01/B02 nicht allein fertig: Image-Digest, tatsächlich ausgeliefertes API-Dokument, echte Rechte-/Locale-/Datumsroundtrips, Reminderverhalten, Kosten/Teileverwendung, unklare Schreibantworten und isolierter Restore benötigen gesonderte Laufzeitprotokolle. Vollständiger Audit-Nachweis direkter UI-Änderungen bleibt ein gesonderter Blocker B03.

Die nachfolgende [Laufzeitprüfung](lubelogger-runtime-verification.md) und [Testbaseline](../../tests/lubelogger/target.lock.json) ergänzen diesen rein statischen Bericht um Digest, API-Bytevergleich und tatsächliche Ergebnisse.
