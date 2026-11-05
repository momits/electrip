# Electrip 2 – Gesamtkonzept agentische Migration

**Status:** Entwurf · Stand 26.10.2026 · Autor: Moritz Renftle
Lebende Fassung: Claude Doc „Electrip 2 – Gesamtkonzept agentische Migration“. Diese Datei ist die Arbeitsgrundlage für die Agenten; Änderungen nur per Pull Request mit Freigabe durch Mo. **Bei Abweichungen gelten `spec/requirements.json` und `spec/decisions/` vor diesem Dokument.**

## Ziel & Leitprinzipien

Electrip 2 wird von KI-Agenten in einer vorbereiteten Umgebung neu geschrieben; der Mensch liefert Spezifikation, Prüfmittel und Hardware-Abnahme, die Agenten liefern den Code.

- **Umgebung vor Prompts.** Wie bei ArtCraft und Anthropics C-Compiler entscheidet die Qualität von Tests, Simulatoren und Regeln über das Ergebnis, nicht ein ausgefeilter Prompt.
- **Befehl zuerst, Knopf danach.** Jede Nutzeraktion ist ein Befehl im Kern; Gamepad, GUI, Tests und Agenten benutzen dieselbe Schnittstelle.
- **Jede Anforderung ist prüfbar.** Eine Anforderung ohne automatischen Test oder ohne definierten Hardware-Test gilt nicht als erfüllt.
- **Ehrliche Parität.** Fortschritt wird getrennt gemessen: angebunden, Verhalten getestet, an echter Anlage abgenommen.
- **Klein halten.** Höchstens 12.000 Zeilen Produktcode; fertige Bibliotheken statt Eigenbau; nach jedem Inkrement ein Review auf DRY, YAGNI und KISS mit sofortigem Refactoring.
- **Der Mensch entscheidet an Toren.** Architektur, Abnahme der Spezifikation und Hardware-Tests bleiben bei Mo.

## Anforderungsquellen

Drei Quellen werden zu einem maschinenlesbaren Paritätskatalog (`spec/requirements.json`) zusammengeführt; jeder Eintrag bekommt eine ID, eine Quelle und mindestens einen Prüffall.

| Quelle | Was sie liefert | Wie sie genutzt wird |
| --- | --- | --- |
| Benutzerhandbuch (`spec/benutzerhandbuch.pdf`, 19 Seiten, Stand 2013) | Fachliches Verhalten aus Nutzersicht: Konfiguration, Kennlinie, Sound-Modelle, Gamepad-Bedienung | Anforderungen B-xx; Screenshots als Referenz für UI-Inhalte |
| Alt-Code (`legacy/`, Python/GTK, ca. 7.600 Zeilen, Stand Feb. 2019) | Aktueller Stand, Details die das Handbuch nicht nennt, JSON-Format, ZIP-Format | Charakterisierungstests: gleiche Eingaben → gleiche SRCP-Befehle und Sound-Ereignisse |
| Neue Anforderungen (Mo, Okt. 2026) | Gamepad-Vielfalt, Zentralen-Interface, Multi-Client, gemeinsame DB, Audio pro Lok | Anforderungen N-xx mit Akzeptanzkriterien |

Bei Widersprüchen gilt: neue Anforderung vor Alt-Code vor Handbuch. Das Handbuch ist älter als der Code (z. B. Python 2.7, Windows-Bundle); Abweichungen protokolliert ein Agent als offene Frage in `spec/questions.md`, statt sie stillschweigend aufzulösen.

## Bestandsanforderungen aus dem Benutzerhandbuch

Das Handbuch beschreibt 24 prüfbare Verhaltensweisen; sie bilden den Pflichtumfang von Electrip 2. Abschnittsnummern beziehen sich auf das Handbuch.

