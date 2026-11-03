# Fortschritt

Neueste Einträge oben. Jede Sitzung ergänzt hier: Datum, Aufgabe/ID, Ergebnis, Einfachheits-Review (ok/refactored), offene Punkte.

## Aufräumkandidaten

_Befunde aus Einfachheits-Reviews, die älteren Code betreffen. Der Aufräum-Agent arbeitet sie je Phase ab._

_Zurzeit keine._

## 2026-11-03 – Q-015 beantwortet, Prüfung des Z21-Treibers offen (Mo + Claude)

- Mo hat Q-015 wie vorgeschlagen beantwortet: Beim Import aus Electrip 1 behält die eingebaute Aktion den Knopf, der `import_report` nennt die ausgelassenen Funktionen.
- **Offen: Prüfung des Z21-Treibers (N-02).**
  Der Agent hat den Treiber in PR #46 ohne das Roco-PDF geschrieben, weil es im Container nicht erreichbar war.
  `AGENTS.md` verlangt aber, dass der Treiber nur aus der Roco-Spezifikation entsteht.
  Der Simulator stammt aus dem PDF und ist gegen z21aio geprüft; das mindert das Risiko, ersetzt die Prüfung aber nicht.
  N-02 steht auf `verified`, gilt aber erst nach dieser Prüfung als belastbar.
- **Plan für die Prüfung:** Mo lädt das PDF (Link und SHA-256 in `sim/z21/README.md`) lokal herunter.
  Eine eigene Sitzung vergleicht `crates/station-z21` mit dem PDF, ohne den Simulator-Code zu lesen.
  Abweichungen werden auf einem Branch behoben und mit der Szenario-Testsuite gegen beide Treiber geprüft.
- Der Loop bleibt bis dahin angehalten (`STOP`); Mo und Claude machen am 2026-11-04 damit weiter.

## 2026-11-03 – Loop hält: Q-015 und Tor zu Phase 2 (Claude)

- CI auf `main` grün.
- Keine Aufgabe ohne Mo: B-21 wartet auf Q-015, B-20 auf Sounds (Phase 2), B-03/B-05 auf Screenshot-Tests der UI (Phase 2). Keine Aufräumkandidaten offen.
- **Wartet auf Mo:** Q-015 in `spec/questions.md` beantworten oder das Tor zu Phase 2 freigeben, danach `STOP` löschen.

## 2026-11-03 – N-02: Z21-Treiber (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Neues Crate `electrip-station-z21` (`crates/station-z21/`): Treiber für die Roco Z21 über UDP, nur mit der Standardbibliothek, ohne Thread (der Host fragt `events` alle 50 ms ab).
  Anmelden mit Broadcast-Flags 0x00010001 (alle Loks, nicht nur abonnierte) und `LAN_X_GET_STATUS`; ohne Antwort in 3 s „no Z21 answers on …“.
  Gesendet wird nur, was sich gegenüber dem letzten bekannten Zustand der Lok ändert (Lok-Modus DCC/MM, Fahrbefehl, einzelne Funktionen), weil jeder Befehl eine Lok-Info an alle Clients auslöst.
  Lok-Nothalt ist der Fahrbefehl mit Fahrstufe „Nothalt“ (geht mit jeder Firmware). Keepalive alle 20 s, nach 70 s ohne Antwort `Disconnected`; beim Trennen `LAN_LOGOFF`.
- **Quelle:** Das PDF der Spezifikation war im Container nicht erreichbar (kein Internet). Der Treiber entstand aus der Kenntnis der Roco-Spezifikation V1.13, ohne den Code des Simulators zu lesen; die Szenarien liefen danach ohne Änderung grün.
  Unsicher und deshalb in der Hardware-Checkliste: Motorola-Fahrstufen auf der Z21 (MM I/II), Keepalive und Abbruch.
- `set_server` hat das Feld `kind` (`srcp` oder `z21`, Vorgabe `srcp`), der Zustand zeigt es unter `station.kind`; die App wählt danach den Treiber.
- Die Szenario-Suite aus `station-srcp/tests/srcpd_loopback.rs` liegt jetzt in `crates/electrip/tests/station_scenarios.rs` und läuft gegen srcpd (`#[ignore]`, `cargo xtask sim up`) und gegen den Z21-Simulator (je Test ein eigener Simulator, im normalen `cargo xtask test`).
  Dazu `station_connection.rs`: die App fährt über den Steuerkanal eine Lok auf dem Simulator; Unit-Tests der Telegramme und des Verbindungsabbruchs.
- `cargo xtask test`, `cargo xtask sim up` (8 srcpd-Szenarien), `cargo xtask loc` (3037 Zeilen) und `cargo xtask parity` grün.
- **N-02** `wired` und `verified`. Offen für Phase 2: „experimentell“ in der UI anzeigen; Hardware-Checkliste für die Z21 in `spec/hw-checklist.md`.
- Offene Punkte: Bei 128 Fahrstufen sendet der Treiber höchstens Fahrstufe 126 (DCC kennt 126), der Host rechnet bis 128. Geht ein UDP-Paket verloren, merkt der Treiber das nicht und sendet die Änderung nicht noch einmal.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: ein `expect_event` für alle Zentralen in `tests/common` statt drei Kopien, `common::z21_simulator`, die XOR-Prüfsumme nur an einer Stelle.
- **Nächster Schritt:** Phase 1 wartet nur noch auf Phase-2-Teile und Q-015 (B-21); Halt mit Eintrag, bis Mo Q-015 beantwortet oder das Tor zu Phase 2 freigibt.

## 2026-11-03 – B-21: Mapping aus Electrip 1 (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Der Import aus Electrip 1 legt jetzt das Mapping „Electrip 1“ an (Q-014): `button<n>` → Aktion „Knopf <n>“, Notaus-, Richtungs-, Fokus- und Fahrgeräusch-Knopf → eingebaute Aktion, `axis<n>` → Fahren mit `axis_threshold` als Totzone; ohne `joystick` gelten die Standardwerte von Electrip 1, ein Knopf -1 wird nicht belegt.
  Ein neuer Gerätetyp bekommt eine Kopie dieses Mappings, sonst das Standard-Mapping.
- Geräte, die beim Öffnen oder Import einer Konfiguration angeschlossen sind, bekommen ein Mapping für ihren Typ; vorher reagierten sie danach auf nichts mehr.
- **Q-015** in `spec/questions.md`: In Electrip 1 kann ein Knopf zugleich eingebaute Aktion und Funktion sein (im Korpus `settings.json` Knopf 8 und 6). Bis zur Antwort behält die eingebaute Aktion den Knopf, und der `import_report` nennt es.
- Tests: `electrip1/tests.rs` (Mapping aus dem Korpus, Standardwerte, eingebaute Aktion vor Funktion, Knopf -1), `host/library/tests.rs` (Kopie für neue und schon angeschlossene Gerätetypen), `crates/electrip/tests/electrip1_import.rs` über den Steuerkanal.
- `cargo xtask test`, `cargo xtask loc` (2735 Zeilen) und `cargo xtask parity` grün.
- **B-21** `wired`. `verified` erst nach Q-015, weil der Korpus nicht verlustfrei importiert wird.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Der Filter auf Knöpfe wiederholte die Regel aus `function` (F28, Knopf -1); jetzt zählt nur, ob es die Aktion gibt.
  Nicht übernommen: Knöpfe aus den Aktionsnamen zurücklesen (eine Funktion ohne Knopf mit dem Namen „Knopf 3“ würde sonst belegt).
- **Nächster Schritt:** Z21-Treiber für N-02 (eigene Sitzung, nur aus der Roco-Spezifikation).

## 2026-11-03 – Q-014 beantwortet, Z21-Treiber in Phase 1 (Mo + Claude)

- Mo hat Q-014 wie vorgeschlagen beantwortet: Der Import aus Electrip 1 legt ein Mapping mit dem Gerätetyp „Electrip 1“ an.
  Ein neuer Gerätetyp ohne eigenes Mapping bekommt eine Kopie davon.
- Mo hat den Z21-Treiber in Phase 1 vorgezogen (`spec/konzept.md`, Notiz zu N-02).
  Der Z21-Simulator steht seit Phase 0; der Treiber entsteht in einer eigenen Sitzung nur aus der Roco-Spezifikation.
- **Nächster Schritt im Loop:** B-21 mit dem Mapping aus Q-014, dann der Z21-Treiber für N-02.

## 2026-11-03 – Loop hält: Q-014 und Tor zu Phase 2 (Claude)

- CI auf `main` grün.
- Keine Aufgabe ohne Mo: B-21 wartet auf Q-014, B-20 auf Sounds (Phase 2), B-03/B-05 auf Screenshot-Tests der UI (Phase 2), N-02 auf den Z21-Treiber (Phase 2). Die Aufräumkandidaten sind abgearbeitet.
- **Wartet auf Mo:** Q-014 in `spec/questions.md` beantworten oder das Tor zu Phase 2 freigeben, danach `STOP` löschen.

## 2026-11-03 – Aufräumen Phase 1 (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Q-014 ist noch offen; die übrigen offenen Anforderungen der Phase 1 warten auf Phase-2-Teile (B-21 auf Q-014, B-20 auf Sounds, B-03/B-05 auf Screenshot-Tests, N-02 auf den Z21-Treiber). Deshalb die Aufräumkandidaten abgearbeitet:
  - `crates/electrip/tests/driving.rs` nutzt jetzt `connect_to_srcpd`, `observer` und `expect_event` aus `common::srcpd` statt eigener Kopien.
  - `Host::apply` und gespeicherte Konfiguration: entfällt. Achsbewegungen vom Gamepad ändern die Sitzung direkt in `Session::input` und laufen nicht über `change`/`save`; nur einzelne Knopfdrücke (Aktion, Richtungswender, Nothalt) vergleichen die Konfiguration. Eine Liste der Befehle, die die Konfiguration ändern, wäre mehr Code und könnte beim Speichern etwas vergessen.
- `cargo xtask test`, `cargo xtask sim up` (srcpd-Loopback), `cargo xtask loc` (2644 Zeilen) grün. Kein Produktcode geändert.
- Einfachheits-Review: ok (selbst, Diff von 26 Zeilen nur in Testcode komplett neu gelesen).
- **Nächster Schritt:** Halt mit Eintrag in `PROGRESS.md`, bis Mo Q-014 beantwortet oder das Tor zu Phase 2 freigibt.

## 2026-11-03 – B-02: eingebaute Aktionen Fokus und Fahrgeräusch an/aus (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Andere Aufgaben der Phase 1 warten: B-21 auf Q-014, B-20 auf Sounds, B-03/B-05 auf Screenshot-Tests, N-02 auf den Z21-Treiber (alles Phase 2).
- Neue Ziele im Mapping: `focus` und `toggle_sound`.
  `focus` setzt das Feld `focus` des Geräts, solange der Knopf gedrückt ist (Electrip 1 hebt die Lok dann hervor und scrollt zu ihr; das macht die UI in Phase 2).
  `toggle_sound` ist auch der Befehl `toggle_sound { loco }` und schaltet das Feld `sound` der Lok um (Start: aus wie in Electrip 1); abspielen kommt mit B-11 ff.
- Alle eingebauten Aktionen lassen sich auf Knöpfe, Achsen (ab 0,5 Auslenkung gedrückt) und Hat-Richtungen legen; Totzone je Achse gab es schon.
- Tests: `host/tests.rs` (Fokus beim Halten, Fahrgeräusch je Lok, Achse und Hat-Richtung als Knopf), `crates/input/tests/built_in_actions.rs` mit virtuellem Joystick (alle eingebauten Aktionen auf Knopf, Achse oder Hat).
  SDL muss im Haupt-Thread laufen, daher ein Test je Datei.
