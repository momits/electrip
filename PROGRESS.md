# Fortschritt

Neueste Einträge oben. Jede Sitzung ergänzt hier: Datum, Aufgabe/ID, Ergebnis, Einfachheits-Review (ok/refactored), offene Punkte.

## Aufräumkandidaten

_Befunde aus Einfachheits-Reviews, die älteren Code betreffen. Der Aufräum-Agent arbeitet sie je Phase ab._

- **Fehlende Sounddateien melden:** `import_electrip1` übernimmt die alten Pfade der Sounddateien (z. B. `/home/electrip/Lokomotiven/V 60/sound/FS1.ogg`) und prüft sie nicht.
  Fehlen die Dateien, antwortet `toggle_sound` mit `ok`, aber das Fahrgeräusch bleibt `off`, und der `import_report` bleibt leer.
  Bei Bildern steht dagegen „cannot read the picture“ im Bericht.
  Gewünscht: `import_electrip1` nennt jede fehlende Sounddatei im `import_report`, und `toggle_sound` meldet, wenn nichts gespielt werden kann.
  Behelf: Loks aus den Paketen (ZIP) mit `import_loco` laden, dann kopiert die App die Sounds in die Bibliothek.
- **Sounds vor dem Spielen laden:** `Speaker::decode` dekodiert jede Datei beim ersten Einreihen ganz und im Host-Thread (`length()` und `samples()` in `crates/audio/src/speaker.rs`).
  Gemessen für Dateien von V 60: 25 bis 46 ms je Segmentdatei, 163 ms für `stop2.ogg` im Debug-Build, 2,5 bis 11 ms im Release-Build.
  Der Mixer selbst ist lückenlos: zwei eingereihte Sounds ergaben keine Lücke auf Sample-Ebene.
  Mo hört beim Hörtest sporadisch Pausen und Knacken, vor allem wenn ein noch nie gespieltes Segment startet.
  Ob das Dekodieren die Ursache ist, ist vermutet und nicht nachgewiesen.
  Zum Prüfen: Release-Build (`cargo run --release`) und jedes Segment vorab einmal spielen.
  Lösung: alle Sounds eines Sound-Modells vorab in einem Hintergrund-Thread dekodieren, beim Laden der Konfiguration und bei Änderungen am Modell, sodass `queue` nur noch den fertigen Puffer nimmt.
- **Pfad der Bilder an einer Stelle:** `Host::media()`, `main.rs` (`library.join(media::PICTURES)`) und `ui/src/view.rs` (`picture::path(media, name)`) finden den Bildordner jeweils selbst; einheitlich über `media::picture_path` relativ zur Bibliothek. Gefunden im Review zu N-04 (Sounds).
- **Konfiguration aus dem Import bauen:** Aus `electrip1::Import` wird an drei Stellen von Hand eine `Config` gebaut (`crates/core/src/host/library.rs`, `crates/core/src/config/tests.rs`, `crates/sync/src/tests.rs`); ein `Config::from(Import)` in `core` spart das. Gefunden im Review zu N-04.
- **Achse ohne Speichern:** `SetAxis` und `Reverse` des Hosts laufen über `Host::change`, das bei jedem Befehl die Sitzung klont und das Speichern prüft; für häufige Fahrbefehle unnötig. Gefunden im Review zu N-03 (Gäste).

## 2026-11-10 – N-03: Client fährt mit seiner Konfiguration (Claude)