| ID | Anforderung | Hb. | Prüfung |
| --- | --- | --- | --- |
| B-01 | Verbindung zu SRCP-Server über Host, Port (Standard 4303) und Bus | 2.1 | srcpd-Loopback |
| B-02 | Globale Gamepad-Belegung: Fahrachse, Richtungswender, Nothalt, Loks wechseln, Fahrgeräusch; Buttons ohne den „–1“-Versatz anzeigen | 2.2 | virtuelles Gamepad |
| B-03 | Bis zu 12 Gamepads gleichzeitig, jedes mit eigener Farbe/Symbol | Feat. 2, 3.1 | virtuelles Gamepad |
| B-04 | Lok anlegen, umbenennen, löschen; Lokliste | 2.4 | Steuerkanal |
| B-05 | Lok-Eigenschaften: Höchstgeschwindigkeit (km/h), Beschleunigungs- und Bremsdauer, Lokbild (110×85 px) | 2.4.1 | Unit + Steuerkanal |
| B-06 | Decoder: Protokoll, Adresse, Fahrstufen; ungültige Kombinationen verhindern; Protokollwechsel setzt Standard-Fahrstufen (z. B. 128 bei DCC) | 2.4.1 | Unit |
| B-07 | Lokfunktionen: Decoder-Nr. (F0…), Gamepad-Button oder keiner, Umschalter oder Taster, Standardzustand An/Aus kehrt Verhalten um | 2.4.2 | Loopback + virtuelles Gamepad |
| B-08 | Geschwindigkeitskennlinie: km/h → Fahrstufe über Kontrollpunkte; erster Punkt = Anfahrstufe, letzter = Vmax, beide nicht löschbar; Punkte per Klick anlegen, Rechtsklick löschen, Ziehen verschieben | 2.4.3 | Golden-Test gegen Alt-Code |
| B-09 | Änderung von Vmax oder Fahrstufen setzt Kennlinie nach Bestätigung zurück | 2.4.3 | Steuerkanal |
| B-10 | Beschleunigung: Vollausschlag erreicht Vmax in der eingestellten Dauer; leichter Ausschlag = leichte Beschleunigung; Vollausschlag zurück = Vollbremsung | 3.1 | Golden-Test |
| B-11 | Fahrgeräusch-Modell „Verbrennungsmotor“ (auch E-Lok): Segmente je Geschwindigkeitsbereich mit Last, Leerlauf, Beschleunigungs- und Bremsgeräusch; lückenlose Wiederholung | 2.4.4a | Audio-Ereignis-Log |
| B-12 | Zusatzgeräusche Verbrennungsmotor: Anlassen, Leerlauf, Abstellen; Regler während Anlassen/Abstellen gesperrt | 2.4.4a, 3 | Audio-Ereignis-Log |
| B-13 | Anfahren und Anhalten synchron zum Übergangsgeräusch Leerlauf ↔ Segment 1 | 3 | Loopback + Audio-Log |
| B-14 | Fahrgeräusch-Modell „Dampf“: Taktgeräusche je Segment; Taktfrequenz aus Treibrad-Durchmesser, Geschwindigkeit, Takten pro Umdrehung; minimale Taktfrequenz; Dampfablassgeräusch und -dauer beim Anfahren | 2.4.4a | Golden-Test Taktzeiten |
| B-15 | Segmente einfügen, löschen, Grenzen ziehen; letztes Segment löschen = Modell auf „Kein Geräusch“ nach Bestätigung | 2.4.4a | Steuerkanal |
| B-16 | Geräusch-Funktionen mit vier Modi: Umschalter (Loop), Taster einmal, Taster wiederholt, Anschalter bis Ende | 2.4.4b | Audio-Log |
| B-17 | Geräusch-Ereignisse: Auslösung bei vmin ≤ v ≤ vmax und amin ≤ a ≤ amax, leere Grenze = egal; per Button aktivierbar | 2.4.4c | Golden-Test |
| B-18 | Audioformate WAV und OGG; Abtastrate korrekt (Alt: manuell 44.100 Hz, neu: automatisch erkennen) | 2.3 | Unit |
| B-19 | Reihenfolge der Bedienknöpfe: Fahrgeräusch, Geräusch-Funktionen, Geräusch-Ereignisse, Lokfunktionen; farblich unterschieden | 2.4.5, 3 | Screenshot |
| B-20 | Lok-Export/-Import als ZIP mit Konfiguration, Bild und Sounds; neu: Entpacken in die Bibliothek statt neben das Archiv | 2.4.6 | Korpus der SourceForge-Lokpakete |
| B-21 | Gesamtkonfiguration als JSON speichern/laden; Alt-Dateien müssen importierbar bleiben | 2.5 | Korpus |
| B-22 | Steuerungsansicht: Regler nebeneinander mit Name, Bild, Geschwindigkeit, Geräuschpegel-Balken, Richtungsknopf, Funktionsknöpfen, aktivem Gamepad-Symbol | 3 | Screenshot |
| B-23 | Lokwechsel per Hat-Switch links/rechts, Dauerdruck scrollt; Nothalt schaltet Gleisstrom ab | 3, 3.1 | virtuelles Gamepad + Loopback |
| B-24 | Maussteuerung als Fallback; Start direkt in Steuerung mit `-f/--file` | 3.2, 3.3 | Steuerkanal |

