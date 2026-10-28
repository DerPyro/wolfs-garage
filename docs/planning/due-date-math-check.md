# Offline-Rechenprüfung der Fälligkeitsbeispiele

Stand: 2026-10-27. Die Beispiele der [Fälligkeitsspezifikation](due-date-spec.md) sind ein Entwurf; dieser Lauf prüft ausschließlich ausgewählte Rechenschritte und ist **kein Test einer Anwendung oder eines produktiven Dienstes**.

Ausführung im Repository: `python3 tests/planning/due_date_math.py`. Benötigt werden Python 3 und verfügbare Zeitzonendaten für `Europe/Berlin`; es sind keine Dienste, Konten, Netzwerkzugriffe oder Schreiboperationen erforderlich. Die Prüfroutine liest die 27 nummerierten Tabellenzeilen und vergleicht ausgewählte extrahierte Zahlen und Daten sowie einige fest formulierte Zwischenerwartungen mittels Standardbibliothek, Kalenderarithmetik, exakten Brüchen und Dezimalzahlen. Das Vorhandensein aller 27 IDs wird geprüft; das ist keine vollständige fachliche Prüfung aller 27 Beispiele.

Ergebnis des Laufs: **34 Rechenvergleiche bestanden, keiner fehlgeschlagen**. Darunter sind drei zusätzliche Dezimal-/Rundungsbeispiele außerhalb der DV-Tabelle. Rechenanteile von 16 IDs wurden geprüft: DV-01, 02, 03, 06–10, 13, 16, 18, 21, 22, 24–26. Bei DV-03 wurde mangels explizitem Stichtag in der Zeile nur die Kilometerrelation geprüft; der behauptete zukünftige Datumszustand wurde nicht nachgewiesen. Bei DV-22 wird das auf dem Messdatum beruhende Beispiel erneut nachgerechnet; dies beweist kein Verhalten einer späteren Anwendung.

Für DV-04, 05, 11, 12, 14, 15, 17, 19, 20, 23 und 27 gibt es in diesem Lauf keine ausführbare Prüfung. Insbesondere belegt der Lauf weder kombinierte Fälligkeitszustände noch Quellenprüfung, Konfliktauflösung, Freigaben, Idempotenz, Transaktionen, Benachrichtigung, Providerverhalten, Zahlungsmodell oder rechtliche und herstellerspezifische Intervalle. Auch die zum Teil geprüften IDs sind nicht insgesamt bestanden. Diese Punkte benötigen später eigenständige Fach- und Integrationstests gegen die implementierte Lösung.

Geprüfte Dateistände (SHA-256):

- `docs/planning/due-date-spec.md`: `6991834f17986f8c795f4cbfb282e5922d7ea3e83c390d4cab641127c187309f`
- `tests/planning/due_date_math.py`: `cbc512eead7c23a04468ba8018c35a4eb338f70d3598e45e896058307e77f2ac`

Ein späterer Lauf kann wegen geänderter Spezifikation, Prüfroutine oder Zeitzonendaten abweichen; die Ausgabe nennt den aktuell geprüften Spezifikationshash und jede einzelne Vergleichsaussage.
