# Fortschritt

Neueste Einträge oben. Jede Sitzung ergänzt hier: Datum, Aufgabe/ID, Ergebnis, Einfachheits-Review (ok/refactored), offene Punkte.

## Aufräumkandidaten

_Befunde aus Einfachheits-Reviews, die älteren Code betreffen. Der Aufräum-Agent arbeitet sie je Phase ab._

- (noch keine)

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
- **Offen:** Commit, Push und CI-Lauf.
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
- **Offen:** Der Commit mit der Antwort auf Q-013 ist noch nicht gepusht.
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
- [ ] Schritt 3e: Z21-Simulator nach Spezifikation (eigene Sitzung)
- [ ] Schritt 4: `loop.sh` und Devcontainer
- [ ] Tor A: Freigabe durch Mo
