#!/usr/bin/env bash
# Runs on the host: builds the image and (re)creates the container electrip,
# writes the tokens into the directory of user keeper, whose auth proxy uses
# them, and clones the repo into the volume electrip-workspace on first start.
# Needs CLAUDE_CODE_OAUTH_TOKEN and GH_TOKEN.
set -euo pipefail
cd "$(dirname "$0")/.."

claude_token=$CLAUDE_CODE_OAUTH_TOKEN github_token=$GH_TOKEN
unset CLAUDE_CODE_OAUTH_TOKEN GH_TOKEN

if [ -n "$(docker ps -q --filter name=^electrip$)" ]; then
  echo "ERROR container electrip is running, stop it first: docker stop electrip" >&2
  exit 1
fi
docker build -q -f .devcontainer/Dockerfile -t electrip . >/dev/null
docker rm electrip >/dev/null 2>&1 || true
docker run -d --name electrip --init --cap-add=NET_ADMIN \
  -v electrip-workspace:/workspaces/electrip -w /workspaces/electrip \
  --env-file .devcontainer/container.env electrip sleep infinity >/dev/null

docker exec electrip sudo /usr/local/bin/init-sandbox.sh
store_token() {
  printf %s "$2" | docker exec -i -u keeper electrip sh -c "umask 077; cat >/etc/electrip-secrets/$1"
}
store_token claude "$claude_token"
store_token github "$github_token"
docker exec electrip bash -c '[ -d .git ] || git clone -q http://127.0.0.1:8080/github-git/ .'
echo "Ready. Start the loop with: docker exec -it electrip ./loop.sh"
