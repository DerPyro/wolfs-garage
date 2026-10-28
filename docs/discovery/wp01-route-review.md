# WP01 — unabhängiges statisches Routen-/Rechteinventar

Stand: 2026-10-27. Ziel ausschließlich LubeLogger `v1.7.4`, Commit `63fa5cd267497ba01c29f4888c65efbbdd4b94bf`, separat vorliegend unter `/tmp/wolfs-b01-source`. Read-only-Quellprüfung, **keine** Änderung einer laufenden Sandbox und kein neuer Exploitnachweis. Gelesene Grundlagen: AGENTS, README, Anforderungen, Architektur, Roadmap, [ADR-0006](../adr/0006-audit-write-boundary.md) und [Threatmodell](../planning/security-threat-model.md).

## Vorgehen, Rohinventar und Grenzen

Zuerst alle öffentlich deklarierten MVC-Actionmethoden der Form `IActionResult`/`Task<IActionResult>` unter `Controllers/` erfassen, dann relevante Schreib-/Bulk-/Import-/Datei-/GET-Seiteneffekte und Rechteprüfungen manuell verfolgen. Das [maschinenlesbare Inventar](../../tests/wp01/route-inventory.json) enthält **329 Deklarationen aus 35 Controllerdateien**, davon 104 mit Attributrouten, 225 konventionelle Routenkandidaten und 47 ohne `Http*`-Verbconstraint. Eine HTTP-Route kann wegen JSON-/Form-Overloads mehrere Deklarationen besitzen. Die Zahlen sind kein Maß für unabhängig erreichbare Endpunkte.

Pro Eintrag: ursprüngliche Signatur, Datei/Zeile/Quelllink, Klassen- und Methodenattribute, deklarierte Verben, Attributtemplates oder konventionell abgeleiteter Kandidat, direkte Permission-Tokens, sichtbare Inlineprüfungen und lexikalische Mutationshinweise. Einzelne Effekte sind manuell überlagert als `reviewed_effect`; alle Einträge behalten `runtime_verified=false`, unabhängig von separat laufenden Tests anderer Agents. Hashes der 35 Quelldateien binden das Rohinventar an den geprüften Stand.

Statisches Parsing ist kein kompilierter `EndpointDataSource`-Export. Routing-Overloads, HEAD-Semantik, Normalisierung, unbekannte Middlewarepfade, SignalR `/api/ws`, öffentliche Assets sowie indirekte private Helper-Aufrufgraphen sind damit nicht vollständig abgedeckt. Mutationsnamen sind nur Hinweise; ein Treffer kann ein Read sein, ein fehlender Treffer beweist keine Writefreiheit. **Dieses JSON ist keine deploybare Positivallowlist.** Die Runtime muss tatsächliche Pfade/Verben/Seiteneffekte nachweisen, bevor ein kontrolliertes Gateway entschieden wird.

