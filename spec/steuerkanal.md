# Steuerkanal (N-08)

Lokaler JSON-Steuerkanal für Agenten, Tests und Skripte (ADR 0002).
Die spätere Client-Host-Verbindung (N-03, ADR 0010) nutzt dasselbe Format.

## Verbindung

- `electrip [--headless] [--control-port <port>] [--library <verzeichnis>] [-f|--file <konfiguration>] [--host <adresse[:port]>] [--no-discovery]` startet die App; Standardport 4711, Port 0 wählt einen freien Port.
- Das Fenster ist selbst ein Client des Steuerkanals und sendet dieselben Befehle (B-22).
  Mit `--headless` läuft die App ohne Fenster; die Tests starten sie so. Ohne Anzeige meldet sie `ERROR no window` und läuft ebenfalls ohne Fenster weiter.
- `--library`: Verzeichnis der Konfigurationen, eine Datei `<name>.json` je Konfiguration (B-21).
  Vorgabe ist `electrip` im Datenverzeichnis des Nutzers (Linux `$XDG_DATA_HOME` bzw. `~/.local/share`, macOS `~/Library/Application Support`, Windows `%APPDATA%`).
  Ein leeres Verzeichnis bekommt die Konfiguration „Electrip“.
- Beim Start ist die Konfiguration `-f`/`--file` geöffnet (B-24), sonst die erste nach Namen.
- Der Steuerkanal ist TCP. Er lauscht auf allen Netzwerkschnittstellen, damit andere Instanzen sich mit dem Sitzungs-Host verbinden können (ADR 0010: dem lokalen Netz wird vertraut).
- `--host`: Die Instanz ist Client des Sitzungs-Hosts an dieser Adresse (N-03; ohne Port gilt 4711; erreichbar heißt: er schickt binnen 2 s `hello`). Sie hat dann keinen eigenen Host: Ihr Steuerkanal reicht jede Verbindung an den Host weiter; ihre Gamepads schicken ihre Befehle dorthin, mit einem zufälligen Versatz in der Geräte-`id`, damit sich die Geräte verschiedener Instanzen nicht überschneiden.
  Ist der Host beim Start nicht erreichbar, meldet die App `ERROR cannot reach the host …` und ist selbst Host. Bis Q-016 beantwortet ist, nutzt ein Client die Konfiguration des Hosts.
- Ohne `--host` sucht die Instanz beim Start ca. 2 s per mDNS (`_electrip._tcp`) nach dem Host ihrer Zentrale und ist dann dessen Client; findet sie keinen, ist sie selbst Host (N-03, ADR 0010).
  Jede Instanz veröffentlicht als TXT-Einträge `id` (Instanz-ID, 16 Hex-Ziffern; beim ersten Start zufällig gewählt und in der Bibliothek unter `instance` gespeichert, N-05), `version` (wie in `hello`), `station` (Zentralen-ID: aufgelöste IP, Port und Bus der Zentrale; eine Zentrale auf `localhost` bekommt die LAN-Adresse des Rechners) und `status` (`searching`, `host` oder `client`); der Port ist der des Steuerkanals.
  Gibt es zwei Hosts derselben Zentrale, verbindet sie sich mit dem mit der kleineren `id`. Starten mehrere Instanzen gleichzeitig, wird von den suchenden die mit der kleinsten `id` Host; die anderen warten bis zu 4 s weiter auf sie.
  Ist mDNS nicht verfügbar, meldet die App `ERROR no discovery: …` und ist selbst Host. Vor der Suche schickt sie einen leeren mDNS-Kopf (12 Null-Bytes) an `224.0.0.251:5353`; scheitert das, fehlt der Zugriff auf das lokale Netzwerk (macOS ohne Berechtigung, Container) und der Grund steht in `hello` unter `alone`. `--no-discovery` schaltet die Suche ab; die Tests starten die App so.
