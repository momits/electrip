# Devcontainer und Loop

Der Devcontainer enthält Rust, Python für den Golden-Harness, Docker für die Simulatoren, die GitHub-CLI und Claude Code.
`loop.sh` startet darin Agenten-Sitzungen nacheinander mit `prompts/session.md`.
Die Sitzungen laufen ohne Rückfragen und ohne Rechteprüfung, deshalb startet `loop.sh` nur im Container.

## Einmalig auf dem Rechner

```sh
claude setup-token                 # Token für Mos Claude-Platz, gilt ein Jahr
export CLAUDE_CODE_OAUTH_TOKEN=…   # Ausgabe von setup-token
export GH_TOKEN=…                  # GitHub-Token für momits/electrip: Schreibrecht auf Inhalte und Pull Requests, Leserecht auf Actions
npm install -g @devcontainers/cli  # oder VS Code mit der Erweiterung „Dev Containers“
```

Beide Tokens reicht der Container aus der Umgebung des Rechners durch.
Git nutzt im Container HTTPS mit `GH_TOKEN`, auch wenn `origin` eine SSH-Adresse ist.
Commits aus dem Container tragen den Autor „Claude (Electrip-Loop)“.

## Starten und beenden

```sh
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . ./loop.sh
```

- Jede Sitzung schreibt ihr Protokoll als JSON Lines nach `logs/`.
  Im Terminal erscheint nur die letzte Nachricht der Sitzung.
- Erreicht eine Sitzung das Nutzungslimit, wartet `loop.sh` 30 Minuten und setzt dieselbe Sitzung fort.
  Das wiederholt sich, bis das Limit zurückgesetzt ist.
  `LIMIT_WAIT` setzt die Wartezeit in Sekunden.
- Nach drei Fehlschlägen in Folge, etwa ohne gültiges Token, bricht `loop.sh` ab.
- `touch STOP` beendet den Loop nach der laufenden Sitzung.
  Der Agent legt `STOP` selbst an, wenn er ohne Mo nicht weiterkommt.
  Vor dem nächsten Start `STOP` löschen.

## Pull Requests

Jede Aufgabe kommt über einen eigenen Pull Request nach `main`.
Der Agent erstellt ihn, wartet auf die grüne CI und merged ihn selbst mit Rebase, damit die Commits mit Trailer erhalten bleiben.
Es läuft immer nur ein Loop mit einem Agenten (ADR 0007).