Routinggrundlage ist [Program.cs](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Program.cs#L154): statische Dateien, MVC-Default `{controller=Home}/{action=Index}/{id?}` sowie SignalR. Konventionelle Pfade leiten sich bei nicht attributgerouteten Aktionen hieraus ab. Eine attributgeroutete Aktion wie `GetStaticFile` wird nicht zusätzlich als konventioneller Alias behauptet; `/Files/GetStaticFile` bleibt ausschließlich negativer Testkandidat.

## Household View richtig provisionieren und messen

1. Nicht-Root-Parent als direkten Collaborator der synthetischen Zielfahrzeuge verwenden. Ein Parent `-1` wird von `AddUserToHousehold` ausdrücklich abgelehnt.
2. Child normal registrieren; **keine direkte Fahrzeugkollaboration** für den Child anlegen. Sonst überschreibt diese die Household-Einschränkung.
3. Root-/Admin-Cookie: `POST /Admin/AddUserToHousehold`, Form `parentUserId=<Parent-ID>`, `username=<Child-Name>`.
4. Neue Household-Permissions sind initial leer. Bei Bedarf mit Root/Admin `POST /Admin/ModifyUserHouseholdPermissions`, `parentUserId`, `childUserId` und leerer Permissions-Liste setzen. `View` ist implizit; keine `Edit`/`Delete`-Einträge hinzufügen.
5. Child mit separatem Cookieclient anmelden, keine Parent-/Root-Cookies und keine Basic-Header mitschicken. View-Lesen und tatsächliche Unterbindung jeder Schreibfamilie separat prüfen, Rechteentzug mit alter Session erneut testen.

Die Bezeichnung „RootAdminAddHousehold“ ist keine Aktion des Releasecodes. Die oben genannten Pfade sind aus belegten Adminaktionen plus Default-Routing abgeleitet. [AdminController](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/AdminController.cs#L101), [UserHousehold-Modell](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Models/User/UserHousehold.cs), [UserLogic](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Logic/UserLogic.cs#L145).

Priorität der Rechte:

- `UserCanEditVehicle` fragt zuerst `UserCanDirectlyEditVehicle`: Root-ID `−1` oder direkter Collaborator erhalten unabhängig von Household-ReadOnly alle angefragten Rechte.
- Erst danach werden direkte Household-Parent-Verknüpfungen mit Fahrzeugzugriff ausgewertet. View ist stets erlaubt; Edit/Delete nur mit entsprechendem Eintrag. Rechte mehrerer Parents können sich ergänzen. Das ist keine rekursive Übernahme beliebig tiefer Haushaltsketten.
- `IsAdmin` allein bewirkt in diesen Fahrzeugprüfungen keine Rootfreigabe; Adminaktionen besitzen aber eigene administrative Macht. Tests müssen Admin und direkten Collaborator auseinanderhalten.
- Fahrzeuglöschung und Collaboratorverwaltung verwenden teils `StrictCollaboratorFilter`, also direkten Zugriff statt bloßem Household-Delete/Edit.
- API-Key-Rolle begrenzt nur Aktionen, die den entsprechenden `APIKeyFilter` tatsächlich anwenden. API-Key-Viewer und Household-View sind getrennte Sicherheitsmechanismen; keiner ist pauschal ein globaler Write-Schalter.
- Auth-Priorität im Handler ist Basic-Header, dann Cookie, dann API-Key. Gemischte Credentials verfälschen Rollenprüfungen.

Quellen: [UserLogic](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Logic/UserLogic.cs#L145), [CollaboratorFilter](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Filter/CollaboratorFilter.cs), [StrictCollaboratorFilter](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Filter/StrictCollaboratorFilter.cs), [APIKeyFilter](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Filter/APIKeyFilter.cs), [Authen](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Middleware/Authen.cs).

## Priorisierte statische Seiteneffektkandidaten

Die folgenden Pfade sind aus Source verifiziert oder konventionell hergeleitet. „Ohne Verbconstraint“ bedeutet fehlende Methodenbeschränkung im Actionattribut, keine Behauptung, dass jedes denkbare Verb bereits erfolgreich getestet wurde.

| Pfad | Deklariertes Verb / Schutz | Statischer Effekt und WP01-Folge |
| --- | --- | --- |
| `/Vehicle/GetOdometerRecordsByVehicleId` | GET, CollaboratorFilter default **View** | Wenn alle Startstände null sind, ruft der Read `AutoConvertOdometerRecord` auf; der Helper speichert jeden Datensatz. View-GET mit mutierendem Altbestand priorisiert testen. |
| `/api/vehicle/odometerrecords` | GET, CollaboratorFilter default **View**, kein Edit-/APIKey-Rollenfilter | Dieselbe bedingte persistierende `AutoConvertOdometerRecord`-Konvertierung wie im nativen GET, noch vor ID-/Datums-/Tagfilterung. Aus NarrowReadGate ausschließen; nicht als unabhängigen Vorher-/Nachher-Beobachter verwenden. |
| `/api/vehicle/odometerrecords/all` | GET, Nutzerfahrzeuge serverseitig gefiltert | Liest/serialisiert Records ohne Aufruf der AutoConvert-Konvertierung. Im WP01-Harness geeigneter separater Beobachtungskandidat; Ergebnisse zusätzlich nach synthetischem Zielfahrzeug filtern. Kein hier behaupteter Runtime-Nachweis. |
| `/Vehicle/CheckRecurringTaxRecords` | POST, CollaboratorFilter default **View** | `UpdateRecurringTaxes` setzt alte Wiederholung aus und legt Folgebelege an. Keine zusätzliche Editprüfung im Helper gefunden. View-only-POST kann fachlichen Zustand ändern; Runtime-Beleg nötig. |
| `/Vehicle/GetVehicleHaveUrgentOrPastDueReminders` | GET, View-Filter, Helper prüft **Edit** plus Userflag | Automatisches Fortschreiben überfälliger Wiederholungen. Für echten Household-View ist Editkontrolle vorhanden; Owner/Direktcollaborator kann bei Read mutieren. |
| `/Vehicle/MoveRecord`, `/Vehicle/MoveRecords` | Ohne Verbconstraint, Inline **Edit** | Quelle in Service/Repair/Upgrade lesen, Ziel speichern, Quelle löschen; GET darf nicht ungeprüft als Read freigegeben werden. |
| `/Vehicle/DeleteRecords` | Ohne Verbconstraint, typisierte Delete-Helper | Bulk-Dispatcher für Service/Repair/Upgrade/Gas/Tax/Supply/Note/Odometer/Reminder/Inspection/Equipment. Helfer prüfen Delete; Test mit Owner-GET und Child-View separat. |
| `/Vehicle/GenerateCsvSample` | GET, Klassen-Authorize | Erzeugt temporäres CSV; kein fachlicher Fahrzeugwrite, aber Dateiseiteneffekt. |
| `/Vehicle/ExportFromVehicleToCsv` | POST, **View** | Export schreibt temporäres CSV; POST allein ist daher kein zuverlässiges Domain-Write-Merkmal. |
| `/Files/UploadCoordinates` | Ohne Verbconstraint, Klassen-Authorize | Schreibt temporäre CSV-Datei ohne Fahrzeugprüfung. |
| `/Files/HandleFileUpload`, `/Files/HandleMultipleFileUpload` | POST, Klassen-Authorize | Temporärer Upload ohne fahrzeugbezogene Permission. |
| `/api/documents/upload` | POST, Klassen-Authorize; **kein APIKeyFilter** | Schreibt direkt `documents/`, keine Fahrzeug-ID. Viewer-Key darf nicht ohne Test als Upload-sicher gelten. |
| `/documents/{fileName}`, `/temp/{fileName}`, `/images/{fileName}`, `/translations/{fileName}` | Attributrouten ohne Http-Verbconstraint, Klassen-Authorize | `GetStaticFile` löst Datei anhand Request.Path ohne Fahrzeugrecht auf. Byteschutz durch separate Runtimefälle belegen. |
| `/Files/PreviewFile` | Ohne Verbconstraint, Klassen-Authorize | Rendert Attachment-HTML; HTTP 200 allein beweist keinen Dokumentbytezugriff. |
| `/Files/MakeBackup`, `/api/makebackup` | GET, Root | Backup-/ZIP-Dateieffekt und sensible Exporte, keine normalen Reads. |
| `/api/cleanup`, `/api/demo/restore` | GET, Root | Dateilöschung bzw. Demo-Restore. Keine echten Daten für Tests verwenden. |
| `/api/vehicle/reminders/send` | GET, Root | Externer Versand; in Isolation keine echten SMTP-/Providerziele konfigurieren. |
| `/Home/UpdateExtraFields` | Ohne Verbconstraint, Root | Persistiert Zusatzfelddefinitionen. |
| `/Admin/GenerateNewToken` | Ohne Verbconstraint, Admin | Erstellt Einladung; `autoNotify` kann E-Mail auslösen. |
| `/Migration/Export`, `/Migration/Import` | Ohne Verbconstraint, Root | Export initialisiert PostgreSQL-Tabellen und Dateien; Import schreibt DB. Nicht als UI-Read/Maintenance-Bypass erlauben. |

Belege: [OdometerController](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/Vehicle/OdometerController.cs#L22), [OdometerLogic](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Logic/OdometerLogic.cs#L54), [TaxController](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/Vehicle/TaxController.cs#L27), [VehicleLogic](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Logic/VehicleLogic.cs#L416), [ReminderController](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/Vehicle/ReminderController.cs#L17), [VehicleController](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/VehicleController.cs#L705), [ImportController](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/Vehicle/ImportController.cs), [FilesController](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/FilesController.cs), [APIController](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/APIController.cs), [MigrationController](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/MigrationController.cs).

### Unabhängige Beobachtung der Kilometer-GETs

Die zusätzliche Quellprüfung von [API/OdometerController.cs](https://github.com/hargata/lubelog/blob/63fa5cd267497ba01c29f4888c65efbbdd4b94bf/Controllers/API/OdometerController.cs#L83) bestätigt zwei getrennte Read-Einstiege in denselben persistierenden Helper: nativer `/Vehicle/GetOdometerRecordsByVehicleId` und öffentlicher `/api/vehicle/odometerrecords`. Ein vorheriger Kontrollabruf über die per-vehicle API kann den mutierbaren Altzustand bereits reparieren und den anschließenden nativen GET falsch negativ erscheinen lassen. Deshalb Vorher-/Nachherstände separat über `/api/vehicle/odometerrecords/all` beobachten; diese Action enthält keinen AutoConvert-Aufruf. Für jeden mutierenden GET eine eigene Fixture mit null Startständen verwenden, sonst konsumiert der erste Test die Bedingung des zweiten.

Der geplante enge Read-Gate darf den per-vehicle Kilometer-API-GET nicht als harmlosen Read zulassen. `/all` wird hier nur als quellengeprüfter Observer-Kandidat eingeordnet; gesamte Reachability, Rechte, Response und Zustandsstabilität bleiben praktisch zu prüfen. Keine pauschale Freigabe anderer GETs wird daraus abgeleitet.

## Weitere Schreibfamilien im Inventar

- Fahrzeug `SaveVehicle`, `DeleteVehicle(s)` und Collaboratorverwaltung; vorhandenes Fahrzeug benötigt Edit, Neuanlage gibt dem Ersteller direkten Zugriff. Auch ein Child kann dadurch eigene direkt editierbare Fahrzeuge erzeugen, soweit native Neuanlage erreichbar bleibt. Das ist getrennt von Verbot, Parent-Fahrzeuge zu ändern, zu bewerten.
- Service/Repair/Upgrade-Save kann neben Hauptbeleg auch Teilebestand/Verwendung, Rückgabe früherer Teile, Dateien aus Temp, Reminderfortschreibung und automatisch Kilometerbelege ändern. Ein einzelner Request kann somit mehrere Aggregatänderungen auslösen.
- Odometer/Gas Bulk-Edit, `AdjustRecordsOdometer`, `DuplicateRecords`, `DuplicateRecordsToOtherVehicles`, `DuplicateDistanceToOtherVehicles`, `BulkCreateOdometerRecords`, `EditMultipleRecords`: nicht nur Einzel-Save/Delete prüfen; jedes Quell-/Zielfahrzeug und jede Record-ID muss autorisiert bleiben.
- `ImportToVehicleIdFromCsv` ist POST mit Edit-Filter, importiert mehrere Belegtypen. Import/Attachments/Dateireferenzen bleiben alternative Schreib- und Datenzugangswege.
- Planner und Templates: Save, Delete, Template↔Plan-Konvertierung, Fortschrittsänderung können Belege/Teile beeinflussen. `OrderPlanSupplies` ist trotz Name nur View-Modal mit Verfügbarkeitsabfrage, keine ausgeführte Bestellung.
- Inspection-/Equipment-/Note-/Tax-/Supply-Saves und deren Deletes sowie automatische Rekurrenz benötigen dieselbe Abgrenzung. Supply-Requisition prüft bei fahrzeuggebundenen Teilen Edit; `vehicleId=0` (Shop Supplies) ist eigener Sonderfall und muss bei aktiviertem Feature separat abgenommen werden.
- API-Dateien unter `Controllers/API/` sowie Fahrzeug-API in `APIController.cs` besitzen eigene JSON-/Form-Overloads und Permissionfilter. Das native MVC-Rechtetestresultat darf nicht pauschal auf API- oder Dateiaktionen übertragen werden.

Ein vollständiger Auditpfad kann nicht allein aus Statuscodes oder einem zentralen Webhook nachgewiesen werden. Auch Updates mit unveränderten Nutzdaten, halb erfolgreiche Bulkoperationen, Teile-/Reminder-Nebeneffekte und Konkurrenz brauchen geeignete Vorher-/Nachherbelege.

## CSRF und Gateway-Folgerung

Read-only-Suche in Release-`Program.cs`, `Controllers/`, `Filter/`, `Middleware/` und Razor-Views fand keine expliziten `ValidateAntiForgeryToken`, `AutoValidateAntiforgeryToken`, `AddAntiforgery` oder Origin-/Referer-Validierung für diese Aktionen. `Program.cs` verwendet `AddControllersWithViews`; kein globaler Antiforgery-Filter ist dort eingerichtet. Beim Login werden CookieOptions mit Expires gesetzt; Secure/HttpOnly/SameSite werden in diesem Aufruf nicht explizit festgelegt. Daraus folgt **kein vollständiger Browser-CSRF-Nachweis**: Plattformdefaults, Browser, tatsächlicher Origin/Scheme und SameSite-Navigation sind praktisch zu messen.

WP01 muss mindestens Owner-Cookie-POST ohne Token, fremden Origin, Cross-site simple Form, GET-Navigation auf mutierende Action und gesonderte Credential-Priorität testen. Ein Requests-Test mit `Origin:` misst Servervalidierung, simuliert jedoch nicht automatisch die Browserentscheidung zur Cookieübertragung. CORS begrenzt Browserantwortzugriff, beweist keine Unterbindung einfacher Form-/GET-Schreibvorgänge.

Eine reine Verbregel „GET frei, POST gesperrt“ kann weder ReadOnly noch Audit gewährleisten. Household-View ist ein brauchbarer Testansatz, nach den statischen View-Seiteneffekten aber **keine bereits bestätigte globale Schreibsperre**. Eine spätere Positivallowlist muss Aktionen/Verben/Normalisierung, Uploads/Export/Restore und direkte Originwege ausdrücklich berücksichtigen. Dieses Inventar entscheidet ADR-0006 nicht, es benennt dessen harte Nachweise und mögliche Ablehnungsgründe.

## Durchgeführte Offlinevalidierung

JSON parsebar; Anzahl extrahierter Deklarationen gegen unabhängigen deklarationsbasierten Zähler abgeglichen; Quellzeilen und alle 35 Datei-Hashes vorhanden. Keine produktiven Dienste, Netzregeln oder Runtimezustände verändert. Laufzeitresultate bleiben im separaten WP01-Bericht und werden nicht aus Quellkandidaten abgeleitet.
