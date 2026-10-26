# 0004 – Audio-Ziele pro Lok
**Status:** Vorschlag · 2026-10-26

**Kontext:** Langfristig soll jede Lok einen eigenen Lautsprecher bekommen (N-05); Bluetooth hat Grenzen bei Anzahl und Latenz, WLAN-Empfänger wären eine Alternative.
**Entscheidung:** Trait `AudioSink`; Sound-Modelle erzeugen nur Audio-Ereignisse. In 2.0 gibt es genau eine Implementierung: ein vom Betriebssystem bereitgestelltes Audiogerät pro Lok. Bluetooth-direkt vs. WLAN wird später entschieden.
**Konsequenzen:** Testmodus des `AudioSink` protokolliert Ereignisse für Golden-Tests.
