# Hardware-Checkliste

Agenten bereiten hier Hardware-Tests (`hw: true`) vor; Mo führt sie durch und trägt das Ergebnis ein.

## N-02 – srcpd-Treiber an echter Zentrale

Vorbereitung: srcpd mit echtem Bus (z. B. ddl), eine DCC- und eine Motorola-Lok auf dem Gleis.
Die Szenario-Tests laufen bisher nur gegen den Loopback-Bus (`cargo xtask sim up`).

- [ ] Verbinden mit Host, Port und Bus der echten Zentrale gelingt; ein falscher Bus wird gemeldet.
- [ ] Gleisstrom aus und wieder an.
- [ ] DCC-Lok (kurze und lange Adresse) fährt vorwärts und rückwärts mit der gesetzten Fahrstufe.
- [ ] Motorola-2-Lok fährt; `INIT … M 2 14 5` wird von srcpd angenommen.
- [ ] F0–F28 schalten bei der DCC-Lok; F0–F4 bei der Motorola-Lok.
- [ ] Lok-Nothalt hält die Lok sofort an, der Gleisstrom bleibt an.
- [ ] Eine Änderung aus einem anderen SRCP-Programm kommt als Ereignis an.

Ergebnis: _offen_

## N-02 – Z21-Treiber an echter Z21 (experimentell)

Vorbereitung: Roco Z21 (Firmware 1.43) im Netz, eine DCC- und eine Motorola-Lok auf dem Gleis, die Z21-App auf einem Handy als zweites Programm.
`electrip` wird über den Steuerkanal bedient: `set_server` mit `kind: z21`, IP der Z21, Port 21105, dann `connect`.
Der Treiber wurde nach dem Bau gegen das PDF der Spezifikation geprüft (2026-11-05); die Szenario-Tests laufen nur gegen den Simulator.

- [ ] Verbinden gelingt, `track_power` zeigt den Gleisstrom der Z21; eine falsche IP ergibt „no Z21 answers on …“.
- [ ] Gleisstrom aus und wieder an; die Stopp-Taste an der Z21 und in der Z21-App kommt als `track_power: false` an.
- [ ] DCC-Lok mit kurzer und langer Adresse (ab 128) fährt vorwärts und rückwärts mit 14, 28 und 128 Fahrstufen.
- [ ] Motorola-Lok fährt (`LAN_SET_LOCOMODE` setzt MM); MM I mit 14, MM II mit 14 und MM II mit 28 Fahrstufen (der Treiber skaliert die Stufe auf die DCC-Stufen des Formats; volle Fahrt und halbe Fahrt prüfen).
- [ ] F0–F28 schalten bei der DCC-Lok; F0–F4 bei der Motorola-Lok.
- [ ] Lok-Nothalt hält die Lok sofort an, der Gleisstrom bleibt an.
- [ ] Eine Fahrt oder Funktion aus der Z21-App kommt als Ereignis an (mit einem zweiten Electrip als Beobachter oder im Log).
- [ ] Nach zwei Minuten ohne Bedienung ist Electrip noch angemeldet (Keepalive alle 20 s); Netzwerkkabel ziehen: nach etwa 70 s `connected: false`.

Ergebnis: _offen_

## B-01 – Verbindung zum SRCP-Server

Vorbereitung: srcpd auf einem anderen Rechner im Netz (z. B. Raspberry Pi) mit echtem Bus; `electrip` läuft und wird über den Steuerkanal bedient (`spec/steuerkanal.md`).

- [ ] `set_server` mit Host/IP des srcpd-Rechners, Port 4303 und Bus, dann `connect`: Zustand zeigt `connected: true`.
- [ ] Falscher Host und falscher Bus ergeben eine verständliche Fehlermeldung.
- [ ] srcpd beenden oder Netzwerkkabel ziehen: Zustand wechselt auf `connected: false` (bei gezogenem Kabel ggf. erst, wenn das Betriebssystem den Abbruch meldet).
- [ ] srcpd wieder starten, `connect` ohne Neustart von Electrip gelingt.

Ergebnis: _offen_

## B-10 – Fahren mit der Achse (über den Steuerkanal, noch ohne Gamepad)

Vorbereitung: wie B-01 verbunden, eine DCC-Lok mit 128 Fahrstufen angelegt (`add_loco`, `set_address`), Beschleunigungs- und Bremsdauer z. B. 10 s.

