# Fortschritt

Neueste Einträge oben. Jede Sitzung ergänzt hier: Datum, Aufgabe/ID, Ergebnis, Einfachheits-Review (ok/refactored), offene Punkte.

## Aufräumkandidaten

_Befunde aus Einfachheits-Reviews, die älteren Code betreffen. Der Aufräum-Agent arbeitet sie je Phase ab._

- (noch keine)

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

- [ ] Schritt 3a: Cargo-Workspace mit leeren Crates, `xtask` (`test`, `loc`, `parity`, Check des Trailers `Simplicity-Review`), CI auf Linux/macOS/Windows
- [ ] Schritt 3b: srcpd mit Loopback-Bus in Docker, `cargo xtask sim up`
- [ ] Schritt 3c: Headless-Harness für Alt-Electrip, Golden-Tests aufzeichnen (B-08, B-10, B-14, B-17)
- [ ] Schritt 3d: Korpus (Mos JSON-Konfigurationen, SourceForge-Lokpakete)
- [ ] Schritt 3e: Z21-Simulator nach Spezifikation (eigene Sitzung)
- [ ] Schritt 4: `loop.sh` und Devcontainer
- [ ] Tor A: Freigabe durch Mo