- Host-Ausfall (N-03): Schließt der Host die Verbindung oder schickt er 3 s lang nichts, ist er weg; die Instanz meldet `ERROR the host … is gone: …` und schließt die weitergereichten Verbindungen.
  Mit Discovery sucht sie wie beim Start nach dem nächsten Host ihrer Zentrale (ohne den weggefallenen) und reicht dann dorthin weiter. Ohne Discovery (`--host`, `--no-discovery`) oder wenn keiner da ist, wird sie selbst Host: Sie öffnet ihre Konfiguration, verbindet sich mit der Zentrale, ohne den Gleisstrom zu schalten, liest Gleisstrom und Zustand der Loks zurück und kennt ihre angeschlossenen Gamepads. Ihr Steuerkanal bleibt auf demselben Port und reicht neue Verbindungen an den eigenen Host weiter.
  Das Fenster verbindet sich bis zu 15 s lang neu, statt sich zu schließen.
- Doppel-Host (N-03): Ein Host prüft alle 2 s, ob mDNS einen erreichbaren Host derselben Zentrale mit kleinerer `id` zeigt (z. B. nachdem ein getrenntes Netz wieder verbunden ist). Dann meldet er `ERROR this instance hands over to the host …`, schließt alle Verbindungen seines Steuerkanals und wird Client des anderen Hosts; seine Gamepads meldet er dort an. Die Clients des abgebenden Hosts finden den verbleibenden wie beim Host-Ausfall.
- Host-Adresse von Hand (N-03, Rückfall ohne mDNS): Auf `join_host` prüft der Host die Adresse (ohne Port gilt 4711): Er verbindet sich und liest `hello`; trägt es seine eigene `id`, ist es er selbst oder einer seiner Clients, und er bleibt Host. Sonst antwortet er mit `ok`, meldet `ERROR this instance hands over to the host …` und wird wie beim Doppel-Host Client des anderen Hosts. Das Fenster hat dafür neben den Ansichtsoptionen ein Feld „Host-Adresse“ mit „Beitreten“ und zeigt über dem Nothalt den Fehler seines letzten Befehls.
  Ist die Instanz selbst Client, beantwortet ihr Steuerkanal `join_host` selbst: Trägt das `hello` an der Adresse die `id` ihres Hosts, bleibt alles, wie es ist. Sonst antwortet sie mit `ok`, schließt die Verbindungen ihres Steuerkanals, meldet `ERROR this instance joins the host …` und wird Client des anderen Hosts; ihr bisheriger Host bleibt Host.
- Gemeinsame Konfigurationen (N-04): Jede Instanz mit Discovery gleicht alle 5 s ihre Konfigurationen mit allen Instanzen ab, die mDNS zeigt, egal welche Zentrale sie haben. Sie fragt mit `configuration_ids` die IDs beider Hosts ab (über den eigenen Steuerkanal und den der anderen Instanz) und führt die Dokumente jeder gemeinsamen ID mit `sync_configuration` zusammen: erst das eigene holen, beim anderen einführen, das Ergebnis beim eigenen einführen. Danach haben beide Bibliotheken die Änderungen beider. Die Lokbilder und Sounds, die eine Seite danach unter `missing` nennt, holt sie mit `file` von der anderen und legt sie mit `add_file` ab. Gleich behandelt werden nur Konfigurationen mit derselben `id`, also Kopien derselben Datei; nach dem ersten Abgleich werden getrennte Änderungen feldweise zusammengeführt.
  Scheitert der Abgleich, meldet die App `ERROR cannot share configurations with …`.
