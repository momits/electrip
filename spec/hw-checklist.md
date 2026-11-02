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
