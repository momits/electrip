#!/usr/bin/env bash
# Runs on the host: starts the devcontainer, writes the tokens into the
# directory of user keeper, whose auth proxy uses them, and clones the repo on
# first start. Needs CLAUDE_CODE_OAUTH_TOKEN and GH_TOKEN.
set -euo pipefail
cd "$(dirname "$0")/.."

claude_token=$CLAUDE_CODE_OAUTH_TOKEN github_token=$GH_TOKEN
unset CLAUDE_CODE_OAUTH_TOKEN GH_TOKEN
id=$(devcontainer up --workspace-folder . | tail -n 1 | jq -r .containerId)
for name in claude github; do
  token_var=${name}_token
  printf %s "${!token_var}" |
    docker exec -i -u keeper "$id" sh -c "umask 077; cat >/etc/electrip-secrets/$name"
done
devcontainer exec --workspace-folder . bash -c '[ -d .git ] || git clone -q http://127.0.0.1:8080/github-git/ .'
echo "Ready. Start the loop with: devcontainer exec --workspace-folder . ./loop.sh"
