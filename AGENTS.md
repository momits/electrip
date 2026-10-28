# AGENTS.md – Regeln für Agenten in diesem Repo

Electrip 2 ist die Neuentwicklung von Electrip (Modellbahnsteuerung mit Gamepads) in Rust. Der Code wird von KI-Agenten geschrieben; Mo (Moritz Renftle) gibt Spezifikation, Architektur und Hardware-Abnahme frei.

## Zuerst lesen

1. `PROGRESS.md` – was zuletzt passiert ist und was als Nächstes ansteht
2. `git log --oneline -20`
3. `spec/requirements.json` – Paritätskatalog; nur hier steht, was gebaut wird
4. `spec/decisions/` – verbindliche Architekturentscheidungen
5. In Phase 0: `spec/phase0-plan.md`
6. Bei Bedarf: `spec/konzept.md` (Gesamtkonzept), `spec/benutzerhandbuch.pdf` (Handbuch Electrip 1), `legacy/` (Code Electrip 1)

## Ablauf einer Sitzung

1. Stand lesen (siehe oben). Ab Phase 0 Schritt 3: `cargo xtask parity` und `cargo xtask test`.
2. Ist etwas rot, das zuerst reparieren – vor jeder neuen Arbeit.
3. **Eine** offene Aufgabe wählen (niedrigste Phase zuerst) und beanspruchen: Datei `current_tasks/<ID>.md` mit Datum, Kurzplan und **Basis-Commit** (`git rev-parse HEAD`) anlegen, committen, pushen. Existiert die Datei schon, andere Aufgabe wählen.
4. Umsetzen. Prüffälle aus `verification` der Anforderung schreiben bzw. grün machen. Wo möglich die App über den Steuerkanal selbst bedienen.
5. **Einfachheits-Review (Pflicht nach jedem Inkrement – Feature, Bugfix, Refactoring, Testwerkzeug):** siehe Abschnitt unten. Befunde sofort refactoren, Tests wieder grün.
6. Abschluss: Status in `spec/requirements.json` setzen, Eintrag in `PROGRESS.md` ergänzen (inkl. Review-Ergebnis), `current_tasks/<ID>.md` löschen, committen, pushen.
7. Wenn die Sitzung vorher endet (Limit, Kontext voll): Zwischenstand committen und in `PROGRESS.md` beschreiben, was fehlt. Ein unfertiges Inkrement wird erst nach seinem Review als fertig markiert.

## Einfachheits-Review: DRY, YAGNI, KISS

Jedes Inkrement wird vor dem Abschluss einmal gegen diese Liste geprüft. Grundlage ist der Diff seit dem Basis-Commit: `git diff <basis>..HEAD`.

**Wer prüft:** möglichst ein frischer Sub-Agent (Task/Agent-Tool) mit nur dem Diff, dieser Liste und `AGENTS.md` als Kontext – wer den Code gerade geschrieben hat, übersieht eigene Umwege. Fehlt dafür das Kontingent, prüft der Agent selbst und liest den Diff dabei komplett neu.

**DRY – nichts doppelt**
- Dieselbe Logik oder dasselbe Fachwissen (Formel, Mapping, Konstante, Protokoll-Detail) steht nur an einer Stelle.
- Kopierte Blöcke (ab ca. 5 ähnlichen Zeilen) werden zusammengeführt.
- Aber: zwei Stellen, die nur zufällig ähnlich aussehen, bleiben getrennt. Abstrahieren erst beim dritten echten Vorkommen (Rule of Three).

**YAGNI – nichts auf Vorrat**
- Jede neue Funktion, jeder Parameter, jede Option ist durch eine Anforderung in `spec/requirements.json` oder einen Test begründet.
- Keine Erweiterungspunkte „für später“, keine Traits/Generics mit nur einer Implementierung – außer per ADR vorgesehen (`CommandStation`, `AudioSink`).
- Kein toter Code, keine auskommentierten Reste, keine ungenutzten Abhängigkeiten oder Feature-Flags.

**KISS – die einfachste Lösung, die die Tests besteht**
- Klarer, direkter Code vor cleverem Code: keine Makros, Typ-Tricks oder Indirektionen, wo eine einfache Funktion reicht.
- Funktionen kurz (Richtwert < 40 Zeilen), Verschachtelung flach, sprechende Namen.
- Standardbibliothek und bereits genutzte Bibliotheken vor eigenem Code.
- Gegenfrage: Ginge dasselbe mit spürbar weniger Zeilen? Dann so.

**Bei Befunden**
- Refactoring ändert kein Verhalten: Tests vorher und nachher grün, Golden Files unverändert.
- Eigener Commit: `<ID>: refactor after simplicity review`.
- Jeder Abschluss-Commit eines Inkrements trägt den Trailer `Simplicity-Review: ok` oder `Simplicity-Review: refactored` (sobald `xtask` existiert, prüft die CI das).
- Befunde, die über das Inkrement hinausgehen (älterer Code), nicht nebenbei umbauen, sondern in `PROGRESS.md` unter „Aufräumkandidaten“ notieren; der Aufräum-Agent arbeitet sie je Phase ab.

## Spezifikation

- `spec/requirements.json`: Agenten ändern **nur** die Felder unter `status`. Anforderungen, Akzeptanzkriterien und Prüfarten ändert nur Mo.
- `status.wired` = Funktion existiert und ist angebunden. `status.verified` = alle automatischen Prüffälle grün. `status.accepted` setzt **nur Mo**.
- Widerspruch oder Lücke zwischen Handbuch, Alt-Code und Anforderung: nicht selbst entscheiden, sondern als Frage in `spec/questions.md` eintragen und mit einer anderen Aufgabe weitermachen. Vorrang bei klaren Fällen: neue Anforderung vor Alt-Code vor Handbuch.
- Neue Architekturentscheidungen nur als ADR-Entwurf (`spec/decisions/NNNN-titel.md`, Status „Vorschlag“); Mo setzt auf „Angenommen“.

## Architekturregeln

- **Befehl zuerst.** Jede Nutzeraktion ist ein Befehl im Kern (`core`). Gamepad, UI, Steuerkanal und Tests rufen nur Befehle auf. Keine Fachlogik in `ui`.
- **Schichten:** `core` hängt von keinem anderen Crate des Workspace ab. Treiber (`station-*`), `input`, `audio`, `library`, `sync` hängen nur von `core` ab. `ui` und `control` dürfen alles nutzen. Die Regel wird per `cargo xtask` geprüft.
- **Zentralen** nur über den Trait `CommandStation`. **Audio** nur über den Trait `AudioSink`.
- **Sitzungs-Host (ADR 0010):** Rampen, Sound-Modelle und Konfliktregeln laufen nur im Host. Steuerkanal und Client-Host-Verbindung sind **dasselbe** JSON-Protokoll – kein zweites Protokoll bauen.
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
