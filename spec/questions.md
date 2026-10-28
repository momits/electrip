# Offene Fragen

Agenten tragen hier Widersprüche und Lücken ein; Mo beantwortet sie. Format: ID, Datum, betroffene Anforderung, Frage, Antwort.

## Q-001 – 2026-10-26 – B-06
**Frage:** Welche Adress- und Fahrstufenbereiche sollen pro Protokoll (M 1, M 2, N 1, N 2) gelten? Werden weitere Protokolle (z. B. mfx, Selectrix) gebraucht?
**Antwort:** Bereiche wie Electrip 1 (`legacy/src/electrip/constants.py`, `PROTOCOLS`), übernommen in B-06. Weitere Protokolle: nicht in 2.0 (Annahme, Mo bitte bestätigen).

## Q-002 – 2026-10-26 – B-21, N-04
**Frage:** Welche echten Electrip-1-Konfigurationen und Lokpakete kann Mo für den Korpus beisteuern?
**Antwort:** _offen_

## Q-003 – 2026-10-28 – B-10
**Frage:** Welche Toleranz gilt beim Golden-Test der Beschleunigung (gesendete Fahrstufen über die Zeit)?
**Vorschlag:** ±1 Fahrstufe und ±50 ms je Stützpunkt.
**Antwort:** _offen_

## Q-004 – 2026-10-28 – B-06, N-02
**Frage:** Wie werden die SRCP-Protokolle (M 1, M 2, N 1, N 2) auf die Z21 abgebildet?
**Vorschlag:** Protokoll intern als „Motorola 1/2“ bzw. „DCC kurz/lang“ führen; jeder Treiber übersetzt. Für Z21: DCC und Motorola (MM) über LAN_X_SET_LOCO_DRIVE mit passendem Fahrstufenformat; nicht unterstützte Kombinationen meldet der Treiber als Fehler.
**Antwort:** _offen_

## Q-005 – 2026-10-28 – N-02
**Frage:** Was gehört zur gemeinsamen Szenario-Testsuite beider Treiber?
**Vorschlag:** Verbinden/Trennen, Gleisstrom an/aus, Lok fahren (Geschwindigkeit, Richtung), Funktionen F0–F28 schalten, Nothalt, Zustandsmeldung einer fremden Änderung empfangen.
**Antwort:** _offen_

## Q-006 – 2026-10-28 – N-05
**Frage:** Ab welcher Latenz zwischen Fahrbefehl und hörbarem Sound gilt ein Audio-Ziel als zu langsam?
**Vorschlag:** Zielwert ≤ 150 ms, Hinweis in der UI bei > 300 ms.
**Antwort:** _offen_

## Q-007 – 2026-10-28 – N-03
**Frage:** Unter welchen Netzbedingungen gelten die 300 ms Synchronisationszeit?
**Vorschlag:** Kabel-LAN oder WLAN mit < 20 ms Roundtrip; im Test lokal mit simulierten 20 ms Verzögerung.
**Antwort:** _offen_

## Q-008 – 2026-10-28 – B-23
**Frage:** Braucht es zusätzlich zum anlagenweiten Nothalt (Gleisstrom aus) einen Nothalt für eine einzelne Lok?
**Vorschlag:** Ja, als eingebaute Aktion „Lok-Nothalt“ (SRCP: Nothalt-Fahrmodus, Z21: Fahrstufe Nothalt); Gleisstrom bleibt an.
**Antwort:** _offen_

## Q-009 – 2026-10-28 – B-22
**Frage:** Welche Verbesserungen der Steuerungsansicht gegenüber Electrip 1 sind gewünscht?
**Vorschlag:** (a) Auto-Fokus standardmäßig an; (b) Loks, die gerade von einem Eingabegerät gesteuert werden, deutlich hervorheben; (c) bei mehr Loks als Platz: kompakte Regler statt nur Scrollen; (d) Filter „nur gesteuerte/fahrende Loks“.
**Antwort:** _offen_

## Q-010 – 2026-10-28 – N-03, B-10
**Frage:** Instanz A beschleunigt eine Lok mit Rampe, Instanz B setzt währenddessen eine andere Geschwindigkeit. Was passiert mit der Rampe in A?
**Vorschlag:** A übernimmt den von der Zentrale gemeldeten Wert als neuen Ausgangspunkt und rampt von dort weiter, solange die Achse in A ausgelenkt ist (die Achse gibt die Beschleunigung vor, nicht die Zielgeschwindigkeit).
**Antwort:** _offen_

## Q-011 – 2026-10-28 – N-05, N-03
**Frage:** Zwei Konfigurationen enthalten dieselbe Lok-Adresse und weisen ihr verschiedene Audio-Ziele bzw. Sounds zu. Sollen beide spielen?
**Vorschlag:** Ja, beide spielen – das ist Sache der Konfiguration. Die UI warnt, wenn eine Lok-Adresse in mehreren aktiven Konfigurationen ein Audio-Ziel hat.
**Antwort:** _offen_

## Q-012 – 2026-10-28 – B-06
**Frage:** In Electrip 1 erlaubt „N 1 – DCC mit kurzen Adressen“ dieselben Adressen wie „N 2“ (1–10239). Kurze DCC-Adressen gehen nach NMRA-Norm nur bis 127. Übernehmen oder korrigieren?
**Vorschlag:** Korrigieren: N 1 = 1–127, N 2 = 1–10239. Alt-Konfigurationen mit N 1 und Adresse > 127 werden beim Import auf N 2 umgestellt.
**Antwort:** _offen_
