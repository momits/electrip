# 0007 – Budget: ein Claude-Team-Premium-Platz
**Status:** Angenommen · 2026-10-28 (Vorschlag vom 2026-10-26)

**Kontext:** Es gibt kein separates API-Budget.
**Entscheidung:** Der Loop läuft mit Claude Code (Abo-Login, headless `claude -p`) über Mos Platz. Standard ist ein Agent; ein zweiter nur, wenn das Limit es trägt. Der Loop-Runner pausiert beim Erreichen des Limits und setzt danach fort.
**Konsequenzen:** Kurze, fokussierte Sitzungen; knappe Testausgaben; mehrere Wochen Kalenderzeit.