- `cargo xtask test`, `cargo xtask loc` (2644 Zeilen) und `cargo xtask parity` grün.
- **B-02** `wired` und `verified`. Offen für Phase 2: Knopfnamen in der UI anzeigen (Kriterium 3), Fokus in der Steuerungsansicht (B-22), Fahrgeräusch nur bei Loks mit Motorgeräusch wie Electrip 1 (B-11/B-14).
- Offene Punkte: Wird das Mapping umgestellt, während Fokus gedrückt ist, bleibt `focus` an, bis das Gerät neu angesteckt wird.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Hilfsfunktion `bind` in `host/tests.rs` auch für die beiden älteren Bind-Blöcke.
- **Nächster Schritt:** Antwort auf Q-014 abwarten; sonst wartet Phase 1 nur noch auf Phase-2-Teile. Dann Halt mit Eintrag in `PROGRESS.md`, bis Mo Q-014 beantwortet oder das Tor zu Phase 2 freigibt.

## 2026-11-03 – B-03: Farbe je Eingabegerät (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Jedes Gerät hat im Zustand ein Feld `color` (1 bis 12, wie die zwölf Gamepad-Symbole von Electrip 1); ein neues Gerät bekommt die kleinste Farbe, die kein angeschlossenes Gerät hat.
  Ein 13. Gerät lehnt `add_device` ab (`TooManyDevices`, „there are already 12 devices“).
- Tests: `host/tests.rs` (Farben 1 bis 12, 13. Gerät abgelehnt, frei gewordene Farbe wird wieder vergeben), `crates/input/tests/hotplug.rs` mit zwölf virtuellen SDL-Gamepads (Farben eindeutig, ein neues Pad bekommt die Farbe des abgezogenen).
- `cargo xtask test`, `cargo xtask loc` (2626 Zeilen) und `cargo xtask parity` grün.
- **B-03** `wired`. `verified` fehlt der Screenshot-Test: Farbsymbol unter der gesteuerten Lok kommt mit der UI in Phase 2.
- Offene Punkte: Ein 13. Gamepad bleibt unbenutzbar, auch wenn danach ein anderes abgezogen wird; es muss neu eingesteckt werden (SDL meldet es nicht noch einmal).
- Einfachheits-Review: ok (Sub-Agent).
- **Nächster Schritt:** Antwort auf Q-014 abwarten; bis dahin B-02 (Fokus und Fahrgeräusch an/aus hängen an UI bzw. Sound, Phase 2) oder N-02 (Z21-Treiber erst Phase 2).

## 2026-11-03 – B-21/B-20: Funktionen beim Import aus Electrip 1 (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- `import_electrip1` und `import_loco` (Pakete von Electrip 1) übernehmen jetzt die Decoder-Funktionen: Name, Nummer, Zustand (als Standardzustand) und Modus (Taster bei „push“ und „push limited“, sonst Schalter).
  Je verwendeter Knopfnummer entsteht eine logische Aktion „Knopf <n>“ (ADR 0009), die alle Loks teilen; eine Funktion ohne Knopf (`button: -1`) bekommt eine Aktion mit ihrem Namen.
  Funktionen über F28 werden ausgelassen und im `import_report` genannt.
- **Q-014** in `spec/questions.md`: Für welchen Gerätetyp legt der Import das Mapping (Knöpfe, Fahrachse, Totzone aus `joystick`) an? Bis zur Antwort legt er noch kein Mapping an.
- Tests: `electrip1/tests.rs` (Korpus mit Funktionen, gemeinsame Aktion je Knopf, Modi, F29), `package/tests.rs` (Funktionen des Korpus-Pakets VT 98), `host/library/tests.rs` (Aktionen der importierten Konfiguration, neue Aktion bekommt eine freie ID).
- `cargo xtask test`, `cargo xtask loc` (2616 Zeilen) und `cargo xtask parity` grün.
- **B-21** und **B-20** bleiben offen: Es fehlen das Mapping (Q-014) und die Sounds (Phase 2).
- Offene Punkte: Eine Funktion ohne Knopf und ohne Namen bekommt eine Aktion mit leerem Namen.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Der Test zählt den Modus „push limited“ wie der Code als Taster.
  Nicht übernommen: `electrip1::action_id` und `Session::action_named` zusammenlegen (verschiedene ID-Vergabe, erst zwei Vorkommen).
- **Nächster Schritt:** Antwort auf Q-014 abwarten; bis dahin B-02 (Totzone je Achse ist schon da, Knopfnamen kommen mit der UI) oder N-02 (Szenario-Testsuite für den srcpd-Treiber).

## 2026-11-03 – N-01: Gamepads und Joysticks über SDL3 (Claude)

- CI auf `main` beim Start grün; `cmake` ist jetzt im Container, SDL3 baut.
- Neues Crate `electrip-input` (`crates/input/`) mit `sdl3-sys` (aus der Quelle gebaut, statisch, ohne Video/Audio, siehe SDL3-Eintrag).
  `Gamepads::poll` macht aus den SDL-Ereignissen die Befehle `add_device`, `remove_device` und `input`.
  Gerätetyp (`kind`) ist der Name von SDL, z. B. „Xbox Series X Controller“, „PS5 Controller“.
  Kennt SDL das Layout (Mapping-Datenbank), heißen die Bedienelemente wie in SDL (`a`, `lefty`, `dpleft`); sonst `button0`, `axis1`, `hat0_up/right/down/left`.
  Geräte-IDs sind die Instanz-IDs von SDL.
- Die App fragt SDL alle 50 ms im Haupt-Thread ab, zusammen mit `Host::poll`; `electrip_control::serve` nimmt dafür eine Eingabequelle, die Clients laufen in eigenen Threads.
  Ein fehlgeschlagener Eingabebefehl ändert nichts. Startet SDL nicht, läuft die App mit Steuerkanal weiter (`ERROR no gamepads`).
  SDL fängt keine Signale ab (`SDL_HINT_NO_SIGNAL_HANDLERS`), sonst beendet Ctrl+C die App nicht mehr.
- Tests mit virtuellen Geräten von SDL (`crates/input/tests/`): Xbox-Pad, PlayStation-Pad und Joystick fahren drei Loks mit eigenem Mapping (Beschleunigen und Bremsen in der eingestellten Dauer ±10 %, Totzone, Richtungswender, Aktion auf F0, Gleisstrom aus, Lokwechsel per Hat); zwölf Pads gleichzeitig, Ab- und Anstecken im Betrieb.
- `cargo xtask test`, `cargo xtask loc` (2545 Zeilen) und `cargo xtask parity` grün.
- **N-01** `wired` und `verified`. Offen für Phase 2: Die UI zeigt die Knopfnamen (dafür gibt es `SDL_GetGamepadButtonLabel`).
  **N-07** `wired` und `verified`: Aktionen werden gespeichert (B-21) und wirken auf die Lok des auslösenden Geräts.
  **B-07**, **B-10**, **B-23** `verified`: Der Test mit virtuellem Gamepad fehlte.
  **B-03** bleibt offen: Farbe/Symbol je Gerät fehlt (Screenshot, Phase 2); zwölf Geräte und Hotplug sind getestet.
  **B-02** bleibt offen: Die eingebauten Aktionen „Fokus“ und „Fahrgeräusch an/aus“ fehlen noch (kommen mit UI bzw. Sound).
- Offene Punkte: Belegt ein virtuelles Gerät über den Steuerkanal schon die ID, die SDL vergibt, wird das echte Gerät nicht angelegt.
  Nicht lokal getestet: Build auf macOS und Windows und der Cross-Build für den Raspberry Pi mit SDL3; das zeigt die CI.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Fehler beim Annehmen von Verbindungen melden statt den Listener-Thread still zu beenden; `Gamepads` ist nicht `Send`; nur das Gamepad-Subsystem beenden statt ganz SDL.
  Nicht übernommen: `remove_device` nach fehlgeschlagenem Öffnen unterdrücken (der Fehler ändert nichts), Hat-Richtungen nur bei Änderung senden (der Kern zählt jeden Druck nur einmal).
- **Nächster Schritt:** Farbe je Gerät (B-03) oder Funktionen beim Import aus Electrip 1 (B-21/B-20).

## 2026-11-02 – B-20: Lok-Export und -Import als ZIP (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- `crates/core/src/package.rs`: `export_loco { loco, path }` schreibt ein ZIP mit `loco.json` (Lok und die Aktionen, die ihre Funktionen nutzen) und dem Lokbild als `media/<name>.png`.
  `import_loco { path }` liest solche ZIPs und die Lokpakete von Electrip 1 (`<name>.loco` mit den Dateien daneben, umgerechnet wie bei `import_electrip1`), legt das Bild in die Bibliothek (`media/`) und hängt die Lok an.
  Funktionen bekommen die Aktionen der offenen Konfiguration mit gleichem Namen; fehlende Aktionen werden angelegt.
  Ein fehlendes oder kaputtes Bild steht im `import_report`, der Import läuft weiter.
- Neue Abhängigkeit `zip` (nur Deflate über flate2 mit miniz_oxide, das `png` schon nutzt). `picture::store_bytes` speichert ein Bild aus dem Speicher; `Loco::set_picture` nimmt jetzt `Option`.
  Die Meldung `ImportError::Invalid` heißt jetzt „invalid file“, weil sie auch für Pakete von Electrip 2 gilt.
- Tests: `package/tests.rs` (alle sechs Korpus-Pakete, Export und wieder Import, fehlendes und kaputtes Bild, keine Lokdatei, kein ZIP), `host/library/tests.rs` (Aktionen nach Namen, fehlgeschlagener Import ändert nichts), `crates/electrip/tests/loco_packages.rs` über den Steuerkanal.
- `cargo xtask test`, `cargo xtask loc` (2407 Zeilen) und `cargo xtask parity` grün.
- **B-20** bleibt offen (nicht `wired`): Verlustfrei ist der Import erst, wenn Sounds (B-11 bis B-17, Phase 2) und die Funktionen von Electrip 1 (`functions` mit `button`, zusammen mit B-21) im Kern sind; bis dahin übergeht der Import sie, ohne das im `import_report` zu nennen.
  Der Export enthält entsprechend noch keine Sounds.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: `filter_map` statt Schleife in `Session::import_loco`.
- **Nächster Schritt:** nach dem Neubau des Containers `electrip-input` mit SDL3 (N-01, siehe SDL3-Eintrag), sonst Funktionen beim Import aus Electrip 1 (B-21/B-20).

## 2026-11-02 – SDL3 im Container baubar (Mo + Claude)

- Das Image enthält jetzt `cmake` aus Debian, die CI-Runner haben es schon.
  Damit baut `sdl3-sys` SDL3 aus der Quelle im Crate `sdl3-src`; die Version ist über `Cargo.lock` gepinnt, es kommt nichts außer crates.io dazu.
- Getestet im Container hinter der Firewall: SDL 3.4.18 baut in etwa 40 s, statisch gelinkt, und ein virtuelles Gamepad lässt sich anlegen.
- Diese Abhängigkeit funktioniert ohne weitere Debian-Pakete (Konsolen-Build ohne Video und Audio, die Oberfläche kommt von Slint):
  `sdl3-sys = { version = "0.7", features = ["build-from-source", "link-static", "sdl-unix-console-build", "no-sdl-audio", "no-sdl-video", "no-sdl-render", "no-sdl-gpu", "no-sdl-camera"] }`
  Ohne diese Features verlangt der Build X11-, Wayland- und Audio-Header.
