# Offene Fragen

Agenten tragen hier Widersprüche und Lücken ein; Mo beantwortet sie. Format: ID, Datum, betroffene Anforderung, Frage, Antwort.

## Q-001 – 2026-10-26 – B-06
**Frage:** Welche Adress- und Fahrstufenbereiche sollen pro Protokoll (M 1, M 2, N 1, N 2) gelten? Werden weitere Protokolle (z. B. mfx, Selectrix) gebraucht?
**Antwort:** Bereiche wie Electrip 1 (`legacy/src/electrip/constants.py`, `PROTOCOLS`), übernommen in B-06. Weitere Protokolle (mfx, Selectrix): nicht in 2.0 (Mo, 2026-10-28).

## Q-002 – 2026-10-26 – B-21, N-04
**Frage:** Welche echten Electrip-1-Konfigurationen und Lokpakete kann Mo für den Korpus beisteuern?
**Antwort:** Nur die SourceForge-Lokpakete; vollständige JSON-Konfigurationen erzeugen die Agenten mit dem Alt-Code. (Mo, 2026-10-28)

## Q-003 – 2026-10-28 – B-10
**Frage:** Welche Toleranz gilt beim Golden-Test der Beschleunigung (gesendete Fahrstufen über die Zeit)?
**Vorschlag:** ±1 Fahrstufe und ±50 ms je Stützpunkt.
**Antwort:** „Ungefähr“ reicht, solange die Spezifikation erfüllt ist: Vmax in der eingestellten Dauer, Beschleunigung proportional zur Auslenkung. Toleranz ±10 %, kein Golden-Test (B-10). (Mo, 2026-10-28)

## Q-004 – 2026-10-28 – B-06, N-02
**Frage:** Wie werden die SRCP-Protokolle (M 1, M 2, N 1, N 2) auf die Z21 abgebildet?
**Vorschlag:** Protokoll intern als „Motorola 1/2“ bzw. „DCC kurz/lang“ führen; jeder Treiber übersetzt. Für Z21: DCC und Motorola (MM) über LAN_X_SET_LOCO_DRIVE mit passendem Fahrstufenformat; nicht unterstützte Kombinationen meldet der Treiber als Fehler.
**Antwort:** Wie vorgeschlagen (B-06). (Mo, 2026-10-28)

## Q-005 – 2026-10-28 – N-02
**Frage:** Was gehört zur gemeinsamen Szenario-Testsuite beider Treiber?
**Vorschlag:** Verbinden/Trennen, Gleisstrom an/aus, Lok fahren (Geschwindigkeit, Richtung), Funktionen F0–F28 schalten, Nothalt, Zustandsmeldung einer fremden Änderung empfangen.
**Antwort:** Wie vorgeschlagen (N-02). (Mo, 2026-10-28)

## Q-006 – 2026-10-28 – N-05
**Frage:** Ab welcher Latenz zwischen Fahrbefehl und hörbarem Sound gilt ein Audio-Ziel als zu langsam?
**Vorschlag:** Zielwert ≤ 150 ms, Hinweis in der UI bei > 300 ms.
**Antwort:** Wie vorgeschlagen (N-05). (Mo, 2026-10-28)

## Q-007 – 2026-10-28 – N-03
**Frage:** Unter welchen Netzbedingungen gelten die 300 ms Synchronisationszeit?
**Vorschlag:** Kabel-LAN oder WLAN mit < 20 ms Roundtrip; im Test lokal mit simulierten 20 ms Verzögerung.
**Antwort:** Wie vorgeschlagen (N-03). (Mo, 2026-10-28)

## Q-008 – 2026-10-28 – B-23
**Frage:** Braucht es zusätzlich zum anlagenweiten Nothalt (Gleisstrom aus) einen Nothalt für eine einzelne Lok?
**Vorschlag:** Ja, als eingebaute Aktion „Lok-Nothalt“ (SRCP: Nothalt-Fahrmodus, Z21: Fahrstufe Nothalt); Gleisstrom bleibt an.
**Antwort:** Ja, Nothalt für die aktuell gesteuerte Lok zusätzlich zum anlagenweiten Nothalt; übernommen in B-23. (Mo, 2026-10-28)

