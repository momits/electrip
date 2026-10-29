# Golden-Harness für Electrip 1

Der Harness startet den unveränderten Code aus `legacy/` ohne GTK, ohne Gamepad und ohne Soundkarte.
Er spielt skriptbare Eingaben ab und zeichnet gesendete SRCP-Befehle und Sound-Ereignisse auf.
Aus diesen Aufzeichnungen entstehen die Golden Files unter `tests/golden/`.

## Aufruf

```sh
cargo xtask golden --record   # alle Szenarien neu aufzeichnen
cargo xtask golden            # prüfen, ob die Golden Files zum Harness passen
python3 tools/legacy-harness/harness.py tests/golden/scenarios/diesel_drive.json
```

Gebraucht wird nur Python ab 3.9, ohne weitere Pakete.
Golden Files nie von Hand ändern (`AGENTS.md`).

## Szenarien

Jede Datei `tests/golden/scenarios/<name>.json` erzeugt `tests/golden/<name>.jsonl`.
Es gibt zwei Arten.

**Kennlinie (B-08):** `curves` ist eine Liste von Kontrollpunkten `points` und Geschwindigkeiten `x`.
Der Harness lädt die Punkte in `LinearSegmentFunction` und gibt die Fahrstufe `step` je `x` aus.
Die Zeile mit `points` zeigt die Punkte nach dem Laden, also nach Sortieren und Begrenzen.

**Fahrsitzung:** Der Harness startet die Steuerung von Electrip 1 (`control_ui.MainBox`) mit einem virtuellen Gamepad.

- `config`: vollständige Konfiguration im JSON-Format von Electrip 1.
- `sound_lengths`: Länge in Sekunden je Sounddatei, so wie sie in `config` steht.
  Dateien gibt es nicht; was hier fehlt, gilt als ungültige Datei.
- `input`: zeitlich geordnete Eingaben.
  `{"t": 2.0, "axis": -1.0}` setzt die Beschleunigungsachse als Rohwert von pygame, −1 ist Vollausschlag nach vorn.
  `{"t": 0.5, "press": 4}` und `{"t": 0.6, "release": 4}` drücken und lösen einen Knopf.
- `until`: Ende der Aufzeichnung in Sekunden.
- `requirements`: Anforderungen, die das Szenario abdeckt.

## Aufgezeichnete Ereignisse

Jede Zeile ist ein JSON-Objekt mit der Zeit `t` in Sekunden ab Start.

- `{"srcp": "SET 1 GL 3 1 36 128 1"}`: an die Zentrale gesendeter Befehl.
- `{"input": {...}}`: die Eingabe aus dem Szenario.
- `{"ch": 0, "sound": "diesel/accel1.wav", "ev": ...}`: Sound-Ereignis auf einem Mixer-Kanal.
  `start` (optional mit `fade_in_ms`), `end` (natürliches Ende), `stop`, `replaced` (von `play` verdrängt), `fade_out` (mit `ms`) und `faded` (Ausblenden fertig).

Kanalnummern sind ein Detail von Electrip 1.
Ein Vergleich mit Electrip 2 sollte sich auf Sound, Ereignis und Zeit stützen.
Zeiten sind auf Mikrosekunden gerundet, Vergleiche brauchen also eine kleine Toleranz.

## Wie der Harness arbeitet

`fakes.py` ersetzt GTK, GObject, pygame und die Threads des Dampf-Sounds.
`harness.py` lädt damit `legacy/src/electrip` und ersetzt nur Modulattribute, nie Dateien in `legacy/`.

- Eine virtuelle Uhr in Mikrosekunden treibt `time.time()`, `GObject.timeout_add` und Wartezeiten der Threads.
  Timer, Idle-Callbacks und Threads laufen streng nacheinander.
  Deshalb liefert jeder Lauf dieselbe Ausgabe.
- Der Mixer folgt pygame 1.9.4 (`src/mixer.c`) und SDL_mixer.
  Ein Kanal hat einen laufenden und höchstens einen wartenden Sound.
  Jedes Ende einer Wiedergabe sendet das End-Ereignis des Kanals.
  Beim natürlichen Ende startet der wartende Sound lückenlos.
  Beim Anhalten verfällt er, und es kommen zwei End-Ereignisse.
- Der Gamepad-Ereignis-Thread von Electrip 1 läuft nicht als Thread.
  Der Harness ruft seine Methode `run` auf, sobald Ereignisse anstehen.
- Die Pegelanzeige (`show_level_bar`) ist aus, weil sie nur die Anzeige betrifft und eigene Threads startet.
- Fallen mehrere Dinge auf denselben Zeitpunkt, laufen zuerst bereite Threads, dann Gamepad- und Mixer-Ereignisse, dann Idle-Callbacks, dann der nächste Timer.

## Auffälligkeiten von Electrip 1

Die Golden Files zeigen das echte Verhalten von Electrip 1, auch wo es überrascht.

- Diesel: Der Mixer plant immer einen Sound voraus.
  Ein Segmentwechsel beginnt daher erst nach dem laufenden und dem schon wartenden Sound.
- Diesel: Die Steuerung sendet die erste Fahrstufe erst mit Beginn des Übergangs Leerlauf → Segment 1 und Fahrstufe 0 erst mit dem Übergang Segment 1 → Leerlauf (B-13).
- Dampf: Eine neue Taktpause gilt erst nach der laufenden Pause.
- Geräusch-Ereignisse: siehe Frage Q-013 in `spec/questions.md`.