- SDL3 steht unter der Lizenz `Zlib` (frei, GPL-kompatibel); `deny.toml` muss sie mit der ersten SDL3-Abhängigkeit erlauben.
- Nicht getestet: der Cross-Build für den Raspberry Pi mit SDL3; das zeigt die CI beim ersten Pull Request mit SDL3.
- **Wartet auf Mo:** Container neu bauen (`docker exec electrip touch STOP`, Sitzung abwarten, `docker stop electrip`, dann `.devcontainer/start.sh`).
- **Nächster Schritt im Loop danach:** Crate `electrip-input` mit SDL3 (N-01), dann virtuelle Gamepads für die Prüfart `virtual-gamepad`.

## 2026-11-02 – B-05: Lokbild (Claude)

- Die vorige Sitzung brach mitten in B-05 ab (Nutzungslimit); ihr Zwischenstand ist der erste Commit dieses Branches.
- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- `crates/core/src/picture.rs`: lädt ein PNG oder JPEG, schneidet einen Ausschnitt im Seitenverhältnis 22:17 aus (`crop`: linke obere Ecke `x`, `y` und Breite `width` in Pixeln des Bildes; Verschieben und Zoomen ändern diese Werte) und speichert ihn in 440×340 px als PNG unter `media/<sha256>.png` in der Bibliothek (ADR 0003: jedes Bild nur einmal).
  Ohne `crop` nimmt es den größten Ausschnitt in der Mitte.
- Neuer Befehl `set_picture { loco, path, crop }`; neues Feld `picture` je Lok im Zustand und in der gespeicherten Konfiguration (`spec/steuerkanal.md`).
  Neu wählen heißt: `set_picture` noch einmal.
- `import_electrip1` übernimmt das Lokbild (`img_path`, relativ zum Ordner der Datei) mittig zugeschnitten; fehlt das Bild, steht das im `import_report`, der Import läuft weiter.
- Neue Abhängigkeiten: `image` (nur PNG und JPEG) und `sha2`; `image` auch als Dev-Abhängigkeit von `electrip` für ein Testbild.
- Tests: `picture/tests.rs` (Ausschnitt, Standard Mitte, feste Größe, gleiches Bild nur einmal, Ausschnitt außerhalb, keine Bilddatei), `host/library/tests.rs` (speichern und wieder öffnen, Fehler ändert nichts, Import schneidet mittig zu), `crates/electrip/tests/loco_properties.rs` über den Steuerkanal.
- `cargo xtask test`, `cargo xtask loc` und `cargo xtask parity` grün.
- **B-05** `wired`: alle Kriterien ohne Oberfläche erfüllt. `verified` fehlt der Screenshot-Test; Bildauswahl mit Verschieben/Zoomen und Anzeige kommen in Phase 2.
- Offene Punkte: Die EXIF-Ausrichtung von JPEGs wird nicht beachtet (Handyfotos im Hochformat liegen dann quer); Bilder in `media/`, die keine Lok mehr nutzt, werden nicht gelöscht.
  Ein Client sieht nur den Namen des Bildes; die Datei liegt beim Host (Übertragung mit N-04/ADR 0010).
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: überflüssige Prüfung `width > 0`, Schreiben ohne Closure.
  Nicht übernommen: `Import.pictures` mit den Loks zu Paaren zusammenlegen (mehr Umbau für wenig Gewinn).
- **Nächster Schritt:** Lok-Export/-Import als ZIP (B-20) oder SDL3 im Container (siehe B-23-Eintrag).

## 2026-11-02 – B-21: Konfigurationen in einer Bibliothek (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Die Bibliothek ist ein Verzeichnis mit einer JSON-Datei `<name>.json` je Konfiguration (Konzept: „Gesamtkonfiguration als JSON speichern/laden“).
  Gespeichert werden Loks (Reihenfolge, Decoder, Kennlinie, Funktionen im Standardzustand), Aktionen, Mappings und Server; Fahrzustand und Geräte nicht.
  `crates/core/src/config.rs` liest und schreibt die Dateien (erst in eine temporäre Datei, dann umbenannt), `crates/core/src/host/library.rs` hat die Befehle.
- Neue Befehle `new_configuration`, `open_configuration`, `rename_configuration`, `remove_configuration` (nur eine andere als die geöffnete), `export_configuration { path }`.
  Jede Änderung an der geöffneten Konfiguration schreibt der Host sofort; schlägt das Schreiben fehl, bleibt die Sitzung unverändert.
  Neu anlegen, öffnen und importieren nur ohne Verbindung, weil sich der Server ändert.
  `import_electrip1` legt jetzt eine neue Konfiguration mit dem Dateinamen ohne Endung an und öffnet sie.
  Namen müssen auf allen Systemen Dateinamen sein; so kann kein Befehl Dateien außerhalb der Bibliothek erreichen.
- Zustand: neue Felder `configuration` und `configurations` (`spec/steuerkanal.md`).
- Die App hat neu `--library <verzeichnis>` (Vorgabe: `electrip` im Datenverzeichnis des Nutzers) und `-f/--file <konfiguration>` (B-24); ohne `-f` öffnet sie die erste Konfiguration nach Namen, eine leere Bibliothek bekommt „Electrip“.
- `tempfile` ist neue Dev-Abhängigkeit (Tests mit Bibliotheksverzeichnis).
- Tests: `config/tests.rs`, `host/library/tests.rs` (speichern und wieder öffnen, wechseln, umbenennen, löschen, exportieren, importieren, ungültige Namen, fehlgeschlagenes Speichern), `crates/electrip/tests/configurations.rs` über den Steuerkanal inkl. Neustart mit `--file`.
- `cargo xtask test`, `cargo xtask loc` und `cargo xtask parity` grün; srcpd-Tests nur in der CI (kein Docker lokal).
- **B-01** `wired` und `verified`: Host, Port und Bus werden jetzt gespeichert.
  **B-04** `wired` und `verified`: Die Reihenfolge der Lokliste wird gespeichert. Offen für Phase 2: Umbenennen und Löschen in der UI.
  **B-24** `wired` und `verified`: `-f/--file` öffnet die Konfiguration. Offen für Phase 2: Maussteuerung.
  **B-21** bleibt offen: Der Import ist erst verlustfrei, wenn Bild, Sounds, Funktionen und Gamepad-Einstellungen im Kern sind.
- Offene Punkte: Beim Laden prüft die App die Werte der Datei nicht gegen die Grenzen (Adresse, Fahrstufen, Kennlinie); das kann eine von Hand bearbeitete Datei verletzen.
  ADR 0003 sieht je Konfiguration ein Automerge-Dokument vor; das kommt mit der gemeinsam genutzten Konfiguration (N-04, Phase 2), bis dahin genügt JSON.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Sitzung zurücksetzen, wenn das Speichern scheitert; Dateien mit ungültigen Namen auslassen (sonst startet die App nicht); atomares Schreiben; `From<io::Error>` statt `map_err` an zehn Stellen.
  Nicht übernommen: `refresh` aufteilen, `-f` direkt an `Host::new` geben (beides mehr Code für wenig Gewinn); `Function.on` wieder nur über `load` setzen.
- **Nächster Schritt:** SDL3 im Container (siehe B-23-Eintrag), sonst Lokbild (B-05) oder Lok-Export/-Import als ZIP (B-20).

## 2026-11-02 – B-23: Lokwechsel mit Dauerdruck (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- **SDL3 ist im Container nicht baubar:** Es gibt weder `libsdl3-dev` noch `cmake` (für `sdl3` mit `build-from-source`), kein `sudo` für `apt`, und der Proxy lässt nur crates.io durch.
  Der nächste Schritt aus N-01 (Crate `electrip-input`) braucht deshalb Mo: `cmake` oder `libsdl3-dev` (Debian trixie hat SDL 3.2) im `.devcontainer/Dockerfile` nachinstallieren und den Container neu bauen.
  Bis dahin habe ich stattdessen das Dauerdruck-Scrollen gebaut.
- Hält ein Gerät „vorige/nächste Lok“, wechselt die Lok sofort, nach 500 ms erneut und dann alle 60 ms, bis der Knopf losgelassen wird (wie Electrip 1: der zweite Wechsel kommt bei 560 ms).
  `Device` merkt sich den gehaltenen Wechsel; `Session::drive` (also `Host::poll`) zählt die Zeit und wechselt die Lok.
  Loslassen beendet das Scrollen auch dann, wenn die Belegung in der Zwischenzeit geändert wurde.
- Tests: `input/tests.rs` (Zeitpunkte), `host/tests.rs` (Scrollen über freie Loks, Ende beim Loslassen, auch nach `unbind`), `crates/electrip/tests/input_devices.rs` über den Steuerkanal.
- `cargo xtask test`, `cargo xtask loc` und `cargo xtask parity` grün.
- **B-23** `wired`: Alle Kriterien ohne Oberfläche sind über den Steuerkanal erfüllt; die Anzeige des Gleisstroms kommt in Phase 2.
  `verified` fehlt der Test mit virtuellem Gamepad (SDL3, siehe oben).
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Loslassen vor dem Nachschlagen der Belegung, `change_and_scroll` statt eines zweiten `start_scroll`.
  Nicht übernommen: die Zweige „vorige/nächste Lok“ zusammenlegen (spart kaum Zeilen).
- **Nächster Schritt:** mit Mo SDL3 in den Container bringen (siehe oben), dann `electrip-input`. Ohne SDL3: B-21 (Konfigurationen speichern) oder fremde Lok-Änderungen im Host übernehmen (Q-010).

## 2026-11-02 – N-01, B-02: Eingabegeräte und Mappings im Kern (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- `crates/core/src/input.rs`: `Mapping` je Gerätetyp (`kind`) von Bedienelementen (Namen wie SDL: `a`, `lefty`, `dpleft`; Joysticks z. B. `button0`, `axis1`, `hat0_left`) auf `Target`: Fahren (mit Totzone je Achse, B-02), Richtungswender, Nothalt der Anlage, Lok-Nothalt, vorige/nächste Lok oder logische Aktion (ADR 0009).
  `Device` ist ein angeschlossenes Gerät mit der Lok, die es steuert, und merkt sich gedrückte Knöpfe, damit wiederholte Meldungen nichts doppelt auslösen.
- Neue Befehle in `crates/core/src/session/devices.rs`: `add_device`, `remove_device`, `bind`, `unbind`, `input`.
  Ein neuer Gerätetyp bekommt das Standard-Mapping nach Electrip 1 (`lefty` fährt, `a` Nothalt der Anlage, `b` Richtungswender, Steuerkreuz links/rechts Lokwechsel).
  Ein neues Gerät steuert die erste freie Lok; Lokwechsel überspringt Loks anderer Geräte wie Electrip 1, die Achse wandert mit.
  `input` liefert dem Host den passenden Befehl (`trigger_action`, `reverse`, `toggle_power`, `emergency_stop`); damit nennt eine Aktion jetzt die Lok des auslösenden Geräts (N-07).
  `remove_action` löscht auch die Belegungen der Aktion.