- [ ] `set_axis` mit `deflection: 1`: die Lok fährt gleichmäßig an und erreicht nach etwa 10 s die Höchstgeschwindigkeit.
- [ ] `set_axis` mit `deflection: 0`: die Lok hält ihre Geschwindigkeit.
- [ ] `set_axis` mit `deflection: -1`: die Lok bremst in etwa 10 s bis zum Stillstand.
- [ ] `reverse` während der Fahrt: die Lok hält sofort an, nach erneutem `set_axis` fährt sie in die andere Richtung.

Ergebnis: _offen_

## B-23 – Gleisstrom und Nothalt (über den Steuerkanal, noch ohne Gamepad)

Vorbereitung: wie B-10 verbunden, eine Lok fährt.

- [ ] `connect` schaltet den Gleisstrom ein (`track_power: true`); nach `set_power_on_start` mit `on: false` bleibt er beim nächsten `connect` aus.
- [ ] `toggle_power`: der Gleisstrom geht aus, alle Loks halten; erneut `toggle_power`: er geht wieder an.
- [ ] Gleisstrom an der Zentrale selbst ausschalten (Stopp-Taste): der Zustand zeigt sofort `track_power: false`.
- [ ] Eine zweite Instanz an derselben Zentrale zeigt jeden Wechsel des Gleisstroms.
- [ ] `emergency_stop` für die fahrende Lok: nur sie hält sofort an, andere Loks fahren weiter, der Gleisstrom bleibt an.

Ergebnis: _offen_

## B-07 – Lokfunktionen über logische Aktionen (über den Steuerkanal, noch ohne Gamepad)

Vorbereitung: wie B-10 verbunden, eine DCC-Lok mit Licht auf F0 und einer weiteren Funktion (z. B. Horn auf F2) angelegt, `add_action` „Licht“ (1) und „Horn“ (2).

- [ ] `add_function` mit Aktion 1, F0, `mode: switch`; `trigger_action` gedrückt und losgelassen: das Licht geht an und bleibt an; beim zweiten Mal geht es aus.
- [ ] `add_function` mit Aktion 2, F2, `mode: push`: die Funktion läuft nur, solange `pressed: true` gilt; nach `pressed: false` hört sie auf.
- [ ] Eine Funktion mit `default_on: true` ist nach `add_function` sofort an und wird durch die Aktion ausgeschaltet.
- [ ] Eine zweite Lok bildet Aktion 1 auf eine andere Funktionsnummer ab: `trigger_action` für diese Lok schaltet nur deren Funktion, die erste Lok bleibt unverändert.
- [ ] Beim Fahren mit `set_axis` bleiben eingeschaltete Funktionen an.

Ergebnis: _offen_

## B-13 – Anfahren synchron zum Sound (braucht die Soundausgabe aus B-18)

Vorbereitung: wie B-10 verbunden, eine Diesellok mit Geräuschen (z. B. aus einem Lok-Paket des Korpus importiert), Fahrgeräusch an (`toggle_sound`) und der Leerlauf erreicht.

- [ ] `set_axis` mit `deflection: 1`: die Lok steht, bis das Beschleunigungsgeräusch in Segment 1 hörbar beginnt, und fährt genau dann los.
- [ ] Bremsen bis zum Stillstand (`deflection: -1`): die Lok rollt mit kleiner Fahrstufe weiter, bis das Bremsgeräusch in den Leerlauf beginnt, und hält genau dann.
- [ ] Fahrgeräusch aus: die Lok fährt und hält wieder sofort mit der Achse.

Ergebnis: _offen_

## B-14 – Fahrgeräusch Dampf (braucht die Soundausgabe aus B-18)

Vorbereitung: wie B-10 verbunden, eine Dampflok mit Geräuschen (z. B. BR 81 aus einem Lok-Paket des Korpus importiert).

- [ ] Fahrgeräusch an (`toggle_sound`) im Stand: das Leerlaufgeräusch läuft ohne Lücke in Schleife, keine Takte.
- [ ] Anfahren mit kleiner Auslenkung: zuerst ist der Zylinderdampf zu hören, die ersten Takte folgen nach der Verzögerung (Standard 2 s); bei sehr kleiner Geschwindigkeit kommen die Takte höchstens im Abstand der minimalen Taktfrequenz (Standard 0,2 Hz = 5 s).
- [ ] Beschleunigen bis Vmax: die Takte werden gleichmäßig schneller, auch über den Abfragetakt von 50 ms hinaus ohne Stolpern; an Segmentgrenzen wechseln die Taktgeräusche.
- [ ] `set_steam` mit größerem Raddurchmesser oder weniger Takten pro Umdrehung: bei gleicher Geschwindigkeit hörbar langsamere Takte.
- [ ] Anhalten: die Takte hören auf, das Leerlaufgeräusch läuft weiter; Fahrgeräusch aus: alles verstummt sofort.

Ergebnis: _offen_

