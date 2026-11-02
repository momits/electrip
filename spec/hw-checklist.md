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