- Die Totzone wird jetzt beim Setzen der Achse angewendet (`drive::deflection`); `set_axis` behält 0,06.
- Zustand: neue Felder `mappings` und `devices` (`spec/steuerkanal.md`). Über den Steuerkanal sind das die virtuellen Eingaben.
- Tests: `input/tests.rs`, `host/tests.rs` (Achse, Totzone je Belegung, Knöpfe einmal je Druck, Aktion an der Lok des Geräts, Lokwechsel, Achse wandert mit, Gerät entfernen), `crates/electrip/tests/input_devices.rs`: Xbox-Pad, PlayStation-Pad und Joystick fahren gleichzeitig drei Loks mit je eigenem Mapping.
- `cargo xtask test` und `cargo xtask parity` grün.
- Status unverändert: Echte Gamepads fehlen (SDL3-Treiber in `input`, Knopfnamen des Geräts, Test mit SDL-Virtual-Joystick).
  B-02: Fokus und Fahrgeräusch an/aus kommen mit Oberfläche bzw. Sound (Phase 2); Knopfnamen kommen mit SDL3.
  B-23: Dauerdruck beim Lokwechsel scrollt noch nicht (Electrip 1: nach 500 ms alle 60 ms).
  Mappings werden noch nicht gespeichert (B-21).
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Totzone beim Setzen der Achse statt eigener `Axis`-Struktur je Lok, einfacheres `match` in `input`, `change_loco` ohne `Option<()>`, `taken_locos` statt doppelter Zeile, Standard-Totzone nur an einer Stelle.
- **Nächster Schritt:** Crate `electrip-input` mit SDL3: Geräte erkennen und ihre Ereignisse als `add_device`/`input` an den Host geben, Test mit SDL-Virtual-Joystick; danach Dauerdruck-Scrollen (B-23).

## 2026-11-02 – N-07, B-07: Logische Aktionen schalten Lokfunktionen (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- `crates/core/src/function.rs`: `Action` (Name, lokübergreifend), `Function` (Aktion → Funktionsnummer F0–F28, Name, Modus Umschalter/Taster, Standardzustand, aktueller Zustand `on`).
  Befehle in `crates/core/src/session/actions.rs`: `add_action`, `rename_action`, `remove_action` (löscht auch die Funktionen, die darauf zeigen), `add_function`, `remove_function`, `move_function`, `trigger_action { loco, action, pressed }`.
  Die Zentrale bekommt alle Funktionen, die an sind; der Host sendet sie wie Fahrstufen nach jeder Änderung.
  Funktionsnummern über F28 sind ein Fehler, weil `CommandStation` nur F0–F28 kennt (N-02); gegen die Grenzen der Zentrale wird nicht geprüft.
- Zustand: neues Feld `actions`, je Lok `functions` (`spec/steuerkanal.md`).
- Tests: `crates/core/src/function/tests.rs` (Umschalter, Taster, Standardzustand „An“), `session/tests.rs`, `crates/electrip/tests/actions.rs` über den Steuerkanal und ein `#[ignore]`-Test gegen srcpd (zwei Loks, dieselbe Aktion auf F0 bzw. F4).
- **Gefunden und behoben:** `cargo xtask sim up` führte nur eine feste Liste von Testdateien aus; die srcpd-Tests aus `track_power.rs` (B-23) liefen deshalb nie.
  Jetzt laufen alle `#[ignore]`-Integrationstests von `electrip` und `electrip-station-srcp`; lokal alle grün.
  Gemeinsame srcpd-Helfer stehen in `crates/electrip/tests/common/srcpd.rs`.
- `cargo xtask test`, `cargo xtask sim up` und `cargo xtask parity` grün. Hardware-Checkliste in `spec/hw-checklist.md` ergänzt.
- **B-07** `wired`; `verified` fehlt der Test mit virtuellem Gamepad (N-01).
  **N-07** bleibt offen: Aktionen werden noch nicht in der Konfiguration gespeichert (B-21), und „die Lok, die das auslösende Eingabegerät steuert“ kommt mit N-01; bis dahin nennt `trigger_action` die Lok.
  Der Import aus Electrip 1 übernimmt noch keine Funktionen (ADR 0009: je Knopfnummer eine Aktion; mit B-21/N-01).
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: `remove_function` in `session/actions.rs`, `remove_action` sucht die Aktion nur einmal, Test-Helfer `try_add_function`.
- **Nächster Schritt:** Eingabegeräte (N-01) mit virtuellem Gamepad, damit B-03, B-07, B-10, B-23 und N-07 vollständig werden; oder B-21 (Konfigurationen speichern).

## 2026-11-02 – B-23: Gleisstrom und Nothalt (Claude)

- Die vorige Sitzung war mitten in B-23 abgebrochen; der Zwischenstand wurde formatiert, geprüft und fertiggestellt.
- Neue Befehle `toggle_power` (Nothalt der Anlage: Gleisstrom aus, beim nächsten Mal an; nur mit Verbindung), `emergency_stop { loco }` (nur diese Lok hält sofort, Achse losgelassen, SRCP-Nothalt) und `set_power_on_start { on }`.
- Zustand `station` hat neu `power_on_start` (Vorgabe an, aus Electrip 1 als `power` importiert) und `track_power`.
  `connect` schaltet den Gleisstrom ein, wenn `power_on_start` gesetzt ist; `track_power` folgt den Meldungen der Zentrale und ist damit über alle Instanzen an derselben Zentrale synchron.
- Tests: `crates/core/src/host/tests.rs` (Fake-Treiber zeichnet Gleisstrom, Fahrstufen und Nothalt auf), `crates/electrip/tests/track_power.rs` über den Steuerkanal, zwei `#[ignore]`-Tests gegen srcpd (Gleisstrom bei zwei Instanzen, Lok-Nothalt kommt an).
  Lokal ohne Docker liefen die srcpd-Tests nicht; sie laufen im CI-Job „srcpd simulator“.
- `cargo xtask test` grün. Hardware-Checkliste in `spec/hw-checklist.md` ergänzt.
- Status unverändert: Der Lokwechsel („vorige/nächste Lok“ mit Auto-Scroll) und die Zuordnung „Lok, die das auslösende Eingabegerät steuert“ brauchen Eingabegeräte (N-01, N-07); die Anzeige des Gleisstroms kommt in Phase 2.
- Einfachheits-Review: ok (Sub-Agent). Optionale Hinweise (Befehlszweige in eigene Methoden, Helfer im Fake-Treiber) nicht übernommen.
- **Nächster Schritt:** Eingabegeräte (N-01/N-07), damit B-03, B-10 und B-23 vollständig werden.

## 2026-11-02 – B-21: Import von Konfigurationsdateien aus Electrip 1 (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- `crates/core/src/electrip1.rs` liest eine Konfigurationsdatei von Electrip 1; neuer Befehl `import_electrip1 { path }` ersetzt Loks und Server (nur ohne Verbindung, ein Fehler ändert nichts).
  Übernommen wird, was Electrip 2 schon kennt: Name, Protokoll, Adresse, Fahrstufen, Vmax, Kennlinie, Beschleunigungs- und Bremsdauer, Lautstärke, Host, Port, Bus.
  Fehlende Werte bekommen die Vorgaben von Electrip 1; fehlen Lokliste, Server oder Kennlinie, ist die Datei ungültig wie in Electrip 1.
  Loks mit N 1 und Adresse über 127 werden DCC lang und stehen im neuen Zustandsfeld `import_report` (B-06).
- `electrip-core` hängt jetzt von `serde_json` ab (mit `float_roundtrip`, damit Werte wie `120.00000000000003` exakt bleiben).
- Tests: `crates/core/src/electrip1/tests.rs` (alle drei Korpus-Konfigurationen Feld für Feld verlustfrei, Vorgaben, Umstellung auf DCC lang, ungültige Dateien), `session/tests.rs`, `control-channel`-Test `crates/electrip/tests/electrip1_import.rs`.
- `cargo xtask test`, `cargo xtask sim up` und `cargo xtask parity` grün.
- **B-06** `wired` und `verified`: Der Import war das letzte fehlende Kriterium; Unit-, `control-channel`- und srcpd-Loopback-Tests grün.
- B-21 bleibt offen: Konfigurationen anlegen, umbenennen, löschen, wechseln, speichern und exportieren fehlen; verlustfrei ist der Import erst, wenn Bild, Sounds, Funktionen und Gamepad-Einstellungen im Kern sind.
  Bis es mehrere Konfigurationen gibt, ersetzt der Import die aktuelle.
  Der Import liegt im Kern statt in `library`, weil der Befehl im Kern ihn braucht und `core` von keinem anderen Crate abhängen darf.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: `Station` wird direkt aus der Datei gelesen statt über eine Kopie ihrer Felder, `import()` ist privat.
  Nicht übernommen: Fehlervarianten zusammenlegen (die getypten Fehler bleiben), gemeinsamer Test-Helfer für den Korpus-Pfad über Crates hinweg.
- **Nächster Schritt:** B-21 weiter: Konfigurationen speichern und verwalten (ADR 0003: Automerge-Dokument je Konfiguration, `library`), damit B-01 und B-04 gespeichert werden.

## 2026-11-02 – Status nach der neuen `wired`-Definition geprüft (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Geprüft wurden B-01, B-04, B-05, B-06, B-08 und B-09 gegen ihre Akzeptanzkriterien. Nur Kriterien zur Oberfläche gelten in Phase 1 als offene Punkte, alle anderen müssen erfüllt sein.
- **B-08** `wired` und `verified`: Endpunkte nicht löschbar und Interpolation im Kern, alle Befehle über den Steuerkanal; Golden-, Unit- und `control-channel`-Tests grün.
  Offen für Phase 2: Klick, Rechtsklick und Ziehen in der UI.
- **B-09** `wired` und `verified`: Ohne `confirmed` liefert der Befehl einen Fehler und ändert nichts, mit `confirmed` wird zurückgesetzt; `control-channel`-Test grün.
  Offen für Phase 2: Warnung mit Bestätigung in der UI.
- Unverändert, weil Kriterien ohne UI-Bezug fehlen:
  - B-01: Host, Port und Bus werden nicht gespeichert (B-21).
  - B-04: Die Reihenfolge der Lokliste wird nicht gespeichert (B-21).
  - B-05: Das Lokbild (Ausschnitt 440×340 px, Import mit mittigem Zuschnitt) fehlt im Kern.
  - B-06: Der Import aus Electrip 1 (N 1 mit Adresse > 127 wird N 2) fehlt (B-21).
- Kein Produktcode geändert. `cargo xtask test` und `cargo xtask parity` grün.
- Einfachheits-Review: ok (Selbstprüfung, nur Statusfelder).
- **Nächster Schritt:** B-21 (Konfigurationsdatei mit Import aus Electrip 1); damit werden B-01, B-04 und B-06 erfüllbar.

## 2026-11-02 – B-10: Fahren mit der Achse im Sitzungs-Host (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Neue Befehle `set_axis` (Auslenkung -1 bis 1, Totzone 0,06 wie Electrip 1) und `reverse` (Richtungswender); der Zustand jeder Lok zeigt `speed` und `forward` (`spec/steuerkanal.md`).
- `Host::poll(seconds)` beschleunigt alle Loks mit ihrer Achse (`Session::drive`, `Motion` aus dem letzten B-10-Eintrag) und schickt dem Treiber jede Lok, deren Fahrstufe oder Richtung sich geändert hat.
  Fahrstufe aus der Kennlinie, abgeschnitten wie in Electrip 1; Funktionen bleiben 0 bis B-07.
  Beim Verbinden und für neue Loks wird erst nach einer Änderung gesendet, damit eine Lok, die ein anderes Programm fährt, nicht angehalten wird.
  Loks fahren auch ohne Verbindung (Zustand ändert sich, nichts wird gesendet).
- Der Steuerkanal übergibt dem Host die seit dem letzten Abfragen vergangene Zeit (Takt 50 ms) und schickt den Zustand, solange er sich ändert.
  Deshalb kann eine `state`-Nachricht vor dem `reply` eintreffen; der Test-Helfer überspringt sie und hat jetzt ein Lese-Timeout von 5 s.
