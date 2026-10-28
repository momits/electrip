# 0003 – Konfigurationen als CRDT, Lok-Zustand über die Zentrale
**Status:** Vorschlag · 2026-10-28 (überarbeitet)

**Kontext:** Es gibt mehrere Konfigurationen; mehrere Instanzen sollen dieselbe Konfiguration gleichzeitig nutzen und bearbeiten (N-04). Dieselbe Lok-Adresse kann in mehreren Konfigurationen vorkommen. Z21-Nutzer haben oft keinen dauerhaft laufenden Rechner.
**Entscheidung:**
- Jede Konfiguration ist ein eigenes Automerge-Dokument. Jede Instanz hat eine Sync-Rolle (Partnersuche per mDNS, Austausch von Änderungen, Medien per SHA-256 adressiert). Ein dauerhaft laufender Rechner kann dieselbe Rolle headless übernehmen.
- Der Lok-Zustand (Geschwindigkeit, Richtung, Funktionen) gehört **nicht** in die Konfiguration. Er ist an die Lok-Adresse gebunden, kommt aus den Rückmeldungen der Zentrale (SRCP INFO-Session, Z21-Broadcasts) und ist dadurch in allen Instanzen und Konfigurationen synchron. Es gilt der zuletzt an der Zentrale angekommene Befehl; es gibt keine Sperren.
**Konsequenzen:** Konfigurationsänderungen werden automatisch zusammengeführt (gleiches Feld: letzte Änderung gilt); Fahrzustand braucht keinen eigenen Sync-Mechanismus; Medien brauchen einen eigenen Übertragungsweg.
