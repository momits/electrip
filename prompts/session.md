# Sitzung im Loop

Du arbeitest allein im autonomen Loop von `loop.sh`.
Niemand beantwortet während der Sitzung Fragen.
Es gelten die Regeln und der Sitzungsablauf aus `AGENTS.md`.
Dieser Prompt ergänzt nur, was im Loop dazukommt.

Im Container gibt es kein `gh` und keine Tokens.
Ein lokaler Proxy setzt die Tokens ein:

- `origin` zeigt auf `http://127.0.0.1:8080/github-git/`, `git pull` und `git push` funktionieren normal.
- Die GitHub-REST-API für dieses Repo erreichst du mit `curl` unter `http://127.0.0.1:8080/github-api/repos/momits/electrip/…`.
  Beispiele: `actions/runs?branch=main&per_page=1`, `pulls` (POST zum Erstellen), `commits/<sha>/check-runs`, `pulls/<n>/merge` (PUT mit `{"merge_method": "rebase"}`), `actions/jobs/<id>/logs` (mit `curl -L`).
  Andere Pfade lehnt der Proxy ab.

1. Bist du nicht auf `main` oder ist der Arbeitsbaum nicht sauber, wurde die letzte Sitzung abgebrochen.
   Committe den Zwischenstand auf dem aktuellen Branch und schließe diese Aufgabe nach Schritt 3 zuerst ab.
2. Wechsle auf `main` und hole den neuesten Stand mit `git pull --rebase`.
3. Prüfe die CI des letzten Commits auf `main`.
   Ist sie rot, repariere das zuerst.
4. Wähle Aufgaben nur aus der niedrigsten Phase mit offenen Anforderungen.
   Eine Phase beginnt erst, wenn Mo das Tor davor in `PROGRESS.md` abgehakt hat.
5. Bearbeite genau eine Aufgabe nach `AGENTS.md`, bis ihr Pull Request gemerged ist.
   Wechsle danach auf `main`.
   Damit endet die Sitzung, `loop.sh` startet die nächste.
6. Gibt es keine Aufgabe, die du ohne Mo erledigen kannst, trage das mit Grund in `PROGRESS.md` ein und bringe es per Pull Request nach `main`.
   Gründe sind etwa: alles erledigt, offene Fragen in `spec/questions.md`, ein Tor oder ein Hardware-Test.
   Lege danach die Datei `STOP` im Wurzelverzeichnis an, damit `loop.sh` endet.

Deine letzte Nachricht ist eine einzige Zeile: Aufgabe, Ergebnis, Link zum Pull Request.
