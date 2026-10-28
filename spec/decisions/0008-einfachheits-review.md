# 0008 – Einfachheits-Review nach jedem Inkrement
**Status:** Angenommen · 2026-10-28 (Vorschlag vom 2026-10-27)

**Kontext:** Agenten erzeugen schnell funktionierenden, aber oft doppelten, auf Vorrat gebauten oder unnötig komplizierten Code. Das kostet Zeilenbudget, Kontext und spätere Wartung.
**Entscheidung:** Nach jedem Inkrement (Feature, Bugfix, Refactoring, Testwerkzeug) wird der Diff seit dem Basis-Commit gegen DRY, YAGNI und KISS geprüft – möglichst durch einen frischen Sub-Agenten. Befunde im eigenen Diff werden sofort und verhaltensneutral refactort; Befunde in älterem Code landen als Aufräumkandidaten in `PROGRESS.md`. Der Abschluss-Commit trägt den Trailer `Simplicity-Review: ok|refactored`; die CI prüft ihn, sobald `xtask` existiert.
**Konsequenzen:** Etwas mehr Verbrauch pro Inkrement, dafür kleinerer, einfacherer Code und weniger Aufräumarbeit später. Checkliste und Ablauf stehen in `AGENTS.md`.