Nicht übernommen werden der srcpd-Einrichtungsassistent (wird durch einen Verbindungsassistenten für beide Zentralen ersetzt) und die Vorgabe „einheitliche Gamepads“ (wird durch N-01 aufgehoben).

## Neue Anforderungen

| ID | Anforderung | Akzeptanzkriterium | Risiko |
| --- | --- | --- | --- |
| N-01 | Mehrere Gamepads und Eingabegeräte mit unterschiedlichen Knöpfen und Layouts; Belegung pro Gerätetyp als Profil | Drei verschiedene virtuelle Gamepads (Xbox-, PlayStation-, Generic-Layout) steuern gleichzeitig drei Loks; UI zeigt die echten Knopfnamen | niedrig: SDL3 GameController + Mapping-Datenbank |
| N-02 | Austauschbare Schnittstelle für Zentralen; Treiber für srcpd und Roco Z21 | Dieselbe Szenario-Testsuite läuft grün gegen srcpd-Loopback und Z21-Simulator | mittel: Z21-Abo-Grenzen, fehlendes LOCK, keine echte Z21 verfügbar |
| N-03 | Multi-Client 1: mehrere Instanzen an derselben Zentrale lauschen auf Zustandsänderungen und bleiben synchron | Drei Instanzen, Änderung in einer ist in den anderen innerhalb 300 ms sichtbar; konkurrierende Steuerung derselben Lok wird gesperrt oder angezeigt | mittel: SRCP INFO-Session + LOCK; Z21 Broadcast-Flags |
| N-04 | Multi-Client 2: Instanzen auf verschiedenen Geräten teilen eine Lok-Datenbank inkl. Bilder und Sounds | Lok auf Gerät A angelegt erscheint auf B; gleichzeitige Änderungen gehen nicht verloren; offline weiter nutzbar | mittel: CRDT-Sync, Partnersuche, Übertragung der Mediendateien |
| N-05 | Pro Lok eine eigene Audio-Ausgabe, perspektivisch Bluetooth-Lautsprecher in der Lok | Zwei Loks spielen gleichzeitig verschiedene Geräusche auf zwei Audiogeräten; Latenz gemessen und dokumentiert | hoch: wenige A2DP-Verbindungen je Adapter, 100–300 ms Latenz, Mobil-OS meist nur ein Ausgang |
| N-06 | Plattformunabhängig | CI baut und testet auf Linux, macOS, Windows; Raspberry Pi als Referenzhost | niedrig |

N-05 wird als austauschbares „Audio-Ziel“ angelegt. In Version 2.0 gibt es genau ein Ziel: jede Lok wählt ein vom Betriebssystem bereitgestelltes Audiogerät. Das deckt bereits Bluetooth-Lautsprecher ab, die im System gekoppelt sind, soweit das System mehrere gleichzeitig zulässt. Ob danach Bluetooth direkt (BlueZ) oder ein WLAN-Empfänger in der Lok folgt, bleibt offen.

## Zielarchitektur

Ein GUI-freier Kern in Rust nimmt alle Befehle entgegen; Treiber, Eingabegeräte, Audio und Sync hängen an klaren Schnittstellen, die Oberfläche ist nur ein weiterer Client.

