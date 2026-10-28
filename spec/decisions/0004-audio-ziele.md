# 0004 – Ein Audio-Ziel pro Lok
**Status:** Vorschlag · 2026-10-28 (überarbeitet)

**Kontext:** Langfristig soll jede Lok einen eigenen Lautsprecher bekommen können (N-05); Bluetooth hat Grenzen bei Anzahl und Latenz, WLAN-Empfänger wären eine Alternative. Mehrere Instanzen können dieselbe Lok sehen.
**Entscheidung:** Jeder Lok ist in der Konfiguration genau ein Audio-Ziel (Trait `AudioSink`) zugeordnet. Das Ziel kann die Soundkarte eines Rechners mit Electrip-Instanz sein, muss es aber nicht. Sound-Modelle laufen im Sitzungs-Host (ADR 0010) und erzeugen nur Audio-Ereignisse, die an das Audio-Ziel geschickt werden. In 2.0 gibt es genau einen Zieltyp: ein Ausgabegerät eines Rechners mit Electrip-Instanz; diese Instanz spielt den Sound, egal wer die Lok fährt. Bluetooth-direkt vs. WLAN wird später entschieden.
**Konsequenzen:** Kein „Sound-Besitzer“-Konzept nötig. Verzögerungen wie in B-13 werden aus Dateilängen berechnet, nicht aus der Wiedergabe. Testmodus des `AudioSink` protokolliert Ereignisse für Golden-Tests.