- CI auf `main` lief beim Start noch (danach grün). Offener Punkt „Relay“ aus „Gast über den Steuerkanal“.
- Eine Instanz, die Client ist, liest die Konfiguration, die sie als Host öffnen würde (`--file`, sonst die erste der Bibliothek), und schickt sie mit `use_configuration` auf jeder weitergeleiteten Verbindung und auf der ihrer Eingabegeräte. Das Relay überspringt dabei die Nachrichten des Hosts bis zur Antwort, sodass das Fenster nach `hello` gleich den Zustand des Gasts bekommt. Hat der Host dieselbe Konfiguration offen, bleibt alles wie bisher.
- Eine Konfiguration ohne Loks schickt die Instanz nicht (neue Instanz mit leerer Standardkonfiguration); dann fährt und ändert sie die des Hosts wie bisher. Sonst konnte ein Host, der einem anderen beitritt, nichts mehr anlegen (Test `a_host_joins_the_host_at_the_address_entered`). Wie eine Client-Instanz ihre eigene Konfiguration ändert, ist offen: Q-018.
- Tests: `control/src/tests.rs` (Client am Relay bekommt nach `hello` den Zustand des Gasts; Geräte der Instanz landen im Gast), `session_host.rs` (Client-App mit eigener Lok sieht sie, der Host nicht; Ändern abgelehnt). `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (7711 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Das Relay hielt seine Sperre, während es auf die Antwort des Hosts wartete; eine abgelehnte Konfiguration wird jetzt gemeldet. Die Regel „`--file`, sonst die erste“ steht nun in `main.rs` und `Host::open_first` (zweites Vorkommen, bleibt).
- **N-03** bleibt offen.
- **Offen:**
  - Q-018 (eigene Konfiguration auf einer Client-Instanz ändern).
  - Ändert sich die Konfiguration der Client-Instanz (Abgleich N-04), gilt das erst nach dem nächsten Rollenwechsel.
  - Übrige offene Punkte aus „Konfigurationen von Gästen im Host“ (Station und Audio im Zustand des Gasts, Sounds entfernter Loks, Punkte 5 und 6 von Q-016).

## 2026-11-10 – N-03: Gast über den Steuerkanal (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). Nächster offener Punkt aus „Konfigurationen von Gästen im Host“, Host-Seite des Steuerkanals.
- Neuer Befehl `use_configuration` mit einer Konfiguration: Der Host legt sie als Gast an (`Host::add_guest`), führt die Befehle dieser Verbindung in der Gast-Sitzung aus und schickt ihr deren Zustand; andere Verbindungen bekommen weiter den des Hosts. Senden mehrere Clients dieselbe Konfiguration, gilt die zuerst geschickte; der Gast wird entfernt, wenn sich sein letzter Client trennt. Die Konfiguration, die der Host selbst offen hat, wird kein Gast.
- Eingabegeräte, die die Verbindung vorher angeschlossen hat, entfernt der Host beim Wechsel aus der alten Sitzung. Eine ungültige Konfiguration ergibt `invalid configuration: …`.
- Tests: `control/src/tests.rs` (Gast bekommt seinen Zustand, fährt, ändert nichts an der Konfiguration, andere Clients sehen den Host; Gast bleibt, solange ein Client ihn nutzt; Geräte beim Wechsel entfernt; ungültige Konfiguration). `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (7664 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Geräte blieben nach dem Wechsel zum Gast im Host hängen (Test ergänzt); die Gast-ID steht nur noch beim Client; Fehlermeldung bei ungültiger Konfiguration.
- **N-03** bleibt offen.
- **Offen:**
  - Relay: Eine Client-Instanz öffnet ihre eigene Konfiguration und schickt `use_configuration` auf jeder weitergeleiteten Verbindung und auf der ihrer Eingabegeräte, wenn sie sich von der des Hosts unterscheidet.
  - Übrige offene Punkte aus „Konfigurationen von Gästen im Host“ (Station und Audio im Zustand des Gasts, Sounds entfernter Loks, Punkte 5 und 6 von Q-016).

## 2026-11-10 – N-03: Konfigurationen von Gästen im Host (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). Q-016 ist beantwortet; dieses Inkrement setzt die Punkte 1 bis 4 im Kern um, noch ohne Netz.
- Der Host hält neben seiner Konfiguration je Gast-Konfiguration eine eigene Sitzung (`Host::add_guest`, `remove_guest`, `guest`, `apply_guest`, Modul `crates/core/src/host/guests.rs`). Eine Konfiguration, die der Host selbst offen hat, wird kein Gast.
- Lok-IDs bleiben im Host eindeutig: Die Loks eines Gasts bekommen IDs nach denen des Hosts, der danach weiterzählt. So bleiben Senden, Abfragen und Audio-Kanäle je Lok getrennt.
- Fahrzustand je Adresse: Ändert sich der Zustand einer Lok in einer Sitzung, schickt der Host ihn einmal an die Zentrale; die Loks mit derselben Adresse in den anderen Sitzungen übernehmen ihn wie eine fremde Änderung (Fahrstufe, Richtung, Funktionen), jeweils mit ihrer eigenen Kennlinie. Meldungen der Zentrale übernehmen alle Sitzungen. Ein neuer Gast übernimmt beim Hinzufügen den Zustand der Loks mit seinen Adressen.
- Konfliktregel: Wer eine Achse zuletzt auslenkt, gewinnt; die Achsen derselben Adresse in den anderen Sitzungen werden freigegeben. Ein Nothalt gibt die Achse in allen Sitzungen frei.
- Ein Gast fährt nur (Achse, Richtung, Nothalt, Fahrgeräusch, Aktionen, Eingaben, Geräte, Gleisspannung); Änderungen an seiner Konfiguration lehnt der Host ab („change this configuration on the instance that opened it“).
- Tests: `host/guests/tests.rs` (IDs, Host fährt → Gast übernimmt und nur ein Fahrbefehl an die Zentrale, Gast fährt mit seiner Kennlinie → Host übernimmt, letzte Achse gewinnt, neuer Gast übernimmt den Zustand ohne Senden, Meldung der Zentrale, Nothalt des Gasts, Gast fährt nur, eigene Konfiguration kein Gast).
- `cargo xtask test`, `cargo xtask loc` (7592 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Ein Nothalt ließ eine ausgelenkte Achse in einer anderen Sitzung weiterrampen; jetzt wird sie überall freigegeben (Test ergänzt). `release_axes` und `send_locos` vereinfacht.
- **N-03** bleibt offen.
- **Offen:**
  - Steuerkanal: Client schickt dem Host beim Verbinden seine Konfiguration, der Host führt dessen Befehle in der Gast-Sitzung aus und schickt ihm deren Zustand; Gast entfernen, wenn sein letzter Client geht.
  - Station (verbunden, Gleisspannung), `audio_devices` und `audio_targets` stehen in der Sitzung eines Gasts noch nicht.
  - Funktionen, die eine Konfiguration nicht kennt, gehen verloren, sobald sie die Lok das nächste Mal schickt (gilt auch für Änderungen fremder Programme).
  - Sounds einer entfernten Lok oder eines entfernten Gasts laufen weiter (gilt auch für `remove_loco`).
  - Punkt 5 (Sound je Konfiguration auf ihrem Audio-Ziel) und 6 (Geräte anderer Instanzen bei der Lok) sowie die Warnung aus N-05.

## 2026-11-10 – N-05: Ausgabegerät neu öffnen (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). N-03 und N-05 hängen sonst an Q-016 und Q-017; dieses Inkrement nicht (Aufräumkandidat „Ausgabegerät wechseln“, dort als Lösung mit N-05 vorgesehen).
- Bisher öffnete der Speaker jedes Ausgabegerät einmal. Wählte man ein anderes Standardgerät, blieb der Ton auf dem alten; ein abgezogenes Gerät blieb stumm, ein Gerät, das sich nicht öffnen ließ, wurde nie wieder versucht.
- Jetzt gilt eine Ausgabe als weg, wenn ihr Stream einen Fehler meldet (`ERROR the output device failed: …`) oder, beim Standardgerät, wenn der Rechner höchstens eine Sekunde später ein anderes Standardgerät hat. Dann öffnet der Speaker sie beim nächsten Sound neu. Ein Gerät, das sich nicht öffnen lässt, versucht er jede Sekunde wieder und meldet es nur beim ersten Mal. Seine Loks spielen in der Zeit auf dem Standardgerät.
- Ein Kanal merkt sich, auf welcher Öffnung seiner Ausgabe er spielt; nach dem Neuöffnen tritt er mit seinem nächsten Sound dem neuen Mixer bei. Was gerade lief, ist dabei weg: Ein Geräusch reißt kurz ab und spielt mit dem nächsten Ereignis weiter.
- Das Standardgerät wird nicht mehr mit `open_default_sink` geöffnet, sondern wie jedes andere Gerät. Damit entfällt der Rückfall von rodio auf ein beliebiges anderes Gerät, wenn sich das Standardgerät nicht öffnen lässt.
- Tests: `speaker/tests.rs` (eine weggefallene Ausgabe wird neu geöffnet, nach einem Fehlversuch eine Sekunde später wieder versucht). Wechsel des Standardgeräts und Abziehen sind im Container nicht prüfbar; Prüfpunkte in `spec/hw-checklist.md` („N-05 – Ausgabegerät neu öffnen“).
- `cargo xtask test`, `cargo xtask loc` (7445 Zeilen) und `cargo xtask parity` grün. `target/` war wieder voll (17 GB), deshalb `cargo clean`.
- Einfachheits-Review: refactored (Sub-Agent). Ein Neuöffnen, das fehlschlug, war endgültig; jetzt wird es jede Sekunde wiederholt. DRY, YAGNI und KISS sonst ok.
- **N-05** bleibt offen.
- **Offen:**
  - Warnung bei derselben Lok-Adresse mit verschiedenen Zielen (hängt an Q-016).
  - Hörbare Latenz je Ziel messen und hier dokumentieren (Mo, Hardware).
  - `audio_devices` wird weiter nur beim Start des Hosts gelesen.

## 2026-11-10 – N-03: Client tritt einem anderen Host selbst bei (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). N-03 und N-05 hängen in großen Teilen an Q-016 und Q-017; dieses Inkrement nicht (offener Punkt aus „Host-Adresse im Fenster eintragen“).
- Bisher reichte eine Instanz, die Client ist, `join_host` an ihren Host weiter; dann trat der Host bei, und ohne mDNS blieb der Client allein zurück. Jetzt beantwortet das Relay des Clients `join_host` selbst: Es prüft das `hello` an der Adresse gegen die `id` seines Hosts, antwortet, schließt seine weitergeleiteten Verbindungen und schickt neue zum anderen Host; `follow` verbindet sich dorthin. Der bisherige Host bleibt Host.
- Dafür leitet das Relay zeilenweise statt mit `io::copy` weiter, damit seine Antwort nicht mitten in eine Nachricht des Hosts fällt.
- Fehlertext beim Beitreten zum eigenen Host oder zu sich selbst jetzt „… is already in this session“.
- Tests: `session_host.rs` (Client tritt A bei, sein Host B behält seine Loks; Hilfsfunktion `ask_to_join` mit dem Host-Fall geteilt). `spec/steuerkanal.md` und `spec/hw-checklist.md` („N-03 – Host-Adresse im Fenster eintragen“) ergänzt.
- `cargo xtask test`, `cargo xtask loc` (7391 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Fehlertext passt jetzt auch für den Client. `join_request`/`join`/`reply` stehen nun in Host und Relay hintereinander (zweites Vorkommen, bleibt nach Rule of Three). `ERROR this instance joins …` bleibt wie `ERROR this instance hands over …`.
- **N-03** bleibt offen.
- **Offen:**
  - Q-016 (verschiedene Konfigurationen an einem Host).
  - Wie schnell sich zwei Hosts nach dem Verbinden des Netzes sehen, misst Mo.

## 2026-11-10 – N-05: Latenz je Audio-Ziel messen (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). N-03 und N-05 hängen in großen Teilen an Q-016 und Q-017; dieses Inkrement nicht (offener Punkt „Latenz je Ziel messen und in der UI melden“).
- Der Host schickt jeder Instanz, die mit `offer_audio` Sounds angeboten hat, ein `ping`: gleich nach dem Angebot, dann frühestens eine Sekunde nach jedem `pong`. Der Client antwortet mit `pong`; die Zeit dazwischen steht im Zustand unter `audio_latency` (ms je Instanz). Ein `pong` einer alten Verbindung derselben Instanz zählt nicht.
- Gemessen wird der Weg Gamepad der Instanz → Host → Audio-Ereignis zurück. Nicht enthalten sind bis zu 50 ms Takt des Hosts und der Puffer des Ausgabegeräts; die hörbare Latenz misst Mo per Video (`spec/hw-checklist.md`, „N-05 – Latenz je Audio-Ziel“). Beim Host selbst gibt es keinen Netzweg, dort steht kein Wert.
- Das Fenster zeigt im Lok-Dialog unter „Tonausgabe“ hinter der Instanz-ID „· N ms“, über 300 ms rot „· N ms, zu langsam“.
- Tests: `control/src/tests.rs` (Host misst den Weg, nächster `ping` nach dem `pong`, Wert verschwindet mit der Verbindung; Relay antwortet auf `ping`), `session_host.rs` (Client-App bekommt einen gemessenen Wert), `ui/src/view/tests.rs` (Latenz je Ziel; Bildschirmfoto `loco_dialog_audio_target.png` zeigt den roten Hinweis). `spec/steuerkanal.md` ergänzt (`ping`, `pong`, `audio_latency`).
- `cargo xtask test`, `cargo xtask loc` (7325 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Die Lok trägt die Latenz ihres Ziels, so findet `contains` sie in der Liste wieder; Schwelle in der Doku „über 300 ms“ wie in der Anforderung. Im Dialog bleibt der Vergleich nach Instanz und Gerät, weil sich die Latenz bei offenem Dialog ändert.
- **N-05** bleibt offen.
- **Offen:**
  - Warnung bei derselben Lok-Adresse mit verschiedenen Zielen (hängt an Q-016).
  - Hörbare Latenz je Ziel messen und hier dokumentieren (Mo, Hardware).
  - Instanzen erscheinen nur mit ihrer Instanz-ID, ohne Namen.

## 2026-11-10 – N-05: Tonausgabe im Fenster wählen (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). N-03 und N-05 hängen in großen Teilen an Q-016 und Q-017; dieses Inkrement nicht (offener Punkt „Audio-Ziel im Fenster wählen“).
- Der Lok-Dialog (Klick aufs Bild) zeigt neben dem Bild die Liste „Tonausgabe“: Standardgerät und Ausgabegeräte des Hosts (`audio_devices`), danach je Instanz aus `audio_targets` ihr Standardgerät und ihre Geräte. Ein Ziel, das eine Lok nennt, das aber nicht verbunden ist, steht am Ende, damit es sichtbar bleibt. Die Ausgabe der Lok ist markiert; ein Klick schickt `set_audio_device`.
- Texte auf Deutsch übersetzt („Tonausgabe“, „Standardgerät“, „Sitzungs-Host“).
- Tests: `ui/src/view/tests.rs` (Reihenfolge der Ziele, nicht verbundenes Ziel, Klick im Dialog schickt `set_audio_device` mit Instanz und Gerät; Bildschirmfoto `loco_dialog_audio_target.png`). Prüfpunkte in `spec/hw-checklist.md` („N-05 – Tonausgabe im Fenster wählen“).
- `target/` war voll (18 GB), dabei wurde eine Datei beim Schreiben geleert; `cargo clean`, Datei aus Git wiederhergestellt.
- `cargo xtask test`, `cargo xtask loc` (7249 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Die Lok trägt ihr Ziel statt eines Index in die Liste, die Liste wird mit zwei Schleifen gebaut.
- **N-05** bleibt offen.
- **Offen:**
  - Instanzen erscheinen nur mit ihrer Instanz-ID, ohne Namen.
  - Warnung bei derselben Lok-Adresse mit verschiedenen Zielen (hängt an Q-016); Latenz je Ziel messen und in der UI melden (> 300 ms).

## 2026-11-10 – N-03: neue Loks bei bestehender Verbindung abfragen (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). N-03 wartet in großen Teilen auf Q-016; dieses Inkrement hängt nicht davon ab (offener Punkt aus „Zustand der Loks beim Verbinden zurücklesen“).
- Bisher fragte der Host den Zustand der Loks nur beim Verbinden ab. Jetzt fragt er jede Lok ab, die der Treiber noch nicht kennt oder deren Decoder (Adresse, Protokoll) sich geändert hat, auch bei bestehender Verbindung (`Host::send_locos`, Feld `requested`). Eine solche Lok schickt er nicht, sondern übernimmt die Antwort der Zentrale wie eine fremde Änderung. Das Verbinden nutzt denselben Weg.
- Folge: Fehler beim Abfragen während des Verbindens melden `connect` und `take_over` nicht mehr direkt. Eine abgebrochene Verbindung kommt wie beim Senden als Ereignis an und trennt.
- Test am Z21-Simulator angepasst: Eine neue Lok, die die Z21 nicht kennt, meldet sie als stehend und rückwärts; der Host übernimmt diese Richtung, die Achse fährt die Lok dann rückwärts.
- Tests: `host/tests.rs` (neue Lok wird abgefragt und nicht geschickt; Lok mit neuer Adresse wird abgefragt und übernimmt die Meldung).
- `cargo xtask test`, `cargo xtask loc` (ca. 7160 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). `decoder` in `send_locos` nur einmal geholt.
- **N-03** bleibt offen.
- **Offen:**
  - Q-016 (verschiedene Konfigurationen an einem Host).
  - Ist die Instanz Client, reicht sie `join_host` an ihren Host weiter; dann tritt dieser bei, nicht nur sie.

## 2026-11-10 – N-05: Audio-Ziel auf einer anderen Instanz (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). N-03 wartet in großen Teilen auf Q-016; dieses Inkrement von N-05 hängt nicht davon ab (Client nutzt die Konfiguration des Hosts).
- Jede Instanz hat eine feste Instanz-ID: beim ersten Start zufällig, gespeichert in der Bibliothek unter `instance`. Sie steht in `hello` und in der mDNS-Ankündigung (vorher je Start zufällig).
- Eine Lok nennt in der Konfiguration Instanz (`audio_instance`, `null` = Host) und Ausgabegerät (`audio_device`); `set_audio_device` hat dafür das optionale Feld `instance`.
- Ein Client schickt seinem Host nach dem Verbinden `offer_audio` mit Instanz-ID und Ausgabegeräten; der Zustand nennt sie unter `audio_targets`. Der Host leitet die Audio-Ereignisse jeder Lok, die diese Instanz nennt, als Nachricht `audio` über dieselbe Verbindung an sie (`Targets` in `crates/core/src/audio/targets.rs`); der Client spielt sie mit den Sounds seiner Bibliothek. Längen der Sounds rechnet weiter der Host.
- Nicht verbunden oder Verbindung weg: der Host spielt selbst auf seinem Standardgerät und meldet das einmal (`ERROR the instance … is not connected …` bzw. `… is gone …`). Wechselt eine Lok die Instanz, verstummen ihre Sounds auf der alten.
- Tests: `audio/targets/tests.rs` (Lok auf ihrer Instanz, nicht verbunden, weg, Wechsel, JSON), `host/tests.rs` (Befehl, gespeichert, `audio_targets`), `control/src/tests.rs` (Instanz-ID bleibt, Host schickt Ereignisse an den Client, Relay bietet an und spielt, Neuverbinden behält das Ziel), `session_host.rs` (Client-App ist Audio-Ziel, solange verbunden). Prüfpunkte in `spec/hw-checklist.md` („N-05 – Audio-Ziel auf einer anderen Instanz“), `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (ca. 7160 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Ein neu verbundener Client behält sein Audio-Ziel, auch wenn die alte Verbindung erst danach endet; Antwort auf `join_host` unter der Sperre, damit sie sich nicht mit Audio-Ereignissen mischt; unbekannte Audio-Ereignisse werden ausgelassen statt die Verbindung zu beenden; kleinere Vereinfachungen. Der Befehl heißt weiter `set_audio_device`, obwohl er jetzt auch die Instanz setzt (Umbenennen änderte das Protokoll).
- **N-05** bleibt offen.
- **Offen:**
  - Audio-Ziel im Fenster wählen (Phase 3, UI); Warnung, wenn zwei Konfigurationen dieselbe Lok-Adresse mit verschiedenen Zielen haben (hängt an Q-016).
  - Latenz je Ziel messen und in der UI melden (> 300 ms).
  - Ziel ist nur eine Instanz, die Client des Hosts ist; eine Instanz ohne Verbindung zum Host (z. B. Host einer anderen Zentrale) kann kein Ziel sein.
  - Die Ziel-Instanz braucht die Sounds in ihrer Bibliothek (Abgleich per N-04, setzt die Konfiguration dort voraus, Q-017); fehlt eine Datei, bleibt der Sound dort stumm.

## 2026-11-10 – N-05: Ausgabegerät pro Lok, erstes Inkrement (Claude)

- CI auf `main` beim Start grün. N-03 wartet in großen Teilen auf Q-016, N-04 ist verifiziert; N-05 war noch nicht begonnen. Dieses Inkrement hängt nicht von Q-016 ab (eine Konfiguration, Host spielt selbst).
- Jede Lok hat in der Konfiguration ein Ausgabegerät `audio_device` (Name, `null` = Standardgerät); neuer Befehl `set_audio_device`. Der Zustand nennt unter `audio_devices` die Ausgabegeräte des Hosts (beim Start gelesen).
- `AudioSink` hat zwei neue Methoden mit Vorgabe: `devices` und `route` (Lok → Gerät). Der Host meldet vor jedem Befehl und jeder Abfrage, wo jede Lok spielt.
- `Speaker` öffnet je Gerät einen Mixer, sobald dort zum ersten Mal eine Lok spielt; ein Gerät, das sich nicht öffnen lässt, meldet er einmal (`ERROR cannot open the output device …`), seine Loks spielen dann auf dem Standardgerät. Wechselt eine Lok das Gerät, verstummen ihre laufenden Sounds, die nächsten spielen auf dem neuen.
- Der Speaker hält seine Geräte selbst; `main.rs` reicht die Soundkarte nicht mehr neben dem Host durch.
- Tests: `speaker/tests.rs` (jede Lok auf ihrem Gerät, Gerätewechsel, fehlendes Gerät → Standardgerät), `host/tests.rs` (Befehl, Meldung an das Audio-Ziel, gespeichert, `audio_devices` im Zustand), Zustandstests angepasst. Prüfpunkte in `spec/hw-checklist.md` („N-05 – Ausgabegerät pro Lok“), `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (ca. 6870 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Gerätenamen nur an einer Stelle (`output_devices`), Rückfall auf das Standardgerät lesbarer, `Speaker::new`/`Output` nur noch im Crate sichtbar.
- **N-05** bleibt offen.
- **Offen:**
  - Audio-Ziel auf einer anderen Instanz: braucht eine feste Instanz-ID (heute zufällig je Start) und Audio-Ereignisse über den Steuerkanal an die Ziel-Instanz.
  - Warnung in der UI, wenn zwei Konfigurationen dieselbe Lok-Adresse mit verschiedenen Zielen haben (hängt an Q-016); Latenz je Ziel messen.
  - `audio_devices` wird nur beim Start des Hosts gelesen; ein später angestecktes Gerät erscheint erst nach einem Neustart. Ein Gerät, das während des Betriebs wegfällt, wird nicht neu geöffnet (siehe Aufräumkandidat „Ausgabegerät wechseln“).
  - Gerätenamen kommen von cpal (unter Linux/ALSA die Beschreibung, z. B. „Discard all samples …“ für `null`).

## 2026-11-10 – N-04: Status gesetzt, Frage zur ersten Übertragung (Claude)

- CI auf `main` beim Start grün. N-03 und N-05 warten in großen Teilen auf Q-016.
- Alle Akzeptanzkriterien von N-04 sind mit Tests belegt (`crates/sync/src/tests.rs`, `crates/sync/src/library/tests.rs`, `crates/control/src/sync/tests.rs`, `crates/core/src/media/tests.rs`): Lok samt Bild und Sounds kommt beim anderen Host an, getrennte Änderungen werden zusammengeführt, Abgleich gemeinsamer IDs alle 5 s mit allen per mDNS gefundenen Instanzen (auch ohne Host und Zentrale), Medien per SHA-256.
- **N-04** `wired` und `verified`.
- Neue Frage Q-017 in `spec/questions.md`: Wie kommt eine Konfiguration zum ersten Mal auf ein zweites Gerät? Heute nur als Kopie der JSON-Datei, ohne gemeinsame Geschichte beim ersten Abgleich.
- Kein Produktcode geändert; `cargo xtask parity` grün.
- Einfachheits-Review: ok (kein Code im Diff).
- **Offen:**
  - Q-017 (erste Übertragung einer Konfiguration).
  - Weiter offen aus den Einträgen davor: Zentrale beim Übernehmen der geöffneten Konfiguration, Loks nach Position statt fester ID, alte absolute Soundpfade aus `import_electrip1`.

## 2026-11-10 – N-04: Sounds in der Bibliothek und zwischen Instanzen (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). N-03 wartet in großen Teilen auf Q-016; deshalb N-04 weiter.
- Neues Modul `core::media`: Bilder und Sounds der Bibliothek heißen nach dem SHA-256 ihres Inhalts und werden über ihren Pfad in der Bibliothek angesprochen (`media/<SHA-256>.png`, `sounds/<SHA-256>.<Endung>`).
- Sounds, die `set_engine_sound`, `set_segment_sound`, `set_stroke_sound`, `add_sound_function` und `add_event_sound` setzen, kopiert der Host nach `sounds/` und trägt den Pfad relativ zur Bibliothek ein; Pakete (`import_loco`) ebenso. Der Host spielt solche Pfade aus der Bibliothek (`LibrarySink` um das Audio-Ziel). Eine Datei, die er nicht lesen kann, bleibt mit ihrem Pfad stehen (wie bisher, Electrip 1 lässt fehlende Sounds weg).
- Abgleich: `missing` nennt jetzt Bilder und Sounds als Pfad; `file`/`add_file` ersetzen `picture`/`add_picture`. `add_file` prüft, dass der SHA-256 im Pfad zum Inhalt passt; andere Pfade werden abgelehnt.
- `package::read`/`write` nehmen die Bibliothek statt einzelner Ordner.
- Tests: `media/tests.rs` (Name, Übertragung, nur Bild- und Sound-Pfade, Inhalt muss passen, fehlende Dateien, Abspielen aus der Bibliothek), `host/library/tests.rs` (Sound kommt in die Bibliothek und wird von dort gespielt), `control/src/sync/tests.rs` (Lok kommt mit Bild und Sound beim anderen Host an), Pakettests angepasst. Prüfpunkte in `spec/hw-checklist.md` („N-04 – Gemeinsame Konfiguration mit Bild und Sounds“), `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (6767 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Sound- und Bildpfad nur noch in `media` gebaut (vorher mit `Path::join`, unter Windows mit `\` und damit nicht erkannt), Hilfsfunktion in `LibrarySink` und `picture::add` eingespart.
- **N-04** bleibt offen.
- **Offen:**
  - `import_electrip1` übernimmt die alten absoluten Soundpfade; diese Sounds werden nicht übertragen (siehe Aufräumkandidat „Fehlende Sounddateien melden“). Ebenso Sounds aus Paketen, die vor diesem Inkrement mit absolutem Pfad gespeichert wurden.
  - Weitere offene Punkte wie im ersten Eintrag zum Abgleich (erster Abgleich ohne gemeinsame Geschichte, Zentrale beim Übernehmen, Loks nach Position); eine Konfiguration kommt auf ein zweites Gerät heute nur als Kopie der Datei.

## 2026-11-10 – N-04: Lokbilder per SHA-256 zwischen Instanzen (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). N-03 wartet in großen Teilen auf Q-016; deshalb N-04 weiter.
- `sync_configuration` antwortet zusätzlich mit `missing`: den Lokbildern der Konfiguration, die in der Bibliothek fehlen. Neue Anfragen `picture` (Bild als Hex nach seinem SHA-256-Namen; andere Namen werden abgelehnt, damit keine Datei außerhalb von `media/` gelesen wird) und `add_picture` (legt ein Bild unter dem SHA-256 seines Inhalts ab).
- `electrip_control::sync` holt nach dem Zusammenführen jeder gemeinsamen Konfiguration die fehlenden Bilder von der anderen Seite; hat sie das Bild auch nicht, wird es übersprungen.
- In `core`: `picture::add` und `picture::content`; `store_bytes` nutzt `add`. `image` ist Dev-Abhängigkeit von `electrip-control` (Testbild).
- Tests: `crates/control/src/sync/tests.rs` (Lok mit Bild kommt samt Bilddatei beim anderen Host an), `picture/tests.rs` (gleicher Name in einer anderen Bibliothek, nur SHA-256-Namen lesbar). `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (6662 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Kürzerer Fehler in `picture::content`, Test mit benannten Verzeichnissen, Kommentar klarer.
- **N-04** bleibt offen.
- **Offen:**
  - Sounds: Ihre Pfade in der Konfiguration sind absolut (auch die aus Paketen in `sounds/<SHA-256>.<Endung>`), auf einem anderen Gerät also falsch. Vorher müssen Sounds aus der Bibliothek relativ zu ihr in der Konfiguration stehen; danach wie die Bilder übertragen.
  - Prüfpunkt für Mo in `spec/hw-checklist.md` (zwei Rechner, Lok mit Bild und Sounds anlegen) kommt mit den Sounds.
  - Weitere offene Punkte wie im Eintrag davor (erster Abgleich ohne gemeinsame Geschichte, Zentrale beim Übernehmen, Loks nach Position).

## 2026-11-10 – N-04: Konfigurationen zwischen Instanzen abgleichen (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). N-03 wartet in großen Teilen auf Q-016; deshalb N-04 weiter.
- Zwei neue Anfragen am Steuerkanal, die der Host selbst beantwortet (wie `join_host`): `configuration_ids` nennt die IDs der Bibliothek, `sync_configuration` führt ein Automerge-Dokument (Hex) in die Konfiguration mit der ID ein und antwortet mit dem Dokument nach dem Zusammenführen.
- `electrip_control::sync(local, peer)` gleicht die gemeinsamen Konfigurationen zweier Hosts ab: eigenes Dokument holen, beim anderen einführen, Ergebnis beim eigenen einführen. Die Instanz macht das alle 5 s mit allen Instanzen, die mDNS zeigt, über den eigenen Steuerkanal (als Client also über ihren Host), auch mit Instanzen anderer Zentralen.
- Ändert der Abgleich die geöffnete Konfiguration, übernimmt der Host sie (`Host::reload`, `Session::merge`): Loks behalten nach Position ihre ID und ihren Fahrzustand, nur geänderte Loks werden ersetzt; die Zentrale bleibt, solange sie verbunden ist.
- Tests: `crates/control/src/sync/tests.rs` (zwei Hosts mit einer Kopie derselben Konfiguration führen getrennte Änderungen zusammen und zeigen sie im Zustand; unbekannte ID; Hex), `host/library/tests.rs` (Übernahme, während eine Lok fährt), `sync/library/tests.rs` (IDs). Der Abgleich per mDNS ist im Container nicht testbar (Multicast gesperrt). `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (6615 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Antwort mit Feldern nur noch über `reply`, Fehler in `sync.rs` per `?` statt sechsmal `map_err`.
- **N-04** bleibt offen.
- **Offen:**
  - Medien (Bilder, Sounds) per SHA-256 nachladen; heute kommen nur die Konfigurationen an.
  - Prüfpunkt für Mo in `spec/hw-checklist.md` (zwei Rechner, Lok anlegen, erscheint auf dem anderen) kommt mit den Medien.
  - Haben zwei Instanzen noch kein Dokument, gewinnt beim ersten Abgleich bei Listen die Seite, deren Dokument zuerst angelegt wird; erst danach werden Änderungen feldweise zusammengeführt.
  - Ändert der Abgleich die Zentrale der geöffneten Konfiguration, während sie verbunden ist, schreibt der Host beim nächsten Speichern die alte zurück.
  - Loks werden beim Übernehmen nach Position zugeordnet (wie in `update`); Abhilfe später: Loks mit fester ID.

## 2026-11-10 – N-04: Automerge-Dokument je Konfiguration in der Bibliothek (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). N-03 wartet in großen Teilen auf Q-016; deshalb N-04 weiter.
- Jede Konfiguration hat jetzt eine feste, zufällige `id` (Feld in der JSON-Datei). Sie bleibt beim Umbenennen und beim Export gleich; neue und importierte Konfigurationen bekommen eine eigene. Dateien ohne `id` (von vor N-04) bekommen beim Lesen eine und werden gleich gespeichert.
- Der Host arbeitet weiter auf den JSON-Dateien (`core` bleibt ohne Automerge). `electrip_sync::library` hält daneben je Konfiguration ein Automerge-Dokument unter `sync/<id>.automerge`:
  - `document` holt die Änderungen der JSON-Datei seit dem letzten Aufruf ins Dokument und gibt es zurück (zum Verschicken).
  - `merge` führt das Dokument einer anderen Instanz ein, speichert Dokument und JSON-Datei und meldet, ob sich die Konfiguration geändert hat. Hat die Bibliothek noch kein Dokument, beginnt sie mit dem fremden, denn nur Dokumente mit gemeinsamer Geschichte werden feldweise zusammengeführt.
  - IDs kommen von anderen Instanzen; eine ID, die kein gültiger Dateiname ist, wird abgelehnt.
- Tests: `crates/sync/src/library/tests.rs` (Dokument unter der ID, Änderungen zweier Bibliotheken landen in beiden Dateien, keine Datei außerhalb der Bibliothek), `config/tests.rs` (ID für alte Dateien), `host/library/tests.rs` (neue Konfiguration mit neuer ID, Umbenennen behält sie).
- `cargo xtask test`, `cargo xtask loc` (6440 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Jede öffentliche Funktion speichert das Dokument nur einmal.
- **N-04** bleibt offen.
- **Offen:**
  - Abgleich zwischen Instanzen: nach dem Verbinden (mDNS, Steuerkanal) IDs austauschen und gemeinsame Dokumente mit `document`/`merge` abgleichen; Medien per SHA-256 nachladen (Bilder heißen schon nach ihrem SHA-256, Sounds aus Paketen ebenso prüfen).
  - Ändert `merge` die offene Konfiguration, muss der Host sie neu laden, auch während er verbunden ist.
  - Wie kommt eine Konfiguration zum ersten Mal auf ein zweites Gerät? Heute nur durch Kopieren der JSON-Datei (gleiche `id`); Export/Import liest nur das Format von Electrip 1. Legen zwei Geräte das Dokument getrennt aus derselben Datei an, gewinnt bei Listen eine Seite ganz.

## 2026-11-10 – N-04: Konfiguration als Automerge-Dokument, erstes Inkrement (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). N-03 wartet in großen Teilen auf Q-016; N-04 war noch nicht begonnen.
- Neues Crate `electrip-sync` (ADR 0003): `Document` hält eine Konfiguration als Automerge-Dokument. `update` schreibt nur die Felder, in denen sich die neue `Config` vom Dokument unterscheidet (Maps und Listen werden durchlaufen, in Listen bleiben gleiche Einträge an Anfang und Ende stehen); `merge` übernimmt die Änderungen einer anderen Kopie; `save`/`load` speichern das Dokument.
- Damit werden Änderungen, die zwei Kopien getrennt machen, feldweise zusammengeführt; ändern beide dasselbe Feld, haben danach beide denselben Wert.
- Neue Abhängigkeit `automerge` 0.7. Im Dev-Profil sind `automerge` und `hexane` optimiert, sonst braucht das Anlegen einer Konfiguration mit 7 Loks im Test ca. 3 s statt 0,2 s.
- Tests: `crates/sync/src/tests.rs` (Konfiguration aus dem Korpus unverändert zurück, keine Änderung ohne Unterschied, getrennte Änderungen zusammengeführt, Änderung trifft die richtige Lok, wenn eine andere gelöscht wird, gleiches Feld überall gleich).
- `cargo xtask test`, `cargo xtask loc` (6360 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Unveränderte Felder werden ohne Nachschlagen im Dokument übersprungen.
- **N-04** bleibt offen; das Dokument ist noch nicht angebunden.
- **Offen:**
  - Bibliothek speichert Konfigurationen als Automerge-Dokument statt JSON (je Konfiguration eine ID), Abgleich zwischen Instanzen über mDNS und Steuerkanal, Medien per SHA-256.
  - Verschiebt ein Gerät Loks oder löscht und ergänzt in einem Schritt, vergleicht `update` die Loks in der Mitte nach Position; eine gleichzeitige Änderung des anderen Geräts kann dann die falsche Lok treffen. Abhilfe später: Loks mit fester ID.
  - Der Speicherplatz im Container ist knapp (`target/debug` ca. 16 GB, Platte voll beim ersten Test); `target/debug/incremental` gelöscht.

## 2026-11-10 – N-03: Host-Adresse im Fenster eintragen (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). Q-016 ist offen; dieses Inkrement hängt nicht davon ab.
- Rückfall ohne mDNS: Das Fenster hat neben den Ansichtsoptionen ein Feld „Host-Adresse“ mit „Beitreten“. Es schickt `join_host`; der Host prüft die Adresse (ohne Port 4711), indem er sich verbindet und `hello` liest, antwortet und wird dann wie beim Doppel-Host Client des anderen (Übergabe über `serve`).
- `hello` trägt jetzt eine zufällige `id` des Hosts. Sieht der Host beim Beitreten seine eigene `id`, ist die Adresse er selbst oder einer seiner Clients; das wird abgelehnt, sonst würden sich die Relays gegenseitig endlos weiterreichen.
- Das Fenster zeigt den Fehler seines letzten Befehls rot über dem Nothalt (bisher nur in der Konsole), z. B. „cannot reach the host …“.
- `--host` nutzt dieselbe Prüfung: ohne Port gilt 4711, erreichbar heißt `hello` binnen 2 s.
- Tests: `crates/control/src/tests.rs` (Beitreten, nicht sich selbst, nicht unerreichbar), `crates/ui/src/view/tests.rs` (Befehl, Screenshot `control_view_error.png`), `session_host.rs` (zwei Apps, eine tritt der anderen bei und reicht weiter). Prüfpunkte in `spec/hw-checklist.md` („N-03 – Host-Adresse im Fenster eintragen“), `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (6200 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Adresse auflösen und Host prüfen nur noch in `electrip_control::find_host` (auch für `--host`), eine Warte-Hilfe im Test, `hello` ohne doppelte Felder. Vorschlag, `reply` wieder nicht generisch zu machen, nicht übernommen (sonst Umwandlung des Ergebnisses beim Beitreten).
- **N-03** bleibt offen.
- **Offen:**
  - Q-016 (verschiedene Konfigurationen an einem Host).
  - Ist die Instanz Client, reicht sie `join_host` an ihren Host weiter; dann tritt dieser bei, nicht nur sie.
  - Wie schnell sich zwei Hosts nach dem Verbinden des Netzes sehen, misst Mo.

## 2026-11-10 – N-03: Doppel-Host während des Betriebs (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). Q-016 ist offen; dieses Inkrement hängt nicht davon ab.
- Sehen sich zwei Hosts derselben Zentrale während des Betriebs (z. B. nach getrenntem Netz), bleibt der mit der kleineren Instanz-ID Host (ADR 0010). Der andere prüft alle 2 s im Hintergrund, ob mDNS einen erreichbaren Host mit kleinerer ID zeigt; dann schließt er alle Verbindungen seines Steuerkanals, wird Client des anderen und meldet dort seine Gamepads an. Seine Clients finden den verbleibenden Host wie beim Host-Ausfall.
- Dafür: `Discovery` browst jetzt dauerhaft und hält die gesehenen Instanzen (`find_host` und `smaller_host` lesen nur noch daraus); `serve` nimmt eine `handover`-Funktion und gibt den nächsten Host zurück; die Instanz läuft auch als Host hinter dem Relay (eigener Port auf `127.0.0.1`), damit der öffentliche Port das Ziel wechseln kann. `main` wechselt die Rolle in einer Schleife (`session`); die Soundkarte gehört zur Host-Rolle.
- Tests: `discovery/tests.rs` (ein Host weicht nur einem Host derselben Zentrale mit kleinerer ID), `crates/control/src/tests.rs` (abgebender Host schließt alle Verbindungen, nimmt keine neuen mehr an und nennt den nächsten Host). Die Übergabe per mDNS selbst ist im Container nicht testbar (Multicast gesperrt); Prüfpunkte in `spec/hw-checklist.md` („N-03 – Doppel-Host während des Betriebs“), `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (6105 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Soundkarte mit der Host-Rolle statt zweimal geöffnet, Meldung `ERROR the mDNS daemon stopped`, kein ständig gebundener Ersatz-Listener, Meldung, wenn der alte Host nicht freigegeben werden kann.
- **N-03** bleibt offen.
- **Offen:**
  - Q-016 (verschiedene Konfigurationen an einem Host).
  - Eingabe der Host-Adresse in der UI (heute nur `--host`); die Übergabe in `session` ist dafür nutzbar.
  - Wie schnell sich zwei Hosts nach dem Verbinden des Netzes sehen, hängt davon ab, wie oft `mdns-sd` neu fragt; Mo misst das.
  - Ist die Z21 beim Start einer Instanz aus, gilt ihre Adresse als ID (wie zuvor).

## 2026-11-10 – N-03: Zentralen-ID der Z21 per Seriennummer (Claude)

- CI auf `main` beim Start grün. Q-016 ist offen; dieses Inkrement hängt nicht davon ab.
- ADR 0010 nennt als Zentralen-ID der Z21 ihre Seriennummer. Bisher galten wie bei srcpd IP, Port und Bus; zwei Instanzen, die dieselbe Z21 unter verschiedenen Namen eintragen, fanden sich deshalb nicht.
- `electrip_station_z21::serial_number` fragt die Z21 mit `LAN_GET_SERIAL_NUMBER` (2.1) und meldet sich danach mit `LAN_LOGOFF` ab; der Socket-Aufbau ist mit `Z21Station::connect` gemeinsam (`open`). `station_id` liefert für eine Z21 `z21:<Seriennummer>`; antwortet sie nicht, steht wie bisher ihre Adresse ein (`ERROR the Z21 has no id, …`).
- Tests: `telegram/tests.rs` (Telegramm und Antwort), `station_connection.rs` (ID am Z21-Simulator, Rückfall ohne Z21).
- Prüfpunkt in `spec/hw-checklist.md` („N-03 – Host per mDNS finden“).
- `cargo xtask test`, `cargo xtask loc` (6015 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: ok (Sub-Agent).
- **N-03** bleibt offen.
- **Offen:**
  - Q-016 (verschiedene Konfigurationen an einem Host).
  - Eingabe der Host-Adresse in der UI (heute nur `--host`).
  - Doppel-Host während des Betriebs.
  - Ist die Z21 beim Start einer Instanz aus, gilt ihre Adresse als ID; eine Instanz, die die Z21 später sieht, findet diesen Host dann nicht.

## 2026-11-10 – N-03: CI auf macOS rot, Steuerkanal ohne Nagle (Claude)

- CI auf `main` beim Start rot: Auf macOS dauerte `a_change_in_one_instance_shows_in_all_others_within_300_ms` 349 ms. Der Commit änderte nur `PROGRESS.md`, der Test war vorher grün, also wacklig.
- Ursache: Nagle-Algorithmus und verzögerte ACKs. `writeln!` auf einem ungepufferten `TcpStream` schreibt eine JSON-Zeile in vielen kleinen Stücken, und der Host schickt Antwort und Zustand direkt hintereinander; auf macOS warten die Pakete dann deutlich länger auf das ACK als unter Linux.
- Der Steuerkanal (Host, Weiterleitung des Clients, Gamepads des Clients) setzt jetzt `TCP_NODELAY`, und jede Zeile geht mit einem `write_all` raus, ebenso im Fenster und im Test-Client; der Netz-Proxy des Tests setzt ebenfalls `TCP_NODELAY`.
- Gemessen im Container (je 5 Läufe): Umbenennen vom Host zu beiden Clients vorher ca. 33 ms, jetzt ca. 11 ms (10 ms Netz simuliert); Lok anlegen an einem Client vorher ca. 45 ms, jetzt ca. 35 ms.
- `cargo xtask test`, `cargo xtask loc` (5981 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: ok (Sub-Agent).
- **N-03** bleibt offen; offene Punkte wie im Eintrag davor.

## 2026-11-10 – N-03: Hinweis ohne Netzwerkzugriff, sechstes Inkrement (Claude)

- CI auf `main` beim Start grün. Q-016 ist offen; dieses Inkrement hängt nicht davon ab.
- Ohne Zugriff auf das lokale Netzwerk lief die Instanz schon allein weiter, aber ohne es zu bemerken: `mdns-sd` protokolliert gescheiterte Sendungen nur intern. `Discovery::start` schickt deshalb vorher einen leeren mDNS-Kopf an `224.0.0.251:5353`; scheitert das (macOS ohne Berechtigung „Lokales Netzwerk“, kein Netz, Container: `EPERM`), meldet die App `ERROR no discovery: no access to the local network: …` und ist Host.
- Der Grund geht im `hello` des Steuerkanals als `alone` an die Clients (auch wenn ein Client nach dem Host-Ausfall ohne Discovery Host wird). Das Fenster zeigt dann über dem Nothalt einen gelben Hinweis, dass Electrip allein läuft und wie man den Zugriff erlaubt, mit dem Grund darunter (deutsch übersetzt).
- Tests: `crates/control/src/tests.rs` (`hello` mit und ohne Grund), `crates/ui/src/view/tests.rs` (Screenshot `control_view_alone.png`), `session_host.rs` (App mit Discovery: `alone` genau dann, wenn Multicast scheitert – im Container ja, in der CI vermutlich nein). Dabei den wackligen Test `an_unreachable_host_leaves_the_instance_on_its_own` repariert: Der freigegebene Port konnte an die App eines parallelen Tests gehen; jetzt Port 1.
- Dabei gefunden: Auf dem Windows-Runner lief Multicast, nachdem eine Instanz mit Discovery gelaufen war, über Loopback; `lan_ip` lieferte dann `127.0.0.1`, und eine Zentrale auf `localhost` behielt `127.0.0.1` in ihrer ID. `lan_ip` nimmt jetzt in dem Fall die Adresse der Standardroute (Ziel 192.0.2.1, es wird nichts gesendet).
- `spec/steuerkanal.md` (Feld `alone`), Prüfpunkte in `spec/hw-checklist.md` („N-03 – Ohne Netzwerkzugriff allein weiter“).
- `cargo xtask test`, `cargo xtask loc` (5973 Zeilen) und `cargo xtask parity` grün. `target/` war wieder voll (17 GB); `cargo clean`.
- Einfachheits-Review: ok (Sub-Agent). Vorschlag, `alone` immer (auch als `null`) zu schicken, nicht übernommen: `hello` ohne Grund bleibt wie bisher.
- **N-03** bleibt offen.
- **Offen:**
  - Q-016 (verschiedene Konfigurationen an einem Host).
  - Eingabe der Host-Adresse in der UI (heute nur `--host`).
  - Doppel-Host während des Betriebs; Zentralen-ID der Z21 per Seriennummer.
  - Ein Host ohne Netzwerkzugriff, den ein Client per `--host` trotzdem erreicht, schickt `alone` auch an dessen Fenster.

## 2026-11-09 – N-03: Host-Ausfall, fünftes Inkrement (Claude)

- CI auf `main` beim Start grün. Q-016 ist offen; dieses Inkrement hängt nicht davon ab.
- Lebenszeichen: Der Host schickt den Zustand mindestens jede Sekunde, auch ohne Änderung. Ein Client (Relay) hält den Host für weg, wenn er die Verbindung schließt oder 3 s lang nichts schickt; ebenso schließt er dann die weitergereichten Verbindungen.
- Danach sucht der Client per mDNS den nächsten Host seiner Zentrale, ohne den weggefallenen, mit derselben Wahlregel wie beim Start. Findet er keinen (oder ohne Discovery), wird er selbst Host: `Host::take_over` verbindet sich mit der Zentrale, ohne den Gleisstrom zu schalten, und liest Gleisstrom und Loks zurück; die Gamepads der Instanz werden beim neuen Host wieder angemeldet (auch bei einem fremden neuen Host). Der Steuerkanal bleibt auf seinem Port und reicht an den eigenen Host weiter; deshalb lauscht er jetzt auch als Client auf allen Schnittstellen.
- Das Fenster schloss sich bisher, wenn seine Verbindung abbrach, und beendete damit die App. Jetzt verbindet es sich bis zu 15 s lang neu.
- Tests: `host/tests.rs` (Übernahme ohne Schalten des Stroms), `crates/control/src/tests.rs` (Lebenszeichen jede Sekunde, stiller Host gilt nach 3 s als weg, Gamepads beim nächsten Host), `session_host.rs` (Host am Z21-Simulator beendet, der Client wird Host und zeigt die Lok mit dem Zustand der Zentrale). Z21-Hilfen der Tests nach `tests/common/changes.rs` verschoben.
- Nicht automatisch getestet: Wahl unter mehreren Clients per mDNS (Multicast im Container gesperrt) und das Neuverbinden des Fensters (keine Anzeige im Container). Prüfpunkte in `spec/hw-checklist.md` („N-03 – Host-Ausfall“).
- `cargo xtask test`, `cargo xtask sim up` (srcpd-loopback), `cargo xtask loc` (5922 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: refactored (Sub-Agent). Lesen des Relay-Ziels und Sperre der Fenster-Verbindung je in einer Funktion, `announce` ohne `Option`.
- **N-03** bleibt offen.
- **Offen:**
  - Q-016 (verschiedene Konfigurationen an einem Host).
  - Mehrere Clients mit `--host` werden nach dem Ausfall alle Host (ohne mDNS gibt es keine Wahl).
  - Doppel-Host während des Betriebs; Zentralen-ID der Z21 per Seriennummer; Hinweis in der UI ohne Netzwerkzugriff, Eingabe der Host-Adresse in der UI.
  - Die Gamepads bekommen beim neuen Host neue Nummern (B-03), Rampen und Sound starten neu (erlaubt).
  - Eine Lok, die bei bestehender Verbindung hinzukommt oder eine neue Adresse bekommt, wird nicht abgefragt.

## 2026-11-09 – N-03: Zustand der Loks beim Verbinden zurücklesen, viertes Inkrement (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). Q-016 ist offen; dieses Inkrement hängt nicht davon ab. Es bereitet den Host-Ausfall vor: Ein neuer Host muss den Zustand von der Zentrale zurücklesen.
- `CommandStation::request_loco` fragt den Zustand einer Lok ab; die Antwort kommt als Ereignis und wird wie eine fremde Änderung übernommen. Der Host fragt beim Verbinden jede Lok der Konfiguration ab.
- Z21: `LAN_X_GET_LOCO_INFO` (4.1). Der Treiber merkt sich den Decoder der abgefragten Lok und rechnet die gemeldete Fahrstufe in die Fahrstufen des Decoders um (Motorola: 28 statt 126). srcpd braucht nichts, die INFO-Sitzung beginnt mit dem aktuellen Stand (Standard-Implementierung ohne Wirkung).
- Kennt die Z21 eine Lok noch nicht, meldet sie Stillstand; der Host übernimmt dann auch die gemeldete Richtung.
- Tests: `host/tests.rs` (Abfrage jeder Lok beim Verbinden), `telegram/tests.rs` (Telegramm), Szenario `reads_back_a_loco` für beide Treiber (Motorola 28 Fahrstufen), `station_changes.rs` (App verbindet sich mit dem Z21-Simulator, während ein fremdes Programm die Lok fährt).
- `cargo xtask test`, `cargo xtask sim up` (srcpd-loopback), `cargo xtask loc` (5793 Zeilen) und `cargo xtask parity` grün. Prüfpunkt in `spec/hw-checklist.md` ergänzt.
- Einfachheits-Review: refactored (Sub-Agent). Kopierte Testschritte in `station_changes.rs` zu Hilfsfunktionen zusammengeführt, erwartete Abfragen im Host-Test als feste Liste.
- **N-03** bleibt offen.
- **Offen:**
  - Q-016 (verschiedene Konfigurationen an einem Host).
  - Lebenszeichen, Host-Ausfall und neuer Host; Doppel-Host während des Betriebs.
  - Eine Lok, die bei bestehender Verbindung hinzukommt oder eine neue Adresse bekommt, wird nicht abgefragt.
  - Zentralen-ID der Z21 per Seriennummer.

## 2026-11-09 – N-03: Änderungen fremder Programme übernehmen, drittes Inkrement (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). Q-016 ist offen; dieses Inkrement hängt nicht davon ab.
- Der Host übernimmt jetzt, was die Zentrale für eine Lok-Adresse meldet, als neuen Ausgangswert (ADR 0010, Q-010): Fahrstufe (als Geschwindigkeit in der Mitte der Fahrstufe, `SpeedCurve::speed_of_step`), Richtung und Funktionen jeder Lok mit der Adresse. Eine ausgelenkte Achse rampt von dort weiter. Er schickt den übernommenen Zustand nicht zurück.
- Was der Host selbst geschickt hat, meldet die Zentrale auch zurück. Solche Echos zählen eine Sekunde lang nicht als fremde Änderung (`crates/core/src/host/echoes.rs`). Die Z21 schaltet jede Funktion einzeln und meldet die Lok nach jedem Schritt; deshalb ist eine Meldung ein Echo, wenn Richtung mit Fahrstufe und jede Funktion zu einem kürzlich gesendeten Zustand passen.
- Dabei gefunden und behoben: srcpd meldet einen Nothalt als Fahrmodus 2, der Treiber las das als „rückwärts“; jetzt bleibt die zuletzt gemeldete Richtung. Die Z21 hat bei 128 Fahrstufen nur 126; der Treiber meldet jetzt die gesendete Fahrstufe 127 oder 128 zurück statt 126, sonst wäre die Lok bei Vmax ständig zurückgesprungen.
- Damit liest auch ein neuer Host bei srcpd den Zustand beim Verbinden zurück (die INFO-Sitzung beginnt mit dem aktuellen Stand). Bei der Z21 kommen nur Änderungen, kein Anfangsstand.
- Tests: `crates/core/src/host/tests.rs` und `host/echoes/tests.rs` (Übernahme, Rampe vom neuen Wert, Echo, unbekannte Adresse), `speed_curve/tests.rs`, `station-srcp/src/tests.rs` (Nothalt behält Richtung), `crates/electrip/tests/station_changes.rs` (App am Z21-Simulator und an srcpd: fremde Änderung übernommen, Beschleunigen bis Vmax ohne Rücksprung), Szenario `reports_the_top_steps_as_sent` für beide Treiber.
- `cargo xtask test`, `cargo xtask sim up` (srcpd-loopback), `cargo xtask loc` (5771 Zeilen) und `cargo xtask parity` grün. Prüfpunkte in `spec/hw-checklist.md` („N-03 – Änderungen fremder Programme übernehmen“).
- Einfachheits-Review: refactored (Sub-Agent). `Session::adopt` gibt die neuen Zustände zurück (keine zweite Schleife im Host), `Echoes::contains` und das Lesen der Z21-Fahrstufe einfacher.
- **N-03** bleibt offen.
- **Offen:**
  - Q-016 (verschiedene Konfigurationen an einem Host).
  - Lebenszeichen, Host-Ausfall und neuer Host; Doppel-Host während des Betriebs.
  - Z21: Anfangszustand der Loks beim Verbinden abfragen (`LAN_X_GET_LOCO_INFO`), damit ein neuer Host ihn kennt.
  - Funktionen, die die Konfiguration nicht kennt, schaltet der Host beim nächsten Senden der Lok aus, weil er den ganzen Zustand schickt (gilt schon vorher).
  - Ändert ein fremdes Programm eine Lok binnen einer Sekunde auf einen Zustand, den der Host gerade geschickt hat, übersieht der Host das.

## 2026-11-09 – N-03: Host per mDNS finden, zweites Inkrement (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). Q-016 ist offen; dieses Inkrement hängt nicht davon ab.
- Ohne `--host` sucht eine Instanz beim Start ca. 2 s per mDNS (`_electrip._tcp`, Bibliothek `mdns-sd` wie in ADR 0010) nach dem Host ihrer Zentrale und wird sein Client; sonst ist sie selbst Host (`crates/control/src/discovery.rs`).
- Jede Instanz veröffentlicht zufällige Instanz-ID, Protokollversion, Zentralen-ID und Status (`searching`, `host`, `client`). Zentralen-ID: aufgelöste IP, Port und Bus; `localhost` wird durch die LAN-Adresse des Rechners ersetzt.
- Gleichzeitiger Start: Von den suchenden Instanzen einer Zentrale wird die mit der kleinsten ID Host, die anderen warten bis zu 4 s auf sie. Von zwei Hosts wählt ein neuer Client den mit der kleineren ID. Ein gefundener Host, der nicht antwortet (abgestürzt, Eintrag noch im Cache), zählt nicht.
- Ohne mDNS meldet die App `ERROR no discovery: …` und ist Host. `--no-discovery` schaltet die Suche ab; die Tests starten die App so, damit sie sich nicht gegenseitig finden und nicht 2 s warten.
- **Im Container ist Multicast gesperrt** (`sendto` liefert `EPERM`, auch ohne Sandbox). Getestet sind deshalb nur Auswahlregel, Lesen der Ankündigung und Zentralen-ID (`crates/control/src/discovery/tests.rs`); die Suche selbst prüft Mo (`spec/hw-checklist.md`, „N-03 – Host per mDNS finden“).
- `cargo xtask test`, `cargo xtask loc` (5677 Zeilen), `cargo xtask parity` und `cargo deny check licenses bans sources` grün.
- Einfachheits-Review: refactored (Sub-Agent). Gefundener Host wird wie bei `--host` auf Antwort geprüft (`answers`), kein Leerlauf bei geschlossenem Kanal des mDNS-Daemons, `elect` einfacher, kein `clone` der Argumente.
- **N-03** bleibt offen.
- **Offen:**
  - Q-016 (verschiedene Konfigurationen an einem Host).
  - Zentralen-ID der Z21: ADR 0010 nennt die Seriennummer; heute IP, Port und Bus wie bei srcpd (braucht `LAN_GET_SERIAL_NUMBER` im Treiber).
  - Doppel-Host während des Betriebs (z. B. nach getrenntem Netz): Ein Host gibt seine Rolle heute nicht ab. Lebenszeichen, Host-Ausfall und neuer Host fehlen ebenso.
  - Eine Instanz, die Client wird, öffnet vorher trotzdem ihre Konfiguration und die Soundkarte (harmlos, nur unnötig).
  - Hinweis in der UI ohne Netzwerkzugriff, Eingabe der Host-Adresse in der UI.

## 2026-11-09 – N-03: Client mit eingetragener Host-Adresse, erstes Inkrement (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). Offen sind in Phase 3 nur noch N-03, N-04 und N-05.
- **Frage Q-016** in `spec/questions.md`: Wie arbeitet der Host mit Clients, deren Konfiguration eine andere ist, aber dieselbe Lok-Adresse enthält (Kennlinie, Funktionen, Sound-Modell, Audio-Ziel)? Davon hängen große Teile von N-03 und N-05 ab. Bis zur Antwort nutzt ein Client die Konfiguration des Hosts.
- `electrip --host <adresse:port>`: Die Instanz ist Client des Sitzungs-Hosts. Ihr Steuerkanal (nur `127.0.0.1`) reicht jede Verbindung an den Host weiter, so laufen Fenster, Tests und Skripte unverändert; ihre Gamepads schicken ihre Befehle an den Host, die Geräte-`id` mit zufälligem Versatz (`crates/control/src/relay.rs`). Ist der Host beim Start nach 2 s nicht erreichbar, ist die Instanz selbst Host.
- Der Host lauscht jetzt auf allen Netzwerkschnittstellen (ADR 0010: dem lokalen Netz wird vertraut). Trennt sich ein Client, entfernt der Host dessen Eingabegeräte, damit ihre Loks nicht mit ausgelenkter Achse weiterfahren.
- `Command` ist jetzt auch `Serialize`, damit der Client die Befehle der Gamepads weiterreichen kann.
- Tests: `crates/electrip/tests/session_host.rs` (drei Instanzen über ein Netz mit 20 ms Roundtrip, Änderung in jeder Instanz in allen anderen unter 300 ms; Geräte eines Clients gehen mit ihm; unerreichbarer Host), `crates/control/src/tests.rs` (Gamepads des Clients kommen mit Versatz beim Host an).
- `spec/steuerkanal.md`: `--host`, Lauschen auf allen Schnittstellen, Geräte beim Trennen.
- `cargo xtask test`, `cargo xtask loc` (5491 Zeilen) und `cargo xtask parity` grün. `target/` war wieder voll (18 GB); `cargo clean`.
- Einfachheits-Review: refactored (Sub-Agent). `offset_device` mit Oder-Muster, ein `broadcast` nach dem Entfernen der Geräte, Zeitlimit von 2 s beim Prüfen des Hosts, der Client endet, wenn der Host weg ist.
- **N-03** bleibt offen.
- **Offen:**
  - Q-016 (verschiedene Konfigurationen an einem Host).
  - Discovery per mDNS (`_electrip._tcp`, ADR 0010), Instanz-ID, Doppel-Host, Lebenszeichen und Host-Ausfall, Zentralen-ID, Hinweis in der UI ohne Netzwerkzugriff, Eingabe der Host-Adresse in der UI.
  - Endet der Host, endet heute auch der Client (kein Wechsel zum neuen Host).
  - Lokbilder: Der Client sucht sie in seiner eigenen Bibliothek (Übertragung mit N-04).
  - Der Versatz der Geräte-`id` hält nur, solange SDL-`id`s unter 65536 bleiben; Geräte, die ein Skript über einen weitergereichten Steuerkanal anschließt, bekommen keinen Versatz.
  - Ein langsamer Client hält heute den Host auf, weil der Host an alle Clients blockierend schreibt (gilt schon für den lokalen Steuerkanal).

## 2026-11-09 – B-03: beliebig viele Gamepads (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Umgesetzt wie von Mo beschrieben (Eintrag „B-03 geändert“ unten): `MAX_DEVICES` und `TooManyDevices` entfernt; das Feld `color` heißt jetzt `number` (Zustand, Steuerkanal, `spec/steuerkanal.md`). Ein neues Gerät bekommt die kleinste freie Nummer ab 1. Ältere Einträge mit „Farbe 1 bis 12“ sind damit überholt.
- Oberfläche: `DeviceColors` in `crates/ui/ui/control.slint` ist die Palette der acht Farben aus Mos Eintrag (Werte unverändert); `DeviceColors.of(number)` liefert `palette[(number - 1) mod 8]`. Die Kreise mit den Nummern brechen in Zeilen um, wenn viele Geräte an einer Lok hängen.
- Tests: 30 virtuelle SDL-Gamepads mit Hotplug (`crates/input/tests/hotplug.rs`); Kern-Test, dass Nummern eindeutig bleiben und frei gewordene wieder vergeben werden; Screenshots `control_view_devices.png` (30 Loks) und `control_view_wrapped.png` (9 Geräte an einer Lok); Kontrast weißer Schrift auf jeder Palettenfarbe mindestens 3:1 (WCAG). Der Test liest die Palette aus der Oberfläche.
- `cargo xtask test`, `cargo xtask loc` (5361 Zeilen) und `cargo xtask parity` grün.
- **B-03** `wired` und `verified`. Prüfpunkte in `spec/hw-checklist.md` ergänzt (Umbruch).
- Einfachheits-Review: ok (Sub-Agent). Nur ein Kommentar zur unbeschränkten Nummernsuche ergänzt.

## 2026-11-09 – B-05: Lokbild und Lautstärke im Fenster (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Klick auf das Bild einer Lok öffnet einen Dialog (`crates/ui/ui/loco.slint`): Pfad zu einem PNG oder JPEG eintragen und laden, Ausschnitt in 22:17 mit der Maus verschieben und mit dem Zoom-Regler (bis 4×) um die Mitte vergrößern, „Bild speichern“ sendet `set_picture` mit dem Ausschnitt. Der Lautstärke-Regler sendet `set_volume` beim Loslassen.
- Fehler behoben: Das Fenster suchte Lokbilder unter `media/<name>` statt `media/<name>.png` und zeigte sie nie. `electrip-ui` nutzt dafür jetzt `electrip_core::picture::path` (Abhängigkeit auf `core`).
- Tests in `crates/ui/src/view/tests.rs`: Bild im Regler sichtbar; Dialog per Maus und Tastatur bedient (Klick, Pfad tippen, Ziehen, Zoom), Screenshots `loco_dialog*.png` mit Pixelprüfung des Ausschnitts, gesendete `SetVolume` und `SetPicture` als `Command`. Deutsche Texte ergänzt, der Übersetzungstest liest beide `.slint`-Dateien.
- Prüfpunkte für Mo in `spec/hw-checklist.md`.
- `cargo xtask test`, `cargo xtask loc` (5351 Zeilen) und `cargo xtask parity` grün.
- **B-05** `verified`.
- Einfachheits-Review: refactored (Sub-Agent). Kommentar zur Begrenzung beim Ziehen, Farbformel des Testbilds nur noch an einer Stelle.
- **Offen:** Kein Dateiauswahl-Dialog des Systems (Slint hat keinen); der Pfad wird eingetippt. Vmax, Beschleunigung und Bremsen stehen noch nicht im Dialog (über den Steuerkanal erreichbar; Vmax braucht die Bestätigung aus B-09). Geräuschpegel-Balken (B-22).

## 2026-11-09 – B-03 geändert: beliebig viele Gamepads (Mo, Claude)

- Mo hat B-03 geändert: keine Obergrenze von 12 Gamepads mehr. Der Kern war schon größenunabhängig (Geräteliste ist ein Vektor); die Grenze steckt nur in `MAX_DEVICES` (`crates/core/src/input.rs`), in `add_device` (`TooManyDevices`) und in der Farbtabelle der Oberfläche.
- Neue Regel: Die Identität eines Geräts ist seine Nummer (kleinste freie, ab 1). Die Farbe ist `Palette[(Nummer - 1) mod 8]`; die Nummer steht als Ziffer im Kreis und trennt Geräte, deren Farbe sich wiederholt.
- `status.verified` von B-03 steht deshalb wieder auf `false`; `wired` bleibt.
- **Aufgabe für Phase 3 (B-03):**
  - `MAX_DEVICES` und `TooManyDevices` entfernen, das Feld `color` im Zustand umbenennen in `number` und `spec/steuerkanal.md` nachziehen.
  - `DeviceColors` in `crates/ui/ui/control.slint` durch die Palette unten ersetzen; die Farbe ergibt sich in der Oberfläche aus der Nummer.
  - Die Gerätesymbole bei einer Lok brechen um, wenn viele Geräte an ihr hängen.
  - Tests: Hotplug und Screenshot mit 30 virtuellen Geräten; Kern-Test, dass Nummern eindeutig bleiben und eine frei gewordene Nummer wieder vergeben wird; Test, dass jede Palettenfarbe gegen weiße Schrift mindestens 3:1 Kontrast hat.
- **Palette (Startwerte, für Kontrast und Unterscheidbarkeit gewählt):**
  Die Farben bauen auf der farbenblindheitssicheren Okabe-Ito-Palette auf, sind aber abgedunkelt, damit weiße Ziffern lesbar bleiben.
  Die Reihenfolge wechselt Farbton und Helligkeit, damit aufeinanderfolgende Nummern sich stark unterscheiden.
  1. `#0072B2` Blau
  2. `#D55E00` Zinnober
  3. `#00855F` Grün
  4. `#B8318A` Magenta
  5. `#8F6A00` Ocker
  6. `#5B4FB5` Violett
  7. `#00838F` Petrol
  8. `#5F6B7A` Grau
  Der Agent darf die Werte anpassen, wenn der Kontrasttest oder der Screenshot es verlangt; Reihenfolge und Zahl 8 bleiben.

## 2026-11-08 – B-25: Deutsch und Englisch (Claude)

- Vorige Sitzung brach ab; Zwischenstand auf dem Branch übernommen.
- Texte im Fenster sind englisch und mit `@tr` markiert. Die deutschen Texte stehen in `crates/ui/translations/de/LC_MESSAGES/electrip-ui.po`, Wortlaut wie in Electrip 1, wo es ihn gab („Nothalt“, „Fahrgeräusch“, „Autofokus“). `build.rs` bündelt sie ins Programm; Slint wählt beim Start die Systemsprache, sonst Englisch.
- Tests: `crates/ui/tests/translations.rs` (jeder `@tr`-Text hat eine deutsche Übersetzung), Screenshots `control_view_de.png` und `control_view_en.png` in `crates/ui/src/view/tests.rs` (die Leiste unten unterscheidet sich je Sprache).
- Prüfpunkte für Mo in `spec/hw-checklist.md` (Systemsprache).
- `cargo xtask test`, `cargo xtask loc` (5150 Zeilen) und `cargo xtask parity` grün.
- **B-25** `wired` und `verified`.
- Einfachheits-Review: ok (selbst, Diff klein).
- **Offen:** Geräuschpegel-Balken (B-22), B-24.

## 2026-11-08 – B-03: Mehrere Gamepads gleichzeitig (Claude)

- Vorige Sitzung brach ab (API-Fehler); Zwischenstand auf dem Branch übernommen. CI auf `main` grün.
- Zwölf virtuelle Geräte und Hotplug waren schon getestet (`crates/input/tests/hotplug.rs`). Neu ist der Screenshot-Prüffall in `crates/ui/src/view/tests.rs`: `control_view_devices.png` mit zwölf Geräten auf zwölf Loks; jede Lok ist in der Farbe ihres Geräts hinterlegt, darüber ein weißer Kreis mit der Nummer in dieser Farbe. Die zwölf Farben stehen im Test in einer Konstante.
- Prüfpunkte für Mo in `spec/hw-checklist.md`.
- `cargo xtask test` und `cargo xtask parity` grün.
- **B-03** `wired` und `verified`.
- Einfachheits-Review: ok (selbst, Diff klein, nur Test und Checkliste).
- **Offen:** Geräuschpegel-Balken (B-22), B-24, B-25 wie zuvor.

## 2026-11-08 – B-19: Reihenfolge der Bedienknöpfe (Claude)

- Vorige Sitzung brach ab (API-Fehler); Zwischenstand auf dem Branch übernommen. CI auf `main` grün.
- Reihenfolge und Farben gab es schon seit B-22. Neu ist der Screenshot-Prüffall in `crates/ui/src/view/tests.rs`: `control_view_buttons.png` mit allen Knöpfen ausgeschaltet; die Farben einer Pixelspalte von oben nach unten müssen Fahrgeräusch (orange), Geräusch-Funktion (blau), Geräusch-Ereignis (lachs), Lokfunktionen (grau) ergeben.
- `cargo xtask test` und `cargo xtask parity` grün.
- **B-19** `wired` und `verified`.
- Einfachheits-Review: refactored (selbst, Diff klein). Die Knopffarben stehen im Test nur noch in einer Konstante.
- **Offen:** Geräuschpegel-Balken (B-22), B-24, B-25 wie zuvor.

## 2026-11-07 – B-22: Fokus, Auto-Fokus, Filter, kompakte Regler (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Kern: Optionen der Ansicht `view` mit `auto_focus` (Standard an) und `only_active`, gespeichert mit der Konfiguration, Befehl `set_view`. Der Import aus Electrip 1 übernimmt `use_auto_focus`. „Fokus“ gab es schon (`focus` in `devices`, solange gehalten).
- Fenster: Hält ein Gerät „Fokus“, scrollt es dessen Lok in den sichtbaren Bereich (so wenig wie nötig, wie Electrip 1). Mit Auto-Fokus auch die neue Lok eines Geräts nach dem Lokwechsel; erkannt am Vergleich mit dem, was das Fenster zuletzt zeigte. Mit `only_active` nur gesteuerte oder fahrende Loks. Passen nicht alle Regler nebeneinander, werden sie schmaler (86 statt 130 px, kleineres Bild), erst danach wird gescrollt. Zwei Häkchen neben dem Nothalt senden `set_view`.
- Bewusst im `ui`: Der Filter wählt nur aus, was der Zustand schon zeigt (Geschwindigkeit, Lok der Geräte); das ist Darstellung, keine Fachlogik.
- Tests: `crates/electrip/tests/control_view.rs` (Steuerkanal: Optionen bleiben nach Neustart, Fokus halten, Lokwechsel), `crates/ui/src/view/tests.rs` (Filter, Fokus und Auto-Fokus, Screenshot `control_view_compact.png` mit zwölf Loks: kompakt und zur gesteuerten letzten Lok gescrollt, `set_view` als `Command`), Import aus dem Korpus (`use_auto_focus` an und aus).
- `spec/steuerkanal.md`: `view`, `set_view`, `focus` in `devices`, Ziele `focus` und `toggle_sound` ergänzt. Prüfpunkte für Mo in `spec/hw-checklist.md`.
- `cargo xtask test`, `cargo xtask loc` (5147 Zeilen) und `cargo xtask parity` grün.
- Der Container hatte keinen Platz mehr auf der Platte (`target/` 16 GB); `cargo clean` hat ihn freigemacht.
- **B-22** `wired` und `verified`.
- Einfachheits-Review: refactored (Sub-Agent). Breite der Regler und Schrittweite je an einer Stelle, `focus()` geradliniger, verlorene Zeile „Ergebnis“ in der Checkliste.
- **Offen:**
  - Optionaler Geräuschpegel-Balken (B-22) nicht gebaut.
  - Maussteuerung der Geschwindigkeit (B-24), Screenshot-Prüffall B-19, Übersetzungen B-25 wie im vorigen Eintrag.

## 2026-11-06 – B-22: Steuerungsansicht, erstes Inkrement (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün). Phase 3 beginnt mit der Oberfläche.
- Neues Crate `electrip-ui` (Slint, ADR 0001): Regler aller Loks nebeneinander in der Reihenfolge der Konfiguration, horizontal scrollbar. Pro Lok Name, Bild, Geschwindigkeit mit senkrechter Skala, Richtungsknopf, Knöpfe (Fahrgeräusch, Geräusch-Funktionen, Geräusch-Ereignisse, Lokfunktionen in je eigener Farbe wie Electrip 1) und Symbole der steuernden Eingabegeräte. Eine gesteuerte Lok ist in der Farbe ihres Geräts hinterlegt. Nothalt-Knopf am unteren Rand, rot bei abgeschaltetem Gleisstrom.
- Das Fenster ist ein Client des Steuerkanals (ADR 0010: ein Protokoll): Es zeigt den Zustand und sendet `reverse`, `toggle_sound`, `trigger_action` und `toggle_power`. `control` ist unverändert. Der Host läuft mit den Gamepads in einem eigenen Thread, das Fenster im Haupt-Thread. `--headless` oder fehlende Anzeige: ohne Fenster; die Tests starten die App mit `--headless`.
- `cargo xtask loc` zählt jetzt auch `.slint`-Dateien. `deny.toml` erlaubt GPL-3.0-only (Slint) und BSL-1.0, ISC, BSD-2-Clause (Crates hinter winit).
- CI: Slint braucht unter Linux fontconfig; die CI hat keine Header, und das Token darf den Workflow nicht ändern. `fontique` mit Feature `fontconfig-dlopen` lädt die Bibliothek zur Laufzeit. `cargo deny` meldet fünf nicht mehr gepflegte Crates (keine Sicherheitslücke) im winit-Backend von Slint; `deny.toml` ignoriert sie mit Begründung, bei Slint-Updates neu prüfen.
- Tests `crates/ui/src/view/tests.rs`: Reihenfolge und Beschriftung der Knöpfe, Gerätesymbole, fehlendes Bild, Knöpfe bleiben beim Fahren und Schalten dieselben Elemente, Screenshot ohne Anzeige (Software-Renderer, `target/test-logs/screenshots/control_view.png`, Farben geprüft) und die gesendeten Befehle als `Command` des Kerns.
- `cargo xtask test`, `cargo xtask loc` (5040 Zeilen), `cargo xtask parity`, `cargo deny check licenses bans sources` grün. Im Container gibt es keine Anzeige; das echte Fenster prüft Mo (`spec/hw-checklist.md`).
- Einfachheits-Review: refactored (Sub-Agent). Befund: Ein gehaltener Taster änderte seinen Zustand, das Fenster ersetzte dabei alle Knöpfe, und das Loslassen ging verloren; jetzt zeilenweise Aktualisierung mit Test. Außerdem leeres Bild statt `has-picture`, `pressed` der TouchArea, Doku zu `--headless`.
- **B-22** bleibt offen (`wired` erst, wenn alles da ist).
- **Offen:**
  - B-22: Aktion „Fokus“ und Option „Auto-Fokus“ (Standard an) scrollen die Lok in den sichtbaren Bereich; kompakte Regler bei Platzmangel; Filter „nur gesteuerte oder fahrende Loks“; Prüffall `control-channel` dafür; optional Geräuschpegel-Balken.
  - Maussteuerung der Geschwindigkeit (B-24): Die Skala zeigt die Geschwindigkeit nur an; dafür fehlt ein Befehl im Kern.
  - B-19: Reihenfolge und Farben sind schon so; es fehlt der eigene Screenshot-Prüffall.
  - B-25: Texte im Fenster stehen mit `@tr` bereit, Übersetzungen fehlen.
  - Gamepads laufen nicht mehr im Haupt-Thread; auf macOS ungeprüft (`spec/hw-checklist.md`).
  - **Nächster Schritt:** B-22 fertigstellen (Fokus, Auto-Fokus, Filter, kompakte Regler).

## 2026-11-06 – Tor C freigegeben (Mo)

- Mo hat Tor C freigegeben, Phase 2 ist abgeschlossen.
- Der Hörtest hat drei Befunde ergeben; sie stehen unter Aufräumkandidaten.
- Phase 3 beginnt mit dem Loop.

## 2026-11-06 – Loop hält: Tor C (Claude)

- CI auf `main` grün.
- Phase 0 bis 2 sind ganz verifiziert, keine Aufräumkandidaten offen, keine offenen Fragen in `spec/questions.md`.
- Phase 3 beginnt erst, wenn Mo Tor C abhakt (Hörtest und Prüfpunkte in `spec/hw-checklist.md`).
- **Wartet auf Mo:** Tor C freigeben, danach `STOP` löschen.

## 2026-11-06 – Aufräumen Phase 2 (Claude)

- CI auf `main` war rot (srcpd-Loopback), danach fiel macOS mit zwei Zeitfehlern auf; zuerst repariert, siehe Einträge B-01 und B-23 darunter.
- Phase 2 ist ganz verifiziert, Phase 3 wartet auf Tor C. Deshalb die Aufräumkandidaten abgearbeitet:
  - `spec/steuerkanal.md`: Befehle `set_engine`, `insert_segment`, `remove_segment`, `move_segment_border`, `set_engine_sound`, `set_segment_sound`, `set_stroke_sound`, `set_steam` und das Feld `sound_model` im Zustand beschrieben.
  - `driving.rs` (`time_to`) und `engine_start.rs` warten mit `Client::wait_for_loco`. `track_power.rs` wartet auf ein Feld der Zentrale, `input_devices.rs` auf mehrere Loks bzw. ein Gerät, `engine_start.rs` (`standing_until`, `drives_off`) prüft unterwegs bzw. wartet auf „ungleich“; dort passt der Helfer nicht, sie bleiben.
  - Doppeltes `allow` in `tests/common/srcpd.rs` entfernt.
  - `Loco::action_ids()`: entfällt. Nur `package.rs` liest die Aktionen; `remove_action` löscht mit `retain` aus jeder Liste und hätte von der Methode nichts.
- `cargo xtask test`, `cargo xtask sim up` (srcpd-Loopback), `cargo xtask loc` (4579 Zeilen, unverändert) und `cargo xtask parity` grün. Kein Produktcode geändert.
- Einfachheits-Review: ok (selbst, Diff von 13 Zeilen Testcode und der Doku komplett neu gelesen).
- **Nächster Schritt:** Halt mit Eintrag in `PROGRESS.md`, bis Mo Tor C abhakt.

## 2026-11-06 – B-23: Zeit ab dem Befehl zählen (Claude)

- CI des Aufräum-Branchs rot auf macOS: `input_devices.rs` (`holding_next_loco_scrolls_after_500_ms`) wechselte die Lok vor 560 ms.
- Ursache: Der Steuerkanal führt einen Befehl zwischen zwei Abfragen aus, die nächste Abfrage zählt aber die ganze Zeit seit der vorigen, also auch die vor dem Befehl. Gehaltene Lokwechsel, Rampen und Sperren beim Anlassen begannen so bis zu einer Abfrage (auf langsamen Rechnern mehr) zu früh.
- `crates/control`: Vor jedem Befehl über den Steuerkanal fährt der Host bis jetzt (`Shared::poll`), danach zählt die Zeit ab dem Befehl. Befehle der Gamepads kommen ohnehin mit der Abfrage.
- Danach fiel auf macOS `engine_start.rs` auf (Abstellen nach 0,18 s): Der Test-Diesel hatte keine Segmentgeräusche, also verstummt er beim Fahren nach dem laufenden Leerlaufgeräusch (wie Electrip 1). Dauerte die kurze Fahrt länger als ein Leerlaufgeräusch (0,3 s), endete `stopping` schon mit dessen Rest. Der Test gibt dem Diesel jetzt Segmentgeräusche; mit künstlich verlängerter Fahrt lokal nachgestellt.
- Prüffall ist der bestehende Test, der jetzt nicht mehr vom Takt abhängt. `cargo xtask test` (zehnmal `input_devices`, `engine_start`, `driving`), `cargo xtask sim up` und `cargo xtask loc` grün.
- Einfachheits-Review: ok (selbst, Diff von 20 Zeilen komplett neu gelesen).

## 2026-11-06 – B-01: srcpd-Loopback in der CI stabil (Claude)

- CI auf `main` rot: Job „srcpd simulator“ (`station_scenarios`, `connection to the SRCP server failed: Resource temporarily unavailable`); derselbe Stand war auf dem Branch grün, lokal schlugen 2 von 15 Läufen fehl.
- Ursache: srcpd lauscht mit Backlog 1 (`ss -ltn`). Verbinden sich mehrere Tests gleichzeitig, verwirft Linux das letzte ACK; der Client hält sich für verbunden, srcpd nimmt die Verbindung aber erst nach Wiederholungen des SYN-ACK an, und die Begrüßung kommt nach dem Timeout von 3 s. Electrip selbst öffnet seine zwei Sitzungen nacheinander; betroffen ist nur der Testlauf.
- `cargo xtask sim up` lässt die srcpd-Loopback-Tests jetzt nacheinander laufen (`--test-threads=1`, etwa 2 s länger).
- Dabei aufgefallen: `actions.rs` (`srcpd_gets_the_functions`) schlug nacheinander immer fehl. `expect_event` verwirft die übrigen Ereignisse; kamen die Funktionen beider Loks in derselben Abfrage an, fehlte die zweite. Jetzt erst Lok 1 auslösen und prüfen, dann Lok 2.
- `cargo xtask sim up` zehnmal hintereinander grün, `cargo xtask test` grün.
- Einfachheits-Review: ok (selbst, Diff von 15 Zeilen komplett neu gelesen).

## 2026-11-06 – B-13: Anfahren synchron zum Sound verifiziert (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Neuer Prüffall `crates/electrip/tests/sound_sync.rs` (`srcpd-loopback`, läuft mit `cargo xtask sim up`, auch in der CI): Die App ohne Soundkarte fährt einen Diesel mit WAV-Dateien bekannter Länge an srcpd. Nach dem Anlassen kommt die erste Fahrstufe > 0 erst nach zwei Leerlaufgeräuschen (dem spielenden und dem wartenden, 0,6 s) bei srcpd an, Fahrstufe 0 erst 0,5 bis 1 s nach dem Stillstand in der App (Lastgeräusch spielt, das nächste wartet). Ohne `synchronize` kommt die Fahrstufe nach 0,05 s; der Test schlägt dann fehl.
- Den Teil `audio-log` decken `driving_sound/tests.rs` und `golden_diesel_drive.rs` ab (B-13 aus 2026-11-05).
- Die WAV- und Diesel-Helfer aus `engine_start.rs` liegen jetzt in `tests/common/diesel.rs`.
- `cargo xtask test`, `cargo xtask sim up`, `cargo xtask loc` (4579 Zeilen, unverändert) und `cargo xtask parity` grün.
- **B-13** `verified`. Phase 2 ist damit ganz verifiziert. `hw: true` – Prüfpunkt für Mo in `spec/hw-checklist.md`.
- Einfachheits-Review: refactored (Sub-Agent). `seconds_until` nutzt `expect_event`, das Warten auf ein Feld der Lok ist `Client::wait_for_loco`, ein doppeltes `allow` entfernt. Ältere Kopien unter „Aufräumkandidaten“.
- **Nächster Schritt:** Phase 3 beginnt erst, wenn Mo Tor C abhakt.

## 2026-11-06 – B-12: Anlassen und Abstellen verifiziert (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Neuer Prüffall `crates/electrip/tests/engine_start.rs` über den Steuerkanal: Die App (ohne Soundkarte, sie kennt die Längen der Dateien) bekommt einen Diesel mit Anlass-, Leerlauf- und Abstellgeräusch als WAV. Beim Anlassen und beim Abstellen bleibt die Geschwindigkeit trotz voll ausgelenkter Fahrachse 0, bis `sound` auf `on` bzw. `off` steht; danach fährt die Lok los. Die Dauer passt zur Länge der Dateien.
- Den Teil `audio-log` decken die Tests aus B-11 ab (`driving_sound/tests.rs`, `host/tests.rs`), das Konfigurieren der Geräusche `sound_segments.rs`.
- `spec/steuerkanal.md`: Befehl `toggle_sound` und Feld `sound` im Zustand ergänzt.
- `cargo xtask test`, `cargo xtask loc` (4579 Zeilen, unverändert) und `cargo xtask parity` grün.
- **B-12** `wired` und `verified`.
- Einfachheits-Review: refactored (Sub-Agent). `add_quick_loco` und `set_axis` liegen jetzt in `tests/common` (auch von `driving.rs` genutzt), ein Helfer mit `Option`-Parameter ist zwei einfachen gewichen, die Doku-Zeile zu `sound` steht hinter dem Eintrag zu `speed`.
- **Offen:**
  - Phase 3: Sperre des Reglers in der UI.
  - **Nächster Schritt:** B-13 `verified` mit dem Prüffall `srcpd-loopback` (Fahrstufe an srcpd erst mit dem Übergangsgeräusch).

## 2026-11-06 – B-18: Ausgabe auf der Soundkarte (Claude)

- CI auf `main` grün.
- `electrip-audio` hat jetzt `Speaker`, das `AudioSink` auf der Soundkarte (rodio mit Feature `playback`, also cpal). `main.rs` nutzt ihn statt `NoAudio`. Ohne Soundkarte meldet die App `ERROR no sound card` und läuft weiter: Der Speaker kennt dann die Längen der Sounds, spielt aber nichts. Damit laufen die Sound-Modelle auch in der CI und im Container.
- Jeder Kanal ist eine Quelle im Mixer von rodio mit spielendem und wartendem Sound. Jeder Sound wird einmal ganz dekodiert (Cache je Datei) und ins Format der Soundkarte umgerechnet; die Abtastrate kommt aus der Datei. So folgt `queue` ohne Lücke, und `play` mit Verzögerung, `stop`, Ein- und Ausblenden wirken auf das Sample genau. Der Kanal gibt immer ganze Frames weiter, damit links und rechts beim Wechsel nicht tauschen.
- Zwei Fehler in rodio 0.23 umgangen (beides im Commit beschrieben): `Player` verliert den Anfang eines Sounds, und die Umrechnung eines OGG-Dekoders endet nach dessen leerem ersten Abschnitt. Außerdem bricht `fade_in` von rodio bei Dauer 0 ab; das Ein- und Ausblenden rechnet der Speaker selbst.
- Tests (`crates/audio/src/speaker/tests.rs`, ziehen die Samples direkt aus dem Mixer): WAV mit anderer Abtastrate als die Ausgabe, OGG aus dem Korpus, `queue` lückenlos und Ersetzen des wartenden Sounds, Kanäle gleichzeitig, `stop`, `play` mit Verzögerung, Ein- und Ausblenden, Stereo-Frames, ohne Ausgabe nur Längen.
- `cargo xtask test`, `cargo xtask loc` (4579 Zeilen) und `cargo xtask parity` grün.
- **B-18** `wired` und `verified`.
- Einfachheits-Review: refactored (Sub-Agent). Befund: Ein Sound konnte mitten im Frame beginnen (links und rechts vertauscht); behoben mit Test. `stop` als let-chain, Blende über 0 Samples ausdrücklich.
- Erledigt aus älteren offenen Punkten: Ersetzen des wartenden Sounds (B-11), `play` mit Verzögerung (B-14), Ein- und Ausblenden (B-17).
- **Offen:**
  - Die Lautstärke der Lok geht noch nicht an das `AudioSink` (wie B-11).
  - Kanäle, die nach dem Ausblenden still sind, bleiben bis zum Ende der App im Mixer (Stille, wenige je Lok).
  - Hörtest an echter Soundkarte mit Tor C (`spec/hw-checklist.md`).
  - **Nächster Schritt:** B-12 und B-13 `verified`: Die App kennt jetzt die Längen der Sounds, die Sperre beim Anlassen ist damit über den Steuerkanal prüfbar; für B-13 fehlt noch der Prüffall `srcpd-loopback`.

## 2026-11-06 – B-20: Sounds in Lok-Paketen (Claude)

- CI auf `main` grün.
- `export_loco` schreibt jetzt jede Sounddatei der Lok (Fahrgeräusch, Takte, Geräusch-Funktionen, Geräusch-Ereignisse) als `sounds/<SHA-256>.<Endung>` ins ZIP; `loco.json` zeigt auf diese Einträge. Fehlt eine Sounddatei, schlägt der Export fehl wie bei einem fehlenden Bild.
- `import_loco` legt die Sounds aus Paketen von Electrip 2 und 1 in die Bibliothek (`sounds/`, Name nach Inhalt, gleiche Dateien nur einmal) und setzt die Pfade dorthin. Ein fehlender Sound steht im `import_report` und wird weggelassen.
- `Loco::map_sounds` erreicht alle Sounddateien einer Lok an einer Stelle; `picture::content_name` teilen sich Bilder und Sounds.
- Lücke gefunden und geschlossen: Electrip 1 speicherte die Geräusch-Ereignisse bis v5.0.8 im `engine` und liest sie dort noch, wenn die Lok selbst keine `event_sounds` hat (`json_model.py`). Bei BR 81, Koef II und V 60 im Korpus ist das so; der Import hat sie bisher verloren. Jetzt übernimmt er sie wie Electrip 1 (auch beim Import von Konfigurationen).
- Tests: `package/tests.rs` (Sounds aller sechs Korpus-Pakete in der Bibliothek, Inhalt gleich dem Archiv, Export und Import mit Sounds, fehlender Sound beim Import und Export), `electrip1/tests.rs` (Geräusch-Ereignisse im `engine`), `crates/electrip/tests/loco_packages.rs` über den Steuerkanal. `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (4387 Zeilen) und `cargo xtask parity` grün.
- **B-20** `wired` und `verified`.
- Einfachheits-Review: ok (Sub-Agent). Der optionale Vorschlag, die Geräusch-Ereignisse gleich nach dem Lesen aus dem `engine` zu verschieben, wäre nicht kürzer geworden (zwei Lesestellen).
- **Offen:**
  - Sounds, die keine Lok mehr nutzt, bleiben in `sounds/` der Bibliothek liegen (wie Bilder in `media/`).
  - Phase 3: Export und Import in der UI.

## 2026-11-06 – B-17: Geräusch-Ereignisse (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Neues Modul `event_sound.rs` wie `EventSoundPlayer` in Electrip 1: Jede Lok hat `event_sounds` mit Aktion, Name, Sounddatei, `default_active`/`active`, Richtung `forward` (`true`, `false` oder `null`), `min_speed`/`max_speed`, `min_accel`/`max_accel` (`null` = beliebig), `fade_in`/`fade_out` in Sekunden und `play_to_end`.
  Es spielt nur, wenn die Lok ein Sound-Modell hat (auch bei ausgeschaltetem Fahrgeräusch, wie Electrip 1), jedes auf einem festen Kanal über dem Fahrgeräusch; die Geräusch-Funktionen spielen jetzt darüber. Solange die Bedingungen gelten, läuft es im Loop (mit Einblenden bei jedem Start wie Electrip 1); gelten sie nicht mehr, blendet es einmal aus, außer bei `play_to_end`.
- Wie in Q-013 entschieden prüft der Host bei jeder Abfrage mit den aktuellen Werten. Die Beschleunigung ist die Änderung der Geschwindigkeit seit der letzten Abfrage (wie im Docstring von `EventSound` in Electrip 1: „derivation of loco.speed“). Anders als Electrip 1 heißt das: Steht die Lok bei gehaltener Bremse, ist a = 0 und das Bremsenquietschen blendet aus. Ebenfalls anders (gleiche Art Fehler wie Q-013 Punkt 3): Electrip 1 prüfte die Richtung „rückwärts“ (`false`) nie; Electrip 2 prüft sie.
- `AudioSink` hat `fade_in(channel, sound, fade)` und `fade_out(channel, fade)`. Befehle `add_event_sound` und `remove_event_sound`; `trigger_action` schaltet beim Drücken auch die Geräusch-Ereignisse aktiv/inaktiv. Gespeichert wird `active` wie `default_active`.
- Import aus Electrip 1 und Lok-Pakete übernehmen die Geräusch-Ereignisse; ein Ereignis ohne Knopf bekommt eine Aktion mit seinem Namen (V 60 „Bremsen“). Im Korpus hat die V 60 „Anfahren“ `fade_in` 500 und `fade_out` 1000 – in Electrip 1 sind das Sekunden; übernommen wie in der Datei.
- Golden-Test `golden_event_sounds.rs`: Anfahrpfiff (Start mit Einblenden 300 ms, Ende nach `play_to_end`) und Start des Bremsenquietschens stimmen auf eine Abfrage (50 ms) genau mit `tests/golden/event_sounds.jsonl`. „Rollen“ und das Ende des Quietschens weichen wie oben und in Q-013 beschrieben ab; der Test prüft dafür das Verhalten von Electrip 2.
- Weitere Tests: `event_sound/tests.rs`, `session/tests.rs`, `electrip1/tests.rs` (Korpus), `package/tests.rs`, `crates/electrip/tests/event_sounds.rs` über den Steuerkanal. `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (4304 Zeilen) und `cargo xtask parity` grün.
- **B-17** `wired` und `verified`.
- Einfachheits-Review: refactored (Sub-Agent). Kleinigkeiten: Umschalten als Filter-Schleife, ein unnötiges `let mut` und ein `clone` im Test entfernt.
- **Offen:**
  - Phase 3: Knöpfe der Geräusch-Ereignisse und ihr Bearbeiten in der UI; dort auch nur anbieten, wenn ein Fahrgeräusch konfiguriert ist.
  - Wird ein Geräusch-Ereignis entfernt, während es spielt, spielt sein Kanal zu Ende; die folgenden rücken einen Kanal nach.
  - Die Lautstärke der Lok geht noch nicht an das `AudioSink` (wie B-11).
  - Die Soundausgabe (B-18) muss Ein- und Ausblenden können.

## 2026-11-06 – B-16: Geräusch-Funktionen (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Neues Modul `function_sound.rs` wie `FunctionSoundPlayer` in Electrip 1: Jede Lok hat `sound_functions` mit Aktion, Name, Sounddatei und Modus `switch` (Loop bis zur zweiten Auslösung), `push_once` (höchstens einmal, Abbruch beim Loslassen), `push` (Loop, solange gehalten) und `tap` (bis Dateiende, Auslösungen dazwischen tun nichts; Standard wie Electrip 1).
  Jede spielende Geräusch-Funktion hat einen eigenen Kanal oberhalb der Kanäle des Fahrgeräuschs (der erste freie). Sie spielen wie in Electrip 1 auch ohne laufendes Fahrgeräusch und ohne Sound-Modell.
- Befehle `add_sound_function`, `remove_sound_function`, `move_sound_function` (wie bei Lokfunktionen; Entfernen und Verschieben teilen sich jetzt zwei kleine Listenhelfer mit Lokfunktionen und Loks). `trigger_action` schaltet auch die Geräusch-Funktionen und läuft deshalb im Host (braucht das `AudioSink`); es speichert die Konfiguration nicht mehr, weil sich dabei nichts Gespeichertes ändert.
- Der Import aus Electrip 1 und die Lok-Pakete übernehmen die Geräusch-Funktionen mit Knopf-Aktion wie bei Lokfunktionen. Damit nennt der `import_report` im Korpus mehr Knöpfe, die zugleich eingebaute Aktion sind (Q-015): in `settings.json` zusätzlich Knopf 5, in `packages.json` die Knöpfe 0, 1, 3 und 4.
- Tests: `function_sound/tests.rs` (alle Modi, Kanäle), `host/tests.rs` (virtuelles Gamepad und Audio-Log), `session/tests.rs`, `electrip1/tests.rs` (Korpus), `package/tests.rs`, `crates/electrip/tests/sound_functions.rs` über den Steuerkanal. `spec/steuerkanal.md` ergänzt.
- `cargo xtask test`, `cargo xtask loc` (4083 Zeilen) und `cargo xtask parity` grün.
- **B-16** `wired` und `verified`.
- Einfachheits-Review: refactored (Sub-Agent). Die Suche nach dem freien Kanal ist eine eigene kleine Funktion.
- **Offen:**
  - Phase 3: Knöpfe der Geräusch-Funktionen in der UI (Anschalter gesperrt, solange er spielt).
  - Wird eine Geräusch-Funktion, ihre Aktion oder die Lok gelöscht, während ein Loop spielt, spielt der Kanal noch bis zu zwei Sounds zu Ende (wie beim Fahrgeräusch, B-11).
  - Die Lautstärke der Lok geht noch nicht an das `AudioSink` (wie B-11).

## 2026-11-05 – B-14: Fahrgeräusch Dampf (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Neues Modul `steam_sound.rs` wie `SteamSoundController` in Electrip 1: Bei laufender Maschine läuft das Leerlaufgeräusch in Schleife. Fährt die Lok, folgen die Zylindertakte aufeinander, jeder auf einem eigenen Kanal. Die Pause ist eine Radumdrehung (3,6 · Durchmesser · π / Geschwindigkeit) geteilt durch die Takte, höchstens 1 / minimale Taktfrequenz.
  Beim Anfahren kommt erst der Zylinderdampf und nach der Verzögerung der erste Takt, außer der Dampf läuft noch. Ein- und Ausschalten wirkt sofort, die Geschwindigkeit bleibt frei, und die Lok wartet nicht auf den Sound (anders als beim Diesel, B-13).
- `AudioSink` hat jetzt mehrere Kanäle je Lok (`ChannelId { loco, nr }`) und `play(channel, sound, delay)`: Ein Takt, der vor der nächsten Abfrage fällig ist, geht mit seiner Verzögerung raus. Bei hoher Geschwindigkeit sind die Takte kürzer als 50 ms.
- Sound-Modell: `steam` (`strokes`, `wheel_diameter`, `start_delay`, `min_frequency`, Standard wie Electrip 1), Motorgeräusch `cylinder` und je Segment `strokes` (Sounddatei je Taktnummer). Neue Befehle: `set_steam { loco, steam }` und `set_stroke_sound { loco, segment, stroke, path }`. Der Import aus Electrip 1 übernimmt alles.
- Golden-Test `golden_steam_drive.rs`: Alle 320 Sound-Ereignisse aus `tests/golden/steam_drive.jsonl` stimmen in Reihenfolge und Sound. Das Leerlaufgeräusch stimmt auf die Mikrosekunde. Dampf und Takte kommen genau eine Abfrage (50 ms) später, auf 20 µs genau; das ist der bekannte Versatz der Beschleunigung (B-10, siehe B-13).
  Der Test-Mixer aus dem Diesel-Test liegt jetzt in `crates/core/tests/common/mod.rs` und kann mehrere Kanäle und verzögerte Sounds.
- Weitere Tests: `steam_sound/tests.rs`, `sound/tests.rs`, `driving_sound/tests.rs`, `electrip1/tests.rs` (Korpus mit BR 81), `crates/electrip/tests/sound_segments.rs` über den Steuerkanal.
- `cargo xtask test`, `cargo xtask loc` (3877 Zeilen) und `cargo xtask parity` grün.
- **B-14** `wired` und `verified`. `hw: true`, Prüfpunkte in `spec/hw-checklist.md` (Hörtest, Tor C).
- Einfachheits-Review: refactored (Sub-Agent). Die Wertebereiche sind privat. Ungültige Dampfwerte aus einer kaputten Datei ergeben keine Pause mehr und damit keine Takte; vorher hätte Raddurchmesser 0 den Host in eine Endlosschleife geschickt. Eine Testfunktion ist geteilt.
- **Offen:**
  - Ändert sich die Taktzahl, während das Fahrgeräusch läuft, gilt sie erst nach dem nächsten Einschalten.
  - Weniger Takte lassen die Sounddateien der höheren Taktnummern im Modell stehen; sie werden nicht gespielt.
  - Die Soundausgabe (B-18) muss `play` mit Verzögerung können (rodio: `Source::delay`).

## 2026-11-05 – B-13: Anfahren synchron zum Sound (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Läuft das Fahrgeräusch, folgt die Lok dem Sound wie in Electrip 1: Sie bekommt eine Fahrstufe > 0 erst, wenn das Beschleunigungsgeräusch Leerlauf → Segment 1 beginnt, und Fahrstufe 0 erst, wenn das Bremsgeräusch Segment 1 → Leerlauf beginnt.
  Bis dahin behält sie die zuletzt gesendete Fahrstufe und Richtung, wie Electrip 1, das in dieser Zeit gar nichts sendet. Funktionen gehen sofort raus.
- `DrivingSound` merkt sich, wohin der gerade spielende Sound führt (aus der Länge der Dateien, ADR 0004). `DrivingSound::synchronize` macht daraus den Zustand, den der Host an die Zentrale schickt.
- Golden-Test `golden_diesel_drive.rs` vergleicht jetzt auch die Befehle an die Zentrale mit den SRCP-Befehlen von Electrip 1 in `tests/golden/diesel_drive.jsonl`: Start bei 7,7 s mit Stufe 36 und Halt bei 31,2 s stimmen genau. Ohne die Änderung startet die Lok schon bei 4,75 s.
  Verglichen werden nur Anfahren und Anhalten. Die Stufen dazwischen kommen in Electrip 2 eine Abfrage (50 ms) später als in Electrip 1; das kommt von der Beschleunigung (B-10), nicht vom Sound.
- Unit-Tests in `driving_sound/tests.rs`.
- `cargo xtask test`, `cargo xtask loc` (3627 Zeilen) und `cargo xtask parity` grün.
- **B-13** `wired`; `verified` folgt wie bei B-12, wenn die App eine echte Ausgabe hat und das über srcpd prüfbar ist (Prüfart `srcpd-loopback`). `hw: true` – Prüfpunkt für Mo kommt mit dem Hörtest (Tor C).
- Einfachheits-Review: refactored (Sub-Agent). `synchronize` ist nur noch im Crate sichtbar.
- **Offen:** Befehle wie Richtungswechsel und Funktionen gehen in Electrip 2 erst mit der nächsten Abfrage an die Zentrale (bis 50 ms später als in Electrip 1). Das betrifft ältere Anforderungen; bei Bedarf als eigene Aufgabe.

## 2026-11-05 – B-11: Fahrgeräusch Verbrennungsmotor (Claude)

- CI auf `main` grün.
- Neuer Trait `AudioSink` (`crates/core/src/audio.rs`, ADR 0004): `length`, `queue` (spielt sofort oder lückenlos nach dem laufenden Sound, ersetzt einen wartenden) und `stop`, je Lok ein Kanal mit der Nummer der Lok.
  Der Host führt je Kanal mit, wie lange der Sound noch läuft (aus der Dateilänge, nicht aus der Wiedergabe).
- Neues Modul `driving_sound.rs`: das Fahrgeräusch wie `DieselSoundController` in Electrip 1. Der Kanal hält immer den nächsten Sound; je Sound ein Segment hoch (Beschleunigungsgeräusch) oder runter (Bremsgeräusch), dazwischen Last- bzw. Leerlaufgeräusch im Loop.
  Im Zustand der Lok steht `sound` jetzt als `off`, `starting`, `on` oder `stopping` statt `true`/`false`.
- Teil von B-12: Anlassen spielt Anlass- und Leerlaufgeräusch, Abschalten im Stand wartet auf den Leerlauf und spielt das Abstellgeräusch. Währenddessen bleibt die Geschwindigkeit stehen, und der Schalter ist gesperrt wie in Electrip 1. Ein- und Ausschalten während der Fahrt startet mit dem Lastgeräusch bzw. verstummt sofort.
- Befehle `set_engine_sound { loco, sound: start|idle|quit, path }` und `set_segment_sound { loco, segment, sound: load|idle|accel|decel, path }`; `path: null` entfernt den Sound. Die Pfade sind Dateien auf dem Host.
- Der Import aus Electrip 1 übernimmt Motor, Geräusche und Segmente. Bei Dampf vorerst nur das Leerlaufgeräusch und die Segmente (B-14).
- Golden-Test `crates/core/tests/golden_diesel_drive.rs`: Das Szenario `diesel_drive` läuft über Import, Gerät „Electrip 1“ und `poll` alle 50 ms. Ein Test-Mixer wie pygame vergleicht alle 54 Sound-Ereignisse mit `tests/golden/diesel_drive.jsonl`; sie stimmen auf die Mikrosekunde.
- Weitere Tests: `audio/tests.rs`, `driving_sound/tests.rs`, `host/tests.rs` (Geschwindigkeit gesperrt beim Anlassen), `electrip1/tests.rs` (Korpus mit Geräuschen), `crates/electrip/tests/sound_segments.rs` über den Steuerkanal.
- `cargo xtask test`, `cargo xtask loc` (3607 Zeilen) und `cargo xtask parity` grün.
- **B-11** `wired` und `verified`. **B-12** `wired`; `verified` folgt, wenn die App mit echter Ausgabe die Sperre auch über den Steuerkanal zeigen kann.
- Einfachheits-Review: refactored (Sub-Agent). `AudioSink::length` liefert eine `Duration`, ein Test-Helfer mit nur einem Aufrufer ist entfallen, Tupel-Zuweisungen sind jetzt einzelne Zuweisungen.
- **Offen:**
  - Die App hat noch keine Ausgabe: `main.rs` nutzt `NoAudio` (keine Datei hat eine Länge, das Fahrgeräusch bleibt aus). Die Ausgabe auf der Soundkarte mit rodio kommt mit B-18. Der Kanal muss dort einen wartenden Sound ersetzen können.
  - Die Lautstärke der Lok geht noch nicht an das `AudioSink`.
  - Wird eine Lok gelöscht oder eine andere Konfiguration geöffnet, spielt ihr Kanal noch bis zu zwei Sounds zu Ende.
  - Lok-Pakete (B-20) übernehmen die Sounddateien noch nicht in die Bibliothek; die Pfade bleiben relativ zum Paket.
  - B-13 (Fahrstufe synchron zum Übergangsgeräusch) ist noch nicht gebaut (inzwischen erledigt, siehe oben).

## 2026-11-05 – B-15: Geräuschsegmente bearbeiten (Claude)

- CI auf `main` lief beim Start noch (letzter Lauf vorher grün).
- Neues Modul `crates/core/src/sound.rs`: Jede Lok hat ein Sound-Modell (`sound_model`, im Zustand `null` = „Kein Geräusch“) mit Motor `diesel` oder `steam` und Segmenten über den Geschwindigkeitsbereich.
  Ein Segment speichert nur, bei welcher Geschwindigkeit (km/h) es beginnt; es endet beim nächsten oder bei Vmax. Die Geräusche je Segment kommen mit B-11 und B-14.
- Befehle: `set_engine { loco, engine, confirmed }` (neues Modell mit einem Segment wie in Electrip 1; ein anderes Modell ersetzen braucht eine Bestätigung), `insert_segment` (teilt das Segment in der Mitte, das neue liegt rechts), `remove_segment { …, confirmed }` (der linke Nachbar übernimmt die Geschwindigkeiten; das letzte Segment löschen setzt nach Bestätigung auf „Kein Geräusch“), `move_segment_border { loco, segment, speed }` (nur zwischen den Nachbargrenzen, sonst ignoriert wie bei den Punkten der Geschwindigkeitskurve).
- Bewusst anders als Electrip 1: Beim Löschen des ersten Segments übernimmt der rechte Nachbar (Electrip 1 verlängerte durch `index - 1` = -1 das letzte Segment). Eine neue Vmax streckt die Segmentgrenzen mit.
- Tests: `sound/tests.rs`, `loco/tests.rs` (Bestätigungen, Vmax), `crates/electrip/tests/sound_segments.rs` über den Steuerkanal.
- `cargo xtask test`, `cargo xtask loc` (3225 Zeilen) und `cargo xtask parity` grün.
- **B-15** `wired` und `verified`. Offen für Phase 3: Segmentleiste mit Ziehen und Bestätigungsdialog in der UI. Der Import aus Electrip 1 übernimmt die Segmente noch nicht (kommt mit den Geräuschen, B-11/B-20).
- Einfachheits-Review: ok (Sub-Agent).

## 2026-11-05 – B-18: WAV und OGG dekodieren (Claude)

- Neues Crate `electrip-audio` (`crates/audio/`): `open(path)` öffnet eine WAV- oder OGG-Datei mit rodio (Dekoder von symphonia). Abtastrate und Kanalzahl kommen aus der Datei, eine Einstellung dafür gibt es nicht.
- rodio läuft vorerst ohne das Feature `playback`. Das zieht cpal nach, und cpal braucht unter Linux die ALSA-Header (`libasound2-dev`), die weder im Container noch auf den CI-Runnern installiert sind (kein sudo im Container).
- Tests (`crates/audio/src/tests.rs`): alle Sounds der sechs Lok-Pakete im Korpus werden dekodiert, darunter WAV mit 22.050 Hz 8 Bit mono und 44.100 Hz 16 Bit stereo sowie OGG mono und stereo. Kaputte und fehlende Dateien ergeben einen Fehler.
- `cargo xtask test`, `cargo xtask loc` (3059 Zeilen) und `cargo xtask parity` grün.
- Einfachheits-Review: ok (selbst, Diff komplett neu gelesen; der Diff hat rund 80 Zeilen).
- **B-18 bleibt offen** (`wired` false): „werden abgespielt“ braucht die Ausgabe über `AudioSink`. Die kommt mit dem ersten Sound-Modell (B-11).
- `deny.toml` erlaubt jetzt MPL-2.0 (symphonia) und BSD-3-Clause (`encoding_rs`, von symphonia gebraucht). Beide sind mit der GPL-3.0 verträglich, ohne sie geht symphonia nicht. Mo hat beide am 2026-11-05 bestätigt.
- **Wartet auf Mo:** Für die Ausgabe auf der Soundkarte müssen `libasound2-dev` ins Devcontainer-`Dockerfile` und in die CI (Ubuntu und die arm64-Cross-Build für den Raspberry Pi). Bis dahin bauen die Sound-Modelle gegen ein `AudioSink`, das nur Ereignisse protokolliert (ADR 0004).

## 2026-11-05 – Phasen neu geordnet: Sound vor Oberfläche (Mo + Claude)

- Phase 1 ließ sich nicht schließen: B-03 und B-05 brauchen Screenshot-Tests der Oberfläche, B-20 braucht Sounds und Audioformate.
- Mo hat Option D gewählt (ADR 0011): Phase 1 Kern, Phase 2 Sound (B-11 bis B-18, B-20), Phase 3 Ausbau (Oberfläche, Multi-Client, Sync, Audio-Ziel), Phase 4 Abnahme.
- `phase` in `spec/requirements.json` geändert: B-11 bis B-18 und B-20 → 2; B-03, B-05, B-19, B-22, B-25, N-03, N-04, N-05 → 3.
  Phase 1 ist damit ganz verifiziert. Mo hat Tor B freigegeben (siehe unten).
- Tore: B Kern, C Sound (Hörtest bei Mo), D alles verifiziert, E Release. `spec/konzept.md` und `AGENTS.md` angepasst.
- **Hinweis:** „Phase 2“ in älteren Einträgen meint die Oberfläche, jetzt Phase 3.
- Mo hat ADR 0011 auf „Angenommen“ gesetzt.

## 2026-11-05 – Tor B freigegeben (Mo)

- Mo hat Tor B freigegeben, Phase 1 ist abgeschlossen.
  Der Fahrtest an der echten Anlage und die Z21-Prüfung an echter Hardware (`spec/hw-checklist.md`) bleiben Aufgaben von Mo und blockieren Phase 2 nicht.
- **Nächster Schritt:** Phase 2 im Loop, zuerst B-18 (Audioformate) und der Sound-Golden-Test.


## 2026-11-05 – B-21: verifiziert (Claude)

- Die drei Akzeptanzkriterien sind mit den Prüfarten `corpus` und `unit` abgedeckt:
  - Anlegen, umbenennen, löschen, wechseln: `crates/electrip/tests/configurations.rs` (`configurations_are_managed_and_kept`).
  - Import aus Electrip 1: `electrip1/tests.rs` (`the_corpus_is_imported_without_loss`) und `crates/electrip/tests/electrip1_import.rs` über den Steuerkanal.
  - Export als Datei: `export_writes_the_configuration_to_a_file`.
- „Verlustfrei“ gilt mit Q-015 (beantwortet am 2026-11-03): Was der Import auslässt, nennt der `import_report` (Knopf mit eingebauter Aktion und Funktion, Bilder in den Lok-Paketen).
- `cargo xtask test` und die genannten Tests grün. Kein Code geändert, daher kein Einfachheits-Review nötig.
- **B-21** `wired` und `verified`. Offen für Phase 2: Bedienung der Konfigurationen in der UI.

## 2026-11-05 – N-02: Prüfung des Z21-Treibers gegen die Spezifikation (Claude)

- Das PDF (Version 1.13, SHA-256 aus `sim/z21/README.md` stimmt) wurde mit `pdftotext` gelesen und `crates/station-z21` Kapitel für Kapitel verglichen.
  Der Code des Simulators wurde nicht gelesen.
- Geprüft und in Ordnung: Datensatz und Prüfsumme (1.2), kombinierte Pakete (1.3), Abmelden und Keepalive (1.1, 2.2), Gleisstrom und Nothalt (2.4–2.14), Broadcast-Flags (2.16), Lok-Modus (3.2), Fahrstufen-Codierung für 14, 28 und 128 (4.2), Einzelfunktionen (4.3.1) und Lok-Info mit Funktionen F0–F28 (4.4).
- **Abweichung behoben:** Das Format-Byte `0x1S` sagt der Z21 auch, ob die Lok Motorola I oder II ist, und bei Motorola II, ob sie 14 oder 28 reale Fahrstufen hat (4.2).
  Der Treiber sendete für Motorola II mit 14 Fahrstufen S=0 (Motorola I, nur F0) und für 28 Fahrstufen S=2.
  Jetzt gilt: Motorola I S=0, Motorola II mit 14 Stufen S=2, mit 28 Stufen S=3.
  Die Z21 rechnet die DCC-Fahrstufe selbst in die reale um, deshalb skaliert der Treiber die Stufe des Hosts auf die DCC-Stufen des Formats und die Lok-Info zurück.
- Nicht übernommen: F29–F31 in der Lok-Info (DB8) werden nicht gelesen. Der Treiber schaltet nur bis F28 (`MAX_FUNCTION`).
- Offen: Die Spezifikation nennt die Umrechnung von DCC- in MM-Stufen nicht; ob die Z21 die Skalierung wie angenommen deutet, prüft Mo an der echten Z21 (`spec/hw-checklist.md`).
- Tests: `telegram/tests.rs` (Format je Protokoll, Hin- und Rückskalierung aller Stufen). `cargo xtask test`, `cargo xtask loc` (3049 Zeilen) und `cargo xtask parity` grün.
  Szenario-Suite `station_scenarios` mit `--include-ignored --test-threads=1`: 8 Tests gegen srcpd und 7 gegen den Z21-Simulator grün.
- **Auffällig, nicht von dieser Änderung:** `cargo xtask sim up` bricht auf `main` und auf diesem Branch bei `tests/actions.rs` (`srcpd_gets_the_functions`) ab; die srcpd-Szenarien laufen parallel nur mit Zeitüberschreitung, einzeln grün.
- Einfachheits-Review: ok (selbst, Diff komplett neu gelesen).

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