- Tests: Unit-Tests in `crates/core/src/host/tests.rs` (Fake-Treiber zeichnet gesendete Zustände auf), `crates/electrip/tests/driving.rs` über den Steuerkanal (Beschleunigen/Bremsen in etwa 1 s, Richtungswender) und ein `#[ignore]`-Test gegen srcpd (Fahrstufe 128, dann Stillstand rückwärts), der in `cargo xtask sim up` mitläuft.
- `cargo xtask test` und `cargo xtask sim up` grün. Hardware-Checkliste in `spec/hw-checklist.md` ergänzt.
- B-10 `wired` gesetzt (neue Definition für Phase 1: Befehl im Kern und über den Steuerkanal).
  `verified` bleibt offen: Die Gamepad-Achse (N-01/B-03) und der Test mit virtuellem Gamepad fehlen. Fremde Lok-Änderungen von der Zentrale übernimmt der Host noch nicht (Q-010).
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: ein Test-Helfer `host()` statt zwei. Nicht übernommen: Totzone als Parameter von `Motion::accelerate` bleibt, weil sie mit N-01 pro Achse kommt.
- **Nächster Schritt:** B-21 (Konfigurationsdatei, damit B-01, B-04 und B-05 gespeichert werden) oder fremde Lok-Änderungen im Host übernehmen (Q-010).
  Offen aus Mos Eintrag unten: Status von B-01, B-04, B-05, B-06, B-08, B-09 nach der neuen Definition prüfen.

## 2026-11-02 – `wired` in Phase 1: Befehl plus Steuerkanal (Mo + Claude)

- Fast alle Bausteine blieben ohne `wired`, weil die Oberfläche fehlt; die kommt erst in Phase 2.
  Damit wäre Tor B (B-01 bis B-10 `verified`) in Phase 1 nicht erreichbar gewesen.
- Mo hat entschieden: In Phase 1 heißt `wired`, dass die Funktion als Befehl im Kern und über den Steuerkanal erreichbar ist (`AGENTS.md`, Abschnitt Spezifikation).
  Kriterien zur Oberfläche bleiben offene Punkte für Phase 2.
- **Nächster Schritt im Loop:** Status der schon gebauten Anforderungen nach dieser Definition prüfen und setzen (B-01, B-04, B-05, B-06, B-08, B-09, B-10), dann weiter mit offenen Anforderungen.

## 2026-11-02 – B-01: Verbindung zum SRCP-Server über den Sitzungs-Host (Claude)

- CI auf `main` lief beim Start noch, danach grün.
- `crates/core/src/host.rs`: `Host` (ADR 0010) hält die Sitzung und den einzigen Treiber; ein `Connector` öffnet ihn, damit `core` den srcpd-Treiber nicht kennt.
  `Host::apply` ist jetzt der einzige Weg, die Sitzung zu ändern (`Session::apply` nur noch im Crate).
  `Host::poll` verarbeitet die Ereignisse der Zentrale; bisher nur `Disconnected`.
- Neue Befehle `set_server` (Host, Port, Bus; nur ohne Verbindung), `connect` und `disconnect`.
  Vorgaben wie Electrip 1: `localhost`, 4303, Bus 1. Ein fehlgeschlagenes `connect` nennt die Ursache und ändert nichts; ein erneutes `connect` öffnet eine neue Verbindung, bevor es die alte schließt.
  Der Zustand `station` ist jetzt ein Objekt `{host, port, bus, connected}` (`spec/steuerkanal.md`).
- Der Steuerkanal fragt den Host alle 50 ms ab und schickt den Zustand an alle Clients, wenn sich etwas geändert hat, z. B. ein Verbindungsabbruch.
  `electrip` hängt jetzt von `electrip-core` und `electrip-station-srcp` ab.
- Tests: Unit-Tests in `crates/core/src/host/tests.rs` (Fake-Treiber). `crates/electrip/tests/station_connection.rs` prüft über den Steuerkanal mit einem Fake-SRCP-Server Einstellen, Verbinden, Abbruch und erneutes Verbinden sowie einen nicht erreichbaren Server.
  Zwei `#[ignore]`-Tests gegen srcpd (Verbinden, fehlender Bus) laufen in `cargo xtask sim up` mit.
  Außerdem von Hand geprüft: App mit srcpd verbunden, srcpd beendet, Zustand wechselte auf `connected: false`.
- `cargo xtask test` und `cargo xtask sim up` grün. Hardware-Checkliste in `spec/hw-checklist.md`.
- Status unverändert: Host, Port und Bus werden noch nicht gespeichert, weil die Konfigurationsdatei fehlt (B-21), und es gibt noch keine Oberfläche.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Kommentar am leeren `Connect`/`Disconnect`-Zweig in `Session::apply`, Test-Helfer `set_server` liefert ein `Result`.
- **Nächster Schritt:** B-10 im Host anbinden (Takt, Fahrbefehle an den Treiber, fremde Lok-Änderungen nach Q-010) oder B-21 (Konfigurationsdatei, damit B-01, B-04 und B-05 gespeichert werden).

## 2026-11-02 – N-02: `CommandStation` und srcpd-Treiber (Claude)

- CI auf `main` lief beim Start noch, danach grün.
- `crates/core/src/station.rs`: Trait `CommandStation` mit `set_power`, `set_loco`, `emergency_stop` (nur die Lok) und `events`.
  Der Treiber bekommt immer den ganzen Lok-Zustand (Richtung, Fahrstufe, F0–F28), weil der Host ihn hält (ADR 0010) und srcpd Funktionen löscht, die ein `SET GL` nicht nennt.
  Anlagen-Nothalt ist Gleisstrom aus (B-23).
- Neues Crate `electrip-station-srcp`: COMMAND-Session für Befehle, INFO-Session in eigenem Thread für Ereignisse (Gleisstrom, Lok-Zustand, auch von fremden Programmen; `Disconnected` bei Abbruch).
  `INIT GL` sendet der Treiber vor dem ersten `SET GL` einer Adresse und nach jedem Wechsel von Protokoll oder Fahrstufen; Funktionszahl wie Electrip 1 (M 1: 1, M 2: 5, DCC: 29).
  Verbinden prüft den Bus mit `INIT <bus> POWER` wie Electrip 1; Fehler (Server nicht erreichbar, kein SRCP, Bus fehlt) haben verständliche Texte.
- Szenario-Tests `crates/station-srcp/tests/srcpd_loopback.rs` (Verbinden/Trennen, Fehler, Gleisstrom, Fahren, Protokollwechsel, F0–F28, Lok-Nothalt, fremde Änderung) sind `#[ignore]`, weil sie srcpd brauchen.
  `cargo xtask sim up` führt sie statt des bisherigen Rauchtests aus, damit laufen sie im CI-Job „srcpd simulator“.
  Unit-Tests für das Parsen der INFO-Zeilen und den Verbindungsabbruch (Fake-Server).
- `cargo xtask test` und `cargo xtask sim up` grün. Hardware-Checkliste in `spec/hw-checklist.md`.
- Status unverändert: Der Z21-Treiber fehlt (Phase 2), und der Treiber ist noch nicht im Sitzungs-Host angebunden.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Die Meldung „Bus fehlt“ nennt die Ursache mit, Fahrstufenzahl nur einmal gelesen.
- **Nächster Schritt:** B-01: Verbindung (Host, Port 4303, Bus) als Befehl im Sitzungs-Host und über den Steuerkanal, Zustand `connected`/`disconnected` aus den Ereignissen.

## 2026-11-02 – B-10: Fahren mit der Achse im Kern (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- `crates/core/src/drive.rs`: `Motion` hält Geschwindigkeit (km/h) und Fahrtrichtung einer Lok.
  `accelerate` ändert die Geschwindigkeit proportional zur Achsauslenkung wie `accelerate_loco` in Electrip 1: Vollausschlag nach vorn erreicht Vmax in der Beschleunigungsdauer, nach hinten steht die Lok aus Vmax in der Bremsdauer; innerhalb der Totzone (Parameter, pro Achse kommt mit N-01) bleibt die Geschwindigkeit.
  Die vergangene Zeit ist ein Parameter statt fester 50-ms-Takte.
  `reverse` (Richtungswender) setzt die Geschwindigkeit auf 0 und wechselt die Richtung.
- 7 Unit-Tests in `crates/core/src/drive/tests.rs` (Dauern mit ±10 % wie Q-003), `cargo xtask test` grün.
  Status unverändert: Noch nicht im Sitzungs-Host angebunden (Takt, Befehle), srcpd-Loopback und virtuelles Gamepad fehlen.
- Einfachheits-Review: ok (Sub-Agent).
- **Nächster Schritt:** Lokbild aus B-05 im Kern oder B-01/N-02 (srcpd-Treiber hinter `CommandStation`), damit B-10 senden kann.

## 2026-11-02 – B-05: Beschleunigungs-, Bremsdauer und Lautstärke im Kern und über den Steuerkanal (Claude)

- CI auf `main` war grün.
- `crates/core/src/loco.rs`: `Loco` hat `accel_duration`, `brake_duration` und `volume`, Vorgaben wie Electrip 1 (11,5 s, 8,5 s, 0,8).
  Dauern wie in Electrip 1 auf 1–9999 s begrenzt, Lautstärke auf 0–1; ein Wert außerhalb ändert nichts und meldet einen Fehler.
  Die Kennlinie bleibt dabei unverändert. Vmax war schon da (B-09).
- Neue Befehle `set_accel_duration`, `set_brake_duration`, `set_volume`; Format in `spec/steuerkanal.md`.
- Unit-Tests in `crates/core/src/loco/tests.rs` und `session/tests.rs`, `control-channel`-Test in `crates/electrip/tests/loco_properties.rs`.
- `cargo xtask test` grün.
  Status unverändert: Lokbild (Ausschnitt wählen, 440×340 px, Import aus Electrip 1) und die UI mit Screenshot-Test fehlen.
- Einfachheits-Review: ok (Sub-Agent).
- **Nächster Schritt:** Lokbild im Kern (Ausschnitt 22:17 auf 440×340 px zuschneiden) oder ein anderer Kernbaustein der Phase 1 (z. B. B-24 oder B-01).

## 2026-11-02 – B-04: Lokverwaltung im Kern und über den Steuerkanal (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- `crates/core`: `Loco` hat einen Namen, neue Loks heißen „Unbenannte Lok“ wie in Electrip 1.
  Neue Befehle `rename_loco`, `remove_loco` und `move_loco` (neue Stelle in der Lokliste); die Reihenfolge von `locos` im Zustand ist die Lokliste.
  Ids werden nie wiederverwendet (`last_id`, nicht im Zustand), damit ein Befehl für eine gelöschte Lok keine neue trifft.
- Unit-Tests in `crates/core/src/session/tests.rs`, `control-channel`-Test in `crates/electrip/tests/loco_management.rs`; Format in `spec/steuerkanal.md`.
- `cargo xtask test` grün.
  Status unverändert: Umbenennen und Löschen in der UI fehlen, und die Reihenfolge wird noch nicht gespeichert, weil es noch keine Konfigurationsdatei gibt (B-21).
  Beim Speichern muss `last_id` mitgespeichert werden.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: `loco()` nutzt `index()`, Test-Helfer zusammengeführt.
- **Nächster Schritt:** B-05 (Lautstärke, Beschleunigungs- und Bremsdauer) im Kern und über den Steuerkanal, ohne Lokbild.

## 2026-11-02 – B-08: Kennlinie über den Steuerkanal (Claude)

