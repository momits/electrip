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

## N-03 – Client mit eingetragener Host-Adresse (erstes Inkrement)

Vorbereitung: zwei Rechner im selben LAN oder WLAN, auf beiden `cargo run --release`. Rechner A startet normal (Host), Rechner B mit `cargo run --release -- --host <IP von A>:4711`. Ein Gamepad an jedem Rechner.

- [ ] macOS fragt auf A, ob eingehende Verbindungen erlaubt sind; nach „Erlauben“ verbindet sich B (kein `ERROR cannot reach the host` auf B).
- [ ] B zeigt die Loks der Konfiguration von A; ein Gamepad an B fährt eine Lok, A zeigt Geschwindigkeit und Gerätesymbol ohne spürbare Verzögerung.
- [ ] Beide Gamepads bekommen verschiedene Nummern und steuern verschiedene Loks.
- [ ] B beenden, während sein Gamepad die Achse ausgelenkt hält: Sein Gerätesymbol verschwindet auf A, die Lok behält ihre Geschwindigkeit und beschleunigt nicht weiter.
- [ ] B mit `--host` auf eine Adresse ohne Electrip starten: Nach etwa 2 s meldet B `ERROR cannot reach the host …` und läuft selbst als Host.

Ergebnis: _offen_

## N-03 – Host per mDNS finden

Im Container der Agenten ist Multicast gesperrt; die Suche per mDNS ist dort nur als Auswahlregel getestet (`crates/control/src/discovery/tests.rs`).
Vorbereitung: zwei Rechner im selben LAN oder WLAN, beide mit derselben Zentrale in der Konfiguration (gleiche Adresse, Port und Bus), auf beiden `cargo run --release` ohne `--host`.

- [ ] A starten: Nach etwa 2 s erscheint das Fenster, A ist Host (Gleisstrom schaltbar).
- [ ] B starten: B zeigt die Loks von A; ein Gamepad an B fährt eine Lok, A zeigt das.
- [ ] `dns-sd -B _electrip._tcp` (macOS) zeigt beide Instanzen; `dns-sd -L <name> _electrip._tcp` zeigt bei A `status=host`, bei B `status=client` und bei beiden dieselbe `station`.
- [ ] Beide beenden und gleichzeitig starten: Genau eine ist Host, die andere ihr Client.
- [ ] B mit einer anderen Zentrale in der Konfiguration starten: B wird selbst Host.
- [ ] WLAN auf B aus: B startet allein als Host, ohne Absturz.
- [ ] Mit einer echten Z21: A trägt sie mit ihrer IP ein, B mit einem anderen Namen derselben Z21 (z. B. Hostname statt IP). `dns-sd -L` zeigt bei beiden `station=z21:<Seriennummer>`, B wird Client von A.

Ergebnis: _offen_

## N-03 – Änderungen fremder Programme übernehmen

Vorbereitung: Electrip mit der Zentrale verbinden (srcpd mit echter Anlage oder Z21), eine Lok in der Konfiguration, ein Gamepad. Als fremdes Programm dient ein zweites Fahrpult: bei der Z21 die Z21-App oder ein Handregler, bei srcpd z. B. Electrip 1 oder `telnet <srcpd> 4303` mit `SET 1 GL <adresse> 0 40 128 0 …`.

- [ ] Das fremde Programm fährt die Lok: Electrip zeigt Geschwindigkeit und Richtung des fremden Programms, die Lok fährt dabei ruhig weiter.
- [ ] Das fremde Programm schaltet das Licht (F0): Electrip zeigt die Funktion an.
- [ ] Achse am Gamepad ausgelenkt halten, dann im fremden Programm die Geschwindigkeit ändern: Electrip beschleunigt vom neuen Wert aus weiter, ohne Sprung zurück.
- [ ] Mit Electrip allein bis Vmax beschleunigen (Lok mit 128 Fahrstufen): Die Anzeige bleibt bei Vmax stehen und zittert nicht.
- [ ] Nothalt der Lok in Electrip: Die Richtung in Electrip bleibt, wie sie war.
- [ ] Das fremde Programm fährt die Lok, Electrip ist dabei nicht verbunden. Dann Electrip verbinden: Electrip zeigt sofort Geschwindigkeit, Richtung und Funktionen der Lok, die Lok fährt ruhig weiter (Z21 und srcpd).

Ergebnis: _offen_

## N-03 – Host-Ausfall

Vorbereitung: zwei Rechner A und B im selben LAN oder WLAN, beide mit derselben Zentrale und derselben Lok in der Konfiguration (bis Q-016 beantwortet ist), auf beiden `cargo run --release` ohne `--host`, Gamepad an B. A ist Host, B Client.

