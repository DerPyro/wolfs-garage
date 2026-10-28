# ADR-0005 — Bestandsoberfläche zuerst, KI erst nach Freigabe

Status: **Vorgeschlagen** · Datum: 2026-10-26 · Entscheidung: offen

## Kontext

Web ist Hauptoberfläche, Telegram Ergänzung. REQ-023/024 verlangen Ampel und priorisierte Aufgaben. Spätere Diagnose muss Quellen, Unsicherheit, Datenfreigabe und sichere Änderungsabläufe respektieren. Die tatsächliche UI-Abdeckung wurde noch nicht mit einer Installation getestet.

## Empfehlung

v1.0 nutzt LubeLogger-UI. Ampel, Listenansicht und Fahrzeughistorie anhand konkreter fünf synthetischer Fahrzeuge prüfen. Erst bei dokumentierter Lücke eine schmale Garage-Ergänzung für Übersicht/Logbuch schaffen, keine vollständige parallele Fahrzeugverwaltung. Paperless bleibt Dokumentoberfläche; Garage verlinkt berechtigt.

v2.0 ergänzt KI als isolierten Adapter ohne direkte Schreibrechte auf Provider oder Datenbanken. Diagnosevorschläge, OBD-Screenshot-Extraktion und recherchierte Aussagen enthalten Provenienz und Unsicherheit. Herstellerintervalle nur mit nachvollziehbarer passender Quelle; Nutzerintervall ausdrücklich kennzeichnen. Kritische Einstufungen benötigen deterministische Fachregeln oder Nutzerbestätigung. Externe Texte/Dokumente sind untrusted und dürfen keine Tools/Änderungen autorisieren.

## Alternativen und Folgen

Eine neue Komplett-UI oder sofortige KI-Integration erhöht Aufwand ohne belegte Notwendigkeit. Wiederverwendung minimiert den MVP, setzt aber einen nachvollziehbaren UI-Abnahmetest voraus. Externe KI kann personenbezogene Historie verarbeiten; bis zur Datenschutzentscheidung keine Übermittlung.

## Offene Entscheidung und Nachweise

UI-Abdeckung, Barrierefreiheit/mobile Bedienbarkeit, KI-Anbieter, Region, Aufbewahrung, Kostenlimit und explizite Datenfreigabe festlegen. Lokales Modell als Alternative bewerten. Regressionen mit erfundenen Herstellerintervallen, Prompt Injection, kritischen Symptomen und fehlerhafter OCR prüfen, bevor v2.0 freigegeben wird.