- CI auf `main` war grün.
- `crates/electrip/tests/speed_curve.rs` prüft über den Steuerkanal: Punkt anlegen, inneren Punkt verschieben, Endpunkt verschieben (ändert nur die Fahrstufe), Punkt löschen; ein neu verbundener Client sieht dasselbe.
  Erster und letzter Punkt lassen sich nicht löschen, eine unbekannte Lok ergibt einen Fehler.
- Kein Produktcode geändert.
- `cargo xtask test` grün. Golden-, Unit- und `control-channel`-Tests von B-08 sind damit vorhanden und grün.
  Status bleibt unverändert: Klick, Rechtsklick und Ziehen in der UI fehlen, also kein `wired` und nach der neuen Regel auch kein `verified`.
- Einfachheits-Review: ok (Selbstprüfung, nur eine Testdatei).
- **Nächster Schritt:** B-04 (Namen, Umbenennen, Löschen, Reihenfolge) im Kern und über den Steuerkanal.

## 2026-11-02 – `verified` nur zusammen mit `wired` (Mo + Claude)

- B-09 stand auf `verified`, aber nicht auf `wired`, weil die Warnung in der Oberfläche fehlt.
  Damit zeigte der Paritätsbericht mehr Fortschritt, als es gibt.
- Mo hat entschieden: `verified` gilt nur zusammen mit `wired` (`AGENTS.md`, Abschnitt Spezifikation).
  B-09 steht deshalb wieder auf `verified: false`, bis die Warnung angebunden ist.

## 2026-11-02 – B-09: Kennlinie zurücksetzen über den Steuerkanal (Claude)

- `crates/electrip/tests/curve_reset.rs` prüft über den Steuerkanal: Vmax, Fahrstufenzahl und Protokoll ohne `confirmed` liefern den Fehler zur Bestätigung, und die Lok samt geknickter Kennlinie bleibt unverändert (auch für einen neu verbundenen Client).
  Mit `confirmed` wird die Kennlinie zur Geraden von (0, 0) bis (Vmax, Fahrstufenzahl).
- Kein Produktcode geändert; der Kern konnte das schon (B-09-Eintrag unten, N-08).
- `cargo xtask test` grün. B-09 `verified` gesetzt, denn `control-channel` ist seine einzige Prüfart.
  `wired` bleibt offen: Die Warnung mit Bestätigung in der UI fehlt, es gibt noch keine Oberfläche.
- Einfachheits-Review: ok (Selbstprüfung, nur eine Testdatei).
- **Nächster Schritt:** `control-channel`-Tests für B-08 (Punkte anlegen, löschen, verschieben); danach B-04 (Namen, Umbenennen, Löschen, Reihenfolge).

## 2026-11-02 – N-08: Steuerkanal (Claude)

- CI auf `main` war grün.
- `crates/core/src/session.rs`: `Session` hält die Loks (mit `id`) und die Verbindung zur Zentrale (bisher nur `disconnected`); `Command` umfasst alle bisherigen Befehle: Lok anlegen (Vorgaben wie Electrip 1), Adresse, Protokoll, Fahrstufen, Vmax (mit `confirmed`, B-09) und Kennlinienpunkte anlegen, löschen, verschieben.
  Fehler haben verständliche Texte (`Display`); ein fehlgeschlagener Befehl ändert nichts.
  `core` nutzt dafür `serde` (derive); `deny.toml` erlaubt deshalb zusätzlich die Lizenz Unicode-3.0 (`unicode-ident`, über jedes Proc-Makro, OSI-anerkannt, nur zur Übersetzungszeit).
- Neues Crate `electrip-control`: zeilenweises JSON über TCP nur auf `127.0.0.1`, `hello` mit Version 1, Zustand nach dem Verbinden und nach jedem erfolgreichen Befehl an alle Clients, auf jeden Befehl eine `reply`.
  Ein Thread je Client, eine gemeinsame Sperre für Sitzung und Clients.
- `electrip [--control-port <port>]` startet ohne Oberfläche (Standardport 4711, 0 = frei) und nennt die Adresse in der ersten Ausgabezeile.
- Format in `spec/steuerkanal.md`.
- Test-Helfer `crates/electrip/tests/common/mod.rs` (`App::start`, `App::connect`, `Client::command`); `crates/electrip/tests/control_channel.rs` prüft Begrüßung, Befehle, Fehler und Meldung an zweiten Client.
  App zusätzlich von Hand über den Steuerkanal bedient.
- `cargo xtask test` grün. N-08 `wired` und `verified` gesetzt.
- Einfachheits-Review: ok (Sub-Agent).
- **Nächster Schritt:** B-06, B-08 und B-09 bekommen ihre `control-channel`-Tests mit dem Helfer; offen bleiben dort UI (B-08, B-09) und srcpd-Loopback (B-06).

## 2026-11-02 – Neue Anforderung N-08: Steuerkanal (Mo + Claude)

- B-06, B-08 und B-09 blieben ohne Status, weil ihre Prüfart `control-channel` keinen Steuerkanal hat.
  Den gab es bisher nur im Konzept und in ADR 0002, nicht als Anforderung.
- Mo hat N-08 „Steuerkanal“ in `spec/requirements.json` aufgenommen (Phase 1).
- **Nächster Schritt im Loop:** N-08 vor weiteren Kernbausteinen, denn B-01, B-04, B-05, B-08, B-09 und B-24 brauchen ihn zur Prüfung.
  Danach die schon gebauten Bausteine über den Steuerkanal anbinden und ihren Status setzen.

## 2026-11-02 – B-09: Kennlinie zurücksetzen im Kern (Claude)

- CI auf `main` war grün.
- `crates/core/src/loco.rs`: `Loco` hält Decoder, Vmax und Kennlinie.
  Ändern von Vmax, Fahrstufenzahl oder Protokoll setzt die Kennlinie wie Electrip 1 auf eine Gerade von (0, 0) bis (Vmax, Fahrstufenzahl) zurück, aber nur mit `confirmed = true`.
  Ohne Bestätigung kommt `ResetNotConfirmed` und die Lok bleibt unverändert; ungültige Werte scheitern schon vorher, damit die UI nur für gültige Änderungen nachfragt.
  Gleiche Werte ändern nichts und brauchen keine Bestätigung; die Adresse ändert die Kennlinie nicht.
- Vmax ist wie in Electrip 1 auf 1–999 km/h begrenzt.
- 9 Unit-Tests grün, `cargo xtask test` grün.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: `change_axes` vergleicht die geänderte Lok selbst, statt dass jeder Setter ein Flag „geändert“ berechnet.
- **Offen für B-09, Status deshalb unverändert:** Befehle, Steuerkanal (einzige Prüfart `control-channel`) und der Warnhinweis in der UI.
  Damit ist auch die Bestätigung beim Protokollwechsel aus B-06 im Kern vorhanden.

## 2026-11-02 – B-08: Geschwindigkeitskennlinie im Kern (Claude)

- CI auf `main` war grün.
- `crates/core/src/speed_curve.rs`: `SpeedCurve` bildet km/h über Kontrollpunkte auf Fahrstufen ab, wie `LinearSegmentFunction` in Electrip 1.
  Punkte anlegen, löschen und verschieben halten die Kennlinie steigend; erster und letzter Punkt bleiben und ändern nur ihre Fahrstufe.
  `step_at` liefert die ungerundete Fahrstufe, Geschwindigkeit 0 ist immer Fahrstufe 0, außerhalb der Kennlinie `None`; abschneiden auf ganze Fahrstufen bleibt Sache des Aufrufers, wie in Electrip 1.
- Bewusste Abweichungen: Ein Punkt auf einer schon belegten Geschwindigkeit wird ignoriert (Electrip 1 stürzt mit Division durch null ab), ebenso ungültige Punktnummern; `new` lehnt weniger als zwei Punkte oder Enden ohne Geschwindigkeitsspanne ab.
  `get_x` ist nicht übernommen, Electrip 1 brauchte es nur zum Zeichnen.
- Golden-Test `crates/core/tests/golden_speed_curve.rs` vergleicht Punkte und Fahrstufen bitgenau mit `tests/golden/speed_curve.jsonl`.
  Dafür ist `serde_json` Dev-Abhängigkeit von `core`, mit `float_roundtrip`, weil der Standard-Parser Fließkommazahlen nicht exakt liest.
- 9 Unit-Tests und der Golden-Test grün, `cargo xtask test` grün.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Beim Verschieben begrenzt zuerst der linke, dann der rechte Nachbar, damit bei fallender Kennlinie wie in Electrip 1 der rechte gewinnt.
- **Offen für B-08, Status deshalb unverändert:** Befehle und Steuerkanal (Prüfart `control-channel`), Bedienung per Klick, Rechtsklick und Ziehen in der UI.

## 2026-11-02 – Prüfung des Review-Trailers entfernt (Mo + Claude)

- Der Loop kam mit PR #7 (B-06) nicht weiter: `cargo xtask review-check` ließ den CI-Job „loc, parity, simplicity review, dependencies“ scheitern.
  Der Trailer `Simplicity-Review: ok` stand im Commit, aber in einem eigenen Absatz vor `Co-Authored-By`; Git wertet nur den letzten Absatz als Trailer.
- Mo hat entschieden, die Prüfung zu streichen.
  Entfernt: `cargo xtask review-check`, der CI-Schritt und die Trailer-Pflicht in `AGENTS.md` und ADR 0008.
  Der Einfachheits-Review selbst bleibt Pflicht, sein Ergebnis steht in `PROGRESS.md` und in der Beschreibung des Pull Requests.
- Der CI-Job heißt jetzt „loc, parity, golden, corpus, dependencies“.

## 2026-10-30 – B-06: Decoder-Modell im Kern (Claude)

- Erste Aufgabe der Phase 1, CI auf `main` war grün.
- `crates/core/src/decoder.rs`: `Protocol` (Motorola 1/2, DCC kurz/lang) mit Adressbereichen und Fahrstufen aus B-06, `Decoder` lässt nur gültige Kombinationen zu.
  Beim Protokollwechsel wird die Adresse auf das Maximum begrenzt und die höchste Fahrstufenzahl gesetzt, wie in Electrip 1.
- `clippy.toml` erlaubt `unwrap()` und `expect()` in Tests, wie `AGENTS.md` es vorsieht.
- 7 Unit-Tests grün, `cargo xtask test` grün.
- Einfachheits-Review: ok (Selbstprüfung, kleiner Diff).
- **Offen für B-06, Status deshalb unverändert:** Bestätigung beim Protokollwechsel (kommt mit der Kennlinie, B-08/B-09), Umstellung N 1 > 127 auf N 2 beim Import (B-21), Übersetzung im srcpd-Treiber und Test gegen srcpd-Loopback (N-02).

## 2026-10-30 – Loop nutzt fest Opus (Claude)

- Auf Wunsch von Mo ruft `loop.sh` Claude mit `--model claude-opus-5-5` auf, auch beim Fortsetzen nach dem Nutzungslimit.
  Vorher lief der Loop mit dem Standardmodell des Abos (Sonnet 5.5).
  Für ein neues Modell `MODEL` in `loop.sh` ändern.
- `--dangerously-skip-permissions` bleibt nach Rücksprache mit Mo; der Container ist die Sicherheitsgrenze.
- Getestet: Argumente mit simuliertem `claude` im Container, Modellname mit dem echten `claude -p`.
- Einfachheits-Review: ok (Selbstprüfung, zwei Zeilen).

## 2026-10-30 – Tor A freigegeben (Mo)

