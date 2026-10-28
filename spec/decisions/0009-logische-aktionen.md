# 0009 – Logische Aktionen statt Knopfnummern
**Status:** Angenommen · 2026-10-28 (Vorschlag vom 2026-10-28)

**Kontext:** Electrip 1 speichert pro Lokfunktion eine Knopfnummer. Mit verschiedenen Gamepads und Joysticks (N-01) bedeutet dieselbe Nummer unterschiedliche physische Knöpfe.
**Entscheidung:** Zwei getrennte Abbildungen:
1. Pro Eingabegerät(etyp): Knopf/Achse/Hat-Richtung → logische Aktion (nutzerdefiniert, lokübergreifend, unbegrenzt) oder eingebaute Aktion.
2. Pro Lok: logische Aktion → Decoder-Funktion, Geräusch-Funktion oder Geräusch-Ereignis.
Beim Import aus Electrip 1 wird je verwendeter Knopfnummer eine logische Aktion erzeugt und ein Mapping für den Gerätetyp angelegt.
**Konsequenzen:** Funktionsnummern werden nicht gegen Grenzen der Zentrale geprüft. Aktionen und Mappings gehören zur Konfiguration.
