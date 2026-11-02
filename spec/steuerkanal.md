# Steuerkanal (N-08)

Lokaler JSON-Steuerkanal für Agenten, Tests und Skripte (ADR 0002).
Die spätere Client-Host-Verbindung (N-03, ADR 0010) nutzt dasselbe Format.

## Verbindung

- `electrip [--control-port <port>]` startet die App ohne Oberfläche; Standardport 4711, Port 0 wählt einen freien Port.
- Der Steuerkanal lauscht nur auf `127.0.0.1` (TCP).
- Die erste Zeile auf der Standardausgabe endet mit der Adresse: `… control channel on 127.0.0.1:4711`.
- Jede Nachricht ist ein JSON-Objekt in einer Zeile (UTF-8, Zeilenende `\n`), in beide Richtungen.

## Nachrichten der App

Jede Nachricht hat ein Feld `type`.

| `type` | Felder | Wann |
|---|---|---|
| `hello` | `version` (Zahl, derzeit `1`) | als erste Nachricht nach dem Verbinden |
| `state` | `state` (Zustand, siehe unten) | nach `hello` und an **alle** Clients nach jedem erfolgreichen Befehl |
| `reply` | `ok` (bool), bei Fehler `error` (Text) | an den Absender, auf jeden Befehl genau eine, vor der folgenden `state` |

Ein fehlgeschlagener Befehl ändert nichts; dann folgt keine `state`-Nachricht.
Die `version` steigt bei inkompatiblen Änderungen des Formats.

## Zustand

```json
{
  "locos": [{
    "id": 1,
    "name": "Unbenannte Lok",
    "decoder": {"protocol": "dcc_short", "address": 1, "speed_steps": 128},
    "max_speed": 100.0,
    "speed_curve": [[0.0, 0.0], [100.0, 128.0]]
  }],
  "station": "disconnected"
}
```

- `locos` steht in der Reihenfolge der Lokliste (B-04); eine `id` wird nie wiederverwendet, auch nicht nach dem Löschen.
- `name`: neue Loks heißen „Unbenannte Lok“ (B-04).
- `protocol`: `motorola1`, `motorola2`, `dcc_short`, `dcc_long` (B-06).
- `speed_curve`: Kontrollpunkte `[km/h, Fahrstufe]` (B-08).
- `station`: Verbindung zur Zentrale; bisher nur `disconnected`, es gibt noch keinen Treiber.

## Befehle

Ein Befehl ist ein Objekt mit dem Feld `command` und seinen Parametern; `loco` ist die `id` der Lok.

| `command` | Parameter | Anforderung |
|---|---|---|
| `add_loco` | – (Vorgaben wie Electrip 1: DCC kurz, Adresse 1, 128 Fahrstufen, 100 km/h) | B-04 |
| `rename_loco` | `loco`, `name` | B-04 |
| `remove_loco` | `loco` | B-04 |
| `move_loco` | `loco`, `position` (neue Stelle in der Lokliste ab 0) | B-04 |
| `set_address` | `loco`, `address` | B-06 |
| `set_protocol` | `loco`, `protocol`, `confirmed` | B-06, B-09 |
| `set_speed_steps` | `loco`, `speed_steps`, `confirmed` | B-06, B-09 |
| `set_max_speed` | `loco`, `max_speed`, `confirmed` | B-05, B-09 |
| `add_curve_point` | `loco`, `speed`, `step` | B-08 |
| `remove_curve_point` | `loco`, `point` (Nummer ab 0) | B-08 |
| `move_curve_point` | `loco`, `point`, `speed`, `step` | B-08 |

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

Noch nicht enthalten: Screenshots und virtuelle Eingaben; sie kommen mit Oberfläche und Eingabegeräten.
