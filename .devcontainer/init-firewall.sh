#!/bin/bash
# Blocks all outgoing traffic except through tinyproxy, which only lets through
# the hosts in /etc/tinyproxy/allowlist. Runs as root at every container start.
# Absolute paths, so the caller's PATH cannot swap in other programs.
set -euo pipefail

/usr/bin/pkill -x tinyproxy || true
/usr/bin/tinyproxy -c /etc/tinyproxy/tinyproxy.conf
# Only localhost itself: Docker's DNS resolver on 127.0.0.11 stays blocked.
for rule in "/usr/sbin/iptables 127.0.0.1" "/usr/sbin/ip6tables ::1"; do
  read -r ipt localhost <<<"$rule"
  $ipt -P OUTPUT DROP
  $ipt -F OUTPUT
  $ipt -A OUTPUT -m owner --uid-owner tinyproxy -j ACCEPT
  $ipt -A OUTPUT -o lo -d "$localhost" -j ACCEPT
  $ipt -A OUTPUT -j REJECT
done
