# Devcontainer und Loop

Der Devcontainer enthält Rust, Python für den Golden-Harness, srcpd, die GitHub-CLI und Claude Code.
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
- **Firewall:** `init-firewall.sh` sperrt bei jedem Start allen ausgehenden Verkehr, auch DNS.
  Nur tinyproxy darf nach außen, und er lässt nur die Hosts aus `allowlist` durch: Anthropic-API, GitHub und crates.io.
  `loop.sh` startet nur, wenn die Firewall aktiv ist.
- **Kein sudo:** Der Nutzer `vscode` darf als root nur `init-firewall.sh` ausführen.
  Firewall und Proxy kann er weder ändern noch beenden.
- **Gepinnte Downloads:** Das Basis-Image ist per Digest gepinnt, Claude Code per Version und SHA-256, Rust über `rust-toolchain.toml`.
  Alles Weitere kommt aus signierten Debian-Paketen.
  Claude Code aktualisiert sich nicht selbst und sendet keine Telemetrie.
  Für ein Update die Pins im `Dockerfile` ändern und das Image neu bauen.

Was bleibt: Der Agent kennt beide Tokens und könnte sie über die erlaubten Hosts nach außen geben, etwa in einem Gist auf GitHub.
Deshalb haben die Tokens nur die nötigen Rechte, und GitHub prüft serverseitig mit.

## Einmalig auf dem Rechner

```sh
claude setup-token                       # Token für Mos Claude-Platz, gilt ein Jahr
export CLAUDE_CODE_OAUTH_TOKEN=…         # Ausgabe von setup-token
export GH_TOKEN=…                        # siehe unten
npm install -g @devcontainers/cli@0.80.0
```

`GH_TOKEN` ist ein Fine-grained Token nur für `momits/electrip` mit kurzer Laufzeit.
Er braucht Schreibrecht auf „Contents“ und „Pull requests“ sowie Leserecht auf „Actions“.
Ohne das Recht „Workflows“ kann der Agent die CI nicht ändern.

Auf GitHub für `main` ein Ruleset anlegen: Pull Request und grüne Status-Checks sind Pflicht, nur Mo darf das umgehen.
In den Repo-Einstellungen muss „Allow rebase merging“ an sein.

## Starten und beenden

```sh
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . ./loop.sh
```

Nur die devcontainer-CLI nutzen, nicht VS Code.
VS Code reicht SSH-Agent und Git-Zugangsdaten des Rechners in den Container durch.

- Jede Sitzung schreibt ihr Protokoll als JSON Lines nach `logs/` im Volume.
  Lesen mit `devcontainer exec --workspace-folder . ls logs`.
  Im Terminal erscheint nur die letzte Nachricht der Sitzung.
- Erreicht eine Sitzung das Nutzungslimit, wartet `loop.sh` 30 Minuten und setzt dieselbe Sitzung fort.
  Das wiederholt sich, bis das Limit zurückgesetzt ist.
  `LIMIT_WAIT` setzt die Wartezeit in Sekunden.
- Nach drei Fehlschlägen in Folge, etwa ohne gültiges Token, bricht `loop.sh` ab.
- `devcontainer exec --workspace-folder . touch STOP` beendet den Loop nach der laufenden Sitzung.
  Der Agent legt `STOP` selbst an, wenn er ohne Mo nicht weiterkommt.
  Vor dem nächsten Start `STOP` löschen.

## Pull Requests

Jede Aufgabe kommt über einen eigenen Pull Request nach `main`.
Der Agent erstellt ihn, wartet auf die grüne CI und merged ihn selbst mit Rebase, damit die Commits mit Trailer erhalten bleiben.
Es läuft immer nur ein Loop mit einem Agenten (ADR 0007).
