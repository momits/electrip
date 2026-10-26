# 0006 – Zeilenbudget
**Status:** Vorschlag · 2026-10-26

**Kontext:** Agenten neigen zu aufgeblähtem Code; jede Sitzung muss den Code lesen und verbraucht dabei Kontingent.
**Entscheidung:** Höchstens 12.000 Zeilen Produktcode (ohne Tests, `xtask`, Simulatoren), geprüft per `cargo xtask loc` in der CI. Überschreitung blockiert neue Funktionen, bis Code abgebaut ist.
**Konsequenzen:** Bibliotheken statt Eigenbau; Aufräum-Agent je Phase mit Ziel „weniger Zeilen bei gleich grünen Tests“.
