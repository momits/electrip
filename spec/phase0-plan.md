# Phase 0 – Arbeitsplan

Phase 0 baut das Fundament, bevor der autonome Loop startet. Jeder Schritt ist so beschrieben, dass eine neue Sitzung (Claude Code im Repo oder ein neuer Chat) ihn ohne Vorwissen ausführen kann. Stand und Haken stehen in `PROGRESS.md`; Regeln in `AGENTS.md`.

**Einstieg für eine neue Sitzung:** „Lies `AGENTS.md`, `PROGRESS.md` und `spec/phase0-plan.md` und mach mit dem nächsten offenen Schritt von Phase 0 weiter.“

## Schritt 1 – Repo (erledigt)
`legacy/` per `git subtree` (Historie von SourceForge, Commits dort nicht umschreiben), `spec/benutzerhandbuch.pdf`, `spec/konzept.md`, `LICENSE`.

## Schritt 2 – Spezifikation (erledigt)
`spec/requirements.json`, `AGENTS.md`, ADRs 0001–0010, `spec/questions.md` (alle beantwortet).

## Schritt 3a – Workspace, xtask, CI
- Cargo-Workspace: nur Crates anlegen, die gebraucht werden (`core`, Binary `electrip`, `xtask`); weitere Crates entstehen mit ihrer ersten Anforderung. Die erlaubten Abhängigkeiten zwischen Crates stehen trotzdem schon in `xtask` (Schichtenregel aus `AGENTS.md`).
- `cargo xtask test`: fmt-Check, Clippy mit `-D warnings`, Schichtenprüfung, Tests; knappe Ausgabe, Details nach `target/test-logs/`.
- `cargo xtask loc`: Produktcode-Zeilen gegen das Budget (12.000).
- `cargo xtask parity`: Paritätsbericht aus `spec/requirements.json`.
- `cargo xtask review-check <basis>`: der jüngste Commit im Bereich, der `crates/` ändert, trägt den Trailer `Simplicity-Review: ok|refactored`.
- GitHub Actions: Test-Matrix Linux/macOS/Windows, Build für Raspberry Pi (aarch64 Linux), Job für loc/parity/review-check.
- Fertig, wenn: CI grün auf allen Plattformen, alle xtask-Befehle laufen lokal.

## Schritt 3b – srcpd-Simulator
- Docker-Image mit srcpd (Debian-Paket `srcpd`) und Konfiguration mit Loopback-Bus; `cargo xtask sim up|down`.
- Rauchtest: per TCP verbinden, `SET CONNECTIONMODE SRCP INFO`, `GO`, Lok setzen, INFO-Meldung empfangen.
- Fertig, wenn: Rauchtest läuft lokal und in der CI (Linux).

## Schritt 3c – Golden-Harness für Electrip 1
- `tools/legacy-harness/`: startet die Logik von `legacy/` ohne GTK mit skriptbaren Eingaben (Achse, Knöpfe, Zeit) und zeichnet gesendete SRCP-Befehle und Sound-Ereignisse auf. `legacy/` selbst nicht ändern.
- Golden Files für B-08 (Kennlinie), B-14 (Dampftakt), B-17 (Geräusch-Ereignisse) und die Sound-Modelle B-11/B-13 nach `tests/golden/`; `cargo xtask golden --record`.
- B-10 braucht keinen Golden-Test (Q-003).

## Schritt 3d – Korpus
- Lokpakete von der SourceForge-Projektseite (Files) nach `tests/corpus/`, SHA-256 in `tests/corpus/SHA256SUMS`, Lizenz der Pakete prüfen.
- Vollständige Electrip-1-Konfigurationen mit dem Alt-Code erzeugen (Q-002).

## Schritt 3e – Z21-Simulator (eigene Sitzung)
- Nur nach Roco-Spezifikation „Z21 LAN Protokoll“; UDP-Server mit den in N-02 genannten Szenarien; Konformitätstests aus den Beispiel-Telegrammen der Spezifikation.
- Nicht in derselben Sitzung wie der Z21-Treiber (ADR 0005).

## Schritt 4 – Loop und Devcontainer
- `.devcontainer/` mit Rust, Claude Code und srcpd, gestartet mit `start.sh` (ohne devcontainer-CLI und ohne Docker-in-Docker, siehe `PROGRESS.md`).
- `loop.sh`: ruft `claude -p` mit `prompts/session.md` in Schleife auf, loggt jede Sitzung nach `logs/`, erkennt das Nutzungslimit, wartet und setzt fort.
- `prompts/session.md`: Sitzungsablauf aus `AGENTS.md` als Prompt.

## Tor A – Freigabe durch Mo
Mo prüft: CI grün, Simulatoren laufen, Golden Files plausibel, Loop startet. Danach Phase 1 im Loop.
