# Steuerkanal (N-08)

Lokaler JSON-Steuerkanal für Agenten, Tests und Skripte (ADR 0002).
Die spätere Client-Host-Verbindung (N-03, ADR 0010) nutzt dasselbe Format.

## Verbindung

- `electrip [--control-port <port>] [--library <verzeichnis>] [-f|--file <konfiguration>]` startet die App ohne Oberfläche; Standardport 4711, Port 0 wählt einen freien Port.
- `--library`: Verzeichnis der Konfigurationen, eine Datei `<name>.json` je Konfiguration (B-21).
  Vorgabe ist `electrip` im Datenverzeichnis des Nutzers (Linux `$XDG_DATA_HOME` bzw. `~/.local/share`, macOS `~/Library/Application Support`, Windows `%APPDATA%`).
  Ein leeres Verzeichnis bekommt die Konfiguration „Electrip“.
- Beim Start ist die Konfiguration `-f`/`--file` geöffnet (B-24), sonst die erste nach Namen.
- Der Steuerkanal lauscht nur auf `127.0.0.1` (TCP).
- Die erste Zeile auf der Standardausgabe endet mit der Adresse: `… control channel on 127.0.0.1:4711`.
- Jede Nachricht ist ein JSON-Objekt in einer Zeile (UTF-8, Zeilenende `\n`), in beide Richtungen.

## Nachrichten der App

Jede Nachricht hat ein Feld `type`.

| `type` | Felder | Wann |
|---|---|---|
| `hello` | `version` (Zahl, derzeit `1`) | als erste Nachricht nach dem Verbinden |
| `state` | `state` (Zustand, siehe unten) | nach `hello` und an **alle** Clients nach jedem erfolgreichen Befehl, außerdem alle 50 ms, solange sich der Zustand ändert (z. B. beim Beschleunigen) |
| `reply` | `ok` (bool), bei Fehler `error` (Text) | an den Absender, auf jeden Befehl genau eine, vor der folgenden `state` |

Ein fehlgeschlagener Befehl ändert nichts; dann folgt keine `state`-Nachricht.
Zwischen Befehl und `reply` kann eine `state`-Nachricht eintreffen, die sich nicht auf den Befehl bezieht.
Die `version` steigt bei inkompatiblen Änderungen des Formats.

## Zustand

```json
{
  "locos": [{
    "id": 1,
    "name": "Unbenannte Lok",
    "decoder": {"protocol": "dcc_short", "address": 1, "speed_steps": 128},
    "max_speed": 100.0,
    "speed_curve": [[0.0, 0.0], [100.0, 128.0]],
    "accel_duration": 11.5,
    "brake_duration": 8.5,
    "volume": 0.8,
    "functions": [{"action": 1, "number": 0, "name": "Licht", "mode": "switch", "default_on": false, "on": false}],
    "sound_functions": [],
    "event_sounds": [],
    "picture": null,
    "speed": 0.0,
    "forward": true
  }],
  "actions": [{"id": 1, "name": "Licht"}],
  "mappings": [{"kind": "Xbox Series X Controller", "bindings": [{"control": "lefty", "target": {"type": "drive", "dead_zone": 0.06}}]}],
  "devices": [{"id": 1, "kind": "Xbox Series X Controller", "loco": 1, "color": 1}],
  "station": {"kind": "srcp", "host": "localhost", "port": 4303, "bus": 1, "power_on_start": true, "connected": false, "track_power": false},
  "import_report": [],
  "configuration": "Electrip",
  "configurations": ["Electrip"]
}
```

