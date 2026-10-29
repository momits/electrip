#!/usr/bin/env bash
# Runs agent sessions one after another with prompts/session.md (spec/phase0-plan.md, step 4).
# Sessions run without permission checks, so the loop only starts behind the
# devcontainer firewall, which allows outgoing traffic only through its proxy.
# Each session logs to logs/. The loop ends when the file STOP exists.
set -euo pipefail
cd "$(dirname "$0")"

LIMIT_WAIT=${LIMIT_WAIT:-1800} # seconds between attempts while the usage limit holds
FAILURE_WAIT=60
MAX_FAILURES=3
RESUME_PROMPT="Das Nutzungslimit ist zurückgesetzt. Mach dort weiter, wo du aufgehört hast."

if curl -s -o /dev/null --max-time 5 --noproxy '*' https://api.anthropic.com; then
  echo "ERROR loop.sh only runs behind the devcontainer firewall" >&2
  exit 1
fi
mkdir -p logs

# Prints the last result message of a session log, or nothing if there is none.
result_of() {
  jq -cR 'fromjson? | select(.type == "result")' "$1" | tail -n 1
}

# The session id lets a session that hit the usage limit continue with its context.
session_of() {
  jq -rR 'fromjson? | .session_id // empty' "$1" | head -n 1
}

failures=0
resume=()
while [ ! -e STOP ]; do
  if [ ${#resume[@]} -eq 0 ]; then prompt=$(cat prompts/session.md); else prompt=$RESUME_PROMPT; fi
  log="logs/$(date +%Y%m%d-%H%M%S).jsonl"
  echo "$(date '+%F %T') session ${resume[*]:-new} -> $log"
  status=0
  claude -p "$prompt" "${resume[@]}" --dangerously-skip-permissions \
    --output-format stream-json --verbose >"$log" 2>&1 || status=$?
  result=$(result_of "$log")
  is_error=true # a session without a result line failed
  if [ -n "$result" ]; then
    is_error=$(jq -r '.is_error' <<<"$result")
    text=$(jq -r '.result // ""' <<<"$result")
  else
    text=$(tail -n 1 "$log")
  fi
  echo "$text"

  if [ $status -eq 0 ] && [ "$is_error" = false ]; then
    failures=0
    resume=()
  elif grep -qiE "hit your .*limit|usage limit" <<<"$text"; then
    sid=$(session_of "$log")
    if [ -n "$sid" ]; then resume=(--resume "$sid"); fi
    echo "$(date '+%F %T') usage limit, next attempt in ${LIMIT_WAIT}s"
    sleep "$LIMIT_WAIT"
  else
    failures=$((failures + 1))
    resume=()
    if [ $failures -ge $MAX_FAILURES ]; then
      echo "ERROR $failures sessions failed in a row, see $log" >&2
      exit 1
    fi
    sleep "$FAILURE_WAIT"
  fi
done
echo "$(date '+%F %T') STOP found, loop ends"
