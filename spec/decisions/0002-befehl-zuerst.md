# 0002 – Befehl zuerst, GUI-freier Kern
**Status:** Vorschlag · 2026-10-26

**Kontext:** Agenten und Tests müssen die App ohne Oberfläche bedienen können.
**Entscheidung:** Jede Nutzeraktion ist ein Befehl in `core`. UI, Gamepad, Steuerkanal und Tests rufen nur Befehle auf. Ein lokaler JSON-Steuerkanal (`control`) erlaubt Zustand lesen, Befehle senden, virtuelle Eingaben und Screenshots.
**Konsequenzen:** Keine Fachlogik in `ui`. Ein MCP-Server ist in 2.0 nicht vorgesehen und kann später als Hülle um den Steuerkanal entstehen.
