#!/bin/bash
# Runs as root at every container start. Starts the auth proxy as user keeper,
# which alone holds the tokens, and tinyproxy for the hosts in
# /etc/tinyproxy/allowlist. All other outgoing traffic is blocked.
# Absolute paths, so the caller's PATH cannot swap in other programs.
set -euo pipefail

/usr/bin/pkill -x tinyproxy || true
/usr/bin/pkill -u keeper || true
/usr/bin/tinyproxy -c /etc/tinyproxy/tinyproxy.conf
cd / # not in a directory the caller controls
ulimit -c 0
/usr/bin/setsid -f /usr/sbin/runuser -u keeper -- /usr/bin/python3 -I \
  /usr/local/lib/electrip/auth-proxy.py >>/var/log/auth-proxy.log 2>&1
# Only localhost itself: Docker's DNS resolver on 127.0.0.11 stays blocked.
for rule in "/usr/sbin/iptables 127.0.0.1" "/usr/sbin/ip6tables ::1"; do
  read -r ipt localhost <<<"$rule"
  $ipt -P OUTPUT DROP
  $ipt -F OUTPUT
  $ipt -A OUTPUT -m owner --uid-owner tinyproxy -j ACCEPT
  $ipt -A OUTPUT -m owner --uid-owner keeper -j ACCEPT
  $ipt -A OUTPUT -o lo -d "$localhost" -j ACCEPT
  $ipt -A OUTPUT -j REJECT
done
