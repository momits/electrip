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
