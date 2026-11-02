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
    "speed": 0.0,
    "forward": true
  }],
  "station": {"host": "localhost", "port": 4303, "bus": 1, "connected": false}
}
```

- `locos` steht in der Reihenfolge der Lokliste (B-04); eine `id` wird nie wiederverwendet, auch nicht nach dem Löschen.
- `name`: neue Loks heißen „Unbenannte Lok“ (B-04).
- `protocol`: `motorola1`, `motorola2`, `dcc_short`, `dcc_long` (B-06).
- `speed_curve`: Kontrollpunkte `[km/h, Fahrstufe]` (B-08).
- `accel_duration`, `brake_duration`: Sekunden von 0 auf Vmax bei voller Beschleunigung bzw. von Vmax auf 0 bei voller Bremsung, 1–9999 s; `volume`: Lautstärke von 0 (stumm) bis 1 (B-05).
- `speed`: Geschwindigkeit in km/h, `forward`: Fahrtrichtung (B-10).
  Die Zentrale bekommt die Fahrstufe aus der Kennlinie, abgeschnitten wie in Electrip 1.
- `station`: SRCP-Server (Vorgabe wie Electrip 1: `localhost`, Port 4303, Bus 1) und ob die App mit ihm verbunden ist (B-01).
  Bricht die Verbindung ab, geht an alle Clients ein Zustand mit `connected: false`.

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
| `add_curve_point` | `loco`, `speed`, `step` | B-08 |
| `remove_curve_point` | `loco`, `point` (Nummer ab 0) | B-08 |
| `move_curve_point` | `loco`, `point`, `speed`, `step` | B-08 |
| `set_axis` | `loco`, `deflection` (Auslenkung der Fahrachse von -1 voll zurück bis 1 voll vor; bis 0,06 wird sie ignoriert wie in Electrip 1) | B-10 |
| `reverse` | `loco` (Richtungswender: Geschwindigkeit 0, dann andere Richtung) | B-10 |
| `set_server` | `host`, `port`, `bus` (nur ohne Verbindung) | B-01 |
| `connect` | – (verbindet mit dem eingestellten Server; ein Fehler nennt die Ursache) | B-01 |
| `disconnect` | – | B-01 |

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