**Bausteine (Cargo-Workspace, Schichten per Build-Check erzwungen):**

- `core` – Domänenmodell (Lok, Funktion, Kennlinie, Sound-Modell) und Befehls-Engine. Jede Aktion ist ein Befehl wie `SetSpeed`, `ToggleFunction`, `AssignController`, `EmergencyStop`.
- `station` – Trait `CommandStation` mit `connect`, `set_loco`, `set_function`, `power`, `emergency_stop` und einem Ereignisstrom; Treiber `station-srcp` (Kommando- und INFO-Session, LOCK) und `station-z21` (UDP, Broadcast-Flags; in 2.0 experimentell).
- `input` – SDL3-GameController, Geräteprofile, Mapping auf logische Aktionen; mehrere Geräte gleichzeitig.
- `audio` – Sound-Modelle (Verbrennung, Dampf, Funktionen, Ereignisse) erzeugen Audio-Ereignisse; Trait `AudioSink` mit zunächst nur einer Implementierung „System-Audiogerät pro Lok“. Bluetooth-direkt und WLAN-Empfänger sind als weitere Ziele vorgesehen, aber nicht Teil von Version 2.0.
- `library` – Lok-Datenbank als Automerge-CRDT, Import alter JSON- und ZIP-Dateien.
- `sync` – Sync-Rolle, die jede Instanz mitbringt: Partner im LAN per mDNS finden, CRDT-Änderungen austauschen, Sounds und Bilder separat übertragen (per SHA-256 adressiert). Läuft ein Rechner dauerhaft (z. B. Pi neben srcpd), übernimmt er dieselbe Rolle headless als stets erreichbarer Partner.
- `control` – lokaler Steuerkanal (JSON): Zustand lesen, Befehle senden, virtuelle Eingaben einspeisen, Screenshots. Für Agenten, Tests und Skripte; ein MCP-Server kann später als dünne Hülle darum folgen.
- `ui` – Oberfläche mit Slint, ruft ausschließlich Befehle auf.

**Warum Rust:** Der strenge Compiler und Clippy sind kostenlose Prüfer für Agenten, Binärdateien laufen auf Linux, macOS, Windows und dem Pi; ArtCraft zeigt, dass Agenten in diesem Setup große Rust-Codebasen tragen.

**Umfang:** Höchstens 12.000 Zeilen Produktcode (heute 7.600 ohne Tests); Tests, Simulator und `xtask` kommen mit geschätzt 6.000–10.000 Zeilen hinzu. Wo es eine etablierte Bibliothek gibt, wird sie genutzt statt nachgebaut: Automerge (Sync), SDL3 (Gamepads), rodio/symphonia (Audio), Slint (Oberfläche). Agenten schreiben nur die Fachlogik.

**Mobilgeräte:** Android/iOS sind in Version 2.0 kein Ziel. Sie können später als schlanker Client über den CRDT-Sync kommen; N-05 läuft dort ohnehin nicht.

## Verifikation

Agenten arbeiten nur so gut wie ihre Prüfer; deshalb entstehen Simulatoren, Korpus und Orakel vor dem ersten Produktcode.