- [ ] B fährt die Lok mit dem Gamepad. A hart beenden (`kill -9`): Nach höchstens etwa 3 s plus Suche (2 s) wird B Host. Das Fenster von B bleibt offen und zeigt die Lok mit Geschwindigkeit, Richtung und Funktionen von der Zentrale; die Lok fährt ruhig weiter.
- [ ] Das Gamepad an B fährt die Lok danach weiter, ohne es neu einzustecken.
- [ ] Den Gleisstrom vorher an A ausschalten, dann A beenden: B schaltet ihn nicht ein und zeigt ihn als aus.
- [ ] Bei A das Netzwerkkabel ziehen bzw. WLAN aus (A beendet sich nicht): B erkennt das ebenso nach wenigen Sekunden.
- [ ] Mit drei Instanzen (A Host, B und C Clients) A beenden: Genau eine von B und C wird Host, die andere ihr Client; `dns-sd -L` zeigt das wie bei „Host per mDNS finden“.
- [ ] B mit `--host <A>:4711` statt mDNS: B wird nach dem Ausfall von A ebenfalls Host.

Ergebnis: _offen_

## N-03 – Doppel-Host während des Betriebs

Vorbereitung: zwei Rechner A und B wie bei „Host-Ausfall“, Gamepad an A und an B.

- [ ] Netzwerk zwischen A und B trennen (Kabel ziehen bzw. WLAN aus), dann auf beiden Electrip ohne `--host` starten: Beide werden Host (`dns-sd -B _electrip._tcp` auf jedem Rechner zeigt nur sich selbst als `host`).
- [ ] Netzwerk wieder verbinden: Eine der beiden Instanzen meldet `ERROR this instance hands over to the host …` und wird Client der anderen; danach zeigt `dns-sd -L` genau einen Host. Bitte notieren, wie lange das nach dem Verbinden dauert (mDNS fragt in wachsenden Abständen neu).
- [ ] Das Fenster der abgebenden Instanz bleibt offen und zeigt danach den Zustand des verbleibenden Hosts; beide Gamepads fahren dort weiter, ohne sie neu einzustecken.

Ergebnis: _offen_

## N-03 – Ohne Netzwerkzugriff allein weiter

Vorbereitung: Mac, `cargo run --release` ohne `--host`.

- [ ] In Systemeinstellungen › Datenschutz & Sicherheit › Lokales Netzwerk den Zugriff für Electrip (bzw. das Terminal, aus dem es läuft) ausschalten und Electrip neu starten: Das Fenster öffnet sich, steuert die Zentrale wie gewohnt und zeigt über dem Nothalt den gelben Hinweis „Electrip läuft allein …“ mit dem Grund darunter. Die Konsole zeigt `ERROR no discovery: no access to the local network: …`.
- [ ] Zugriff wieder einschalten und Electrip neu starten: kein Hinweis.
- [ ] WLAN ganz aus und kein Kabel: Electrip startet, läuft allein und zeigt den Hinweis.

Ergebnis: _offen_

## N-03 – Host-Adresse im Fenster eintragen

Vorbereitung: zwei Rechner im selben Netz, beide `cargo run --release` (ohne `--host`), dieselbe Zentrale; IP-Adresse von Rechner A notieren.

- [ ] Auf B in das Feld „Host-Adresse“ (unten rechts) die IP-Adresse von A ohne Port eintragen und „Beitreten“ drücken: Das Fenster von B zeigt kurz „Nicht verbunden“, dann die Loks von A. Die Konsole von B zeigt `ERROR this instance hands over to the host …`. Eine Lok, die B fährt, fährt auch im Fenster von A.
- [ ] Gamepad an B: Es steuert danach Loks über A.
- [ ] Eine falsche Adresse (z. B. `192.0.2.1`) eintragen: Nach ca. 2 s erscheint über dem Nothalt rot „cannot reach the host …“; B bleibt, wie es war.
- [ ] Auf A die eigene Adresse eintragen: rot „… is this instance“; A bleibt Host.

Ergebnis: _offen_

## N-04 – Gemeinsame Konfiguration mit Bild und Sounds

Vorbereitung: zwei Rechner im selben Netz, Bibliothek mit `--library <Ordner>` (oder Standardordner `electrip` im Datenordner). Die Konfigurationsdatei (`<Name>.json`) von A in die Bibliothek von B kopieren, damit beide dieselbe Konfiguration (gleiche `id`) haben. Beide `cargo run --release`.

- [ ] Auf A eine Lok anlegen, ihr ein Bild und eine Geräusch-Funktion mit Sound geben (im Fenster oder über den Steuerkanal, `add_sound_function`): Nach höchstens ca. 10 s zeigt B die Lok mit Bild; in der Bibliothek von B liegen Bild unter `media/` und Sound unter `sounds/`.
- [ ] Auf B die Geräusch-Funktion der neuen Lok auslösen: Der Sound ist zu hören.
- [ ] Netz trennen, auf A die Lok umbenennen, auf B ihre Vmax ändern, Netz verbinden: Nach ca. 10 s haben beide Rechner beide Änderungen.

Ergebnis: _offen_
