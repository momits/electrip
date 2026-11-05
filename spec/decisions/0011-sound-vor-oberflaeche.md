# 0011 – Sound vor Oberfläche
**Status:** Angenommen · 2026-11-05 (Mo)

**Kontext:** Phase 1 ließ sich nicht schließen. B-03 und B-05 prüft man mit Screenshots, also erst mit der Oberfläche. B-20 enthält Sounds und braucht die Audioformate aus B-18. Die Sound-Modelle (B-11 bis B-18) lassen sich dagegen ohne Oberfläche mit Audio-Log, Golden-Tests und Steuerkanal prüfen (ADR 0004, 0010). Sie sind das größte Risiko des Projekts.
**Entscheidung:** Der Sound wird eine eigene Phase vor der Oberfläche.

- Phase 1 · Kern: unverändert, nur B-03, B-05 und B-20 wandern heraus. Tor B: B-01 bis B-10 verifiziert und Fahrtest an der echten Anlage.
- Phase 2 · Sound: B-11 bis B-18 und B-20. Tor C: verifiziert, dazu ein Hörtest bei Mo.
- Phase 3 · Ausbau: Oberfläche (B-03, B-05, B-19, B-22, B-25), Multi-Client und Sync (N-03, N-04), Audio-Ziel (N-05). Tor D: alle B- und N-Anforderungen verifiziert.
- Phase 4 · Abnahme: wie bisher Phase 3. Tor E: Release.

**Konsequenzen:** Der Agent arbeitet nach „niedrigste Phase zuerst“ von selbst in dieser Reihenfolge. Es gibt lange keine Oberfläche zum Ausprobieren; Mo hört den Sound über den Steuerkanal. Die Hardware-Tests für B-11, B-13 und B-14 kommen früher. Das Zeilenbudget (ADR 0006) trägt vor allem der Sound. Einträge in `PROGRESS.md` vor dem 2026-11-05 meinen mit „Phase 2“ die Oberfläche, die jetzt Phase 3 ist.