| Prüfmittel | Prüft | Aufbau |
| --- | --- | --- |
| srcpd mit Loopback-Bus im Container | B-01, B-07, B-10, B-13, B-23, N-02, N-03 | Echter srcpd ohne Hardware; Testskripte lesen die INFO-Session mit |
| Z21-Simulator | N-02, N-03 | Keine echte Z21 vorhanden: eigener Simulator streng nach Roco-LAN-Spezifikation, Konformitätstests aus den Beispiel-Telegrammen der Spezifikation, Gegenprobe gegen unabhängige Implementierungen (z21aio, Z21ServerEmulator/Arduino-Bibliothek) |
| Virtuelle Gamepads | B-02, B-03, B-07, B-23, N-01 | SDL-Virtual-Joystick bzw. Linux-uinput; Profile für Xbox-, PlayStation- und Generic-Layout |
| Audio-Ereignis-Log | B-11 bis B-17 | `AudioSink` im Testmodus protokolliert Datei, Start, Ende, Loop mit Zeitstempel; dazu PipeWire-Null-Sink für echte Wiedergabe |
| Alt-Electrip als Orakel | B-08, B-10, B-14, B-17 | Alt-Code (`legacy/`) headless mit Skript-Eingaben; aufgezeichnete SRCP-Befehle und Sound-Ereignisse als Golden Files |
| Korpus | B-20, B-21 | Mos echte Konfigurationen, SourceForge-Lokpakete (z. B. „BR 216“), SHA-256-gepinnt; Import muss verlustfrei sein |
| Multi-Client-Szenarien | N-03, N-04 | docker-compose mit srcpd/Z21-Sim und drei headless Instanzen; Netztrennung und Offline-Änderungen werden simuliert, danach muss der Zustand überall gleich sein; Vergleich per Steuerkanal |
| Steuerkanal-Screenshots | B-19, B-22, UI | Agent bedient die App über den Steuerkanal und prüft Screenshots |
| Fuzzing | Parser SRCP, Z21, JSON, ZIP | `cargo fuzz` in der nächtlichen CI |
| Hardware-Abnahme (Mo) | alles mit „HW“ markiert | Checkliste pro Release an der echten Anlage, Ergebnisse als Issues zurück |

**Paritätsbericht:** `cargo xtask parity` zeigt pro Anforderung drei Stufen getrennt: *angebunden* (Befehl existiert), *verifiziert* (alle Prüffälle grün), *abgenommen* (Hardware-Test bestanden). Nur die letzte Stufe zählt als fertig.

## Harness & Loop

Kein eigenes Agenten-Framework: Claude Code (headless) in Containern, gesteuert über Dateien im Repo, Git und CI – die Kombination aus Anthropics Initialisierer-Muster, Ralph-Loop und den ArtCraft-Regeln.

**Steuerdateien im Repo:**

- `AGENTS.md` – Regeln: Schichten nicht verletzen; jede Aktion zuerst als Befehl; kein `panic` außerhalb von Tests; Clippy ohne Warnungen; neue Module statt wachsender Sammeldateien; Zeilenbudget von höchstens 12.000 Zeilen Produktcode, geprüft per `cargo xtask loc` in der CI – liegt der Code darüber, muss der nächste Pull Request zuerst Code abbauen; Abweichungen vom Handbuch als Frage in `spec/questions.md`.
- `spec/requirements.json` – Paritätskatalog (B-xx, N-xx) mit Prüffällen und den drei Statusstufen; Agenten dürfen nur den Status ändern, nicht die Anforderung.
- `spec/decisions/` – Architekturentscheidungen (ADRs), von Mo freigegeben.
- `PROGRESS.md` – Fortschrittsprotokoll; jede Sitzung liest es zuerst und ergänzt es zuletzt.
- `xtask` – `init`, `test`, `sim up`, `parity`, `corpus`, `golden`, `loc` als einheitliche Einstiegspunkte.

**Ablauf einer Agenten-Sitzung:**

1. Git-Log, `PROGRESS.md` und `cargo xtask parity` lesen.
2. `cargo xtask sim up` und Rauchtest; ist etwas rot, zuerst reparieren.
3. Eine offene Anforderung wählen und dafür einen Branch anlegen.
4. Umsetzen, Prüffälle schreiben bzw. grün machen, App über Steuerkanal selbst bedienen.
5. Einfachheits-Review des Diffs gegen DRY, YAGNI und KISS (möglichst durch frischen Sub-Agenten); Befunde sofort refactoren, Tests wieder grün.
6. Committen, Status in `requirements.json` setzen, `PROGRESS.md` ergänzen, Pull Request erstellen und nach grüner CI selbst mergen.

**Loop und Laufzeit:** Ein Skript startet Sitzungen in Folge (`while`-Loop mit `claude -p`), jede in einem Devcontainer mit allen Simulatoren und vollen Rechten nur im Container. Es arbeitet immer nur ein Agent, die Sitzungen laufen streng nacheinander; Sperren gegen parallele Agenten sind deshalb nicht nötig. Jede Aufgabe kommt über einen eigenen Pull Request nach `main`, den der Agent ohne Mo merged. Die CI (Linux, macOS, Windows) muss grün sein, bevor gemergt wird.