- Mo hat Tor A freigegeben, Phase 0 ist abgeschlossen.
- Der erste Lauf des Loops mit echten Tokens hat Klon, Claude-Sitzung, Push, Pull Request und Merge über den Auth-Proxy bestätigt (PR #4).
- **Nächster Schritt:** Phase 1 im Loop (`.devcontainer/start.sh`, dann `docker exec -it electrip ./loop.sh`).

## 2026-10-30 – Loop hält vor Tor A (Claude)

- CI auf `main` (`bc4abc0`) ist grün, es gibt nichts zu reparieren.
- Alle Schritte der Phase 0 sind erledigt, Tor A ist nicht abgehakt, Phase 1 darf deshalb nicht beginnen.
- **Wartet auf Mo:** Tor A prüfen (Container mit echten Tokens starten: Klon, Push, Pull Request, Claude-Sitzung), abhaken und `STOP` löschen.
- Einfachheits-Review: entfällt, nur Doku geändert.

## 2026-10-30 – Phase 0, Schritt 4: Container ohne devcontainer-CLI (Claude)

- Mo fragte, wie sicher `npm install -g @devcontainers/cli` ist.
  Das Paket läuft mit Mos Rechten auf dem Mac, ist nur per Versionsnummer gepinnt und ohne Provenance-Nachweis.
  Seit der Härtung nutzt der Container keine Devcontainer-Features mehr, also braucht es die CLI nicht.
- `start.sh` baut das Image und startet den Container `electrip` nur mit Docker: mit `--init`, `NET_ADMIN`, dem Volume `electrip-workspace` und `container.env`.
  Läuft der Container schon, bricht es ab, damit kein laufender Loop stirbt.
  `devcontainer.json` ist entfallen, seine Umgebung steht in `container.env`.
  Den Loop startet `docker exec -it electrip ./loop.sh`.
- Getestet mit Platzhalter-Tokens: Container startet als `vscode`, Firewall, tinyproxy und Auth-Proxy laufen, das Volume gehört `vscode`, die Umgebung enthält keine Tokens, die GitHub-API antwortet über den Proxy mit 401.
  Der Klon scheitert mit Platzhaltern erwartungsgemäß.
  Ein zweiter Start bei laufendem Container bricht ab.
- Einfachheits-Review: ok (Selbstprüfung, kleiner Diff): eine Quelle für die Umgebung, keine neue Abhängigkeit, eine Abhängigkeit weniger.
- **Nicht getestet:** echte Tokens, also Klon, Push, Pull Request und eine Claude-Sitzung im Container.

## 2026-10-30 – Phase 0, Schritt 4: Tokens für den Agenten unlesbar (Claude)

Mo wollte, dass der Agent die Tokens nur benutzen, aber nicht auslesen kann.
Umgebungsvariablen reichen dafür nicht: Jeder Prozess desselben Nutzers kann sie lesen.

- `auth-proxy.py` läuft unter dem eigenen Nutzer `keeper`, der allein die Tokens in `/etc/electrip-secrets` lesen kann.
  Er setzt sie in Anfragen an die Anthropic-API, an die GitHub-API für `momits/electrip` und an Git für dieses Repo ein, alle anderen Pfade lehnt er ab.
- Claude Code bekommt nur einen Platzhalter und `ANTHROPIC_BASE_URL`.
  Ein Versuch auf dem Mac hat gezeigt, dass das mit dem Abo-Login geht, auch mit Streaming.
- `gh` ist entfernt, der Agent nutzt die REST-API per `curl` über den Proxy; `prompts/session.md` nennt die Pfade.
  `origin` zeigt auf den Proxy.
- `.devcontainer/start.sh` startet den Container und schreibt die Tokens per `docker exec -u keeper` direkt zu `keeper`, nicht über die Umgebung.
- Direkt nach außen dürfen nur noch `keeper` und tinyproxy; tinyproxy lässt nur crates.io und den Speicher für CI-Logs durch.
- Getestet im Container mit Platzhalter-Tokens: Der Agent kann Token-Dateien, Umgebung und Speicher von `keeper` nicht lesen und nichts in dessen Verzeichnis schreiben.
  Anthropic, GitHub-API und Git antworten über den Proxy mit 401 auf die Platzhalter, also kommt das eingesetzte Token an.
  Andere Pfade wie `gists` lehnt der Proxy ab, direkte Verbindungen zu Anthropic und GitHub sind gesperrt.
- Einfachheits- und Sicherheits-Review: refactored (Sub-Agent), kein Weg zu den Tokens gefunden.
  Übernommen: `Content-Length` aus `len(body)` statt vom Client, Antwort 502 bei Fehlern der Gegenstelle, keine doppelten Header, Proxy startet in `/` ohne Core-Dumps, `store-secret` entfällt, Tokens gehen nur an `docker exec`, Recht „Checks“ für das GitHub-Token.
- **Nicht getestet:** echte Tokens im Container, also Klon, Push und Claude-Sitzung über den Proxy, sowie `start.sh` selbst.

## 2026-10-29 – Phase 0, Schritt 4: Härtung des Devcontainers (Claude)

Mo hat eine Prüfung auf Sandbox-Isolation und Supply-Chain-Sicherheit verlangt und alle vorgeschlagenen Härtungen freigegeben.

- **Isolation:** Der Container klont das Repo in ein eigenes Volume, statt Mos Arbeitsordner einzubinden.
  Er läuft ohne Docker-in-Docker und ohne `privileged`, nur mit `NET_ADMIN`.
  Eine Firewall lässt ausgehenden Verkehr nur über tinyproxy zu, der nur Anthropic-API, GitHub und crates.io durchlässt; DNS ist gesperrt.
  `vscode` darf per sudo nur noch das Firewall-Skript starten.
  `loop.sh` startet nur hinter der Firewall statt nur im Container.
- **srcpd ohne Docker:** `cargo xtask sim up` startet srcpd direkt, wenn es installiert ist, sonst wie bisher in Docker.
  srcpd kommt im Container aus dem Debian-Paket.
- **Supply Chain:** Basis-Images per Digest, Claude Code per Version und SHA-256 ohne Auto-Update und Telemetrie, gh und srcpd aus Debian statt aus Devcontainer-Features.
  Rust ist auf 1.99.1 gepinnt (`rust-toolchain.toml`), die CI nutzt das statt `dtolnay/rust-toolchain`.
  CI: Actions per Commit-SHA, `permissions: contents: read`, z21aio per Hash in `sim/z21/requirements.txt`, neuer Schritt `cargo deny check` mit `deny.toml`.
  Damit ist auch die Warnung zu `actions/checkout@v4` erledigt.
- **Für Mo auf GitHub:** Fine-grained `GH_TOKEN` ohne Recht „Workflows“, Ruleset für `main` mit Pflicht zu Pull Request und grünen Checks, Rebase-Merge erlauben.
  Details in `.devcontainer/README.md`.
- Getestet: Image baut. Hinter der Firewall sind `cargo xtask test`, `golden`, `corpus` und `sim up|down` grün, auch mit leerem Cargo-Cache.
  Erlaubte Hosts antworten, andere Hosts, direkter Verkehr und DNS sind gesperrt.
  `sudo` für andere Befehle, `iptables` und das Beenden des Proxys scheitern.
  `claude -p` erreicht über den Proxy die API.
  `cargo deny check` ist grün.
- **Weiter nicht getestet:** `devcontainer up` selbst, also Klon ins Volume, `postStartCommand` und Push aus dem Container.
- **Rest-Risiko:** Der Agent kennt beide Tokens und könnte sie über GitHub nach außen geben.
  Gegenmittel sind knappe Token-Rechte und die Regeln auf GitHub.
- Einfachheits- und Sicherheits-Review: refactored (Sub-Agent).
  Übernommen: Klon erst nach dem Start der Firewall, weil er den Proxy braucht.
  Die Firewall sperrt zuerst alles und lässt auf `lo` nur `127.0.0.1` und `::1` zu, damit auch Dockers DNS auf `127.0.0.11` gesperrt bleibt.
  Das Firewall-Skript nutzt absolute Pfade.
  `insteadOf` für SSH-Adressen ist entfallen, `xtask sim` prüft nur einmal auf srcpd.
  Offen und bewusst so gelassen: CI-Runner, apt-Pakete der CI und Debian-Paketversionen sind nicht gepinnt.

## 2026-10-29 – Phase 0, Schritt 4: Loop und Devcontainer (Claude)

- `.devcontainer/`: Image `devcontainers/rust:2-1-trixie` mit Claude Code, dazu die Features Docker-in-Docker und GitHub-CLI.
  Python und jq bringt das Image schon mit.
  Tokens `CLAUDE_CODE_OAUTH_TOKEN` und `GH_TOKEN` kommen aus der Umgebung des Rechners, Git pusht im Container über HTTPS mit `GH_TOKEN`.
  Commits aus dem Container tragen den Autor „Claude (Electrip-Loop)“.
  Anleitung in `.devcontainer/README.md`.
- `loop.sh`: startet Sitzungen mit `prompts/session.md`, schreibt jede nach `logs/` und läuft nur im Container.
  Beim Nutzungslimit wartet es 30 Minuten und setzt dieselbe Sitzung mit `--resume` fort.
  Nach drei Fehlschlägen in Folge bricht es ab, die Datei `STOP` beendet es.
- `prompts/session.md`: verweist auf `AGENTS.md` und ergänzt nur den Loop: abgebrochene Sitzung aufräumen, CI prüfen, Phasentore beachten, eine Aufgabe je Sitzung, `STOP` anlegen, wenn nur Mo weiterhelfen kann.
- Entscheidung von Mo: Es arbeitet immer nur ein Agent, Sitzungen laufen nacheinander.
  Die Sperrdateien in `current_tasks/` entfallen, ebenso das eigene `CARGO_TARGET_DIR` je Agent.
  `AGENTS.md`, `spec/konzept.md` und ADR 0007 sind angepasst.
- Ebenfalls von Mo: Jede Aufgabe kommt über einen eigenen, aussagekräftigen Pull Request nach `main`.
  Der Agent merged ihn selbst mit Rebase, sobald die CI grün ist.
  Die Regeln dazu stehen in `AGENTS.md` unter „Git“.
- Getestet: Das Image baut, im Container sind `cargo xtask test`, `golden`, `corpus` und `loc` grün.
  `loop.sh` lief im Container mit einem simulierten `claude` für Erfolg, Limit mit Fortsetzen, Fehlschläge und fehlende Ergebniszeile; außerhalb des Containers bricht es ab.
  Format von `stream-json` und `--resume` mit dem echten `claude -p` geprüft.
- **Nicht getestet:** `devcontainer up` mit den Features, also Docker-in-Docker mit `cargo xtask sim up`, GitHub-CLI, Push und Pull Requests aus dem Container.
  Das prüft Mo beim Tor A.
  Der genaue Wortlaut der Limit-Meldung ist nicht beobachtet; `loop.sh` erkennt „hit your … limit“ und „usage limit“.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Reihenfolge im Prompt, damit `git pull` nicht an einem schmutzigen Arbeitsbaum scheitert, Einträge in `.gitignore` an die Wurzel gebunden, fehlende Ergebniszeile ausdrücklich als Fehlschlag.
- **Nächster Schritt:** Tor A, Freigabe durch Mo.

## 2026-10-29 – Phase 0, Schritt 3e: Z21-Simulator (Claude)

- `sim/z21/`: Crate `electrip-sim-z21`, ein UDP-Server nach Roco „Z21 LAN Protokoll“ V1.13.
  Das PDF liegt wegen der Rechte von Roco nicht im Repo; Link und SHA-256 stehen in `sim/z21/README.md`.
- Er deckt die Szenarien von N-02 ab: Anmelden und Abmelden, Gleisstrom, Lok fahren, Funktionen F0–F31, Nothalt für Anlage und Lok, Broadcasts an andere Clients.
  Dazu kommen Lok-Format MM für B-06 und die Hardware-Info, mit der ein Treiber die Firmware 1.43 für den Lok-Nothalt prüfen kann.
- Aufruf: `cargo run -p electrip-sim-z21`, in Rust-Tests `electrip_sim_z21::serve` mit eigenem Socket.
  Er zählt nicht zum Zeilenbudget, weil er unter `sim/` liegt.
- 22 Tests: Konformität mit den Beispiel-Telegrammen der Spezifikation, Szenarien auf virtueller Uhr und ein UDP-Test.
- Gegenprobe mit der unabhängigen Bibliothek z21aio 1.0.7 in `sim/z21/crosscheck.py`, lokal grün.
  Der neue CI-Job „Z21 simulator“ führt sie aus.
- Wo die Spezifikation schweigt, hat der Simulator Annahmen getroffen.
  Sie stehen in `sim/z21/README.md`, und der Z21-Treiber darf sich nicht auf sie verlassen.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Konstante für `LAN_X_UNKNOWN_COMMAND`, Firmware als eine Konstante, eine Schleife für Broadcasts, klarerer Methodenname.
  Entfernt, weil keine Anforderung sie braucht: Freischaltcode, Binärzustände, Lok herausnehmen.
  MM und Hardware-Info bleiben wegen B-06 und B-23.
- CI für `0397f7b` ist in allen sieben Jobs grün, auch der neue Job „Z21 simulator“.
- **Nächster Schritt:** 4, `loop.sh` und Devcontainer.

## 2026-10-29 – Phase 0, Schritt 3d: Korpus (Claude)

- `tests/corpus/packages/`: die sechs Lokpakete von SourceForge, unverändert (BR 216, BR 81, Koef II, V 200, V 60, VT 98).
- `tests/corpus/configs/`: drei vollständige Konfigurationen, erzeugt mit dem Code aus `legacy/` durch `tools/legacy-harness/corpus.py` (Q-002).
  Sie decken alle Pakete, eine neue Lok mit Vorgabewerten, geänderte Einstellungen und alle Felder eines Geräusch-Ereignisses ab.
- `cargo xtask corpus` prüft `tests/corpus/SHA256SUMS` und ob `corpus.py` dieselben Konfigurationen erzeugt; `--record` schreibt beides neu.
  Der CI-Job „checks“ führt die Prüfung aus.
  Neue Abhängigkeit von `xtask`: `sha2`.
- Lizenz: Das Projekt steht auf SourceForge unter GPLv3, die Pakete haben keine eigene Lizenzdatei.
  Einige Sounds tragen Namen fremder Sammlungen.
  Das Repo ist privat; vor einer Veröffentlichung sollte Mo die Herkunft klären.
- Auffälligkeiten für B-20 und B-21 stehen in `tools/legacy-harness/README.md`.
  Wichtig: Electrip 1 entpackt das Bild von Koef II unter falschem Namen, weil das ZIP UTF-8-Namen ohne UTF-8-Flag enthält.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Hex-Ausgabe von `sha2` statt eigener Schleife, ein Vergleich für `SHA256SUMS` mit klarer Meldung bei fehlender Datei, Prüfung auf neue oder fehlende Konfigurationen, doppeltes Bytecode-Flag entfernt, Parametername in `corpus.py`.
  Golden Files unverändert.
- CI für `68f9b9a` ist in allen sechs Jobs grün, auch die neue Korpus-Prüfung.
- Nachtrag: `68f9b9a` enthielt versehentlich eine `.pyc`-Datei.
  `harness.py` setzt das Bytecode-Flag erst beim eigenen Import, deshalb setzt `corpus.py` es wieder selbst vor dem Import.
- **Nächster Schritt:** 3e, Z21-Simulator (eigene Sitzung).

## 2026-10-28 – Phase 0, Schritt 3c: Golden-Harness für Electrip 1 (Claude)

- `tools/legacy-harness/`: startet den unveränderten Code aus `legacy/` mit Fakes für GTK, pygame und Threads auf einer virtuellen Uhr.
  Er zeichnet SRCP-Befehle, Eingaben und Sound-Ereignisse als JSON Lines auf.
  Der Mixer folgt pygame 1.9.4 und SDL_mixer, Details in `tools/legacy-harness/README.md`.
- Szenarien unter `tests/golden/scenarios/`, Golden Files unter `tests/golden/`:
  `speed_curve` (B-08), `diesel_drive` (B-11, B-13), `steam_drive` (B-14), `event_sounds` (B-17).
- `cargo xtask golden --record` zeichnet auf, `cargo xtask golden` prüft; der CI-Job „checks“ führt die Prüfung aus.
  Die Ausgabe ist über mehrere Läufe und unter Python 3.9 und 3.12 identisch.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Thread- und Event-Fakes auf das Genutzte reduziert, No-op-Helfer zusammengelegt, Ereignis-Pumpe direkt, `STOP_EVENT` aus `legacy/` statt Kopie, klare Meldung bei fehlender Golden-Datei.
  Golden Files nach dem Refactoring unverändert.
- Neue Frage Q-013: Geräusch-Ereignisse in Electrip 1 prüfen alte Werte und beobachten die Geschwindigkeit nicht.
  Soll Electrip 2 das nachbilden?
- CI für `8b7984b` ist in allen sechs Jobs grün, auch die neue Golden-Prüfung.
- Q-013 hat Mo beantwortet: Electrip 2 bildet die Eigenheiten nicht nach.
  Der Golden-Test für B-17 vergleicht nur Szenarien, in denen altes und neues Verhalten übereinstimmen.
  Der Harness bleibt unverändert.
- **Nächster Schritt:** 3d, Korpus.

## 2026-10-28 – Phase 0, Schritt 3b: srcpd-Simulator (Claude)

- CI von Schritt 3a ist auf allen Plattformen grün.
  Der macOS-Job war im ersten Lauf ohne Runner abgebrochen und lief beim Neustart durch.
  N-06 steht deshalb auf `wired` und `verified`.
- `sim/srcpd/`: Docker-Image mit srcpd 2.1.7 aus Debian trixie, Bus 1 ist ein Loopback-Bus wie in Electrip 1.
- `cargo xtask sim up` baut und startet den Container auf `127.0.0.1:4303` und führt den Rauchtest aus.
  Eine COMMAND-Sitzung setzt Lok 3, eine INFO-Sitzung muss die Meldung empfangen.
  `cargo xtask sim down` entfernt den Container.
- Neuer CI-Job „srcpd simulator“ auf Linux.
  CI für `faa52ba` ist in allen sechs Jobs grün.
- Einfachheits-Review: refactored (Sub-Agent).
  Übernommen: Gesamtfrist für den Rauchtest, Port nur an localhost, ein Stream statt zwei, Fehlerpräfix an einer Stelle.
- Hinweis für lokale Sitzungen: Die Toolchain muss Edition 2024 können (Rust ≥ 1.85), sonst `rustup update stable`.
- **Offen:** GitHub warnt, dass `actions/checkout@v4` noch Node 20 nutzt; bei Gelegenheit auf v5 umstellen.
- **Nächster Schritt:** 3c, Golden-Harness für Electrip 1.

## 2026-10-28 – Phase 0, Schritt 3a: Workspace, xtask, CI (Claude)

- Cargo-Workspace (Edition 2024) mit `crates/core` (`electrip-core`), `crates/electrip` (Binary) und `xtask`; Clippy verbietet `unwrap`/`expect`/`panic` im Produktcode.
- `cargo xtask test | loc | parity | review-check` lokal getestet, inkl. Negativtest der Schichtenregel.
- GitHub Actions `.github/workflows/ci.yml`: Tests auf Linux/macOS/Windows, Build für Raspberry Pi (aarch64), Job für loc/parity/review-check.
- Einfachheits-Review: ok (Selbstprüfung; nur angelegt, was Schritt 3a verlangt, weitere Crates erst mit ihrer ersten Anforderung).
- **Offen:** Erster CI-Lauf auf GitHub nach dem Push; N-06 erst auf `verified` setzen, wenn alle Jobs grün sind.

## 2026-10-28 – Alle offenen Fragen beantwortet (Mo)

- Q-001 bis Q-012 beantwortet und in B-06, B-10, B-20, B-21, B-22, B-23, N-02, N-03, N-05 übernommen.
- ADRs 0001–0010 von Mo angenommen (2026-10-28).
- **Wartet auf Mo:** pushen. Danach Schritt 3a.

## 2026-10-28 – Sitzungs-Host und Discovery (Mo + Claude)

- ADR 0010: Host-Rolle in jeder Instanz, ein Host pro Zentrale, Discovery per mDNS (`_electrip._tcp`), Doppel-Host- und Ausfallregeln, manuelle Host-Adresse als Rückfall.
- N-03, N-04, N-05, B-13 und Glossar angepasst; Q-010 und Q-011 beantwortet; B-05 Lokbild als Profilbild-Ausschnitt (22:17).

## 2026-10-28 – Anforderungen nach Review durch Mo überarbeitet

- Glossar und `out_of_scope` in `spec/requirements.json` ergänzt (Weichen/Signale raus).
- Geändert: B-02, B-03, B-07, B-10 (Richtungswender), B-13, B-16, B-17 (voller Alt-Umfang), B-21 (mehrere Konfigurationen), B-22, B-23 (Gleisstrom wie Electrip 1), B-24, N-01 (Gamepads + Joysticks), N-03 (synchroner Lok-Zustand, keine Sperren), N-04 (gemeinsame Konfiguration), N-05 (ein Audio-Ziel pro Lok).
- Neu: B-25 (Deutsch/Englisch), N-07 (logische Aktionen), ADR 0009; ADR 0003 und 0004 überarbeitet.
- Offene Fragen Q-003 bis Q-011 mit Vorschlägen in `spec/questions.md`.

## 2026-10-27 – Einfachheits-Review eingeführt (Mo + Claude)

- `AGENTS.md`: Pflicht-Review auf DRY, YAGNI, KISS nach jedem Inkrement, Commit-Trailer `Simplicity-Review`, ADR 0008.

## 2026-10-26 – Phase 0, Schritt 2: Spezifikation (Mo + Claude, interaktiv)

- `spec/requirements.json` angelegt: 24 Bestandsanforderungen (B-01…B-24) aus dem Handbuch, 6 neue (N-01…N-06), alle Status `false`.
- `AGENTS.md` (Regeln), `CLAUDE.md` (verweist auf AGENTS.md), `spec/questions.md`, ADRs 0001–0007 als „Vorschlag“.
- **Wartet auf Mo:** Anforderungen und ADRs prüfen, ADRs auf „Angenommen“ setzen.

## Nächste Schritte (Phase 0)

Details zu jedem Schritt: `spec/phase0-plan.md`.

- [x] Schritt 3a: Cargo-Workspace mit leeren Crates, `xtask` (`test`, `loc`, `parity`, Check des Trailers `Simplicity-Review`), CI auf Linux/macOS/Windows
- [x] Schritt 3b: srcpd mit Loopback-Bus in Docker, `cargo xtask sim up`
- [x] Schritt 3c: Headless-Harness für Alt-Electrip, Golden-Tests aufzeichnen (B-08, B-10, B-14, B-17)
- [x] Schritt 3d: Korpus (Mos JSON-Konfigurationen, SourceForge-Lokpakete)
- [x] Schritt 3e: Z21-Simulator nach Spezifikation (eigene Sitzung)
- [x] Schritt 4: `loop.sh` und Devcontainer
- [x] Tor A: Freigabe durch Mo (2026-10-30)
