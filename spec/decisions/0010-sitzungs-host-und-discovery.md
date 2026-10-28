# 0010 – Sitzungs-Host pro Zentrale und Discovery per mDNS
**Status:** Vorschlag · 2026-10-28

**Kontext:** Electrip rechnet Beschleunigungsrampen, Sound-Modelle und das soundsynchrone Anfahren (B-13) selbst; die Zentrale meldet nur Fahrstufen zurück. Steuern mehrere Instanzen dieselbe Lok, würden getrennt gerechnete Rampen gegeneinander arbeiten und Sounds aus ungenauen Rückmeldungen geraten werden. Geprüfte Optionen: A) kein Server, Abgleich über die Zentrale; B) eigener Server; C) wechselnder Lok-Besitzer; D) Host-Rolle in jeder Instanz; E) Rampe im Decoder (verworfen: Electrip kennt dann die echte Geschwindigkeit nicht).
**Entscheidung:** Option D.
- Jede Instanz kann **Sitzungs-Host** sein. Pro Zentralen-ID gibt es genau einen Host; nur er ist mit der Zentrale verbunden. Er hält den Lok-Zustand (Geschwindigkeit, Richtung, Funktionen, laufende Rampe, Sound-Phase), rechnet Rampen, Sound-Modelle und B-13 und schickt Audio-Ereignisse an die Audio-Ziele.
- Clients senden nur Eingaben und empfangen den Zustand. Eine einzelne Instanz ist Host und Client in einem Prozess (Phase 1).
- **Ein Protokoll:** Steuerkanal (Agenten, Tests, Skripte) und Client-Host-Verbindung sind derselbe JSON-Strom – Befehle hinein, Zustand heraus, lokal oder übers Netz.
- **Konfliktregel:** zuletzt aktive Eingabe gewinnt; ausgelenkte Achse rampt vom aktuellen Wert weiter. Fremde Änderungen an der Zentrale übernimmt der Host als neuen Ausgangswert.
- **Discovery:** ein mDNS/DNS-SD-Diensttyp `_electrip._tcp` (Bibliothek `mdns-sd`). Jede Instanz veröffentlicht Instanz-ID, Protokollversion und ggf. die Zentralen-ID, für die sie Host ist. Zentralen-ID: Z21-Seriennummer bzw. aufgelöste LAN-IP + Port + Bus bei srcpd.
- **Start:** ca. 2 s suchen; Host gefunden → verbinden, sonst selbst Host. **Doppel-Host:** kleinere Instanz-ID bleibt Host. **Host-Ausfall:** ein Client wird neuer Host und liest den Zustand von der Zentrale zurück; laufende Rampen und Sound-Phase starten neu.
- **Rückfall:** manuell eingetragene Host-Adresse, wenn mDNS blockiert ist (Gäste-WLAN, VLANs). Ohne Netzwerkzugriff läuft die Instanz allein.
- **Konfigurations-Sync** (ADR 0003) nutzt dieselbe Discovery: nach dem Verbinden Konfigurations-IDs austauschen, gemeinsame per CRDT abgleichen – auch ohne Host.
- **Sicherheit:** dem lokalen Netz wird vertraut (wie bei srcpd und Z21); ein Anlagen-Kennwort ist nicht Teil von 2.0.
**Konsequenzen:** Ersetzt in ADR 0003 den Teil „Lok-Zustand kommt aus den Rückmeldungen der Zentrale“ für den Mehr-Instanzen-Fall. Kein eigenes Server-Programm; ein Pi kann die Host-Rolle headless dauerhaft übernehmen. Testbar per docker-compose (Multicast im Bridge-Netz) und durch eine austauschbare Discovery-Schnittstelle.
