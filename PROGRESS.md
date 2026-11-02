# Fortschritt

Neueste Einträge oben. Jede Sitzung ergänzt hier: Datum, Aufgabe/ID, Ergebnis, Einfachheits-Review (ok/refactored), offene Punkte.

## Aufräumkandidaten

_Befunde aus Einfachheits-Reviews, die älteren Code betreffen. Der Aufräum-Agent arbeitet sie je Phase ab._

- (noch keine)

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