- Trennt sich ein Client, entfernt der Host die Eingabegeräte, die dieser Client angeschlossen hat (`add_device`); ihre Loks behalten ihre Geschwindigkeit wie bei `remove_device`. Hat der Client mit `offer_audio` Sounds angeboten, entfernt der Host auch dieses Audio-Ziel.
- Audio-Ziel auf einer anderen Instanz (N-05): Eine Instanz, die Client ist, schickt ihrem Host nach dem Verbinden `offer_audio` mit ihrer Instanz-ID und ihren Ausgabegeräten. Der Host schickt ihr dann über dieselbe Verbindung die Audio-Ereignisse (`audio`) aller Loks, deren `audio_instance` diese ID ist; sie spielt sie mit den Sounds ihrer eigenen Bibliothek. Ist die Instanz nicht verbunden, spielt der Host die Sounds der Lok selbst auf seinem Standardgerät und meldet einmal `ERROR the instance … is not connected, the host plays the sounds of loco …`; bricht die Verbindung ab, meldet er `ERROR the instance … is gone, the host plays its sounds`. Wechselt eine Lok die Instanz, verstummen ihre Sounds auf der alten.
- Gäste (N-03, Q-016): Ein Client mit einer anderen Konfiguration schickt sie mit `use_configuration`. Der Host hält sie als eigene Sitzung (Gast), führt die Befehle dieser Verbindung dort aus und schickt ihr deren Zustand, darin `station`, `audio_devices`, `audio_targets`, `audio_latency` und `audio_conflicts` des Hosts; andere Verbindungen bekommen weiter seinen eigenen. Die Loks eines Gasts haben IDs nach denen des Hosts; Loks mit derselben Adresse teilen den Fahrzustand. Ein Gast fährt nur; Befehle, die seine Konfiguration ändern, beantwortet der Host mit `change this configuration on the instance that opened it`. Schicken mehrere Clients dieselbe Konfiguration (`id`), gilt die zuerst geschickte; der Host entfernt den Gast, wenn sich der letzte dieser Clients trennt. Ist es die Konfiguration, die der Host selbst offen hat, bleibt die Verbindung beim Host. Eingabegeräte, die die Verbindung vorher angeschlossen hat, entfernt der Host dabei; eine ungültige Konfiguration beantwortet er mit `invalid configuration: …` und ändert nichts. Eine Instanz, die Client ist, schickt auf jeder weitergeleiteten Verbindung und auf der ihrer Eingabegeräte selbst `use_configuration` mit der Konfiguration, die sie als Host öffnen würde (`--file`, sonst die erste der Bibliothek), sofern diese Loks hat; der Client am Steuerkanal der Instanz bekommt dann nach `hello` gleich den Zustand des Gasts, ohne die Antwort darauf.
- Die erste Zeile auf der Standardausgabe endet mit der Adresse: `… control channel on 127.0.0.1:4711`.
- Jede Nachricht ist ein JSON-Objekt in einer Zeile (UTF-8, Zeilenende `\n`), in beide Richtungen.

## Nachrichten der App

Jede Nachricht hat ein Feld `type`.

