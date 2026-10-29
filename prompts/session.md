# Sitzung im Loop

Du arbeitest allein im autonomen Loop von `loop.sh`.
Niemand beantwortet während der Sitzung Fragen.
Es gelten die Regeln und der Sitzungsablauf aus `AGENTS.md`.
Dieser Prompt ergänzt nur, was im Loop dazukommt.

1. Bist du nicht auf `main` oder ist der Arbeitsbaum nicht sauber, wurde die letzte Sitzung abgebrochen.
   Committe den Zwischenstand auf dem aktuellen Branch und schließe diese Aufgabe nach Schritt 3 zuerst ab.
2. Wechsle auf `main` und hole den neuesten Stand mit `git pull --rebase`.
3. Prüfe die CI des letzten Commits auf `main` mit `gh run list --branch main --limit 1`.
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
