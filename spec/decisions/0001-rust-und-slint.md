# 0001 – Rust und Slint
**Status:** Vorschlag · 2026-10-26

**Kontext:** Electrip 1 ist Python/GTK. Electrip 2 soll plattformunabhängig sein und von Agenten gebaut werden.
**Entscheidung:** Rust (stable) als Sprache, Slint für die Oberfläche, Cargo-Workspace mit `xtask`.
**Konsequenzen:** Strenger Compiler und Clippy dienen als Prüfer für Agenten; einzelne Binärdateien für Linux, macOS, Windows, Raspberry Pi. Kein Code aus `legacy/` wird direkt übernommen.