| `type` | Felder | Wann |
|---|---|---|
| `hello` | `version` (Zahl, derzeit `1`); `id` (Instanz-ID des Hosts, 16 Hex-Ziffern, für `join_host`); `alone` (Text, nur wenn die Discovery gescheitert ist: warum andere Instanzen diese nicht finden, N-03) | als erste Nachricht nach dem Verbinden |
| `state` | `state` (Zustand, siehe unten) | nach `hello` und an **alle** Clients nach jedem erfolgreichen Befehl, außerdem alle 50 ms, solange sich der Zustand ändert (z. B. beim Beschleunigen), und sonst mindestens jede Sekunde als Lebenszeichen (N-03) |
| `reply` | `ok` (bool), bei Fehler `error` (Text) | an den Absender, auf jeden Befehl genau eine, vor der folgenden `state` |
| `audio` | `audio`: ein Audio-Ereignis mit `event` und Feldern: `queue` (`channel`, `sound`), `play` (`channel`, `sound`, `delay`), `stop` (`channel`), `fade_in` (`channel`, `sound`, `fade`), `fade_out` (`channel`, `fade`), `route` (`loco`, `device`). `channel` ist `{"loco": …, "nr": …}`, `sound` ein Pfad wie in der Konfiguration (z. B. `sounds/<SHA-256>.ogg`), `delay` und `fade` sind `{"secs": …, "nanos": …}` | nur an Clients nach `offer_audio`, für die Loks, die ihre Instanz nennen (N-05) |
| `ping` | – | nur an Clients nach `offer_audio`: gleich nach dem Angebot, dann frühestens eine Sekunde nach jedem `pong`; der Client antwortet mit `pong` (N-05) |

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
    "sound_model": null,
    "picture": null,
    "audio_instance": null,
    "audio_device": null,
    "speed": 0.0,
    "forward": true
  }],
  "actions": [{"id": 1, "name": "Licht"}],
  "mappings": [{"kind": "Xbox Series X Controller", "bindings": [{"control": "lefty", "target": {"type": "drive", "dead_zone": 0.06}}]}],
  "devices": [{"id": 1, "kind": "Xbox Series X Controller", "loco": 1, "number": 1, "focus": false}],
  "station": {"kind": "srcp", "host": "localhost", "port": 4303, "bus": 1, "power_on_start": true, "connected": false, "track_power": false},
  "view": {"auto_focus": true, "only_active": false},
  "import_report": [],
  "configuration": "Electrip",
  "configurations": ["Electrip"],
  "audio_devices": ["MacBook Pro-Lautsprecher", "USB Audio"],
  "audio_targets": {"3f2a9c0d1b4e5a67": ["Pi-Kopfhörer"]},
  "audio_latency": {"3f2a9c0d1b4e5a67": 42},
  "audio_conflicts": []
}
```

- `locos` steht in der Reihenfolge der Lokliste (B-04); eine `id` wird nie wiederverwendet, auch nicht nach dem Löschen.
- `name`: neue Loks heißen „Unbenannte Lok“ (B-04).
- `protocol`: `motorola1`, `motorola2`, `dcc_short`, `dcc_long` (B-06).
- `speed_curve`: Kontrollpunkte `[km/h, Fahrstufe]` (B-08).
- `accel_duration`, `brake_duration`: Sekunden von 0 auf Vmax bei voller Beschleunigung bzw. von Vmax auf 0 bei voller Bremsung, 1–9999 s; `volume`: Lautstärke von 0 (stumm) bis 1 (B-05).
- `functions`: Decoder-Funktionen der Lok in der vom Nutzer sortierten Reihenfolge (B-07): logische Aktion `action`, Funktionsnummer `number` (F0–F28), `name`, `mode` (`switch` Umschalter: erste Auslösung an, zweite aus; `push` Taster: an, solange gehalten), `default_on` (Standardzustand „An“ kehrt beide Modi um) und `on` (ob die Funktion gerade an ist; die Zentrale bekommt alle Funktionen, die an sind).
- `sound_functions`: Geräusch-Funktionen der Lok in der vom Nutzer sortierten Reihenfolge (B-16): logische Aktion `action`, `name`, Sounddatei `path` auf dem Host (oder `null`; ein Sound in der Bibliothek steht als `sounds/<SHA-256>.<Endung>` relativ zu ihr), `mode` (`switch` Umschalter: Loop bis zur zweiten Auslösung; `push_once` Taster einmal: höchstens einmal, Abbruch beim Loslassen; `push` Taster wiederholt: Loop, solange gehalten; `tap` Anschalter: bis Dateiende, Auslösungen dazwischen tun nichts) und `on` (ob sie gerade an ist; zu Beginn aus, ein Anschalter geht am Dateiende aus).
- `event_sounds`: Geräusch-Ereignisse der Lok (B-17): logische Aktion `action` (jedes Drücken schaltet aktiv/inaktiv), `name`, Sounddatei `path` auf dem Host (oder `null`; ein Sound in der Bibliothek steht als `sounds/<SHA-256>.<Endung>` relativ zu ihr), `default_active` (aktiv zu Beginn, Standard `true`; wird gespeichert), `active` (ob es gerade aktiv ist), `forward` (`true` nur vorwärts, `false` nur rückwärts, `null` beliebig), `min_speed`/`max_speed` in km/h, `min_accel`/`max_accel` in km/h pro Sekunde (`null` = keine Grenze), `fade_in`/`fade_out` in Sekunden und `play_to_end` (einmal gestartet bis zum Ende, ohne Ausblenden).
  Es spielt nur, wenn die Lok ein Sound-Modell hat, und läuft im Loop, solange alle Bedingungen gelten; gelten sie nicht mehr, blendet es aus. Der Host prüft bei jeder Abfrage (50 ms); die Beschleunigung ist die Änderung der Geschwindigkeit seit der letzten Abfrage.
- `sound_model`: Sound-Modell der Lok (B-11, B-14, B-15) oder `null` („Kein Geräusch“). `engine`: `diesel` (Verbrennungsmotor, auch für E-Loks) oder `steam`; `sounds`: Sounddateien auf dem Host je Motorgeräusch `start`, `idle`, `quit` (Diesel) bzw. `idle`, `cylinder` (Dampf); `segments`: Geräuschsegmente nach Geschwindigkeit sortiert, je mit `start` (km/h, ab hier gilt das Segment bis zum nächsten, das letzte bis Vmax; das erste beginnt bei 0), `sounds` je `load`, `idle`, `accel`, `decel` (Diesel) und `strokes` (Dampf: Sounddatei je Taktnummer ab 0); `steam`: `strokes` (Takte je Radumdrehung, 1–9999, Standard 4), `wheel_diameter` (m, 0,1–99, Standard 1,2), `start_delay` (s vom Zylinderdampf bis zum ersten Takt, 0–9999, Standard 2), `min_frequency` (Takte je Sekunde mindestens, 0,1–9999, Standard 0,2). Ändert sich Vmax, wandern die Grenzen der Segmente mit.
- `picture`: Name des Lokbilds (B-05) oder `null`. Die Datei `media/<picture>.png` in der Bibliothek ist der gespeicherte Ausschnitt in 440×340 px; der Name ist ihr SHA-256, so liegt jedes Bild nur einmal dort.
- `audio_instance`: Instanz-ID der Instanz, die die Sounds der Lok spielt (N-05), eine aus `audio_targets`, oder `null` für den Host; wird gespeichert.
- `audio_device`: Ausgabegerät dieser Instanz, auf dem die Sounds der Lok spielen (N-05), beim Host ein Name aus `audio_devices`, sonst aus `audio_targets`, oder `null` für das Standardgerät; wird gespeichert. Kann der Host das Gerät nicht öffnen, meldet er `ERROR cannot open the output device …` (einmal) und spielt auf dem Standardgerät. Wechselt eine Lok das Gerät, verstummen ihre laufenden Sounds; die nächsten spielen auf dem neuen.
- `actions`: logische Aktionen der Konfiguration (N-07); eine `id` wird nie wiederverwendet.
- `mappings`: je Gerätetyp `kind` die Belegung seiner Bedienelemente (N-01, B-02, ADR 0009).
  `control` heißt wie in SDL, z. B. `a`, `lefty`, `dpleft`; Joysticks ohne Gamepad-Belegung z. B. `button0`, `axis1`, `hat0_left`.
  `target` ist ein Objekt mit `type`: `drive` (Fahrachse, `dead_zone` Totzone, Standard 0,06), `reverse`, `toggle_power` (Nothalt der Anlage), `emergency_stop` (Lok-Nothalt), `previous_loco`, `next_loco` (Lokwechsel zur nächsten Lok in der Liste, die kein anderes Gerät steuert, wie Electrip 1), `focus` (Lok des Geräts zeigen, solange gehalten), `toggle_sound` (Fahrgeräusch an/aus) oder `action` mit `action` (logische Aktion).
  Ein neuer Gerätetyp bekommt das Standard-Mapping nach Electrip 1: `lefty` fährt, `a` Nothalt der Anlage, `b` Richtungswender, `dpleft`/`dpright` Lokwechsel.
- `devices`: angeschlossene Eingabegeräte, auch virtuelle über den Steuerkanal; `loco` ist die Lok, die das Gerät steuert (`null`, wenn keine frei ist).
  Ein neues Gerät steuert die erste Lok, die kein anderes Gerät steuert; wird seine Lok gelöscht oder kommt eine Lok dazu, bekommt ein Gerät ohne Lok die erste freie.
  `focus`: ob das Gerät gerade „Fokus“ hält (B-22).
  `number` ist die Nummer des Geräts (ab 1, ohne Obergrenze); ein neues Gerät bekommt die kleinste, die kein angeschlossenes Gerät hat. Die Oberfläche macht daraus eine Farbe der Palette: Nummer n bekommt Farbe `(n - 1) mod 8` (B-03).
- `speed`: Geschwindigkeit in km/h, `forward`: Fahrtrichtung (B-10).
  Die Zentrale bekommt die Fahrstufe aus der Kennlinie, abgeschnitten wie in Electrip 1.
- `sound`: Fahrgeräusch `off`, `starting`, `on` oder `stopping` (B-11, B-12). Beim Diesel spielt `starting` das Anlassgeräusch bis zum Leerlauf; `stopping` wartet auf das Ende des Leerlaufgeräuschs und spielt das Abstellgeräusch. Währenddessen bleibt die Geschwindigkeit stehen, auch bei ausgelenkter Fahrachse; die Dauer kommt aus der Länge der Dateien.
- `station`: Zentrale (`kind`: `srcp` oder `z21`; Vorgabe wie Electrip 1: SRCP-Server `localhost`, Port 4303, Bus 1) und ob die App mit ihr verbunden ist (B-01, N-02).
  Bricht die Verbindung ab, geht an alle Clients ein Zustand mit `connected: false`.
- `power_on_start`: ob `connect` den Gleisstrom einschaltet (Vorgabe an, B-23); `track_power`: Gleisstrom, wie ihn die Zentrale zuletzt gemeldet hat, ohne Verbindung `false`.
  Schaltet eine andere Instanz an derselben Zentrale den Gleisstrom, folgt `track_power` (B-23).
- `view`: Optionen der Steuerungsansicht (B-22), gespeichert mit der Konfiguration. `auto_focus` (Standard an; beim Import aus Electrip 1 `use_auto_focus`): Wechselt ein Gerät die Lok, holt das Fenster die neue Lok in den sichtbaren Bereich. `only_active`: Das Fenster zeigt nur Loks, die ein Gerät steuert oder die fahren.
  Hält ein Gerät „Fokus“ (`focus` in `devices`), zeigt das Fenster dessen Lok.
- `configuration`: Name der geöffneten Konfiguration; `configurations`: alle Konfigurationen der Bibliothek, sortiert (B-21).
  Jede Änderung an Loks, Aktionen, Mappings und Server wird sofort in die Datei der geöffneten Konfiguration geschrieben, Funktionen in ihrem Standardzustand; Fahrzustand und Geräte werden nicht gespeichert.
- `audio_devices`: Namen der Ausgabegeräte des Hosts, gelesen beim Start des Hosts (N-05).
- `audio_targets`: die Instanzen, die mit `offer_audio` Sounds angeboten haben und verbunden sind, je Instanz-ID die Namen ihrer Ausgabegeräte (N-05).
- `audio_latency`: je Instanz aus `audio_targets` die zuletzt gemessene Zeit in Millisekunden von `ping` bis `pong`, sobald gemessen (N-05). Das ist der Weg eines Fahrbefehls vom Gamepad dieser Instanz zum Host und des Audio-Ereignisses zurück; nicht enthalten sind bis zu 50 ms bis zum nächsten Takt des Hosts und der Puffer des Ausgabegeräts. Das Fenster zeigt den Wert bei der Tonausgabe und über 300 ms rot mit „zu langsam“.
- `audio_conflicts`: die Adressen, deren Loks über alle Sitzungen des Hosts (seine und die der Gäste) auf verschiedenen Audio-Zielen spielen, sortiert (N-05). Beide Ziele bekommen die Audio-Ereignisse; das Fenster warnt mit einem roten „!“ auf dem Lokbild und im Lok-Dialog bei der Tonausgabe. Der Host prüft das bei jedem Takt.
- `import_report`: Was der letzte Import aus Electrip 1 angepasst hat, eine Zeile je Änderung, z. B. Loks mit N 1 und Adresse über 127, die auf DCC lang umgestellt wurden (B-06).

## Befehle

Ein Befehl ist ein Objekt mit dem Feld `command` und seinen Parametern; `loco` ist die `id` der Lok.

Sounddateien, die `set_engine_sound`, `set_segment_sound`, `set_stroke_sound`, `add_sound_function` und `add_event_sound` setzen, kopiert der Host nach `sounds/` in die Bibliothek (Name nach Inhalt), damit andere Instanzen sie bekommen (N-04); eine Datei, die er nicht lesen kann, bleibt mit ihrem Pfad stehen und wird beim Spielen weggelassen.

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
| `set_audio_device` | `loco`, optional `instance` (Instanz-ID aus `audio_targets`, ohne oder `null` der Host), `device` (Name eines Ausgabegeräts dieser Instanz oder `null` für das Standardgerät) | N-05 |
| `set_picture` | `loco`, `path` (PNG oder JPEG auf dem Rechner der App), optional `crop` (Ausschnitt in Pixeln des Bildes: `x`, `y` linke obere Ecke, `width` Breite; die Höhe folgt aus dem Seitenverhältnis 22:17. Verschieben ändert `x`/`y`, Zoomen `width`. Standard: der größte Ausschnitt in der Mitte); speichert den Ausschnitt als Lokbild in 440×340 px | B-05 |
| `add_curve_point` | `loco`, `speed`, `step` | B-08 |
| `remove_curve_point` | `loco`, `point` (Nummer ab 0) | B-08 |
| `move_curve_point` | `loco`, `point`, `speed`, `step` | B-08 |
| `set_axis` | `loco`, `deflection` (Auslenkung der Fahrachse von -1 voll zurück bis 1 voll vor; bis 0,06 wird sie ignoriert wie in Electrip 1) | B-10 |
| `reverse` | `loco` (Richtungswender: Geschwindigkeit 0, dann andere Richtung) | B-10 |
| `set_engine` | `loco`, `engine` (`diesel`, `steam` oder `null`), `confirmed`; setzt ein neues Sound-Modell mit einem Segment bzw. entfernt es. Ein vorhandenes Sound-Modell wird nur mit `confirmed: true` ersetzt, sonst Fehler; dieselbe Motorart tut nichts | B-15 |
| `insert_segment` | `loco`, `segment` (Nummer ab 0); teilt das Segment in der Mitte wie Electrip 1, das neue ist die rechte Hälfte | B-15 |
| `remove_segment` | `loco`, `segment`, `confirmed`; der linke Nachbar (beim ersten der rechte) übernimmt seine Geschwindigkeiten. Das einzige Segment entfernt das ganze Sound-Modell und braucht `confirmed: true` | B-15 |
| `move_segment_border` | `loco`, `segment`, `speed` (km/h, wo das Segment beginnt); nur zwischen den Nachbargrenzen, sonst und beim ersten Segment ignoriert wie bei der Kennlinie | B-15 |
| `set_engine_sound` | `loco`, `sound` (`start`, `idle`, `quit`, `cylinder`), `path` (Sounddatei auf dem Host oder `null` zum Entfernen) | B-11, B-12, B-14 |
| `set_segment_sound` | `loco`, `segment`, `sound` (`load`, `idle`, `accel`, `decel`), `path` (oder `null`) | B-11, B-15 |
| `set_stroke_sound` | `loco`, `segment`, `stroke` (Taktnummer ab 0, kleiner als `steam.strokes`), `path` (oder `null`) | B-14 |
| `set_steam` | `loco`, `steam` (Objekt wie im Zustand, alle vier Felder); ein Wert außerhalb seines Bereichs ist ein Fehler und ändert nichts | B-14 |
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
| `add_device` | `device` (frei gewählte `id`), `kind` (Gerätetyp); schließt ein (virtuelles) Eingabegerät an; keine Obergrenze | N-01, B-03 |
| `remove_device` | `device`; die Achse seiner Lok wird losgelassen, die Lok behält ihre Geschwindigkeit | N-01 |
| `bind` | `kind`, `control`, `target` (siehe `mappings`); ersetzt die bisherige Belegung des Bedienelements | N-01, B-02 |
| `unbind` | `kind`, `control` | N-01, B-02 |
| `input` | `device`, `control`, `value` (Knöpfe und Hat-Richtungen `1` gedrückt, `0` losgelassen; Achsen -1 bis 1, nach oben negativ wie in SDL); wirkt über das Mapping auf die Lok des Geräts, ein unbelegtes Bedienelement tut nichts | N-01, B-02 |
| `set_server` | `kind` (`srcp` oder `z21`, Vorgabe `srcp`; der Z21-Treiber ist experimentell), `host`, `port` (srcpd 4303, Z21 21105), `bus` (nur SRCP; nur ohne Verbindung) | B-01, N-02 |
| `connect` | – (verbindet mit dem eingestellten Server; ein Fehler nennt die Ursache) | B-01 |
| `disconnect` | – | B-01 |
| `set_power_on_start` | `on` | B-23 |
| `set_view` | `view` (Objekt wie im Zustand, beide Felder) | B-22 |
| `toggle_power` | – (Nothalt der Anlage: Gleisstrom aus, beim nächsten Mal wieder an; nur mit Verbindung) | B-23 |
| `emergency_stop` | `loco` (Lok-Nothalt: nur diese Lok hält sofort, die Achse wird losgelassen; der Gleisstrom bleibt an) | B-23 |
| `new_configuration` | `name` (legt eine leere Konfiguration an und öffnet sie; nur ohne Verbindung) | B-21 |
| `open_configuration` | `name` (nur ohne Verbindung; Loks bekommen neue `id`s, Geräte behalten ihre Lok, wenn sie können) | B-21 |
| `rename_configuration` | `name` (neuer Name der geöffneten Konfiguration) | B-21 |
| `remove_configuration` | `name` (löscht eine andere als die geöffnete Konfiguration) | B-21 |
| `export_configuration` | `path` (schreibt die geöffnete Konfiguration in eine Datei auf dem Rechner der App) | B-21 |
| `import_electrip1` | `path` (Konfigurationsdatei von Electrip 1 auf dem Rechner der App; wird eine neue Konfiguration mit dem Dateinamen ohne Endung und geöffnet, nur ohne Verbindung; ein Fehler nennt die Ursache und ändert nichts). Übernommen wird bisher, was Electrip 2 kennt: Name, Decoder, Vmax, Kennlinie, Dauern, Lautstärke, Lokbild (mittig zugeschnitten; ein relativer Pfad gilt ab dem Ordner der Datei, ein fehlendes Bild steht im `import_report`), Server. Fehlende Werte bekommen die Vorgaben von Electrip 1. | B-21, B-06 |
| `join_host` | `address` (`host:port` oder nur `host`, dann Port 4711); die Instanz wird Client des Hosts an der Adresse; nach `ok` schließt sie alle Verbindungen. Ein Fehler (nicht erreichbar, die Instanz selbst) ändert nichts | N-03 |
| `use_configuration` | `configuration` (eine Konfiguration wie in der Bibliothek, mit `id`); der Absender fährt ab jetzt als Gast mit ihr (siehe oben) | N-03 |
| `offer_audio` | `instance` (Instanz-ID), `devices` (Namen der Ausgabegeräte); der Host schickt dem Absender ab jetzt die Audio-Ereignisse der Loks, die diese Instanz nennen, bis er sich trennt. Ein Client schickt das selbst | N-05 |
| `pong` | – ; Antwort auf `ping`, ohne `reply`. Ein Client schickt das selbst | N-05 |
| `configuration_ids` | – ; die Antwort trägt zusätzlich `ids`: die IDs aller Konfigurationen der Bibliothek des Hosts | N-04 |
| `sync_configuration` | `id` (ID einer Konfiguration), optional `document` (Automerge-Dokument der Konfiguration als Hex); führt das Dokument in die Konfiguration mit der ID ein, ist es die geöffnete, übernimmt der Host sie, ohne dass die Loks anhalten. Die Antwort trägt zusätzlich `document`: das Dokument der Konfiguration nach dem Zusammenführen, und `missing`: die Pfade der Lokbilder und Sounds aus der Bibliothek, die die Konfiguration nutzt und die dort fehlen (z. B. `media/<SHA-256>.png`, `sounds/<SHA-256>.ogg`). Eine unbekannte ID ist ein Fehler | N-04 |
| `file` | `path` (Pfad eines Lokbilds oder Sounds in der Bibliothek wie unter `missing`); die Antwort trägt zusätzlich `content`: die Datei als Hex. Eine fehlende Datei oder ein anderer Pfad ist ein Fehler | N-04 |
| `add_file` | `path` (wie bei `file`), `content` (Datei als Hex); legt die Datei unter dem Pfad in der Bibliothek ab. Passt der SHA-256 im Pfad nicht zum Inhalt, ist das ein Fehler | N-04 |
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

Noch nicht enthalten: Screenshots über den Steuerkanal; die Tests der Oberfläche zeichnen das Fenster ohne Anzeige (`crates/ui`) und legen das Bild unter `target/test-logs/screenshots/` ab.