## B-22 – Steuerungsansicht im Fenster

Vorbereitung: `cargo run --release -- -f <konfiguration>` auf dem Mac, Gamepad angeschlossen.
Im Container gibt es keine Anzeige; geprüft ist nur das ohne Anzeige gezeichnete Bild (`target/test-logs/screenshots/control_view.png`).
Neu ist, dass die Gamepads nicht mehr im Haupt-Thread abgefragt werden (dort läuft jetzt das Fenster); ob SDL das auf macOS mitmacht, ist ungeprüft.

- [ ] Das Fenster öffnet sich und zeigt alle Loks nebeneinander mit Name, Bild, Geschwindigkeit und Knöpfen.
- [ ] Das Gamepad fährt eine Lok; ihr Regler ist in der Farbe des Gamepads hinterlegt, und die Geschwindigkeit läuft mit.
- [ ] Richtungsknopf, Fahrgeräusch, Funktionsknöpfe (auch Taster: gedrückt halten) und Nothalt-Knopf wirken per Maus.
- [ ] Fenster schließen beendet die App.
- [ ] Bei mehr Loks, als nebeneinander passen, werden die Regler schmaler; erst wenn auch das nicht reicht, erscheint die Bildlaufleiste.
- [ ] Mit „Auto focus“ (Standard an) scrollt das Fenster beim Lokwechsel per Steuerkreuz zur neuen Lok; ohne bleibt es stehen.
- [ ] Der Fokus-Knopf (in Konfigurationen aus Electrip 1 der `focus_button`) holt die Lok des Gamepads in den sichtbaren Bereich.
- [ ] „Only active locos“ zeigt nur gesteuerte und fahrende Loks; beide Häkchen sind nach einem Neustart noch gesetzt.

Ergebnis: _offen_

## B-03 – Mehrere Gamepads gleichzeitig

Vorbereitung: `cargo run --release -- -f <konfiguration>` auf dem Mac, so viele Gamepads wie vorhanden, mindestens so viele Loks.
Geprüft sind dreißig virtuelle Geräte (`crates/input/tests/hotplug.rs`) und die ohne Anzeige gezeichneten Bilder (`target/test-logs/screenshots/control_view_devices.png`, `control_view_wrapped.png`).

- [ ] Jedes Gamepad steuert eine eigene Lok; die Loks fahren gleichzeitig.
- [ ] Jedes Gamepad hat eine eigene Nummer und eine Farbe der Palette (ab dem 9. Gamepad wiederholen sich die Farben); die gesteuerte Lok ist darin hinterlegt, und oben steht ein Kreis mit der Nummer des Gamepads.
- [ ] Mehrere Gamepads an dieselbe Lok: die Kreise mit den Nummern brechen in Zeilen um und bleiben lesbar.
- [ ] Ein Gamepad abstecken und wieder anstecken, während die App läuft: es wird ohne Neustart wieder erkannt und steuert weiter.

Ergebnis: _offen_

## B-25 – Deutsch und Englisch

Vorbereitung: `cargo run --release -- -f <konfiguration>` auf dem Mac.
Geprüft sind die ohne Anzeige gezeichneten Bilder (`target/test-logs/screenshots/control_view_de.png` und `control_view_en.png`); die Sprache ist dort fest gewählt.

- [ ] Mit Systemsprache Deutsch zeigt das Fenster „Nothalt“ (bzw. „Nicht verbunden“), „Autofokus“, „Nur aktive Loks“ und „Fahrgeräusch“.
- [ ] Mit Systemsprache Englisch oder einer anderen Sprache (z. B. Französisch) zeigt es die englischen Texte.

Ergebnis: _offen_

## B-05 – Lokbild und Lautstärke im Fenster

Vorbereitung: `cargo run --release -- -f <konfiguration>` auf dem Mac, ein Foto (PNG oder JPEG) bereitlegen.
Geprüft sind die ohne Anzeige gezeichneten Bilder (`target/test-logs/screenshots/loco_dialog*.png`).

- [ ] Klick auf das Bild einer Lok öffnet den Dialog mit Name, Bild, Zoom und Lautstärke.
- [ ] Pfad zum Foto eintragen, „Laden“: der größte Ausschnitt in der Mitte erscheint.
- [ ] Ziehen mit der Maus verschiebt den Ausschnitt, er bleibt im Bild; der Zoom-Regler vergrößert um die Mitte.
- [ ] „Bild speichern“ schließt den Dialog; der Regler der Lok zeigt den Ausschnitt.
- [ ] Der Lautstärke-Regler ändert die Lautstärke des Fahrgeräuschs hörbar.

Ergebnis: _offen_
