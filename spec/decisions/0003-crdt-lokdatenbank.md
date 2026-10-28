# 0003 – Konfigurationen als CRDT, Lok-Zustand über die Zentrale
**Status:** Angenommen · 2026-10-28 (Vorschlag vom 2026-10-28)

**Kontext:** Es gibt mehrere Konfigurationen; mehrere Instanzen sollen dieselbe Konfiguration gleichzeitig nutzen und bearbeiten (N-04). Dieselbe Lok-Adresse kann in mehreren Konfigurationen vorkommen. Z21-Nutzer haben oft keinen dauerhaft laufenden Rechner.
**Entscheidung:**
- Jede Konfiguration ist ein eigenes Automerge-Dokument. Jede Instanz hat eine Sync-Rolle (Partnersuche per mDNS, Austausch von Änderungen, Medien per SHA-256 adressiert). Ein dauerhaft laufender Rechner kann dieselbe Rolle headless übernehmen.
- Der Lok-Zustand (Geschwindigkeit, Richtung, Funktionen) gehört **nicht** in die Konfiguration. Er ist an die Lok-Adresse gebunden, kommt aus den Rückmeldungen der Zentrale (SRCP INFO-Session, Z21-Broadcasts) und ist dadurch in allen Instanzen und Konfigurationen synchron. Es gilt der zuletzt an der Zentrale angekommene Befehl; es gibt keine Sperren.
**Hinweis:** Für den Lok-Zustand bei mehreren Instanzen gilt ADR 0010 (Sitzungs-Host); die Zentrale bleibt Quelle für Änderungen fremder Programme und für die Wiederherstellung nach Host-Ausfall.
**Konsequenzen:** Konfigurationsänderungen werden automatisch zusammengeführt (gleiches Feld: letzte Änderung gilt); Fahrzustand braucht keinen eigenen Sync-Mechanismus; Medien brauchen einen eigenen Übertragungsweg.
