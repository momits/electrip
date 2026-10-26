# AGENTS.md – Regeln für Agenten in diesem Repo

Electrip 2 ist die Neuentwicklung von Electrip (Modellbahnsteuerung mit Gamepads) in Rust. Der Code wird von KI-Agenten geschrieben; Mo (Moritz Renftle) gibt Spezifikation, Architektur und Hardware-Abnahme frei.

## Zuerst lesen

1. `PROGRESS.md` – was zuletzt passiert ist und was als Nächstes ansteht
2. `git log --oneline -20`
3. `spec/requirements.json` – Paritätskatalog; nur hier steht, was gebaut wird
4. `spec/decisions/` – verbindliche Architekturentscheidungen
5. Bei Bedarf: `spec/konzept.md` (Gesamtkonzept), `spec/benutzerhandbuch.pdf` (Handbuch Electrip 1), `legacy/` (Code Electrip 1)

## Ablauf einer Sitzung

1. Stand lesen (siehe oben). Ab Phase 0 Schritt 3: `cargo xtask parity` und `cargo xtask test`.
2. Ist etwas rot, das zuerst reparieren – vor jeder neuen Arbeit.
3. **Eine** offene Aufgabe wählen (niedrigste Phase zuerst) und beanspruchen: Datei `current_tasks/<ID>.md` mit Datum und Kurzplan anlegen, committen, pushen. Existiert die Datei schon, andere Aufgabe wählen.
4. Umsetzen. Prüffälle aus `verification` der Anforderung schreiben bzw. grün machen. Wo möglich die App über den Steuerkanal selbst bedienen.
5. Abschluss: Status in `spec/requirements.json` setzen, Eintrag in `PROGRESS.md` ergänzen, `current_tasks/<ID>.md` löschen, committen, pushen.
6. Wenn die Sitzung vorher endet (Limit, Kontext voll): Zwischenstand committen und in `PROGRESS.md` beschreiben, was fehlt.

## Spezifikation

- `spec/requirements.json`: Agenten ändern **nur** die Felder unter `status`. Anforderungen, Akzeptanzkriterien und Prüfarten ändert nur Mo.
- `status.wired` = Funktion existiert und ist angebunden. `status.verified` = alle automatischen Prüffälle grün. `status.accepted` setzt **nur Mo**.
- Widerspruch oder Lücke zwischen Handbuch, Alt-Code und Anforderung: nicht selbst entscheiden, sondern als Frage in `spec/questions.md` eintragen und mit einer anderen Aufgabe weitermachen. Vorrang bei klaren Fällen: neue Anforderung vor Alt-Code vor Handbuch.
- Neue Architekturentscheidungen nur als ADR-Entwurf (`spec/decisions/NNNN-titel.md`, Status „Vorschlag“); Mo setzt auf „Angenommen“.

## Architekturregeln

- **Befehl zuerst.** Jede Nutzeraktion ist ein Befehl im Kern (`core`). Gamepad, UI, Steuerkanal und Tests rufen nur Befehle auf. Keine Fachlogik in `ui`.
- **Schichten:** `core` hängt von keinem anderen Crate des Workspace ab. Treiber (`station-*`), `input`, `audio`, `library`, `sync` hängen nur von `core` ab. `ui` und `control` dürfen alles nutzen. Die Regel wird per `cargo xtask` geprüft.
- **Zentralen** nur über den Trait `CommandStation`. **Audio** nur über den Trait `AudioSink`.
- **Bibliotheken statt Eigenbau:** Automerge (Sync), SDL3 (Gamepads), rodio/symphonia (Audio), Slint (UI). Neue Abhängigkeiten nur mit Begründung in der Commit-Nachricht; keine Abhängigkeit für ein paar Zeilen Code.

## Code-Regeln

- Rust stable, `cargo fmt`, `cargo clippy -- -D warnings`.
- Kein `panic!`, `unwrap()`, `expect()` außerhalb von Tests; Fehler als `Result`.
- **Zeilenbudget: höchstens 12.000 Zeilen Produktcode** (ohne Tests, `xtask`, Simulatoren). `cargo xtask loc` prüft das in der CI. Liegt der Code darüber, muss die nächste Änderung zuerst Code abbauen.
- Lieber ein neues kleines Modul als eine wachsende Sammeldatei. Keine spekulativen Abstraktionen.
- Code, Bezeichner, Kommentare und Commit-Nachrichten auf Englisch; Spezifikation und Doku auf Deutsch.
- Jeder Agent nutzt ein eigenes `CARGO_TARGET_DIR`, wenn mehrere Agenten parallel laufen.

## Tests

- Jede Anforderung braucht die in `verification` genannten Prüfarten, bevor `verified` gesetzt wird.
- Tests geben kurz aus; Details gehen in Logdateien unter `target/test-logs/`. Fehlerzeilen beginnen mit `ERROR`.
- Golden Files (Verhalten von Alt-Electrip) liegen unter `tests/golden/` und werden nur mit `cargo xtask golden --record` neu erzeugt – nie von Hand angepasst, damit ein Test grün wird.
- Hardware gibt es in der Sitzung nicht. Hardware-Tests (`hw: true`) bereitet der Agent als Checkliste in `spec/hw-checklist.md` vor; durchführen tut sie Mo.
- Es gibt keine echte Z21. Z21-Simulator und Z21-Treiber werden in getrennten Sitzungen gebaut, jeweils nur aus der Roco-Spezifikation.

## Git

- Kleine, in sich abgeschlossene Commits; Nachricht beginnt mit der Anforderungs-ID, z. B. `B-08: add speed curve interpolation`.
- Nichts in `legacy/` ändern (Referenz). Ausnahme: ein Headless-Wrapper für Golden-Tests unter `tools/legacy-harness/`, nicht in `legacy/` selbst.
- Keine Secrets, keine großen Binärdateien außer im Korpus (`tests/corpus/`, SHA-256 in `tests/corpus/SHA256SUMS`).