**Rollen:** Programmier-Agent; ein Prüf-Agent je Phase bzw. für größere Pull Requests (Architekturregeln, Duplikate, Testqualität); ein Aufräum-Agent je Phase mit dem Ziel „weniger Zeilen bei gleich grünen Tests“; ein Doku-Agent pflegt das neue Benutzerhandbuch aus `requirements.json`.

## Phasenplan

Die Agenten arbeiten autonom innerhalb einer Phase; zwischen den Phasen gibt Mo an einem Tor frei.

| Phase | Wer | Inhalt | Tor am Ende |
| --- | --- | --- | --- |
| 0 · Fundament | Mo + 1 Agent, interaktiv | Anforderungskatalog, ADRs, `AGENTS.md`, `xtask`, CI auf 3 Plattformen; srcpd-Loopback, Z21-Simulator, Golden-Tests aus Alt-Electrip, Korpus, Loop-Skript | A: Mo gibt Spezifikation und Prüfmittel frei |
| 1 · Kern | 1 Agent im Loop | Befehls-Engine, Steuerkanal, srcpd- und Z21-Treiber, Gamepad-Profile, Kennlinie, Beschleunigung, Import alter JSON- und ZIP-Dateien | B: B-01 bis B-10 verifiziert, Fahrtest an der echten Anlage |
| 2 · Sound | 1 Agent im Loop | Audio-Modelle ohne Oberfläche: Audioformate, Verbrennungs- und Dampfmodell, Geräusch-Funktionen und -Ereignisse, Lok-Export und -Import mit Sounds | C: B-11 bis B-18 und B-20 verifiziert, Hörtest bei Mo |
| 3 · Ausbau | 1 Agent im Loop | Oberfläche, Multi-Client, CRDT-Lok-Sync, Audio-Ziel System-Audiogerät pro Lok | D: alle B- und N-Anforderungen im Paritätsbericht verifiziert |
| 4 · Abnahme | Mo + Loop für Fixes | Hardware-Checkliste je Release, Befunde als Issues zurück in den Loop; neues Benutzerhandbuch | E: Release Electrip 2.0 |

Der Sound kommt vor der Oberfläche (ADR 0011): Er braucht sie kaum, und die Sound-Modelle sind das größte Risiko.
B-03, B-05 und B-19 prüft man mit Screenshots, deshalb gehören sie zur Oberfläche in Phase 3.
Tor B verlangt zusätzlich einen Fahrtest an der echten Anlage über den Steuerkanal.

Phase 0 ist die wichtigste: Ohne Simulatoren, Golden-Tests und Katalog produziert der Loop schnell Code, dessen Richtigkeit niemand prüfen kann.

## Risiken

| Risiko | Folge | Gegenmaßnahme |
| --- | --- | --- |
| Bluetooth: wenige A2DP-Verbindungen je Adapter, PipeWire-Probleme mit mehreren Geräten, 100–300 ms Latenz | N-05 nur mit 2–3 Loks oder spürbar verzögert | In 2.0 nur System-Audiogerät; Bluetooth-direkt vs. WLAN-Empfänger später per Spike entscheiden |
| Z21: begrenzte Lok-Abos pro Client, kein LOCK | N-03 unvollständig | Spezifikation genau umsetzen, Sperre auf App-Ebene über die Synchronisation |
| Z21-Treiber entsteht im Blindflug (keine Z21 vorhanden) | Simulator und Treiber teilen dieselben Missverständnisse der Spezifikation; Fehler zeigen sich erst bei echten Nutzern | Simulator und Treiber in getrennten Agenten-Sitzungen bauen; Gegenprobe gegen z21aio und Z21ServerEmulator; Z21-Treiber in 2.0 als „experimentell“, Stufe „abgenommen“ offen bis ein Tester mit Z21 gefunden ist |
| Parität wird überschätzt (ArtCraft-Effekt) | Funktion „vorhanden“, aber falsch | Drei Statusstufen, Golden-Tests gegen Alt-Electrip |
| Komplexe Logik (Sound-Modelle) migriert schlecht | Fallstudie VB6: nur ca. 47 % Äquivalenz bei komplexen Funktionen | Sound-Modelle zuerst als Golden-Tests festschreiben, dann umsetzen |
| Agenten brechen Bestehendes | Rückschritte | CI-Pflicht vor Merge, Prüf-Agent, kleine PRs |