- `locos` steht in der Reihenfolge der Lokliste (B-04); eine `id` wird nie wiederverwendet, auch nicht nach dem Löschen.
- `name`: neue Loks heißen „Unbenannte Lok“ (B-04).
- `protocol`: `motorola1`, `motorola2`, `dcc_short`, `dcc_long` (B-06).
- `speed_curve`: Kontrollpunkte `[km/h, Fahrstufe]` (B-08).
- `accel_duration`, `brake_duration`: Sekunden von 0 auf Vmax bei voller Beschleunigung bzw. von Vmax auf 0 bei voller Bremsung, 1–9999 s; `volume`: Lautstärke von 0 (stumm) bis 1 (B-05).
- `functions`: Decoder-Funktionen der Lok in der vom Nutzer sortierten Reihenfolge (B-07): logische Aktion `action`, Funktionsnummer `number` (F0–F28), `name`, `mode` (`switch` Umschalter: erste Auslösung an, zweite aus; `push` Taster: an, solange gehalten), `default_on` (Standardzustand „An“ kehrt beide Modi um) und `on` (ob die Funktion gerade an ist; die Zentrale bekommt alle Funktionen, die an sind).
- `sound_functions`: Geräusch-Funktionen der Lok in der vom Nutzer sortierten Reihenfolge (B-16): logische Aktion `action`, `name`, Sounddatei `path` auf dem Host (oder `null`), `mode` (`switch` Umschalter: Loop bis zur zweiten Auslösung; `push_once` Taster einmal: höchstens einmal, Abbruch beim Loslassen; `push` Taster wiederholt: Loop, solange gehalten; `tap` Anschalter: bis Dateiende, Auslösungen dazwischen tun nichts) und `on` (ob sie gerade an ist; zu Beginn aus, ein Anschalter geht am Dateiende aus).
- `event_sounds`: Geräusch-Ereignisse der Lok (B-17): logische Aktion `action` (jedes Drücken schaltet aktiv/inaktiv), `name`, Sounddatei `path` auf dem Host (oder `null`), `default_active` (aktiv zu Beginn, Standard `true`; wird gespeichert), `active` (ob es gerade aktiv ist), `forward` (`true` nur vorwärts, `false` nur rückwärts, `null` beliebig), `min_speed`/`max_speed` in km/h, `min_accel`/`max_accel` in km/h pro Sekunde (`null` = keine Grenze), `fade_in`/`fade_out` in Sekunden und `play_to_end` (einmal gestartet bis zum Ende, ohne Ausblenden).
  Es spielt nur, wenn die Lok ein Sound-Modell hat, und läuft im Loop, solange alle Bedingungen gelten; gelten sie nicht mehr, blendet es aus. Der Host prüft bei jeder Abfrage (50 ms); die Beschleunigung ist die Änderung der Geschwindigkeit seit der letzten Abfrage.
- `picture`: Name des Lokbilds (B-05) oder `null`. Die Datei `media/<picture>.png` in der Bibliothek ist der gespeicherte Ausschnitt in 440×340 px; der Name ist ihr SHA-256, so liegt jedes Bild nur einmal dort.
- `actions`: logische Aktionen der Konfiguration (N-07); eine `id` wird nie wiederverwendet.
- `mappings`: je Gerätetyp `kind` die Belegung seiner Bedienelemente (N-01, B-02, ADR 0009).
  `control` heißt wie in SDL, z. B. `a`, `lefty`, `dpleft`; Joysticks ohne Gamepad-Belegung z. B. `button0`, `axis1`, `hat0_left`.
  `target` ist ein Objekt mit `type`: `drive` (Fahrachse, `dead_zone` Totzone, Standard 0,06), `reverse`, `toggle_power` (Nothalt der Anlage), `emergency_stop` (Lok-Nothalt), `previous_loco`, `next_loco` (Lokwechsel zur nächsten Lok in der Liste, die kein anderes Gerät steuert, wie Electrip 1) oder `action` mit `action` (logische Aktion).
  Ein neuer Gerätetyp bekommt das Standard-Mapping nach Electrip 1: `lefty` fährt, `a` Nothalt der Anlage, `b` Richtungswender, `dpleft`/`dpright` Lokwechsel.
