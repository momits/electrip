# 0003 – Lok-Datenbank als CRDT
**Status:** Vorschlag · 2026-10-26

**Kontext:** Mehrere Instanzen auf verschiedenen Geräten teilen Loks (N-04). Z21-Nutzer haben oft keinen dauerhaft laufenden Rechner.
**Entscheidung:** Lok-Datenbank als Automerge-Dokument. Jede Instanz hat eine Sync-Rolle (Partnersuche per mDNS, Austausch von Änderungen, Medien per SHA-256 adressiert). Ein dauerhaft laufender Rechner kann dieselbe Rolle headless übernehmen.
**Konsequenzen:** Offline-Änderungen werden automatisch zusammengeführt; Medien brauchen einen eigenen Übertragungsweg; Historie wächst mit.
