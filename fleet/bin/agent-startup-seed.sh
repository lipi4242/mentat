#!/usr/bin/env bash
# agent-startup-seed.sh — a startup/loop parancs beküldése az ágens tmux
# sessionjébe, MIUTÁN a prompt megjelent.
#
# MIÉRT NEM FIX SLEEP: 2026-08-03-án a telepítéskor a 25 másodperc kevés
# volt, a billentyűk a boot-képernyőre estek és ELVESZTEK — a processz élt, a
# tmux session megvolt, és az ágens NÉMÁN nem tickelt. Ez a legrosszabb
# hibaosztály: minden felügyeleti jel zöld, a munka mégsem történik meg.
#
# HASZNÁLAT (ExecStartPost a unitban):
#   agent-startup-seed.sh <tmux-session> '<parancs>'
# Kilépési kód mindig 0: ez ExecStartPost, és egy bukó ExecStartPost `failed`-re
# állítaná a unitot, miközben a session fut — félig futó állapot. A hibát a
# `fleet postcheck` / arming látja meg, nem a systemd.
set -uo pipefail
SESSION="${1:-}"; CMD="${2:-}"
[ -n "$SESSION" ] && [ -n "$CMD" ] || { echo "startup-seed: hianyzo argumentum" >&2; exit 0; }
MAX_WAIT_S="${AGENT_PROMPT_WAIT_S:-200}"
# NEM `TMUX`: az a tmux saját környezeti változója (a socket útja). Egy tmux-sessionből
# futtatva felülírná, és a kliens a bináris útját nyitná socketként.
TMUX_BIN="${AGENT_TMUX_BIN:-/usr/bin/tmux}"
# Pane-cél: "=név:" — a tmux 3.6 a csupasz "=név"-et capture-pane/send-keys
# alatt nem oldja fel ("can't find pane"), és a seed 200 s után némán feladta
# (2026-10-14, két ágens friss indításkor tick nélkül maradt).
TARGET="=$SESSION:"
waited=0; ready=0
while [ "$waited" -lt "$MAX_WAIT_S" ]; do
    sleep 5; waited=$((waited + 5))
    if "$TMUX_BIN" capture-pane -p -t "$TARGET" 2>/dev/null | grep -q "bypass permissions"; then
        ready=1; break
    fi
done
if [ "$ready" -ne 1 ]; then
    # Prompt nelkul NEM kuldunk: a boot-kepernyore esett billentyu elveszik, es
    # a "bekuldtem" hamis nyugta lenne. A postcheck/arming latja majd a hianyt.
    echo "startup-seed[$SESSION]: a prompt ${MAX_WAIT_S}s alatt nem jelent meg — NEM kuldok" >&2
    exit 0
fi
sleep 5
# -l: szo szerinti szoveg (a tmux kulcsnev-ertelmezese nelkul), az Enter kulon.
if "$TMUX_BIN" send-keys -t "$TARGET" -l "$CMD" 2>/dev/null && "$TMUX_BIN" send-keys -t "$TARGET" Enter 2>/dev/null; then
    echo "startup-seed[$SESSION]: '$CMD' bekuldve ${waited}s utan"
else
    echo "startup-seed[$SESSION]: send-keys sikertelen" >&2
fi
exit 0