- `devices`: angeschlossene Eingabegeräte, auch virtuelle über den Steuerkanal; `loco` ist die Lok, die das Gerät steuert (`null`, wenn keine frei ist).
  Ein neues Gerät steuert die erste Lok, die kein anderes Gerät steuert; wird seine Lok gelöscht oder kommt eine Lok dazu, bekommt ein Gerät ohne Lok die erste freie.
  `color` ist die Farbe des Geräts (1 bis 12, wie die zwölf Gamepad-Symbole von Electrip 1); ein neues Gerät bekommt die kleinste, die kein angeschlossenes Gerät hat (B-03).
- `speed`: Geschwindigkeit in km/h, `forward`: Fahrtrichtung (B-10).
- `sound`: Fahrgeräusch `off`, `starting`, `on` oder `stopping` (B-11, B-12). Beim Diesel spielt `starting` das Anlassgeräusch bis zum Leerlauf; `stopping` wartet auf das Ende des Leerlaufgeräuschs und spielt das Abstellgeräusch. Währenddessen bleibt die Geschwindigkeit stehen, auch bei ausgelenkter Fahrachse; die Dauer kommt aus der Länge der Dateien.
  Die Zentrale bekommt die Fahrstufe aus der Kennlinie, abgeschnitten wie in Electrip 1.
- `station`: Zentrale (`kind`: `srcp` oder `z21`; Vorgabe wie Electrip 1: SRCP-Server `localhost`, Port 4303, Bus 1) und ob die App mit ihr verbunden ist (B-01, N-02).
  Bricht die Verbindung ab, geht an alle Clients ein Zustand mit `connected: false`.
- `power_on_start`: ob `connect` den Gleisstrom einschaltet (Vorgabe an, B-23); `track_power`: Gleisstrom, wie ihn die Zentrale zuletzt gemeldet hat, ohne Verbindung `false`.
  Schaltet eine andere Instanz an derselben Zentrale den Gleisstrom, folgt `track_power` (B-23).
- `configuration`: Name der geöffneten Konfiguration; `configurations`: alle Konfigurationen der Bibliothek, sortiert (B-21).
  Jede Änderung an Loks, Aktionen, Mappings und Server wird sofort in die Datei der geöffneten Konfiguration geschrieben, Funktionen in ihrem Standardzustand; Fahrzustand und Geräte werden nicht gespeichert.
- `import_report`: Was der letzte Import aus Electrip 1 angepasst hat, eine Zeile je Änderung, z. B. Loks mit N 1 und Adresse über 127, die auf DCC lang umgestellt wurden (B-06).

## Befehle

Ein Befehl ist ein Objekt mit dem Feld `command` und seinen Parametern; `loco` ist die `id` der Lok.