## Entscheidungen

- [x] Rust + Slint (24.10.2026)
- [x] Lok-Datenbank: CRDT (Automerge), jede Instanz kann synchronisieren; ein dauerhaft laufender Rechner kann optional als stets erreichbarer Partner dienen
- [x] Audio: Architektur erlaubt mehrere Audio-Ziele; umgesetzt wird zuerst nur „System-Audiogerät pro Lok“. Bluetooth vs. WLAN bleibt offen.
- [x] Lizenz: GPLv3 bleibt
- [x] Budget: ein Claude-Team-Premium-Platz, keine zusätzlichen API-Kosten
- [x] Z21: Umsetzung ohne Hardware, Treiber in 2.0 experimentell
- [x] Zeilenbudget: höchstens 12.000 Zeilen Produktcode; kein MCP-Server in 2.0
- [x] Einfachheits-Review (DRY, YAGNI, KISS) nach jedem Inkrement, Befunde werden sofort refactort

## Budget und Laufzeit

Der Loop läuft ausschließlich über Mos Claude-Team-Premium-Platz (Claude Code mit Abo-Login, auch headless mit `claude -p`). Begrenzend ist damit nicht Geld, sondern das Nutzungslimit des Platzes; auch Prüf- und Aufräum-Agenten zählen darauf.

- Es läuft **ein** Agent im Loop, Sitzungen nacheinander.
- Der Loop-Runner erkennt das Erreichen des Limits, beendet die Sitzung sauber (Commit, `PROGRESS.md`) und setzt nach dem Zurücksetzen des Limits fort.
- Sitzungen bleiben kurz und fokussiert (eine Anforderung), Tests liefern knappe Ausgaben, Logs gehen in Dateien – das spart Kontext.
- Prüf- und Aufräum-Agent laufen je Phase statt je Pull Request.

Zielumfang höchstens 12.000 Zeilen Produktcode plus geschätzt 6.000–10.000 Zeilen Tests und Werkzeuge. Weniger Code senkt auch den Verbrauch: Jede Sitzung muss weniger lesen. Unter einem einzelnen Abo-Limit ist trotzdem mit mehreren Wochen Kalenderzeit zu rechnen. Der größte Posten bleibt Mos Zeit für Spezifikation und Hardware-Tests.

## Quellen

- [Electrip auf SourceForge](https://sourceforge.net/projects/electrip/) – inkl. Git-Repository und `benutzerhandbuch.pdf`
- [SRCP 0.8.4 Spezifikation](https://srcpd.sourceforge.net/srcp/srcp-084.html)
- [z21aio](https://pypi.org/project/z21aio/) · [Z21ServerEmulator](https://git.disroot.org/gfgit/Z21ServerEmulator/blame/branch/master/README.md)
- [PipeWire-Issue: mehrere Bluetooth-Geräte](https://gitlab.freedesktop.org/pipewire/pipewire/-/issues/2401)
- [Anthropic: Effective harnesses for long-running agents](https://anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Anthropic: Building a C compiler with parallel Claudes](https://anthropic.com/engineering/building-c-compiler)
- [Ralph-Loop (Geoffrey Huntley)](https://devinterrupted.substack.com/p/inventing-the-ralph-wiggum-loop-creator)
- [PhotoCraft README](https://github.com/storytold/photocraft) · [ArtCraft-Analyse (syskb)](https://syskb.com/artcraft-claude-code-rust/) · [Phoronix](https://www.phoronix.com/news/Photocraft-Filmcraft-AI)
- [Fallstudie Legacy-Migration mit Coding-Agenten](https://arxiv.org/abs/2608.28972)
- [GitHub Spec Kit](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
