# 0007 – Budget: ein Claude-Team-Premium-Platz
**Status:** Angenommen · 2026-10-28 (Vorschlag vom 2026-10-26), geändert von Mo am 2026-10-29: nur noch ein Agent

**Kontext:** Es gibt kein separates API-Budget.
**Entscheidung:** Der Loop läuft mit Claude Code (Abo-Login, headless `claude -p`) über Mos Platz. Es arbeitet immer nur ein Agent, Sitzungen laufen nacheinander. Der Loop-Runner pausiert beim Erreichen des Limits und setzt danach fort.
**Konsequenzen:** Keine Sperrdateien für Aufgaben; kurze, fokussierte Sitzungen; knappe Testausgaben; mehrere Wochen Kalenderzeit.