| `command` | Parameter | Anforderung |
|---|---|---|
| `add_loco` | – (Vorgaben wie Electrip 1: DCC kurz, Adresse 1, 128 Fahrstufen, 100 km/h, Beschleunigung 11,5 s, Bremsen 8,5 s, Lautstärke 0,8) | B-04 |
| `rename_loco` | `loco`, `name` | B-04 |
| `remove_loco` | `loco` | B-04 |
| `move_loco` | `loco`, `position` (neue Stelle in der Lokliste ab 0) | B-04 |
| `set_address` | `loco`, `address` | B-06 |
| `set_protocol` | `loco`, `protocol`, `confirmed` | B-06, B-09 |
| `set_speed_steps` | `loco`, `speed_steps`, `confirmed` | B-06, B-09 |
| `set_max_speed` | `loco`, `max_speed`, `confirmed` | B-05, B-09 |
| `set_accel_duration` | `loco`, `seconds` | B-05 |
| `set_brake_duration` | `loco`, `seconds` | B-05 |
| `set_volume` | `loco`, `volume` | B-05 |
| `set_picture` | `loco`, `path` (PNG oder JPEG auf dem Rechner der App), optional `crop` (Ausschnitt in Pixeln des Bildes: `x`, `y` linke obere Ecke, `width` Breite; die Höhe folgt aus dem Seitenverhältnis 22:17. Verschieben ändert `x`/`y`, Zoomen `width`. Standard: der größte Ausschnitt in der Mitte); speichert den Ausschnitt als Lokbild in 440×340 px | B-05 |
| `add_curve_point` | `loco`, `speed`, `step` | B-08 |
| `remove_curve_point` | `loco`, `point` (Nummer ab 0) | B-08 |
| `move_curve_point` | `loco`, `point`, `speed`, `step` | B-08 |
| `set_axis` | `loco`, `deflection` (Auslenkung der Fahrachse von -1 voll zurück bis 1 voll vor; bis 0,06 wird sie ignoriert wie in Electrip 1) | B-10 |
| `reverse` | `loco` (Richtungswender: Geschwindigkeit 0, dann andere Richtung) | B-10 |
| `toggle_sound` | `loco` (schaltet das Fahrgeräusch ein oder aus; ohne Sound-Modell tut es nichts) | B-02, B-11, B-12 |
| `add_action` | `name` | N-07 |
| `rename_action` | `action`, `name` | N-07 |
| `remove_action` | `action` (löscht auch alle Funktionen und Belegungen, die auf die Aktion zeigen) | N-07 |
| `add_function` | `loco`, `function` (Objekt mit `action`, `number`, optional `name` (Standard leer), `mode` (Standard `switch`), `default_on` (Standard `false`)); hängt die Funktion an, sie steht im Standardzustand | B-07 |
| `remove_function` | `loco`, `index` (Nummer ab 0 in `functions`) | B-07 |
| `move_function` | `loco`, `index`, `position` (neue Stelle ab 0) | B-07 |
| `add_sound_function` | `loco`, `function` (Objekt mit `action`, `path`, optional `name` (Standard leer), `mode` (Standard `tap` wie Electrip 1)); hängt die Geräusch-Funktion aus an | B-16 |
| `remove_sound_function` | `loco`, `index` (Nummer ab 0 in `sound_functions`) | B-16 |
| `move_sound_function` | `loco`, `index`, `position` (neue Stelle ab 0) | B-16 |
| `add_event_sound` | `loco`, `sound` (Objekt wie in `event_sounds` mit `action` und `path`, alles andere optional); hängt das Geräusch-Ereignis an, `active` wie `default_active` | B-17 |
| `remove_event_sound` | `loco`, `index` (Nummer ab 0 in `event_sounds`) | B-17 |
| `trigger_action` | `loco`, `action`, `pressed` (`true` gedrückt, `false` losgelassen); schaltet die Funktionen, Geräusch-Funktionen und Geräusch-Ereignisse der Lok, die auf die Aktion zeigen, eine Aktion ohne Funktion bei dieser Lok tut nichts | N-07, B-07, B-16, B-17 |
| `add_device` | `device` (frei gewählte `id`), `kind` (Gerätetyp); schließt ein (virtuelles) Eingabegerät an; höchstens 12 gleichzeitig | N-01, B-03 |
| `remove_device` | `device`; die Achse seiner Lok wird losgelassen, die Lok behält ihre Geschwindigkeit | N-01 |
| `bind` | `kind`, `control`, `target` (siehe `mappings`); ersetzt die bisherige Belegung des Bedienelements | N-01, B-02 |
| `unbind` | `kind`, `control` | N-01, B-02 |
| `input` | `device`, `control`, `value` (Knöpfe und Hat-Richtungen `1` gedrückt, `0` losgelassen; Achsen -1 bis 1, nach oben negativ wie in SDL); wirkt über das Mapping auf die Lok des Geräts, ein unbelegtes Bedienelement tut nichts | N-01, B-02 |
| `set_server` | `kind` (`srcp` oder `z21`, Vorgabe `srcp`; der Z21-Treiber ist experimentell), `host`, `port` (srcpd 4303, Z21 21105), `bus` (nur SRCP; nur ohne Verbindung) | B-01, N-02 |
| `connect` | – (verbindet mit dem eingestellten Server; ein Fehler nennt die Ursache) | B-01 |
| `disconnect` | – | B-01 |
| `set_power_on_start` | `on` | B-23 |
| `toggle_power` | – (Nothalt der Anlage: Gleisstrom aus, beim nächsten Mal wieder an; nur mit Verbindung) | B-23 |
| `emergency_stop` | `loco` (Lok-Nothalt: nur diese Lok hält sofort, die Achse wird losgelassen; der Gleisstrom bleibt an) | B-23 |
| `new_configuration` | `name` (legt eine leere Konfiguration an und öffnet sie; nur ohne Verbindung) | B-21 |
| `open_configuration` | `name` (nur ohne Verbindung; Loks bekommen neue `id`s, Geräte behalten ihre Lok, wenn sie können) | B-21 |
| `rename_configuration` | `name` (neuer Name der geöffneten Konfiguration) | B-21 |
| `remove_configuration` | `name` (löscht eine andere als die geöffnete Konfiguration) | B-21 |
| `export_configuration` | `path` (schreibt die geöffnete Konfiguration in eine Datei auf dem Rechner der App) | B-21 |
| `import_electrip1` | `path` (Konfigurationsdatei von Electrip 1 auf dem Rechner der App; wird eine neue Konfiguration mit dem Dateinamen ohne Endung und geöffnet, nur ohne Verbindung; ein Fehler nennt die Ursache und ändert nichts). Übernommen wird bisher, was Electrip 2 kennt: Name, Decoder, Vmax, Kennlinie, Dauern, Lautstärke, Lokbild (mittig zugeschnitten; ein relativer Pfad gilt ab dem Ordner der Datei, ein fehlendes Bild steht im `import_report`), Server. Fehlende Werte bekommen die Vorgaben von Electrip 1. | B-21, B-06 |
| `export_loco` | `loco`, `path` (Datei auf dem Rechner der App); schreibt die Lok als ZIP: `loco.json` mit der Lok und den Aktionen, die ihre Funktionen nutzen, das Lokbild als `media/<name>.png` und jede Sounddatei als `sounds/<name>` (Name nach Inhalt); eine fehlende Sounddatei ist ein Fehler | B-20 |
| `import_loco` | `path` (ZIP von `export_loco` oder Lokpaket von Electrip 1 auf dem Rechner der App); hängt die Lok an die Lokliste, Bild und Sounds kommen in die Bibliothek (Sounds nach `sounds/`, Name nach Inhalt). Funktionen bekommen die Aktionen dieser Konfiguration mit gleichem Namen, fehlende Aktionen werden angelegt. Aus Paketen von Electrip 1 wird übernommen, was `import_electrip1` übernimmt; ein fehlendes Bild oder ein fehlender Sound steht im `import_report` und wird weggelassen | B-20 |

Namen von Konfigurationen müssen auf allen Systemen Dateinamen sein: nicht leer, ohne `.` am Anfang und Leerzeichen am Ende, ohne `< > : " / \ | ? *` und Steuerzeichen.

`confirmed` ist optional (Standard `false`).
Setzt eine Änderung die Kennlinie zurück und fehlt die Bestätigung, antwortet die App mit einem Fehler und ändert nichts (B-09).

Beispiel:

```
→ {"command": "set_max_speed", "loco": 1, "max_speed": 80}
← {"type": "reply", "ok": false, "error": "this change resets the speed curve and needs a confirmation"}
→ {"command": "set_max_speed", "loco": 1, "max_speed": 80, "confirmed": true}
← {"type": "reply", "ok": true}
← {"type": "state", "state": {…}}
```

## Tests

`crates/electrip/tests/common/mod.rs` startet die App auf einem freien Port und spricht den Steuerkanal an (`App::start`, `App::connect`, `Client::command`).
Tests mit der Prüfart `control-channel` liegen unter `crates/electrip/tests/` und binden den Helfer mit `mod common;` ein.

Noch nicht enthalten: Screenshots; sie kommen mit der Oberfläche.
