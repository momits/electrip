# Devcontainer und Loop

Der Devcontainer enthält Rust, Python für den Golden-Harness, srcpd und Claude Code.
`loop.sh` startet darin Agenten-Sitzungen nacheinander mit `prompts/session.md`.
Die Sitzungen laufen ohne Rückfragen und ohne Rechteprüfung.
Deshalb schützt der Container den Rechner und begrenzt, was ein Agent anrichten kann.

## Schutz

- **Eigener Klon:** Der Container klont das Repo beim ersten Start in das Docker-Volume `electrip-workspace`.
  Dein Arbeitsordner ist nicht eingebunden.
  So kann der Agent keine Git-Hooks oder IDE-Konfigurationen ändern, die später auf dem Rechner laufen.
- **Keine Sonderrechte:** Der Container läuft ohne `privileged` und ohne Docker.
  Er hat nur die Fähigkeit `NET_ADMIN` für die Firewall.
  srcpd läuft direkt im Container, `cargo xtask sim up` startet es dort.
- **Tokens unlesbar:** Die Tokens liegen in `/etc/electrip-secrets`, das nur der Nutzer `keeper` lesen kann.
  Unter `keeper` läuft `auth-proxy.py` auf `127.0.0.1:8080`.
  Er setzt die Tokens in Anfragen an die Anthropic-API, an die GitHub-API für dieses Repo und an Git für dieses Repo ein.
  Andere Ziele und andere Repos lehnt er ab.
  Claude Code bekommt nur einen Platzhalter und `ANTHROPIC_BASE_URL`, `origin` zeigt auf den Proxy, `gh` gibt es nicht.
  Der Agent kann die Tokens also benutzen, solange der Container läuft, aber nicht auslesen und mitnehmen.
- **Firewall:** `init-sandbox.sh` sperrt bei jedem Start allen ausgehenden Verkehr, auch DNS.
  Direkt nach außen dürfen nur `keeper` und tinyproxy.
  tinyproxy lässt nur die Hosts aus `allowlist` durch: crates.io und den Speicher für CI-Logs.
  `loop.sh` startet nur, wenn die Firewall aktiv ist.
- **Kein sudo:** Der Nutzer `vscode` darf als root nur `init-sandbox.sh` ausführen.
  Firewall und Proxys kann er weder ändern noch beenden.
- **Gepinnte Downloads:** Das Basis-Image ist per Digest gepinnt, Claude Code per Version und SHA-256, Rust über `rust-toolchain.toml`.
  Alles Weitere kommt aus signierten Debian-Paketen.
  Claude Code aktualisiert sich nicht selbst und sendet keine Telemetrie.
  Für ein Update die Pins im `Dockerfile` ändern und das Image neu bauen.

Was bleibt: Der Agent kann alles tun, was der Proxy ihm erlaubt, also etwa Pull Requests mergen oder über Claude Anfragen stellen.
Deshalb haben die Tokens nur die nötigen Rechte, und GitHub prüft serverseitig mit.

## Einmalig auf dem Rechner

```sh
claude setup-token   # Token für Mos Claude-Platz, gilt ein Jahr
```

Außer Docker braucht es auf dem Rechner nichts.

`GH_TOKEN` ist ein Fine-grained Token nur für `momits/electrip` mit kurzer Laufzeit.
Er braucht Schreibrecht auf „Contents“ und „Pull requests“ sowie Leserecht auf „Actions“ und „Checks“.
Ohne das Recht „Workflows“ kann der Agent die CI nicht ändern.

Auf GitHub für `main` ein Ruleset anlegen: Pull Request und grüne Status-Checks sind Pflicht, nur Mo darf das umgehen.
In den Repo-Einstellungen muss „Allow rebase merging“ an sein.

## Starten und beenden

```sh
CLAUDE_CODE_OAUTH_TOKEN=… GH_TOKEN=… .devcontainer/start.sh
docker exec -it electrip ./loop.sh
```

`start.sh` baut das Image, legt den Container `electrip` neu an und startet Firewall und Proxys.
Es schreibt die Tokens als Nutzer `keeper` in dessen Verzeichnis und klont beim ersten Start das Repo.
Die Tokens landen nur bei `keeper`, nicht in der Umgebung des Containers.
Der Klon liegt im Volume `electrip-workspace` und bleibt beim Neuanlegen erhalten.
Läuft der Container noch, bricht `start.sh` ab; vorher `docker stop electrip`.
Die Umgebung des Containers steht in `container.env`.

Den Container nicht in VS Code öffnen.
VS Code reicht SSH-Agent und Git-Zugangsdaten des Rechners in den Container durch.

- Jede Sitzung schreibt ihr Protokoll als JSON Lines nach `logs/` im Volume.
  Lesen mit `docker exec electrip ls logs`.
  Im Terminal erscheint nur die letzte Nachricht der Sitzung.
- Erreicht eine Sitzung das Nutzungslimit, wartet `loop.sh` 30 Minuten und setzt dieselbe Sitzung fort.
  Das wiederholt sich, bis das Limit zurückgesetzt ist.
  `LIMIT_WAIT` setzt die Wartezeit in Sekunden.
- Nach drei Fehlschlägen in Folge, etwa ohne gültiges Token, bricht `loop.sh` ab.
- `docker exec electrip touch STOP` beendet den Loop nach der laufenden Sitzung.
  Der Agent legt `STOP` selbst an, wenn er ohne Mo nicht weiterkommt.
  Vor dem nächsten Start `STOP` löschen.

## Pull Requests

Jede Aufgabe kommt über einen eigenen Pull Request nach `main`.
Der Agent erstellt ihn, wartet auf die grüne CI und merged ihn selbst mit Rebase, damit die Commits mit Trailer erhalten bleiben.
Es läuft immer nur ein Loop mit einem Agenten (ADR 0007).
