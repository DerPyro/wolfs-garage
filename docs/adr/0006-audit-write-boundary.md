# ADR-0006 — Vollständiges Audit über einen kontrollierten Schreibweg

Status: **Vorgeschlagen** · Datum: 2026-10-26 · Entscheidung: offen

> **Scope-Fortschreibung 2026-10-27:** Der Nutzer will ein Cloudflare-Login und für alle zugelassenen Webnutzer Adminrechte. Ein read-only-nativer Nutzer und ein Gateway zur Durchsetzung verschiedener Nutzerrechte sind damit keine Produktanforderung. Die bisherigen WP01-Messungen bleiben gültig. REQ-043/020 zur fachlichen Historie bleiben offen und werden anhand der tatsächlichen Anforderungen geprüft; ein lückenloses Vorher-/Nachher-Audit sämtlicher nativer Wege war eine ältere zusätzliche technische Interpretation. Aktuelle Produktvorgabe: [ADR-0008](0008-single-user-access.md).

## Kontext

REQ-043 fordert Änderungsprotokolle für Wartung/Logbuch, REQ-020 nachvollziehbare unveränderliche Problemhistorie. B01/B02 bestätigt native und API-Schreibwege, aber keinen vollständigen Auditvertrag mit Actor/Änderung/Ergebnis. Webhooks haben keine belastbare Event-ID oder vollständigen Vorher-/Nachherdaten. Die Anforderung wird nicht eigenmächtig auf „letzter Snapshot“ verkürzt.

## Empfehlung und harte Bedingung

Vor v1.0 einen isolierten Spike für read-only native Anzeige plus einzigen auditierten Wartungs-Schreibweg planen. Nur wenn serverseitige Fahrzeug-/Schreibrechte, alternative MVC-/GET-/Bulk-/Import-/Uploadwege und direkter Originzugriff zuverlässig abgegrenzt sind, kann Garage als Write-Gateway den fachlichen Auditpfad liefern. UI-Schaltflächen auszublenden oder bloß API-Keys einzuschränken genügt nicht für Cookie-basierte native Schreibwege. Native Benutzerrollen/Household-Rechte sind dafür erst zu validieren; sie werden nicht als nachgewiesene Lösung behauptet.

Audit mindestens: Actor und Kanal, Fahrzeug/Vorgang, Nutzlast-/Schema-Version, vorher/nachher soweit verfügbar, bestätigter Änderungswunsch, Zeitpunkt, externe Operation/Referenz und Status einschließlich unklarer Ergebnisse. Vor dem externen Write wird ein Intent dauerhaft gespeichert; nach Erfolg folgt ein eigenes Ergebnisereignis. Ein fehlendes Ergebnis wird reconciled, nicht als nie ausgeführter Write interpretiert. Die Datenbanktransaktion kann externe API-Schreibvorgänge nicht atomar mit einschließen.

Korrekturen erzeugen Ereignisse. Anwendungskonto erhält kein Update/Delete auf Auditereignisse; Administratoren können technisch trotzdem Speicher verändern. Das ist kein manipulationssicherer Rechtsnachweis. Ein Hash allein bietet ohne separat geschützten Anker keinen Schutz gegen einen privilegierten Angreifer; keine unnötige Blockchain-/Signaturinfrastruktur für dieses Projekt voraussetzen.

## Alternativen und Folgen

- Vollständiges Upstream-Audit: geringere eigene UI-Kopplung, aber Verfügbarkeit/Umfang unbewiesen.
- Nur Webhook/regelmäßiger Snapshot: kann Hinweise und Drift liefern, verliert Zwischenänderungen; erfüllt die hier angenommene vollständige Coverage nicht.
- Explizit kleinerer Auditumfang in v1.0: möglich nur nach Produktentscheidung.

Ein früher Garage-Schreibpfad verschiebt einen Teil von v1.1 nach v1.0; deshalb ist dies **ein Roadmap-Vorschlag**, keine bereits vorgenommene Scope-Änderung. LubeLogger darf im Wartungsfenster nur mit dokumentiertem Verfahren direkt beschrieben werden; ein solcher Bypass muss vor Freigabe als Ausnahme entschieden und anschließend abgeglichen werden. Er wird nicht still als vollständiges Audit gewertet.

## Nachweise und Entscheidung

Rollen/Route-Spike, UI-Funktionsumfang, Drift-/Bypassalarm, zwei konkurrierende Änderungen, Schreib-Timeout, Rechteentzug, Restore und administrative Notfalländerung anhand synthetischer Daten prüfen. Ergebnis kann eine Ablehnung des Gateways sein; dann Alternative wählen statt private LubeLogger-Routen als API zu nutzen. B03 bleibt bis dahin offen. Details: [Lieferplan](../planning/delivery-plan.md), [Threatmodell](../planning/security-threat-model.md).

## WP01-Nachtrag — 2026-10-27

**Die technische Hypothese einer allein über Household-View/Viewer-Key schreibfreien nativen Ansicht ist im geprüften v1.7.4 widerlegt.** [42 Laufzeitchecks](../discovery/wp01-runtime-verification.md) reproduzieren persistierende native und öffentliche Kilometer-GETs sowie Steuerfortschreibung mit View-Grundlage. Gewöhnliche Save-/Delete-/Bulkwege sind in den ausgewählten Fällen gesperrt, daraus folgt keine globale Schreibfreiheit. Native Fahrzeugneuanlage und allgemeine Datei-Uploads bleiben weitere erlaubte Wirkungspfade.

Die oben vorgeschlagene Variante wird deshalb **nicht als machbar abgenommen**. Ein vollständiger nativer UI-Schutzproxy ist nicht nachgewiesen und wäre eine eigene aufwendige, versionsgebundene Untersuchung. Eine sehr enge Positivliste aus zwei kontrollierten API-Leseoperationen hat 31 getestete Varianten vor Weiterleitung abgewehrt; sie enthält weder vollständige Oberfläche, Auditwriter noch Origin-Netzisolation.

Aktuelle Empfehlung: schmalen eigenen Garage-Zugang vor einer eventuellen Veröffentlichung konkretisieren, LubeLogger nur intern über nachgewiesene Operationen nutzen; native Administration separat begrenzen. Das kann eigene Anzeige-/Schreibfunktionen früher benötigen, und öffentliche Teile-/Recurrence-Lücken bleiben zu lösen. **Keine Scopeentscheidung des Nutzers wird angenommen**, der ADR bleibt vorgeschlagen und B03/B16 offen. Alternative Upstream-Lösung oder explizite Umfangsentscheidung siehe [WP01-Optionen](../discovery/wp01-runtime-verification.md).
