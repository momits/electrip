# Z21-Simulator

Der Simulator spielt eine Roco Z21 per UDP nach.
Er entsteht nur aus der Roco-Spezifikation „Z21 LAN Protokoll“ (ADR 0005), nicht aus anderen Implementierungen.
Er dient als Gegenstelle für die Szenario-Testsuite von N-02 und N-03.

## Quelle

- Z21 LAN Protokoll Spezifikation, Dokumentenversion 1.13 vom 06.11.2023, Z21 FW 1.43.
- Download: <https://www.z21.eu/media/Kwc_Basic_DownloadTag_Component/47-1652-959-downloadTag/default/69bad87e/1699290251/z21-lan-protokoll.pdf>
- SHA-256 des PDF: `4bd094ff09d05cafba61c21f79d142af798dc078def1ed596b698b2a169e7cdd`

Das PDF liegt nicht im Repo, weil Roco die Rechte daran hält.
Kapitelnummern in Code und Tests beziehen sich auf diese Version.

## Aufruf

```sh
cargo run -p electrip-sim-z21                    # auf 127.0.0.1:21105
cargo run -p electrip-sim-z21 -- 0.0.0.0:21105   # im ganzen Netz
```

Rust-Tests rufen `electrip_sim_z21::serve` mit einem eigenen Socket auf oder treiben `Z21::handle` direkt mit virtueller Uhr.

## Umfang

Der Simulator kennt die Befehle für Verbinden, Gleisstrom, Fahren, Funktionen und Nothalt:

- Kapitel 2: Seriennummer, Abmelden, X-Bus-Version, Status, Gleisstrom an und aus, Nothalt, Firmware-Version, Broadcast-Flags, Systemzustand, Hardware-Info.
- Kapitel 3: Lok-Format DCC oder MM lesen und setzen.
- Kapitel 4: Lok-Info und Abo, Fahren mit 14, 28 und 128 Fahrstufen, Einzelfunktionen und Funktionsgruppen F0–F31, Lok-Nothalt.
  Funktionsgruppen ab F32 nimmt er ohne Rückmeldung an, wie die Spezifikation es beschreibt.
- Mehrere Datensätze in einem UDP-Paket (1.3), Abmeldung nach einer Minute ohne Nachricht (1.1), höchstens 16 Lok-Abos je Client (4).

Alles andere fehlt bewusst: Freischaltcode, Binärzustände, Lok herausnehmen, Weichen, CV-Programmierung, R-Bus, RailCom, LocoNet, CAN, zLink und Modellzeit.
Unbekannte LAN-Header bleiben ohne Antwort.

## Annahmen, wo die Spezifikation schweigt

Der Z21-Treiber darf sich auf diese Annahmen nicht verlassen.
Er folgt allein der Spezifikation.

1. Der Gleisstrom ist beim Start an.
2. Wer Gleisstrom oder Nothalt schaltet, bekommt die Meldung immer, auch ohne Broadcast-Flag.
   Andere Clients bekommen sie nur mit Flag 0x00000001.
3. Flag 0x00010000 wirkt nur zusammen mit Flag 0x00000001, weil es dieses laut 2.16 „ergänzt“.
4. Eine neue Lok meldet 128 Fahrstufen, Stillstand, Richtung rückwärts und alle Funktionen aus.
5. `LAN_X_SET_STOP` ändert nur den Zentralenstatus.
   Die Zustände der Loks bleiben, und es gehen keine Lok-Infos hinaus.
6. Fahr- und Funktionsbefehle gelten auch bei abgeschaltetem Gleisstrom oder Nothalt.
7. `LAN_SYSTEMSTATE_DATACHANGED` geht nur bei einer Änderung des Zentralenstatus hinaus, nicht regelmäßig.
   Ströme, Spannungen und Temperatur sind feste Werte.
8. Ungültige X-Befehle beantwortet der Simulator mit `LAN_X_UNKNOWN_COMMAND`.
   Dazu zählen eine falsche Prüfsumme, unbekannte Befehle, das Fahrstufenformat S=1, der Umschalttyp 11 und Funktionen über F31.
9. In Lok-Infos sind die beiden höchsten Bits von Adr_MSB immer 0.

## Gegenprobe mit z21aio

`crosscheck.py` spielt die Szenarien mit der unabhängigen Python-Bibliothek [z21aio](https://pypi.org/project/z21aio/) 1.0.7 durch.
Ein Client schaltet, ein zweiter muss die Änderungen als Broadcast sehen.
Der CI-Job „Z21 simulator“ führt die Gegenprobe aus.

```sh
cargo run -p electrip-sim-z21 &
uv run --no-project --with z21aio==1.0.7 python sim/z21/crosscheck.py
```
