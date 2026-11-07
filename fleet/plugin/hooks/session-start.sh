#!/usr/bin/env bash
# session-start.sh — a fleet plugin SessionStart hookja. Egy sor a session
# elejére: ki vagy a flottában, milyen verziójú szabályokkal. Semmi külső
# függés (nincs registry, nincs hálózat): a repó .claude/fleet.json-ját
# olvassa, és ha nincs, csendben kilép — egy nem-tag repóban nincs mit mondani.
set -uo pipefail
m=".claude/fleet.json"
[ -f "$m" ] || exit 0
agent=$(sed -n 's/.*"agent": *"\([^"]*\)".*/\1/p' "$m" | head -1)
fleet=$(sed -n 's/.*"fleet": *"\([^"]*\)".*/\1/p' "$m" | head -1)
[ -n "$agent" ] || exit 0
echo "[fleet] te vagy: $agent · flotta-szabályok v${fleet:-?} (.claude/rules/fleet.md) · névsor: /fleet:roster · állapot: /fleet:doctor · ágensnek: PR-komment vagy SendMessage"
exit 0