## Q-009 – 2026-10-28 – B-22
**Frage:** Welche Verbesserungen der Steuerungsansicht gegenüber Electrip 1 sind gewünscht?
**Vorschlag:** (a) Auto-Fokus standardmäßig an; (b) Loks, die gerade von einem Eingabegerät gesteuert werden, deutlich hervorheben; (c) bei mehr Loks als Platz: kompakte Regler statt nur Scrollen; (d) Filter „nur gesteuerte/fahrende Loks“.
**Antwort:** Alle vier Vorschläge übernehmen (B-22). (Mo, 2026-10-28)

## Q-010 – 2026-10-28 – N-03, B-10
**Frage:** Instanz A beschleunigt eine Lok mit Rampe, Instanz B setzt währenddessen eine andere Geschwindigkeit. Was passiert mit der Rampe in A?
**Vorschlag:** A übernimmt den von der Zentrale gemeldeten Wert als neuen Ausgangspunkt und rampt von dort weiter, solange die Achse in A ausgelenkt ist (die Achse gibt die Beschleunigung vor, nicht die Zielgeschwindigkeit).
**Antwort:** Gelöst durch ADR 0010 (Sitzungs-Host): Rampen laufen nur im Host; zuletzt aktive Eingabe gewinnt, ausgelenkte Achse rampt vom aktuellen Wert weiter. (Mo, 2026-10-28)

## Q-011 – 2026-10-28 – N-05, N-03
**Frage:** Zwei Konfigurationen enthalten dieselbe Lok-Adresse und weisen ihr verschiedene Audio-Ziele bzw. Sounds zu. Sollen beide spielen?
**Vorschlag:** Ja, beide spielen – das ist Sache der Konfiguration. Die UI warnt, wenn eine Lok-Adresse in mehreren aktiven Konfigurationen ein Audio-Ziel hat.
**Antwort:** Ja, wie vorgeschlagen; der Host schickt Ereignisse an beide Ziele (N-05). (Mo, 2026-10-28)

## Q-012 – 2026-10-28 – B-06
**Frage:** In Electrip 1 erlaubt „N 1 – DCC mit kurzen Adressen“ dieselben Adressen wie „N 2“ (1–10239). Kurze DCC-Adressen gehen nach NMRA-Norm nur bis 127. Übernehmen oder korrigieren?
**Vorschlag:** Korrigieren: N 1 = 1–127, N 2 = 1–10239. Alt-Konfigurationen mit N 1 und Adresse > 127 werden beim Import auf N 2 umgestellt.
**Antwort:** Wie vorgeschlagen: N 1 = 1–127, Umstellung beim Import (B-06). (Mo, 2026-10-28)

## Q-013 – 2026-10-28 – B-17
**Frage:** Der Golden-Harness zeigt drei Eigenheiten der Geräusch-Ereignisse in Electrip 1 (`pygame_io.EventSoundPlayer`, `config/unsaved_changes.py`).
Sie widersprechen dem Akzeptanzkriterium „Auslösung bei passender Richtung und vmin ≤ v ≤ vmax und amin ≤ a ≤ amax“.
Soll Electrip 2 sie nachbilden, damit der Golden-Test `tests/golden/event_sounds.jsonl` grün wird?
1. Beobachter laufen vor der Zuweisung und prüfen daher den alten Wert.
   Beim Einschalten eines Ereignisses per Knopf zählt noch „aus“, beim Ausschalten noch „an“.
   Im Golden-Test startet „Rollen“ erst beim Ausschalten.
2. Aus demselben Grund prüft die Bedingung die Beschleunigung des vorigen Takts (50 ms zu spät).
3. Die Geschwindigkeit wird nicht beobachtet.
   Ein Ereignis nur mit vmin/vmax prüft seine Bedingung nur beim Start, bei Richtungs- oder Zustandswechsel und am Ende jeder Wiedergabe.
   Außerdem gilt eine Grenze von 0 als „beliebig“.

**Vorschlag:** Nicht nachbilden.
Electrip 2 prüft die Bedingungen mit den aktuellen Werten bei jeder Änderung von Zustand, Richtung, v und a.
Der Golden-Test für B-17 vergleicht dann nur Szenarien, in denen beide Verhalten übereinstimmen.
Der Harness bleibt unverändert und zeichnet weiter das echte Alt-Verhalten auf.
**Antwort:** _offen_
